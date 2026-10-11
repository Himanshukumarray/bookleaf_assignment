import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.orchestrator import AIOrchestrator
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini import GeminiProvider
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import FailureRateLimiter
from app.db.session import build_engine, build_session_factory
from app.realtime.websocket_manager import ConnectionManager
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
_UNSET = object()


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    ai_provider: AIProvider | None | object = _UNSET,
) -> FastAPI:
    """Application factory. Tests inject a session factory and a fake AI provider."""
    settings = settings or get_settings()
    configure_logging()
    engine = None
    if session_factory is None:
        engine = build_engine(settings)
        session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Author support & communication portal with an AI-assisted triage and drafting pipeline.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    if ai_provider is _UNSET:
        ai_provider = GeminiProvider(settings) if settings.ai_configured else None
        if ai_provider is None:
            logger.warning("GEMINI_API_KEY not set: AI assistance disabled, tickets fall back to manual handling.")

    manager = ConnectionManager()
    notifier = NotificationService(manager)
    app.state.session_factory = session_factory
    app.state.settings = settings
    app.state.login_limiter = FailureRateLimiter(settings.login_max_failures, settings.login_failure_window_seconds)
    app.state.ws_manager = manager
    app.state.notifier = notifier
    app.state.ai_provider = ai_provider
    app.state.orchestrator = AIOrchestrator(
        provider=ai_provider, session_factory=session_factory, settings=settings, notifier=notifier
    )

    app.include_router(api_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "ai_configured": ai_provider is not None}

    return app


app = create_app()
