from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.ai.priority import PriorityEngine
from app.ai.royalty import RoyaltyState, assess_royalty
from app.models import Book
from app.models.enums import Category, Priority
from tests.dataset import BELOW_THRESHOLD_BOOK, IN_PRODUCTION_BOOK, NEVER_PAID_OVERDUE_BOOK, PAID_UP_BOOK

TODAY = date(2026, 10, 8)
engine = PriorityEngine()


async def book(session_factory, external_id: str) -> Book:
    async with session_factory() as s:
        return (await s.execute(select(Book).where(Book.external_book_id == external_id))).scalar_one()


def resolve(priority, category, text, b=None):
    return engine.resolve(model_priority=priority, category=category, text=text, book=b, today=TODAY)


@pytest.mark.parametrize("model", [Priority.LOW, Priority.MEDIUM])
def test_isbn_error_has_high_floor(model):
    d = resolve(model, Category.ISBN, "The ISBN on Amazon is different from the one in my book")
    assert d.priority is Priority.HIGH and d.applied_rules


def test_print_defect_has_high_floor():
    assert resolve(Priority.LOW, Category.PRINTING, "My author copies contain missing pages").priority is Priority.HIGH


def test_legal_language_forces_critical():
    d = resolve(Priority.MEDIUM, Category.ROYALTY, "I will take legal action if this isn't fixed")
    assert d.priority is Priority.CRITICAL


def test_model_cannot_pick_critical_without_escalation_signal():
    d = resolve(Priority.CRITICAL, Category.GENERAL, "Please add a dedication page to my book")
    assert d.priority is Priority.HIGH
    assert "critical_requires_escalation_signal" in d.applied_rules[0]


def test_bio_update_is_capped_at_low():
    assert resolve(Priority.HIGH, Category.GENERAL, "Can I update my author bio?").priority is Priority.LOW


def test_no_rule_leaves_model_priority_untouched():
    d = resolve(Priority.MEDIUM, Category.DISTRIBUTION, "My book is unavailable on Amazon")
    assert d.priority is Priority.MEDIUM and not d.overridden_model


async def test_pending_below_threshold_is_not_overdue_and_caps_priority(session_factory):
    b = await book(session_factory, BELOW_THRESHOLD_BOOK["book_id"])
    assert assess_royalty(b, TODAY).state is RoyaltyState.BELOW_THRESHOLD
    d = resolve(Priority.HIGH, Category.ROYALTY, "Where is my royalty payment?", b)
    assert d.priority is Priority.MEDIUM


async def test_pending_above_threshold_and_stale_is_flagged_overdue(session_factory):
    b = await book(session_factory, NEVER_PAID_OVERDUE_BOOK["book_id"])
    assert assess_royalty(b, TODAY).state is RoyaltyState.POSSIBLY_OVERDUE
    assert resolve(Priority.LOW, Category.ROYALTY, "Where is my royalty?", b).priority is Priority.HIGH


async def test_recent_publication_is_inside_payout_window(session_factory):
    b = await book(session_factory, NEVER_PAID_OVERDUE_BOOK["book_id"])
    soon_after_publication = b.publication_date + timedelta(days=30)
    assert assess_royalty(b, soon_after_publication).state is RoyaltyState.WITHIN_PAYOUT_WINDOW


async def test_zero_balance_and_in_production_book(session_factory):
    for src in (PAID_UP_BOOK, IN_PRODUCTION_BOOK):
        assert assess_royalty(await book(session_factory, src["book_id"]), TODAY).state is RoyaltyState.NO_BALANCE


def test_baseline_without_ai_still_applies_rules():
    d = engine.baseline(category=None, text="Pages are torn and some pages are missing pages", book=None, today=TODAY)
    assert d.priority is Priority.HIGH
    assert engine.baseline(category=None, text="hello there", book=None, today=TODAY).priority is Priority.MEDIUM
