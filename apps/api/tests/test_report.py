import json
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from provenance.report import DayRow, Report, build_report, format_report


def _log(conn: psycopg.Connection, status: str, cost: str, total_ms: float, days_ago: int) -> None:
    conn.execute(
        "INSERT INTO query_logs (session_id, question, answer_status, tokens_in, tokens_out,"
        " cost_usd, stage_timings_ms, citations_valid, created_at)"
        " VALUES ('s', 'a fictional question', %s, 100, 20, %s, %s, %s,"
        " now() - make_interval(days => %s))",
        (status, cost, json.dumps({"total": total_ms}), status == "answered", days_ago),
    )


@pytest.mark.integration
def test_report_summarises_recent_days_only(db: psycopg.Connection) -> None:
    _log(db, "answered", "0.0010", 1000, 0)
    _log(db, "answered", "0.0020", 3000, 0)
    _log(db, "no_evidence", "0", 200, 0)
    _log(db, "answered", "0.5000", 9000, 30)
    report = build_report(db, days=7)
    assert len(report.rows) == 1
    row = report.rows[0]
    assert (row.questions, row.answered, row.tokens_in) == (3, 2, 300)
    assert row.cost_usd == Decimal("0.0030")
    assert row.p50_ms == 1000
    assert row.citation_problems == 1
    assert report.statuses == [("answered", 2), ("no_evidence", 1)]


def test_format_shows_totals_and_never_questions() -> None:
    row = DayRow(date(2026, 1, 2), 3, 2, 300, 40, Decimal("0.003"), 1000.0, 2900.0, 0)
    text = format_report(Report(days=7, rows=[row], statuses=[("answered", 2)]))
    assert "2026-01-02" in text
    assert "total: 3 question(s), $0.0030" in text
    assert "by status: answered 2" in text
    assert "question?" not in text


def test_format_with_no_traffic() -> None:
    assert "no questions logged" in format_report(Report(days=7, rows=[], statuses=[]))
