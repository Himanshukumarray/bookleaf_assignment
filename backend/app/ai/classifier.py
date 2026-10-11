from app.ai.prompts import classification as prompts
from app.ai.providers.base import AIProvider
from app.ai.retry import run_with_retry
from app.ai.schemas import ClassificationResult, ProviderResult


class TicketClassifier:
    """One model call yields category + priority proposal + confidences (cheaper than two calls)."""

    prompt_version = prompts.PROMPT_VERSION

    def __init__(self, provider: AIProvider, *, max_attempts: int, base_delay_seconds: float, sleep=None):
        self._provider = provider
        self._max_attempts = max_attempts
        self._base_delay = base_delay_seconds
        self._sleep = sleep

    async def classify(self, *, subject: str, description: str, book_hint: str | None) -> ProviderResult[ClassificationResult]:
        user_prompt = prompts.build_user_prompt(subject=subject, description=description, book_hint=book_hint)
        kwargs = {"sleep": self._sleep} if self._sleep else {}
        return await run_with_retry(
            lambda: self._provider.classify_ticket(system_prompt=prompts.SYSTEM_PROMPT, user_prompt=user_prompt),
            max_attempts=self._max_attempts,
            base_delay_seconds=self._base_delay,
            operation="classify",
            **kwargs,
        )
