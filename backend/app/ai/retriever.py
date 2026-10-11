"""Hybrid knowledge retrieval: pgvector semantic similarity + category prior.

Degrades gracefully: with no embeddings / no AI, the category prior alone still selects the right
policy section, so drafting and the UI keep working.
"""
import logging
from dataclasses import dataclass, field

from app.ai.errors import AIError
from app.ai.prompts import sanitize_untrusted
from app.ai.providers.base import AIProvider, EmbeddingTask
from app.models.enums import Category
from app.models.knowledge_chunk import KnowledgeChunk
from app.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)

CATEGORY_BOOST = 0.25  # added to cosine similarity (0..1) for chunks mapped to the ticket's category
MIN_SIMILARITY = 0.6   # a chunk outside the ticket's category must be at least this similar to be sent


@dataclass
class RetrievalResult:
    chunks: list[KnowledgeChunk]
    used_vectors: bool
    embedding_calls: int = 0
    embedding_latency_ms: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def chunk_ids(self) -> list[int]:
        return [c.id for c in self.chunks]

    def render(self) -> str:
        return "\n\n".join(f"[{c.title}]\n{c.content}" for c in self.chunks)


class KnowledgeRetriever:
    def __init__(self, repo: KnowledgeRepository, provider: AIProvider | None, top_k: int = 3):
        self._repo = repo
        self._provider = provider
        self._top_k = top_k

    async def retrieve(self, *, query_text: str, category: Category | None) -> RetrievalResult:
        all_chunks = await self._repo.list_all()
        always = [c for c in all_chunks if c.chunk_metadata.get("always_include")]
        candidates = [c for c in all_chunks if not c.chunk_metadata.get("always_include")]

        similarity: dict[int, float] = {}
        result = RetrievalResult(chunks=[], used_vectors=False)
        if self._provider and any(c.embedding for c in candidates):
            try:
                embedded = await self._provider.create_embedding(
                    [sanitize_untrusted(query_text, 1500)], task=EmbeddingTask.QUERY
                )
                hits = await self._repo.similarity_search(embedded.value[0], limit=len(candidates))
                similarity = {chunk.id: score for chunk, score in hits}
                result.used_vectors = True
                result.embedding_calls = 1
                result.embedding_latency_ms = embedded.latency_ms
            except AIError as exc:
                logger.warning("Query embedding failed (%s); using category prior only.", exc.message)
                result.notes.append("Semantic search unavailable; used category matching.")
        elif self._provider:
            result.notes.append("Knowledge embeddings not initialised; used category matching.")

        def in_category(chunk: KnowledgeChunk) -> bool:
            return category is not None and category.value in chunk.chunk_metadata.get("categories", [])

        def score(chunk: KnowledgeChunk) -> float:
            return similarity.get(chunk.id, 0.0) + (CATEGORY_BOOST if in_category(chunk) else 0.0)

        ranked = sorted(candidates, key=lambda c: (-score(c), c.id))
        relevant = [c for c in ranked if in_category(c) or similarity.get(c.id, 0.0) >= MIN_SIMILARITY]
        selected = relevant[: self._top_k]
        if not selected and similarity:  # nothing cleared the bar: still send the single closest chunk
            selected = ranked[:1]
        if not selected:  # no vectors, no category: ground on the general overview
            selected = [c for c in ranked if "General Inquiry" in c.chunk_metadata.get("categories", [])][:1]
        result.chunks = selected + always
        return result
