from fastapi import APIRouter

from app.api.v1.endpoints import admin, ai, auth, books, tickets, ws

api_router = APIRouter(prefix="/api/v1")
for module in (auth, books, tickets, admin, ai, ws):
    api_router.include_router(module.router)
