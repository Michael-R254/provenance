import asyncio
import json

import httpx2 as httpx
import pytest

from provenance.llm import (
    PRICES,
    AnthropicProvider,
    GenerationRequest,
    GenerationResult,
    Message,
    MockProvider,
    OllamaProvider,
    ProviderError,
)

REQUEST = GenerationRequest("system", [Message("user", "question")], max_output_tokens=200)


async def collect(provider: object) -> tuple[str, GenerationResult]:
    text, result = "", None
    async for item in provider.stream(REQUEST):  # type: ignore[attr-defined]
        if isinstance(item, GenerationResult):
            result = item
        else:
            text += item
    assert result is not None
    return text, result


def test_mock_provider_streams_its_reply_and_records_the_call() -> None:
    provider = MockProvider(reply="Fictional answer [c1].", chunk_size=4)
    text, result = asyncio.run(collect(provider))
    assert text == "Fictional answer [c1]."
    assert provider.calls == [REQUEST]
    assert result.cost_usd == provider.cost_usd


def test_mock_provider_can_fail() -> None:
    with pytest.raises(ProviderError):
        asyncio.run(collect(MockProvider(fail=True)))


def test_haiku_price_and_cache_weighting() -> None:
    price = PRICES["claude-haiku-5-5"]
    result = GenerationResult("claude-haiku-5-5", tokens_in=1_000_000, tokens_out=1_000_000)
    assert price.cost(result) == pytest.approx(0.60)
    cached = GenerationResult("claude-haiku-5-5", cache_read_tokens=1_000_000)
    assert price.cost(cached) == pytest.approx(0.01)


def test_anthropic_estimate_is_an_upper_bound_and_makes_no_call() -> None:
    provider = AnthropicProvider("sk-test-not-real", "claude-haiku-5-5", timeout_seconds=1)
    estimate = provider.estimate_max_cost_usd(REQUEST)
    assert estimate >= 200 * 0.50 / 1_000_000


def test_anthropic_refuses_models_without_a_price() -> None:
    with pytest.raises(ValueError):
        AnthropicProvider("sk-test-not-real", "unpriced-model", timeout_seconds=1)


def test_ollama_provider_reads_the_streamed_lines() -> None:
    lines = [
        {"message": {"content": "Local "}, "done": False},
        {"message": {"content": "answer [c1]."}, "done": False},
        {"message": {"content": ""}, "done": True, "prompt_eval_count": 12, "eval_count": 5},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        assert sent["messages"][0] == {"role": "system", "content": "system"}
        assert sent["options"]["num_predict"] == 200
        return httpx.Response(200, text="\n".join(json.dumps(x) for x in lines))

    provider = OllamaProvider("http://ollama.test", "m", 1, transport=httpx.MockTransport(handler))
    text, result = asyncio.run(collect(provider))
    assert text == "Local answer [c1]."
    assert (result.tokens_in, result.tokens_out, result.cost_usd) == (12, 5, 0.0)


def test_ollama_errors_become_provider_errors() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    with pytest.raises(ProviderError):
        asyncio.run(collect(OllamaProvider("http://ollama.test", "m", 1, transport=transport)))
