"""Application settings, read from environment variables (and .env during local development)."""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/infrastructure/settings.py -> repository root. The file is absent in
# containers, where every value comes from real environment variables.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # Local-development default; matches the defaults in docker-compose.yml.
    database_url: str = "postgresql+psycopg://educommute:educommute_dev@localhost:5432/educommute"
    # Comma-separated origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    # Requests one client address may make per minute; 0 switches the limit off.
    # One page of the app makes about six calls, and moving a slider makes more.
    rate_limit_per_minute: int = 120

    # --- AI layer. Without a key every AI feature is switched off and the rest
    # of the app works as before. SecretStr keeps the key out of logs and reprs.
    gemini_api_key: SecretStr | None = None
    gemini_text_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-2"
    # A request waits at most this long for the model before it falls back.
    llm_timeout_seconds: float = 10.0
    # Requests one client address may make per minute to the endpoints that call
    # the model; 0 switches this limit off. It protects the free quota.
    ai_rate_limit_per_minute: int = 10
    # Requests per day the free tier allows for each model; a hard limit. When a
    # model's count reaches it, its features stay off until the provider's next
    # day (midnight Pacific time). Check the current figures in Google AI Studio
    # (Usage and limits) and lower these to keep some requests in reserve.
    ai_daily_text_requests: int = 500
    ai_daily_embedding_requests: int = 1000
    # The free tier also limits embedded texts per minute (100 when checked on
    # 2026-10-16); offline jobs pace themselves below it.
    ai_embedding_texts_per_minute: int = 90
    # A passage counts as evidence for a question only at or above this cosine
    # similarity. The value belongs to the embedding model: measured for
    # gemini-embedding-2 with the evaluation in backend/evaluation/.
    rag_min_similarity: float = 0.68

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_the_psycopg_driver(cls, value: object) -> object:
        """Hosted databases (Neon, Render, Supabase) hand out plain
        "postgresql://" or "postgres://" addresses; SQLAlchemy needs to be told
        to use psycopg 3, the driver this project installs."""
        if isinstance(value, str):
            for prefix in ("postgresql://", "postgres://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _blank_key_means_no_key(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def ai_enabled(self) -> bool:
        return self.gemini_api_key is not None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
