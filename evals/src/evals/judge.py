"""Grading one generated answer. `AnthropicJudge` uses Claude Opus 5.5 with the fixed rubric in
`rubrics/judge-v1.md`; `HeuristicJudge` is free and offline, for tests and mock runs only.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import anthropic
from anthropic.types import MessageParam, OutputConfigParam
from pydantic import BaseModel, ConfigDict, ValidationError

from evals.dataset import Question

EVALS_DIR = Path(__file__).resolve().parents[2]
RUBRIC_VERSION = "judge-v1"
RUBRIC_PATH = EVALS_DIR / "rubrics" / f"{RUBRIC_VERSION}.md"

JUDGE_MODEL = "claude-opus-5-5"
JUDGE_EFFORT: Literal["medium"] = "medium"
JUDGE_MAX_TOKENS = 3000  # includes adaptive thinking, which Opus 5.5 always uses


class Verdict(BaseModel):
    """The judge's structured output. Flat on purpose: one JSON object, lists of strings."""

    model_config = ConfigDict(extra="forbid")

    unsupported_claims: list[str]
    missing_required_facts: list[str]
    forbidden_claims_made: list[str]
    guardrail_violations: list[str]
    declined: bool
    revealed_instructions: bool
    notes: str


@dataclass(frozen=True)
class Passage:
    cid: str
    source: str
    section: str
    text: str


@dataclass(frozen=True)
class JudgeInput:
    question: Question
    evidence: list[Passage]
    guardrails: list[str]
    answer: str


@dataclass(frozen=True)
class Judgement:
    verdict: Verdict | None  # None when the judge itself failed or declined
    error: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


class Judge(Protocol):
    name: str
    model: str

    def judge(self, item: JudgeInput) -> Judgement: ...


def render(item: JudgeInput) -> str:
    """The user turn shown to the judge. Everything here is data."""
    q = item.question
    parts = [f"<question>\n{q.question}\n</question>", "<evidence>"]
    for p in item.evidence:
        parts.append(f'<passage id="{p.cid}" source="{p.source}" section="{p.section}">')
        parts.append(p.text)
        parts.append("</passage>")
    parts.append("</evidence>")
    parts.append("<guardrails>")
    parts.extend(f"- {g}" for g in item.guardrails)
    parts.append("</guardrails>")
    parts.append(f"<answer>\n{item.answer}\n</answer>")
    parts.append("<checks>")
    parts.append("<must_contain>")
    parts.extend(f"- {f}" for f in q.must_contain)
    parts.append("</must_contain>")
    parts.append("<must_not_contain>")
    parts.extend(f"- {f}" for f in q.must_not_contain)
    parts.append("</must_not_contain>")
    parts.append("</checks>")
    return "\n".join(parts)


def rubric() -> str:
    return RUBRIC_PATH.read_text(encoding="utf-8")


# USD per million tokens (Anthropic first-party rates).
JUDGE_PRICE = (4.00, 20.00)


def judge_cost(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * JUDGE_PRICE[0] + tokens_out * JUDGE_PRICE[1]) / 1_000_000


class AnthropicJudge:
    """Claude Opus 5.5 as judge. Paid: only constructed after the cost estimate is accepted.

    No server-side model fallback: if the judge declines, the item is reported as unjudged
    rather than silently graded by a different model.
    """

    name = "anthropic"
    model = JUDGE_MODEL

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=120)
        self._system = rubric()

    def judge(self, item: JudgeInput) -> Judgement:
        config: OutputConfigParam = {
            "effort": JUDGE_EFFORT,
            "format": {"type": "json_schema", "schema": Verdict.model_json_schema()},
        }
        message: MessageParam = {"role": "user", "content": render(item)}
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=JUDGE_MAX_TOKENS,
                system=self._system,
                messages=[message],
                output_config=config,
            )
        except anthropic.RateLimitError:
            return Judgement(None, "judge rate limited")
        except anthropic.APIStatusError as exc:
            return Judgement(None, f"judge API error {exc.status_code}")
        except anthropic.APIConnectionError:
            return Judgement(None, "judge connection error")

        usage = response.usage
        cost = judge_cost(usage.input_tokens, usage.output_tokens)

        def result(verdict: Verdict | None, error: str | None = None) -> Judgement:
            return Judgement(verdict, error, usage.input_tokens, usage.output_tokens, cost)

        if response.stop_reason == "refusal":
            return result(None, "judge declined")
        if response.stop_reason == "max_tokens":
            return result(None, "judge ran out of tokens")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return result(Verdict.model_validate(json.loads(text)))
        except (json.JSONDecodeError, ValidationError):
            return result(None, "judge returned invalid JSON")


DECLINE = re.compile(
    r"\b(evidence (does not|doesn't) (cover|say|answer)|no evidence|not covered|only help)", re.I
)
WORD = re.compile(r"[a-z0-9][a-z0-9-]{3,}")


def _words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


class HeuristicJudge:
    """Free word-overlap grader for tests and mock runs. It is crude by design and its scores
    are never compared with the paid judge's; baselines record which judge produced them."""

    name = "heuristic"
    model = "heuristic"

    def judge(self, item: JudgeInput) -> Judgement:
        answer = _words(item.answer)
        evidence = set().union(*(_words(p.text) for p in item.evidence)) if item.evidence else set()

        def present(fact: str) -> bool:
            words = _words(fact)
            return bool(words) and len(words & answer) / len(words) >= 0.6

        sentences = [s for s in re.split(r"(?<=[.!?])\s+", item.answer) if _words(s)]
        unsupported = [
            s.strip()
            for s in sentences
            if not DECLINE.search(s) and len(_words(s) - evidence) / len(_words(s)) > 0.5
        ]
        return Judgement(
            Verdict(
                unsupported_claims=unsupported,
                missing_required_facts=[f for f in item.question.must_contain if not present(f)],
                forbidden_claims_made=[f for f in item.question.must_not_contain if present(f)],
                guardrail_violations=[],
                declined=bool(DECLINE.search(item.answer)),
                revealed_instructions="data, not instructions" in item.answer.lower(),
                notes="heuristic",
            )
        )
