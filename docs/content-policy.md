# Content policy

What the system may publish, hide or change by itself. These rules are accepted ([ADR 0004](decisions/0004-content-and-ingestion-defaults.md)); what is built is in [status](status.md).

## Two outputs, shared knowledge

- **News** answers "what happened or became available?" **Guides** answer "what should I consider for this purpose today?"
- Both use the same entities and claims. Each has its own approval path; news never waits for guide review.
- One identity per thing across topics and guides. A practice and a tool that implements it are different entities.
- Evidence shows what a source said. It does not certify that it is true.

## Default publication

- **Shadow mode.** Originals stay readable. Anything proposed as "already known" is labelled and inspectable. Nothing is hidden automatically.
- Automatic hiding needs a reviewed evaluation on real data, an explicit switch and a way back. Hiding never deletes.
- Publication time and discovery time are kept apart. Old but new to you is a discovery, not breaking news.
- A security, deprecation or availability change about something familiar is still shown.
- A model timeout, malformed output or missing data leaves the item pending or "not sure". It never invents novelty or redundancy. No silent cloud fallback.

## Living guides

- A guide has a purpose, eligibility criteria, ordered entries and a revision history. An entry links an entity and holds suitability, requirements, caveats and evidence.
- Your own text is stored apart from generated proposals and is never overwritten.
- Proposal kinds: add, update, warning, retire. New does not mean recommended. A dead link makes evidence stale; it does not mean the project is abandoned.
- Every model-proposed edit needs your approval ([ADR 0009](decisions/0009-guide-proposal-resolution-policies.md)). Approval checks the guide revision it was computed against; a stale proposal is recomputed, not applied.
- With your confirmation, entities in a guide count as familiar.

## Topics, sources and onboarding

- Sources and topics are created by you, never as a side effect of ingestion.
- Setup picks topics and sources. Starter packs suggest feeds; none are preselected.
- Backfill is quiet and bounded: recent history only, unread, out of the main view, with skipped entries counted. A later poll never imports older entries as current.
- A backfill that finishes late keeps its quiet status. A restart never turns history into alerts.

## Feedback and correction

- "Already knew this" records your familiarity. It does not change the entity, the claim or read state.
- "Wrong match" opens a correction for review. It never merges or splits entities by itself.
- An approved correction reassigns the affected records and re-evaluates what depended on them. History is kept; published guide text is not silently rewritten.

## Retention and privacy

- Keep the minimum needed for audit: the quoted passage, source URL, revision fingerprint, scope, time and how the decision was made.
- How long full article text is kept is configurable and not yet chosen. Nothing is purged automatically until that policy and its tests exist.
- Removing article text must not silently remove published evidence: keep the permitted passage or mark the record "evidence unavailable".
- No article corpus in git. No blanket redistribution of full text. No paywall bypass.

## Separate state axes

Each of these is its own state. Completing one does not imply another.

| Axis | States |
|---|---|
| Content | pending, available, failed |
| Analysis | pending, running, completed, failed; decisions can remain "not sure" |
| News | proposed, accepted, suppressed, superseded |
| Guide proposal | proposed, approved, rejected, stale |
| Job | pending, leased, succeeded, failed |

## Atomic boundaries

Three separate transactions, none of which makes an external call:

1. **Ingestion:** the receipt, the supplied text if any, and the job.
2. **Knowledge:** validated claims and their classification, after rechecking the baseline they were compared with.
3. **Guide approval:** the reviewed change, the expected-revision check and the new guide revision.

A stale analysis is re-evaluated, never committed with its old verdict.

## Evaluation gates

No automatic hiding and no automatic guide approval without an evaluation on real data that you reviewed. Metrics are in the [roadmap](roadmap.md#evaluation-metrics).
