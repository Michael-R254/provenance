from itertools import pairwise

from ingest.chunk import chunk_document, estimate_tokens


def test_one_chunk_per_level_two_section() -> None:
    body = "## First\n\nAlpha text.\n\n## Second\n\nBeta text.\n"
    chunks = chunk_document(body, "Doc")
    assert [(c.section, c.anchor, c.ordinal) for c in chunks] == [
        ("First", "first", 0),
        ("Second", "second", 1),
    ]


def test_preamble_is_filed_under_the_title_and_comments_are_removed() -> None:
    body = "<!-- hidden -->\nIntro words.\n\n## Next\n\nMore."
    chunks = chunk_document(body, "Doc Title")
    assert chunks[0].section == "Doc Title"
    assert chunks[0].text == "Intro words."
    assert all("hidden" not in c.text for c in chunks)


def test_headings_inside_code_fences_are_not_sections() -> None:
    body = "## Code\n\n```python\n## not a heading\n```\n"
    chunks = chunk_document(body, "Doc")
    assert len(chunks) == 1
    assert "## not a heading" in chunks[0].text


def test_empty_sections_are_skipped_but_keep_anchor_numbering() -> None:
    body = "## Results\n\n## Results\n\nSecond one.\n"
    chunks = chunk_document(body, "Doc")
    assert [(c.section, c.anchor) for c in chunks] == [("Results", "results-1")]


def test_long_sections_split_on_paragraphs_with_overlap() -> None:
    paragraphs = [f"Paragraph {i} " + "word " * 40 for i in range(6)]
    body = "## Long\n\n" + "\n\n".join(paragraphs)
    chunks = chunk_document(body, "Doc", max_words=100)
    assert len(chunks) > 1
    assert all(c.section == "Long" and c.anchor == "long" for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    # each piece after the first repeats the previous piece's last paragraph
    for previous, current in pairwise(chunks):
        assert current.text.split("\n\n")[0] == previous.text.split("\n\n")[-1]


def test_token_estimate_is_positive_and_scales_with_length() -> None:
    assert estimate_tokens("one") == 1
    assert estimate_tokens("word " * 30) == 40
