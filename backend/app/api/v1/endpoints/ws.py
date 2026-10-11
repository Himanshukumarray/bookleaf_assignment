import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.models.enums import Role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realtime"])

WS_UNAUTHORIZED = 4401


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
    """Event channel. Browsers can't set headers on WebSockets, so the JWT arrives as `?token=`.

    Authentication is stateless (claims only) so connecting never touches the database.
    """
    app = websocket.app
    try:
        claims = decode_access_token(app.state.settings, token)
        user_id, role = int(claims["sub"]), Role(claims["role"])
    except (UnauthorizedError, KeyError, ValueError):
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    manager = app.state.ws_manager
    await websocket.accept()
    manager.connect(websocket, user_id=user_id, role=role)
    try:
        while True:
            if await websocket.receive_text() == "ping":  # client heartbeat
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user_id=user_id)
