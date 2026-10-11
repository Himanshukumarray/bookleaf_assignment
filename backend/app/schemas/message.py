from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import SenderRole
from app.schemas.common import ORMModel


class AuthorMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class AdminMessageCreate(AuthorMessageCreate):
    ai_draft_id: int | None = None


class MessageOut(ORMModel):
    """Author-facing: deliberately omits AI-assistance metadata."""

    id: int
    sender_role: SenderRole
    sender_label: str
    message: str
    created_at: datetime


class AdminMessageOut(MessageOut):
    is_ai_assisted: bool


class InternalNoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=3000)


class InternalNoteOut(ORMModel):
    id: int
    admin_email: str
    note: str
    created_at: datetime
