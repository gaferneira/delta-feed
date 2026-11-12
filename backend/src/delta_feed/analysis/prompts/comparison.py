"""Prompt rendering for the versioned claim comparison task."""

import json
from pathlib import Path
from string import Template

from delta_feed.analysis.contracts.comparison import COMPARISON_SCHEMA_ID

PROMPT_VERSION = "delta-feed.compare-claims.v1"
MAX_BASELINE_CLAIMS = 50
_TEMPLATE_PATH = Path(__file__).with_name("compare_claims_v1.md")


def _get(item, key):
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def render_comparison_prompt(entity, new_claims, baseline_claims) -> str:
    """Render the comparison prompt.

    `new_claims` are dicts (claim_data) and get their list position as `claim_index`;
    `baseline_claims` are Claim rows, newest first, cut to MAX_BASELINE_CLAIMS.
    Article-derived text is only ever placed inside JSON in delimited data blocks.
    """
    baseline = list(baseline_claims)[:MAX_BASELINE_CLAIMS]
    labels = list(dict.fromkeys(p for p in (_get(c, "predicate") for c in baseline) if p))
    return Template(_TEMPLATE_PATH.read_text(encoding="utf-8")).substitute(
        schema_identifier=COMPARISON_SCHEMA_ID,
        entity_name=json.dumps(entity.name, ensure_ascii=False),
        entity_type=json.dumps(entity.type, ensure_ascii=False),
        predicate_labels=_json(labels),
        baseline_claims=_json(
            [
                {
                    "id": claim.pk,
                    "predicate": _get(claim, "predicate"),
                    "claim_text": _get(claim, "claim_text"),
                    "version": _get(claim, "version"),
                    "platform": _get(claim, "platform"),
                    "availability": _get(claim, "availability"),
                }
                for claim in baseline
            ]
        ),
        new_claims=_json(
            [
                {
                    "claim_index": index,
                    "predicate": _get(claim, "predicate"),
                    "value": _get(claim, "value"),
                    "version": _get(claim, "version"),
                    "platform": _get(claim, "platform"),
                    "availability": _get(claim, "availability"),
                    "evidence": _get(claim, "evidence_text"),
                }
                for index, claim in enumerate(new_claims)
            ]
        ),
    )
