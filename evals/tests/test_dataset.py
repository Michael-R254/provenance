from pathlib import Path

import pytest
from ingest.validate import prepare
from pydantic import ValidationError

from evals.dataset import Dataset, load_dataset
from evals.retrieval import DEFAULT_CONTENT, DEFAULT_DATASET


def test_fixture_dataset_loads_and_points_at_real_fixture_chunks() -> None:
    dataset = load_dataset(DEFAULT_DATASET)
    available = {
        f"{doc.source.relative_path}#{chunk.anchor}"
        for doc in prepare(DEFAULT_CONTENT).documents
        for chunk in doc.chunks
    }
    for question in dataset.questions:
        for expected in question.expected:
            assert expected in available, f"{question.id}: {expected} is not a fixture chunk"


def test_expected_entries_need_an_anchor() -> None:
    with pytest.raises(ValidationError):
        Dataset.model_validate(
            {
                "version": "x",
                "questions": [
                    {"id": "a", "category": "single_project", "question": "q", "expected": ["p.md"]}
                ],
            }
        )


def test_duplicate_ids_are_rejected() -> None:
    question = {"id": "a", "category": "unanswerable", "question": "q"}
    with pytest.raises(ValidationError):
        Dataset.model_validate({"version": "x", "questions": [question, question]})


def test_real_question_file_is_valid_if_present() -> None:
    path = Path(DEFAULT_DATASET).parent / "questions.yaml"
    if path.exists():
        load_dataset(path)
