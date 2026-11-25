"""Internal cost and latency report from `query_logs`. Read only; prints no visitor questions.

python -m provenance.report                  # last 7 days, PROVENANCE_DATABASE_URL
python -m provenance.report --days 30 --database-url postgresql://...
"""

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg

DAILY_SQL = """
SELECT
    (created_at AT TIME ZONE 'UTC')::date AS day,
    count(*) AS questions,
    count(*) FILTER (WHERE answer_status = 'answered') AS answered,
    coalesce(sum(tokens_in), 0) AS tokens_in,
    coalesce(sum(tokens_out), 0) AS tokens_out,
    coalesce(sum(cost_usd), 0) AS cost_usd,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY (stage_timings_ms ->> 'total')::float) AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY (stage_timings_ms ->> 'total')::float) AS p95_ms,
    count(*) FILTER (WHERE citations_valid IS false) AS citation_problems
FROM query_logs
WHERE created_at >= now() - make_interval(days => %(days)s)
GROUP BY day
ORDER BY day
"""

STATUS_SQL = """
SELECT answer_status, count(*)
FROM query_logs
WHERE created_at >= now() - make_interval(days => %(days)s)
GROUP BY answer_status
ORDER BY count(*) DESC, answer_status
"""


@dataclass(frozen=True)
class DayRow:
    day: date
    questions: int
    answered: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    p50_ms: float | None
    p95_ms: float | None
    citation_problems: int


@dataclass(frozen=True)
class Report:
    days: int
    rows: list[DayRow]
    statuses: list[tuple[str, int]]


def build_report(conn: psycopg.Connection, days: int) -> Report:
    params = {"days": days}
    rows = [DayRow(*row) for row in conn.execute(DAILY_SQL, params).fetchall()]
    statuses = [(str(s), int(n)) for s, n in conn.execute(STATUS_SQL, params).fetchall()]
    return Report(days=days, rows=rows, statuses=statuses)


def _ms(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f}"


def format_report(report: Report) -> str:
    lines = [f"Provenance usage, last {report.days} day(s), UTC"]
    if not report.rows:
        lines.append("no questions logged")
        return "\n".join(lines)
    header = (
        f"{'day':<10} {'asked':>6} {'answered':>8} {'tokens in':>10} {'tokens out':>10}"
        f" {'cost $':>9} {'p50 ms':>8} {'p95 ms':>8} {'cite!':>5}"
    )
    lines += [header, "-" * len(header)]
    for r in report.rows:
        lines.append(
            f"{r.day.isoformat():<10} {r.questions:>6} {r.answered:>8} {r.tokens_in:>10,}"
            f" {r.tokens_out:>10,} {r.cost_usd:>9.4f} {_ms(r.p50_ms):>8} {_ms(r.p95_ms):>8}"
            f" {r.citation_problems:>5}"
        )
    total_cost = sum((r.cost_usd for r in report.rows), Decimal(0))
    total_questions = sum(r.questions for r in report.rows)
    lines.append("-" * len(header))
    lines.append(f"total: {total_questions} question(s), ${total_cost:.4f}")
    lines.append("by status: " + ", ".join(f"{s} {n}" for s, n in report.statuses))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m provenance.report", description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--database-url")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")
    url = args.database_url or os.environ.get("PROVENANCE_DATABASE_URL")
    if not url:
        sys.exit("error: set PROVENANCE_DATABASE_URL or pass --database-url")
    with psycopg.connect(url) as conn:
        conn.read_only = True
        print(format_report(build_report(conn, args.days)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
