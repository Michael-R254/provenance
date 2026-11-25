import pytest

from evals.metrics import hit_at_k, mean, recall_at_k, reciprocal_rank


def test_recall_counts_expected_items_in_top_k() -> None:
    assert recall_at_k(["a", "b"], ["x", "a", "y", "b"], k=2) == 0.5
    assert recall_at_k(["a", "b"], ["x", "a", "y", "b"], k=4) == 1.0


def test_recall_is_undefined_without_expected_items() -> None:
    with pytest.raises(ValueError):
        recall_at_k([], ["a"], k=1)


def test_hit_and_reciprocal_rank() -> None:
    assert hit_at_k(["b"], ["a", "b"], k=1) == 0.0
    assert hit_at_k(["b"], ["a", "b"], k=2) == 1.0
    assert reciprocal_rank(["b"], ["a", "b"]) == 0.5
    assert reciprocal_rank(["z"], ["a", "b"]) == 0.0


def test_mean_of_nothing_is_zero() -> None:
    assert mean([]) == 0.0
    assert mean([1.0, 0.0]) == 0.5
