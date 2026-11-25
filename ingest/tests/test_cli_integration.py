import os
from pathlib import Path

import psycopg
import pytest

from ingest.__main__ import main
from ingest.index import active_version

pytestmark = pytest.mark.integration


def _url() -> str:
    return os.environ["PROVENANCE_TEST_DATABASE_URL"]


def test_gated_flow_builds_checks_then_activates(
    db: psycopg.Connection, fixture_content: Path, tmp_path: Path
) -> None:
    version_file = tmp_path / "version"
    common = ["--database-url", _url()]
    assert (
        main(
            [
                "run",
                "--content",
                str(fixture_content),
                "--embedder",
                "fake",
                "--version-file",
                str(version_file),
                *common,
            ]
        )
        == 0
    )
    version = int(version_file.read_text())
    assert active_version(db) is None, "run without --activate must not go live"
    check = ["check", str(version), "--content", str(fixture_content), "--embedder", "fake"]
    assert main([*check, *common]) == 0
    assert main(["activate", str(version), *common]) == 0
    assert active_version(db) == version


def test_a_failed_gate_keeps_the_previous_version(
    db: psycopg.Connection,
    fixture_content: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    common = ["--database-url", _url()]
    run = ["run", "--content", str(fixture_content), "--embedder", "fake"]
    assert main([*run, "--activate", *common]) == 0
    live = active_version(db)
    version_file = tmp_path / "version"
    assert main([*run, "--version-file", str(version_file), *common]) == 0
    candidate = int(version_file.read_text())
    # checked against the wrong embedder, so the gate fails
    assert main(["check", str(candidate), "--content", str(fixture_content), *common]) == 1
    assert main(["mark-failed", str(candidate), *common]) == 0
    assert active_version(db) == live
    assert main(["versions", *common]) == 0
    out = capsys.readouterr().out
    assert f"{candidate:>5}  failed" in out
