"""AI evaluation harness.

Offline (default, free):  pytest tests/ai            -> schema + guardrail checks, no model calls
Live (optional, costs $): python -m app.ai.evaluation --live   -> real Gemini classification vs labels
Free Gemini tier:         python -m app.ai.evaluation --live --free-tier

Metrics: category accuracy, priority agreement (within [min, max] bounds), schema-valid rate.
Provider failures (429/5xx/timeouts that outlast the retries) are reported as *API failures* and are
excluded from the quality percentages: they say nothing about the model. They are never counted as correct,
and no model output is ever faked or substituted.
"""
import argparse
import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.models.enums import Category, Priority

DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "eval_dataset.json"

FREE_TIER_MIN_DELAY_SECONDS = 13.0  # ~4.5 requests/minute, under the 5 RPM free-tier quota
FREE_TIER_MIN_RETRIES = 6
MAX_BACKOFF_SECONDS = 120.0
_RETRY_HINT = re.compile(r"retry (?:in|after)\s*((?:\d+h)?(?:\d+m)?(?:\d+(?:\.\d+)?s)?)", re.IGNORECASE)
_HINT_PART = re.compile(r"(\d+(?:\.\d+)?)([hms])")

Logger = Callable[[str], None]


class ApiUnavailable(Exception):
    """The provider could not produce an answer for a case (quota, outage, bad key). Not a model-quality result."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class EvalCase:
    id: str
    text: str
    book_id: str | None
    expected_category: Category
    min_priority: Priority | None = None
    max_priority: Priority | None = None
    rule_enforced: bool = False

    def priority_ok(self, priority: Priority) -> bool:
        if self.min_priority and priority.rank < self.min_priority.rank:
            return False
        if self.max_priority and priority.rank > self.max_priority.rank:
            return False
        return True


@dataclass(frozen=True)
class Prediction:
    category: Category
    priority: Priority
    latency_ms: int | None = None


@dataclass
class EvalReport:
    total: int = 0
    api_failures: int = 0
    category_correct: int = 0
    priority_agree: int = 0
    schema_valid: int = 0
    failures: list[str] = field(default_factory=list)
    api_failure_notes: list[str] = field(default_factory=list)
    latencies_ms: list[int] = field(default_factory=list)

    @property
    def completed(self) -> int:
        """Cases where the model actually answered (validly or not)."""
        return self.total - self.api_failures

    @staticmethod
    def _rate(part: int, whole: int) -> float:
        return part / whole if whole else 0.0

    @property
    def completion_rate(self) -> float:
        return self._rate(self.completed, self.total)

    @property
    def category_accuracy(self) -> float:
        return self._rate(self.category_correct, self.completed)

    @property
    def priority_agreement(self) -> float:
        return self._rate(self.priority_agree, self.completed)

    @property
    def schema_valid_rate(self) -> float:
        return self._rate(self.schema_valid, self.completed)

    def summary(self) -> str:
        c = self.completed
        lines = [
            "BookLeaf AI Evaluation",
            "",
            f"Total cases: {self.total}",
            f"Completed: {c}/{self.total} ({self.completion_rate:.0%})",
            f"API failures: {self.api_failures}",
            "",
            "Classification (over completed cases):",
            f"{self.category_correct}/{c} correct - {self.category_accuracy:.0%}",
            "",
            "Priority (over completed cases):",
            f"{self.priority_agree}/{c} within bounds - {self.priority_agreement:.0%}",
            "",
            "Structured output (over completed cases):",
            f"{self.schema_valid}/{c} valid - {self.schema_valid_rate:.0%}",
            "",
            "Average latency of successful calls:",
            f"{sum(self.latencies_ms) / len(self.latencies_ms):.0f} ms over {len(self.latencies_ms)} calls"
            if self.latencies_ms
            else "n/a (no successful live calls)",
        ]
        if self.failures:
            lines += ["", "Model-quality failures:"] + [f"  - {f}" for f in self.failures]
        if self.api_failure_notes:
            lines += ["", "API failures (not model quality):"] + [f"  - {f}" for f in self.api_failure_notes]
        return "\n".join(lines)


def load_cases(path: Path = DATASET_PATH) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))["cases"]
    return [
        EvalCase(
            id=c["id"],
            text=c["text"],
            book_id=c.get("book_id"),
            expected_category=Category(c["expected_category"]),
            min_priority=Priority(c["min_priority"]) if c.get("min_priority") else None,
            max_priority=Priority(c["max_priority"]) if c.get("max_priority") else None,
            rule_enforced=c.get("rule_enforced", False),
        )
        for c in raw
    ]


def select_cases(cases: list[EvalCase], start: int = 0, count: int | None = None) -> list[EvalCase]:
    """0-based `start`, optional `count`; `--start 0 --count 5` -> first five cases."""
    if start < 0 or (count is not None and count < 1):
        raise ValueError("--start must be >= 0 and --count >= 1")
    return cases[start : None if count is None else start + count]


def retry_hint_seconds(message: str) -> float | None:
    """Provider-suggested wait ('Please retry in 42.5s' / '6h20m26.1s'), if the error message carries one."""
    match = _RETRY_HINT.search(message)
    if not match or not match.group(1):
        return None
    units = {"h": 3600, "m": 60, "s": 1}
    return sum(float(value) * units[unit] for value, unit in _HINT_PART.findall(match.group(1)))


async def call_with_backoff(
    call: Callable[[], Awaitable],
    *,
    max_retries: int,
    base_delay_seconds: float = 5.0,
    max_delay_seconds: float = MAX_BACKOFF_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    log: Logger = print,
):
    """Live-evaluation retry: re-run the SAME case on transient errors (429/5xx/timeouts).

    Wait = max(provider hint + 1s, exponential backoff), capped. Permanent errors (bad key, 400/401/403)
    are not retried. After `max_retries` retries the case is reported as an API failure.
    """
    from app.ai.errors import AIInvalidResponseError, AIPermanentError, AITransientError

    retries = 0
    while True:
        try:
            return await call()
        except AITransientError as exc:
            if retries >= max_retries:
                raise ApiUnavailable(f"{exc.message} (gave up after {retries} retries)", status_code=exc.status_code) from exc
            hint = retry_hint_seconds(exc.message)
            if hint is not None and hint > max_delay_seconds:
                # e.g. a daily quota ("retry in 6h20m"): waiting here cannot help, so fail fast and say why.
                raise ApiUnavailable(
                    f"{exc.message} (provider asks for a {hint / 60:.0f} min wait; not retrying)", status_code=exc.status_code
                ) from exc
            delay = min(max(base_delay_seconds * 2**retries, (hint + 1) if hint else 0), max_delay_seconds)
            retries += 1
            log(f"    {exc.status_code or 'transient error'} received, retry {retries}/{max_retries} in {delay:.0f}s...")
            await sleep(delay)
        except AIInvalidResponseError:
            raise  # a model-quality outcome; the caller records it as a schema failure
        except AIPermanentError as exc:
            raise ApiUnavailable(exc.message, status_code=exc.status_code) from exc


async def run_evaluation(
    cases: list[EvalCase],
    predict: Callable[[EvalCase], Awaitable[Prediction | None]],
    *,
    delay_seconds: float = 0.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    log: Logger | None = None,
) -> EvalReport:
    """Run cases one at a time (never concurrently).

    `predict` returns None when the model output was missing/invalid (counts against schema validity) and
    raises `ApiUnavailable` when the provider failed (counted separately, excluded from quality rates).
    `delay_seconds` paces consecutive cases; offline runs leave it at 0.
    """
    report = EvalReport(total=len(cases))
    for index, case in enumerate(cases, start=1):
        if delay_seconds > 0 and index > 1:
            if log:
                log(f"    waiting {delay_seconds:.0f}s for rate limit...")
            await sleep(delay_seconds)
        try:
            prediction = await predict(case)
        except ApiUnavailable as exc:
            report.api_failures += 1
            report.api_failure_notes.append(f"{case.id}: {exc.message[:160]}")
            if log:
                log(f"[{index}/{len(cases)}] {case.id} ... API FAILURE")
            continue
        if prediction is None:
            report.failures.append(f"{case.id}: no schema-valid output")
            if log:
                log(f"[{index}/{len(cases)}] {case.id} ... FAIL (no schema-valid output)")
            continue
        report.schema_valid += 1
        problems = []
        if prediction.category is case.expected_category:
            report.category_correct += 1
        else:
            problems.append("category")
            report.failures.append(f"{case.id}: category {prediction.category.value!r} != {case.expected_category.value!r}")
        if case.priority_ok(prediction.priority):
            report.priority_agree += 1
        else:
            problems.append("priority")
            report.failures.append(f"{case.id}: priority {prediction.priority.value} outside bounds")
        if prediction.latency_ms is not None:
            report.latencies_ms.append(prediction.latency_ms)
        if log:
            log(f"[{index}/{len(cases)}] {case.id} ... " + ("PASS" if not problems else f"FAIL ({', '.join(problems)})"))
    return report


async def _live(args: argparse.Namespace) -> int:  # pragma: no cover - needs network + API key
    from app.ai.classifier import TicketClassifier
    from app.ai.context_builder import ContextBuilder
    from app.ai.errors import AIInvalidResponseError
    from app.ai.priority import PriorityEngine
    from app.ai.providers.gemini import GeminiProvider
    from app.core.config import get_settings
    from app.db.session import build_engine, build_session_factory
    from app.repositories.book_repository import BookRepository

    settings = get_settings()
    delay = settings.ai_eval_delay_seconds if args.delay is None else args.delay
    max_retries = args.max_retries if args.max_retries is not None else settings.ai_eval_max_retries
    if args.free_tier:
        delay = max(delay, FREE_TIER_MIN_DELAY_SECONDS)
        max_retries = max(max_retries, FREE_TIER_MIN_RETRIES)

    # One provider attempt per call: the evaluation's own backoff (below) owns retrying, so a case is never
    # retried twice over. Production retry settings are untouched.
    classifier = TicketClassifier(GeminiProvider(settings), max_attempts=1, base_delay_seconds=0)
    priority_engine = PriorityEngine()
    factory = build_session_factory(build_engine(settings))
    cases = select_cases(load_cases(), args.start, args.count)
    print(f"Live evaluation: {len(cases)} case(s), model={settings.gemini_model}, "
          f"sequential, {delay:.0f}s between cases, up to {max_retries} retries on 429/5xx/timeouts.")

    async def predict(case: EvalCase) -> Prediction | None:
        async with factory() as session:
            book = await BookRepository(session).get_by_external_id(case.book_id) if case.book_id else None
        try:
            result = await call_with_backoff(
                lambda: classifier.classify(
                    subject=case.text[:80], description=case.text, book_hint=ContextBuilder.book_hint(book)
                ),
                max_retries=max_retries,
            )
        except AIInvalidResponseError:
            return None
        decision = priority_engine.resolve(model_priority=result.value.priority, category=result.value.category,
                                           text=case.text, book=book)
        return Prediction(result.value.category, decision.priority, result.latency_ms)

    report = await run_evaluation(cases, predict, delay_seconds=delay, log=print)
    print()
    print(report.summary())
    if report.completed == 0 or report.api_failures:
        return 2  # incomplete run: the quality numbers do not cover every case
    return 0 if report.category_accuracy >= args.threshold else 1


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Evaluate AI triage against the labelled dataset.")
    parser.add_argument("--live", action="store_true", help="Call Gemini (costs API credits)")
    parser.add_argument("--free-tier", action="store_true",
                        help=f"Quota-safe: >= {FREE_TIER_MIN_DELAY_SECONDS:.0f}s between cases, >= {FREE_TIER_MIN_RETRIES} retries")
    parser.add_argument("--delay", type=float, default=None, help="Seconds between live cases (default AI_EVAL_DELAY_SECONDS)")
    parser.add_argument("--max-retries", type=int, default=None, help="Retries per case on 429/5xx/timeout (default AI_EVAL_MAX_RETRIES)")
    parser.add_argument("--start", type=int, default=0, help="0-based index of the first case to run")
    parser.add_argument("--count", type=int, default=None, help="Number of cases to run (default: all remaining)")
    parser.add_argument("--threshold", type=float, default=0.8, help="Min category accuracy for exit code 0")
    args = parser.parse_args()
    if not args.live:
        parser.error("Offline evaluation runs under pytest (tests/ai). Pass --live for a real-model run.")
    try:
        select_cases(load_cases(), args.start, args.count)
    except ValueError as exc:
        parser.error(str(exc))
    raise SystemExit(asyncio.run(_live(args)))


if __name__ == "__main__":
    main()
