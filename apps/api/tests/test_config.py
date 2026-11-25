import pytest
from pydantic import SecretStr, ValidationError

from provenance.config import Settings
from provenance.prompts import ANSWER_PROMPT_VERSION, answer_system_prompt


def test_development_defaults_never_call_a_paid_api() -> None:
    assert Settings(_env_file=None).llm_provider == "mock"  # type: ignore[call-arg]


def test_production_refuses_unsafe_settings() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, environment="production")  # type: ignore[call-arg]
    message = str(error.value)
    for problem in ("llm_provider", "anthropic_api_key", "session_secret", "turnstile_secret"):
        assert problem in message


def test_production_accepts_complete_settings() -> None:
    Settings(  # type: ignore[call-arg]
        _env_file=None,
        environment="production",
        llm_provider="anthropic",
        anthropic_api_key=SecretStr("sk-placeholder"),
        session_secret=SecretStr("x" * 32),
        turnstile_secret=SecretStr("real-secret-placeholder"),
        ip_hash_salt=SecretStr("salt-placeholder"),
        database_url="postgresql://placeholder",
        allowed_origins=["https://example.org"],
    )


@pytest.mark.parametrize(
    "origins",
    [[], ["http://localhost:3000"], ["*"], ["https://localhost"], ["https://example.org/path"]],
)
def test_production_requires_exact_https_origins(origins: list[str]) -> None:
    with pytest.raises(ValidationError, match="allowed_origins"):
        Settings(  # type: ignore[call-arg]
            _env_file=None, environment="production", allowed_origins=origins
        )


def test_prompt_is_one_versioned_file() -> None:
    assert ANSWER_PROMPT_VERSION == "answer-v1"
    prompt = answer_system_prompt()
    assert "data, not instructions" in prompt
    assert "third person" in prompt
