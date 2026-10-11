from fastapi import APIRouter, Depends, Request

from app.api.dependencies import auth_service, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, request: Request, service: AuthService = Depends(auth_service)
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    return await service.login(payload.email, payload.password, client_ip)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user), service: AuthService = Depends(auth_service)) -> UserOut:
    return await service.user_out(user)
