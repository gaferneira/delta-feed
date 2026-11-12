# Core loop: ingest → extract → claims → comparison → Delta API

## Objective

Make one loop work end to end on real articles from the dev database: an analysed article's extracted claims become knowledge claims, are compared with the baseline, and come back as a Delta card from `GET /api/reader/delta`.

## Scope

- In: product clarity review; design Units 1 and 2 in full; from Unit 3 only the Delta endpoint and the shared analysis-status helpers; a real run against LM Studio.
- Out (listed under "Open decisions" in `docs/roadmap.md`): baseline readiness, landing preference and banner, Feed item extensions, guide proposal changes (Unit 4), frontend (Unit 5), evaluation harness (Unit 6), ADR 0011 and doc updates (Unit 7), new automated tests (waived for this phase).

## Checklist

- [x] T0 Clarity review (a4ac647). Its findings now live in `docs/status.md` and its open decisions in `docs/roadmap.md`; the review file was removed in the docs reorganisation.
- [x] T1 Unit 1: `ExtractedMention`, claim comparison fields and fingerprint (`knowledge` 0005), `core/claim_fingerprint.py`, `application/mention_resolution.py`, `record_claim` taking a decision, mentions list/resolve API.
- [x] T2 Unit 2: `AnalysisRun.kind` and `compared_at` (`analysis` 0006), comparison contract and prompt, `application/claim_comparison.py`, `analysis.compare` and `analysis.compare_group` jobs, `enqueue_comparisons` command.
- [x] T3 Unit 3 (reduced): `GET /api/reader/delta` with `pending_mentions`; `analysis/status.py`.
- [x] T4 Real run (2026-11-12, LM Studio `google/gemma-4-e4b`): migrations applied to the dev DB after a file backup; 3 articles extracted (1 completed, 2 `invalid_output`: a claim referenced an undeclared entity ref); the name was created through `POST /api/knowledge/mentions/resolve`; `GET /api/reader/delta` returned one card for article 2498 with two first-sighting claims. Requests ran through Django's test client as the existing user, not over HTTP.
- [x] T5 Extraction salvage: malformed claims and entities are dropped and listed under `dropped` in the run output instead of failing the article; failed runs store their validation error.
- [x] T6 Extraction prompt pass: plain entity names, six fixed entity types, declared refs, short predicate labels. Re-run on 5 real articles (dev DB reset to its pre-run copy first): 5 completed, 5 Delta cards, 11 entities.
- [x] T7 Matching and salvage pass, checked on real articles: mentions resolve by name regardless of type; an entity with a valid claim survives a bad quote of its own; comparison keeps the valid answers when the model skips a claim; prompt rules for editions, specific values and fact-based comparison. The same roundup from two feeds (articles 2283 and 2326): 5 of 6 claims duplicate, 1 unsure.

## Checks

- `cd backend && DJANGO_DEBUG=true uv run python manage.py makemigrations --check`
- `make test-backend` (existing suite must keep passing; assertions updated only where behaviour changed)
- `make lint-backend`
- T4: the `curl` request and response for `GET /api/reader/delta`, recorded in the final report.
