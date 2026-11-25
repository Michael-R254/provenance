"""Turn content files into validated documents, or explain why they were left out."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from ingest.chunk import Chunk, chunk_document
from ingest.parse import ParseError, SourceFile, discover, read_source
from ingest.schema import ProfileFrontmatter, ProjectFrontmatter

Outcome = Literal["included", "skipped_draft", "error"]


@dataclass(frozen=True)
class PreparedDocument:
    source: SourceFile
    meta: ProjectFrontmatter | ProfileFrontmatter
    chunks: list[Chunk]

    @property
    def url(self) -> str:
        if isinstance(self.meta, ProjectFrontmatter):
            return f"/projects/{self.meta.id}"
        return f"/about#{self.meta.id}"


@dataclass
class FileReport:
    relative_path: str
    outcome: Outcome
    messages: list[str] = field(default_factory=list)
    chunk_count: int = 0


@dataclass
class ValidationResult:
    documents: list[PreparedDocument]
    reports: list[FileReport]

    @property
    def has_errors(self) -> bool:
        return any(r.outcome == "error" for r in self.reports)


def _format_errors(error: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc']) or 'file'}: {e['msg']}" for e in error.errors()]


def prepare(content_dir: Path, max_words: int | None = None) -> ValidationResult:
    """Validate every content file. Only approved, valid files become documents."""
    documents: list[PreparedDocument] = []
    reports: list[FileReport] = []
    seen_ids: dict[str, str] = {}

    for path, doc_type in discover(content_dir):
        relative = path.relative_to(content_dir).as_posix()
        try:
            source = read_source(path, content_dir, doc_type)
            model = ProjectFrontmatter if doc_type == "project" else ProfileFrontmatter
            meta = model.model_validate(source.frontmatter)
        except ParseError as exc:
            reports.append(FileReport(relative, "error", [str(exc)]))
            continue
        except ValidationError as exc:
            reports.append(FileReport(relative, "error", _format_errors(exc)))
            continue

        if meta.status != "approved":
            reports.append(FileReport(relative, "skipped_draft", ["status is not approved"]))
            continue
        if meta.id in seen_ids:
            reports.append(
                FileReport(
                    relative, "error", [f"id '{meta.id}' already used by {seen_ids[meta.id]}"]
                )
            )
            continue
        if doc_type == "project" and path.stem != meta.id:
            reports.append(
                FileReport(relative, "error", [f"file name must match id: expected {meta.id}.md"])
            )
            continue

        chunks = (
            chunk_document(source.body, meta.title)
            if max_words is None
            else chunk_document(source.body, meta.title, max_words=max_words)
        )
        if not chunks:
            reports.append(FileReport(relative, "error", ["no content to index"]))
            continue

        seen_ids[meta.id] = relative
        documents.append(PreparedDocument(source=source, meta=meta, chunks=chunks))
        reports.append(FileReport(relative, "included", chunk_count=len(chunks)))

    return ValidationResult(documents=documents, reports=reports)
