from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book


class BookRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def list_for_author(self, author_id: int) -> list[Book]:
        stmt = select(Book).where(Book.author_id == author_id).order_by(Book.external_book_id)
        return list((await self._s.execute(stmt)).scalars().all())

    async def get_by_external_id(self, external_book_id: str) -> Book | None:
        stmt = select(Book).where(Book.external_book_id == external_book_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get(self, book_id: int) -> Book | None:
        return await self._s.get(Book, book_id)
