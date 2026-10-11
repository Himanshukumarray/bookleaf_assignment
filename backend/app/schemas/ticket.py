from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AIStatus, Category, DecisionSource, Priority, TicketStatus
from app.schemas.author import AuthorRef
from app.schemas.book import BookRef
from app.schemas.common import ORMModel


class TicketCreate(BaseModel):
    book_id: str | None = Field(default=None, description="External book id (e.g. BK001); null for account-level queries")
    subject: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=10, max_length=5000)


class TicketOut(ORMModel):
    """Author-facing ticket. No AI internals (confidence, reasoning, status)."""

    ticket_id: str = Field(validation_alias="display_id")
    book: BookRef | None = None
    subject: str
    description: str
    category: Category | None = None
    priority: Priority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class AdminTicketSummary(ORMModel):
    ticket_id: str = Field(validation_alias="display_id")
    author: AuthorRef
    book: BookRef | None = None
    subject: str
    category: Category | None = None
    category_source: DecisionSource
    category_confidence: float | None = None
    priority: Priority
    priority_source: DecisionSource
    priority_confidence: float | None = None
    status: TicketStatus
    ai_status: AIStatus
    needs_human_attention: bool = False
    assigned_admin_email: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminTicketPage(BaseModel):
    items: list[AdminTicketSummary]
    total: int
    page: int
    page_size: int


class TicketUpdate(BaseModel):
    category: Category | None = None
    priority: Priority | None = None
    status: TicketStatus | None = None


class AssignRequest(BaseModel):
    admin_id: int | None = Field(default=None, description="Defaults to the calling admin")
