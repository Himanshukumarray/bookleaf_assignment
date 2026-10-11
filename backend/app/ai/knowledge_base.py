"""Loads the static knowledge base from JSON and (re)computes its embeddings once."""
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIError
from app.ai.providers.base import AIProvider, EmbeddingTask
from app.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)

KB_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.json"


@dataclass(frozen=True)
class KnowledgeSection:
    section: str
    title: str
    content: str
    categories: list[str]
    always_include: bool


def load_sections(path: Path = KB_PATH) -> list[KnowledgeSection]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        KnowledgeSection(
            section=s["section"],
            title=s["title"],
            content=s["content"],
            categories=s.get("categories", []),
            always_include=s.get("always_include", False),
        )
        for s in raw["sections"]
    ]


async def sync_knowledge_sections(session: AsyncSession, sections: list[KnowledgeSection] | None = None) -> int:
    """Idempotently upsert KB text. Changed content invalidates its embedding."""
    repo = KnowledgeRepository(session)
    sections = sections or load_sections()
    for s in sections:
        await repo.upsert_section(
            section=s.section,
            title=s.title,
            content=s.content,
            metadata={"categories": s.categories, "always_include": s.always_include},
        )
    return len(sections)


async def embed_missing_chunks(session: AsyncSession, provider: AIProvider) -> int:
    """Embed only chunks lacking a vector (static KB => generated once, reused for every ticket)."""
    repo = KnowledgeRepository(session)
    pending = [c for c in await repo.list_all() if c.embedding is None]
    if not pending:
        return 0
    try:
        result = await provider.create_embedding(
            [f"{c.title}\n{c.content}" for c in pending], task=EmbeddingTask.DOCUMENT
        )
    except AIError as exc:
        logger.warning("KB embedding failed (%s); retrieval will use category matching only.", exc.message)
        raise
    for chunk, vector in zip(pending, result.value):
        chunk.embedding = vector
    await session.flush()
    return len(pending)
