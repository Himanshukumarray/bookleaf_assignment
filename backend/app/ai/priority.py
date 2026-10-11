"""Hybrid priority: the model proposes, deterministic business rules dispose.

The LLM never has the last word on priority. Rules can raise a floor (ISBN errors, defects, legal
threats, evidenced overdue royalties) or impose a ceiling (CRITICAL requires an escalation signal;
below-threshold royalty balances and low-urgency topics are capped).
"""
import re
from dataclasses import dataclass, field
from datetime import date

from app.ai.royalty import RoyaltyState, assess_royalty
from app.models.book import Book
from app.models.enums import Category, Priority

_CRITICAL_SIGNALS = re.compile(
    r"\b(legal action|lawyer|attorney|advocate|sue\b|suing|lawsuit|court|consumer forum|police|fraud|scam|cheat(ed|ing)?|"
    r"defam|plagiari[sz]|copyright infring|media|press|social media|expose|report you)\b",
    re.IGNORECASE,
)
_ISBN_PROBLEM = re.compile(
    r"\b(wrong|different|mismatch|incorrect|duplicate|same isbn|another book|not matching|doesn'?t match|does not match)\b",
    re.IGNORECASE,
)
_DEFECT = re.compile(
    r"\b(missing pages?|torn|damaged|defect(ive)?|misprint(ed)?|blank pages?|pages? (fell|falling|coming) out|"
    r"wrong cover|smudged|smeared|upside.?down|binding (broke|broken|issue)|misaligned|poor print)\b",
    re.IGNORECASE,
)
_LOW_URGENCY = re.compile(r"\b(author bio|my bio|bio update|update my bio|profile (photo|picture)|about the author)\b", re.IGNORECASE)
_ROYALTY_WORDS = re.compile(r"\b(royalt(y|ies)|payment|payout|paid|bank)\b", re.IGNORECASE)


@dataclass
class PriorityDecision:
    priority: Priority
    applied_rules: list[str] = field(default_factory=list)

    @property
    def overridden_model(self) -> bool:
        return bool(self.applied_rules)


def _raise_to(current: Priority, floor: Priority) -> Priority:
    return floor if floor.rank > current.rank else current


def _lower_to(current: Priority, ceiling: Priority) -> Priority:
    return ceiling if ceiling.rank < current.rank else current


class PriorityEngine:
    def resolve(
        self,
        *,
        model_priority: Priority,
        category: Category | None,
        text: str,
        book: Book | None,
        today: date | None = None,
    ) -> PriorityDecision:
        today = today or date.today()
        priority = model_priority
        rules: list[str] = []

        def raise_floor(floor: Priority, rule: str) -> None:
            nonlocal priority
            if floor.rank > priority.rank:
                priority = floor
                rules.append(f"{rule}->min {floor.value}")

        def cap(ceiling: Priority, rule: str) -> None:
            nonlocal priority
            if priority.rank > ceiling.rank:
                priority = ceiling
                rules.append(f"{rule}->max {ceiling.value}")

        has_critical_signal = bool(_CRITICAL_SIGNALS.search(text))

        # Ceilings first, so later floors can legitimately re-raise.
        if not has_critical_signal:
            cap(Priority.HIGH, "critical_requires_escalation_signal")
            if category is Category.GENERAL and _LOW_URGENCY.search(text):
                cap(Priority.LOW, "low_urgency_topic")
            if category is Category.ROYALTY and book is not None:
                if assess_royalty(book, today).state in (RoyaltyState.BELOW_THRESHOLD, RoyaltyState.NO_BALANCE):
                    cap(Priority.MEDIUM, "royalty_balance_not_payable")

        # Floors.
        if has_critical_signal:
            raise_floor(Priority.CRITICAL, "legal_or_escalation_language")
        if (category is Category.ISBN or "isbn" in text.lower()) and _ISBN_PROBLEM.search(text):
            raise_floor(Priority.HIGH, "isbn_error")
        if (category is Category.PRINTING or category is None) and _DEFECT.search(text):
            raise_floor(Priority.HIGH, "print_defect")
        if (category is Category.ROYALTY or (category is None and _ROYALTY_WORDS.search(text))) and book is not None:
            if assess_royalty(book, today).state is RoyaltyState.POSSIBLY_OVERDUE:
                raise_floor(Priority.HIGH, "royalty_overdue_evidence")

        return PriorityDecision(priority, rules)

    def baseline(self, *, category: Category | None, text: str, book: Book | None, today: date | None = None) -> PriorityDecision:
        """No-AI fallback: MEDIUM adjusted by the same deterministic rules."""
        return self.resolve(model_priority=Priority.MEDIUM, category=category, text=text, book=book, today=today)
