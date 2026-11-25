import os
from pathlib import Path

import pytest

from evals.retrieval import DEFAULT_BASELINE, main

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
