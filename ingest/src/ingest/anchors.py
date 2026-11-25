"""Heading anchor rules shared with the web app (see docs/decisions/0002-chunking-and-anchors.md).

Rules, matching GitHub-style heading ids:
1. Lowercase the heading text.
2. Remove every character that is not a letter, digit, space, hyphen or underscore.
3. Replace each space with a hyphen (runs of hyphens are kept, as on GitHub).
4. Repeated anchors in one document get "-1", "-2", ... appended in order of appearance.
"""

import re

_STRIP = re.compile(r"[^\w\- ]", re.UNICODE)


def slugify(heading: str) -> str:
    return _STRIP.sub("", heading.strip().lower()).replace(" ", "-")


class AnchorRegistry:
    """Assigns unique anchors within one document."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def anchor_for(self, heading: str) -> str:
        base = slugify(heading)
        count = self._seen.get(base, 0)
        self._seen[base] = count + 1
        return base if count == 0 else f"{base}-{count}"
