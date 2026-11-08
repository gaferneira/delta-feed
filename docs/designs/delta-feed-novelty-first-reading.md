# Delta Feed: novelty-first reading

*   **Author:** Gabriel
*   **Status:** Proposed
*   **Date:** 2026-11-07

--------------------------------------------------------------------------------

## Overview

Delta Feed is a self-hosted reader for tech people who run homelab servers. It shows what is new to the reader and hides nothing for good. It breaks each article into claims about things (tools, versions, features), compares those claims with a baseline of what the reader already has, and shows one card per article containing only the new, changed or conflicting claims. A plain chronological Feed lists every article.

The reader also keeps "living guides": their own reference articles as structured entries plus their own writing. The system proposes guide changes with evidence, and the reader approves or rejects each one.

The reader chooses the model: a local one (Ollama or LM Studio) or their own API key. No cloud inference is on by default.

## The Problem

The reader opens articles whose titles promise value ("things every engineer should know in 2026", "hidden Claude features") and finds that most items are already known. Titles give no way to tell beforehand. Separately, ten articles often repeat the same news with the same content.

Deciding "this is nothing new" takes reading the article and knowing what the reader already knows. Both are costly, and a wrong "you know this" hides something useful, which costs more than the time saved. So the design must (a) judge novelty per claim, not per article, (b) keep everything reachable, and (c) build its model of the reader's knowledge from the reader's own guides, history and feedback, not from guesses.

The proposed solution is a Delta page of per-article cards built only from non-duplicate claims, a Feed page that hides nothing, a defined baseline, and manual-first guide proposals.

## Goals

*   One defined baseline: guide entities (confirmed by the reader), claims from the quiet backfill, and claims from articles already analysed. An entity with no baseline claims is shown as a "first sighting", not "new".
*   One Delta card per article that has at least one new, changed or conflicting claim. Card text comes only from those claims, each linked to its evidence passage.
*   Feed lists every article, newest first, and shows the matched duplicate for anything filtered out.
*   An article is never silently absent from Delta: when its mentions wait for review, Delta shows how many are waiting and Feed marks the article.
*   Feed is the landing page until a measurable baseline-readiness check passes. A banner then offers the switch to Delta. The page never changes on its own.
*   Guide proposals are manual only in the first release: one live proposal per guide entry, bulk reject, and decision data recorded from day one ([ADR 0009](../decisions/0009-guide-proposal-resolution-policies.md)).
*   PostgreSQL for any deployment, SQLite only for local development and tests; pgvector deferred ([ADR 0010](../decisions/0010-postgres-required-pgvector-deferred.md)).
*   Inference is the reader's choice: a local model or their own API key. Inference may run on the same machine or on another one.
*   A labelled corpus of real articles and an evaluation harness exist before Delta becomes the landing page, with two separate measures: novelty judged correctly, and guide proposal accepted.
*   Repeated coverage of one release produces few cards. Target: from a labelled group of 10 articles on one release, 2 or fewer produce a Delta card; if more do, the core promise fails.

## Non-Goals

*   Event clustering across articles. It may return later as a display layer if per-article cards still feel repetitive in the trial.
*   Model-written article summaries.
*   Expire-to-dismissed and auto-accept for guide proposals (a later ADR).
*   Multi-user hosting and a hosted service.
*   Hiding or suppressing articles automatically.
*   A collector ingestion API. It is a separate design, [Collector ingestion API](collector-ingestion-api.md); this design works with articles from any source because it starts after an article revision exists.

## Open Questions

*   **Readiness threshold**: Which measurable check and threshold mark the baseline as ready for the Delta banner? To be set from trial data.
*   **Claim matching method**: Exact claim fingerprints (entity, scope, attribute) first, then a model for ambiguous cases. How is the model's "same claim" answer validated against the evaluation corpus?
*   **Credit for repeated coverage**: Credit goes to the first article compared, and later articles point at it. Ordering comparisons by publication date across articles, and marking sources as primary or secondary, are deferred. Do they matter in the trial?
*   **Hosted API keys**: Only Ollama and OpenAI-compatible servers are supported today. Is a hosted API-key provider tested in the first slice?
*   **Review queue size**: Unresolved mentions wait for review. How many does a real corpus produce per day, and is grouping by name enough to keep the queue manageable? Measured in the evaluation harness.
*   **Landing preference storage**: The per-user landing page and banner dismissal are stored on `ReaderProfile`. Is a single profile row per user enough, given the app is single-user?

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

The plan extends the pipeline that already exists: article revision, extraction job, `AnalysisRun.output`. It adds the missing middle: writing claims to the baseline, comparing them in tiers, and serving Delta cards from the result. Names below come from the current code (`analysis/use_cases.py`, `knowledge/use_cases.py`, `core/claim_delta.py`, `reader/api.py`).

```text
RSS / manual submit / other sources
        |
        v
 Article + ArticleRevision (existing)
        |
        v   analysis.extract job (existing; Ollama / OpenAI-compatible)
 AnalysisRun.output  (entities + claims: predicate, value, scope, quotes)
        |
        v   analysis.compare job (new), one entity at a time
 +---------------------------------------------------------------+
 | 1. Resolve each mention to an entity (exact name/alias match; |
 |    no match -> pending mention, waits for review)             |
 | 2. Tier 1, deterministic: fingerprint match, then existing    |
 |    lexical rules in core/claim_delta.py     -> no model call  |
 | 3. Tier 2, model: compare against this entity's baseline      |
 |    claims  -> duplicate | refinement | contradiction |         |
 |               new | unsure                                    |
 | 4. In a transaction: lock entity, recheck baseline, write     |
 |    Claim with classification + matched claim + method         |
 +---------------------------------------------------------------+
        |
        v
 Claim (append-only) --> Delta API --> Delta cards (non-duplicates)
        |                          \-> Feed API   (everything)
        \--> guide proposals (manual review)
```

