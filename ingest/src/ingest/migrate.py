"""Apply ordered SQL migrations from db/migrations, recording each one once."""

from pathlib import Path

import psycopg


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
    applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
    newly_applied: list[str] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in applied:
            continue
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
        newly_applied.append(path.name)
    return newly_applied
