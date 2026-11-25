"""Generation evaluation: ask every question through the real API code path, grade each answer,
and report citation validity, groundedness, required facts, refusals, latency and cost.

Free by default (mock model, heuristic judge). A paid run prints its estimated cost first and
stops unless --yes is given; it never spends more than --max-cost.

    python -m evals.generation --reset-database                       # free, offline
    python -m evals.generation --reset-database --provider anthropic --judge anthropic
    python -m evals.generation --reset-database --provider anthropic --judge anthropic --yes
"""

import argparse
import json
import math
import os
import re
import secrets
import sys
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import psycopg
import yaml
from fastapi.testclient import TestClient
from provenance.config import Settings
from provenance.llm import (
    PRICES,
    AnthropicProvider,
    GenerationRequest,
    GenerationResult,
    LLMProvider,
    MockProvider,
    OllamaProvider,
    estimate_input_tokens,
)
from provenance.main import create_app
from provenance.services import build_services
from pydantic import SecretStr

from evals.dataset import Dataset, Question, load_dataset
from evals.judge import (
    JUDGE_MAX_TOKENS,
    RUBRIC_VERSION,
    AnthropicJudge,
    HeuristicJudge,
    Judge,
    JudgeInput,
    Passage,
    judge_cost,
    render,
    rubric,
)
from evals.retrieval import EVALS_DIR, make_embedders, reset_and_index

DEFAULT_DATASET = EVALS_DIR / "datasets" / "fixture-generation.yaml"
DEFAULT_CONTENT = EVALS_DIR / "fixtures" / "content"
DEFAULT_THRESHOLDS = EVALS_DIR / "thresholds.yaml"
BASELINES = EVALS_DIR / "baselines"
ANSWER_MODEL = "claude-haiku-5-5"
ROLES = ("browsing", "recruiter", "hiring-manager", "engineer")  # apps/web/src/lib/recruiter.ts
ANSWERING = ("single_project", "multi_project", "recruiter", "distinction")
GATED = ("distinction", "adversarial")
# A typical judgement, for the "expected" estimate. The worst case uses JUDGE_MAX_TOKENS.
TYPICAL_JUDGE_OUTPUT_TOKENS = 1200

ProviderName = Literal["mock", "ollama", "anthropic"]
JudgeName = Literal["heuristic", "anthropic"]


# ---------------------------------------------------------------- providers used by the runner


@dataclass
class RecordingProvider:
    """Wraps the configured provider so the runner sees exactly what the model was sent."""

    inner: LLMProvider
    requests: list[GenerationRequest] = field(default_factory=list)
    results: list[GenerationResult] = field(default_factory=list)
    name: str = ""
    model: str = ""

    def __post_init__(self) -> None:
        self.name, self.model = self.inner.name, self.inner.model

    def estimate_max_cost_usd(self, request: GenerationRequest) -> float:
        return self.inner.estimate_max_cost_usd(request)

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str | GenerationResult]:
        self.requests.append(request)
        async for item in self.inner.stream(request):
            if isinstance(item, GenerationResult):
                self.results.append(item)
            yield item


PASSAGE = re.compile(
    r'<passage id="(c\d+)" source="([^"]*)" section="([^"]*)">\n(.*?)\n</passage>', re.S
)


def passages(request: GenerationRequest) -> list[Passage]:
    return [Passage(*m.groups()) for m in PASSAGE.finditer(request.messages[-1].content)]


def guardrails(request: GenerationRequest) -> list[str]:
    turn = request.messages[-1].content
    block = turn.partition("<guardrails>")[2].partition("</guardrails>")[0]
    return [line[2:].strip() for line in block.splitlines() if line.startswith("- ")]


def extractive_reply(request: GenerationRequest) -> str:
    """Mock answer: the first sentence of the top passage, cited. Free and deterministic."""
    found = passages(request)
    if not found:
        return "The evidence does not cover that."
    first = re.split(r"(?<=[.!?])\s+", found[0].text.strip())[0].rstrip(".")
    return f"{first} [{found[0].cid}]."


# ---------------------------------------------------------------- running questions


@dataclass
class Asked:
    question: Question
    status: str  # answered | refused | no_evidence | error code
    answer: str
    citations_used: list[str]
    citations_removed: list[str]
    uncited_sentences: list[str]
    request: GenerationRequest | None
    result: GenerationResult | None
    latency_ms: float


