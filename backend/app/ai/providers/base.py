from abc import ABC, abstractmethod
from enum import Enum

from app.ai.schemas import ClassificationResult, ProviderResult


class EmbeddingTask(str, Enum):
    DOCUMENT = "document"
    QUERY = "query"


class AIProvider(ABC):
    """Everything the application needs from an LLM vendor. Services depend on this, never on an SDK."""

    model_name: str
    embedding_model_name: str

    @abstractmethod
    async def classify_ticket(self, *, system_prompt: str, user_prompt: str) -> ProviderResult[ClassificationResult]:
        """Single structured-output call returning category + priority + confidences."""

    @abstractmethod
    async def generate_response(
        self, *, system_prompt: str, user_prompt: str, max_output_tokens: int
    ) -> ProviderResult[str]:
        """Free-text draft for a human agent to review."""

    @abstractmethod
    async def create_embedding(self, texts: list[str], *, task: EmbeddingTask) -> ProviderResult[list[list[float]]]:
        """One vector per input text."""
