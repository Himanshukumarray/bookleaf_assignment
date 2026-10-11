from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.models.enums import Category, Priority

T = TypeVar("T")


class ClassificationResult(BaseModel):
    """Structured output contract for the single classify+prioritise call."""

    category: Category
    priority: Priority
    category_confidence: float = Field(ge=0.0, le=1.0)
    priority_confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=300, description="One or two sentences, no step-by-step reasoning.")
    needs_human_attention: bool


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    value: T
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    attempts: int = 1
