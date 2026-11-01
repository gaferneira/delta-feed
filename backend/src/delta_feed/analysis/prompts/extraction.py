"""Prompt rendering for the versioned entity-and-claim extraction task."""

from pathlib import Path
from string import Template

from delta_feed.analysis.contracts.extraction import EXTRACTION_SCHEMA_ID

PROMPT_VERSION = "delta-feed.extract-claims.v1"
_TEMPLATE_PATH = Path(__file__).with_name("extract_claims_v1.md")


def render_extraction_prompt(*, article_title: str, article_text: str) -> str:
    template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.substitute(
        schema_identifier=EXTRACTION_SCHEMA_ID,
        title=article_title,
        article_text=article_text,
    )
