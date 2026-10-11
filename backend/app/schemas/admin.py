from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Category
from app.schemas.ai import AIDraftOut, AIRunOut, KnowledgeRef
from app.schemas.author import AuthorOut
from app.schemas.book import BookOut
from app.schemas.message import AdminMessageOut, InternalNoteOut
from app.schemas.ticket import AdminTicketSummary


class CategoryCount(BaseModel):
    category: Category | None
    count: int


class ActivityItem(BaseModel):
    ticket_id: str
    event_type: str
    old_value: str | None
    new_value: str | None
    created_at: datetime


class AdminDashboard(BaseModel):
    open_tickets: int
    unresolved_tickets: int
    critical_tickets: int
    high_priority_tickets: int
    unassigned_tickets: int
    ai_failed_tickets: int
    by_category: list[CategoryCount]
    recent_activity: list[ActivityItem]


class TicketEventOut(BaseModel):
    event_type: str
    old_value: str | None
    new_value: str | None
    created_at: datetime


class AdminTicketDetail(BaseModel):
    ticket: AdminTicketSummary
    description: str
    ai_reasoning: str | None
    author: AuthorOut
    book: BookOut | None
    messages: list[AdminMessageOut]
    internal_notes: list[InternalNoteOut]
    ai_draft: AIDraftOut | None
    knowledge_used: list[KnowledgeRef]
    ai_runs: list[AIRunOut]
    events: list[TicketEventOut]
