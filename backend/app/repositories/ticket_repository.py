import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author
from app.models.book import Book
from app.models.enums import UNRESOLVED_STATUSES, Category, Priority, TicketStatus
from app.models.internal_note import InternalNote
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_message import TicketMessage

DISPLAY_ID_BASE = 1000


@dataclass
class AdminTicketFilters:
    status: TicketStatus | None = None
    category: Category | None = None
    priority: Priority | None = None
    assignment: str | None = None  # "unassigned" | "assigned" | "me"
    author: str | None = None  # external author id or name fragment
    book: str | None = None  # external book id
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = None
    sort: str = "urgency"  # urgency | newest | oldest | updated
    page: int = 1
    page_size: int = 25


def _priority_rank():
    return case(
        (Ticket.priority == Priority.CRITICAL, 3),
        (Ticket.priority == Priority.HIGH, 2),
        (Ticket.priority == Priority.MEDIUM, 1),
        else_=0,
    )


class TicketRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ---- tickets ---------------------------------------------------------
    async def create(self, ticket: Ticket) -> Ticket:
        ticket.display_id = f"TMP-{uuid.uuid4().hex}"
        self._s.add(ticket)
        await self._s.flush()
        ticket.display_id = f"TKT-{DISPLAY_ID_BASE + ticket.id}"
        await self._s.flush()
        return ticket

    async def get_by_id(self, ticket_id: int) -> Ticket | None:
        return await self._s.get(Ticket, ticket_id)

    async def get_by_display_id(self, display_id: str) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.display_id == display_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list_for_author(self, author_id: int) -> list[Ticket]:
        stmt = select(Ticket).where(Ticket.author_id == author_id).order_by(Ticket.updated_at.desc())
        return list((await self._s.execute(stmt)).scalars().all())

    async def search_admin(self, f: AdminTicketFilters, admin_id: int) -> tuple[list[Ticket], int]:
        conditions = []
        stmt = select(Ticket).join(Author, Ticket.author_id == Author.id)
        if f.status:
            conditions.append(Ticket.status == f.status)
        if f.category:
            conditions.append(Ticket.category == f.category)
        if f.priority:
            conditions.append(Ticket.priority == f.priority)
        if f.assignment == "unassigned":
            conditions.append(Ticket.assigned_admin_id.is_(None))
        elif f.assignment == "assigned":
            conditions.append(Ticket.assigned_admin_id.is_not(None))
        elif f.assignment == "me":
            conditions.append(Ticket.assigned_admin_id == admin_id)
        if f.author:
            like = f"%{f.author.strip()}%"
            conditions.append(or_(Author.external_author_id == f.author.strip().upper(), Author.name.ilike(like)))
        if f.book:
            stmt = stmt.outerjoin(Book, Ticket.book_id == Book.id)
            conditions.append(Book.external_book_id == f.book.strip().upper())
        if f.date_from:
            conditions.append(Ticket.created_at >= datetime.combine(f.date_from, time.min, tzinfo=timezone.utc))
        if f.date_to:
            conditions.append(Ticket.created_at < datetime.combine(f.date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
        if f.q:
            like = f"%{f.q.strip()}%"
            conditions.append(or_(Ticket.subject.ilike(like), Ticket.description.ilike(like), Ticket.display_id.ilike(like)))
        if conditions:
            stmt = stmt.where(and_(*conditions))

        total = (await self._s.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
        stmt = stmt.order_by(*self._ordering(f.sort)).offset((f.page - 1) * f.page_size).limit(f.page_size)
        return list((await self._s.execute(stmt)).scalars().all()), total

    @staticmethod
    def _ordering(sort: str):
        if sort == "newest":
            return [Ticket.created_at.desc()]
        if sort == "oldest":
            return [Ticket.created_at.asc()]
        if sort == "updated":
            return [Ticket.updated_at.desc()]
        # Urgency: unresolved first; priority rank plus an aging boost (+1 after 7d, +2 after 14d); oldest first.
        now = datetime.now(timezone.utc)
        aging = case(
            (Ticket.created_at < now - timedelta(days=14), 2),
            (Ticket.created_at < now - timedelta(days=7), 1),
            else_=0,
        )
        unresolved_first = case((Ticket.status.in_(UNRESOLVED_STATUSES), 0), else_=1)
        return [unresolved_first, (_priority_rank() + aging).desc(), Ticket.created_at.asc()]

    # ---- messages / notes / events --------------------------------------
    def add_message(self, message: TicketMessage) -> TicketMessage:
        self._s.add(message)
        return message

    async def list_messages(self, ticket_id: int) -> list[TicketMessage]:
        stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.id)
        return list((await self._s.execute(stmt)).scalars().all())

    def add_note(self, note: InternalNote) -> InternalNote:
        self._s.add(note)
        return note

    async def list_notes(self, ticket_id: int) -> list[InternalNote]:
        stmt = select(InternalNote).where(InternalNote.ticket_id == ticket_id).order_by(InternalNote.id)
        return list((await self._s.execute(stmt)).scalars().all())

    def add_event(self, ticket_id: int, event_type: str, old: str | None, new: str | None, actor_id: int | None) -> None:
        self._s.add(TicketEvent(ticket_id=ticket_id, event_type=event_type, old_value=old, new_value=new, actor_id=actor_id))

    async def list_events(self, ticket_id: int, limit: int = 30) -> list[TicketEvent]:
        stmt = select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.id.desc()).limit(limit)
        return list((await self._s.execute(stmt)).scalars().all())

    # ---- aggregates ------------------------------------------------------
    async def count_by(self, *conditions) -> int:
        stmt = select(func.count(Ticket.id)).where(*conditions) if conditions else select(func.count(Ticket.id))
        return (await self._s.execute(stmt)).scalar_one()

    async def counts_by_category(self) -> list[tuple[Category | None, int]]:
        stmt = select(Ticket.category, func.count(Ticket.id)).group_by(Ticket.category)
        return [(row[0], row[1]) for row in (await self._s.execute(stmt)).all()]

    async def recent_events(self, limit: int = 12) -> list[tuple[TicketEvent, str]]:
        stmt = (
            select(TicketEvent, Ticket.display_id)
            .join(Ticket, TicketEvent.ticket_id == Ticket.id)
            .order_by(TicketEvent.id.desc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in (await self._s.execute(stmt)).all()]
