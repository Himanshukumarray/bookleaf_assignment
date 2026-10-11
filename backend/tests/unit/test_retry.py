import pytest

from app.ai.errors import AIPermanentError, AITransientError
from app.ai.retry import run_with_retry
from app.ai.schemas import ProviderResult


class Flaky:
    def __init__(self, errors):
        self.errors, self.calls = list(errors), 0

    async def __call__(self):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return ProviderResult("ok")


async def run(call, attempts=3):
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    try:
        result = await run_with_retry(call, max_attempts=attempts, base_delay_seconds=1.0, sleep=fake_sleep)
        return result, sleeps, None
    except Exception as exc:  # noqa: BLE001
        return None, sleeps, exc


async def test_exponential_backoff_then_success():
    call = Flaky([AITransientError("429"), AITransientError("503")])
    result, sleeps, error = await run(call)
    assert error is None and result.attempts == 3 and call.calls == 3
    assert 0.8 < sleeps[0] < 1.2 and 1.7 < sleeps[1] < 2.3  # ~1s then ~2s


async def test_gives_up_after_max_attempts_and_reports_attempts():
    call = Flaky([AITransientError("503")] * 5)
    _, sleeps, error = await run(call)
    assert isinstance(error, AITransientError) and error.attempts == 3 and call.calls == 3 and len(sleeps) == 2


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_permanent_errors_fail_fast(status):
    call = Flaky([AIPermanentError("nope", status_code=status)])
    _, sleeps, error = await run(call)
    assert isinstance(error, AIPermanentError) and call.calls == 1 and sleeps == []


def test_failure_rate_limiter_window_expires():
    from app.core.rate_limit import FailureRateLimiter

    now = [0.0]
    limiter = FailureRateLimiter(max_failures=2, window_seconds=10, clock=lambda: now[0])
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert limiter.retry_after("k") == 10
    now[0] = 11.0
    assert limiter.retry_after("k") == 0
    limiter.record_failure("k")
    limiter.reset("k")
    assert limiter.retry_after("k") == 0
