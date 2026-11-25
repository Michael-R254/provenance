from ingest.anchors import AnchorRegistry, slugify


def test_slugify_follows_github_style_rules() -> None:
    assert slugify("My contributions") == "my-contributions"
    assert slugify("Limitations and what I would do next") == "limitations-and-what-i-would-do-next"
    assert slugify("Links & media") == "links--media"
    assert slugify("  C++ / CUDA  ") == "c--cuda"


def test_registry_suffixes_repeated_headings() -> None:
    registry = AnchorRegistry()
    assert [registry.anchor_for("Results") for _ in range(3)] == [
        "results",
        "results-1",
        "results-2",
    ]
