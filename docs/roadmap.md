# Roadmap and evaluation

Implementation status is tracked only in [README's Project status](../README.md#project-status).

News comes first, but guides are not left until the end. Manual guides follow the first reader slice, and model-proposed guide changes arrive together with the analysis that produces news. Guide review never blocks news processing.

## Milestone 0: Real examples

Collect actual article URLs/evidence and record the prior known baseline and desired cards. [baseline-corpus.md](baseline-corpus.md) is the standard procedure for collecting the baseline and daily verdicts. Cover mostly-known roundups, renames, similar distinct tools/forks, repeated announcements, beta/GA changes, refinements/contradictions, familiar security events, irrelevant novelty, and incomplete source extraction. Include sources beyond AI news, such as hobbyist hardware and home-automation project blogs, forums and repositories, so extraction is not tuned to one kind of writing.

Also write down one or two of your own guides as they stand today (for example "Raspberry Pi home automation" or "Recommended skills every project should have") and, for some collected articles, the guide change you would expect: add, update, warning, retire, or no useful change.

Before semantic implementation, review worked examples that each specify:

- Source URL, permitted evidence passages and relevant publication/observation time.
- Prior entity/claim baseline and personal familiarity, kept distinct from read state.
- Expected entity matches, scoped claims and duplicate/novel/refinement/contradiction decisions with reasons.
- Exact desired reader card and its supporting evidence, or the reason no new card should appear.
- Expected guide proposal, if any, and why.
- What remains uncertain and how the original/proposal remains inspectable.

Do not check copyrighted full articles into a public repo without permission. Keep restricted corpus text local; public fixtures can be licensed excerpts or explicitly synthetic failure/logic scenarios. Never represent synthetic examples as retrieved sources. No corpus or completed examples exist yet; these are acceptance criteria, not evaluation results.

### Evaluation metrics

Measure discovery false merges/misses, missed important events, false-new repetition and repeated cards, claim-delta precision/recall, unsupported claims, uncertain rate, relevance, unsuitable guide recommendations, and latency/cost. Use actual source-backed expected outputs and reserve held-out examples to prevent evaluation leakage. Agree trial duration and target error rates only after reviewing real data. Never use model self-reported confidence or generic vector thresholds as release gates.

## Milestone 1: Reader vertical slice, no AI

Detailed use-case ports and persistence schemas are designed within this slice. Confirm compatible versions, lock Python and frontend dependencies, scaffold Astro SSR, Django Ninja and Postgres, then implement Django-owned login/session, versioned submission, article revisions and reader read/save state. Exercise login → Astro SSR feed → API save/read → persisted reload, duplicate/revision handling, mobile UX, SSR cookie forwarding, enforced browser CSRF (missing and invalid tokens), session expiry, unauthorized access, private-cache isolation and restart persistence. Generate frontend types from backend OpenAPI, build them from a clean checkout and verify drift. This slice is the first proof of [ADR 0002](decisions/0002-astro-django-ninja.md). Add actual run commands and CI only once exercised.

## Milestone 2: Manual guides, no AI

Guide definitions (purpose/audience, topic links, eligibility criteria, ordered sections), structured entries linked to entities, preserved personal prose, manual editing and revision history. Render the article-like view from structured entries; preserve imported Markdown as-is. With your confirmation, guide entries mark their entities as familiar and can seed the watchlist. Test expected-revision checks on concurrent edits and revision history persistence.

## Milestone 3: Safe ingestion and jobs

RSS polling, bounded extraction, source health, durable worker leases/retries and failure UI. Implement explicit topic/source onboarding and quiet backfill, preserving unread state and backfill intent through restart/replay. Test malformed/oversized inputs, hostile HTML, SSRF/redirects, unavailable sources, and restart mid-job. Generic Compose must run independently of private infrastructure integrations.

## Milestone 4: Discovery shadow mode and guide additions

Structured extraction, exact identities, embeddings/candidate search, adjudication, reviewable proposals and corrections. Keep all originals visible; no automatic suppression. Log source evidence and model/prompt/index versions. Exercise near-identity and concurrent/replayed analysis cases.

Discoveries that match a guide's eligibility criteria produce reviewable add-entry proposals; new does not mean recommended. Test guide creation from existing knowledge and guide-specific onboarding without changing quiet-backfill behavior.

## Milestone 5: Entity deltas and guide updates in shadow mode

Atomic scoped claims, duplicate/refinement/contradiction relationships, material event handling, source-linked timelines. Test out-of-order releases, availability differences, stale baselines, and bounded retrieval misses.

The reader-facing result is the Delta page; its delivery order is under [ADR 0008](#adr-0008-delta-page-and-feed).

Deltas affecting guide entries produce update, warning or retire proposals with evidence. Test stale approval, changed criteria, failed source links, unsuitable recommendations and corrections affecting existing advice. No automatic guide edits.

## Milestone 6: Private deployment and first daily trial

Onboarding and familiarity follow the [ADR 0005 phases](#adr-0005-progressive-onboarding); the trial needs at least its Phase A familiarity core. Verify standalone install and backup restore before optional infrastructure integration. Configure private HTTPS ingress through the installer's infrastructure workflow; n8n/Telegram remain optional and are not gates for the trial. Test unavailable inference, index catch-up, pending visibility and quiet backfill; test delivery failures if notifications are enabled. Evaluate whether the reader surfaces worthwhile discoveries/updates without repeated cards or missed important events, and whether guide proposals are useful. A guide review backlog never delays news. Keep suppression in shadow mode unless reviewed evaluation supports explicit enablement with easy rollback.

This repository is public and AGPL-3.0 licensed from its initial commit. That is not an installability claim: provide sanitized examples, deployment/auth guidance and exercised supported architectures before claiming a supported application distribution.

## Plans for proposed ADRs

ADRs record decisions only; their phases and slices live here. Each phase ships with tests and starts only when its prerequisite works.

### ADR 0005: Progressive onboarding

Plan for [ADR 0005](decisions/0005-progressive-onboarding.md).

| Phase | Scope | Prerequisite |
|---|---|---|
| A. Familiarity core | `Topic` model; per-user familiarity with an append-only change history; "Already knew this" API records familiarity; delivery levels (topic default, entity override) and feed ordering; `manage.py import_known <csv>` | None (no AI, no new UI beyond the card action) |
| B. Minimal setup | First-account creation guarded by a one-time setup token; starter-pack format, loader and validation; first-run topics + sources screen; triggers quiet backfill. Delivered ahead of Phase A, without delivery levels or familiarity. | Phase A; recurring RSS polling |
| C. Triage and bulk | Most-mentioned-entities triage after backfill; roundup "all except…" action; calibration label | Extraction wired into the worker and run on real articles |
| D. Nudges and notifications | Suggestions from repeated dismissals, thresholds tuned on trial data; significant-event notifications for `notify` items | Milestone 6 daily trial data; claim/event classification; a configured notification integration |

- [Milestone 0](#milestone-0-real-examples) informs the formats: check the import columns and the triage list against real collected baselines before Phase A freezes them.
- When ADR 0005 is accepted, update the content policy's onboarding section and the glossary to match.

Phase B as implemented:

- **Account:** a 24-hour token, stored only as a hash, is logged once at WARNING when `/api/accounts/setup-status` is first requested on an empty instance; `/setup` consumes it, and `manage.py setup_token` rotates it when the logs are lost. `scripts/init.sh` prompts for the first user in local development.
- **Setup:** after the first login, a user with no completed onboarding is sent to `/onboarding` before any reader page, picks starter-pack topics, ticks the packs' feeds they want (all start unticked), and finishes or skips; both mark it complete (`ReaderProfile.onboarding_completed_at`; accounts that existed when this shipped were marked complete by a data migration). Finishing upserts the shared `Topic` rows (in `knowledge`), records the user's `TopicSelection`, and registers each chosen feed through the ordinary source use case, attached to its topic, which queues the usual quiet backfill. Only feeds from the chosen packs are accepted here; custom feeds still use the Sources page. There are no delivery levels, topic parents, exclusions or entity links yet, and no watchlist or guide offer.

### ADR 0006: Attention budget and analysis funnel

Plan for [ADR 0006](decisions/0006-attention-budget-and-analysis-funnel.md).

| Phase | Scope | Prerequisite |
|---|---|---|
| A. Bounds | Bounded backfill with skipped counts; Today budget with "More from today"; per-source cap; recurring RSS polling so current articles reach Today; worker documented as a dev process | None (no AI) |
| B. Model work | `analysis.extract` job after ingestion, daily model budget, priority queue, unanalysed state | Phase A; extraction exercised against a real local model |
| C. Relevance | Embeddings populated at ingest; relevance gate before extraction | Phase B; embedding model chosen |
| D. Ranking | Novelty and significance in ranking, card reasons | Phase B and [ADR 0007](#adr-0007-preference-signals-and-transparent-ranking) slices |
| E. Enforcement | Turn individual shadow rules into real filtering | Evaluation against real reading data |

Ranking inputs arrive in this order: recency and source diversity (Phase A), preferences (ADR 0007), then delivery level, novelty and significance (Phase D).

Phase A as implemented:

- **Settings** (environment, defaults): `BACKFILL_DAYS=30`, `BACKFILL_MAX_ITEMS=20`, `RSS_POLL_INTERVAL_MINUTES=30`, `TODAY_BUDGET=12`, `TODAY_PER_SOURCE_CAP=3`.
- **Backfill:** dated entries inside the window come first, newest first, then undated entries in feed order, capped at the item maximum. The `rss.poll` job result (`Job.result`) and the log record `imported`, `skipped_outside_window`, `skipped_over_cap` and `skipped_invalid_link`.
- **Cutoff:** the first poll stores `Source.backfill_cutoff` (poll time minus `BACKFILL_DAYS`). A later non-backfill poll skips a not-yet-stored entry published before that cutoff and counts it. When the item cap trims dated entries inside the window, the cutoff is raised to just after the publication date of the newest trimmed entry; when the cap trims nothing, the cutoff stays at the window. Undated entries are not covered by the cutoff. Sources imported before this change get `created_at` minus 30 days in a data migration.
- **Recurring polling:** `run_worker` calls `schedule_due_polls` at start and then about once a minute (`--once` schedules once too). A source is due when its last fetch attempt is older than the interval times 2^consecutive failures, capped at 24 hours. A source with a pending or leased poll is never given a second one; a source without a cutoff gets a backfill poll again instead of a recurring one.
- **Today:** current articles *discovered* (created in the database, not published) in the last 24 hours. The budget is filled in rounds so each source contributes its newest article before any contributes a second, with no source above the cap; the selection is shown newest first. Manual submissions never count against a source cap. `GET /api/reader/feed?view=today` returns the budget and `more_count`; `more=true` returns the rest of the day. The reader renders it behind a "Show N more from today" link, so nothing is hidden and All still lists everything.
- **Import status:** `GET /api/content/import-status` reports sources fetched, queued polls and whether a worker handled a job in the last five minutes; the reader uses it for the first-run, worker-stopped and caught-up messages.

Phase B as implemented (not yet run against a real model):

- **Provider port:** `analysis.providers` holds a `LanguageModel` protocol and a registry selected by `ANALYSIS_PROVIDER`: `ollama` (`/api/generate` with the output schema as `format`) and `openai_compatible` (`/chat/completions` with a strict `json_schema` response format, for LM Studio and similar servers). Only the configured provider is used, never a fallback, and both run at temperature 0.
- **Contract:** the model returns evidence as exact quotes only; the server resolves their offsets, and a quote that is not verbatim in the article fails the run. Bodies longer than `ANALYSIS_MAX_BODY_CHARS` are analysed as a prefix and the output records `truncated`.
- **Output:** the validated proposal, with resolved evidence offsets, is stored on `AnalysisRun.output`. It is not turned into knowledge claims yet.
- **Scheduling:** the worker calls `schedule_due_analysis` about once a minute. It queues nothing while the provider is unconfigured or an extraction job is pending or leased, and at most 5 articles per batch within `ANALYSIS_DAILY_BUDGET`. Current articles go first, newest discovered first; quiet backfill goes last and only seeds the baseline. An extraction job's lease is the model timeout plus a minute.
- **Failures:** a provider outage (`inference_unavailable`) retries with backoff, does not spend the budget and leaves the article unanalysed; invalid model output (`invalid_output`) settles the article as failed and is not retried automatically.
- **State:** the feed API returns `analysis_status` (`unanalysed`, `analysed`, `failed`) for the article's current revision.

### ADR 0007: Preference signals and transparent ranking

Plan for [ADR 0007](decisions/0007-preference-signals-and-transparent-ranking.md). Each slice is usable on its own.

1. **Card feedback and topic/source ranking (no AI).** Prerequisite: ADR 0006 Phase A, since ranking only matters once there is a cut line.
   - `PreferenceEvent` (user, kind, target type and id, value, origin, created_at) and undo.
   - "Not interested" and "More like this" on reader cards; save and open-original recorded as weak signals.
   - Derived per-user weights for topics and sources, with decay.
   - Today ranking v1: topic weight + source weight + recency, under the budget and the per-source cap.
   - A "why" line on each card from the top components.
   - Evaluation: compare the ranked Today against the [baseline corpus](baseline-corpus.md) daily log verdicts.
2. **Delivery levels and the preferences page (no AI).**
   - Topic-level `notify` / `show` / `mute` with source overrides (ADR 0005 Phase A), feeding the score.
   - `/preferences`: learned weights, their events, undo and reset.
   - Mute suggestions after repeated "not interested".
3. **Entity-level signals** (needs extraction, ADR 0006 Phase B).
   - "Already knew this" records familiarity; novelty becomes a score component.
   - Entity weights from feedback on cards that mention them; entity-level delivery overrides.
4. **Exploration and evaluation.**
   - The exploration slot.
   - A shadow report: which cards ranking would have dropped below the cut line, compared with what the reader actually opened, saved or marked.

### ADR 0008: Delta page and Feed

Plan for [ADR 0008](decisions/0008-delta-page-and-feed.md).

1. **Pages without AI:** Feed as the chronological list of every article (absorbing All and Earlier), and the landing page until the baseline is ready; Delta showing the waiting-for-analysis state; shared read/save. Baseline readiness is a measurable check (for example the share of backfilled articles analysed, plus some guide entities); the threshold is set from trial data. When it passes, a banner offers the switch to Delta.
2. **Extraction in the worker** (ADR 0006 Phase B), including the lowest-priority backfill extraction that seeds the baseline.
3. **Claim comparison and delta cards:** non-duplicate claims per article, generated headline and bullets referencing claims, fallback text. Delta is ordered newest first, without a budget.
4. **Tuning**, driven by trial data:
   - Ranking on Delta under the ADR 0006 budget and ADR 0007 preferences, replacing the old Today budget.
   - Feed badges per article ("3 new", "nothing new", "unanalysed") linking to the Delta card.
   - "Also mentioned in" on a delta when a later article repeats the claim, as metadata rather than a new card.
   - Analyse a source's official announcements ahead of secondary coverage within a batch, so the primary source tends to carry the delta.
5. **Event grouping** across articles, only if per-article cards still feel repetitive in the trial.

## Documentation discipline

Keep a small living set: README for onboarding and status, glossary for terms, product for behavior, architecture for invariants, technology for choices, ADRs for decisions and why, roadmap for phases and implementation gates. Personal task tracking stays outside this public repository; avoid duplicating task status here. The ingestion design contract is documented now; generated API documentation follows actual implementation. Add operator runbook, CONTRIBUTING and SECURITY when there is exercised behavior to support them, not as empty placeholder files.
