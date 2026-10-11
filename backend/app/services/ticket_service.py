from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.base import utcnow
from app.models.author import Author
from app.models.enums import SenderRole, TicketStatus
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage
from app.repositories.book_repository import BookRepository
from app.repositories.ticket_repository import TicketRepository
from app.schemas.message import AdminMessageOut, MessageOut
from app.schemas.ticket import TicketCreate
from app.services import notification_service as events
from app.services.notification_service import NotificationService

SUPPORT_LABEL = "BookLeaf Support"


def message_label(message: TicketMessage, ticket: Ticket) -> str:
    return ticket.author.name if message.sender_role is SenderRole.AUTHOR else SUPPORT_LABEL


def to_message_out(message: TicketMessage, ticket: Ticket) -> MessageOut:
    return MessageOut(
        id=message.id, sender_role=message.sender_role, sender_label=message_label(message, ticket),
        message=message.message, created_at=message.created_at,
    )


def to_admin_message_out(message: TicketMessage, ticket: Ticket) -> AdminMessageOut:
    return AdminMessageOut(
        id=message.id, sender_role=message.sender_role, sender_label=message_label(message, ticket),
        message=message.message, created_at=message.created_at, is_ai_assisted=message.is_ai_assisted,
    )


class TicketService:
    """Author-facing ticket operations. Every method enforces ownership server-side."""

    def __init__(self, session: AsyncSession, notifier: NotificationService):
        self._session = session
        self._tickets = TicketRepository(session)
        self._books = BookRepository(session)
        self._notifier = notifier

    async def create_ticket(self, author: Author, payload: TicketCreate, actor_user_id: int) -> Ticket:
        book = None
        if payload.book_id:
            book = await self._books.get_by_external_id(payload.book_id)
            if book is None or book.author_id != author.id:
                raise NotFoundError("Book was not found.", code="BOOK_NOT_FOUND")
        ticket = await self._tickets.create(
            Ticket(author_id=author.id, book_id=book.id if book else None,
                   subject=payload.subject.strip(), description=payload.description.strip())
        )
        self._tickets.add_event(ticket.id, "ticket.created", None, TicketStatus.OPEN.value, actor_user_id)
        # Commit *before* any AI work is scheduled: the ticket must exist whatever happens next.
        await self._session.commit()
        await self._session.refresh(ticket)
        await self._notifier.ticket_event(events.TICKET_CREATED, ticket)
        return ticket

    async def list_for_author(self, author: Author) -> list[Ticket]:
        return await self._tickets.list_for_author(author.id)

    async def get_owned(self, author: Author, display_id: str) -> Ticket:
        ticket = await self._tickets.get_by_display_id(display_id)
        # 404 (not 403) for other authors' tickets so ticket ids can't be probed.
        if ticket is None or ticket.author_id != author.id:
            raise NotFoundError("Ticket was not found.", code="TICKET_NOT_FOUND")
        return ticket

    async def list_messages(self, author: Author, display_id: str) -> list[MessageOut]:
        ticket = await self.get_owned(author, display_id)
        return [to_message_out(m, ticket) for m in await self._tickets.list_messages(ticket.id)]

    async def add_author_message(self, author: Author, display_id: str, text: str, actor_user_id: int) -> MessageOut:
        ticket = await self.get_owned(author, display_id)
        if ticket.status is TicketStatus.CLOSED:
            raise ConflictError("This ticket is closed. Please open a new ticket.", code="TICKET_CLOSED")
        message = self._tickets.add_message(
            TicketMessage(ticket_id=ticket.id, sender_id=actor_user_id, sender_role=SenderRole.AUTHOR, message=text.strip())
        )
        ticket.updated_at = utcnow()
        if ticket.status is TicketStatus.RESOLVED:  # author replied after resolution => reopen
            self._tickets.add_event(ticket.id, "status.reopened", ticket.status.value, TicketStatus.OPEN.value, actor_user_id)
            ticket.status, ticket.resolved_at = TicketStatus.OPEN, None
        await self._session.commit()
        await self._session.refresh(message)
        await self._notifier.ticket_event(events.MESSAGE_CREATED, ticket)
        return to_message_out(message, ticket)
