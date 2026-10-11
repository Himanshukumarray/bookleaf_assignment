from dataclasses import dataclass

from app.ai.grounding import GroundingReport, check_grounding
from app.ai.prompts import response as prompts
from app.ai.providers.base import AIProvider
from app.ai.retry import run_with_retry
from app.ai.schemas import ProviderResult

_MAX_DRAFT_CHARS = 2500


@dataclass
class GeneratedDraft:
    text: str
    grounding: GroundingReport


class ResponseGenerator:
    prompt_version = prompts.PROMPT_VERSION

    def __init__(
        self, provider: AIProvider, *, max_attempts: int, base_delay_seconds: float, max_output_tokens: int, sleep=None
    ):
        self._provider = provider
        self._max_attempts = max_attempts
        self._base_delay = base_delay_seconds
        self._max_output_tokens = max_output_tokens
        self._sleep = sleep

    async def generate(
        self,
        *,
        author_name: str,
        account_context: str,
        knowledge_context: str,
        subject: str,
        description: str,
        recent_messages: str,
    ) -> ProviderResult[GeneratedDraft]:
        user_prompt = prompts.build_user_prompt(
            author_name=author_name,
            account_context=account_context,
            knowledge_context=knowledge_context,
            subject=subject,
            description=description,
            recent_messages=recent_messages,
        )
        kwargs = {"sleep": self._sleep} if self._sleep else {}
        result = await run_with_retry(
            lambda: self._provider.generate_response(
                system_prompt=prompts.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_output_tokens=self._max_output_tokens,
            ),
            max_attempts=self._max_attempts,
            base_delay_seconds=self._base_delay,
            operation="draft",
            **kwargs,
        )
        text = result.value.strip()[:_MAX_DRAFT_CHARS]
        report = check_grounding(text, account_context, knowledge_context)  # author-claimed figures are NOT trusted facts
        return ProviderResult(GeneratedDraft(text, report), result.usage, result.latency_ms, result.attempts)
