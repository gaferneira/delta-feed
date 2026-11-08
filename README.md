# Delta Feed

A self-hosted reader with two jobs: show you what is actually new (unfamiliar projects and meaningful updates) without repeating what you already know, and keep your own reference articles up to date.

> **Status:** early, local-only. The reader, guides, RSS ingestion and claim API are implemented and covered by automated tests (backend 217 pytest, frontend 116 vitest + Astro build) against a SQLite dev DB. Several pieces are built but not wired together, and nothing has been deployed or run against real data. See [Project status](#project-status).

## The problem

A ten-item roundup may contain only one project you haven't seen. Five articles may announce the same feature. Reading all of them to find the one new thing is wasted time.

Meanwhile, the articles you actually rely on, such as "Recommended skills every project should have" or "Raspberry Pi projects for home automation", go stale quietly: a recommended tool gets a major release, another is abandoned, a better option appears.

## What Delta Feed does

- **News about new things.** It breaks articles into the things they mention (tools, libraries, projects, hardware, practices) and the claims they make about them ("version 2 adds ARM support", "now generally available"). It compares those against what it has already seen and surfaces the genuine discoveries and changes, always linked to the original sources. When it is unsure, it says so; it never silently hides content.
- **Living guides.** You keep your own articles as structured entries plus your own writing. When the news shows that an entry should be added, updated, warned about or retired, Delta Feed proposes the change with evidence. Nothing changes until you approve it, and your own text is never overwritten.

The two reinforce each other: news produces guide proposals, and what is already in your guides tells Delta Feed what you know and care about.

Software, AI and home-automation hardware are the first interests, but topics are configuration, not hardcoded categories.

## MVP

- Responsive web reader with Delta, Feed and Saved pages ([ADR 0008](docs/decisions/0008-delta-page-and-feed.md)).
- Built-in RSS/Atom, manual submission, and an authenticated ingestion API for external collectors such as n8n.
- Entity resolution using strong identifiers, similarity candidates and bounded model adjudication.
- Claim comparison that respects version, platform and availability, with source evidence.
- Read/save state plus "already knew this" and "wrong match" feedback.
- Pending, failed, uncertain and suppressed content stays inspectable.
- Guides: manual structured entries with your notes and revision history first; reviewed, evidence-backed update proposals once analysis exists.
- Configurable inference and embedding providers; local Ollama first.

Out of scope: multi-user hosting, autonomous browsing or source discovery, arbitrary scraping, and complex recommendation systems.


## How it will work

- **Reader:** Astro, server-rendered, TypeScript.
- **API and backend:** Django, with Django Ninja for the JSON API. Django also handles login, the database layer and business logic.
- **Storage:** PostgreSQL for deployment; SQLite for local development and tests only. pgvector is deferred until embeddings are used ([ADR 0010](docs/decisions/0010-postgres-required-pgvector-deferred.md)).
- **Background worker:** a separate Python process sharing the backend image.
- **Models:** a local Ollama instance by default; no cloud inference unless you explicitly configure it.

Everything ships as one repository and one Compose installation. Built-in RSS and direct Ollama support make it standalone; FreshRSS, n8n, Telegram and agent runtimes are optional integrations, never requirements.

## Project status

This section is the single place that tracks project status; other documents link here.

- **Decided:** standalone modular monolith ([ADR 0001](docs/decisions/0001-modular-monolith.md)), Astro + Django Ninja ([ADR 0002](docs/decisions/0002-astro-django-ninja.md)), selective hexagonal backend ([ADR 0003](docs/decisions/0003-selective-hexagonal-backend.md)), content and ingestion defaults ([ADR 0004](docs/decisions/0004-content-and-ingestion-defaults.md)).
- **Proposed:** attention budget and analysis funnel ([ADR 0006](docs/decisions/0006-attention-budget-and-analysis-funnel.md)) and preference signals with transparent ranking ([ADR 0007](docs/decisions/0007-preference-signals-and-transparent-ranking.md)). Only ADR 0006 Phase A is implemented: bounded backfill (last 30 days, 20 items per source), recurring RSS polling by the worker, and a Today budget (12 cards, 3 per source, "Show N more from today"). Covered by automated tests and a curl smoke run on a throwaway DB, with the network mocked; not run against live feeds or in a browser. Phases B to E and ADR 0007 are not implemented.
- **Proposed:** Delta page and chronological Feed ([ADR 0008](docs/decisions/0008-delta-page-and-feed.md)): the default page shows per-article delta cards built only from non-duplicate claims, Feed lists every article newest first, and the quiet backfill seeds the baseline. Not implemented.
- **Proposed:** guide proposal resolution ([ADR 0009](docs/decisions/0009-guide-proposal-resolution-policies.md)): manual review only at first, expiry and auto-accept deferred. PostgreSQL required for deployment, SQLite for development and tests only, pgvector deferred ([ADR 0010](docs/decisions/0010-postgres-required-pgvector-deferred.md)). ADR 0009 is not implemented; ADR 0010 matches the current code (SQLite default, `DB_ENGINE=postgresql` switch), but no PostgreSQL deployment has been verified.
- **Proposed:** progressive onboarding and familiarity ([ADR 0005](docs/decisions/0005-progressive-onboarding.md)), with phased delivery; only step 0 is implemented: first-run account creation at `/setup`, guarded by a one-time token logged by the backend or printed by `cd backend && uv run python manage.py setup_token` (rotates the token; refuses once a user exists). Covered by automated tests only, not exercised in a browser. Step 1 is also implemented minimally: a user who has not finished onboarding is sent to `/onboarding` to pick topics and confirm starter-pack feeds from `starter-packs/` (or skip), which registers them as sources with a quiet backfill; tested and smoke-tested with curl, not exercised in a browser.
- **Verified by automated tests only (SQLite dev DB, mocked network, no live browser/end-to-end run):**
  - [Milestone 1](docs/roadmap.md#milestone-1-reader-vertical-slice-no-ai): login, manual submission, paginated reader feed (Today / Earlier / All), read/save state.
  - [Milestone 2](docs/roadmap.md#milestone-2-manual-guides-no-ai): manual guides with optimistic-concurrency revisions.
  - [Milestone 3](docs/roadmap.md#milestone-3-safe-ingestion-and-jobs) (partial): bounded RSS fetching that validates every redirect hop and pins the connection to the validated public IP, http(s)-only link validation, and a DB-backed lease/retry job worker. DNS pinning is tested against a loopback server and mocks, not against real TLS/SNI endpoints.
  - [Milestone 4](docs/roadmap.md#milestone-4-discovery-shadow-mode-and-guide-additions) and [5](docs/roadmap.md#milestone-5-entity-deltas-and-guide-updates-in-shadow-mode) as library/API code: entity matching, append-only scoped claims tied to the analysed article revision (completed analysis runs only), and reviewable guide proposals. Accepting an update merges into existing text instead of overwriting it.
- **Built but not wired into a running flow:**
  - Extraction ([ADR 0006 Phase B](docs/roadmap.md#adr-0006-attention-budget-and-analysis-funnel)) runs in the worker as an `analysis.extract` job under a daily budget and stores a validated shadow proposal on `AnalysisRun`, but it has not been run against a real model, and its claims are not yet turned into knowledge claims or delta cards.
  - `guides.use_cases.generate_guide_proposals_for_entity` has no production caller. Update/warning/retire proposals are only generated when a claim is posted through `POST /api/knowledge/claims`.
  - RSS polling runs only while the worker is running (`manage.py run_worker`, or `scripts/dev.sh`); without it no new articles arrive.
  - Embedding/similarity candidate matching exists, but nothing populates embeddings.
- **Known limits:** login throttling uses a per-process cache; analysis runs recorded before revision tracking have no revision and cannot accept claims; the frontend was upgraded to Astro 6 because Astro 7 needs a newer Node than the dev machine has.
- **Not yet done:** [Milestone 0](docs/roadmap.md#milestone-0-real-examples)'s real-article worked-example corpus (requires Gabriel's own collected examples, not synthetic ones), and [Milestone 6](docs/roadmap.md#milestone-6-private-deployment-and-first-daily-trial) deployment — production PostgreSQL, HTTPS ingress, backup/restore verification, migration runs against Postgres, and the daily trial itself.
- **Local development:** copy `.env.example` to `.env` (gitignored) and adjust it, then run `./scripts/dev.sh` to start the backend (8000), the worker and the frontend (4321) together; Ctrl-C stops all three. The script loads `.env`, with variables already set in your shell taking precedence; Django itself only reads the process environment, so tests never pick up `.env`. It never runs migrations: if some are pending it prints the command. Or run each yourself, for example `cd backend && uv run --env-file ../.env python manage.py run_worker` starts the worker (it polls sources every `RSS_POLL_INTERVAL_MINUTES`, default 30, and handles queued jobs). Attention settings, all optional environment variables: `BACKFILL_DAYS` (30), `BACKFILL_MAX_ITEMS` (20), `RSS_POLL_INTERVAL_MINUTES` (30), `TODAY_BUDGET` (12), `TODAY_PER_SOURCE_CAP` (3). Extraction runs only when the provider is configured: `ANALYSIS_PROVIDER` set to `ollama` (with `OLLAMA_HOST` and `OLLAMA_MODEL`) or `openai_compatible` for LM Studio and similar servers (with `OPENAI_COMPAT_BASE_URL`, for example `http://localhost:1234/v1`, `OPENAI_COMPAT_MODEL` and, only if the server needs one, `OPENAI_COMPAT_API_KEY`), plus `ANALYSIS_DAILY_BUDGET` (50 model runs a day), `ANALYSIS_TIMEOUT_SECONDS` (300) and `ANALYSIS_MAX_BODY_CHARS` (20000). Tests: `cd backend && uv run pytest -q` and `cd frontend && npm test`. Settings refuse to start without a real `DJANGO_SECRET_KEY` unless `DJANGO_DEBUG=true`; production cookies are `Secure` by default. `scripts/init.sh` sets `DJANGO_DEBUG=true` for local use.

**Next step:** run extraction against a real local model and review the claims, then build the [Delta page and Feed](docs/roadmap.md#adr-0008-delta-page-and-feed), then [Milestone 6](docs/roadmap.md#milestone-6-private-deployment-and-first-daily-trial): verify standalone install (PostgreSQL, Compose) and backup/restore before the first daily trial. Installation commands remain pending until that scaffold is exercised end-to-end outside the dev environment.

## Documentation

1. [Glossary](docs/glossary.md)
2. [Product scope and acceptance](docs/product.md)
3. [Architecture and reliability](docs/architecture.md)
4. [Technology selection](docs/technology.md)
5. [Architecture decisions](docs/decisions/)
6. [Repository layout and module ownership](docs/repository-structure.md)
7. [Development workflow and Claude skills](docs/development-workflow.md)
8. [Roadmap and evaluation](docs/roadmap.md)
9. [Building your baseline corpus](docs/baseline-corpus.md): start here to contribute real reading data
10. [Ingestion contract](docs/ingestion-contract.md)
11. [Content, guide and publication policy](docs/content-policy.md)

[AGENTS.md](AGENTS.md) defines implementation guardrails for coding assistants.

## Data and privacy

The application database owns articles, identities, claims, jobs, feedback and reading state. Git owns code, tests, technical decisions and deployment instructions. Personal planning lives outside this repository, and the news stream is never copied automatically into personal notes.

No cloud inference is enabled implicitly. Source excerpts, credentials and private infrastructure configuration must never be committed.

## License

Copyright © 2026 Gabriel Neira. Licensed under the [GNU Affero General Public License v3.0](LICENSE).

You may use, modify and redistribute Delta Feed freely. If you distribute a modified version, or let others use it over a network, you must make its source available under the same license.
