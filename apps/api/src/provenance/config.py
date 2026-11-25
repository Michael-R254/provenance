"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Cloudflare's documented test secret: every token passes. Development only.
TURNSTILE_TEST_SECRET = "1x0000000000000000000000000000000AA"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROVENANCE_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    allowed_origins: list[str] = ["http://localhost:3000"]
    database_url: str | None = None

    # Model provider
    llm_provider: Literal["mock", "ollama", "anthropic"] = "mock"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-haiku-5-5"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    max_output_tokens: int = 600
    llm_timeout_seconds: float = 30.0

    # Retrieval and answer limits
    top_n: int = 6
    evidence_min_similarity: float = 0.35
    max_question_chars: int = 500
    max_history_turns: int = 3
    max_history_chars: int = 1500

    # Cost and abuse controls
    daily_spend_cap_usd: float = 1.0
    session_secret: SecretStr | None = None
    session_ttl_seconds: int = 3600
    turnstile_secret: SecretStr = SecretStr(TURNSTILE_TEST_SECRET)
    ip_hash_salt: SecretStr = SecretStr("development-only-salt")
    rate_session_per_minute: int = 6
    rate_session_per_day: int = 60
    rate_ip_per_hour: int = 60
    rate_ip_sessions_per_hour: int = 10

    @model_validator(mode="after")
    def _production_is_locked_down(self) -> Self:
        if self.environment != "production":
            return self
        problems = []
        if self.llm_provider != "anthropic":
            problems.append("llm_provider must be anthropic")
        if self.anthropic_api_key is None:
            problems.append("anthropic_api_key is required")
        if self.session_secret is None or len(self.session_secret.get_secret_value()) < 32:
            problems.append("session_secret must be at least 32 characters")
        if self.turnstile_secret.get_secret_value() == TURNSTILE_TEST_SECRET:
            problems.append("turnstile_secret must be the real secret")
        if self.ip_hash_salt.get_secret_value() == "development-only-salt":
            problems.append("ip_hash_salt must be set")
        if self.database_url is None:
            problems.append("database_url is required")
        if problems:
            raise ValueError("unsafe production settings: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
