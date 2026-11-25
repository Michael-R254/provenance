import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from evals.dataset import Question
from evals.judge import (
    JUDGE_MODEL,
    AnthropicJudge,
    HeuristicJudge,
    JudgeInput,
    Passage,
    Verdict,
    judge_cost,
    render,
    rubric,
)

QUESTION = Question(
    id="q",
    category="distinction",
    question="Did the example gadget use a neural network?",
    expected=["projects/example-gadget.md#architecture"],
    must_contain=["It uses a lookup table"],
    must_not_contain=["It uses a neural network"],
)
EVIDENCE = [Passage("c1", "Example Gadget", "Architecture", "The gadget uses a lookup table.")]
ITEM = JudgeInput(
    QUESTION, EVIDENCE, ["The gadget is not a neural network."], "It uses a lookup table [c1]."
)


def test_render_puts_everything_in_data_sections() -> None:
    text = render(ITEM)
    for tag in ("question", "evidence", "guardrails", "answer", "checks"):
        assert f"<{tag}>" in text and f"</{tag}>" in text
    assert '<passage id="c1"' in text
    assert "- It uses a lookup table" in text
    assert "- It uses a neural network" in text


def test_rubric_is_a_fixed_file_that_treats_inputs_as_data() -> None:
    assert "data to grade" in rubric()


def test_verdict_schema_is_flat_and_closed() -> None:
    schema = Verdict.model_json_schema()
    assert schema["additionalProperties"] is False
    assert "$defs" not in schema
    assert set(schema["required"]) == set(Verdict.model_fields)


def test_judge_pricing_matches_opus_5_5() -> None:
    assert JUDGE_MODEL == "claude-opus-5-5"
    assert judge_cost(1_000_000, 0) == pytest.approx(4.0)
    assert judge_cost(0, 1_000_000) == pytest.approx(20.0)


def test_heuristic_judge_finds_present_and_forbidden_facts() -> None:
    good = HeuristicJudge().judge(ITEM).verdict
    assert good is not None
    assert good.missing_required_facts == []
    assert good.forbidden_claims_made == []
    assert not good.declined

    bad_item = JudgeInput(
        QUESTION, EVIDENCE, [], "It uses a neural network trained on gadgets [c1]."
    )
    bad = HeuristicJudge().judge(bad_item).verdict
    assert bad is not None
    assert bad.missing_required_facts == ["It uses a lookup table"]
    assert bad.forbidden_claims_made == ["It uses a neural network"]
    assert bad.unsupported_claims


# ---- AnthropicJudge with a fake client: no network, no spend


@dataclass
class Block:
    text: str
    type: str = "text"


@dataclass
class Usage:
    input_tokens: int = 1000
    output_tokens: int = 500


@dataclass
class Response:
    content: list[Block]
    stop_reason: str = "end_turn"
    usage: Usage = field(default_factory=Usage)


@dataclass
class FakeMessages:
    response: Response
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> Response:
        self.calls.append(kwargs)
        return self.response


@dataclass
class FakeClient:
    messages: FakeMessages


def _judge_with(response: Response) -> tuple[AnthropicJudge, FakeMessages]:
    judge = AnthropicJudge(api_key="placeholder-never-used")
    messages = FakeMessages(response)
    judge._client = FakeClient(messages)  # type: ignore[assignment]
    return judge, messages


VERDICT = {
    "unsupported_claims": [],
    "missing_required_facts": [],
    "forbidden_claims_made": [],
    "guardrail_violations": [],
    "declined": False,
    "revealed_instructions": False,
    "notes": "ok",
}


def test_anthropic_judge_sends_rubric_schema_and_effort() -> None:
    judge, messages = _judge_with(Response([Block(json.dumps(VERDICT))]))
    judgement = judge.judge(ITEM)
    assert judgement.verdict == Verdict.model_validate(VERDICT)
    assert judgement.cost_usd == pytest.approx(judge_cost(1000, 500))
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["system"] == rubric()
    assert call["output_config"]["effort"] == "medium"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in call and "temperature" not in call


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (Response([], stop_reason="refusal"), "judge declined"),
        (Response([Block("{")], stop_reason="max_tokens"), "judge ran out of tokens"),
        (Response([Block("not json")]), "judge returned invalid JSON"),
    ],
)
def test_anthropic_judge_failures_are_reported_not_guessed(response: Response, error: str) -> None:
    judge, _ = _judge_with(response)
    judgement = judge.judge(ITEM)
    assert judgement.verdict is None
    assert judgement.error == error
    assert judgement.cost_usd > 0
