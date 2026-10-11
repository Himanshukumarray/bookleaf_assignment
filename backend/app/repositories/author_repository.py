from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author
from app.models.user import User


class AuthorRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def get_by_user_id(self, user_id: int) -> Author | None:
        return (await self._s.execute(select(Author).where(Author.user_id == user_id))).scalar_one_or_none()

    async def get_by_id(self, author_id: int) -> Author | None:
        return await self._s.get(Author, author_id)

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_user(self, user_id: int) -> User | None:
        return await self._s.get(User, user_id)
