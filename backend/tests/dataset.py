"""The official BookLeaf JSON is the single source of truth for tests: nothing here is hardcoded business data.

Scenario books are *found by predicate* (e.g. "a book still in production"), so tests describe behaviour,
not specific titles or amounts.
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "bookleaf_sample_data.json"
AUTHORS: list[dict] = json.loads(DATA_PATH.read_text(encoding="utf-8"))["authors"]
BOOKS: list[dict] = [{**b, "author_id": a["author_id"]} for a in AUTHORS for b in a["books"]]
AUTHOR_BY_ID = {a["author_id"]: a for a in AUTHORS}
BOOK_BY_ID = {b["book_id"]: b for b in BOOKS}

FIRST_AUTHOR, SECOND_AUTHOR = AUTHORS[0], AUTHORS[1]
FIRST_BOOK, SECOND_BOOK = FIRST_AUTHOR["books"][0], SECOND_AUTHOR["books"][0]


def _one(predicate, description: str) -> dict:
    found = [b for b in BOOKS if predicate(b)]
    assert found, f"dataset has no book that is {description}"
    return found[0]


def _money(value) -> Decimal:
    return Decimal(str(value or 0))


# --- behaviour-driven scenario books ----------------------------------------------------------
IN_PRODUCTION_BOOK = _one(lambda b: b["publication_date"] is None, "still in production (null publication date)")
BELOW_THRESHOLD_BOOK = _one(lambda b: 0 < _money(b["royalty_pending"]) < 1000, "below the payout threshold")
NEVER_PAID_OVERDUE_BOOK = _one(
    lambda b: _money(b["royalty_pending"]) >= 1000 and b["last_royalty_payout_date"] is None
    and b["publication_date"] and date.fromisoformat(b["publication_date"]) < date(2025, 6, 1),
    "unpaid, above threshold and published long ago",
)
PAID_UP_BOOK = _one(lambda b: _money(b["royalty_pending"]) == 0 and _money(b["total_royalty_earned"]) > 0, "fully paid")
RECENT_PAYOUT_BOOK = _one(lambda b: b["last_royalty_payout_date"] and _money(b["royalty_pending"]) >= 1000, "paid before, balance pending")
EMPTY_PLATFORMS_BOOK = _one(lambda b: not b["available_on"], "listed on no platform")
MULTI_PLATFORM_BOOK = max(BOOKS, key=lambda b: len(b["available_on"]))
MULTI_BOOK_AUTHOR = _one(lambda b: len(AUTHOR_BY_ID[b["author_id"]]["books"]) > 1, "owned by an author with several books")
MULTI_BOOK_AUTHOR = AUTHOR_BY_ID[MULTI_BOOK_AUTHOR["author_id"]]


def author_of(book: dict) -> dict:
    return AUTHOR_BY_ID[book["author_id"]]


def money_text(value) -> str:
    """Format like the context builder: ₹ with Indian-style thousands only where the builder does (plain commas)."""
    return f"₹{_money(value):,.0f}"
