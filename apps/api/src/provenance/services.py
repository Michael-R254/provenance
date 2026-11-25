"""Long-lived objects the endpoints share. Tests build their own with fakes."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
from psycopg_pool import ConnectionPool

from provenance.config import Settings
from provenance.embedding import DEFAULT_MODEL, EMBEDDING_DIM, Embedder, FastEmbedEmbedder
from provenance.llm import AnthropicProvider, LLMProvider, MockProvider, OllamaProvider
from provenance.retrieval import Retriever
from provenance.sessions import CloudflareTurnstile, SessionSigner, TurnstileVerifier


class LazyFastEmbed:
    """Loads the embedding model on first use, so starting the app (and its tests) stays fast."""

    model_name = DEFAULT_MODEL
    dim = EMBEDDING_DIM

    def __init__(self) -> None:
        self._inner: FastEmbedEmbedder | None = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self._inner is None:
            self._inner = FastEmbedEmbedder(self.model_name)
        return self._inner.embed(texts)


class Database:
    def __init__(self, url: str, max_size: int = 5) -> None:
        self._pool = ConnectionPool(
            url, min_size=0, max_size=max_size, kwargs={"autocommit": True}, open=False
        )

    def open(self) -> None:
        self._pool.open()

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        with self._pool.connection() as conn:
            yield conn


@dataclass
class Services:
    database: Database | None
    retriever: Retriever
    provider: LLMProvider
    signer: SessionSigner | None
    turnstile: TurnstileVerifier


def build_services(settings: Settings, embedder: Embedder | None = None) -> Services:
    provider: LLMProvider
    if settings.llm_provider == "anthropic":
        if settings.anthropic_api_key is None:
            raise ValueError("PROVENANCE_ANTHROPIC_API_KEY is required for the anthropic provider")
        provider = AnthropicProvider(
            settings.anthropic_api_key.get_secret_value(),
            settings.anthropic_model,
            settings.llm_timeout_seconds,
        )
    elif settings.llm_provider == "ollama":
        provider = OllamaProvider(
            settings.ollama_url, settings.ollama_model, settings.llm_timeout_seconds
        )
    else:
        provider = MockProvider()
    signer = (
        SessionSigner(settings.session_secret.get_secret_value(), settings.session_ttl_seconds)
        if settings.session_secret
        else None
    )
    return Services(
        database=Database(settings.database_url) if settings.database_url else None,
        retriever=Retriever(embedder or LazyFastEmbed()),
        provider=provider,
        signer=signer,
        turnstile=CloudflareTurnstile(settings.turnstile_secret.get_secret_value()),
    )
