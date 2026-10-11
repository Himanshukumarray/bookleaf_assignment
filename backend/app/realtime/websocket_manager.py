import logging
from collections import defaultdict
from typing import Protocol

from app.models.enums import Role

logger = logging.getLogger(__name__)


class SocketLike(Protocol):
    async def send_json(self, data: dict) -> None: ...


class ConnectionManager:
    """In-process fan-out. Production: swap for Redis pub/sub so multiple API workers share events."""

    def __init__(self) -> None:
        self._by_user: dict[int, set[SocketLike]] = defaultdict(set)
        self._admin_ids: set[int] = set()

    def connect(self, socket: SocketLike, *, user_id: int, role: Role) -> None:
        self._by_user[user_id].add(socket)
        if role is Role.ADMIN:
            self._admin_ids.add(user_id)

    def disconnect(self, socket: SocketLike, *, user_id: int) -> None:
        sockets = self._by_user.get(user_id)
        if not sockets:
            return
        sockets.discard(socket)
        if not sockets:
            self._by_user.pop(user_id, None)
            self._admin_ids.discard(user_id)

    def connection_count(self) -> int:
        return sum(len(s) for s in self._by_user.values())

    async def publish(self, event: dict, *, author_user_id: int | None) -> None:
        """Send to the ticket's author and every connected admin. Payload is intentionally minimal."""
        recipients = set(self._admin_ids)
        if author_user_id is not None:
            recipients.add(author_user_id)
        for user_id in recipients:
            for socket in list(self._by_user.get(user_id, ())):
                try:
                    await socket.send_json(event)
                except Exception:  # noqa: BLE001 - a dead socket must not break the request that triggered the event
                    logger.info("Dropping dead websocket for user %s", user_id)
                    self.disconnect(socket, user_id=user_id)
