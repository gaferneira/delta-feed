"""Today selection: a bounded, source-diverse view of recently discovered articles.

Pure functions over plain tuples so the ranking rule is testable without a database.
"""
from collections.abc import Hashable, Sequence


def select_today(
    candidates: Sequence[tuple[int, Hashable]], *, budget: int, per_source_cap: int
) -> tuple[list[int], list[int]]:
    """Split candidates into (shown ids, overflow ids).

    ``candidates`` are (article_id, source_key) pairs, newest first. The budget is
    filled in rounds: each round gives every source its next-newest article, so a
    prolific source cannot crowd out others, and no source exceeds ``per_source_cap``.
    Both lists keep the recency order of the input; nothing is dropped.
    """
    per_source: dict[Hashable, list[int]] = {}
    for article_id, source_key in candidates:
        per_source.setdefault(source_key, []).append(article_id)

    shown: set[int] = set()
    for round_number in range(max(0, per_source_cap)):
        for ids in per_source.values():
            if len(shown) >= budget:
                break
            if round_number < len(ids):
                shown.add(ids[round_number])
    ordered = [article_id for article_id, _source_key in candidates]
    return (
        [article_id for article_id in ordered if article_id in shown],
        [article_id for article_id in ordered if article_id not in shown],
    )
