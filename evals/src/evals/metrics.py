"""Retrieval metrics. Pure functions over ranked result keys ('path.md#anchor')."""

from collections.abc import Sequence


def recall_at_k(expected: Sequence[str], ranked: Sequence[str], k: int) -> float:
    """Share of expected chunks that appear in the top k."""
    if not expected:
        raise ValueError("recall is undefined for questions with no expected chunks")
    top = set(ranked[:k])
    return sum(1 for item in set(expected) if item in top) / len(set(expected))


def hit_at_k(expected: Sequence[str], ranked: Sequence[str], k: int) -> float:
    """1.0 if any expected chunk appears in the top k, else 0.0."""
    return 1.0 if set(expected) & set(ranked[:k]) else 0.0


def reciprocal_rank(expected: Sequence[str], ranked: Sequence[str]) -> float:
    """1 / rank of the first expected chunk (0.0 if none is retrieved)."""
    wanted = set(expected)
    for rank, item in enumerate(ranked, start=1):
        if item in wanted:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
