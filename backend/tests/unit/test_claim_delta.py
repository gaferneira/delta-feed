from delta_feed.core.claim_delta import classify_claim_delta


def claim(text, *, version=None, platform=None, availability=None):
    return {
        "claim_text": text,
        "version": version,
        "platform": platform,
        "availability": availability,
    }


def test_same_scope_same_normalized_assertion_is_duplicate():
    assert classify_claim_delta(
        claim("Widget supports ARM."),
        [claim(" widget   supports ARM ")],
    ) == "duplicate"


def test_same_scope_additional_nonconflicting_detail_is_refinement():
    assert classify_claim_delta(
        claim("Widget supports ARM on Linux."),
        [claim("Widget supports ARM.")],
    ) == "refinement"


def test_same_scope_explicit_negation_is_contradiction():
    assert classify_claim_delta(
        claim("Widget does not support ARM."),
        [claim("Widget supports ARM.")],
    ) == "contradiction"


def test_different_scope_is_new_even_when_assertion_text_matches():
    assert classify_claim_delta(
        claim("Widget supports ARM.", version="2.0"),
        [claim("Widget supports ARM.", version="1.0")],
    ) == "new"


def test_no_prior_claim_is_new():
    assert classify_claim_delta(claim("Widget supports ARM."), []) == "new"
