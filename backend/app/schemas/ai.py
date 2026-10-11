from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class KnowledgeRef(BaseModel):
    section: str
    title: str


class AIDraftOut(ORMModel):
    id: int
    draft: str
    model: str
    prompt_version: str
    grounding_warnings: list[str] = []
    knowledge: list[KnowledgeRef] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    created_at: datetime


class AIRunOut(ORMModel):
    id: int
    operation: str
    model: str
    prompt_version: str
    status: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    attempts: int
    error_type: str | None = None
    created_at: datetime


class AISystemStatus(BaseModel):
    provider_configured: bool
    model: str
    embedding_model: str
    knowledge_chunks: int
    knowledge_chunks_embedded: int


class EmbedResult(BaseModel):
    embedded_chunks: int
