# Status

The only place that tracks what works. Last updated 2026-11-12.

**Stage:** early, single user, local development only. Nothing is deployed.

## What works

| Area | State | How it was checked |
|---|---|---|
| Sign-in, first-run setup, onboarding with starter packs | Works | Automated tests |
| RSS polling with bounded backfill, manual submission | Works | Automated tests; 181 real articles imported from 9 feeds |
| Reader: feed, read, save | Works | Automated tests |
| Saved page, topic and entity chips on Feed and Saved, Delta cards removed on read or save with Undo | Built, not covered by tests | `/api/reader/saved`, topics and entities checked with ad hoc requests; the screens have not been opened in a browser |
| Guides: manual entries, revisions, proposals to review | Works | Automated tests |
| Background worker: jobs, leases, retries | Works | Automated tests |
| Extraction with a local model | Works | Real run, see below |
| Name review (link, create, dismiss, undo, batch), claim comparison, Delta API | Works through the API | Real run, see below |
| Delta and Names screens | Work | Headless browser against the dev database, desktop and phone width; frontend tests |

Automated tests: 223 backend (pytest) and 145 frontend (vitest) pass. They use SQLite, a mocked network and a fake model, so they prove logic, not behaviour with real feeds, real models or concurrent workers.

## Real run (2026-11-12)

Dev machine, SQLite, LM Studio serving `google/gemma-4-e4b` (a small model; the machine has 16 GB of RAM).

- Extraction completed on every article tried after the fixes below, in 11 to 105 seconds each.
- Seven articles went through the whole loop; `GET /api/reader/delta` returned five cards.
- The same roundup from two feeds: the second copy's six claims came out as five duplicates and one "not sure".
- Requests were made with Django's test client as the signed-in user, and job handlers were called directly. The worker loop has not run these jobs. The screens were checked later in a headless browser; a full day of use in a normal browser has not happened yet.

What the run changed: malformed items from the model are dropped and counted instead of failing the article; names match existing entities regardless of type; the extraction prompt asks for plain names and a fixed list of six types.

## Known problems

- **Repeated coverage of an event is not caught.** Four articles about one security incident attached it to four different entities, and comparison only looks within one entity. This is the product's central promise and it does not hold yet.
- **The small model is unstable.** The same article gives between one and six claims across runs. A larger model has not been tried.
- **Every new name blocks its claims** until reviewed. By decision; the Names screen is meant to make this quick.
- **Extraction runs newest first, backfill last**, so history does not seed the baseline before today's articles are compared.
- **SQLite ignores row locks.** Two workers can both call a claim new. PostgreSQL is required for real use ([ADR 0010](decisions/0010-postgres-required-pgvector-deferred.md)) and has not been tested.
- Login throttling uses a per-process cache.

## Not built

- "I already knew this" and "wrong match" feedback.
- Baseline readiness check and choosing Delta as the landing page.
- Claim counts and matched duplicates on Feed rows; article detail.
- Guide proposal supersession, bulk reject and decision data ([ADR 0009](decisions/0009-guide-proposal-resolution-policies.md)).
- Evaluation harness and labelled corpus.
- Preference ranking, delivery levels, notifications.
- Embeddings and relevance filtering (the embedding table exists; nothing fills it).
- Collector API for external tools such as n8n.
- Deployment: PostgreSQL, Compose, HTTPS, backup and restore.
