from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.author import Author
from app.models.book import Book
from app.repositories.book_repository import BookRepository


class BookService:
    def __init__(self, session: AsyncSession):
        self._books = BookRepository(session)

    async def list_for_author(self, author: Author) -> list[Book]:
        return await self._books.list_for_author(author.id)

    async def get_for_author(self, author: Author, external_book_id: str) -> Book:
        book = await self._books.get_by_external_id(external_book_id)
        # Same response whether the book is missing or belongs to someone else: no existence leak.
        if book is None or book.author_id != author.id:
            raise NotFoundError("Book was not found.", code="BOOK_NOT_FOUND")
        return book
