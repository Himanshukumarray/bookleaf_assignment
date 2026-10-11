from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Book(Base, TimestampMixin):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("total_copies_sold >= 0", name="ck_books_copies_nonneg"),
        CheckConstraint("royalty_pending >= 0", name="ck_books_pending_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_book_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    isbn: Mapped[str | None] = mapped_column(String(32))
    genre: Mapped[str | None] = mapped_column(String(100))
    publication_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(80))
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    author_royalty_per_copy: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_copies_sold: Mapped[int] = mapped_column(Integer, default=0)
    total_royalty_earned: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    royalty_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    royalty_pending: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    last_royalty_payout_date: Mapped[date | None] = mapped_column(Date)
    print_partner: Mapped[str | None] = mapped_column(String(100))

    availability: Mapped[list["BookAvailability"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="BookAvailability.id"
    )

    @property
    def platforms(self) -> list[str]:
        return [a.platform for a in self.availability]


class BookAvailability(Base):
    __tablename__ = "book_availability"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(80))
