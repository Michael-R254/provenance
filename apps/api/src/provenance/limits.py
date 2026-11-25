"""Fixed-window rate limits and the daily spend cap, both stored in Postgres."""

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class Limit:
    name: str
    window_seconds: int
    max_requests: int


def hit(conn: psycopg.Connection, key: str, limit: Limit) -> bool:
    """Count one request against `limit` for `key`. Returns False once the window is full."""
    row = conn.execute(
        "INSERT INTO rate_limits (key, window_start, count) VALUES ("
        " %(key)s,"
        " to_timestamp(floor(extract(epoch FROM now()) / %(w)s) * %(w)s),"
        " 1)"
        " ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limits.count + 1"
        " RETURNING count",
        {"key": f"{limit.name}:{key}", "w": limit.window_seconds},
    ).fetchone()
    return row is not None and int(row[0]) <= limit.max_requests


def purge_old_rate_limits(conn: psycopg.Connection) -> None:
    """Rate-limit rows hold hashed client keys; keep them no longer than 24 hours."""
    conn.execute("DELETE FROM rate_limits WHERE window_start < now() - interval '24 hours'")


def spent_today_usd(conn: psycopg.Connection) -> float:
    row = conn.execute(
        "SELECT coalesce(sum(cost_usd), 0) FROM query_logs"
        " WHERE created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
    ).fetchone()
    return float(row[0]) if row else 0.0
