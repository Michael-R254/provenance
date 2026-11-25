from pathlib import Path

from ingest.schema import ProjectFrontmatter
from ingest.validate import prepare

VALID_PROJECT = """---
id: {id}
title: Example
status: {status}
version: 1
updated: 2026-01-01
type: personal
permission: {permission}
summary: Fictional.
---

## Overview

Fictional text.
"""


def _write(tmp_path: Path, name: str, text: str) -> None:
    target = tmp_path / "projects" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_fixture_content_includes_only_approved_files(fixture_content: Path) -> None:
    result = prepare(fixture_content)
    outcomes = {r.relative_path: r.outcome for r in result.reports}
    assert outcomes == {
        "projects/example-project-a.md": "included",
        "projects/example-project-b.md": "skipped_draft",
        "profile.md": "included",
    }
    assert not result.has_errors
    all_text = " ".join(c.text for d in result.documents for c in d.chunks)
    assert "zebra-draft-marker" not in all_text


def test_draft_is_never_included(tmp_path: Path) -> None:
    _write(tmp_path, "x.md", VALID_PROJECT.format(id="x", status="draft", permission="pending"))
    result = prepare(tmp_path)
    assert result.documents == []
    assert result.reports[0].outcome == "skipped_draft"


def test_unknown_status_is_an_error_not_a_skip(tmp_path: Path) -> None:
    _write(tmp_path, "x.md", VALID_PROJECT.format(id="x", status="published", permission="ok"))
    result = prepare(tmp_path)
    assert result.documents == []
    assert result.has_errors


def test_approved_with_pending_permission_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "x.md", VALID_PROJECT.format(id="x", status="approved", permission="pending"))
    result = prepare(tmp_path)
    assert result.has_errors
    assert "permission" in " ".join(result.reports[0].messages)


def test_unknown_frontmatter_keys_are_rejected(tmp_path: Path) -> None:
    text = VALID_PROJECT.format(id="x", status="approved", permission="ok").replace(
        "summary:", "accuracy: 99%\nsummary:"
    )
    _write(tmp_path, "x.md", text)
    assert prepare(tmp_path).has_errors


def test_file_name_must_match_id(tmp_path: Path) -> None:
    _write(tmp_path, "wrong.md", VALID_PROJECT.format(id="x", status="approved", permission="ok"))
    result = prepare(tmp_path)
    assert result.has_errors
    assert "file name" in result.reports[0].messages[0]


def test_missing_frontmatter_is_an_error(tmp_path: Path) -> None:
    _write(tmp_path, "x.md", "## Overview\n\nNo frontmatter.\n")
    result = prepare(tmp_path)
    assert result.has_errors


def test_blank_optional_fields_become_none(tmp_path: Path) -> None:
    text = VALID_PROJECT.format(id="x", status="approved", permission="ok").replace(
        "summary:", 'repo: ""\norganisation: ""\nsummary:'
    )
    _write(tmp_path, "x.md", text)
    result = prepare(tmp_path)
    assert not result.has_errors
    meta = result.documents[0].meta
    assert isinstance(meta, ProjectFrontmatter)
    assert meta.repo is None
