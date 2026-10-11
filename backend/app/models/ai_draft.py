from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonType, utcnow


class AIDraft(Base):
    __tablename__ = "ai_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    draft: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40))
    knowledge_chunk_ids: Mapped[list[int]] = mapped_column(JsonType, default=list)
    grounding_warnings: Mapped[list[str]] = mapped_column(JsonType, default=list)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="GENERATED")  # GENERATED | SENT | SUPERSEDED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
