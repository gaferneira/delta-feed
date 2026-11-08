# Collector ingestion API

*   **Author:** Gabriel
*   **Status:** Proposed
*   **Date:** 2026-11-07

--------------------------------------------------------------------------------

## Overview

Delta Feed is a self-hosted reader for tech people who run homelab servers. Articles reach it today through RSS polling and manual submission. This design adds a third way in: an authenticated HTTP API that external collectors (n8n, scripts) call to submit an article's title and text. It is the `provided_content` mode of the ingestion contract in [docs/ingestion-contract.md](../ingestion-contract.md). The contract's other mode, `fetch_url`, where the server fetches a page itself, stays a reference and is not built here.

What happens to an article after it arrives (extraction, claim comparison, the Delta page) is a separate design: [Delta Feed: novelty-first reading](delta-feed-novelty-first-reading.md). That design works with articles from any source and does not depend on this one.

## The Problem

RSS covers sources that publish a feed. Other sources need a collector that fetches, logs in or extracts text on its own, and then needs a safe way to hand the result to Delta Feed. The API must accept observations only: a collector cannot submit instructions, novelty verdicts or guide edits. It must also be safe to retry, because collectors run unattended and networks fail. A leaked collector credential must be revocable without touching the reader's own login, and must reach only the sources it was granted.

## Goals

*   Collectors submit articles through `POST /api/v1/ingestions` in `provided_content` mode, following the contract.
*   Revocable bearer credentials, each scoped to a set of configured sources. Credentials are stored only as hashes.
*   Retries are safe: the same idempotency key and payload returns the same receipt, and a different payload under the same key is rejected.
*   A status endpoint shows what happened to a submission, in stages.
*   The server makes no outbound request on this path; the collector supplies the text.
*   Oversized requests and floods are refused with clear errors, and error payloads never include tokens or article bodies.

## Non-Goals

*   The contract's `fetch_url` mode. Requests in that mode are rejected with a clear error.
*   Callback URLs. The contract accepts none, because they add an outbound trust boundary; collectors poll the status endpoint.
*   Creating sources or topics as a side effect of ingestion. Sources and credentials are created by an administrator command.
*   Using `topic_hints` for classification. They are validated and stored on the receipt only.
*   Multi-user hosting.

## Open Questions

*   **Idempotency retention window**: The contract leaves the window unset. This design keeps receipts without purging; what window should apply before collectors are enabled?
*   **Revision ordering rule**: A delayed or excerpt-only submission must not replace a newer or fuller revision. The rule in the plan (use `source_modified_at` when present, never let an excerpt replace a full body, otherwise arrival order) is provisional, and the contract says ambiguous precedence should keep both observations without replacing. Is the rule acceptable for each source, or must ordering be declared per source?
*   **URL required**: The contract allows `external_id` without a URL. `Article.url` is required and the reader links to it, so this design requires a URL. Is an `external_id`-only submission needed?
*   **Collector routing**: The browser proxy forwards only an allowlist of headers, so collectors must reach the backend through the deployment's reverse proxy at `/api/v1/`, not through the Astro `/api/` route. Compose routing is not built yet.
*   **Status stages**: The `analysis` and `delta` stages of the status endpoint need the novelty pipeline design to exist. Until then the endpoint returns only the `content` stage.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

Terms: a *source* is an explicitly configured publisher (the existing `Source` model). An *article revision* is one stored snapshot of an article's title and text. A *receipt* records one accepted submission.

