import os
from pathlib import Path

import pytest
from provenance.answering import Evidence, build_request
from provenance.llm import GenerationRequest, GenerationResult
from provenance.retrieval import RetrievedChunk

from evals.dataset import Question
from evals.generation import (
    Asked,
    Estimate,
    estimate_cost,
    extractive_reply,
    grade,
    guardrails,
    main,
    passages,
    release_gate,
    summarise,
    threshold_problems,
)
from evals.judge import HeuristicJudge

DIST = Question(
    id="d",
    category="distinction",
    question="Did the example gadget use a neural network?",
    expected=["projects/example-gadget.md#architecture"],
    must_contain=["uses a lookup table"],
    must_not_contain=["uses a neural network"],
)
NONE = Question(id="u", category="unanswerable", question="Where did they go to school?")


def _request() -> GenerationRequest:
    chunk = RetrievedChunk(
        chunk_id=1,
        document_title="Example Gadget",
        section="Architecture",
        anchor="architecture",
        text="The gadget uses a lookup table. It is small.",
        source_path="projects/example-gadget.md",
        url="/projects/example-gadget",
        project_slug="example-gadget",
    )
    return build_request(
        "system",
        DIST.question,
        [],
        Evidence.from_chunks([chunk]),
        {"example-gadget": ["Not a neural network."]},
        600,
    )


def _asked(q: Question, status: str, answer: str, cited: bool = True) -> Asked:
    answered = status == "answered"
    return Asked(
        question=q,
        status=status,
        answer=answer,
        citations_used=["c1"] if answered and cited else [],
        citations_removed=[],
        uncited_sentences=[],
        request=_request() if answered else None,
        result=GenerationResult(model="m", cost_usd=0.001) if answered else None,
        latency_ms=10.0,
    )


def test_passages_and_guardrails_are_read_from_the_exact_request() -> None:
    request = _request()
    found = passages(request)
    assert [(p.cid, p.source, p.section) for p in found] == [
        ("c1", "Example Gadget", "Architecture")
    ]
    assert found[0].text.startswith("The gadget uses a lookup table.")
    assert guardrails(request) == ["example-gadget: Not a neural network."]
    assert extractive_reply(request) == "The gadget uses a lookup table [c1]."


def test_grading_by_category() -> None:
    judge = HeuristicJudge()
    good = grade(_asked(DIST, "answered", "The gadget uses a lookup table [c1]."), judge)
    assert good.passed is True and good.citations_valid is True

    wrong = grade(_asked(DIST, "answered", "The gadget uses a neural network [c1]."), judge)
    assert wrong.passed is False
    assert "forbidden claim made" in wrong.problems

    uncited = grade(_asked(DIST, "answered", "The gadget uses a lookup table.", cited=False), judge)
    assert "citation problems" in uncited.problems

    declined = grade(_asked(DIST, "no_evidence", "I couldn't find anything."), judge)
    assert "declined an answerable question" in declined.problems

    refused = grade(_asked(NONE, "no_evidence", "I couldn't find anything."), judge)
    assert refused.passed is True and refused.declined


def test_summary_gate_and_thresholds() -> None:
    judge = HeuristicJudge()
    graded = [
        grade(_asked(DIST, "answered", "The gadget uses a neural network [c1]."), judge),
        grade(_asked(NONE, "no_evidence", "I couldn't find anything."), judge),
    ]
    summary = summarise(graded, [DIST, NONE])
    assert summary["correct_refusal"] == 1.0
    assert summary["by_category"]["distinction"] == {"passed": 0, "total": 1}
    [failure] = release_gate(graded)
    assert failure.startswith("distinction d: forbidden claim made")
    problems = threshold_problems(
        summary, {"minimum": {"correct_refusal": 1.0}, "maximum": {"p95_latency_ms": 5}}
    )
    assert problems == ["p95_latency_ms 10.0 is above 5"]


def test_estimate_errs_high_and_counts_only_paid_parts() -> None:
    asked = [_asked(DIST, "answered", "x"), _asked(NONE, "no_evidence", "x")]
    free = estimate_cost(asked, "mock", "heuristic")
    assert free.worst == 0 and free.judged == 0
    paid = estimate_cost(asked, "anthropic", "anthropic")
    careful = estimate_cost(asked, "anthropic", "anthropic", "claude-opus-5-5")
    assert careful.judge_worst > 30 * paid.judge_worst
    assert paid.judged == 2, "no-evidence questions are costed as if they call the model"
    assert 0 < paid.answers_expected <= paid.answers_worst < 0.01
    assert 0 < paid.judge_expected < paid.judge_worst
    assert isinstance(paid, Estimate)


# ---- end to end against Postgres (free: mock model, heuristic judge)

needs_db = pytest.mark.skipif(
    not os.environ.get("PROVENANCE_TEST_DATABASE_URL"),
    reason="PROVENANCE_TEST_DATABASE_URL is not set",
)


@pytest.mark.integration
@needs_db
def test_free_run_reports_and_checks_recruiter_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "report.json"
    assert main(["--reset-database", "--embedder", "fake", "--output", str(output)]) == 0
    out = capsys.readouterr().out
    assert "role rejected by API True, identical prompts True" in out
    assert "answers  expected $0.0000" in out
    assert output.exists()


@pytest.mark.integration
@needs_db
def test_paid_run_stops_after_the_estimate_without_yes(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    args = [
        "--reset-database",
        "--embedder",
        "fake",
        "--provider",
        "anthropic",
        "--judge",
        "anthropic",
    ]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "Estimated cost" in out
    assert "Nothing has been spent" in out


@pytest.mark.integration
@needs_db
def test_paid_run_refuses_when_the_worst_case_passes_the_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--reset-database",
        "--embedder",
        "fake",
        "--judge",
        "anthropic",
        "--max-cost",
        "0.0001",
    ]
    assert main([*args, "--yes"]) == 1
    assert "nothing was spent" in capsys.readouterr().err
