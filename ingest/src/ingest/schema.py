"""Frontmatter schemas for content files. Mirrors content/_template.md."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

Status = Literal["draft", "approved"]
ProjectType = Literal["research", "dissertation", "coursework", "personal", "work"]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=SLUG_PATTERN)
    title: str = Field(min_length=1)
    status: Status
    version: int = Field(ge=1)
    updated: date


class ProfileFrontmatter(_Base):
    """Frontmatter for non-project files such as profile.md, cv.md, skills.md and faq.md."""


class ProjectFrontmatter(_Base):
    type: ProjectType
    organisation: str | None = None
    role: str | None = None
    period: str | None = None
    repo: str | None = Field(default=None, pattern=r"^https://")
    permission: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    research_areas: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)

    _blank = field_validator("organisation", "role", "period", "repo", mode="before")(
        _blank_to_none
    )

    @model_validator(mode="after")
    def _approved_needs_permission(self) -> "ProjectFrontmatter":
        if self.status == "approved" and self.permission.strip().lower() == "pending":
            raise ValueError("an approved project cannot have permission: pending")
        return self

    def tags(self) -> dict[str, list[str]]:
        return {
            "skills": self.skills,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "models": self.models,
            "research_areas": self.research_areas,
        }