### 1. Baseline

The baseline is one query, not a separate store: the active (not superseded) `Claim` rows of an entity, plus the entity's presence in the reader's guides. Guide membership marks an entity as familiar but adds no claims, so an entity with guide membership and no claims is a first sighting. Claims enter the baseline when `record_claim` writes them from a completed analysis run.

### 2. Resolving mentions (author decision: unresolved mentions wait for review)

Extraction returns mentions with a name, a type and quotes, and no identifiers. Nothing in the code turns a mention into an `Entity` today, because entities are created only through the API and existing matching uses strong identifiers and embeddings.

*   A mention resolves automatically only on an exact match: its normalized name (see the normalization definition below) equals the normalized `Entity.name` or one of the normalized `aliases` of exactly one entity of the same type. Several matches leave the mention pending.
*   Any other mention is stored as a pending mention with its claims and evidence, and its claims are not written to the baseline.
*   The reader resolves pending mentions on a review page. For each group of mentions with the same normalized name and entity type, they link to an existing entity (the page lists entities whose normalized name contains or is contained by the mention's name, closest length first), create a new entity, or dismiss the group. A link adds the mention's name to the entity's aliases, so the same name resolves on its own from then on. One decision resolves every pending mention in the group, and the claims of each are then compared and written.
*   A dismissed group is remembered: mentions with the same normalized name and type are stored with status `dismissed` and skip the queue. Every mention is stored as an `ExtractedMention` row, with status `resolved` when it matched automatically, so counts stay consistent.
*   Entities from guide entries and starter packs already exist, so mentions of things the reader follows resolve without review.
*   Known cost: until mentions are resolved, their claims are missing from the baseline, so the cold start depends on how fast the reader clears the queue. Grouping by name, remembered aliases and bulk decisions are the mitigations.

### 3. Comparison tiers (author decision: fingerprint first, model for the rest)

*   **Fingerprint.** Extraction already returns `predicate`, `value` and `scope` per claim. The fingerprint is a hash of entity id, normalized predicate, normalized value and scope (version, platform, availability). An exact match to an active baseline claim is a duplicate with no model call. The existing lexical rules in `classify_claim_delta` (exact text, explicit negation, strict token-subset) run in the same deterministic tier.
*   **Model.** Claims that share an entity but match no fingerprint go to a new versioned task, `compare_claims`, with the entity's active baseline claims (typically dozens) as input. Output is validated against a strict schema: a classification, the id of the baseline claim it matched, and a one-line reason. After validation the code checks that every matched id was in the baseline supplied in the prompt. Anything the model cannot place, or any output that fails a check, is `unsure`, never `duplicate`.
*   **First sighting.** An entity with no baseline claims needs no comparison; its claims are `new` and the card labels the entity a first sighting.
*   **Predicate drift.** The same attribute named two ways ("Zigbee support", "Zigbee") misses the fingerprint and costs a model call. The comparison prompt shows the baseline's predicate labels so the model can match on meaning, and the evaluation harness counts how often this happens.

### 4. Writing claims safely

*   `Claim` stays append-only. It gains `predicate`, `value` and `fingerprint` (indexed), `matched_claim` (nullable, points at the claim it duplicates, refines or contradicts), `comparison_method` (`fingerprint`, `lexical`, `model`, `first_sighting`, `manual`), and an `unsure` classification.
*   Model calls never run inside a database transaction. The job reads the baseline, calls the model, then opens a transaction, locks the entity row (`select_for_update`, as `record_claim` does today), and rechecks that the baseline did not change. If it changed, the job reruns the deterministic tier against the new claims; if the claim still needs a model, it retries once and then records `unsure`.
*   Credit goes to the first article compared. A later duplicate points at that claim through `matched_claim`, and the card shows its source and publication date, so a reader can see when the first article was published later than the duplicate. This gives "first reported by X, also covered by N" without event clustering. Ordering comparisons by publication date across articles is deferred.
*   Inference outages leave claims unwritten and the job retries with backoff, like the extraction job. Invalid model output records `unsure` and stores the validation error.

### 5. Delta, Feed and the landing page

*   **Delta API** returns, per article, the claims classified `new`, `refinement`, `contradiction` or `unsure`, each with its evidence quote and the matched claim, plus the "also covered by N" count. Card text in the first slice is the original title plus claim bullets (the fallback ADR 0008 already allows). The model-written headline stays a later step.
*   **Feed API** (existing) lists every article. For an article with only duplicate claims it shows the matched baseline claim.
*   **Pending mentions.** An article whose mentions wait for review can have no Delta card, because their claims are not yet in the baseline. So the Delta API returns how many name groups and articles are waiting (`pending_mentions`), the Delta page shows a notice with that count and a link to the review page, and each such article shows "N mentions waiting for review" in Feed.
*   **Baseline readiness** is a function over the share of backfilled articles whose current revision has a completed comparison run and the number of guide entities, both compared with thresholds from settings (the share and the entity count must both pass). The API returns it with the threshold from settings. Feed is the landing page until the check passes, then the reader shows a banner offering Delta. The choice is stored per user and never changes automatically.

### 6. Guide proposals (manual only)

Proposals keep manual approval and add: one live proposal per guide entry (a newer one marks the older `superseded`), a bulk "reject older than N days" action, and recorded decision data (kind, decision, time to decision). Proposals have no inbox in the navigation, because they never block news: they appear as badges on the guide entries they affect and as a pending count per guide, and the reader opens them when they choose. Pending mentions do get a page in the navigation, because they block the baseline. Update, warning and retire proposals are generated through `record_claim`, which the compare job calls. `generate_guide_proposals_for_entity` (add proposals) is called when a mention group is resolved to an entity.

### 7. Inference and database

The `compare_claims` task uses the same provider adapters as extraction (Ollama, OpenAI-compatible with an optional API key), so a homelab can use a local model, a model on another machine, or a hosted API. PostgreSQL is required for deployment; SQLite stays for development and tests ([ADR 0010](../decisions/0010-postgres-required-pgvector-deferred.md)). No vector search is used.

### 8. Evaluation harness

A management command reads a labelled corpus from `local-corpus/` (kept out of git) and reports two measures separately: claims classified correctly, and the repeated-release test (a labelled group of 10 articles on one release produces 2 or fewer Delta cards). It runs on a real model before Delta becomes the landing page.

### 9. Sources other than RSS

The pipeline above starts after an article revision exists, so it does not depend on the source. Articles from a future collector API reach it the same way as RSS and manual submissions; that API is designed separately in [Collector ingestion API](collector-ingestion-api.md).

## Alternatives Considered

### Alternative A: Summarize each article with a model

*   **Pros**: Short cards, one model call per article, no claim comparison needed.
*   **Cons**: A summary repeats what the reader already knows, which is the pain being removed.
*   **Reason for Rejection**: Rejected by author: a summary does not say what is new, so it does not reduce reading.

### Alternative B: One card per event across articles

*   **Pros**: Ten articles on one launch become one card.
*   **Cons**: Needs reliable event clustering before the main page works. A wrong merge hides content.
*   **Reason for Rejection**: Deferred by author: claim-level novelty already keeps repeat articles off Delta, since only the first article carries the claims. Event grouping returns as a display layer only if the trial still shows repeated cards.

### Alternative C: Event grouping as a user setting now

*   **Pros**: Each reader picks the behaviour they want.
*   **Cons**: Two code paths and two screens to test, before there is evidence the second one is needed.
*   **Reason for Rejection**: Rejected by author for the first release: ship one behaviour and decide from trial data.

### Alternative D: The system decides what to hide from the feed

*   **Pros**: Fewer items to scan.
*   **Cons**: A wrong "you know this" hides something useful, which costs more than the reading time saved. It needs a model of the reader that does not exist at the start.
*   **Reason for Rejection**: Rejected by author: Feed stays unfiltered, and Delta only adds a view.

### Alternative E: Delta as the landing page from the first login

*   **Pros**: One default page and no switch to build.
*   **Cons**: With an empty baseline, almost every claim looks new, so the first days look like a summary feed.
*   **Reason for Rejection**: Rejected by author: Feed is the landing page until a measurable readiness check passes, then a banner offers the switch.

### Alternative F: Model compares every claim with the baseline (no fingerprints)

*   **Pros**: One comparison path, no new extraction field, simplest to test.
*   **Cons**: Every claim waits on the model, so an offline or slow model stalls the pipeline and the daily budget runs out quickly. A weak model gives inconsistent answers and repeated cards come back.
*   **Reason for Rejection**: Rejected by author: the fingerprint tier removes most model calls and makes exact duplicates explainable.

### Alternative G: Embedding similarity with a threshold

*   **Pros**: Handles paraphrases without per-attribute labels.
*   **Cons**: Nothing populates embeddings today and the threshold needs a corpus that does not exist yet. Similar text with different versions or negations can score as a duplicate and hide a real change. It also brings back the vector work deferred in ADR 0010.
*   **Reason for Rejection**: Rejected by author: unproven threshold and a risk of hiding changes. Revisit if predicate drift proves frequent in the evaluation harness.

### Alternative H: Auto-accept or expire guide proposals from the first release

*   **Pros**: A shorter review queue with no work from the reader.
*   **Cons**: Silence becomes consent, so a wrong version number or a wrongly "abandoned" tool could enter a guide unread. The acceptance data needed to judge it does not exist.
*   **Reason for Rejection**: Deferred by author ([ADR 0009](../decisions/0009-guide-proposal-resolution-policies.md)): manual only, with decision data recorded so a later ADR can use it.

### Alternative I: SQLite for deployment, or two databases

*   **Pros**: A single-file install on SQLite, or a separate store for vectors.
*   **Cons**: SQLite ignores the row locks the novelty design depends on, so two jobs can both call a claim new. Two stores must be kept in sync.
*   **Reason for Rejection**: Rejected by author ([ADR 0010](../decisions/0010-postgres-required-pgvector-deferred.md)): one database, PostgreSQL for deployment, SQLite for development and tests only.

### Alternative J: Match mentions by name and auto-create entities

*   **Pros**: No review step; cards flow immediately.
*   **Cons**: One thing under two names splits the baseline, so the second article looks like a first sighting and repeated cards return. Two unrelated things with one name merge.
*   **Reason for Rejection**: Rejected by author: wrong splits and merges corrupt the baseline, and similarity or name guesses never merge silently.

### Alternative K: Extraction returns strong identifiers, name as fallback

*   **Pros**: Reuses the identifier matching already in the code, and a verbatim check against the evidence quote blocks invented identifiers.
*   **Cons**: Roundups often state no identifier, so most mentions would fall back to name matching anyway. A prompt change forces re-extraction of articles already analysed.
*   **Reason for Rejection**: Rejected by author for the first release: it adds model work without removing the need for review.

### Alternative L: Hosted-only product for non-technical users

*   **Pros**: No install for the reader.
*   **Cons**: A different product with hosting, billing and multi-user concerns, and sending reading data to a service.
*   **Reason for Rejection**: Rejected by author: the target is tech people who self-host on homelab servers.

## Risks & Mitigations

Each row names a way the design can fail or do harm, what limits it, and what remains. "Feed" is the page that lists every article; "baseline" is what the reader already has, as defined in the glossary.

| Risk | What limits it | What remains |
|---|---|---|
| A wrong "same claim" judgement hides a real change. | A claim counts as a duplicate only on an exact fingerprint match, a lexical rule, or a model answer that names the matched baseline claim. Anything the model cannot place is `unsure`, which still appears on the card. Feed shows the matched duplicate for every filtered article. The harness reports classification accuracy. | A weak model can still misjudge a paraphrase. Accuracy per model class is unmeasured until the harness runs. |
| Text inside an article tries to steer the model (prompt injection). | The prompt delimits article text as data. The output schema allows only five classifications and a matched id, and code checks the id against the baseline. The model never writes to the database; code does. | A model can still be misled into a wrong classification inside the allowed set. |
| Evidence is invented. | Extraction rejects any quote that is not verbatim in the text the model received, and `record_claim` re-checks the span against the analysed revision. | None known beyond the extraction quote check itself. |
| Cold start: an empty baseline makes everything look new. | Feed is the landing page until a measurable readiness check passes. Entities with no claims are labelled "first sighting". The quiet backfill seeds the baseline. | The readiness thresholds are provisional until trial data sets them. |
| The mention review queue grows faster than the reader clears it, and the baseline stays thin. | Mentions are grouped by name and type, so one decision resolves many. A link remembers the name as an alias. Delta shows how many mentions wait and Feed marks affected articles. | Cold start still depends on how fast the reader clears the queue. Queue size is measured in the harness, not yet known. |
| Two jobs classify the same claim as new at once. | Row lock on the entity, a baseline-version recheck before writing, unique constraints per run, and PostgreSQL required for deployment. | SQLite does not honour the locks. New tests are deferred, so the manual two-worker PostgreSQL check is the only verification. |
| Model calls exhaust the daily budget and the backlog grows. | The deterministic tier needs no model call. Comparison calls count against the same daily budget as extraction. Claims that cannot be decided wait unwritten and are retried later. | With a small budget, comparison can lag behind extraction. The share of claims that need a model is measured in the harness. |
| The model provider is down or returns invalid output. | Outages leave claims unwritten and the job retries with backoff. Invalid output records `unsure` and stores the validation error on the comparison run. | During a long outage, Delta shows how many articles await analysis and Feed stays complete. |
| Delta hides articles with nothing new, which is a form of suppression. | Feed lists every article and shows matched duplicates. Delta does not fill itself with unanalysed articles. | There is no automatic check for a missed important event. The daily trial watches whether the reader falls back to Feed. |
| The first article compared gets credit even if another was published first. | A later article points at the first claim and the card shows both publication dates. | Ordering comparisons by publication date across articles is deferred. |
| Guide proposals pile up unreviewed. | One live proposal per guide entry, a bulk "reject older than N days" action, and manual approval only. | The queue can still grow for a reader who stops reviewing; expiry and auto-accept are deferred ([ADR 0009](../decisions/0009-guide-proposal-resolution-policies.md)). |
| Article text goes to a hosted service when the reader configures an API key. | No cloud inference is on by default. A hosted endpoint is used only when the reader sets it. | The reader decides, and `.env.example` warns that a hosted endpoint receives article text. |
| Untested code paths ship because new tests are deferred. | The existing suites must keep passing, and the harness and manual checks cover the new behaviour. | Regressions in new code can pass unnoticed until tests are added. This is an accepted trade-off for this phase. |

## Detailed Implementation Plan

Paths are relative to the repository root. Backend paths under `backend/src/delta_feed/` are shortened to `delta_feed/`. Work is split into commit-sized units, each with at most one migration file. Build the units in order; each needs the data or endpoints of the earlier ones it uses.

| Unit | Scope | Migration |
|---|---|---|
| 1 | Pending mentions, claim fields, fingerprint, claim writer | `knowledge` 0005 |
| 2 | Comparison task and the compare job | `analysis` 0006 |
| 3 | Delta and baseline-readiness APIs, landing preference | `accounts` 0004 |
| 4 | Guide proposal supersession, bulk reject, decision data | `guides` 0006 |
| 5 | Frontend: Delta, mentions review, banner, Feed default, proposals surfaced on guides | none |
| 6 | Evaluation harness | none |
| 7 | ADR and documentation | none |

Lettered items (7a, 9a, 10a, 17a, 22a, 32a) belong to the unit of the item before them.

### Data and contract definitions

*   **`ExtractedMention`** (knowledge): `analysis_run` (FK, CASCADE), `source_article` (FK, CASCADE), `ref` (`CharField(80)`, the mention's reference id inside its extraction output), `name` (250), `normalized_name` (250, indexed), `entity_type` (80), `evidence` (JSON quotes with offsets), `claims` (JSON: the extraction claims that reference this mention), `status` (`pending`, `resolved`, `dismissed`; default `pending`), `entity` (FK, PROTECT, null until resolved), `created_at`, `resolved_at` (null, set only on manual resolution), `compared_at` (null, set when the mention's claims have been compared and written). Unique on (`analysis_run`, `ref`) so a retried job cannot duplicate mentions.
*   **`Claim`** additions: `predicate` (`CharField(120)`) and `value` (`TextField`), both nullable, and `fingerprint` (`CharField(64)`, nullable, indexed), so claims posted through the existing claims API keep working; `matched_claim` (self FK, nullable, `on_delete=PROTECT`, `related_name="matched_by"`); `comparison_method` (`fingerprint`, `lexical`, `model`, `first_sighting`, `manual`; default `manual`); `comparison_model_version` and `comparison_prompt_version` (`CharField(120)`, blank allowed); and `unsure` added to `Classification`. Unique on (`analysis_run`, `fingerprint`) where the fingerprint is not null, so a retried compare job cannot duplicate claims.
*   **Extraction to claim mapping**: `claim_text` is `"<predicate>: <value>"`; `predicate`, `value` and the scope fields are copied (a missing scope value stays null); the first evidence span of the claim is the stored evidence; `confidence` is not stored in this release; `observed_at` is the article's `source_published_at` when set, otherwise the analysis run's `completed_at`. Spans lie inside the analysed text, because `resolve_evidence` rejects a quote that is not found in the truncated text the model received. In `claim_data` terms: `claim_text`, `version`, `platform` and `availability` (from `scope`), and `evidence_start`, `evidence_end` and `evidence_text` (from the first span's `start`, `end` and `quote`).
*   **Normalization**: `normalize_text` lowercases, collapses whitespace and strips trailing punctuation. `normalize_name` is `normalize_text` applied to entity names, aliases and mention names before comparing; stored `Entity.name` and aliases are normalized at comparison time, not rewritten.
*   **Fingerprint** (pseudocode): `sha256(entity_id | normalize_text(predicate) | normalize_text(value) | version | platform | availability)`, joined with `|`, with an empty string for a missing scope value.
*   **Comparison output schema** `delta-feed.comparison.v1`: `{ schema_id, results: [ { claim_index (zero-based), classification: duplicate | refinement | contradiction | new | unsure, matched_claim_id | null, reason (max 300 chars) } ] }`. Every extracted claim must have exactly one result. `duplicate`, `refinement` and `contradiction` require a non-null `matched_claim_id`; `new` and `unsure` require null. That every id belongs to the baseline supplied in the prompt is checked in code after model validation, because the provider adapters validate output without context.
*   **Delta API response** `GET /api/reader/delta`: `{ items: [ { article fields as in the Feed item, claims: [ { id, entity_name, claim_text, classification (new | refinement | contradiction | unsure), first_sighting, evidence_text, matched_claim_text | null } ], also_covered_by: int } ], total, limit, offset, has_more, pending_mentions: { groups, articles } }`. Items are ordered by article publication time (discovery time when unknown), newest first, and paged like the Feed (default 25, maximum 100). Ranking under the ADR 0006 budget is added later, during tuning ([roadmap](../roadmap.md#adr-0008-delta-page-and-feed)). `also_covered_by` is the number of distinct other articles that have a `duplicate` claim whose `matched_claim` is one of this article's displayed claims. Cards show `new` as New, `refinement` as Changed, `contradiction` as Conflicts and `unsure` as Not sure. `first_sighting` is per claim: true when that claim's `comparison_method` is `first_sighting`. The Feed item gains `pending_mentions` (integer: the article's mentions still waiting for review), `claim_counts` (`{ new, refinement, contradiction, unsure, duplicate }`, integers) and up to five `duplicates` (`{ claim_text, matched_claim_text, matched_article_title }`).
*   **Baseline API** `GET /api/reader/baseline`: `{ backfill_total, backfill_analysed, guide_entities, ready, landing_page, banner_dismissed }`. `POST /api/reader/landing` takes exactly one of `{ landing_page: "feed" | "delta" }` or `{ dismiss_banner: true }` (422 otherwise) and returns `{ landing_page, banner_dismissed }`. Both endpoints create the user's `ReaderProfile` when it is missing.
*   **Mentions API**: `GET /api/knowledge/mentions?status=pending` returns `MentionGroupOut` items `{ normalized_name, name_samples, entity_type, count, article_titles (up to 3), evidence_sample, candidates: [ { entity_id, name } ] }`. `status` accepts `pending`, `resolved` or `dismissed` (default `pending`). `candidates` holds at most 5 entities. `name_samples` holds up to 3 distinct raw names; `evidence_sample` is the first evidence quote of the first mention, cut to 300 characters. `POST /api/knowledge/mentions/resolve` takes `MentionResolveIn` `{ normalized_name, entity_type, action: link | create | dismiss, entity_id?, new_entity? }`: `link` requires `entity_id` of the same type as the group; `create` takes an optional `new_entity` `{ name, entity_type, canonical_url? }` that defaults to the group's name and type; `dismiss` takes neither; any other combination returns 422 and an unknown group 404. It returns `{ resolved_mentions, jobs_enqueued }`. A claim belongs to the mention whose `ref` equals its `entity_ref`; extraction validation already guarantees that mention exists.
*   **Bulk reject** `POST /api/guides/proposals/reject-older` takes `RejectOlderIn` `{ older_than_days }` (integer, at least 1) and rejects pending proposals older than that, returning the count. Bulk rejections store `decision_source` `bulk`; manual ones `manual`; replaced ones `superseded`.

*   **`AnalysisRun.kind`** (analysis): `extract` (default) or `compare`. Each `compare_claims` model call writes one `compare` run with its results in `output`, so the daily budget counts extraction runs and comparison calls together. `AnalysisRun.compared_at` (nullable) is set on an extraction run when its claims have been compared and written. `unanalysed_articles()` and the analysis-status helpers use only `extract` runs; `_budgeted_runs_today` stays unfiltered so comparison calls count, and provider outages do not count against the budget (it already excludes them).

### Target Files to Create/Modify

#### Unit 1: pending mentions, claim fields, claim writer

1.  `delta_feed/knowledge/models.py` (Modify). Add `ExtractedMention`; add the `Claim` fields, `ComparisonMethod` choices, the unique constraints and the `unsure` classification above. `Claim` stays append-only: all new fields are set at creation.
2.  `delta_feed/knowledge/migrations/0005_mentions_and_claim_comparison.py` (Create). Generated with `makemigrations -n mentions_and_claim_comparison`.
3.  `delta_feed/core/claim_fingerprint.py` (Create). Pure functions `normalize_text`, `normalize_name` and `claim_fingerprint(entity_id, predicate, value, scope)`, as defined above; the fingerprint imports `SCOPE_FIELDS` from `core/claim_delta.py`. No Django imports, matching `core/claim_delta.py`.
4.  `delta_feed/application/mention_resolution.py` (Create). `resolve_by_name(name, entity_type)` (scans entities in Python, comparing `normalize_name` of the mention with `normalize_name` of `Entity.name` and each alias; resolves only when exactly one entity of the same type matches); `candidate_entities(name, entity_type)` (name containment, closest length first); `queue_mentions(analysis_run, mentions, claims)` (stores every mention, with status `resolved`, `pending` or `dismissed`); `resolve_group(normalized_name, entity_type, action, entity=None, new_entity=None)` (links or creates the entity, adds the name to `aliases`, marks the group's mentions resolved, and returns them so the caller can enqueue comparison; `compared_at` later marks which mentions still need comparing).
5.  `delta_feed/knowledge/use_cases.py` (Modify). Extend `record_claim` with a keyword-only `decision` argument (classification, matched claim, method, model and prompt versions) plus `predicate` and `value`. When `decision` is given, the lexical classifier is skipped and the decision is stored. `supersedes` is set to the matched claim only for `contradiction`; `refinement` keeps both claims active. The fingerprint is computed when predicate and value are present. Keep the per-entity `select_for_update` and the guide-proposal hook as they are.
6.  `delta_feed/knowledge/api.py` (Modify). Add the two mentions endpoints. The candidates in the group listing come from `candidate_entities`; resolving calls `resolve_group` and marks the group's mentions resolved; it enqueues no job in this unit, because the job is registered in Unit 2. `create_claim` in this file sets `comparison_method` to `manual`. `delete_entity` returns the same 409 for mentions as it does for claims (verify against the existing handling when implementing).

#### Unit 2: comparison task and compare job

7.  `delta_feed/analysis/contracts/comparison.py` (Create). Pydantic strict models for `delta-feed.comparison.v1` with the validators above (one result per claim, and the classification and matched-id consistency rules above).
8.  `delta_feed/analysis/prompts/compare_claims_v1.md` (Create) and `delta_feed/analysis/prompts/comparison.py` (Create). Versioned prompt and `render_comparison_prompt(entity, new_claims, baseline_claims)`. The prompt lists the baseline's predicate labels and tells the model to answer `unsure` when it cannot place a claim. The prompt template delimits article text as data and tells the model to ignore instructions inside it; the output schema limits what a model can do to the listed classifications. The prompt includes at most 50 baseline claims, newest first; beyond that the claim records `unsure`.
9.  `delta_feed/application/claim_comparison.py` (Create). `compare_and_record(entity, claims, analysis_run, provider)` runs these steps:
    1. Read the entity's active baseline and its baseline version, the highest active claim id. If the baseline is empty, record every claim as `new` with `first_sighting` and stop.
    2. Run the deterministic tier per claim: fingerprint match, then `classify_claim_delta_with_match`.
    3. Outside any transaction, send the claims still undecided to the model in one call (one `compare` run); check the result against the consistency rules and the supplied baseline ids, and mark any claim that fails a check `unsure`.
    4. Open one `transaction.atomic`, lock the entity with `select_for_update`, and read the baseline version again.
    5. If it is unchanged, write the claims in extraction order through `record_claim` and stop. A claim whose fingerprint equals one already written from the same article is skipped, and so is a claim whose (`analysis_run`, `fingerprint`) already exists, so a retried job is safe.
    6. If it changed, leave the transaction and repeat from step 2 against the new baseline. Run at most two rounds; claims still undecided after the second round are recorded `unsure`.
    A model call that returns invalid output still writes its `compare` run, with `failure_reason` `invalid_output` and the validation error text in the run's `output`.
10. `delta_feed/analysis/use_cases.py` (Modify). Add `compare_run_job(payload)`: load a completed extraction run, split its output into mentions and claims, resolve mentions by name, store every mention through `queue_mentions`, call `compare_and_record` for the resolved ones, and set `AnalysisRun.compared_at` when every claim is written or recorded `unsure`. Add `compare_mention_group_job(payload)`: compare the claims of one run for the group's resolved mentions that have `compared_at` empty, call `generate_guide_proposals_for_entity(entity, that run)`, and set `compared_at` on those mentions. Inference outages raise for a durable retry, like `extract_article_job`. Enqueue an `analysis.compare` job at the end of a successful extraction. The deterministic tier needs no budget. When a claim needs a model call and the budget is spent, the job writes the claims it could decide, leaves the rest unwritten, returns `budget_exhausted` and leaves `compared_at` empty; `schedule_due_analysis` also enqueues compare jobs for completed extraction runs with `compared_at` empty, within the budget. `unanalysed_articles()` filters on `kind=extract`, and `record_run` takes `kind`; compare runs use schema `delta-feed.comparison.v1` with the comparison prompt and model versions.
11. `delta_feed/jobs/services.py` (Modify). Add these registry entries, and make `_lease_seconds` return the long extraction lease for both job types (each job handles one run, so the lease covers one run's model calls):

    | Job type (`JOB_TYPES`) | Handler name (`HANDLERS` key) | `module:function` value | Payload |
    |---|---|---|---|
    | `analysis.compare` | `analysis.compare_run` | `delta_feed.analysis.use_cases:compare_run_job` | `{run_id}` |
    | `analysis.compare_group` | `analysis.compare_mention_group` | `delta_feed.analysis.use_cases:compare_mention_group_job` | `{normalized_name, entity_type, analysis_run_id}` |

7a. `delta_feed/analysis/models.py` (Modify). Add `AnalysisRun.kind` (`extract` default, `compare`) and `AnalysisRun.compared_at` (nullable).
7b. `delta_feed/analysis/migrations/0006_analysisrun_kind.py` (Create). Generated with `makemigrations -n analysisrun_kind`.
9a. `delta_feed/core/claim_delta.py` (Modify). Add `classify_claim_delta_with_match` returning the classification and the matched claim (or none); `classify_claim_delta` becomes a wrapper so existing callers and tests keep working.
10a. `delta_feed/analysis/management/__init__.py`, `delta_feed/analysis/management/commands/__init__.py`, `delta_feed/analysis/management/commands/enqueue_comparisons.py` (Create). Enqueues `analysis.compare` for completed extraction runs with `compared_at` empty, and `analysis.compare_group` for resolved mentions with `compared_at` empty, so articles analysed before this change reach the baseline. `delta_feed/knowledge/api.py` (Modify): from this unit on, the resolve endpoint enqueues one `analysis.compare_group` job per analysis run in the group.

#### Unit 3: Delta and baseline APIs, landing preference

14. `delta_feed/accounts/models.py` (Modify). Add `landing_page` (`CharField(10)`, `feed` or `delta`, default `feed`) and `delta_banner_dismissed` (bool, default false) to `ReaderProfile`. `delta_feed/config/settings.py` and `.env.example` (Modify) add `BASELINE_READY_ANALYSED_PERCENT` (integer 0 to 100, default 80) and `BASELINE_READY_MIN_GUIDE_ENTITIES` (integer, default 1), both read with `_env_int` and provisional until trial data sets them.
15. `delta_feed/accounts/migrations/0004_readerprofile_landing_page.py` (Create). Generated with `makemigrations -n readerprofile_landing_page`.
16. `delta_feed/reader/baseline.py` (Create). `baseline_status(user)` computes `backfill_total` (articles with `is_backfill` true that have a current revision) and `backfill_analysed` (articles whose current revision's extraction run has `compared_at` set, or failed with invalid output; an article waiting on an outage does not count). It counts distinct entities of non-retired entries in non-archived guides, and passes only when both settings are met.
17. `delta_feed/reader/api.py` (Modify). Add `GET /delta`, `GET /baseline`, `POST /landing`. Extend the Feed item with `claim_counts` and up to five `duplicates` (claim text, matched claim text, matched article title) so a filtered article shows what matched, and with `pending_mentions` (the article's mentions with status `pending`). The Delta response also returns `pending_mentions` as `{ groups, articles }`: the number of distinct (`normalized_name`, `entity_type`) groups and of distinct articles that have pending mentions. Delta reads claims through the latest completed `extract` run of the current revision, excludes `duplicate`, and computes `also_covered_by` as defined in the Delta API response. Feed and Delta use only `extract` runs. The `/baseline` and `/landing` endpoints use `get_or_create` for the user's profile.
17a. `delta_feed/analysis/status.py` (Create) and `delta_feed/reader/api.py` (Modify, same change as item 17). Move `_current_run` and `_analysis_status` into the new module, filtered on `kind=extract`, so other code, such as a collector status endpoint, can share them without a circular import.

#### Unit 4: guide proposals

18. `delta_feed/guides/models.py` (Modify). Add `Status.SUPERSEDED`, `decided_at` (null) and `decision_source` (`manual`, `bulk`, `superseded`; blank until decided) on `GuideProposal`.
19. `delta_feed/guides/migrations/0006_proposal_supersession.py` (Create). Generated with `makemigrations -n proposal_supersession`.
20. `delta_feed/guides/use_cases.py` (Modify). Supersession runs inside both `get_or_create` paths: a newly created proposal marks older pending proposals for the same guide and target entry (or, for add proposals, the same guide and entity) as `superseded`, with `decided_at` and `decision_source` `superseded`. A `get_or_create` that returns an existing row supersedes nothing.
21. `delta_feed/guides/api.py` (Modify). Set `decided_at` and `decision_source` (`manual`) in `accept_proposal` and `reject_proposal`, and include both in their `update_fields`; include `decided_at` and `decision_source` in `GuideProposalOut`; add `POST /proposals/reject-older` (`RejectOlderIn`), which sets `decision_source` `bulk`; add an optional `guide_id` query parameter to `GET /proposals` that limits the list to one guide. Accept logic stays in the view because only a person triggers it in this release.

#### Unit 5: frontend

22. `frontend/src/lib/api/types.ts` (Modify). Add Delta, baseline and mention types and extend the Feed item.
22a. `frontend/src/lib/api/browser.ts` and `frontend/src/lib/api/server.ts` (Modify). Add calls for Delta, baseline, landing, mentions and bulk reject. Browser POSTs send the CSRF token the same way the existing mutations do.
23. `frontend/src/components/DeltaCard.astro` (Create). One card: original title and source, one bullet per claim with its classification label (New, Changed, Conflicts, Not sure), first-sighting marker, evidence quote, "also covered by N".
24. `frontend/src/pages/delta.astro` (Create). Lists cards with pagination. While articles await analysis it shows a message saying how many, with a link to Feed. When `pending_mentions.groups` is above zero it also shows a notice, "N names from M articles are waiting for review", linking to the mentions page.
25. `frontend/src/pages/mentions/index.astro` (Create) and `frontend/src/lib/mentions.ts` (Create). Review page for pending mention groups with link, create and dismiss actions; the helper builds the resolve payload.
26. `frontend/src/components/ReadinessBanner.astro` (Create). Shown on Feed when the baseline is ready, the landing page is `feed` and the banner is not dismissed; "Switch to Delta" and "Not now" post to `/api/reader/landing`.
27. `frontend/src/pages/index.astro` (Modify). Render one Feed list (all articles newest first, labelled "Feed") with an "Imported history" filter that reuses the existing `backfill` view, render the banner, and redirect to `/delta` when the stored landing page is `delta` and the request has no `view` parameter. The Today, Earlier and All tabs are removed: Feed replaces All and Earlier, and the Today budget returns on Delta with ranking during tuning. The "Feed" link in the navigation points to `/`. If the baseline call fails, render the Feed and no banner.
28. `frontend/src/components/ArticleCard.astro` (Modify). Show claim counts, the matched duplicates for filtered articles, and "N mentions waiting for review" when the article has pending mentions.
29. `frontend/src/layouts/SiteLayout.astro` (Modify). Add Delta and Names (the mentions page, with its pending group count) to the main navigation, and remove the "Discoveries" link to `/proposals`.
30. `frontend/src/pages/guides/index.astro`, `frontend/src/pages/guides/[id].astro`, `frontend/src/pages/proposals/index.astro` (Modify) and `frontend/src/lib/guides/types.ts` (Modify). The guides index shows each guide's pending proposal count (from `GET /api/guides/proposals`, grouped by `guide_id`) and the "Reject proposals older than N days" control. The guide page marks each entry that has a pending proposal (by `target_entry_id`) and shows "N proposed additions" for add proposals; both link to `/proposals?guide_id=<id>`. The proposals page keeps its approve and reject actions, reads `guide_id`, and is reached only from guides.

#### Unit 6: evaluation harness

32. `delta_feed/analysis/management/commands/evaluate_delta.py` (Create). Run as `cd backend && uv run python manage.py evaluate_delta <corpus_dir> <labels.jsonl>`, normally through the Makefile target in item 32a. It creates one `Source` named `evaluation` and one `Article` per corpus file (first line is the title, the rest is the body), orders files within a release group by file name, runs extraction and comparison against the configured model, matches each produced claim to a label by normalized entity name, predicate and value, and prints: claims classified correctly (by classification), share of mentions left pending, predicate drift (model comparisons whose matched claim has the same entity, scope and value but a different normalized predicate), and the repeated-release result (Delta cards produced from a labelled release group; pass when 2 or fewer of 10).
32a. `Makefile` (Modify). Add `evaluate-delta` (variables `CORPUS` and `LABELS`): it exports `DB_ENGINE=sqlite` and `SQLITE_PATH=<new temporary file>` for the command (settings read them at import), runs `migrate` on that file, runs `evaluate_delta`, then deletes the file.
33. `docs/baseline-corpus.md` (Modify). Document the label file format the command reads: one JSON Lines file with entries `{ article_file, claims: [ { entity, predicate, value, expected: new | duplicate | refinement | contradiction } ], release_group? }`. The same section describes the article file layout (first line title, rest body) and reconciles both with the existing corpus notes.

#### Unit 7: decision record and documentation

34. `docs/decisions/0011-mention-resolution-and-claim-comparison.md` (Create). ADR for unresolved-mentions-wait-for-review and the fingerprint-then-model comparison tiers, with the alternatives from this document.
35. `docs/architecture.md` (Modify). Add the mention queue and comparison tiers to the invariants, and the baseline-version recheck.
36. `docs/glossary.md` (Modify). Add mention, pending mention, fingerprint.
37. `docs/roadmap.md` (Modify). Record the unit order, the provisional readiness settings and the queue-size measurement.
38. `README.md` (Modify). Update Project status and local-development commands only after each unit's checks in the Verification Plan have passed and the manual browser check has been done.

### Verification Plan

Test waiver (confirmed by the author): new automated tests are out of scope for this phase, so locking is verified only by the manual PostgreSQL check below. Verification uses the commands below and the evaluation harness.

*   **Compilation/Build**: `make build-frontend` (Astro SSR build); `cd backend && DJANGO_DEBUG=true uv run python manage.py makemigrations --check` after each migration unit; `make typecheck-frontend` after the frontend unit.
*   **Existing suites**: `make test-backend` and `make test-frontend` must still pass. Update existing assertions only where this plan changes behaviour: backend `test_analysis_scheduling.py`, `test_extraction_use_case.py`, `test_claims_api.py`, `test_today_feed.py`, `test_reader_api.py`, `test_guide_proposals_api.py`, and frontend `contracts.test.ts`, `today-state.test.ts`. A test that cannot be updated in this phase stays red and is listed in the commit message.
*   **Static Analysis & Linting**: `make lint-backend` (ruff).
*   **Evaluation harness**: `make evaluate-delta CORPUS=<dir> LABELS=<file>` against a real configured model. Pass: claims classified correctly reported by classification, and 2 or fewer Delta cards from a labelled group of 10 articles on one release.
*   **Browser**: with the worker running, submit an article, resolve its pending mentions, see the Delta card, and see the banner once readiness passes.
*   **PostgreSQL concurrency (manual)**: start PostgreSQL, set `DB_ENGINE=postgresql` and the database variables defined in `config/settings.py`, run `migrate`, run two `run_worker` processes, and submit two articles that carry the same new claim at the same moment. Pass: exactly one of the two claims is `new` and the other is `duplicate`. SQLite does not honour the row locks, so this check cannot run there.

--------------------------------------------------------------------------------

*Drafted with EGM*