*   **Separate API.** `POST /api/v1/ingestions` and `GET /api/v1/ingestions/{id}` live on a second Ninja API instance mounted at `/api/v1/`, with bearer authentication and no CSRF or session handling. The existing session API at `/api/` is unchanged.
*   **Credentials.** A collector credential is a random token stored only as a hash, with a display prefix, a revocation time, a last-used time and a set of sources it may submit to. Credentials and collector sources are created by an administrator command, never as an ingestion side effect. The raw token is shown once and never logged.
*   **Sources.** A source gets a stable `key` (the contract's `source_id`). Collector sources have no RSS URL.
*   **Request.** Fields follow the contract's `provided_content` envelope: `source_id`, `url`, `title`, `content` (`format` text, `body`, `completeness`, optional `extraction_method`), optional `external_id`, `published_at`, `topic_hints` (validated against existing topic ids, 422 on unknown ids, stored on the receipt and not used further), `source_revision_id`, `source_modified_at`, `observed_at`. Unknown fields and `mode: fetch_url` are rejected with 422. The `Idempotency-Key` header is required.
*   **Idempotency.** A receipt is unique per credential and key. The same key with the same normalized payload returns 200 with the existing receipt and its current state (a first acceptance returns 202); the same key with a different payload returns 409 and changes nothing. The normalized payload covers source key, URL, title, body, completeness, `source_revision_id` and `source_modified_at`, and excludes `observed_at` and the idempotency key. Concurrent retries are settled by the database unique constraint.
*   **Acceptance.** In one transaction the server stores the receipt, finds or creates the article (by `external_id`, then URL, adopting a manual article with the same URL), and appends a revision when the body hash differs from the latest revision's. Analysis is then picked up by the worker's existing scheduling of unanalysed articles. The response is 202 with `ingestion_id`, `status` and `status_url`.
*   **Revision ordering (provisional).** A new body becomes the current revision unless ordering evidence says it is older: `source_modified_at` earlier than the current revision's, or an `excerpt` arriving when the current revision is `full`. In those cases the revision is stored with the next version number, the article's current version stays unchanged, and nothing is replaced.
*   **Status.** `GET` returns the stages separately: content (stored), analysis (unanalysed, analysed or failed, from the analysis-status helper the Feed also uses) and delta (claim counts and pending mentions for the current revision). The `analysis` and `delta` stages need the novelty pipeline design; until it exists the endpoint returns only the content stage. Only the credential that created the receipt can read a receipt; others get 403.
*   **Limits.** A middleware limited to `/api/v1/` returns 413 when `Content-Length` exceeds a request-size cap, before the body is parsed; a parsed body above a character cap returns 413 in the view. Submissions per credential are rate limited (429, keyed on the credential id, 60-second window), following the throttle in `accounts/api.py`, and error payloads never include tokens or bodies. The rate limit uses Django's default per-process cache, which is a known limit for several web workers.
*   **Routing.** The browser proxy forwards only an allowlist of headers and cannot carry bearer tokens, so it is not the route for collectors. Collectors reach `/api/v1/` through the deployment's reverse proxy, or directly on the backend port in development.

## Alternatives Considered

### Alternative A: Build `fetch_url` mode in this design

*   **Pros**: Matches the full contract, and a bare URL could be submitted from any tool.
*   **Cons**: An outbound request to a user-supplied URL brings in SSRF, decompression, slow-server and redirect risks that the contract requires tests for before exposure. Article text extraction adds a dependency that is not pinned.
*   **Reason for Rejection**: Rejected by author for this design: `provided_content` is mandatory and `fetch_url` stays a reference in the contract, so the collector sends the text.

### Alternative B: Collectors reuse the browser session login

*   **Pros**: No new credential model.
*   **Cons**: Cookies and CSRF are built for browsers. A session cannot be scoped to sources or revoked per collector, and a leaked cookie grants the whole account.
*   **Reason for Rejection**: Rejected by author: the contract requires revocable, scoped bearer credentials for collectors.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Paths are relative to the repository root. Backend paths under `backend/src/delta_feed/` are shortened to `delta_feed/`. The work is one commit-sized unit with one migration file, `content` 0007. The submission endpoint is independent of the novelty pipeline design; the status endpoint's `analysis` and `delta` stages are added after that design's Units 1 to 3 exist.

### Data and contract definitions

*   **`CollectorCredential`** (content): `name` (200), `token_prefix` (8 characters), `token_hash` (64, unique), `sources` (M2M to `Source`), `created_by` (FK user, PROTECT), `created_at`, `last_used_at` (null), `revoked_at` (null).
*   **`IngestionReceipt`** (content): `credential` (FK, PROTECT), `idempotency_key` (255), `request_fingerprint` (64), `source` (FK, PROTECT), `external_id` (512, null), `url` (2048), `topic_hints` (JSON list), `article` (FK, CASCADE), `revision` (FK, CASCADE), `received_at`. Unique on (`credential`, `idempotency_key`).
*   **`Source.key`** (content): `SlugField(80)`, unique, nullable; used as the contract's `source_id`.
*   **`ArticleRevision`** additions: `source_revision_id` (255, blank allowed), `source_modified_at` and `observed_at` (null), `completeness` (`full`, `excerpt`, `unknown`; default `unknown`), `extraction_method` (80, blank allowed), `received_via` (`manual`, `rss`, `collector`; default `manual`; the migration sets `rss` where the article has a source and `submitted_by` is null, and `manual` otherwise; legacy snapshot revisions created by `current_revision` get `rss` when the article has a source and `manual` when it does not).
*   **Ingestion response**: `{ ingestion_id, status, status_url }` with 202; status `GET` returns `{ ingestion_id, received_at, content: { stored, article_id, revision_number, is_current }, analysis: unanalysed | analysed | failed, delta: { claims_by_kind, pending_mentions } }`.

### Target Files to Create/Modify

1.  `delta_feed/content/models.py` (Modify). Add `Source.key`, the `ArticleRevision` fields, `CollectorCredential` and `IngestionReceipt`. `delta_feed/content/api.py`, `delta_feed/content/rss.py` and `delta_feed/content/revisions.py` (Modify) set `received_via` (`manual` and `rss`) where they create revisions, following the backfill rule above.
2.  `delta_feed/content/migrations/0007_collector_ingestion.py` (Create). Generated with `makemigrations -n collector_ingestion`.
3.  `delta_feed/content/collector_auth.py` (Create). Token generation (`secrets.token_urlsafe(32)`, with `token_prefix` its first 8 characters), SHA-256 hex hashing, and an `HttpBearer` authenticator that looks up the hash, rejects revoked credentials, updates `last_used_at` at most once a minute, and attaches the credential to the request. Never logs the token.
4.  `delta_feed/content/ingestion.py` (Create). `observe_article(...)`: finds or creates the article in this order: (source, `external_id`, capped at 512 characters), then (source, URL checked with `safe_http_url`), then a manual article with the same URL and no source, which is adopted by setting its source, as `rss.py` does; a new article gets `is_backfill` false. It reuses `article_content_hash` and compares a new body with the latest revision's hash only; collector revisions have `submitted_by` null (the credential is on the receipt). The older-replay logic in `rss.py` is not reused; the revision-ordering rule in the Technical Plan is used instead. It applies that rule, updates `Article.title`, `body`, `current_version`, `source_published_at` and `is_backfill` as `submit_article` does, stores the revision and the receipt in one transaction, and handles the idempotency conflict (same fingerprint returns the receipt, different fingerprint raises a conflict). `request_fingerprint(payload)` hashes the normalized fields listed in the Technical Plan.
5.  `delta_feed/content/collector_limits.py` (Create). A Django middleware that applies only to paths under `/api/v1/` and returns 413 when `Content-Length` exceeds `COLLECTOR_MAX_REQUEST_BYTES`, before Ninja parses the body.
6.  `delta_feed/content/collector_api.py` (Create). Router with the discriminated request schema (`provided_content` accepted; `fetch_url` and unknown fields give 422), the `Idempotency-Key` check, the parsed-body character check (413), the rate limit (429), the 202 response and the status `GET` with its source and owner scope (403). The status `analysis` and `delta` stages call the shared analysis-status helper and claim counts from the novelty pipeline design once they exist.
7.  `delta_feed/api.py` (Modify). Add a second Ninja API instance named `collector_api` with `urls_namespace="collector"`, the bearer authenticator, no CSRF decorator, and the collector router. The status endpoint reads the authenticated credential from `request.auth`.
8.  `delta_feed/config/urls.py` (Modify). Mount `api/v1/` before `api/`.
9.  `delta_feed/content/management/__init__.py`, `delta_feed/content/management/commands/__init__.py` (Create). Package files for the new command.
10. `delta_feed/content/management/commands/manage_collectors.py` (Create). Subcommands `create-source` (name, key), `create-credential` (name, source keys, `--user <username>`, which defaults to the only user when exactly one exists and is an error otherwise; prints the token once), `revoke-credential`, `list`.
11. `delta_feed/content/sources_api.py` (Modify). `GET /api/content/sources` lists only sources that have an RSS feed URL, so collector sources do not appear on the Sources page.
12. `delta_feed/config/settings.py` (Modify). Add `COLLECTOR_MAX_REQUEST_BYTES` (integer, default 1,500,000), `COLLECTOR_MAX_BODY_CHARS` (integer, default 300,000, matching manual submission) and `COLLECTOR_RATE_LIMIT_PER_MINUTE` (integer, default 60, provisional), all read with `_env_int`. The middleware in item 5 is added to `MIDDLEWARE` here and enforces the byte cap, and `DATA_UPLOAD_MAX_MEMORY_SIZE` is set to the same value; the view checks the parsed body against the character cap (413).
13. `.env.example` (Modify). Document the three collector settings.
14. `docs/ingestion-contract.md` (Modify). Mark `provided_content` as implemented, keep `fetch_url` as a reference, and record the narrowing: URL required, provisional revision-ordering rule, no idempotency purge yet, no ingestion job created (analysis is scheduled by the worker's existing loop), and the third status stage named `delta` instead of `publication`.

### Verification Plan

New automated tests are out of scope for this phase (author decision); verification uses the commands below.

*   **Compilation/Build**: `cd backend && DJANGO_DEBUG=true uv run python manage.py makemigrations --check`.
*   **Existing suites**: `make test-backend` must still pass. Update existing assertions only where this plan changes behaviour (for example tests that create revisions). A test that cannot be updated in this phase stays red and is listed in the commit message.
*   **Static Analysis & Linting**: `make lint-backend` (ruff).
*   **Collector API (curl)**: create a source and credential with `manage_collectors` and use `curl` with the bearer token. Cases and results: first submission, 202; same `Idempotency-Key` and payload, 200 with the same receipt; same key with a different payload, 409; revoked token, 401; source outside the credential's set, 403; `mode: fetch_url`, 422; oversized request, 413; status endpoint, the `content` stage (and `analysis` and `delta` once the novelty pipeline design is built).

--------------------------------------------------------------------------------

*Drafted with EGM*
