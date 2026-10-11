from pydantic import BaseModel

from app.schemas.ticket import TicketOut


class BookStatusCount(BaseModel):
    status: str
    count: int


class AuthorDashboard(BaseModel):
    total_books: int
    open_tickets: int
    total_royalty_earned: float
    total_royalty_paid: float
    total_royalty_pending: float
    recent_tickets: list[TicketOut]
    book_status_overview: list[BookStatusCount]
