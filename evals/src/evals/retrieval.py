"""Retrieval evaluation: build an index from a content folder, run every question through each
retrieval method, and report recall@k, hit@k and MRR. Optionally compare with a baseline.

    python -m evals.retrieval --reset-database            # fixture corpus, fake embedder
    python -m evals.retrieval --reset-database --embedder fastembed
    python -m evals.retrieval --reset-database --update-baseline

    # score an index version that is built but not yet active (the ingest workflow's gate);
    # read only, nothing is wiped
    python -m evals.retrieval --index-version 12 --database-url ... --embedder fastembed \
        --dataset datasets/questions.yaml --baseline baselines/content-retrieval.json
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from ingest import embed as ingest_embed
from ingest.index import activate, build_index
from ingest.migrate import apply_migrations
from ingest.validate import prepare
from provenance import embedding as api_embedding
from provenance.retrieval import Method, Retriever

from evals.dataset import Dataset, load_dataset
from evals.metrics import hit_at_k, mean, recall_at_k, reciprocal_rank

EVALS_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = EVALS_DIR.parent
DEFAULT_DATASET = EVALS_DIR / "datasets" / "fixture.yaml"
DEFAULT_CONTENT = EVALS_DIR / "fixtures" / "content"
DEFAULT_BASELINE = EVALS_DIR / "baselines" / "fixture-retrieval.json"
METHODS: tuple[Method, ...] = ("hybrid", "vector", "keyword")
GATED_METRICS = ("recall_at_k", "mrr")


@dataclass(frozen=True)
class Embedders:
    ingest: ingest_embed.Embedder
    query: api_embedding.Embedder


def make_embedders(name: str) -> Embedders:
    if name == "fake":
        return Embedders(ingest_embed.FakeEmbedder(), api_embedding.FakeEmbedder())
    return Embedders(ingest_embed.FastEmbedEmbedder(), api_embedding.FastEmbedEmbedder())


def reset_and_index(conn: psycopg.Connection, content: Path, embedders: Embedders) -> int:
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")
    apply_migrations(conn, REPO_ROOT / "db" / "migrations")
    result = prepare(content)
    if result.has_errors:
        raise SystemExit("content has validation errors; run `python -m ingest validate`")
    version = build_index(conn, result.documents, embedders.ingest)
    activate(conn, version)
    return version


def evaluate(
    conn: psycopg.Connection,
    dataset: Dataset,
    retriever: Retriever,
    k: int,
    index_version: int | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {"dataset": dataset.version, "k": k, "methods": {}}
    for method in METHODS:
        per_question = []
        for q in dataset.questions:
            result = retriever.retrieve(
                conn,
                q.question,
                top_n=k,
                method=method,
                project=q.project,
                index_version=index_version,
            )
            ranked = [f"{c.source_path}#{c.anchor}" for c in result.chunks]
            row: dict[str, Any] = {"id": q.id, "category": q.category, "retrieved": ranked}
            if q.answerable:
                row["recall_at_k"] = recall_at_k(q.expected, ranked, k)
                row["hit_at_k"] = hit_at_k(q.expected, ranked, k)
                row["reciprocal_rank"] = reciprocal_rank(q.expected, ranked)
            row["timings_ms"] = result.timings_ms
            per_question.append(row)
        answerable = [r for r in per_question if "recall_at_k" in r]
        report["methods"][method] = {
            "recall_at_k": round(mean([r["recall_at_k"] for r in answerable]), 4),
            "hit_at_k": round(mean([r["hit_at_k"] for r in answerable]), 4),
            "mrr": round(mean([r["reciprocal_rank"] for r in answerable]), 4),
            "mean_total_ms": round(mean([r["timings_ms"]["total"] for r in per_question]), 2),
            "answerable": len(answerable),
            "unanswerable": len(per_question) - len(answerable),
            "questions": per_question,
        }
    return report


def format_table(report: dict[str, Any]) -> str:
    k = report["k"]
    lines = [
        f"dataset {report['dataset']}, k = {k}",
        f"{'method':<8} {'recall@' + str(k):>10} {'hit@' + str(k):>8} {'MRR':>6} {'mean ms':>9}",
    ]
    for method, m in report["methods"].items():
        lines.append(
            f"{method:<8} {m['recall_at_k']:>10.3f} {m['hit_at_k']:>8.3f}"
            f" {m['mrr']:>6.3f} {m['mean_total_ms']:>9.1f}"
        )
    hybrid = report["methods"]["hybrid"]["questions"]
    misses = [r["id"] for r in hybrid if r.get("recall_at_k", 1.0) < 1.0]
    lines.append("hybrid misses: " + (", ".join(misses) if misses else "none"))
    return "\n".join(lines)


def summary(report: dict[str, Any], embedder: str) -> dict[str, Any]:
    return {
        "dataset": report["dataset"],
        "k": report["k"],
        "embedder": embedder,
        "methods": {
            method: {name: m[name] for name in ("recall_at_k", "hit_at_k", "mrr")}
            for method, m in report["methods"].items()
        },
    }


def compare_with_baseline(current: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Return a list of regressions (empty if none). Only hybrid metrics are gated."""
    if (current["dataset"], current["k"], current["embedder"]) != (
        baseline["dataset"],
        baseline["k"],
        baseline["embedder"],
    ):
        return ["baseline was produced with a different dataset, k or embedder"]
    problems = []
    for name in GATED_METRICS:
        now = current["methods"]["hybrid"][name]
        before = baseline["methods"]["hybrid"][name]
        if now + 1e-9 < before:
            problems.append(f"hybrid {name} dropped from {before:.3f} to {now:.3f}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.retrieval", description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument("--embedder", choices=["fake", "fastembed"], default="fake")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--database-url")
    parser.add_argument(
        "--reset-database",
        action="store_true",
        help="required: wipes the target database's public schema before indexing",
    )
    parser.add_argument(
        "--index-version",
        type=int,
        help="score this existing version in place (read only) instead of building a fresh index",
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--no-baseline", action="store_true", help="skip the baseline gate")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--output", type=Path, help="write the full JSON report here")
    args = parser.parse_args(argv)

    dataset = load_dataset(args.dataset)
    if args.index_version is not None:
        if args.reset_database or args.update_baseline:
            sys.exit("error: --index-version is read only; drop --reset-database/--update-baseline")
        if not args.database_url:
            sys.exit("error: --index-version needs an explicit --database-url")
        embedders = make_embedders(args.embedder)
        with psycopg.connect(args.database_url) as conn:
            conn.read_only = True
            report = evaluate(conn, dataset, Retriever(embedders.query), args.k, args.index_version)
    else:
        url = args.database_url or os.environ.get("PROVENANCE_TEST_DATABASE_URL")
        if not url:
            sys.exit("error: set PROVENANCE_TEST_DATABASE_URL or pass --database-url")
        if not args.reset_database:
            sys.exit("error: pass --reset-database to confirm the target database may be wiped")
        embedders = make_embedders(args.embedder)
        with psycopg.connect(url, autocommit=True) as conn:
            reset_and_index(conn, args.content, embedders)
            report = evaluate(conn, dataset, Retriever(embedders.query), args.k)

    print(format_table(report))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    current = summary(report, args.embedder)
    if args.update_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written to {args.baseline}")
        return 0
    if args.no_baseline:
        return 0
    if not args.baseline.exists():
        print(f"error: no baseline at {args.baseline}; run with --update-baseline", file=sys.stderr)
        return 1
    problems = compare_with_baseline(current, json.loads(args.baseline.read_text("utf-8")))
    for problem in problems:
        print(f"REGRESSION: {problem}", file=sys.stderr)
    if not problems:
        print("baseline check: no regression")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
