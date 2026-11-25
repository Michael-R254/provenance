"""Versioned prompt text. Loaded only by the server; never returned by any endpoint."""

from importlib.resources import files

ANSWER_PROMPT_VERSION = "answer-v1"


def answer_system_prompt() -> str:
    return files(__package__).joinpath(f"{ANSWER_PROMPT_VERSION}.md").read_text(encoding="utf-8")
