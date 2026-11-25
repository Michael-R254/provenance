from pathlib import Path

import pytest

from ingest.__main__ import main


def test_dry_run_prints_summary_and_succeeds(
    fixture_content: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "--content", str(fixture_content), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "OK     projects/example-project-a.md" in out
    assert "SKIP   projects/example-project-b.md" in out
    assert "2 file(s) included" in out


def test_validate_fails_on_invalid_content(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "bad.md").write_text("no frontmatter", encoding="utf-8")
    assert main(["validate", "--content", str(tmp_path)]) == 1


def test_validate_passes_on_empty_content_dir(tmp_path: Path) -> None:
    assert main(["validate", "--content", str(tmp_path)]) == 0
