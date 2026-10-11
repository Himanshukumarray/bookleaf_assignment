import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import create_app
from app.models.enums import Role
from app.realtime.websocket_manager import ConnectionManager


class FakeSocket:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    async def send_json(self, data):
        if self.fail:
            raise RuntimeError("closed")
        self.sent.append(data)


EVENT = {"type": "ticket.message.created", "ticket_id": "TKT-1001", "timestamp": "now"}


async def test_event_reaches_ticket_author_and_admins_only():
    m = ConnectionManager()
    author, other_author, admin = FakeSocket(), FakeSocket(), FakeSocket()
    m.connect(author, user_id=10, role=Role.AUTHOR)
    m.connect(other_author, user_id=11, role=Role.AUTHOR)
    m.connect(admin, user_id=1, role=Role.ADMIN)
    await m.publish(EVENT, author_user_id=10)
    assert author.sent == [EVENT] and admin.sent == [EVENT] and other_author.sent == []


async def test_staff_only_event_skips_author():
    m = ConnectionManager()
    author, admin = FakeSocket(), FakeSocket()
    m.connect(author, user_id=10, role=Role.AUTHOR)
    m.connect(admin, user_id=1, role=Role.ADMIN)
    await m.publish(EVENT, author_user_id=None)
    assert author.sent == [] and admin.sent == [EVENT]


async def test_dead_socket_is_dropped_without_breaking_publish():
    m = ConnectionManager()
    dead, alive = FakeSocket(fail=True), FakeSocket()
    m.connect(dead, user_id=10, role=Role.AUTHOR)
    m.connect(alive, user_id=1, role=Role.ADMIN)
    await m.publish(EVENT, author_user_id=10)
    assert alive.sent == [EVENT] and m.connection_count() == 1


def test_websocket_rejects_missing_or_invalid_token(settings):
    app = create_app(settings, session_factory=None, ai_provider=None)
    with TestClient(app) as client:
        for url in ("/api/v1/ws", "/api/v1/ws?token=garbage"):
            with pytest.raises(WebSocketDisconnect) as exc:
                with client.websocket_connect(url):
                    pass
            assert exc.value.code == 4401


def test_websocket_accepts_valid_token_and_heartbeat(settings):
    app = create_app(settings, session_factory=None, ai_provider=None)
    token, _ = create_access_token(settings, user_id=5, role="AUTHOR")
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
