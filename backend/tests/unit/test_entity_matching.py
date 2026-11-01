from delta_feed.core.entity_matching import match_exact_identifiers


def test_exact_identifier_match_returns_matching_entity_key():
    entities = [
        (1, {"canonical_url": "https://example.org/tool"}),
        (2, {"slug": "another-tool"}),
    ]

    assert match_exact_identifiers(
        {"canonical_url": "https://example.org/tool"}, entities
    ) == 1


def test_nonmatching_identifier_returns_no_match():
    entities = [(1, {"canonical_url": "https://example.org/tool"})]

    assert match_exact_identifiers({"slug": "different"}, entities) is None


def test_empty_candidate_identifiers_return_no_match():
    entities = [(1, {"canonical_url": "https://example.org/tool"})]

    assert match_exact_identifiers({}, entities) is None


def test_ambiguous_exact_identifiers_return_no_match():
    entities = [
        (1, {"canonical_url": "https://example.org/tool"}),
        (2, {"slug": "tool"}),
    ]

    assert match_exact_identifiers(
        {"canonical_url": "https://example.org/tool", "slug": "tool"}, entities
    ) is None
