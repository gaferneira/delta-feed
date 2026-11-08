Status: resolved (auto accept applied; Issue 4 escalated, Issues 30 and 32 declined)

# Goldfish Annotated Review Report

**Target:** `docs/designs/delta-feed-novelty-first-reading.md` (`lines 244..366`, Detailed Implementation Plan; lines 1..243 are context)

**Source findings:** the implementation readiness audit (Stage 9: 4 Blocker, 17 Major, 11 Nit; raw report not kept). The findings from Stages 5, 6, 7 and 8 (zoom-out, comprehension, critic and intermediate zoom-out reports; raw reports not kept) were not part of this resolution and remain unaddressed.

Summary of suggestions: 4 blockers (3 PROPOSE FIX, 1 ESCALATE), 20 majors (all PROPOSE FIX), 9 nits (7 PROPOSE FIX, 2 DECLINE). The source report's header says 17 majors and 11 nits, but it lists 20 and 9 findings under those severities; this report follows the findings as listed. No finding is contested.

## Prioritized Findings & AI Suggestions

### [Issue 1] [`egm-implementation-readiness`, `egm-codebase-details`] Extraction output never mapped to `record_claim` input - Severity: Blocker
*   **Affected Scope:** [Lines 282-294](docs/designs/delta-feed-novelty-first-reading.md#L282-L294) (Unit 1 and 2 items; Open Question at line 51)
*   **Discrepancy Description:** `record_claim` needs `claim_text`, one evidence span and flat scope fields. `ExtractedClaim` has `predicate`, `value`, a `scope` object, `confidence` and several evidence spans. The plan does not say how they map.
*   **Rationale:** The fingerprint and card text depend on this mapping, and the design lists it as an open question.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** The reviewers are right: `analysis/contracts/extraction.py` has no `claim_text`. The mapping is mechanical once the field choices are written down.
*   ***Proposed Edit:***
    *   Location: "Data and contract definitions" (add a bullet after `Claim` additions); delete the "Claim storage" Open Question (line 51).
    *   Change: Add "**Extraction to claim mapping**: `claim_text` is `"<predicate>: <value>"`; `predicate`, `value` and the scope fields are copied (missing scope stays null); the first evidence span of the claim is the stored evidence; `confidence` is not stored in this release; `observed_at` is the article's `source_published_at` when set, otherwise the analysis run's `completed_at`. Spans always lie inside the analysed text because `resolve_evidence` runs against the truncated prefix."

### [Issue 2] [`egm-implementation-readiness`, `egm-codebase-details`] `record_claim` override semantics and `supersedes` undefined - Severity: Blocker
*   **Affected Scope:** [Lines 264, 285, 286, 293](docs/designs/delta-feed-novelty-first-reading.md#L264-L293) (Unit 1 items 1 and 5, Unit 2 item 9)
*   **Discrepancy Description:** `record_claim` always runs the lexical classifier and sets `supersedes` only for lexical contradictions. The plan adds an override without defining it. `classify_claim_delta` returns no matched claim, and `core/claim_delta.py` is not in the file list.
*   **Rationale:** Without a rule, a contradicted claim stays in the active baseline.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. `knowledge/use_cases.py` lines 17-54 and `core/claim_delta.py` lines 39-62 confirm both gaps.
*   ***Proposed Edit:***
    *   Location: Unit 1 item 5; add a new file entry under Unit 2 for `delta_feed/core/claim_delta.py`.
    *   Change: Item 5 becomes "Extend `record_claim` with a keyword-only `decision` argument (classification, matched claim, method, model and prompt versions) plus `predicate` and `value`. When `decision` is given, the lexical classifier is skipped and the decision is stored. `supersedes` is set to the matched claim only for `contradiction`; `refinement` keeps both claims active." New entry: "`delta_feed/core/claim_delta.py` (Modify): add `classify_claim_delta_with_match` returning the classification and the matched claim (or none); `classify_claim_delta` becomes a wrapper so existing callers and tests keep working."

### [Issue 3] [`egm-implementation-readiness`, `egm-codebase-details`] Compare job has no budget, lease or job naming design - Severity: Blocker
*   **Affected Scope:** [Lines 293-296](docs/designs/delta-feed-novelty-first-reading.md#L293-L296) (Unit 2 items 9 to 12)
*   **Discrepancy Description:** `_budgeted_runs_today` counts `AnalysisRun` rows and the compare job creates none. `_lease_seconds` gives a long lease only to `analysis.extract`. Job types, handlers and payloads are unnamed.
*   **Rationale:** A slow compare call can outlive a 60-second lease and a second worker would rerun it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; confirmed in `analysis/use_cases.py` 104-111 and `jobs/services.py` 34-39. This is a design choice with alternatives (a new table versus reusing `AnalysisRun`). I propose reusing `AnalysisRun` so budget counting works unchanged; overrule in the interactive breakdown if you prefer a separate table.
*   ***Proposed Edit:***
    *   Location: Unit 2 items 10 to 12; Unit 2 gets one migration (update the units table).
    *   Change: Add `AnalysisRun.kind` (`extract` default, `compare`) in `analysis/models.py` with `analysis/migrations/0006_analysisrun_kind.py`. Each `compare_claims` model call writes one `compare` run with its results in `output`, so `ANALYSIS_DAILY_BUDGET` counts extraction runs and comparison calls together. Feed and Delta queries filter on `kind=extract`. Job types and handlers: `analysis.compare` to `analysis.compare_run` (payload `{run_id}`) and `analysis.compare_group` to `analysis.compare_mention_group` (payload `{normalized_name, entity_type}`). `_lease_seconds` returns the long extraction lease for both. Units table: Unit 2 migration is `analysis` 0006.

### [Issue 4] [`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`] No test plan - Severity: Blocker (Major if the waiver is accepted)
*   **Affected Scope:** [Lines 356-362](docs/designs/delta-feed-novelty-first-reading.md#L356-L362) (Verification Plan)
*   **Discrepancy Description:** New automated tests are out of scope with no named tests, yet the plan has concurrency- and security-critical code. ADR 0010 requires concurrency tests on PostgreSQL. Existing tests that will break are not named.
*   **Rationale:** The standard treats a missing test plan as a Blocker.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** The reviewers could not see `CLAUDE.local.md`, where the owner says not to focus on tests in this phase. That is a decision outside every file they read, so the severity is not mine to change and the waiver is yours to confirm. The parts that stand regardless are handled in Issue 5's edit: name the existing tests that need updates and give the PostgreSQL concurrency check a command and pass criterion.
*   ***Proposed Edit:***
    *   Location: Verification Plan, "Unit Tests" bullet.
    *   Change: If you confirm the waiver, add: "Test waiver: new tests are deferred by the author for this phase (see `CLAUDE.local.md`); locking is therefore verified only by the PostgreSQL run below." Add the existing tests to update: `backend/tests/integration/test_analysis_scheduling.py`, `test_extraction_use_case.py`, `test_reader_api.py`, `test_guide_proposals_api.py`, `test_claims_api.py`, and frontend `tests/contracts.test.ts`, `tests/today-state.test.ts`.

### [Issue 5] [`egm-implementation-readiness`, `egm-codebase-details`] Baseline recheck mechanism undefined - Severity: Major
*   **Affected Scope:** [Lines 293-294](docs/designs/delta-feed-novelty-first-reading.md#L293-L294)
*   **Discrepancy Description:** "Baseline did not change" has no detection rule, and the lock and transaction structure is unspecified.
*   **Rationale:** Without a rule the recheck can be skipped or done twice.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. A single rule is enough.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 9.
    *   Change: Add "The baseline version is the highest active claim id for the entity, read before the model call and again inside the transaction after `select_for_update`. `compare_and_record` opens one outer `transaction.atomic`; the per-claim writes inside it reuse the same lock. Claims for one entity from one article are written in extraction order so each sees the earlier ones."

### [Issue 6] [`egm-implementation-readiness`, `egm-codebase-details`] Job idempotency and retry unspecified - Severity: Major
*   **Affected Scope:** [Lines 285, 293-294](docs/designs/delta-feed-novelty-first-reading.md#L285-L294)
*   **Discrepancy Description:** A retried compare job can duplicate `ExtractedMention` and `Claim` rows.
*   **Rationale:** Retries are part of the job design (backoff on outages).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. `Claim` is append-only, so duplicates cannot be cleaned up.
*   ***Proposed Edit:***
    *   Location: Unit 1 items 1 and 4; Unit 2 item 10.
    *   Change: `ExtractedMention` gets a unique constraint on (`analysis_run`, `ref`). `Claim` gets a unique constraint on (`analysis_run`, `fingerprint`) where the fingerprint is not null. `compare_run_job` skips claims whose (`analysis_run`, `fingerprint`) already exists.

### [Issue 7] [`egm-implementation-readiness`, `egm-codebase-details`] Published-date ordering cannot be implemented - Severity: Major
*   **Affected Scope:** [Lines 122, 289-294](docs/designs/delta-feed-novelty-first-reading.md#L289-L294)
*   **Discrepancy Description:** The ordering rule needs a batch, but `compare_run_job` handles one run and nothing orders comparisons across articles.
*   **Rationale:** "First reported by X" can be wrong.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Of the two fixes (a batching mechanism or dropping the guarantee), dropping it is the smaller, honest change for this release; the existing `matched_claim` link still records who was first by analysis order.
*   ***Proposed Edit:***
    *   Location: Technical Plan section 4, bullet "Within one extraction batch..."; Unit 2 item 10; Open Question "Tie-breaking for credit".
    *   Change: Replace with "Credit goes to the first article compared. A later duplicate points at that claim through `matched_claim`, and the card shows its source and publication date, so a reader can see when the first article was published later than the duplicate. Ordering comparisons by publication date across articles is deferred." Remove "in published-date order" from item 10.

### [Issue 8] [`egm-implementation-readiness`] Existing completed runs and rollout path - Severity: Major
*   **Affected Scope:** [Line 294](docs/designs/delta-feed-novelty-first-reading.md#L294)
*   **Discrepancy Description:** Compare is enqueued only after a successful extraction, so already-completed runs and the backfill never get claims, while readiness counts them as analysed.
*   **Rationale:** Readiness would pass with an empty baseline.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Readiness must count articles with comparison done.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 10; Unit 3 item 16.
    *   Change: Add a management command `enqueue_comparisons` (in `delta_feed/analysis/management/commands/`) that enqueues `analysis.compare` for completed extraction runs with no compare run. `baseline_status` counts a backfilled article as analysed only when its current revision has a completed `compare` run.

### [Issue 9] [`egm-implementation-readiness`, `egm-codebase-details`] Mention resolution and candidate generation underspecified - Severity: Major
*   **Affected Scope:** [Lines 106, 263, 269, 284-287](docs/designs/delta-feed-novelty-first-reading.md#L284-L287)
*   **Discrepancy Description:** `match_or_suggest_entities` returns nothing for a mention (no identifiers, no embedding), so the review page has no candidates. Alias matching on a JSON list is not portable, duplicate names are unhandled, and `create` has no payload.
*   **Rationale:** The review page is the only way a mention reaches the baseline.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; also answers Stage 6's finding on the similarity score.
*   ***Proposed Edit:***
    *   Location: Technical Plan section 2; Mentions API definition; Unit 1 items 4 and 6.
    *   Change: Group key is (`normalized_name`, `entity_type`). Resolution scans entities in Python (the table is small) comparing the normalized name with `Entity.name` and each alias; one hit with the same type resolves, several hits leave the mention pending. Candidates are entities whose normalized name contains or is contained by the mention's name, ordered by length difference; `similarity` is removed from the API. `create` takes `{ name, entity_type, canonical_url? }` defaulting to the mention's name and type. Every mention is stored as an `ExtractedMention` row, with status `resolved` when matched automatically, so counts are consistent. Dismissal is stored as status `dismissed` on the group's mentions and checked by (`normalized_name`, `entity_type`).

### [Issue 10] [`egm-implementation-readiness`, `egm-codebase-details`] Model fields lack types, defaults and nullability - Severity: Major
*   **Affected Scope:** [Lines 264, 272-275](docs/designs/delta-feed-novelty-first-reading.md#L264-L275)
*   **Discrepancy Description:** New enum fields on `ArticleRevision` have no default for existing rows, writers are not listed, and field types and relations are missing.
*   **Rationale:** A blanket migration default would mislabel RSS revisions.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: "Data and contract definitions".
    *   Change: `ArticleRevision.received_via` is a `CharField(max_length=20)` with default `manual`, and the migration sets `rss` for revisions of articles that have a source; `completeness` default `unknown`; `source_revision_id` (255), `extraction_method` (80) blank allowed; `source_modified_at`, `observed_at` nullable. `Claim.matched_claim` is a nullable self FK with `on_delete=PROTECT` and `related_name="matched_by"`; `comparison_method` default `manual`; `fingerprint` is `CharField(max_length=64, null=True, db_index=True)`. The fingerprint joins parts with a `|` separator and writes an empty string for a missing scope value. Add `content/api.py`, `content/rss.py` and `content/revisions.py` to the file list as writers that set `received_via`.

### [Issue 11] [`egm-implementation-readiness`, `egm-codebase-details`] Collector ingestion design gaps - Severity: Major
*   **Affected Scope:** [Lines 148-156, 276, 342-350](docs/designs/delta-feed-novelty-first-reading.md#L342-L350)
*   **Discrepancy Description:** `topic_hints` has no storage, the idempotency fingerprint inputs are undefined, replay status code and rate-limit key are unstated, `observe_article` does not follow `submit_article`'s updates, the status endpoint reuses private Feed helpers, and the second API needs a name and namespace. Collector sources would also appear on the Sources page with a blank RSS URL.
*   **Rationale:** An implementer would need to guess each of these.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Several of these also support the Stage 5 and 8 view that the collector API is a separate feature; this fix keeps it in scope as you decided.
*   ***Proposed Edit:***
    *   Location: Technical Plan section 9; Unit 8 items 42 to 47.
    *   Change: `topic_hints` are validated against existing topic ids (422 on unknown ids) and stored on the receipt as a JSON list, not used further in this release. `request_fingerprint` hashes source key, url, title, body, completeness, `source_revision_id` and `source_modified_at` and excludes `observed_at` and the idempotency key. A replay returns 200 with the existing receipt; a first acceptance returns 202. The rate limit is keyed on the credential id with a 60-second window. `observe_article` reuses `article_content_hash`, `safe_http_url` and the same article updates as `submit_article`, and caps `external_id` at 512. Shared analysis-status logic moves from `reader/api.py` into a new `delta_feed/analysis/status.py` that both routers import. The second API is named `collector_api` with `urls_namespace="collector"`. `GET /api/content/sources` lists only sources that have an RSS feed URL.

### [Issue 12] [`egm-codebase-details`, `egm-implementation-readiness`, `egm-style`] Body-size cap unit and enforcement undefined - Severity: Major
*   **Affected Scope:** [Lines 345, 348, 350](docs/designs/delta-feed-novelty-first-reading.md#L345-L350)
*   **Discrepancy Description:** The cap counts characters but "before parsing" implies bytes, and Django does not return 413 by itself.
*   **Rationale:** The contract asks for finite byte and text limits.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Technical Plan section 9 "Limits"; Unit 8 item 48.
    *   Change: "Two checks: the view reads `Content-Length` and returns 413 above `COLLECTOR_MAX_REQUEST_BYTES` (default 1,500,000) before reading the body; after parsing, a body longer than `COLLECTOR_MAX_BODY_CHARS` (300,000 characters) returns 413 as well."

### [Issue 13] [`egm-codebase-details`, `egm-style`] New settings underspecified - Severity: Major
*   **Affected Scope:** [Lines 270, 296, 348, 350](docs/designs/delta-feed-novelty-first-reading.md#L270-L350)
*   **Discrepancy Description:** `BASELINE_READY_ANALYSED_SHARE` is a fraction but `_env_int` accepts only non-negative integers. Types and defaults are missing for the other new settings.
*   **Rationale:** The settings module would raise on a float.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; `config/settings.py` lines 17-24.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 12; Unit 8 item 48.
    *   Change: Use integer percent: `BASELINE_READY_ANALYSED_PERCENT` (default 80, range 0-100) and `BASELINE_READY_MIN_GUIDE_ENTITIES` (default 1), both parsed with `_env_int`. `COLLECTOR_RATE_LIMIT_PER_MINUTE` is an integer, default 60. `older_than_days` is an integer of at least 1. All defaults are provisional until trial data sets them.

### [Issue 14] [`egm-implementation-readiness`, `egm-codebase-details`] Frontend API client files missing from the allowlist - Severity: Major
*   **Affected Scope:** [Lines 313-323](docs/designs/delta-feed-novelty-first-reading.md#L313-L323)
*   **Discrepancy Description:** New calls need functions in `lib/api/browser.ts` and `server.ts`; CSRF handling, the SSR failure path and the default-view change are unspecified.
*   **Rationale:** The Feed page's existing "Today" links and empty states would break.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 5 (add entries).
    *   Change: Add `frontend/src/lib/api/browser.ts` and `frontend/src/lib/api/server.ts` (Modify: add Delta, baseline, landing, mentions and bulk-reject calls; browser POSTs send the CSRF token the same way existing mutations do). Item 27 adds "if the baseline call fails, `index.astro` renders the Feed and shows no banner". Item 27 also says: the default view is `all` labelled "Feed"; the "Today" tab stays; "Back to Today" links and the Today empty state remain on the Today view only.

### [Issue 15] [`egm-implementation-readiness`, `egm-codebase-details`] Delta API details - Severity: Major
*   **Affected Scope:** [Lines 267-268, 301-304](docs/designs/delta-feed-novelty-first-reading.md#L267-L304)
*   **Discrepancy Description:** No item ordering, no rule for several runs on one revision, no schemas for `claim_counts` and `duplicates`, no scoping of guide entities, and no `ReaderProfile` creation rule.
*   **Rationale:** Two implementers would build different responses.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Delta API response definition; Unit 3 items 16 and 17.
    *   Change: Items are ordered by article publication time (falling back to discovery time), newest first. Only `kind=extract` runs are used; claims are read through the latest completed extraction run of the current revision. `claim_counts` is `{ new, refinement, contradiction, unsure, duplicate }` (integers); each `duplicates` entry is `{ claim_text, matched_claim_text, matched_article_title }`, at most five. `baseline_status` counts distinct entities of non-retired entries in non-archived guides. `/baseline` and `/landing` use `get_or_create` for the user's `ReaderProfile`. `/landing` accepts exactly one of the two fields (422 otherwise) and returns the new `{ landing_page, banner_dismissed }`.

### [Issue 16] [`egm-implementation-readiness`, `egm-codebase-details`] Guide proposal supersession and generator caller - Severity: Major
*   **Affected Scope:** [Lines 133, 253, 286, 310](docs/designs/delta-feed-novelty-first-reading.md#L133-L310)
*   **Discrepancy Description:** The design says the compare job gives the generator a production caller, but `generate_guide_update_proposals_for_claim` is already called from `record_claim`, while `generate_guide_proposals_for_entity` has no caller. Supersession placement and decision data are unspecified.
*   **Rationale:** The statement is inaccurate as written and the plan has no step that wires the entity generator.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; confirmed in `knowledge/use_cases.py` (the hook inside `record_claim`).
*   ***Proposed Edit:***
    *   Location: Technical Plan section 6; Unit 4 items 18 to 21.
    *   Change: Section 6 now says "Update, warning and retire proposals are generated through `record_claim`, which the compare job calls. `generate_guide_proposals_for_entity` (add proposals) is called when a mention group is resolved to an entity." Item 20: supersession runs inside both `get_or_create` paths in `guides/use_cases.py`; a newly created proposal supersedes older pending ones for the same guide and target entry (or guide and entity for add proposals), and a repeated `get_or_create` that returns an existing row supersedes nothing. Superseded rows get `decided_at`. Add `decision_source` (`manual`, `bulk`, `superseded`) on `GuideProposal` so ADR 0009's decision data can tell them apart (same migration, `guides` 0006).

### [Issue 17] [`egm-codebase-details`, `egm-implementation-readiness`, `egm-style`] Comparison contract details - Severity: Major
*   **Affected Scope:** [Lines 120, 262-266, 283, 291-292](docs/designs/delta-feed-novelty-first-reading.md#L262-L292)
*   **Discrepancy Description:** Ids "drawn from the supplied baseline" cannot be enforced by strict model validation, `claim_index` has no base, classification and `matched_claim_id` have no consistency rules, the prompt has no size cap, and `comparison_method` lists differ (five versus four values).
*   **Rationale:** The adapters call `model_validate_json` with no context.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; `analysis/adapters/ollama.py` and `openai_compatible.py` validate without context.
*   ***Proposed Edit:***
    *   Location: Technical Plan section 3; comparison output schema definition; Unit 2 items 7 to 9.
    *   Change: `claim_index` is zero-based. After model validation, `compare_and_record` checks that every `matched_claim_id` is one of the supplied baseline ids; a failure records `unsure` with the error in the run output. Consistency rules: `duplicate`, `refinement` and `contradiction` require a non-null `matched_claim_id`; `new` and `unsure` require null. The prompt includes at most 50 baseline claims, newest first; beyond that the claim records `unsure`. The `comparison_method` list is `fingerprint`, `lexical`, `model`, `first_sighting`, `manual` everywhere; `manual` is written by `knowledge/api.py` `create_claim` (add it to the file list).

### [Issue 18] [`egm-codebase-details`, `egm-implementation-readiness`, `egm-style`] Evaluation harness and corpus format undefined - Severity: Major
*   **Affected Scope:** [Lines 36, 325-329, 362](docs/designs/delta-feed-novelty-first-reading.md#L325-L362)
*   **Discrepancy Description:** The label format is deferred to a doc edit, `local-corpus/` holds no claim-level labels, the throwaway database and command usage are unspecified, "fingerprint-near" has no meaning for a SHA-256 hash, and "at most about 2 cards" is not a measurable threshold.
*   **Rationale:** The success target cannot be checked.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Goals (success target); Unit 6 items 32 and 33; Verification Plan.
    *   Change: Labels are one JSON Lines file per corpus: `{ article_file, claims: [ { entity, predicate, value, expected: new|duplicate|refinement|contradiction } ], release_group? }`. The command is `uv run python manage.py evaluate_delta <corpus_dir> <labels.jsonl>`; it creates a temporary SQLite database through `DB_ENGINE=sqlite` and `SQLITE_PATH` set to a temp file, and deletes it afterwards. The repeated-release pass criterion is an integer: in a group of 10 articles on one release, 2 or fewer produce a Delta card. Predicate drift is counted as model comparisons whose matched claim has the same entity, scope and value but a different normalized predicate.

### [Issue 19] [`egm-style`, `egm-implementation-readiness`, `egm-codebase-details`] Unit order contradiction - Severity: Major
*   **Affected Scope:** [Lines 246, 259](docs/designs/delta-feed-novelty-first-reading.md#L246-L259)
*   **Discrepancy Description:** Line 246 says every unit depends on the ones before it, line 259 says Unit 8 can be built first. Units 2 and 8 both edit `config/settings.py` and `.env.example`, and `BASELINE_READY_*` is added in Unit 2 but first used in Unit 3.
*   **Rationale:** An implementer cannot tell the build order.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Line 246; Unit 2 item 12 and 13; Unit 8 items 48 and 49.
    *   Change: Line 246 becomes "Units 1 to 7 depend on the ones before them; Unit 8 is independent and can be built first." Move the `BASELINE_READY_*` settings from Unit 2 to Unit 3. Each unit edits `config/settings.py` and `.env.example` only for its own settings.

### [Issue 20] [`egm-style`] Normalisation rules inconsistent - Severity: Major
*   **Affected Scope:** [Lines 104, 265, 284, 285](docs/designs/delta-feed-novelty-first-reading.md#L104-L285)
*   **Discrepancy Description:** Three places describe normalization differently, and `normalize_text` and `normalize_name` are not distinguished.
*   **Rationale:** Matching results would depend on which description the implementer reads.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Data and contract definitions (fingerprint bullet); Technical Plan section 2; Unit 1 items 3 and 4.
    *   Change: Define once: "`normalize_text`: lowercase, collapse whitespace, strip trailing punctuation. `normalize_name`: `normalize_text` applied to entity names and aliases, and to the mention name before comparing. Stored `Entity.name` and aliases are normalized at comparison time, not rewritten." Other places refer to these two functions by name.

### [Issue 21] [`egm-style`] `kind` vs `classification` naming - Severity: Major
*   **Affected Scope:** [Lines 120, 264-267, 316](docs/designs/delta-feed-novelty-first-reading.md#L264-L316)
*   **Discrepancy Description:** One concept has two names, and the UI labels are not mapped to model values.
*   **Rationale:** Readers will not know whether `kind` and `classification` are the same field.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; also resolves Stage 6's finding on the same mapping.
*   ***Proposed Edit:***
    *   Location: Delta API response; Unit 5 item 23.
    *   Change: Rename `kind` to `classification` in the API and add the mapping: "`new` is shown as New, `refinement` as Changed, `contradiction` as Conflicts, `unsure` as Not sure."

### [Issue 22] [`egm-codebase-details`, `egm-implementation-readiness`] Verification commands omit required env and checks - Severity: Major
*   **Affected Scope:** [Lines 358-362](docs/designs/delta-feed-novelty-first-reading.md#L358-L362)
*   **Discrepancy Description:** `makemigrations --check` fails without `DJANGO_DEBUG=true`, `make typecheck-frontend` is not run, and the e2e line does not pair outcomes with cases.
*   **Rationale:** The literal command in the plan would fail.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; `config/settings.py` lines 34-40.
*   ***Proposed Edit:***
    *   Location: Verification Plan.
    *   Change: Use `cd backend && DJANGO_DEBUG=true uv run python manage.py makemigrations --check`; add `make typecheck-frontend`; write each e2e outcome as case then result (for example "revoked token: 401; source outside the credential's set: 403").

### [Issue 23] [`egm-codebase-details`] Migration names are placeholders - Severity: Major
*   **Affected Scope:** [Lines 278, 283, 302, 309, 342](docs/designs/delta-feed-novelty-first-reading.md#L278-L342)
*   **Discrepancy Description:** Migration files use `<generated name>`, so the allowlist has no exact paths.
*   **Rationale:** Item 2 of the standard asks for exact paths.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid and cheap.
*   ***Proposed Edit:***
    *   Location: Unit 1, 2, 3, 4, 8 migration entries.
    *   Change: Pin names with `makemigrations -n`: `knowledge/migrations/0005_mentions_and_claim_comparison.py`, `analysis/migrations/0006_analysisrun_kind.py`, `accounts/migrations/0004_readerprofile_landing_page.py`, `guides/migrations/0006_proposal_supersession.py`, `content/migrations/0007_collector_ingestion.py`.

### [Issue 24] [`egm-codebase-details`, `egm-style`] `manage_collectors` credential details - Severity: Major
*   **Affected Scope:** [Lines 272, 343, 347](docs/designs/delta-feed-novelty-first-reading.md#L272-L347)
*   **Discrepancy Description:** `created_by` is a required user FK but `create-credential` has no way to pick a user, and the token format is vague.
*   **Rationale:** The command cannot run as specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 8 items 41 and 47.
    *   Change: `create-credential` takes `--user <username>` (default: the only user when exactly one exists, otherwise an error). The token is 32 random bytes encoded URL-safe base64 (`secrets.token_urlsafe(32)`); `token_prefix` is its first 8 characters; the stored hash is the SHA-256 hex digest.

### [Issue 25] [`egm-codebase-details`] Step 50 omits contract departures - Severity: Nit
*   **Affected Scope:** [Lines 150, 154, 352](docs/designs/delta-feed-novelty-first-reading.md#L352)
*   **Discrepancy Description:** The narrowing list omits that no ingestion job is created and that status stages are named `delta` instead of `publication`.
*   **Rationale:** The contract and the design differ silently.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Cheap and accurate.
*   ***Proposed Edit:***
    *   Location: Unit 8 item 50.
    *   Change: Append "no ingestion job is created (analysis is scheduled by the worker's existing loop) and the third status stage is `delta`, not `publication`."

### [Issue 26] [`egm-style`] Ambiguous budget counting wording - Severity: Nit
*   **Affected Scope:** [Line 296](docs/designs/delta-feed-novelty-first-reading.md#L296)
*   **Discrepancy Description:** "A run that reaches the model counts once" has several readings.
*   **Rationale:** The counted unit is unclear.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Covered by Issue 3's edit; the sentence is replaced.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 12.
    *   Change: Replace with "Each model call to extraction or `compare_claims` counts as one against `ANALYSIS_DAILY_BUDGET`; provider outages do not count."

### [Issue 27] [`egm-implementation-readiness`] Mentions and reject-older endpoint schemas unnamed - Severity: Nit
*   **Affected Scope:** [Lines 270, 287](docs/designs/delta-feed-novelty-first-reading.md#L270-L287)
*   **Discrepancy Description:** Schema names are not given for `/mentions`, and the reject-older route has no stated conflict with `/proposals/{id}/accept|reject`.
*   **Rationale:** Minor ambiguity.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Cheap.
*   ***Proposed Edit:***
    *   Location: Unit 1 item 6; Unit 4 item 21.
    *   Change: Name `MentionGroupOut`, `MentionResolveIn`, `RejectOlderIn`. State that `POST /proposals/reject-older` is a literal path and is registered before the `{proposal_id}` routes.

### [Issue 28] [`egm-style`] Undefined terms - Severity: Nit
*   **Affected Scope:** [Lines 129, 303, 320, 321](docs/designs/delta-feed-novelty-first-reading.md#L129-L321)
*   **Discrepancy Description:** "settled run", "Today and backfill views" and "waiting state" are used without definition.
*   **Rationale:** A reader cannot tell what they mean.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Cheap, and it also answers Stage 6 findings 9 and 11.
*   ***Proposed Edit:***
    *   Location: Unit 3 item 16; Unit 5 items 24 and 27.
    *   Change: "settled run" becomes "completed extraction run"; "waiting state" becomes "a message that says how many articles await analysis, with a link to Feed"; "Today and backfill views" gets "the existing Feed views that list recent articles and imported history".

### [Issue 29] [`egm-style`] "units have been run" wording - Severity: Nit
*   **Affected Scope:** [Line 338](docs/designs/delta-feed-novelty-first-reading.md#L338)
*   **Discrepancy Description:** Units are built, not run.
*   **Rationale:** Wording.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** One-word fix.
*   ***Proposed Edit:***
    *   Location: Unit 7 item 38.
    *   Change: "after the units have been run" becomes "after the units are implemented and exercised".

### [Issue 30] [`egm-style`] Repeated "single migration" phrase - Severity: Nit
*   **Affected Scope:** [Lines 283, 302, 309, 342](docs/designs/delta-feed-novelty-first-reading.md#L283-L342)
*   **Discrepancy Description:** The same sentence appears four times.
*   **Rationale:** Repetition.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Harmless, and Issue 23's edit rewrites those four entries anyway.
*   ***Proposed Edit:***
    *   Location: n/a
    *   Change: None.

### [Issue 31] [`egm-style`] Item 9 overlong - Severity: Nit
*   **Affected Scope:** [Line 293](docs/designs/delta-feed-novelty-first-reading.md#L293)
*   **Discrepancy Description:** One sentence chain with more than six clauses.
*   **Rationale:** Hard to read.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Worth doing; Issues 5, 6 and 17 also change this item.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 9.
    *   Change: Rewrite as five numbered steps in the order of Technical Plan section 4: read baseline; run deterministic tier; call the model for the rest; open the transaction and lock; recheck and write.

### [Issue 32] [`egm-style`] Redundant coverage line and heading reuse - Severity: Nit
*   **Affected Scope:** [Lines 359, 361](docs/designs/delta-feed-novelty-first-reading.md#L359-L361)
*   **Discrepancy Description:** "Test Coverage Requirement: None" repeats the waiver sentence, and "Unit Tests" also heads the existing suites.
*   **Rationale:** Redundant.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** The template requires the Verification Plan bullets, and Issue 4's decision determines their final wording.
*   ***Proposed Edit:***
    *   Location: n/a
    *   Change: None.

### [Issue 33] [`egm-style`] Absolute prompt-safety claim unchecked - Severity: Nit
*   **Affected Scope:** [Line 292](docs/designs/delta-feed-novelty-first-reading.md#L292)
*   **Discrepancy Description:** "Article text is passed as quoted data, never as instructions" has no check.
*   **Rationale:** An absolute claim with no verification.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; models can still follow injected text, so the claim is too strong.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 8.
    *   Change: Replace with "the prompt template delimits article text as data and tells the model to ignore instructions inside it; the output schema limits what a model can do to the listed classifications."
