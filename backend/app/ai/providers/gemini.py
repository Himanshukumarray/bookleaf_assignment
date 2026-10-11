"""Gemini implementation of AIProvider. The only module that imports google-genai."""
import asyncio
import logging
import time

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.ai.errors import (
    AIInvalidResponseError,
    AINotConfiguredError,
    AIPermanentError,
    AITransientError,
)
from app.ai.providers.base import AIProvider, EmbeddingTask
from app.ai.schemas import ClassificationResult, ProviderResult, Usage
from app.core.config import Settings

logger = logging.getLogger(__name__)

_TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}


def _translate(exc: Exception) -> Exception:
    """Map SDK/transport exceptions onto the provider-neutral taxonomy."""
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        message = f"Gemini API error {code}: {getattr(exc, 'message', None) or exc.__class__.__name__}"
        if code in _TRANSIENT_HTTP:
            return AITransientError(message, status_code=code)
        return AIPermanentError(message, status_code=code)
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException, httpx.TransportError)):
        return AITransientError(f"Network/timeout error: {exc.__class__.__name__}")
    return AIPermanentError(f"Unexpected provider error: {exc.__class__.__name__}")


def _usage(response: types.GenerateContentResponse) -> Usage:
    meta = response.usage_metadata
    if meta is None:
        return Usage()
    return Usage(meta.prompt_token_count or 0, meta.candidates_token_count or 0)


class GeminiProvider(AIProvider):
    def __init__(self, settings: Settings):
        if not settings.ai_configured:
            raise AINotConfiguredError("GEMINI_API_KEY is not configured.")
        self.model_name = settings.gemini_model
        self.embedding_model_name = settings.gemini_embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=settings.ai_request_timeout_seconds * 1000),
        )

    def _config(self, **kwargs) -> types.GenerateContentConfig:
        # Flash models: disable hidden "thinking" tokens; they cost money and eat the output budget.
        if "flash" in self.model_name:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kwargs)

    async def classify_ticket(self, *, system_prompt: str, user_prompt: str) -> ProviderResult[ClassificationResult]:
        started = time.perf_counter()
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=self._config(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=ClassificationResult,
                    temperature=0.0,
                    max_output_tokens=400,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - translated, never swallowed
            raise _translate(exc) from exc

        try:
            parsed = response.parsed
            if not isinstance(parsed, ClassificationResult):
                parsed = ClassificationResult.model_validate_json(response.text or "")
        except (ValidationError, ValueError) as exc:
            raise AIInvalidResponseError("Model returned output that does not match the classification schema.") from exc
        return ProviderResult(parsed, _usage(response), int((time.perf_counter() - started) * 1000))

    async def generate_response(
        self, *, system_prompt: str, user_prompt: str, max_output_tokens: int
    ) -> ProviderResult[str]:
        started = time.perf_counter()
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=self._config(
                    system_instruction=system_prompt, temperature=0.4, max_output_tokens=max_output_tokens
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc
        text = (response.text or "").strip()
        if not text:
            raise AIInvalidResponseError("Model returned an empty response (possibly blocked by safety filters).")
        return ProviderResult(text, _usage(response), int((time.perf_counter() - started) * 1000))

    async def create_embedding(self, texts: list[str], *, task: EmbeddingTask) -> ProviderResult[list[list[float]]]:
        started = time.perf_counter()
        task_type = "RETRIEVAL_DOCUMENT" if task is EmbeddingTask.DOCUMENT else "RETRIEVAL_QUERY"
        try:
            response = await self._client.aio.models.embed_content(
                model=self.embedding_model_name,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self._dimensions),
            )
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc
        vectors = [list(e.values) for e in (response.embeddings or []) if e.values]
        if len(vectors) != len(texts):
            raise AIInvalidResponseError("Embedding count did not match input count.")
        return ProviderResult(vectors, Usage(), int((time.perf_counter() - started) * 1000))
