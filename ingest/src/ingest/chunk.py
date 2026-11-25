"""Heading-aware chunking: one chunk per '##' section, split on paragraphs when long."""

import re
from dataclasses import dataclass

from ingest.anchors import AnchorRegistry

DEFAULT_MAX_WORDS = 300
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Chunk:
    section: str
    anchor: str
    ordinal: int
    text: str
    token_count: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate (about 4 tokens per 3 words). Used for budgeting, not billing."""
    return max(1, round(len(text.split()) * 4 / 3))


def _sections(body: str, title: str) -> list[tuple[str, str]]:
    """Split a Markdown body into (heading, text) pairs on level-2 headings.

    Headings inside fenced code blocks are ignored. Text before the first '##' heading is
    filed under the document title. Level-1 headings are dropped; deeper headings stay in text.
    """
    sections: list[tuple[str, list[str]]] = [(title, [])]
    in_fence = False
    for line in _COMMENT.sub("", body).split("\n"):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            sections.append((line[3:].strip(), []))
            continue
        if not in_fence and line.startswith("# "):
            continue
        sections[-1][1].append(line)
    return [(heading, "\n".join(lines).strip()) for heading, lines in sections]


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_long(text: str, max_words: int) -> list[str]:
    """Pack paragraphs into pieces of at most max_words, repeating one paragraph of overlap.

    A single paragraph longer than max_words becomes its own piece rather than being cut
    mid-sentence.
    """
    if len(text.split()) <= max_words:
        return [text]
    pieces: list[list[str]] = []
    current: list[str] = []
    for para in _paragraphs(text):
        words = sum(len(p.split()) for p in current)
        if current and words + len(para.split()) > max_words:
            pieces.append(current)
            overlap = current[-1]
            current = [overlap] if len(overlap.split()) < max_words // 2 else []
        current.append(para)
    if current:
        pieces.append(current)
    return ["\n\n".join(piece) for piece in pieces]


def chunk_document(body: str, title: str, max_words: int = DEFAULT_MAX_WORDS) -> list[Chunk]:
    anchors = AnchorRegistry()
    chunks: list[Chunk] = []
    for heading, text in _sections(body, title):
        anchor = anchors.anchor_for(heading)
        if not text:
            continue
        for piece in _split_long(text, max_words):
            chunks.append(
                Chunk(
                    section=heading,
                    anchor=anchor,
                    ordinal=len(chunks),
                    text=piece,
                    token_count=estimate_tokens(piece),
                )
            )
    return chunks
