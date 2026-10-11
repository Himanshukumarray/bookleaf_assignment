from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ForbiddenError, TooManyRequestsError, UnauthorizedError
from app.core.rate_limit import FailureRateLimiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import Role
from app.models.user import User
from app.repositories.author_repository import AuthorRepository
from app.schemas.auth import TokenResponse, UserOut
from app.schemas.author import AuthorOut

# Verified against when the email is unknown so response time doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("timing-equaliser")


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings, limiter: FailureRateLimiter):
        self._authors = AuthorRepository(session)
        self._settings = settings
        self._limiter = limiter

    async def login(self, email: str, password: str, client_ip: str = "unknown") -> TokenResponse:
        key = f"{client_ip}:{email.lower()}"
        wait = self._limiter.retry_after(key)
        if wait:
            raise TooManyRequestsError(
                f"Too many failed sign-in attempts. Try again in {wait} seconds.",
                code="TOO_MANY_ATTEMPTS",
                details={"retry_after_seconds": wait},
            )
        user = await self._authors.get_user_by_email(email)
        valid = verify_password(password, user.password_hash if user else _DUMMY_HASH)
        if user is None or not valid:
            self._limiter.record_failure(key)
            raise UnauthorizedError("Invalid email or password.", code="INVALID_CREDENTIALS")
        self._limiter.reset(key)
        if not user.is_active:
            raise ForbiddenError("This account has been disabled.", code="ACCOUNT_DISABLED")
        token, expires_in = create_access_token(self._settings, user_id=user.id, role=user.role.value)
        return TokenResponse(access_token=token, expires_in=expires_in, user=await self.user_out(user))

    async def user_out(self, user: User) -> UserOut:
        author = await self._authors.get_by_user_id(user.id) if user.role is Role.AUTHOR else None
        return UserOut(
            id=user.id, email=user.email, role=user.role,
            author=AuthorOut.model_validate(author) if author else None,
        )
