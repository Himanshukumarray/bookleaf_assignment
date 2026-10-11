from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.ai.orchestrator import AIOrchestrator
from app.api.dependencies import (
    CurrentAuthor,
    get_orchestrator,
    require_author,
    ticket_service,
)
from app.schemas.message import AuthorMessageCreate, MessageOut
from app.schemas.ticket import TicketCreate, TicketOut
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    background: BackgroundTasks,
    current: CurrentAuthor = Depends(require_author),
    service: TicketService = Depends(ticket_service),
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
) -> TicketOut:
    ticket = await service.create_ticket(current.author, payload, current.user.id)  # committed here
    # AI runs after the response is sent; production would enqueue this on a worker (Redis + RQ/Celery).
    background.add_task(orchestrator.process_ticket, ticket.id)
    return TicketOut.model_validate(ticket)


@router.get("", response_model=list[TicketOut])
async def list_tickets(
    current: CurrentAuthor = Depends(require_author), service: TicketService = Depends(ticket_service)
) -> list[TicketOut]:
    return [TicketOut.model_validate(t) for t in await service.list_for_author(current.author)]


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: str, current: CurrentAuthor = Depends(require_author), service: TicketService = Depends(ticket_service)
) -> TicketOut:
    return TicketOut.model_validate(await service.get_owned(current.author, ticket_id))


@router.get("/{ticket_id}/messages", response_model=list[MessageOut])
async def list_messages(
    ticket_id: str, current: CurrentAuthor = Depends(require_author), service: TicketService = Depends(ticket_service)
) -> list[MessageOut]:
    return await service.list_messages(current.author, ticket_id)


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def add_message(
    ticket_id: str,
    payload: AuthorMessageCreate,
    current: CurrentAuthor = Depends(require_author),
    service: TicketService = Depends(ticket_service),
) -> MessageOut:
    return await service.add_author_message(current.author, ticket_id, payload.message, current.user.id)
