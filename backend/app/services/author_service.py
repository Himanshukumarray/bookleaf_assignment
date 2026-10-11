from collections import Counter
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author
from app.models.enums import UNRESOLVED_STATUSES
from app.repositories.book_repository import BookRepository
from app.repositories.ticket_repository import TicketRepository
from app.schemas.dashboard import AuthorDashboard, BookStatusCount
from app.schemas.ticket import TicketOut


class AuthorService:
    def __init__(self, session: AsyncSession):
        self._books = BookRepository(session)
        self._tickets = TicketRepository(session)

    async def dashboard(self, author: Author) -> AuthorDashboard:
        books = await self._books.list_for_author(author.id)
        tickets = await self._tickets.list_for_author(author.id)

        def total(attr: str) -> float:
            return float(sum((Decimal(getattr(b, attr) or 0) for b in books), Decimal(0)))

        statuses = Counter(b.status for b in books)
        return AuthorDashboard(
            total_books=len(books),
            open_tickets=sum(1 for t in tickets if t.status in UNRESOLVED_STATUSES),
            total_royalty_earned=total("total_royalty_earned"),
            total_royalty_paid=total("royalty_paid"),
            total_royalty_pending=total("royalty_pending"),
            recent_tickets=[TicketOut.model_validate(t) for t in tickets[:5]],
            book_status_overview=[BookStatusCount(status=s, count=n) for s, n in sorted(statuses.items())],
        )
