from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role
from app.schemas.author import AuthorOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    email: str
    role: Role
    author: AuthorOut | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
