import math

from ingest.embed import EMBEDDING_DIM, FakeEmbedder, embedding_input


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_embedder_is_deterministic_normalised_and_correct_size() -> None:
    embedder = FakeEmbedder()
    first, again = embedder.embed(["sorting widgets"]), embedder.embed(["sorting widgets"])
    assert first == again
    assert len(first[0]) == EMBEDDING_DIM
    assert math.isclose(math.sqrt(sum(v * v for v in first[0])), 1.0)


def test_fake_embedder_ranks_overlapping_text_higher() -> None:
    query, near, far = FakeEmbedder().embed(
        ["sorting widgets by colour", "widgets sorted by colour", "database migrations"]
    )
    assert _cosine(query, near) > _cosine(query, far)


def test_embedding_input_includes_title_and_section() -> None:
    assert embedding_input("Title", "Section", "Body") == "Title | Section\n\nBody"
