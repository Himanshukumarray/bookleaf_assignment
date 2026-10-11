"""FastAPI dependency wiring: sessions, auth/RBAC, and service construction."""
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import AIOrchestrator
from app.core.config import Settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.author import Author
from app.models.enums import Role
from app.models.user import User
from app.repositories.author_repository import AuthorRepository
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.author_service import AuthorService
from app.services.book_service import BookService
from app.services.notification_service import NotificationService
from app.services.response_service import ResponseService
from app.services.ticket_service import TicketService

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_notifier(request: Request) -> NotificationService:
    return request.app.state.notifier


def get_orchestrator(request: Request) -> AIOrchestrator:
    return request.app.state.orchestrator


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication required.", code="NOT_AUTHENTICATED")
    claims = decode_access_token(settings, credentials.credentials)
    user = await AuthorRepository(session).get_user(int(claims["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is not available.", code="TOKEN_INVALID")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role is not Role.ADMIN:
        raise ForbiddenError("Admin access required.", code="ADMIN_ONLY")
    return user


@dataclass(frozen=True)
class CurrentAuthor:
    user: User
    author: Author


async def require_author(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> CurrentAuthor:
    if user.role is not Role.AUTHOR:
        raise ForbiddenError("This resource is only available to authors.", code="AUTHOR_ONLY")
    author = await AuthorRepository(session).get_by_user_id(user.id)
    if author is None:
        raise ForbiddenError("No author profile is linked to this account.", code="NO_AUTHOR_PROFILE")
    return CurrentAuthor(user, author)


# ---- service factories ----------------------------------------------------
def auth_service(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> AuthService:
    return AuthService(session, settings, request.app.state.login_limiter)


def book_service(session: AsyncSession = Depends(get_session)) -> BookService:
    return BookService(session)


def author_service(session: AsyncSession = Depends(get_session)) -> AuthorService:
    return AuthorService(session)


def ticket_service(
    session: AsyncSession = Depends(get_session), notifier: NotificationService = Depends(get_notifier)
) -> TicketService:
    return TicketService(session, notifier)


def admin_service(
    session: AsyncSession = Depends(get_session), notifier: NotificationService = Depends(get_notifier)
) -> AdminService:
    return AdminService(session, notifier)


def response_service(
    session: AsyncSession = Depends(get_session),
    notifier: NotificationService = Depends(get_notifier),
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
) -> ResponseService:
    return ResponseService(session, notifier, orchestrator)
