import os
from pathlib import Path

import psycopg
import pytest
from ingest.embed import FakeEmbedder
from ingest.index import active_version, build_index
from ingest.validate import prepare

from evals.retrieval import DEFAULT_BASELINE, DEFAULT_CONTENT, main

pytestmark = pytest.mark.integration


def test_fixture_evaluation_meets_the_stored_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if not os.environ.get("PROVENANCE_TEST_DATABASE_URL"):
        pytest.skip("PROVENANCE_TEST_DATABASE_URL is not set")
    output = tmp_path / "report.json"
    code = main(["--reset-database", "--baseline", str(DEFAULT_BASELINE), "--output", str(output)])
    assert code == 0, capsys.readouterr().err
    assert output.exists()
    assert "aubergine-draft-marker" not in output.read_text(encoding="utf-8")


def test_a_candidate_version_is_scored_in_place_without_activation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    url = os.environ.get("PROVENANCE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PROVENANCE_TEST_DATABASE_URL is not set")
    assert main(["--reset-database", "--no-baseline"]) == 0
    with psycopg.connect(url, autocommit=True) as conn:
        live = active_version(conn)
        candidate = build_index(conn, prepare(DEFAULT_CONTENT).documents, FakeEmbedder())
    code = main(["--index-version", str(candidate), "--database-url", url])
    assert code == 0, capsys.readouterr().err
    with psycopg.connect(url) as conn:
        assert active_version(conn) == live


def test_scoring_in_place_refuses_to_wipe_or_rewrite_the_baseline() -> None:
    with pytest.raises(SystemExit, match="read only"):
        main(["--index-version", "1", "--database-url", "postgresql://x", "--reset-database"])
