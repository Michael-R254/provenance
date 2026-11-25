"""Evaluation question sets (see datasets/fixture.yaml for the format)."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal[
    "single_project", "multi_project", "recruiter", "distinction", "unanswerable", "adversarial"
]


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: Category
    question: str = Field(min_length=1)
    project: str | None = None
    expected: list[str] = Field(default_factory=list)
    must_contain: list[str] = Field(default_factory=list)
    must_not_contain: list[str] = Field(default_factory=list)

    @field_validator("expected")
    @classmethod
    def _expected_are_source_anchor_pairs(cls, value: list[str]) -> list[str]:
        for item in value:
            source, sep, anchor = item.partition("#")
            if not sep or not source or not anchor:
                raise ValueError(f"expected entries look like 'path.md#anchor', got {item!r}")
        return value

    @property
    def answerable(self) -> bool:
        return bool(self.expected)


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    questions: list[Question]

    @field_validator("questions")
    @classmethod
    def _unique_ids(cls, value: list[Question]) -> list[Question]:
        ids = [q.id for q in value]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate question ids: {sorted(duplicates)}")
        return value


def load_dataset(path: Path) -> Dataset:
    return Dataset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
