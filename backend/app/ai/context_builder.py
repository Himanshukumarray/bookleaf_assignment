"""Builds the ACCOUNT_CONTEXT and RECENT_MESSAGES blocks from PostgreSQL data.

Only fields relevant to the ticket category are included (cost + minimises leakage). The model is
never asked to look anything up: facts, and conclusions drawn from policy, are handed to it.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.ai.prompts import sanitize_untrusted
from app.ai.royalty import assess_royalty
from app.models.author import Author
from app.models.book import Book
from app.models.enums import Category, SenderRole
from app.models.ticket_message import TicketMessage

_NOT_AVAILABLE = "not available"


def _money(value: Decimal | int | None) -> str:
    return _NOT_AVAILABLE if value is None else f"₹{Decimal(value):,.0f}"


def _date(value: date | None) -> str:
    return _NOT_AVAILABLE if value is None else value.isoformat()


@dataclass
class AccountContext:
    facts: dict[str, str] = field(default_factory=dict)
    derived_facts: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"- {key}: {value}" for key, value in self.facts.items()]
        if self.derived_facts:
            lines.append("DERIVED_FACTS:")
            lines += [f"- {fact}" for fact in self.derived_facts]
        return "\n".join(lines)


class ContextBuilder:
    def __init__(self, history_limit: int = 6, message_char_limit: int = 600):
        self._history_limit = history_limit
        self._message_char_limit = message_char_limit

    # ---- account context -------------------------------------------------
    def build_account_context(
        self,
        *,
        category: Category | None,
        book: Book | None,
        author: Author,
        author_books: list[Book] | None = None,
        today: date | None = None,
    ) -> AccountContext:
        today = today or date.today()
        if book is None:
            return self._account_level(category, author_books or [], today)

        ctx = AccountContext({"Book": book.title, "Production status": book.status})
        if category is Category.ROYALTY:
            ctx.facts.update(
                {
                    "MRP": _money(book.mrp),
                    "Copies sold": str(book.total_copies_sold),
                    "Royalty per copy": _money(book.author_royalty_per_copy),
                    "Total royalty earned": _money(book.total_royalty_earned),
                    "Royalty paid": _money(book.royalty_paid),
                    "Royalty pending": _money(book.royalty_pending),
                    "Last royalty payout date": _date(book.last_royalty_payout_date),
                }
            )
            ctx.derived_facts.append(assess_royalty(book, today).explanation)
        elif category is Category.ISBN:
            ctx.facts["ISBN on record"] = book.isbn or "none assigned yet"
            ctx.facts["Publication date"] = _date(book.publication_date)
        elif category is Category.DISTRIBUTION:
            ctx.facts["Publication date"] = _date(book.publication_date)
            ctx.facts["Platforms listed"] = ", ".join(book.platforms) or "none listed yet"
            ctx.facts["Print partner"] = book.print_partner or "not assigned"
        elif category is Category.PRINTING:
            ctx.facts["Print partner"] = book.print_partner or "in-house / not assigned"
            ctx.facts["Publication date"] = _date(book.publication_date)
        elif category is Category.PRODUCTION:
            ctx.facts["Publication date"] = _date(book.publication_date)
        return ctx

    def _account_level(self, category: Category | None, books: list[Book], today: date) -> AccountContext:
        ctx = AccountContext({"Scope": "Account-level query (no specific book selected)"})
        if category is Category.ROYALTY and books:
            ctx.facts["Books on account"] = str(len(books))
            ctx.facts["Total royalty earned (all books)"] = _money(sum(Decimal(b.total_royalty_earned or 0) for b in books))
            ctx.facts["Total royalty paid (all books)"] = _money(sum(Decimal(b.royalty_paid or 0) for b in books))
            ctx.facts["Total royalty pending (all books)"] = _money(sum(Decimal(b.royalty_pending or 0) for b in books))
        elif books:
            ctx.facts["Books on account"] = "; ".join(f"{b.title} ({b.status})" for b in books[:10])
        return ctx

    # ---- conversation ----------------------------------------------------
    def build_recent_messages(self, messages: list[TicketMessage]) -> str:
        recent = messages[-self._history_limit :]
        lines = []
        for m in recent:
            who = "Author" if m.sender_role is SenderRole.AUTHOR else "Support"
            lines.append(f"[{who}] {sanitize_untrusted(m.message, self._message_char_limit)}")
        return "\n".join(lines)

    @staticmethod
    def book_hint(book: Book | None) -> str | None:
        """Minimal, non-sensitive hint for the classifier."""
        if book is None:
            return None
        return f"Book: {book.title}; production status: {book.status}; ISBN assigned: {'yes' if book.isbn else 'no'}"