class Harness:
    """The real FastAPI app, in process, against the evaluation database."""

    def __init__(self, settings: Settings, provider: LLMProvider, embedder_name: str) -> None:
        services = build_services(settings, make_embedders(embedder_name).query)
        self.provider = RecordingProvider(provider)
        services = replace(services, provider=self.provider, turnstile=_AlwaysPass())
        self.client = TestClient(create_app(settings, services))
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    def _token(self) -> str:
        response = self.client.post("/v1/session", json={"turnstile_token": "evaluation"})
        response.raise_for_status()
        return str(response.json()["session_token"])

    def post_chat(self, body: dict[str, Any]) -> tuple[int, list[tuple[str, Any]]]:
        response = self.client.post(
            "/v1/chat", json=body, headers={"Authorization": f"Bearer {self._token()}"}
        )
        return response.status_code, _parse_sse(response.text)

    def ask(self, question: Question) -> Asked:
        before_req, before_res = len(self.provider.requests), len(self.provider.results)
        body: dict[str, Any] = {"question": question.question}
        if question.project:
            body["project"] = question.project
        started = time.perf_counter()
        status_code, events = self.post_chat(body)
        latency = (time.perf_counter() - started) * 1000
        answer = "".join(data["text"] for kind, data in events if kind == "token")
        cites = next((data for kind, data in events if kind == "citations"), None)
        done = next((data for kind, data in events if kind == "done"), None)
        error = next((data for kind, data in events if kind == "error"), None)
        if done:
            status = str(done["status"])
        elif error:
            status = str(error["code"])
        else:
            status = f"http_{status_code}"
        new_requests = self.provider.requests[before_req:]
        new_results = self.provider.results[before_res:]
        return Asked(
            question=question,
            status=status,
            answer=answer,
            citations_used=[c["id"] for c in (cites or {}).get("used", [])],
            citations_removed=list((cites or {}).get("removed", [])),
            uncited_sentences=list((cites or {}).get("unsupported", [])),
            request=new_requests[-1] if new_requests else None,
            result=new_results[-1] if new_results else None,
            latency_ms=round(latency, 1),
        )


class _AlwaysPass:
    async def verify(self, token: str, remote_ip: str | None) -> bool:
        return True


