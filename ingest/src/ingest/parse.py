"""Discover content files and split them into frontmatter and body."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

DocType = Literal["project", "profile"]


class ParseError(ValueError):
    """Raised when a file has no valid frontmatter block."""


@dataclass(frozen=True)
class SourceFile:
    path: Path
    relative_path: str
    doc_type: DocType
    frontmatter: dict[str, Any]
    body: str
    content_hash: str


def discover(content_dir: Path) -> list[tuple[Path, DocType]]:
    """Project files live in content/projects/; other top-level .md files are profile docs.

    Files whose names start with "_" (such as the template) and README files are ignored.
    """
    found: list[tuple[Path, DocType]] = []
    for path in sorted((content_dir / "projects").glob("*.md")):
        if not path.name.startswith("_"):
            found.append((path, "project"))
    for path in sorted(content_dir.glob("*.md")):
        if not path.name.startswith("_") and path.name.lower() != "readme.md":
            found.append((path, "profile"))
    return found


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalised = text.replace("\r\n", "\n")
    if not normalised.startswith("---\n"):
        raise ParseError("file must start with a '---' frontmatter block")
    end = normalised.find("\n---\n", 4)
    if end == -1:
        raise ParseError("frontmatter block is not closed with '---'")
    loaded = yaml.safe_load(normalised[4:end]) or {}
    if not isinstance(loaded, dict):
        raise ParseError("frontmatter must be a mapping of keys to values")
    return loaded, normalised[end + 5 :]


def read_source(path: Path, content_dir: Path, doc_type: DocType) -> SourceFile:
    raw = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(raw)
    return SourceFile(
        path=path,
        relative_path=path.relative_to(content_dir).as_posix(),
        doc_type=doc_type,
        frontmatter=frontmatter,
        body=body,
        content_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )
