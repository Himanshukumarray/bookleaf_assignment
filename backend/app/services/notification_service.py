from datetime import datetime, timezone

from app.models.ticket import Ticket
from app.realtime.websocket_manager import ConnectionManager

MESSAGE_CREATED = "ticket.message.created"
STATUS_UPDATED = "ticket.status.updated"
PRIORITY_UPDATED = "ticket.priority.updated"
ASSIGNED = "ticket.assigned"
AI_UPDATED = "ticket.ai.updated"
TICKET_CREATED = "ticket.created"


class NotificationService:
    """Turns domain changes into minimal WebSocket events (type + ticket id + timestamp only).

    Clients react by invalidating their TanStack Query cache and re-fetching through the
    authorised REST API, so the socket never carries ticket content or leaks data.
    """

    def __init__(self, manager: ConnectionManager):
        self._manager = manager

    async def ticket_event(self, event_type: str, ticket: Ticket) -> None:
        event = {
            "type": event_type,
            "ticket_id": ticket.display_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # AI progress is staff-only; authors only learn about conversation/status/priority changes.
        author_user_id = None if event_type == AI_UPDATED else ticket.author.user_id
        await self._manager.publish(event, author_user_id=author_user_id)
