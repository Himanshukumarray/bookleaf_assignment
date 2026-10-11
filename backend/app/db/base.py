from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


def str_enum(enum_cls: type, name: str) -> Enum:
    """Portable enum: stored as VARCHAR + CHECK (no CREATE TYPE churn on migrations)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        length=40,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


JsonType = JSON().with_variant(JSONB(), "postgresql")


class EmbeddingType(TypeDecorator):
    """pgvector `vector(n)` on PostgreSQL, JSON list elsewhere (keeps unit tests DB-agnostic)."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int | None = None):
        super().__init__()
        self.dimensions = dimensions or get_settings().embedding_dimensions

    def load_dialect_impl(self, dialect: Any):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON(none_as_null=True))