def _parse_sse(text: str) -> list[tuple[str, Any]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines and "data" in lines:
            events.append((lines["event"], json.loads(lines["data"])))
    return events


# ---------------------------------------------------------------- recruiter mode


def recruiter_consistency(harness: Harness, dataset: Dataset) -> dict[str, Any]:
    """Structural check (free): the API refuses a role field, and the same question yields a
    byte-identical generation request every time, so the role cannot change the facts."""
    questions = [q for q in dataset.questions if q.category == "recruiter"] or dataset.questions[:1]
    rejected = all(
        harness.post_chat({"question": q.question, "role": role})[0] == 422
        for q in questions
        for role in ROLES
    )
    identical = True
    for q in questions:
        seen = set()
        for _role in ROLES:  # one fresh session per role, as the site would open
            asked = harness.ask(q)
            seen.add(repr(asked.request))
        identical = identical and len(seen) == 1
    return {"role_rejected_by_api": rejected, "identical_generation_requests": identical}


# ---------------------------------------------------------------- cost


@dataclass(frozen=True)
class Estimate:
    answers_expected: float
    answers_worst: float
    judge_expected: float
    judge_worst: float
    questions: int
    judged: int

    @property
    def expected(self) -> float:
        return self.answers_expected + self.judge_expected

    @property
    def worst(self) -> float:
        return self.answers_worst + self.judge_worst


def estimate_cost(dry_run: Sequence[Asked], provider: ProviderName, judge: JudgeName) -> Estimate:
    """From a free dry run that captured every generation request the paid run would send."""
    answers_expected = answers_worst = judge_expected = judge_worst = 0.0
    judged = 0
    price = PRICES[ANSWER_MODEL]
    system_tokens = len(rubric()) // 3
    captured = [a.request for a in dry_run if a.request is not None]
    # A question that found no evidence in the dry run may find some with another embedder, so
    # it is costed like the largest request seen: the estimate errs high, never low.
    largest = max(captured, key=estimate_input_tokens, default=None)
    for asked in dry_run:
        request = asked.request or largest
        if request is None:
            continue
        tokens_in = estimate_input_tokens(request)
        max_out = request.max_output_tokens
        if provider == "anthropic":
            answers_worst += (
                tokens_in * price.input_per_mtok + max_out * price.output_per_mtok
            ) / 1e6
            answers_expected += (
                tokens_in * price.input_per_mtok + max_out / 3 * price.output_per_mtok
            ) / 1e6
        if judge == "anthropic":
            judged += 1
            item = JudgeInput(
                asked.question,
                passages(request),
                guardrails(request),
                "x" * max_out * 4,
            )
            judge_in = system_tokens + len(render(item)) // 3
            judge_worst += judge_cost(judge_in, JUDGE_MAX_TOKENS)
            judge_expected += judge_cost(judge_in, TYPICAL_JUDGE_OUTPUT_TOKENS)
    return Estimate(
        round(answers_expected, 4),
        round(answers_worst, 4),
        round(judge_expected, 4),
        round(judge_worst, 4),
        len(dry_run),
        judged,
    )


def format_estimate(e: Estimate, provider: ProviderName, judge: JudgeName) -> str:
    return "\n".join(
        [
            f"Estimated cost for {e.questions} questions"
            f" (answers: {provider}, judge: {judge}, {e.judged} judged):",
            f"  answers  expected ${e.answers_expected:.4f}   worst case ${e.answers_worst:.4f}",
            f"  judge    expected ${e.judge_expected:.4f}   worst case ${e.judge_worst:.4f}",
            f"  total    expected ${e.expected:.4f}   worst case ${e.worst:.4f}",
        ]
    )


# ---------------------------------------------------------------- grading


@dataclass
class Graded:
    id: str
    category: str
    status: str
    answer: str
    passed: bool | None  # None: could not be judged
    problems: list[str]
    citations_valid: bool | None
    declined: bool
    unsupported_claims: list[str]
    missing_required_facts: list[str]
    forbidden_claims_made: list[str]
    latency_ms: float
    answer_cost_usd: float
    judge_cost_usd: float
    judge_notes: str


def grade(asked: Asked, judge: Judge) -> Graded:
    q = asked.question
    problems: list[str] = []
    answered = asked.status in ("answered", "refused")
    citations_valid = (
        not asked.citations_removed and not asked.uncited_sentences and bool(asked.citations_used)
        if answered
        else None
    )
    judge_cost_usd = 0.0
    verdict = None
    notes = ""
    if asked.request is not None and answered:
        judgement = judge.judge(
            JudgeInput(q, passages(asked.request), guardrails(asked.request), asked.answer)
        )
        judge_cost_usd = judgement.cost_usd
        verdict = judgement.verdict
        notes = judgement.error or (verdict.notes if verdict else "")

    if asked.status not in ("answered", "refused", "no_evidence"):
        problems.append(f"request ended with {asked.status}")
    declined = asked.status == "no_evidence" or bool(verdict and verdict.declined)
    unsupported = list(verdict.unsupported_claims) if verdict else []
    missing = list(verdict.missing_required_facts) if verdict else []
    forbidden = list(verdict.forbidden_claims_made) if verdict else []
    unjudged = answered and verdict is None

    if verdict:
        if unsupported:
            problems.append(f"{len(unsupported)} unsupported claim(s)")
        if forbidden:
            problems.append("forbidden claim made")
        if verdict.guardrail_violations:
            problems.append("guardrail violated")
        if verdict.revealed_instructions:
            problems.append("revealed instructions")
    if q.category in ANSWERING:
        if declined:
            problems.append("declined an answerable question")
        if missing:
            problems.append(f"{len(missing)} required fact(s) missing")
        if citations_valid is False:
            problems.append("citation problems")
    elif q.category == "unanswerable" and not declined:
        problems.append("answered without evidence")

    return Graded(
        id=q.id,
        category=q.category,
        status=asked.status,
        answer=asked.answer,
        passed=None if unjudged else not problems,
        problems=problems + (["not judged: " + notes] if unjudged else []),
        citations_valid=citations_valid,
        declined=declined,
        unsupported_claims=unsupported,
        missing_required_facts=missing,
        forbidden_claims_made=forbidden,
        latency_ms=asked.latency_ms,
        answer_cost_usd=round(asked.result.cost_usd, 6) if asked.result else 0.0,
        judge_cost_usd=round(judge_cost_usd, 6),
        judge_notes=notes,
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)], 1)


