from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_draft import AIDraft
from app.models.ai_run import AIRun


class AIRepository:
    """Persistence for AI observability (runs) and generated drafts."""

    def __init__(self, session: AsyncSession):
        self._s = session

    def add_run(self, run: AIRun) -> AIRun:
        self._s.add(run)
        return run

    async def save_draft(self, draft: AIDraft) -> AIDraft:
        await self._s.execute(
            update(AIDraft)
            .where(AIDraft.ticket_id == draft.ticket_id, AIDraft.status == "GENERATED")
            .values(status="SUPERSEDED")
        )
        self._s.add(draft)
        await self._s.flush()
        return draft

    async def latest_draft(self, ticket_id: int) -> AIDraft | None:
        stmt = (
            select(AIDraft)
            .where(AIDraft.ticket_id == ticket_id, AIDraft.status != "SUPERSEDED")
            .order_by(AIDraft.id.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_draft(self, draft_id: int) -> AIDraft | None:
        return await self._s.get(AIDraft, draft_id)

    async def recent_runs(self, ticket_id: int, limit: int = 10) -> list[AIRun]:
        stmt = select(AIRun).where(AIRun.ticket_id == ticket_id).order_by(AIRun.id.desc()).limit(limit)
        return list((await self._s.execute(stmt)).scalars().all())
