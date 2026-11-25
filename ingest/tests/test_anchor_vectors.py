import json
from pathlib import Path

from ingest.anchors import AnchorRegistry

VECTORS = Path(__file__).parent / "fixtures" / "anchor-vectors.json"


def test_shared_anchor_vectors() -> None:
    """The web app runs the same vectors, so page ids and citation links always agree."""
    for case in json.loads(VECTORS.read_text(encoding="utf-8"))["cases"]:
        registry = AnchorRegistry()
        anchors = [registry.anchor_for(h) for h in [case["title"], *case["headings"]]]
        assert anchors == case["anchors"], case["title"]