def summarise(graded: Sequence[Graded], questions: Sequence[Question]) -> dict[str, Any]:
    by_id = {q.id: q for q in questions}
    answering = [g for g in graded if g.category in ANSWERING]
    unanswerable = [g for g in graded if g.category == "unanswerable"]
    answered = [g for g in graded if g.citations_valid is not None]
    judged = [g for g in answered if g.passed is not None]
    required = sum(len(by_id[g.id].must_contain) for g in answering if g.passed is not None)
    missing = sum(len(g.missing_required_facts) for g in answering if g.passed is not None)
    latencies = [g.latency_ms for g in graded]
    return {
        "questions": len(graded),
        "passed": sum(g.passed is True for g in graded),
        "unjudged": sum(g.passed is None for g in graded),
        "citation_validity": _rate(sum(bool(g.citations_valid) for g in answered), len(answered)),
        "groundedness": _rate(sum(not g.unsupported_claims for g in judged), len(judged)),
        "required_facts": _rate(required - missing, required),
        "correct_refusal": _rate(sum(g.declined for g in unanswerable), len(unanswerable)),
        "false_refusal": _rate(sum(g.declined for g in answering), len(answering)),
        "by_category": {
            category: {
                "passed": sum(g.passed is True for g in graded if g.category == category),
                "total": sum(g.category == category for g in graded),
            }
            for category in sorted({g.category for g in graded})
        },
        "latency_ms": {"p50": _percentile(latencies, 0.5), "p95": _percentile(latencies, 0.95)},
        "cost_usd": {
            "answers": round(sum(g.answer_cost_usd for g in graded), 4),
            "judge": round(sum(g.judge_cost_usd for g in graded), 4),
        },
    }


def release_gate(graded: Sequence[Graded]) -> list[str]:
    """Architecture section 8: every distinction check passes; no adversarial question produces
    a fabricated claim. Unjudged items fail the gate: they were not shown to be safe."""
    return [
        f"{g.category} {g.id}: " + "; ".join(g.problems)
        for g in graded
        if g.category in GATED and g.passed is not True
    ]


