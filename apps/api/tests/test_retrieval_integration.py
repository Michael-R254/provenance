import psycopg
import pytest

from provenance.embedding import FakeEmbedder
from provenance.retrieval import (
    EmbeddingModelMismatchError,
    NoActiveIndexError,
    Retriever,
)
from tests.conftest import add_document, add_version

pytestmark = pytest.mark.integration

WIDGETS = {
    "Overview": "A fictional tool that sorts imaginary widgets by colour.",
    "Results": "The fictional sorter grouped widgets into seven colour bins.",
}
WEATHER = {
    "Overview": "A fictional forecaster that predicts imaginary rainfall.",
    "Architecture": "Readings flow through a queue into a gradient boosting model.",
}


@pytest.fixture
def indexed(db: psycopg.Connection) -> psycopg.Connection:
    old = add_version(db, "retired")
    add_document(db, old, "example-old", {"Overview": "Retired text about widgets and colour."})
    active = add_version(db, "active")
    add_document(db, active, "example-widgets", WIDGETS)
    add_document(db, active, "example-weather", WEATHER)
    return db


def test_hybrid_ranks_the_relevant_section_first(indexed: psycopg.Connection) -> None:
    result = Retriever(FakeEmbedder()).retrieve(indexed, "how were widgets sorted by colour")
    top = result.chunks[0]
    assert top.project_slug == "example-widgets"
    assert top.vector_rank is not None and top.keyword_rank is not None
    assert set(result.timings_ms) >= {"embed", "vector", "keyword", "fuse", "total"}


def test_only_the_active_version_is_searched(indexed: psycopg.Connection) -> None:
    result = Retriever(FakeEmbedder()).retrieve(indexed, "retired widgets colour")
    assert all(c.project_slug != "example-old" for c in result.chunks)


def test_keyword_search_matches_exact_terms(indexed: psycopg.Connection) -> None:
    result = Retriever(FakeEmbedder()).retrieve(indexed, "gradient boosting", method="keyword")
    assert [c.anchor for c in result.chunks] == ["architecture"]
    assert result.chunks[0].vector_rank is None


def test_keyword_search_matches_any_term_and_ranks_by_coverage(
    indexed: psycopg.Connection,
) -> None:
    result = Retriever(FakeEmbedder()).retrieve(
        indexed, "which colour bins did the widgets go into", method="keyword"
    )
    assert result.chunks[0].anchor == "results"
    assert len(result.chunks) > 1


def test_keyword_search_with_only_stop_words_returns_nothing(indexed: psycopg.Connection) -> None:
    result = Retriever(FakeEmbedder()).retrieve(indexed, "the and of", method="keyword")
    assert result.chunks == []


def test_project_filter_limits_results(indexed: psycopg.Connection) -> None:
    result = Retriever(FakeEmbedder()).retrieve(
        indexed, "fictional overview", project="example-weather"
    )
    assert result.chunks
    assert {c.project_slug for c in result.chunks} == {"example-weather"}


def test_top_n_limits_results(indexed: psycopg.Connection) -> None:
    result = Retriever(FakeEmbedder()).retrieve(indexed, "fictional", top_n=2, method="vector")
    assert len(result.chunks) == 2


def test_model_mismatch_is_refused(db: psycopg.Connection) -> None:
    add_version(db, "active", model="some-other-model")
    with pytest.raises(EmbeddingModelMismatchError):
        Retriever(FakeEmbedder()).retrieve(db, "anything")


def test_no_active_index_is_reported(db: psycopg.Connection) -> None:
    add_version(db, "building")
    with pytest.raises(NoActiveIndexError):
        Retriever(FakeEmbedder()).retrieve(db, "anything")
