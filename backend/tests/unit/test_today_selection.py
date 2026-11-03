from delta_feed.reader.today import select_today


def candidates(*source_keys):
    """Newest-first (article_id, source_key) pairs; ids count up from 1."""
    return [(index + 1, key) for index, key in enumerate(source_keys)]


def test_everything_shown_when_within_budget_and_cap():
    shown, overflow = select_today(candidates("a", "b", "a"), budget=12, per_source_cap=3)
    assert shown == [1, 2, 3]
    assert overflow == []


def test_per_source_cap_pushes_extra_articles_to_overflow():
    shown, overflow = select_today(
        candidates("a", "a", "a", "a", "a", "b"), budget=12, per_source_cap=3
    )
    assert shown == [1, 2, 3, 6]
    assert overflow == [4, 5]


def test_budget_is_filled_in_rounds_so_one_source_cannot_crowd_out_others():
    # Source a is newest and prolific; b and c each have one older article.
    shown, overflow = select_today(
        candidates("a", "a", "a", "b", "c"), budget=3, per_source_cap=3
    )
    # Round 1 gives a, b, c their newest article; a's extras wait.
    assert shown == [1, 4, 5]
    assert overflow == [2, 3]


def test_shown_and_overflow_keep_recency_order_and_partition_the_input():
    pairs = candidates("a", "b", "a", "c", "b", "a", "d", "a")
    shown, overflow = select_today(pairs, budget=5, per_source_cap=2)
    assert shown == sorted(shown)
    assert overflow == sorted(overflow)
    assert sorted(shown + overflow) == [pair[0] for pair in pairs]
    assert len(shown) == 5


def test_zero_budget_shows_nothing_but_hides_nothing():
    shown, overflow = select_today(candidates("a", "b"), budget=0, per_source_cap=3)
    assert shown == []
    assert overflow == [1, 2]
