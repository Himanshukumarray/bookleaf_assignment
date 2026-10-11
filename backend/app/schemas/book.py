from datetime import date

from pydantic import Field

from app.schemas.common import ORMModel


class BookOut(ORMModel):
    book_id: str = Field(validation_alias="external_book_id")
    title: str
    isbn: str | None = None
    genre: str | None = None
    publication_date: date | None = None
    status: str
    mrp: float | None = None
    author_royalty_per_copy: float | None = None
    total_copies_sold: int = 0
    total_royalty_earned: float = 0
    royalty_paid: float = 0
    royalty_pending: float = 0
    last_royalty_payout_date: date | None = None
    print_partner: str | None = None
    available_on: list[str] = Field(default_factory=list, validation_alias="platforms")


class BookRef(ORMModel):
    book_id: str = Field(validation_alias="external_book_id")
    title: str
    status: str
