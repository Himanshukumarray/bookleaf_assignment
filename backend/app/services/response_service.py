from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIError
from app.ai.orchestrator import AIOrchestrator
from app.core.exceptions import (
    AIUnavailableError,
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.db.base import utcnow
from app.models.ai_draft import AIDraft
from app.models.enums import AIStatus, SenderRole, TicketStatus
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage
from app.models.user import User
from app.repositories.ai_repository import AIRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ai import AIDraftOut, KnowledgeRef
from app.schemas.message import AdminMessageOut
from app.services import notification_service as events
from app.services.notification_service import NotificationService
from app.services.ticket_service import to_admin_message_out

STALE_PROCESSING_AFTER = timedelta(minutes=3)  # a worker that died mid-run must not wedge the ticket forever


def _is_stale(updated_at: datetime) -> bool:
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return utcnow() - updated_at > STALE_PROCESSING_AFTER


AI_UNAVAILABLE_MESSAGE = "AI assistance temporarily unavailable. You can respond manually."


class ResponseService:
    """Human-in-the-loop replies and AI draft management. AI output only ever reaches an author via send_response."""

    def __init__(self, session: AsyncSession, notifier: NotificationService, orchestrator: AIOrchestrator):
        self._session = session
        self._tickets = TicketRepository(session)
        self._ai = AIRepository(session)
        self._knowledge = KnowledgeRepository(session)
        self._notifier = notifier
        self._orchestrator = orchestrator

    async def _get(self, display_id: str) -> Ticket:
        ticket = await self._tickets.get_by_display_id(display_id)
        if ticket is None:
            raise NotFoundError("Ticket was not found.", code="TICKET_NOT_FOUND")
        return ticket

    async def send_response(self, display_id: str, admin: User, text: str, ai_draft_id: int | None) -> AdminMessageOut:
        ticket = await self._get(display_id)
        if ticket.status is TicketStatus.CLOSED:
            raise ConflictError("Ticket is closed. Reopen it before responding.", code="TICKET_CLOSED")

        draft: AIDraft | None = None
        if ai_draft_id is not None:
            draft = await self._ai.get_draft(ai_draft_id)
            if draft is None or draft.ticket_id != ticket.id:
                raise BadRequestError("The referenced AI draft does not belong to this ticket.", code="INVALID_DRAFT")

        message = self._tickets.add_message(TicketMessage(
            ticket_id=ticket.id, sender_id=admin.id, sender_role=SenderRole.ADMIN,
            message=text.strip(), is_ai_assisted=draft is not None,
        ))
        if draft is not None:
            draft.status = "SENT"
        pending_events = [events.MESSAGE_CREATED]
        if ticket.assigned_admin_id is None:
            self._tickets.add_event(ticket.id, "ticket.assigned", None, admin.email, admin.id)
            ticket.assigned_admin_id, ticket.assigned_admin = admin.id, admin
            pending_events.append(events.ASSIGNED)
        if ticket.status is TicketStatus.OPEN:
            self._tickets.add_event(ticket.id, "status.changed", TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value, admin.id)
            ticket.status = TicketStatus.IN_PROGRESS
            pending_events.append(events.STATUS_UPDATED)
        self._tickets.add_event(ticket.id, "response.sent", None, "ai_assisted" if draft else "manual", admin.id)
        ticket.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(message)
        for event_type in pending_events:
            await self._notifier.ticket_event(event_type, ticket)
        return to_admin_message_out(message, ticket)

    async def regenerate_draft(self, display_id: str) -> AIDraftOut:
        """Explicit admin action only: drafts are never regenerated automatically (cost control)."""
        ticket = await self._get(display_id)
        await self._session.commit()  # release the read transaction before the (slow) model call
        try:
            draft = await self._orchestrator.regenerate_draft(ticket.id)
        except AIError as exc:
            raise AIUnavailableError(AI_UNAVAILABLE_MESSAGE, details={"reason": exc.error_type}) from exc
        chunks = await self._knowledge.get_by_ids(draft.knowledge_chunk_ids)
        return AIDraftOut.model_validate(draft).model_copy(
            update={"knowledge": [KnowledgeRef(section=c.section, title=c.title) for c in chunks]}
        )

    async def mark_for_retry(self, display_id: str, admin: User) -> Ticket:
        ticket = await self._get(display_id)
        if ticket.ai_status is AIStatus.PROCESSING and not _is_stale(ticket.updated_at):
            raise ConflictError("AI analysis is already running for this ticket.", code="AI_IN_PROGRESS")
        ticket.ai_status = AIStatus.PENDING
        self._tickets.add_event(ticket.id, "ai.retry", None, None, admin.id)
        await self._session.commit()  # committed before the background task starts
        return ticket
