"""Offline evaluation: free, deterministic. Live model evaluation: `python -m app.ai.evaluation --live`."""
from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.ai.errors import AIInvalidResponseError, AIPermanentError, AITransientError
from app.ai.evaluation import (
    ApiUnavailable,
    EvalCase,
    Prediction,
    call_with_backoff,
    load_cases,
    retry_hint_seconds,
    run_evaluation,
    select_cases,
)
from app.ai.priority import PriorityEngine
from app.ai.schemas import ClassificationResult
from app.models import Book
from app.models.enums import Category, Priority

TODAY = date(2026, 10, 8)
CASES = load_cases()


def test_dataset_is_large_and_covers_every_category():
    assert len(CASES) >= 20
    assert {c.expected_category for c in CASES} == set(Category)
    assert len({c.id for c in CASES}) == len(CASES)


async def test_harness_scores_a_perfect_classifier_at_100_percent():
    async def oracle(case: EvalCase):
        return Prediction(case.expected_category, case.min_priority or case.max_priority or Priority.MEDIUM)

    report = await run_evaluation(CASES, oracle)
    assert report.category_accuracy == 1.0 and report.priority_agreement == 1.0 and report.schema_valid_rate == 1.0


async def test_harness_reports_misclassifications_and_schema_failures():
    async def broken(case: EvalCase):
        if case.id == "E01":
            return None
        return Prediction(Category.GENERAL, Priority.LOW)

    report = await run_evaluation(CASES, broken)
    assert report.schema_valid < report.total and report.category_accuracy < 0.5
    assert any(f.startswith("E01") for f in report.failures)


async def test_api_failures_are_reported_separately_and_never_counted_correct_or_incorrect():
    async def flaky(case: EvalCase):
        if case.id in {"E02", "E03"}:
            raise ApiUnavailable("429 quota", status_code=429)
        return Prediction(case.expected_category, case.min_priority or case.max_priority or Priority.MEDIUM)

    report = await run_evaluation(CASES, flaky)
    assert report.api_failures == 2 and report.completed == len(CASES) - 2
    assert report.category_accuracy == 1.0 and report.schema_valid_rate == 1.0  # quality judged on completed only
    assert report.failures == [] and len(report.api_failure_notes) == 2
    assert "Completed:" in report.summary() and "API failures: 2" in report.summary()


async def test_pacing_waits_between_cases_only_and_is_off_by_default():
    waits: list[float] = []

    async def fake_sleep(seconds: float):
        waits.append(seconds)

    async def oracle(case: EvalCase):
        return Prediction(case.expected_category, case.min_priority or case.max_priority or Priority.MEDIUM)

    await run_evaluation(CASES[:4], oracle, sleep=fake_sleep)
    assert waits == []
    await run_evaluation(CASES[:4], oracle, delay_seconds=13, sleep=fake_sleep)
    assert waits == [13, 13, 13]


async def test_backoff_retries_same_call_and_respects_provider_retry_hint():
    waits: list[float] = []
    calls = {"n": 0}

    async def fake_sleep(seconds: float):
        waits.append(seconds)

    async def call():
        calls["n"] += 1
        if calls["n"] == 1:
            raise AITransientError("Gemini API error 429: quota. Please retry in 42.5s.", status_code=429)
        if calls["n"] == 2:
            raise AITransientError("Gemini API error 503: busy", status_code=503)
        return "ok"

    assert await call_with_backoff(call, max_retries=4, base_delay_seconds=5, sleep=fake_sleep, log=lambda _m: None) == "ok"
    assert calls["n"] == 3
    assert waits == [pytest.approx(43.5), 10]  # hint+1 beats 5s base; then base*2


async def test_backoff_is_bounded_and_gives_up_as_api_failure():
    async def fake_sleep(_s: float):
        pass

    calls = {"n": 0}

    async def call():
        calls["n"] += 1
        raise AITransientError("Gemini API error 503", status_code=503)

    with pytest.raises(ApiUnavailable):
        await call_with_backoff(call, max_retries=2, sleep=fake_sleep, log=lambda _m: None)
    assert calls["n"] == 3  # first try + 2 retries, then stop


async def test_backoff_does_not_retry_permanent_errors_and_keeps_schema_failures_distinct():
    calls = {"n": 0}

    async def bad_key():
        calls["n"] += 1
        raise AIPermanentError("Gemini API error 403: bad key", status_code=403)

    with pytest.raises(ApiUnavailable):
        await call_with_backoff(bad_key, max_retries=5, log=lambda _m: None)
    assert calls["n"] == 1

    async def bad_schema():
        raise AIInvalidResponseError("does not match schema")

    with pytest.raises(AIInvalidResponseError):  # model-quality outcome, not an API failure
        await call_with_backoff(bad_schema, max_retries=5, log=lambda _m: None)


async def test_backoff_fails_fast_when_provider_asks_for_hours():
    """A daily quota ('retry in 6h20m') cannot be waited out inside one run: report it, don't spin."""
    slept: list[float] = []

    async def fake_sleep(seconds: float):
        slept.append(seconds)

    async def call():
        raise AITransientError("Gemini API error 429: Quota exceeded. Please retry in 6h20m26.17s.", status_code=429)

    with pytest.raises(ApiUnavailable, match="not retrying"):
        await call_with_backoff(call, max_retries=6, sleep=fake_sleep, log=lambda _m: None)
    assert slept == []
    assert retry_hint_seconds("Please retry in 6h20m26.5s.") == pytest.approx(6 * 3600 + 20 * 60 + 26.5)
    assert retry_hint_seconds("Please retry in 42.5s.") == 42.5
    assert retry_hint_seconds("no hint here") is None


def test_select_cases_supports_subsets():
    assert [c.id for c in select_cases(CASES, 0, 5)] == [c.id for c in CASES[:5]]
    assert select_cases(CASES, 20) == CASES[20:]
    with pytest.raises(ValueError):
        select_cases(CASES, -1)


@pytest.mark.parametrize("case", [c for c in CASES if c.rule_enforced], ids=lambda c: c.id)
async def test_guardrails_enforce_priority_bounds_regardless_of_model(case, session_factory):
    """Worst case for each rule-covered example: the model proposes the most wrong priority."""
    book = None
    if case.book_id:
        async with session_factory() as s:
            book = (await s.execute(select(Book).where(Book.external_book_id == case.book_id))).scalar_one()
    engine = PriorityEngine()
    for proposed in (Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.CRITICAL):
        decision = engine.resolve(model_priority=proposed, category=case.expected_category, text=case.text, book=book, today=TODAY)
        assert case.priority_ok(decision.priority), f"{case.id}: model said {proposed}, guardrails gave {decision.priority}"


def test_classification_schema_rejects_out_of_contract_output():
    good = dict(category="Royalty & Payments", priority="HIGH", category_confidence=0.9, priority_confidence=0.8,
                reason="x", needs_human_attention=True)
    assert ClassificationResult.model_validate(good).category is Category.ROYALTY
    for bad in (
        {**good, "category": "Billing"},            # not one of the six categories
        {**good, "priority": "URGENT"},              # not a priority value
        {**good, "category_confidence": 1.7},        # confidence out of range
        {k: v for k, v in good.items() if k != "reason"},
    ):
        with pytest.raises(ValidationError):
            ClassificationResult.model_validate(bad)
