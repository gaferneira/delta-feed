# Product scope

## Outcome

A useful daily reading destination, not a processing dashboard or a list of generated summaries, plus a small set of your own reference articles that stay current. Replace repetitive browsing without concealing important developments.

## Reading experience

- **Today:** relevant discoveries and meaningful events grouped by configured topic.
- **Discoveries:** previously unfamiliar entities extracted even from familiar roundups.
- **Following:** scoped feature changes and events for watched entities.
- **Saved:** reading queue.
- **Guides:** your own living articles (e.g. recommended skills every project should have, Raspberry Pi home automation) as structured entries with personal notes, evidence and reviewed revision history. Manual first; model-proposed updates arrive with analysis.
- **All Content:** originals, suppressions with reasons, uncertain items, and processing failures.

Cards explain what is new, why they appear, supporting sources, and publication versus discovery time. Provide read/save, already-knew, and wrong-match actions.

[Content policy](content-policy.md) defines accepted shadow-mode, living-guide, onboarding, feedback, retention and transaction defaults. [Ingestion contract](ingestion-contract.md) defines URL-fetch/provided-text inputs and retry/revision rules. These are planned behavior, not running features.

## Independent concepts

Identity, registry novelty, user relevance, delivery, and acknowledgement/read status are distinct. Indexed is not read. Familiar does not mean unimportant: security advisories and release-status changes remain eligible for display.

Topics are many-to-many labels on articles/entities/events, not separate identity registries. One entity can belong to several topics without duplication. Start with explicit preferences and watchlists, not opaque learned ranking.

## MVP acceptance: reader

- [ ] Authenticated article submission persists a revision and returns an inspectable job/status.
- [ ] A responsive reader displays original/source-linked cards and persists read/save state.
- [ ] Topics/sources are explicitly administered; quiet backfill preserves unread state and does not flood Today.
- [ ] Repeated submissions are idempotent; changed content is revisioned.
- [ ] Roundups yield known/new/uncertain item decisions supported by evidence.
- [ ] Entity timelines retain duplicate, novel, refinement, contradiction, and availability distinctions without overwriting history.
- [ ] No similarity-only match silently suppresses a discovery.
- [ ] Uncertain/model-failed items remain accessible and retryable.
- [ ] Sources and topics are configurable without code edits.
- [ ] Restart/retry and backup/restore tests pass.
- [ ] Real daily trial evaluates missed important items and repeated cards before enabling automatic suppression.

## MVP acceptance: guides

- [ ] Guides support manual structured entries, preserved personal prose and revision history, before any AI.
- [ ] With confirmation, guide entries mark entities as familiar and can seed the Following watchlist.
- [ ] Model-proposed add/update/warning/retire changes are evidence-backed and require review; new does not mean recommended.
- [ ] Approval rejects stale proposals; corrections propose repairs rather than silently rewriting published advice.

Guide review is a separate path: news processing never waits for guide approval.

## Non-goals

Multi-user tenancy, hosted SaaS, autonomous source discovery, arbitrary browser scraping, agent tool execution on source text, real-time guarantees, and advanced recommendation systems.

## Unresolved

Initial feeds/watchlist, trial duration, acceptable error rates, content retention policy, and supported deployment resources. The code is licensed under AGPL-3.0; that license covers this software, not the third-party content it reads. Source discovery and article access are not equivalent to a right to republish full copyrighted content; default to attributed excerpts and original links, and respect source restrictions.
