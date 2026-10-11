from fastapi import APIRouter, Depends

from app.api.dependencies import (
    CurrentAuthor,
    author_service,
    book_service,
    require_author,
)
from app.schemas.book import BookOut
from app.schemas.dashboard import AuthorDashboard
from app.services.author_service import AuthorService
from app.services.book_service import BookService

router = APIRouter(tags=["author"])


@router.get("/author/dashboard", response_model=AuthorDashboard)
async def dashboard(
    current: CurrentAuthor = Depends(require_author), service: AuthorService = Depends(author_service)
) -> AuthorDashboard:
    return await service.dashboard(current.author)


@router.get("/books", response_model=list[BookOut])
async def list_books(
    current: CurrentAuthor = Depends(require_author), service: BookService = Depends(book_service)
) -> list[BookOut]:
    return [BookOut.model_validate(b) for b in await service.list_for_author(current.author)]


@router.get("/books/{book_id}", response_model=BookOut)
async def get_book(
    book_id: str, current: CurrentAuthor = Depends(require_author), service: BookService = Depends(book_service)
) -> BookOut:
    return BookOut.model_validate(await service.get_for_author(current.author, book_id))
