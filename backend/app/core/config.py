"""Centralised, typed configuration. Nothing else in the codebase reads os.environ."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "BookLeaf Support Portal"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bookleaf_support"

    jwt_secret_key: str = "replace_with_a_secure_secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    login_max_failures: int = 5
    login_failure_window_seconds: int = 300

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    ai_max_retries: int = 3
    ai_retry_base_delay_seconds: float = 1.0
    ai_request_timeout_seconds: int = 60
    ai_max_response_tokens: int = 700
    ai_conversation_history_limit: int = 6
    ai_retrieval_top_k: int = 3
    # Live evaluation pacing only (python -m app.ai.evaluation --live); does not affect the application.
    ai_eval_delay_seconds: float = 13.0
    ai_eval_max_retries: int = 6

    cors_origins: str = "http://localhost:5173"

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.gemini_api_key) and not self.gemini_api_key.startswith("your_")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
