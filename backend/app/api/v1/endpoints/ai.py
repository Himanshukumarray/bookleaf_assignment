from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIError
from app.ai.knowledge_base import embed_missing_chunks, sync_knowledge_sections
from app.api.dependencies import get_session, get_settings_dep, require_admin
from app.core.config import Settings
from app.core.exceptions import AIUnavailableError
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.ai import AISystemStatus, EmbedResult

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(require_admin)])


@router.get("/status", response_model=AISystemStatus)
async def ai_status(
    session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings_dep)
) -> AISystemStatus:
    total, embedded = await KnowledgeRepository(session).counts()
    return AISystemStatus(
        provider_configured=settings.ai_configured,
        model=settings.gemini_model,
        embedding_model=settings.gemini_embedding_model,
        knowledge_chunks=total,
        knowledge_chunks_embedded=embedded,
    )


@router.post("/knowledge/embed", response_model=EmbedResult)
async def embed_knowledge(request: Request, session: AsyncSession = Depends(get_session)) -> EmbedResult:
    """(Re)generate embeddings for KB sections that lack one. Idempotent."""
    provider = request.app.state.ai_provider
    if provider is None:
        raise AIUnavailableError("AI provider is not configured (set GEMINI_API_KEY).")
    await sync_knowledge_sections(session)
    try:
        count = await embed_missing_chunks(session, provider)
    except AIError as exc:
        raise AIUnavailableError("Could not generate embeddings right now.", details={"reason": exc.error_type}) from exc
    return EmbedResult(embedded_chunks=count)
