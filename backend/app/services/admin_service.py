from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.db.base import utcnow
from app.models.enums import (
    UNRESOLVED_STATUSES,
    AIStatus,
    DecisionSource,
    Priority,
    Role,
    TicketStatus,
)
from app.models.internal_note import InternalNote
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.ai_repository import AIRepository
from app.repositories.author_repository import AuthorRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.ticket_repository import AdminTicketFilters, TicketRepository
from app.schemas.admin import (
    ActivityItem,
    AdminDashboard,
    AdminTicketDetail,
    CategoryCount,
    TicketEventOut,
)
from app.schemas.ai import AIDraftOut, AIRunOut, KnowledgeRef
from app.schemas.author import AuthorOut
from app.schemas.book import BookOut
from app.schemas.message import InternalNoteOut
from app.schemas.ticket import AdminTicketPage, AdminTicketSummary, TicketUpdate
from app.services import notification_service as events
from app.services.notification_service import NotificationService
from app.services.ticket_service import to_admin_message_out


class AdminService:
    def __init__(self, session: AsyncSession, notifier: NotificationService):
        self._session = session
        self._tickets = TicketRepository(session)
        self._ai = AIRepository(session)
        self._knowledge = KnowledgeRepository(session)
        self._users = AuthorRepository(session)
        self._notifier = notifier

    # ---- reads -----------------------------------------------------------
    async def get_ticket(self, display_id: str) -> Ticket:
        ticket = await self._tickets.get_by_display_id(display_id)
        if ticket is None:
            raise NotFoundError("Ticket was not found.", code="TICKET_NOT_FOUND")
        return ticket

    async def dashboard(self) -> AdminDashboard:
        t = self._tickets
        unresolved = Ticket.status.in_(UNRESOLVED_STATUSES)
        return AdminDashboard(
            open_tickets=await t.count_by(Ticket.status == TicketStatus.OPEN),
            unresolved_tickets=await t.count_by(unresolved),
            critical_tickets=await t.count_by(unresolved, Ticket.priority == Priority.CRITICAL),
            high_priority_tickets=await t.count_by(unresolved, Ticket.priority == Priority.HIGH),
            unassigned_tickets=await t.count_by(unresolved, Ticket.assigned_admin_id.is_(None)),
            ai_failed_tickets=await t.count_by(unresolved, Ticket.ai_status == AIStatus.FAILED),
            by_category=[CategoryCount(category=c, count=n) for c, n in await t.counts_by_category()],
            recent_activity=[
                ActivityItem(ticket_id=display_id, event_type=e.event_type, old_value=e.old_value,
                             new_value=e.new_value, created_at=e.created_at)
                for e, display_id in await t.recent_events()
            ],
        )

    async def queue(self, filters: AdminTicketFilters, admin: User) -> AdminTicketPage:
        items, total = await self._tickets.search_admin(filters, admin.id)
        return AdminTicketPage(
            items=[AdminTicketSummary.model_validate(t) for t in items],
            total=total, page=filters.page, page_size=filters.page_size,
        )

    async def detail(self, display_id: str) -> AdminTicketDetail:
        ticket = await self.get_ticket(display_id)
        messages = await self._tickets.list_messages(ticket.id)
        notes = await self._tickets.list_notes(ticket.id)
        draft = await self._ai.latest_draft(ticket.id)
        chunks = await self._knowledge.get_by_ids(draft.knowledge_chunk_ids) if draft else []
        knowledge = [KnowledgeRef(section=c.section, title=c.title) for c in chunks]
        draft_out = None
        if draft:
            draft_out = AIDraftOut.model_validate(draft).model_copy(update={"knowledge": knowledge})
        return AdminTicketDetail(
            ticket=AdminTicketSummary.model_validate(ticket),
            description=ticket.description,
            ai_reasoning=ticket.ai_reasoning,
            author=AuthorOut.model_validate(ticket.author),
            book=BookOut.model_validate(ticket.book) if ticket.book else None,
            messages=[to_admin_message_out(m, ticket) for m in messages],
            internal_notes=[InternalNoteOut.model_validate(n) for n in notes],
            ai_draft=draft_out,
            knowledge_used=knowledge,
            ai_runs=[AIRunOut.model_validate(r) for r in await self._ai.recent_runs(ticket.id)],
            events=[TicketEventOut(event_type=e.event_type, old_value=e.old_value, new_value=e.new_value,
                                   created_at=e.created_at) for e in await self._tickets.list_events(ticket.id)],
        )

    # ---- writes ----------------------------------------------------------
    async def update_ticket(self, display_id: str, admin: User, payload: TicketUpdate) -> Ticket:
        ticket = await self.get_ticket(display_id)
        changed: list[str] = []

        if payload.category is not None and payload.category != ticket.category:
            self._tickets.add_event(ticket.id, "category.manual", ticket.category.value if ticket.category else None,
                                    payload.category.value, admin.id)
            ticket.category, ticket.category_source, ticket.category_confidence = payload.category, DecisionSource.MANUAL, None
        if payload.priority is not None and payload.priority != ticket.priority:
            self._tickets.add_event(ticket.id, "priority.manual", ticket.priority.value, payload.priority.value, admin.id)
            ticket.priority, ticket.priority_source, ticket.priority_confidence = payload.priority, DecisionSource.MANUAL, None
            changed.append(events.PRIORITY_UPDATED)
        if payload.status is not None and payload.status != ticket.status:
            self._apply_status(ticket, payload.status, admin.id)
            changed.append(events.STATUS_UPDATED)

        ticket.updated_at = utcnow()
        await self._session.commit()
        for event_type in changed or [events.AI_UPDATED]:
            await self._notifier.ticket_event(event_type, ticket)
        return ticket

    def _apply_status(self, ticket: Ticket, new_status: TicketStatus, actor_id: int) -> None:
        self._tickets.add_event(ticket.id, "status.changed", ticket.status.value, new_status.value, actor_id)
        ticket.status = new_status
        ticket.resolved_at = utcnow() if new_status is TicketStatus.RESOLVED else (
            ticket.resolved_at if new_status is TicketStatus.CLOSED else None)
        ticket.closed_at = utcnow() if new_status is TicketStatus.CLOSED else None

    async def assign(self, display_id: str, admin: User, target_admin_id: int | None) -> Ticket:
        ticket = await self.get_ticket(display_id)
        target_id = target_admin_id or admin.id
        target = await self._users.get_user(target_id)
        if target is None or target.role is not Role.ADMIN or not target.is_active:
            raise BadRequestError("Assignee must be an active admin.", code="INVALID_ASSIGNEE")
        if ticket.assigned_admin_id != target.id:
            self._tickets.add_event(ticket.id, "ticket.assigned",
                                    ticket.assigned_admin_email, target.email, admin.id)
            ticket.assigned_admin_id = target.id
            ticket.assigned_admin = target
            if ticket.status is TicketStatus.OPEN:
                self._apply_status(ticket, TicketStatus.IN_PROGRESS, admin.id)
            ticket.updated_at = utcnow()
        await self._session.commit()
        await self._notifier.ticket_event(events.ASSIGNED, ticket)
        return ticket

    async def add_note(self, display_id: str, admin: User, text: str) -> InternalNote:
        ticket = await self.get_ticket(display_id)
        note = self._tickets.add_note(InternalNote(ticket_id=ticket.id, admin_id=admin.id, note=text.strip()))
        self._tickets.add_event(ticket.id, "note.added", None, None, admin.id)
        await self._session.commit()
        await self._session.refresh(note)
        note.admin = admin  # already loaded; avoids lazy IO when serialising
        return note
