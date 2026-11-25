"""Turning retrieved chunks into a grounded prompt, and checking the citations that come back.

Everything here is plain, deterministic Python so it can be unit tested without a model.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from provenance.llm import GenerationRequest, Message
from provenance.retrieval import RetrievedChunk

CITATION = re.compile(r"\[(c\d{1,3})\]")
_MAX_PENDING = 8  # longest possible citation marker is "[c999]"


@dataclass(frozen=True)
class Turn:
    question: str
    answer: str


@dataclass(frozen=True)
class Evidence:
    """Chunks shown to the model, each with a stable citation ID (c1, c2, ...)."""

    chunks: Mapping[str, RetrievedChunk]

    @classmethod
    def from_chunks(cls, chunks: Sequence[RetrievedChunk]) -> "Evidence":
        return cls({f"c{i}": chunk for i, chunk in enumerate(chunks, start=1)})


def has_enough_evidence(chunks: Sequence[RetrievedChunk], min_similarity: float) -> bool:
    """True when at least one chunk is semantically close enough to answer from.

    Keyword matches alone are not enough: any-term matching (ADR 0003) finds something for
    almost every question, including ones the corpus cannot answer.
    """
    best = max((c.vector_score or 0.0 for c in chunks), default=0.0)
    return best >= min_similarity


_FOLLOW_UP = re.compile(
    r"^(and|also|what about|how about|why|how|tell me more|more)\b|\b(it|its|that|this|they|"
    r"them|those|these|there|he|his|him)\b",
    re.IGNORECASE,
)


def retrieval_query(question: str, history: Sequence[Turn]) -> str:
    """Rule-based follow-up rewrite: short or pronoun-led questions borrow the last question.

    No model call, so it costs nothing and cannot be steered by prompt injection.
    """
    if not history:
        return question
    if len(question.split()) <= 6 or _FOLLOW_UP.search(question):
        return f"{history[-1].question} {question}"
    return question


def build_request(
    system_prompt: str,
    question: str,
    history: Sequence[Turn],
    evidence: Evidence,
    guardrails: Mapping[str, Sequence[str]],
    max_output_tokens: int,
) -> GenerationRequest:
    messages: list[Message] = []
    for turn in history:
        messages.append(Message("user", turn.question))
        messages.append(Message("assistant", turn.answer))
    messages.append(Message("user", _user_turn(question, evidence, guardrails)))
    return GenerationRequest(system_prompt, messages, max_output_tokens)


def _user_turn(question: str, evidence: Evidence, guardrails: Mapping[str, Sequence[str]]) -> str:
    parts = ["<evidence>"]
    for cid, chunk in evidence.chunks.items():
        parts.append(
            f'<passage id="{cid}" source="{_attr(chunk.document_title)}"'
            f' section="{_attr(chunk.section)}">\n{_strip_tags(chunk.text)}\n</passage>'
        )
    parts.append("</evidence>")
    slugs = sorted({c.project_slug for c in evidence.chunks.values() if c.project_slug})
    rules = [(slug, rule) for slug in slugs for rule in guardrails.get(slug, ())]
    if rules:
        parts.append("<guardrails>")
        parts.extend(f"- {slug}: {_strip_tags(rule)}" for slug, rule in rules)
        parts.append("</guardrails>")
    parts.append(f"<question>\n{_strip_tags(question)}\n</question>")
    return "\n".join(parts)


def _attr(value: str) -> str:
    return value.replace('"', "'").replace("<", "").replace(">", "")


def _strip_tags(text: str) -> str:
    """Stop data from closing our own XML-style sections early."""
    return re.sub(r"</?\s*(evidence|passage|guardrails|question)\b[^>]*>", "", text, flags=re.I)


@dataclass
class CitationFilter:
    """Streams text through, dropping citation markers whose IDs were never supplied.

    Text after an unclosed "[" is held back (a few characters at most) until it can be judged.
    """

    allowed: frozenset[str]
    removed: list[str] = field(default_factory=list)
    used: list[str] = field(default_factory=list)
    _pending: str = ""
    _text: list[str] = field(default_factory=list)

    def feed(self, delta: str) -> str:
        buffer = self._pending + delta
        out: list[str] = []
        i = 0
        while i < len(buffer):
            start = buffer.find("[", i)
            if start == -1:
                out.append(buffer[i:])
                i = len(buffer)
                break
            out.append(buffer[i:start])
            end = buffer.find("]", start)
            if end == -1:
                if len(buffer) - start <= _MAX_PENDING and _could_be_citation(buffer[start:]):
                    self._pending = buffer[start:]
                    emitted = "".join(out)
                    self._text.append(emitted)
                    return emitted
                out.append(buffer[start])
                i = start + 1
                continue
            marker = buffer[start : end + 1]
            match = CITATION.fullmatch(marker)
            if match is None:
                out.append(buffer[start])
                i = start + 1
                continue
            cid = match.group(1)
            if cid in self.allowed:
                out.append(marker)
                if cid not in self.used:
                    self.used.append(cid)
            else:
                self.removed.append(cid)
            i = end + 1
        self._pending = ""
        emitted = "".join(out)
        self._text.append(emitted)
        return emitted

    def flush(self) -> str:
        rest, self._pending = self._pending, ""
        self._text.append(rest)
        return rest

    @property
    def text(self) -> str:
        return "".join(self._text)


def _could_be_citation(prefix: str) -> bool:
    return re.fullmatch(r"\[(c\d{0,3})?", prefix) is not None


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")


def unsupported_sentences(answer: str) -> list[str]:
    """Sentences that make a statement but carry no citation (wave 2 adds a semantic check)."""
    sentences = [s.strip() for s in _SENTENCE.split(answer) if s.strip()]
    return [s for s in sentences if not CITATION.search(s) and len(s.split()) > 3]
