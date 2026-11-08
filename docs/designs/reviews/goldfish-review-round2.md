Status: resolved (auto accept applied: all 30 findings)

# Goldfish Annotated Review Report (Round 2)

**Target:** `docs/designs/delta-feed-novelty-first-reading.md` (`lines 242..378`)

**Source findings:** the round 2 implementation readiness audit (0 Blocker, 17 Major, 13 Nit; raw report not kept). This report is separate from `goldfish-review-round1.md` so both resolution records stay. The re-audit cap is reached, so no further reviewer round runs after these edits.

Summary of suggestions: 17 majors and 13 nits, all PROPOSE FIX. No finding is contested or escalated. Issue 8 repeats the test-waiver topic that round 1 escalated (Issue 4 there, still open); the edit below stays inside the waiver and only names tests and a manual check.

Four fixes remove problems my round-1 edits created or exposed: M1 (a compare run per model call only), M2 (`kind` filtering), M5 (a job enqueued before it exists) and M17 (Unit 8 independence).

## Prioritized Findings & AI Suggestions

### [Issue 1] [`egm-implementation-readiness`, `egm-codebase-details`] M1 Compare run missing when no model call is made - Severity: Major
*   **Affected Scope:** [Lines 274, 293-295, 306, 312, 327](docs/designs/delta-feed-novelty-first-reading.md#L274-L327)
*   **Discrepancy Description:** A `compare` run exists only per model call. Articles decided without a model call never count as analysed, and `enqueue_comparisons` re-enqueues them on every run.
*   **Rationale:** Readiness and the "awaiting analysis" message would stay wrong.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid, and caused by my round-1 edits for Issues 3 and 8. A durable marker on the extraction run is simpler than a compare run per job.
*   ***Proposed Edit:***
    *   Location: `AnalysisRun.kind` definition; Unit 2 items 7a, 10, 10a; Unit 3 item 16.
    *   Change: Add `AnalysisRun.compared_at` (nullable) to the same `analysis` 0006 migration. `compare_run_job` sets it on the extraction run when all its claims are written or recorded `unsure`. `compare` runs still exist only for budget counting per model call. `enqueue_comparisons` selects completed extraction runs with `compared_at` null. `baseline_status` counts an article as analysed when its current revision's extraction run has `compared_at` set.

### [Issue 2] [`egm-implementation-readiness`, `egm-codebase-details`] M2 `AnalysisRun.kind` filtering and `record_run` incomplete - Severity: Major
*   **Affected Scope:** [Lines 274, 298, 305, 313, 361](docs/designs/delta-feed-novelty-first-reading.md#L274-L361)
*   **Discrepancy Description:** Only the Feed and Delta queries are told to filter `kind=extract`. `unanalysed_articles()`, `_current_run` and `_analysis_status` are not covered, `analysis/status.py` is missing from Unit 3, and `record_run` has no `kind` parameter.
*   **Rationale:** A failed compare run would mark an article as failed in the reader.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: `AnalysisRun.kind` definition; Unit 2 item 10; Unit 3.
    *   Change: "`unanalysed_articles()` and the analysis-status helpers filter on `kind=extract`; `_budgeted_runs_today` stays unfiltered so comparison calls count. `record_run` takes `kind`; compare runs use schema `delta-feed.comparison.v1` and the comparison prompt and model versions." Add `delta_feed/analysis/status.py` (Create) and `delta_feed/analysis/use_cases.py` (Modify) to Unit 3 (see Issue 17).

### [Issue 3] [`egm-implementation-readiness`] M3 Model call inside the transaction - Severity: Major
*   **Affected Scope:** [Lines 292, 297](docs/designs/delta-feed-novelty-first-reading.md#L292-L297)
*   **Discrepancy Description:** Step 5 says undecided claims "get one more model call (steps 3 to 4)", which reads as a model call under the entity lock and contradicts the design.
*   **Rationale:** The architecture forbids holding a transaction open across a model call.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; my wording was ambiguous.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 9, steps 4 and 5.
    *   Change: Rewrite as a loop: "Repeat at most twice: read the baseline version; run the deterministic tier and, outside any transaction, the model call for undecided claims; then open `transaction.atomic`, lock the entity and read the baseline version again. If unchanged, write the claims and stop. If changed, leave the transaction and repeat. After two rounds, record still-undecided claims as `unsure`."

### [Issue 4] [`egm-implementation-readiness`, `egm-codebase-details`] M4 Group compare and group resolution undefined across runs - Severity: Major
*   **Affected Scope:** [Lines 284, 286, 298](docs/designs/delta-feed-novelty-first-reading.md#L284-L298)
*   **Discrepancy Description:** There is no "resolved but not yet compared" marker on `ExtractedMention`, `resolved_at` is set for auto-matches too, and `compare_and_record` and `generate_guide_proposals_for_entity` take one run while a group spans several runs.
*   **Rationale:** Re-running a group would repeat comparisons.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: `ExtractedMention` definition; Unit 1 item 4; Unit 2 item 10.
    *   Change: Add `compared_at` (nullable) to `ExtractedMention`. Resolving a group enqueues one `analysis.compare_group` job per analysis run in the group, payload `{normalized_name, entity_type, analysis_run_id}`. The job compares that run's claims for the group's resolved mentions with `compared_at` null, calls `generate_guide_proposals_for_entity(entity, that run)`, and sets `compared_at` on those mentions.

### [Issue 5] [`egm-implementation-readiness`] M5 Unit 1 enqueues a job that is not yet registered - Severity: Major
*   **Affected Scope:** [Lines 248, 250, 286, 298, 299](docs/designs/delta-feed-novelty-first-reading.md#L248-L299)
*   **Discrepancy Description:** `knowledge/api.py` enqueues `analysis.compare_group` in Unit 1, but registration and the handler arrive in Unit 2, so `enqueue_job` raises after Unit 1 alone.
*   **Rationale:** Unit 1 would not work when built alone.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; caused by my Issue 9 edit in round 1.
*   ***Proposed Edit:***
    *   Location: Unit 1 item 6; Unit 2 item 10a.
    *   Change: In Unit 1, resolving a group only marks mentions resolved and does not enqueue. In Unit 2, `enqueue_comparisons` also selects resolved mentions with `compared_at` null, and the resolve endpoint starts enqueueing group jobs.

### [Issue 6] [`egm-codebase-details`] M6 Registry keys unclear - Severity: Major
*   **Affected Scope:** [Lines 298-299](docs/designs/delta-feed-novelty-first-reading.md#L298-L299)
*   **Discrepancy Description:** `HANDLERS` is keyed by handler name with `module:function` values and `JOB_TYPES` maps type to handler name; the plan names only types. `_lease_seconds` matches only the string `"analysis.extract"`.
*   **Rationale:** The registry entries cannot be written from the text.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; also covers N9 (job name table).
*   ***Proposed Edit:***
    *   Location: Unit 2 items 10 and 11.
    *   Change: Replace the prose with a table: `JOB_TYPES["analysis.compare"] = "analysis.compare_run"`, `HANDLERS["analysis.compare_run"] = "delta_feed.analysis.use_cases:compare_run_job"`, payload `{run_id}`; `JOB_TYPES["analysis.compare_group"] = "analysis.compare_mention_group"`, `HANDLERS["analysis.compare_mention_group"] = "delta_feed.analysis.use_cases:compare_mention_group_job"`, payload `{normalized_name, entity_type, analysis_run_id}`. `_lease_seconds` returns the long lease for both job types; each job handles one run, so the lease covers one run's model calls.

### [Issue 7] [`egm-implementation-readiness`, `egm-codebase-details`] M7 `evaluate_delta` database switch cannot work as written - Severity: Major
*   **Affected Scope:** [Line 338](docs/designs/delta-feed-novelty-first-reading.md#L338)
*   **Discrepancy Description:** `config/settings.py` reads `DB_ENGINE` and `SQLITE_PATH` at import, so a running command cannot switch databases. Label loading, claim matching, ordering and reconciliation with `docs/baseline-corpus.md` are unstated.
*   **Rationale:** The harness cannot run as described.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the round-1 fix was incomplete. I could not read the contents of `local-corpus/articles`, so the article file format below is a new convention, to be reconciled in the same doc edit.
*   ***Proposed Edit:***
    *   Location: Unit 6 items 32 and 33; Verification Plan.
    *   Change: Run through a new Makefile target `evaluate-delta` (add `Makefile` (Modify) to Unit 6) that exports `DB_ENGINE=sqlite` and `SQLITE_PATH=<new temporary file>`, runs `cd backend && uv run python manage.py migrate`, then `uv run python manage.py evaluate_delta <corpus_dir> <labels.jsonl>`, then deletes the file. The command creates one `Source` named `evaluation`, one `Article` per corpus file (first line is the title, the rest is the body), orders files within a release group by file name, and matches a produced claim to a label by normalized entity name, predicate and value. `docs/baseline-corpus.md` is updated to describe this file layout and reconcile it with the existing corpus notes.

### [Issue 8] [`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`] M8 PostgreSQL concurrency check and existing tests still unspecified - Severity: Major
*   **Affected Scope:** [Lines 368-374](docs/designs/delta-feed-novelty-first-reading.md#L368-L374)
*   **Discrepancy Description:** "Must also be run against PostgreSQL" has no command, setup, scenario or pass criterion; the E2E bullet mixes four checks; only two existing test files are named.
*   **Rationale:** The check cannot be run or judged.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The test waiver itself stays open from round 1 (Issue 4 there); this edit works inside it with a manual script and a list of tests to update.
*   ***Proposed Edit:***
    *   Location: Verification Plan.
    *   Change: Split the E2E bullet into three: collector API, evaluation harness, browser check. Add a PostgreSQL bullet: "Manual concurrency check: start PostgreSQL, set `DB_ENGINE=postgresql` and the database variables defined in `config/settings.py`, run `migrate`, then run two `run_worker` processes and submit two articles that carry the same new claim at the same moment. Pass: exactly one of the two claims is `new` and the other is `duplicate`." Name the tests to update: `test_analysis_scheduling.py`, `test_extraction_use_case.py`, `test_claims_api.py`, `test_today_feed.py`, `test_reader_api.py`, `test_guide_proposals_api.py`, and frontend `contracts.test.ts`, `today-state.test.ts`; "tests that cannot be updated in this phase stay red and are listed in the commit message".

### [Issue 9] [`egm-implementation-readiness`] M9 `also_covered_by` and Delta API gaps - Severity: Major
*   **Affected Scope:** [Lines 265, 267, 297](docs/designs/delta-feed-novelty-first-reading.md#L265-L297)
*   **Discrepancy Description:** `also_covered_by` is one integer per article but would count reverse links of every classification and repeats from the same article. Delta paging defaults and the meaning of `first_sighting` on a mixed article are missing.
*   **Rationale:** The number shown to the reader would be wrong.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Delta API response; Unit 3 item 17.
    *   Change: "`also_covered_by` is the number of distinct other articles that have a `duplicate` claim whose `matched_claim` is one of this article's displayed claims." Delta uses the Feed's page size (default 25, maximum 100). `first_sighting` is per claim.

### [Issue 10] [`egm-implementation-readiness`] M10 Mentions API under-specified - Severity: Major
*   **Affected Scope:** [Lines 267, 284, 328](docs/designs/delta-feed-novelty-first-reading.md#L267-L328)
*   **Discrepancy Description:** `status` values, candidate count, sample contents, invalid `action` combinations, the resolve response and empty-group behaviour are open, as are how claims tie to mentions and what happens to a claim whose `entity_ref` matches no mention.
*   **Rationale:** Two implementers would build different endpoints.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The orphan-claim case cannot occur: `ExtractionResult` already rejects claims whose `entity_ref` is not a declared mention (`analysis/contracts/extraction.py`).
*   ***Proposed Edit:***
    *   Location: Mentions API definition.
    *   Change: `status` accepts `pending`, `resolved` or `dismissed` (default `pending`). `candidates` holds at most 5 entities. `name_samples` holds up to 3 distinct raw names; `evidence_sample` is the first evidence quote of the first mention, cut to 300 characters. `link` requires `entity_id` of the same type as the group; `create` takes an optional `new_entity`; `dismiss` takes neither; any other combination returns 422, an unknown group 404. The resolve response is `{ resolved_mentions, jobs_enqueued }`. A claim belongs to the mention whose `ref` equals its `entity_ref`; extraction validation already guarantees one exists.

### [Issue 11] [`egm-codebase-details`] M11 Compare jobs and the daily budget - Severity: Major
*   **Affected Scope:** [Lines 291, 298, 300](docs/designs/delta-feed-novelty-first-reading.md#L291-L300)
*   **Discrepancy Description:** `extract_article_job` returns `budget_exhausted` before calling the model; the plan does not say what compare jobs do when the budget is spent.
*   **Rationale:** Behaviour at the budget limit is undefined.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 10.
    *   Change: "The deterministic tier needs no budget. When a claim needs a model call and the budget is spent, the job writes the claims it could decide, leaves the rest unwritten, returns `budget_exhausted`, and leaves `compared_at` empty. `schedule_due_analysis` also enqueues compare jobs for completed extraction runs with `compared_at` empty, within the budget. The unique (`analysis_run`, `fingerprint`) rule makes the retry safe."

### [Issue 12] [`egm-codebase-details`] M12 Invalid-output error has no storage location - Severity: Major
*   **Affected Scope:** [Line 295](docs/designs/delta-feed-novelty-first-reading.md#L295)
*   **Discrepancy Description:** `failure_reason` holds only codes and `Claim` has no error field, so "with the validation error in the job result" has no stored place beyond the job.
*   **Rationale:** The error would be lost with the job record.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 9 (after the loop).
    *   Change: Add "A model call that returns invalid output still writes its `compare` run, with `failure_reason` `invalid_output` and the validation error text in the run's `output`."

### [Issue 13] [`egm-codebase-details`] M13 `on_delete` missing on new foreign keys - Severity: Major
*   **Affected Scope:** [Lines 259-260, 270-271](docs/designs/delta-feed-novelty-first-reading.md#L259-L271)
*   **Discrepancy Description:** Foreign keys on `ExtractedMention`, `IngestionReceipt` and `CollectorCredential.created_by` have no delete rule, and `ExtractedMention.entity` affects the current rule that claims block an entity delete.
*   **Rationale:** Migrations need an explicit rule for each.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The choices below keep audit records and match how `Claim` protects entities; `delete_entity` must handle the new protected case, which I could not confirm from line 205 of `knowledge/api.py` and the plan says to check.
*   ***Proposed Edit:***
    *   Location: `ExtractedMention`, `CollectorCredential` and `IngestionReceipt` definitions; Unit 1 item 6.
    *   Change: `ExtractedMention`: `analysis_run` and `source_article` CASCADE, `entity` PROTECT. `CollectorCredential.created_by` PROTECT. `IngestionReceipt`: `credential` PROTECT, `source` PROTECT, `article` CASCADE, `revision` CASCADE. Unit 1 item 6 adds: `delete_entity` returns the same 409 for mentions as it does for claims (verify against the existing handling at implementation).

### [Issue 14] [`egm-codebase-details`] M14 `received_via` backfill rule is wrong - Severity: Major
*   **Affected Scope:** [Lines 273, 351, 354](docs/designs/delta-feed-novelty-first-reading.md#L273-L354)
*   **Discrepancy Description:** "`rss` for revisions of articles that have a source" mislabels manual submissions, which `submit_article` appends to articles that have a source with `submitted_by` set.
*   **Rationale:** Existing manual revisions would be mislabelled.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the revision model has `submitted_by` for exactly this distinction.
*   ***Proposed Edit:***
    *   Location: `ArticleRevision` additions definition; Unit 8 item 39.
    *   Change: "the migration sets `rss` where the article has a source and `submitted_by` is null, and `manual` otherwise; legacy snapshot revisions created by `current_revision` get `rss` when the article has a source and `manual` when it does not."

### [Issue 15] [`egm-codebase-details`] M15 `observe_article` lookup and dedupe - Severity: Major
*   **Affected Scope:** [Line 354](docs/designs/delta-feed-novelty-first-reading.md#L354)
*   **Discrepancy Description:** A lookup under the source only misses the manual-article adoption that `rss.py` performs, so a collector submission of an already-submitted URL creates a parallel article. `is_backfill`, dedupe scope and `submitted_by` are unstated.
*   **Rationale:** Duplicate articles would produce duplicate claims.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 8 item 42.
    *   Change: Lookup order is (source, `external_id`), then (source, URL), then a manual article with the same URL (no source), which is adopted by setting its source, as `rss.py` does. A new article gets `is_backfill` false. A new body is deduplicated against the latest revision's hash only. Collector revisions have `submitted_by` null; the credential is recorded on the receipt. The older-replay logic in `rss.py` is not reused; section 9's revision-ordering rule applies instead.

### [Issue 16] [`egm-codebase-details`] M16 Request-size check versus Ninja body parsing - Severity: Major
*   **Affected Scope:** [Lines 153, 355, 362](docs/designs/delta-feed-novelty-first-reading.md#L153-L362)
*   **Discrepancy Description:** Ninja parses the body before the view runs, so a `Content-Length` check in the view cannot run first. Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` also applies, and the throttle cache is Django's default per-process cache.
*   **Rationale:** The 413 mechanism is undefined.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the round-1 fix named the check but not where it runs.
*   ***Proposed Edit:***
    *   Location: Technical Plan section 9 "Limits"; Unit 8.
    *   Change: Add `delta_feed/content/collector_limits.py` (Create), a Django middleware that applies only to paths under `/api/v1/` and returns 413 when `Content-Length` exceeds `COLLECTOR_MAX_REQUEST_BYTES`; add `delta_feed/config/settings.py` (already listed) `MIDDLEWARE` entry and set `DATA_UPLOAD_MAX_MEMORY_SIZE` to the same value. The rate limit follows the throttle in `accounts/api.py` (Django default local-memory cache, a known limit with several web workers).

### [Issue 17] [`egm-codebase-details`] M17 Unit 8 is not independent - Severity: Major
*   **Affected Scope:** [Lines 244, 275, 361](docs/designs/delta-feed-novelty-first-reading.md#L244-L361)
*   **Discrepancy Description:** The status `delta` stage needs `Claim` classifications and `ExtractedMention` from Unit 1. Item 42a edits `reader/api.py`, which Unit 3 also modifies. It is not said which unit adds the `COLLECTOR_*` settings.
*   **Rationale:** A repeat of the round-1 independence finding; my fix only edited one sentence.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Line 244; Unit 3; Unit 8 items 42a and 48.
    *   Change: Line 244: "Unit 8's submission endpoint is independent and can be built first. Its status endpoint returns only the `content` stage until Units 1 to 3 exist, and then adds `analysis` and `delta`." Move the creation of `delta_feed/analysis/status.py` and the `reader/api.py` change from item 42a to Unit 3. Unit 8 items 48 and 49 add the `COLLECTOR_*` settings and the `.env.example` lines.

### [Issue 18] [`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`] N1 Management package files created twice - Severity: Nit
*   **Affected Scope:** [Lines 306, 337](docs/designs/delta-feed-novelty-first-reading.md#L306-L337)
*   **Discrepancy Description:** `analysis/management/__init__.py` and `commands/__init__.py` appear in both items 10a and 31. Lettered sub-items are unexplained.
*   **Rationale:** Duplicate creation.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** One-line deletion; the style reviewer rated it Major, the other two Nit, and I kept the lower rating.
*   ***Proposed Edit:***
    *   Location: Unit 6 item 31; Unit 2 intro.
    *   Change: Remove the two package files from item 31 (item 10a creates them). Add under the units table: "Lettered items (7a, 9a, 10a, 22a, 42a, 46a) belong to the unit of the item before them."

### [Issue 19] [`egm-implementation-readiness`] N2 `backfill_total` undefined - Severity: Nit
*   **Affected Scope:** [Lines 266, 312](docs/designs/delta-feed-novelty-first-reading.md#L266-L312)
*   **Discrepancy Description:** Which articles count (backfill flag, no revision, failed extraction) is not stated.
*   **Rationale:** The readiness percentage depends on it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Cheap.
*   ***Proposed Edit:***
    *   Location: Unit 3 item 16.
    *   Change: "`backfill_total` counts articles with `is_backfill` true that have a current revision; articles whose extraction failed with invalid output count as analysed (they are settled), articles waiting on an outage do not."

### [Issue 20] [`egm-implementation-readiness`, `egm-codebase-details`] N3 Duplicate fingerprints within one article - Severity: Nit
*   **Affected Scope:** [Lines 285, 297](docs/designs/delta-feed-novelty-first-reading.md#L285-L297)
*   **Discrepancy Description:** The "skip existing" rule drops a second claim with the same fingerprint silently, and the round-1 "extraction order" sentence is not in the document.
*   **Rationale:** Behaviour with repeated claims in one article is undefined.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; Issue 3's loop rewrite also removed the ordering sentence.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 9.
    *   Change: "Claims are written in extraction order inside the transaction. Within one article, a claim whose fingerprint equals one already written from the same article is skipped, so each article contributes a given claim once."

### [Issue 21] [`egm-codebase-details`] N4 `guides/api.py` details - Severity: Nit
*   **Affected Scope:** [Lines 105, 306-310, 320-321](docs/designs/delta-feed-novelty-first-reading.md#L306-L321)
*   **Discrepancy Description:** `list_proposals` returns only pending rows, so a "superseded" status never shows on the page. `update_fields` and the output schema need the new fields. "Registered before the `{proposal_id}` routes" is unnecessary.
*   **Rationale:** The page change in Unit 5 would show nothing.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 4 item 21; Unit 5 item 30; reject-older definition.
    *   Change: Item 21 adds "`accept_proposal` and `reject_proposal` include `decided_at` and `decision_source` in `update_fields`; `GuideProposalOut` carries both fields." Item 30 drops "and the superseded status". Remove "registered before the `{proposal_id}` routes" from both places.

### [Issue 22] [`egm-codebase-details`] N5 `/` to `/delta` redirect - Severity: Nit
*   **Affected Scope:** [Line 330](docs/designs/delta-feed-novelty-first-reading.md#L330)
*   **Discrepancy Description:** The redirect has no rule for requests that carry a `view` parameter, and the "All" tab and the "Feed" nav link are not reconciled.
*   **Rationale:** A user who picks a view would be redirected away.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 5 item 27.
    *   Change: "The redirect applies only when the request has no `view` parameter. The Feed view keeps the default `all` listing; the former 'All' tab is removed because Feed replaces it; the 'Feed' link in the navigation points to `/`."

### [Issue 23] [`egm-codebase-details`] N6 Reuse and gaps - Severity: Nit
*   **Affected Scope:** [Lines 261, 283-285](docs/designs/delta-feed-novelty-first-reading.md#L261-L285)
*   **Discrepancy Description:** The fingerprint should reuse `SCOPE_FIELDS`; the mapping from evidence `{start, end, quote}` and nested `scope` to flat `record_claim` keys is not spelled out; the Python scan in `resolve_by_name` sits oddly with the hexagonal adapter pattern.
*   **Rationale:** Small gaps and possible duplication.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid for the first two; the third is kept as designed (the entity table is small, and a query adapter can replace the scan when it is not).
*   ***Proposed Edit:***
    *   Location: Unit 1 item 3; extraction-to-claim mapping.
    *   Change: "`claim_fingerprint` imports `SCOPE_FIELDS` from `core/claim_delta.py`." Mapping: "`claim_data` keys are `claim_text`, `version`, `platform`, `availability` (from `scope`), `evidence_start`, `evidence_end`, `evidence_text` (from the first evidence span's `start`, `end` and `quote`)."

### [Issue 24] [`egm-style`] N7 "Units 1 to 7 depend on the ones before them" overstates - Severity: Nit
*   **Affected Scope:** [Line 244](docs/designs/delta-feed-novelty-first-reading.md#L244)
*   **Discrepancy Description:** Not every unit depends on all earlier ones.
*   **Rationale:** Overstated.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; merges with Issue 17's edit to this line.
*   ***Proposed Edit:***
    *   Location: Line 244.
    *   Change: "Build units 1 to 7 in order (each needs the data or endpoints of the earlier ones it uses); Unit 8's submission endpoint is independent and can be built first."

### [Issue 25] [`egm-style`] N8 "Modify" items that change nothing - Severity: Nit
*   **Affected Scope:** [Lines 300-301](docs/designs/delta-feed-novelty-first-reading.md#L300-L301)
*   **Discrepancy Description:** Items 12 and 13 say "no change in this unit".
*   **Rationale:** Empty entries in a file list.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the budget rule is already stated in the data definitions and in item 10.
*   ***Proposed Edit:***
    *   Location: Unit 2 items 12 and 13.
    *   Change: Delete both. State once in the `AnalysisRun.kind` definition: "Provider outages do not count against the budget (`_budgeted_runs_today` already excludes them)."

### [Issue 26] [`egm-style`] N9 Inconsistent job names - Severity: Nit
*   **Affected Scope:** [Lines 286, 298, 299](docs/designs/delta-feed-novelty-first-reading.md#L286-L299)
*   **Discrepancy Description:** Four names refer to overlapping things.
*   **Rationale:** Hard to follow.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Covered by Issue 6's table.
*   ***Proposed Edit:***
    *   Location: Unit 2 item 10.
    *   Change: Refer to the jobs by the table in item 11 only.

### [Issue 27] [`egm-style`] N10 Collector definitions run on - Severity: Nit
*   **Affected Scope:** [Lines 268-270](docs/designs/delta-feed-novelty-first-reading.md#L268-L270)
*   **Discrepancy Description:** A blank line separates the collector definitions without a lead-in.
*   **Rationale:** Layout.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Cheap.
*   ***Proposed Edit:***
    *   Location: Data and contract definitions, before `CollectorCredential`.
    *   Change: Add the lead-in "Collector ingestion (Unit 8):" and remove the stray blank line.

### [Issue 28] [`egm-style`] N11 "Spans always lie inside the analysed text" - Severity: Nit
*   **Affected Scope:** [Line 261](docs/designs/delta-feed-novelty-first-reading.md#L261)
*   **Discrepancy Description:** An absolute word on a claim the code only guarantees under one condition.
*   **Rationale:** Unsupported absolute.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Extraction-to-claim mapping.
    *   Change: "Spans lie inside the analysed text, because `resolve_evidence` rejects a quote that is not found in the truncated text the model received."

### [Issue 29] [`egm-style`] N12 "Unit Tests" label and empty coverage bullet - Severity: Nit
*   **Affected Scope:** [Lines 370-373](docs/designs/delta-feed-novelty-first-reading.md#L370-L373)
*   **Discrepancy Description:** The label does not match its content, and "Test Coverage Requirement: None" is empty.
*   **Rationale:** Wording.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Cheap; consistent with the round-1 decision to keep the waiver open.
*   ***Proposed Edit:***
    *   Location: Verification Plan.
    *   Change: Rename the bullet "Existing suites" and drop the "Test Coverage Requirement" bullet, keeping the sentence at the top of the section that says new tests are out of scope for this phase.

### [Issue 30] [`egm-style`] N13 "Implemented and exercised" is vague - Severity: Nit
*   **Affected Scope:** [Line 347](docs/designs/delta-feed-novelty-first-reading.md#L347)
*   **Discrepancy Description:** No concrete gate for updating the README.
*   **Rationale:** Vague condition.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: Unit 7 item 38.
    *   Change: "Update Project status and local-development commands only after each unit's checks in the Verification Plan have passed and the manual browser check has been done."
