import math

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_chunk import KnowledgeChunk


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def list_all(self) -> list[KnowledgeChunk]:
        return list((await self._s.execute(select(KnowledgeChunk).order_by(KnowledgeChunk.id))).scalars().all())

    async def get_by_ids(self, ids: list[int]) -> list[KnowledgeChunk]:
        if not ids:
            return []
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids))
        return list((await self._s.execute(stmt)).scalars().all())

    async def get_by_section(self, section: str) -> KnowledgeChunk | None:
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.section == section)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def upsert_section(self, *, section: str, title: str, content: str, metadata: dict) -> KnowledgeChunk:
        chunk = await self.get_by_section(section)
        if chunk is None:
            chunk = KnowledgeChunk(section=section, title=title, content=content, chunk_metadata=metadata)
            self._s.add(chunk)
        else:
            if chunk.content != content:
                chunk.embedding = None  # stale vector: must be regenerated
            chunk.title, chunk.content, chunk.chunk_metadata = title, content, metadata
        await self._s.flush()
        return chunk

    async def counts(self) -> tuple[int, int]:
        total = (await self._s.execute(select(func.count(KnowledgeChunk.id)))).scalar_one()
        embedded = (
            await self._s.execute(select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.embedding.is_not(None)))
        ).scalar_one()
        return total, embedded

    async def similarity_search(self, vector: list[float], limit: int) -> list[tuple[KnowledgeChunk, float]]:
        """Top-`limit` chunks by cosine similarity. pgvector `<=>` on PostgreSQL, Python fallback otherwise."""
        dialect = self._s.get_bind().dialect.name
        if dialect == "postgresql":
            distance = KnowledgeChunk.embedding.op("<=>", return_type=Float)(
                cast(literal("[" + ",".join(f"{x:.8f}" for x in vector) + "]"), Vector(len(vector)))
            )
            stmt = (
                select(KnowledgeChunk, distance.label("distance"))
                .where(KnowledgeChunk.embedding.is_not(None))
                .order_by(distance)
                .limit(limit)
            )
            rows = (await self._s.execute(stmt)).all()
            return [(chunk, 1.0 - float(dist)) for chunk, dist in rows]

        chunks = [c for c in await self.list_all() if c.embedding]
        scored = [(c, _cosine_similarity(vector, c.embedding)) for c in chunks]
        return sorted(scored, key=lambda pair: pair[1], reverse=True)[:limit]
