from typing import Any

from ingest.embed import FakeEmbedder as IngestFake
from provenance.embedding import FakeEmbedder as ApiFake

from evals.retrieval import compare_with_baseline


def test_ingest_and_api_fake_embedders_are_identical() -> None:
    texts = ["Example Project | Overview\n\nSorting widgets by colour.", "", "ÜnïcØde text"]
    assert IngestFake().embed(texts) == ApiFake().embed(texts)
    assert IngestFake.model_name == ApiFake.model_name


def _summary(recall: float, mrr: float, embedder: str = "fake") -> dict[str, Any]:
    return {
        "dataset": "d",
        "k": 5,
        "embedder": embedder,
        "methods": {"hybrid": {"recall_at_k": recall, "hit_at_k": 1.0, "mrr": mrr}},
    }


def test_no_regression_when_metrics_hold_or_improve() -> None:
    assert compare_with_baseline(_summary(0.9, 0.8), _summary(0.9, 0.7)) == []


def test_drop_in_recall_or_mrr_is_a_regression() -> None:
    problems = compare_with_baseline(_summary(0.8, 0.6), _summary(0.9, 0.7))
    assert len(problems) == 2


def test_mismatched_setup_is_reported() -> None:
    assert compare_with_baseline(_summary(1, 1, "fastembed"), _summary(1, 1))
