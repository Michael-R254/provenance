"""Command line interface: python -m ingest <command>. Run with --help for the list."""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg

from ingest.embed import DEFAULT_MODEL, Embedder, FakeEmbedder, FastEmbedEmbedder
from ingest.index import activate, build_index, check_version, list_versions, mark_failed
from ingest.migrate import apply_migrations
from ingest.validate import ValidationResult, prepare

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTENT = REPO_ROOT / "content"
DEFAULT_MIGRATIONS = REPO_ROOT / "db" / "migrations"


def _print_report(result: ValidationResult) -> None:
    labels = {"included": "OK     ", "skipped_draft": "SKIP   ", "error": "ERROR  "}
    for report in result.reports:
        detail = f"{report.chunk_count} chunks" if report.outcome == "included" else ""
        print(f"{labels[report.outcome]}{report.relative_path}  {detail}".rstrip())
        for message in report.messages:
            print(f"         - {message}")
    included = sum(r.outcome == "included" for r in result.reports)
    chunks = sum(len(d.chunks) for d in result.documents)
    print(
        f"\n{included} file(s) included, {chunks} chunk(s), {len(result.reports)} file(s) checked"
    )


def _database_url(args: argparse.Namespace) -> str:
    url = args.database_url or os.environ.get("PROVENANCE_DATABASE_URL")
    if not url:
        sys.exit("error: set PROVENANCE_DATABASE_URL or pass --database-url")
    return str(url)


def _git_sha() -> str | None:
    if sha := os.environ.get("GITHUB_SHA"):
        return sha
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def _embedder(name: str) -> Embedder:
    return FakeEmbedder() if name == "fake" else FastEmbedEmbedder()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingest", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="check content files without writing anything")
    p_validate.add_argument("--content", type=Path, default=DEFAULT_CONTENT)

    p_migrate = sub.add_parser("migrate", help="apply SQL migrations")
    p_migrate.add_argument("--migrations", type=Path, default=DEFAULT_MIGRATIONS)
    p_migrate.add_argument("--database-url")

    p_run = sub.add_parser("run", help="build a new index version from approved content")
    p_run.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    p_run.add_argument("--dry-run", action="store_true", help="validate and chunk only")
    p_run.add_argument("--activate", action="store_true", help="activate the new version")
    p_run.add_argument("--embedder", choices=["fastembed", "fake"], default="fastembed")
    p_run.add_argument("--database-url")
    p_run.add_argument("--version-file", type=Path, help="write the new version id here")

    p_check = sub.add_parser("check", help="check a built version against the approved content")
    p_check.add_argument("version", type=int)
    p_check.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    p_check.add_argument("--embedder", choices=["fastembed", "fake"], default="fastembed")
    p_check.add_argument("--database-url")

    p_activate = sub.add_parser("activate", help="activate an existing version (rollback)")
    p_activate.add_argument("version", type=int)
    p_activate.add_argument("--database-url")

    p_failed = sub.add_parser("mark-failed", help="mark a building version as failed")
    p_failed.add_argument("version", type=int)
    p_failed.add_argument("--database-url")

    p_versions = sub.add_parser("versions", help="list recent index versions")
    p_versions.add_argument("--limit", type=int, default=10)
    p_versions.add_argument("--database-url")

    args = parser.parse_args(argv)

    if args.command == "migrate":
        with psycopg.connect(_database_url(args)) as conn:
            applied = apply_migrations(conn, args.migrations)
        print("applied: " + (", ".join(applied) if applied else "nothing new"))
        return 0

    if args.command == "activate":
        with psycopg.connect(_database_url(args)) as conn:
            activate(conn, args.version)
        print(f"index version {args.version} is now active")
        return 0

    if args.command == "mark-failed":
        with psycopg.connect(_database_url(args)) as conn:
            mark_failed(conn, args.version)
        print(f"index version {args.version} marked failed (if it was still building)")
        return 0

    if args.command == "versions":
        with psycopg.connect(_database_url(args)) as conn:
            rows = list_versions(conn, args.limit)
        print(f"{'id':>5}  {'status':<9} {'created (UTC)':<17} {'chunks':>6}  git")
        for vid, status, created, _activated, sha, chunks in rows:
            when = created.strftime("%Y-%m-%d %H:%M") if isinstance(created, datetime) else ""
            print(f"{vid:>5}  {status:<9} {when:<17} {chunks:>6}  {str(sha or '')[:10]}")
        return 0

    result = prepare(args.content)
    if args.command == "check":
        if result.has_errors:
            _print_report(result)
            return 1
        model = FakeEmbedder.model_name if args.embedder == "fake" else DEFAULT_MODEL
        with psycopg.connect(_database_url(args)) as conn:
            problems = check_version(conn, args.version, result.documents, model)
        for problem in problems:
            print(f"CHECK FAILED: {problem}", file=sys.stderr)
        if not problems:
            print(f"index version {args.version} matches {len(result.documents)} approved file(s)")
        return 1 if problems else 0

    _print_report(result)
    if result.has_errors:
        print("\nerror: fix the files above before indexing", file=sys.stderr)
        return 1
    if args.command == "validate" or args.dry_run:
        return 0
    if not result.documents:
        print("error: nothing approved to index", file=sys.stderr)
        return 1

    with psycopg.connect(_database_url(args)) as conn:
        version_id = build_index(conn, result.documents, _embedder(args.embedder), _git_sha())
        print(f"built index version {version_id}")
        if args.version_file:
            args.version_file.write_text(f"{version_id}\n", encoding="utf-8")
        if args.activate:
            activate(conn, version_id)
            print(f"index version {version_id} is now active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
