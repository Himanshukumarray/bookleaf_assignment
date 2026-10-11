from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.ai.orchestrator import AIOrchestrator
from app.api.dependencies import (
    admin_service,
    get_orchestrator,
    require_admin,
    response_service,
)
from app.models.enums import Category, Priority, TicketStatus
from app.models.user import User
from app.repositories.ticket_repository import AdminTicketFilters
from app.schemas.admin import AdminDashboard, AdminTicketDetail
from app.schemas.ai import AIDraftOut
from app.schemas.message import (
    AdminMessageCreate,
    AdminMessageOut,
    InternalNoteCreate,
    InternalNoteOut,
)
from app.schemas.ticket import (
    AdminTicketPage,
    AdminTicketSummary,
    AssignRequest,
    TicketUpdate,
)
from app.services.admin_service import AdminService
from app.services.response_service import ResponseService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def queue_filters(
    status_: TicketStatus | None = Query(None, alias="status"),
    category: Category | None = None,
    priority: Priority | None = None,
    assignment: str | None = Query(None, pattern="^(unassigned|assigned|me)$"),
    author: str | None = Query(None, max_length=100, description="Author id (AUTH001) or name fragment"),
    book: str | None = Query(None, max_length=32, description="External book id, e.g. BK001"),
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(None, max_length=100),
    sort: str = Query("urgency", pattern="^(urgency|newest|oldest|updated)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> AdminTicketFilters:
    return AdminTicketFilters(
        status=status_, category=category, priority=priority, assignment=assignment, author=author, book=book,
        date_from=date_from, date_to=date_to, q=q, sort=sort, page=page, page_size=page_size,
    )


@router.get("/dashboard", response_model=AdminDashboard)
async def dashboard(service: AdminService = Depends(admin_service)) -> AdminDashboard:
    return await service.dashboard()


@router.get("/tickets", response_model=AdminTicketPage)
async def list_tickets(
    filters: AdminTicketFilters = Depends(queue_filters),
    admin: User = Depends(require_admin),
    service: AdminService = Depends(admin_service),
) -> AdminTicketPage:
    return await service.queue(filters, admin)


@router.get("/tickets/{ticket_id}", response_model=AdminTicketDetail)
async def get_ticket(ticket_id: str, service: AdminService = Depends(admin_service)) -> AdminTicketDetail:
    return await service.detail(ticket_id)


@router.patch("/tickets/{ticket_id}", response_model=AdminTicketSummary)
async def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    admin: User = Depends(require_admin),
    service: AdminService = Depends(admin_service),
) -> AdminTicketSummary:
    return AdminTicketSummary.model_validate(await service.update_ticket(ticket_id, admin, payload))


@router.post("/tickets/{ticket_id}/assign", response_model=AdminTicketSummary)
async def assign_ticket(
    ticket_id: str,
    payload: AssignRequest | None = None,
    admin: User = Depends(require_admin),
    service: AdminService = Depends(admin_service),
) -> AdminTicketSummary:
    target = payload.admin_id if payload else None
    return AdminTicketSummary.model_validate(await service.assign(ticket_id, admin, target))


@router.post("/tickets/{ticket_id}/notes", response_model=InternalNoteOut, status_code=status.HTTP_201_CREATED)
async def add_note(
    ticket_id: str,
    payload: InternalNoteCreate,
    admin: User = Depends(require_admin),
    service: AdminService = Depends(admin_service),
) -> InternalNoteOut:
    return InternalNoteOut.model_validate(await service.add_note(ticket_id, admin, payload.note))


@router.post("/tickets/{ticket_id}/messages", response_model=AdminMessageOut, status_code=status.HTTP_201_CREATED)
async def send_response(
    ticket_id: str,
    payload: AdminMessageCreate,
    admin: User = Depends(require_admin),
    service: ResponseService = Depends(response_service),
) -> AdminMessageOut:
    """The only path by which text (AI-assisted or not) reaches an author."""
    return await service.send_response(ticket_id, admin, payload.message, payload.ai_draft_id)


@router.post("/tickets/{ticket_id}/ai-draft", response_model=AIDraftOut)
async def regenerate_draft(ticket_id: str, service: ResponseService = Depends(response_service)) -> AIDraftOut:
    return await service.regenerate_draft(ticket_id)


@router.post("/tickets/{ticket_id}/ai-retry", status_code=status.HTTP_202_ACCEPTED, response_model=AdminTicketSummary)
async def retry_ai(
    ticket_id: str,
    background: BackgroundTasks,
    admin: User = Depends(require_admin),
    service: ResponseService = Depends(response_service),
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
) -> AdminTicketSummary:
    ticket = await service.mark_for_retry(ticket_id, admin)
    background.add_task(orchestrator.process_ticket, ticket.id)
    return AdminTicketSummary.model_validate(ticket)
