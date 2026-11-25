from provenance.retrieval import RetrievedChunk, reciprocal_rank_fusion


def _chunk(
    chunk_id: int, vector_rank: int | None = None, keyword_rank: int | None = None
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_title="Example",
        project_slug="example",
        source_path="projects/example.md",
        url="/projects/example",
        section="Section",
        anchor="section",
        text="text",
        vector_rank=vector_rank,
        keyword_rank=keyword_rank,
    )


def test_chunk_found_by_both_methods_outranks_chunks_found_by_one() -> None:
    vector = [_chunk(1, vector_rank=1), _chunk(2, vector_rank=2)]
    keyword = [_chunk(3, keyword_rank=1), _chunk(2, keyword_rank=2)]
    fused = reciprocal_rank_fusion(vector, keyword, rrf_k=60)
    assert [c.chunk_id for c in fused] == [2, 1, 3]
    top = fused[0]
    assert top.vector_rank == 2 and top.keyword_rank == 2
    assert top.fused_score == 2 / 62


def test_ties_break_by_best_rank_then_id() -> None:
    fused = reciprocal_rank_fusion([_chunk(5, vector_rank=1)], [_chunk(4, keyword_rank=1)])
    assert [c.chunk_id for c in fused] == [4, 5]


def test_single_list_keeps_its_order() -> None:
    hits = [_chunk(9, keyword_rank=1), _chunk(3, keyword_rank=2), _chunk(7, keyword_rank=3)]
    assert [c.chunk_id for c in reciprocal_rank_fusion([], hits)] == [9, 3, 7]


def test_empty_inputs_give_empty_output() -> None:
    assert reciprocal_rank_fusion([], []) == []


def test_citation_url_appends_anchor() -> None:
    assert _chunk(1).citation_url == "/projects/example#section"
