import pytest

from delta_feed.core.entity_matching import rank_embedding_candidates


def test_cosine_similarity_ranks_candidates_descending_and_skips_incompatible_vectors():
    ranked = rank_embedding_candidates(
        [1.0, 0.0],
        [
            (1, [0.0, 1.0]),
            (2, [1.0, 0.0]),
            (3, [0.8, 0.6]),
            (4, [1.0]),
        ],
    )

    assert [candidate.entity_key for candidate in ranked] == [2, 3, 1]
    assert [candidate.similarity for candidate in ranked] == pytest.approx([1.0, 0.8, 0.0])


def test_cosine_similarity_rejects_empty_zero_or_nonfinite_query_vectors():
    with pytest.raises(ValueError):
        rank_embedding_candidates([], [])
    with pytest.raises(ValueError):
        rank_embedding_candidates([0.0, 0.0], [])
    with pytest.raises(ValueError):
        rank_embedding_candidates([float("nan"), 1.0], [])