def threshold_problems(summary: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    problems = []
    for name, bound in thresholds.get("minimum", {}).items():
        value = summary.get(name)
        if value is not None and value < bound:
            problems.append(f"{name} {value:.3f} is below {bound}")
    for name, bound in thresholds.get("maximum", {}).items():
        value = summary.get(name)
        if name == "p95_latency_ms":
            value = summary["latency_ms"]["p95"]
        if value is not None and value > bound:
            problems.append(f"{name} {value} is above {bound}")
    return problems


def format_report(graded: Sequence[Graded], summary: dict[str, Any]) -> str:
    def pct(v: float | None) -> str:
        return "-" if v is None else f"{v:.0%}"

    lines = [
        f"{'id':<36} {'category':<15} {'status':<12} result",
        "-" * 80,
    ]
    for g in graded:
        result = "pass" if g.passed else ("UNJUDGED" if g.passed is None else "FAIL")
        lines.append(f"{g.id:<36} {g.category:<15} {g.status:<12} {result}")
        if not g.passed:
            lines.extend(f"{'':<4}- {p}" for p in g.problems)
    lines += [
        "-" * 80,
        f"passed {summary['passed']}/{summary['questions']} (unjudged {summary['unjudged']})",
        f"citation validity {pct(summary['citation_validity'])}"
        f" | groundedness {pct(summary['groundedness'])}"
        f" | required facts {pct(summary['required_facts'])}",
        f"correct refusals {pct(summary['correct_refusal'])}"
        f" | false refusals {pct(summary['false_refusal'])}",
        f"latency p50 {summary['latency_ms']['p50']} ms | p95 {summary['latency_ms']['p95']} ms",
        f"cost: answers ${summary['cost_usd']['answers']:.4f},"
        f" judge ${summary['cost_usd']['judge']:.4f}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- command line


def _settings(url: str, provider: ProviderName, spend_cap: float) -> Settings:
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("PROVENANCE_ANTHROPIC_API_KEY")
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        environment="test",
        database_url=url,
        llm_provider=provider,
        anthropic_api_key=SecretStr(key) if key else None,
        anthropic_model=ANSWER_MODEL,
        session_secret=SecretStr(secrets.token_urlsafe(48)),
        daily_spend_cap_usd=spend_cap,
        rate_session_per_minute=1000,
        rate_session_per_day=10_000,
        rate_ip_per_hour=10_000,
        rate_ip_sessions_per_hour=10_000,
    )


def _provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        if settings.anthropic_api_key is None:
            sys.exit("error: set ANTHROPIC_API_KEY for --provider anthropic")
        return AnthropicProvider(
            settings.anthropic_api_key.get_secret_value(),
            settings.anthropic_model,
            settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            settings.ollama_url, settings.ollama_model, settings.llm_timeout_seconds
        )
    return MockProvider(reply=extractive_reply)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.generation", description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument("--embedder", choices=["fake", "fastembed"], default="fastembed")
    parser.add_argument("--provider", choices=["mock", "ollama", "anthropic"], default="mock")
    parser.add_argument("--judge", choices=["heuristic", "anthropic"], default="heuristic")
    parser.add_argument("--database-url")
    parser.add_argument(
        "--reset-database",
        action="store_true",
        help="required: wipes the target database's public schema before indexing",
    )
    parser.add_argument("--max-cost", type=float, default=3.0, help="hard limit in USD")
    parser.add_argument("--yes", action="store_true", help="accept the estimate and spend")
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument("--gate", action="store_true", help="exit 1 if the release gate fails")
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--output", type=Path, help="write the full JSON report here")
    args = parser.parse_args(argv)

    url = args.database_url or os.environ.get("PROVENANCE_TEST_DATABASE_URL")
    if not url:
        sys.exit("error: set PROVENANCE_TEST_DATABASE_URL or pass --database-url")
    if not args.reset_database:
        sys.exit("error: pass --reset-database to confirm the target database may be wiped")
    paid = args.provider == "anthropic" or args.judge == "anthropic"

    dataset = load_dataset(args.dataset)
    with psycopg.connect(url, autocommit=True) as conn:
        reset_and_index(conn, args.content, make_embedders(args.embedder))

    # 1. Free dry run with the mock model: proves the pipeline works, captures every request the
    #    paid run would send, and checks recruiter mode.
    dry = Harness(_settings(url, "mock", 1.0), MockProvider(reply=extractive_reply), args.embedder)
    try:
        dry_run = [dry.ask(q) for q in dataset.questions]
        recruiter = recruiter_consistency(dry, dataset)
    finally:
        dry.close()
    estimate = estimate_cost(dry_run, args.provider, args.judge)
    print(format_estimate(estimate, args.provider, args.judge))
    print(f"Spending limit (--max-cost): ${args.max_cost:.2f}")
    if args.estimate_only:
        return 0
    if paid and estimate.worst > args.max_cost:
        print("error: the worst case exceeds --max-cost; nothing was spent", file=sys.stderr)
        return 1
    if paid and not args.yes:
        print("Nothing has been spent. Re-run with --yes to accept this estimate.")
        return 0

    # 2. The evaluated run. The API's own daily spend cap is set to the limit as a second stop.
    settings = _settings(url, args.provider, args.max_cost)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("TRUNCATE query_logs, rate_limits")
    judge: Judge = AnthropicJudge() if args.judge == "anthropic" else HeuristicJudge()
    harness = Harness(settings, _provider(settings), args.embedder)
    graded: list[Graded] = []
    spent = 0.0
    per_question_worst = estimate.worst / max(estimate.questions, 1)
    try:
        for q in dataset.questions:
            if paid and spent + per_question_worst > args.max_cost:
                print(f"stopping: ${spent:.4f} spent, next question could pass --max-cost")
                break
            g = grade(harness.ask(q), judge)
            spent += g.answer_cost_usd + g.judge_cost_usd
            graded.append(g)
    finally:
        harness.close()

    summary = summarise(graded, dataset.questions)
    summary["recruiter_consistency"] = recruiter
    print(format_report(graded, summary))
    print(
        "recruiter mode: role rejected by API"
        f" {recruiter['role_rejected_by_api']}, identical prompts"
        f" {recruiter['identical_generation_requests']}"
    )
    meta = {
        "dataset": dataset.version,
        "provider": args.provider,
        "answer_model": harness.provider.model,
        "judge": judge.name,
        "judge_model": judge.model,
        "rubric": RUBRIC_VERSION,
        "embedder": args.embedder,
    }
    report = {**meta, "summary": summary, "results": [asdict(g) for g in graded]}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.update_baseline:
        path = BASELINES / f"fixture-generation-{args.provider}-{judge.name}.json"
        path.write_text(json.dumps({**meta, "summary": summary}, indent=2) + "\n", "utf-8")
        print(f"baseline written to {path}")

    problems = []
    if not all(recruiter.values()):
        problems.append("recruiter mode could change what the model is asked")
    if args.gate:
        problems += release_gate(graded)
        if len(graded) < len(dataset.questions):
            problems.append("the run stopped before every question was asked")
        thresholds = yaml.safe_load(args.thresholds.read_text("utf-8"))
        breaches = threshold_problems(summary, thresholds)
        if thresholds.get("status") == "approved":
            problems += breaches
        else:
            for breach in breaches:
                print(f"threshold (proposed, not enforced): {breach}")
    for problem in problems:
        print(f"GATE: {problem}", file=sys.stderr)
    if not problems:
        print("gate: pass" if args.gate else "done (gate not requested)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
