import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.ai.errors import AIError, AITransientError
from app.ai.schemas import ProviderResult

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def run_with_retry(
    call: Callable[[], Awaitable[ProviderResult[T]]],
    *,
    max_attempts: int,
    base_delay_seconds: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    operation: str = "ai_call",
) -> ProviderResult[T]:
    """Retry transient failures with exponential backoff + jitter; fail fast on permanent ones.

    Delays: base, 2*base, 4*base ... (e.g. 1s, 2s). The final error carries `.attempts`.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            result = await call()
            return ProviderResult(result.value, result.usage, result.latency_ms, attempts=attempt)
        except AITransientError as exc:
            exc.attempts = attempt
            if attempt >= max_attempts:
                logger.warning("%s failed after %d attempts: %s", operation, attempt, exc.message)
                raise
            delay = base_delay_seconds * (2 ** (attempt - 1)) * random.uniform(0.9, 1.1)
            logger.info("%s transient failure (attempt %d/%d), retrying in %.1fs", operation, attempt, max_attempts, delay)
            await sleep(delay)
        except AIError as exc:  # permanent: never retried
            exc.attempts = attempt
            raise
