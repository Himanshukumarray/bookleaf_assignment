"""Deterministic royalty interpretation: policy (threshold, payout window) applied to account data.

Shared by the priority guardrails and the context builder so the model is *told* the conclusion
instead of being trusted to derive it (e.g. ₹850 pending is a legitimate rollover, not a missed payment).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from app.models.book import Book

PAYOUT_THRESHOLD = Decimal("1000")
# Quarter (<= ~92 days) + 45-day payout window, rounded: beyond this a pending balance warrants a finance check.
OVERDUE_AFTER_DAYS = 137


class RoyaltyState(str, Enum):
    NO_BALANCE = "NO_BALANCE"
    BELOW_THRESHOLD = "BELOW_THRESHOLD"
    WITHIN_PAYOUT_WINDOW = "WITHIN_PAYOUT_WINDOW"
    POSSIBLY_OVERDUE = "POSSIBLY_OVERDUE"


@dataclass(frozen=True)
class RoyaltyAssessment:
    state: RoyaltyState
    explanation: str


def assess_royalty(book: Book, today: date) -> RoyaltyAssessment:
    pending = Decimal(book.royalty_pending or 0)
    if pending <= 0:
        return RoyaltyAssessment(RoyaltyState.NO_BALANCE, "No royalty balance is pending for this book.")
    if pending < PAYOUT_THRESHOLD:
        return RoyaltyAssessment(
            RoyaltyState.BELOW_THRESHOLD,
            f"Pending royalty (₹{pending:,.0f}) is below the ₹1,000 minimum payout threshold, "
            "so it legitimately rolls over to the next quarter. This is NOT a missed payment.",
        )
    reference = book.last_royalty_payout_date or book.publication_date
    if reference is None:
        return RoyaltyAssessment(
            RoyaltyState.WITHIN_PAYOUT_WINDOW,
            "Pending royalty meets the payout threshold but there is no payout or publication date on record to judge timing.",
        )
    days = (today - reference).days
    basis = "last payout" if book.last_royalty_payout_date else "publication"
    if days > OVERDUE_AFTER_DAYS:
        return RoyaltyAssessment(
            RoyaltyState.POSSIBLY_OVERDUE,
            f"Pending royalty (₹{pending:,.0f}) meets the payout threshold and {days} days have passed since "
            f"{basis} ({reference.isoformat()}). This may be overdue and needs a finance check.",
        )
    return RoyaltyAssessment(
        RoyaltyState.WITHIN_PAYOUT_WINDOW,
        f"Pending royalty (₹{pending:,.0f}) meets the threshold; only {days} days since {basis}, "
        "so it may still fall inside the normal quarterly payout window.",
    )
