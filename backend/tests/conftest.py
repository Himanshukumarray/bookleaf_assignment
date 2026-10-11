import hashlib
import re
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.ai.errors import AIError
from app.ai.knowledge_base import sync_knowledge_sections
from app.ai.providers.base import AIProvider, EmbeddingTask
from app.ai.schemas import ClassificationResult, ProviderResult, Usage
from app.core import security
from app.core.config import Settings
from app.db.base import Base
from app.db.seed import seed_operational_data
from app.main import create_app
from app.models.enums import Category, Priority
from tests.dataset import FIRST_AUTHOR, FIRST_BOOK, SECOND_AUTHOR

AUTHOR_PASSWORD = "Author@123"
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@bookleaf.com", "Admin@123"


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """Argon2 with minimal cost so seeding 11 users per test stays fast."""
    monkeypatch.setattr(security, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))


class FakeProvider(AIProvider):
    """Scriptable AIProvider: no network, deterministic bag-of-words embeddings."""

    model_name = "fake-model"
    embedding_model_name = "fake-embedding"

    def __init__(self) -> None:
        self.classification = ClassificationResult(
            category=Category.GENERAL, priority=Priority.MEDIUM, category_confidence=0.9,
            priority_confidence=0.8, reason="Fake classification.", needs_human_attention=False,
        )
        self.draft_text = "Hi there,\n\nThanks for reaching out. We are looking into this.\n\nWarm regards,\nBookLeaf Support Team"
        self.classify_errors: list[AIError] = []   # raised in order, then success
        self.draft_errors: list[AIError] = []
        self.embedding_error: AIError | None = None
        self.classify_calls = 0
        self.draft_calls = 0
        self.embed_calls = 0
        self.last_draft_prompt = ""
        self.last_classify_prompt = ""

    async def classify_ticket(self, *, system_prompt: str, user_prompt: str):
        self.classify_calls += 1
        self.last_classify_prompt = user_prompt
        if self.classify_errors:
            raise self.classify_errors.pop(0)
        return ProviderResult(self.classification, Usage(120, 40), 25)

    async def generate_response(self, *, system_prompt: str, user_prompt: str, max_output_tokens: int):
        self.draft_calls += 1
        self.last_draft_prompt = user_prompt
        if self.draft_errors:
            raise self.draft_errors.pop(0)
        return ProviderResult(self.draft_text, Usage(900, 150), 60)

    async def create_embedding(self, texts, *, task: EmbeddingTask):
        self.embed_calls += 1
        if self.embedding_error:
            raise self.embedding_error
        return ProviderResult([self.embed(t) for t in texts], Usage(), 5)

    @staticmethod
    def embed(text: str, dims: int = 64) -> list[float]:
        vec = [0.0] * dims
        for word in re.findall(r"[a-z]+", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % dims] += 1.0
        return vec


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret_key="test-secret-key-that-is-at-least-32-bytes", gemini_api_key="", ai_retry_base_delay_seconds=0.0, ai_max_retries=3)


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed_operational_data(session)
        await sync_knowledge_sections(session)
        await session.commit()
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def app(settings, session_factory, provider):
    return create_app(settings, session_factory=session_factory, ai_provider=provider)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client: httpx.AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin_headers(client) -> dict[str, str]:
    return await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest_asyncio.fixture
async def author_headers(client) -> dict[str, str]:  # first author in the official dataset
    return await login(client, FIRST_AUTHOR["email"], AUTHOR_PASSWORD)


@pytest_asyncio.fixture
async def other_headers(client) -> dict[str, str]:  # second author in the official dataset
    return await login(client, SECOND_AUTHOR["email"], AUTHOR_PASSWORD)


async def create_ticket(client, headers, *, book_id=FIRST_BOOK["book_id"], subject="Question about my book",
                        description="I have a question about my book and would like some help please."):
    response = await client.post("/api/v1/tickets", headers=headers,
                                 json={"book_id": book_id, "subject": subject, "description": description})
    assert response.status_code == 201, response.text
    return response.json()
