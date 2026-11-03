# Starter packs

A starter pack is a topic plus a few suggested RSS/Atom feeds. The first-run onboarding screen at `/onboarding` offers them so a new reader does not start with an empty feed. Packs contain feeds only: no entity lists, no personal data. See [ADR 0005](../docs/decisions/0005-progressive-onboarding.md).

## Format

One TOML file per pack, read with the standard library (`tomllib`), no extra dependency. The loader (`backend/src/delta_feed/knowledge/starter_packs.py`) is strict: unknown keys, missing or empty fields, duplicate slugs, a `schema_version` it does not know, and any feed URL that is not an absolute `https://` URL without credentials are rejected with an error naming the file.

```toml
schema_version = 1            # currently always 1
slug = "home-automation"      # unique, lowercase letters, digits and hyphens; also the topic slug
title = "Home automation"
description = "One sentence on what the topic covers."

[[feeds]]                     # at least one
name = "Home Assistant blog"  # unique across all packs; becomes the Source name
feed_url = "https://www.home-assistant.io/atom.xml"
homepage_url = "https://www.home-assistant.io/blog/"
```

Choosing a pack creates its `Topic` (by slug) and registers each ticked feed as a source attached to that topic, which queues the usual quiet backfill. The backend reads this directory from `STARTER_PACKS_DIR` (default: `starter-packs/` at the repository root).

## Contributing a pack

1. Add `<slug>.toml` here, keeping the pack to a handful of feeds from sources the topic's readers would recognize.
2. Verify every feed URL yourself and note the output in the pull request:
   `curl -sSL -m 10 -o /dev/null -w '%{http_code} %{content_type}' <feed_url>` must print `200` and an XML, RSS or Atom content type. Never include a URL you have not checked.
3. No private data: no personal hostnames, tokens, private feed URLs or per-user query strings.
4. Run `cd backend && uv run pytest -q tests/unit/test_starter_packs.py`; it loads every shipped pack.
