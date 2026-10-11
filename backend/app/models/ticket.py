from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, str_enum
from app.models.author import Author
from app.models.book import Book
from app.models.enums import AIStatus, Category, DecisionSource, Priority, TicketStatus
from app.models.user import User


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_priority", "status", "priority"),
        Index("ix_tickets_author_created", "author_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    display_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)

    category: Mapped[Category | None] = mapped_column(str_enum(Category, "ticket_category"), index=True)
    category_source: Mapped[DecisionSource] = mapped_column(
        str_enum(DecisionSource, "decision_source_category"), default=DecisionSource.DEFAULT
    )
    category_confidence: Mapped[float | None] = mapped_column(Float)

    priority: Mapped[Priority] = mapped_column(str_enum(Priority, "ticket_priority"), default=Priority.MEDIUM)
    priority_source: Mapped[DecisionSource] = mapped_column(
        str_enum(DecisionSource, "decision_source_priority"), default=DecisionSource.DEFAULT
    )
    priority_confidence: Mapped[float | None] = mapped_column(Float)

    needs_human_attention: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    ai_status: Mapped[AIStatus] = mapped_column(str_enum(AIStatus, "ai_status"), default=AIStatus.PENDING)

    status: Mapped[TicketStatus] = mapped_column(str_enum(TicketStatus, "ticket_status"), default=TicketStatus.OPEN)
    assigned_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author: Mapped[Author] = relationship(lazy="selectin")
    book: Mapped[Book | None] = relationship(lazy="selectin")
    assigned_admin: Mapped[User | None] = relationship(lazy="selectin")

    @property
    def assigned_admin_email(self) -> str | None:
        return self.assigned_admin.email if self.assigned_admin else None
