"""Checks the real embedding model. Opt-in because it downloads the model (about 70 MB)."""

import os

import pytest

from ingest.embed import EMBEDDING_DIM, FastEmbedEmbedder

pytestmark = pytest.mark.skipif(
    os.environ.get("PROVENANCE_TEST_REAL_EMBEDDER") != "1",
    reason="set PROVENANCE_TEST_REAL_EMBEDDER=1 to download and test the real model",
)


def test_real_model_has_expected_size_and_ranks_related_text_higher() -> None:
    embedder = FastEmbedEmbedder()
    query, near, far = embedder.embed(
        [
            "How were made-up answers from the language model reduced?",
            "We reduced hallucinations by grounding generation in retrieved evidence.",
            "The database migrations run in a single transaction.",
        ]
    )
    assert len(query) == EMBEDDING_DIM

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(query, near) > cosine(query, far)
