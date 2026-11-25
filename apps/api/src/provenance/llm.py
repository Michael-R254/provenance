"""Language model providers behind one small interface.

`AnthropicProvider` is production, `OllamaProvider` is free local development and `MockProvider`
is for tests. Callers never import a vendor SDK directly.
"""

import json
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

import anthropic
import httpx2 as httpx
from anthropic import AsyncAnthropic

if TYPE_CHECKING:
    from anthropic.types import MessageParam

Speaker = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Speaker
    content: str


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    messages: Sequence[Message]
    max_output_tokens: int


@dataclass(frozen=True)
class GenerationResult:
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    stop_reason: str | None = None
    cost_usd: float = 0.0


class ProviderError(RuntimeError):
    """The provider failed. The message is for logs only, never for visitors."""


class LLMProvider(Protocol):
    name: str
    model: str

    def stream(self, request: GenerationRequest) -> AsyncIterator[str | GenerationResult]:
        """Yield text deltas, then exactly one GenerationResult as the final item."""
        ...

    def estimate_max_cost_usd(self, request: GenerationRequest) -> float:
        """Upper bound on what `request` can cost, used by the daily spend cap."""
        ...


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, result: GenerationResult) -> float:
        # Cache reads bill at 0.1x input, 5-minute cache writes at 1.25x input.
        weighted_in = (
            result.tokens_in + 0.1 * result.cache_read_tokens + 1.25 * result.cache_write_tokens
        )
        return (
            weighted_in * self.input_per_mtok + result.tokens_out * self.output_per_mtok
        ) / 1_000_000


# USD per million tokens, prompts up to 100K tokens (ours are far smaller).
PRICES: dict[str, Price] = {"claude-haiku-5-5": Price(0.10, 0.50)}


def estimate_input_tokens(request: GenerationRequest) -> int:
    """Generous estimate (about 3 characters per token) so the spend cap errs on the safe side."""
    chars = len(request.system) + sum(len(m.content) for m in request.messages)
    return chars // 3 + 50


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        if model not in PRICES:
            raise ValueError(f"no price configured for {model}; add it to PRICES first")

        self.model = model
        self._price = PRICES[model]
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_seconds, max_retries=1)

    def estimate_max_cost_usd(self, request: GenerationRequest) -> float:
        bound = GenerationResult(
            model=self.model,
            tokens_in=estimate_input_tokens(request),
            tokens_out=request.max_output_tokens,
        )
        return self._price.cost(bound)

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str | GenerationResult]:
        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=request.max_output_tokens,
                # The system prompt is fixed, so it is marked for prompt caching.
                system=[
                    {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[_anthropic_message(m) for m in request.messages],
                # Short grounded answers do not need extended thinking; it would add cost.
                thinking={"type": "disabled"},
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"anthropic status {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("anthropic connection error") from exc
        usage = final.usage
        result = GenerationResult(
            model=self.model,
            tokens_in=usage.input_tokens,
            tokens_out=usage.output_tokens,
            cache_read_tokens=usage.cache_read_input_tokens or 0,
            cache_write_tokens=usage.cache_creation_input_tokens or 0,
            stop_reason=final.stop_reason,
        )
        yield GenerationResult(**{**result.__dict__, "cost_usd": self._price.cost(result)})


def _anthropic_message(message: Message) -> "MessageParam":
    if message.role == "user":
        return {"role": "user", "content": message.content}
    return {"role": "assistant", "content": message.content}


class OllamaProvider:
    """Local models through Ollama's chat API. Free, so its cost is always zero."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._url = base_url.rstrip("/") + "/api/chat"
        self._timeout = timeout_seconds
        self._transport = transport

    def estimate_max_cost_usd(self, request: GenerationRequest) -> float:
        return 0.0

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str | GenerationResult]:
        payload = {
            "model": self.model,
            "stream": True,
            "options": {"num_predict": request.max_output_tokens},
            "messages": [{"role": "system", "content": request.system}]
            + [{"role": m.role, "content": m.content} for m in request.messages],
        }
        tokens_in = tokens_out = 0
        try:
            async with (
                httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client,
                client.stream("POST", self._url, json=payload) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    text = data.get("message", {}).get("content", "")
                    if text:
                        yield text
                    if data.get("done"):
                        tokens_in = int(data.get("prompt_eval_count", 0))
                        tokens_out = int(data.get("eval_count", 0))
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama error: {type(exc).__name__}") from exc
        yield GenerationResult(model=self.model, tokens_in=tokens_in, tokens_out=tokens_out)


@dataclass
class MockProvider:
    """Deterministic provider for tests and offline development. Records every request."""

    reply: str | Callable[[GenerationRequest], str] = "This is a mock answer [c1]."
    chunk_size: int = 7
    cost_usd: float = 0.0001
    max_cost_usd: float = 0.001
    fail: bool = False
    name: str = "mock"
    model: str = "mock-model"
    calls: list[GenerationRequest] = field(default_factory=list)

    def estimate_max_cost_usd(self, request: GenerationRequest) -> float:
        return self.max_cost_usd

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str | GenerationResult]:
        self.calls.append(request)
        if self.fail:
            raise ProviderError("mock failure")
        text = self.reply(request) if callable(self.reply) else self.reply
        for start in range(0, len(text), self.chunk_size):
            yield text[start : start + self.chunk_size]
        yield GenerationResult(
            model=self.model,
            tokens_in=estimate_input_tokens(request),
            tokens_out=len(text) // 4,
            stop_reason="end_turn",
            cost_usd=self.cost_usd,
        )
