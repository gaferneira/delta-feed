# Roadmap and evaluation

All work below is pending. No runnable scaffold exists.

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

Detailed use-case ports and persistence schemas are designed within this slice. Confirm compatible versions, lock Python and frontend dependencies, scaffold Astro SSR, Django Ninja and Postgres, then implement Django-owned login/session, versioned submission, article revisions and reader read/save state. Exercise login → Astro SSR feed → API save/read → persisted reload, duplicate/revision handling, mobile UX, SSR cookie forwarding, enforced browser CSRF, private caching and restart persistence. Generate frontend types from backend OpenAPI and verify drift. Add actual run commands and CI only once exercised.

## Milestone 2: Manual guides, no AI

Guide definitions (purpose/audience, topic links, eligibility criteria, ordered sections), structured entries linked to entities, preserved personal prose, manual editing and revision history. Render the article-like view from structured entries; preserve imported Markdown as-is. With your confirmation, guide entries mark their entities as familiar and can seed the Following watchlist. Test expected-revision checks on concurrent edits and revision history persistence.

## Milestone 3: Safe ingestion and jobs

RSS polling, bounded extraction, source health, durable worker leases/retries and failure UI. Implement explicit topic/source onboarding and quiet backfill, preserving unread state and backfill intent through restart/replay. Test malformed/oversized inputs, hostile HTML, SSRF/redirects, unavailable sources, and restart mid-job. Generic Compose must run independently of private infrastructure integrations.

## Milestone 4: Discovery shadow mode and guide additions

Structured extraction, exact identities, embeddings/candidate search, adjudication, reviewable proposals and corrections. Keep all originals visible; no automatic suppression. Log source evidence and model/prompt/index versions. Exercise near-identity and concurrent/replayed analysis cases.

Discoveries that match a guide's eligibility criteria produce reviewable add-entry proposals; new does not mean recommended. Test guide creation from existing knowledge and guide-specific onboarding without changing quiet-backfill behavior.

## Milestone 5: Entity deltas and guide updates in shadow mode

Atomic scoped claims, duplicate/refinement/contradiction relationships, material event handling, source-linked timelines. Test out-of-order releases, availability differences, stale baselines, and bounded retrieval misses.

Deltas affecting guide entries produce update, warning or retire proposals with evidence. Test stale approval, changed criteria, failed source links, unsuitable recommendations and corrections affecting existing advice. No automatic guide edits.

## Milestone 6: Private deployment and first daily trial

Onboarding and familiarity follow the phased plan in [ADR 0005](decisions/0005-progressive-onboarding.md) (proposed); the trial needs at least its Phase A familiarity core. Verify standalone install and backup restore before optional infrastructure integration. Configure private HTTPS ingress through the installer's infrastructure workflow; n8n/Telegram remain optional and are not gates for the trial. Test unavailable inference, index catch-up, pending visibility and quiet backfill; test delivery failures if notifications are enabled. Evaluate whether the reader surfaces worthwhile discoveries/updates without repeated cards or missed important events, and whether guide proposals are useful. A guide review backlog never delays news. Keep suppression in shadow mode unless reviewed evaluation supports explicit enablement with easy rollback.

This repository is public and AGPL-3.0 licensed from its initial commit. That is not an installability claim: provide sanitized examples, deployment/auth guidance and exercised supported architectures before claiming a supported application distribution.

## Documentation discipline

Keep a small living set: README for onboarding, glossary for terms, product for behavior, architecture for invariants, technology for choices, ADRs for why, roadmap for implementation gates. Personal task tracking stays outside this public repository; avoid duplicating task status here. The ingestion design contract is documented now; generated API documentation follows actual implementation. Add operator runbook, CONTRIBUTING and SECURITY when there is exercised behavior to support them, not as empty placeholder files.
