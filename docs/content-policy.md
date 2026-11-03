# Content, publication and living-guide policy

**Status:** Defaults accepted; policy/schema implementation pending. See ADR 0004 and the ingestion contract. No numerical quality thresholds or retention duration have been invented.

## Two outputs, shared knowledge

News answers “what happened or became available?” Living guides answer “what should I consider for this purpose today?” Both use shared entities/claims but have separate publication and approval paths. Manual guides follow the first reader slice; model-proposed guide changes arrive with discovery shadow mode (see the [roadmap](roadmap.md)). News processing never waits for guide approval.

Topics organize relevance; sources provide observations; source articles retain provenance; entities represent tools/libraries/projects or reusable practices/capabilities; scoped claims describe what a source says. Events group corroborating coverage of a discovery/change. Guides curate contextual recommendations; a globally known entity can be newly useful in a guide.

One identity across topics/guides. Names of practices and concrete skill implementations are not automatically the same entity. Relevance, registry-known, delivered and personally read/acknowledged are distinct. Source evidence supports attribution, not objective truth certification.

## Default publication

- Shadow mode initially: originals readable, proposed news events/suppression inspectable and labeled, no model-proposed automatic hiding. Accept validated knowledge separately from approving/enabling visible publication; the transition is explicit, not implied by completed analysis.
- Future automatic suppression requires user-reviewed real evaluation, explicit enablement and rollback. Suppression never deletes source observations.
- Differentiate occurred_at/source publication time from discovered_at/ingestion time. Old-but-new-to-you is a discovery, not breaking news. Important familiar security/deprecation/availability events remain eligible.
- Guides require review for every model-proposed edit in the initial guide release. Valid news processing does not wait for editorial approval.
- Model timeout/malformed output/incomplete index preserves pending/uncertain status, never fabricates novelty or redundancy. No silent cloud fallback.

## Living guides

A guide has purpose/audience, topic links, eligibility/exclusion criteria, ordered sections, curated entries and published revision history. An entry links an entity/concept and contains contextual suitability, requirements, caveats, evidence and review/freshness metadata. Personal introduction/annotations are stored separately from generated proposals and never overwritten by regeneration.

Guide entries are an explicit signal of familiarity and interest. With your confirmation, entities in a guide count as known for discovery and can be added to the Following watchlist. This is personal familiarity, not a registry correction.

Render the article-like view from structured entries; no independently regenerated prose copy that can drift. Imported custom Markdown remains preserved; extraction into structured entries is a reviewed proposal, not an automatic replacement.

Proposal kinds: add entry, update entry, add warning, retire entry, or no useful change. New does not imply recommended. A failed link makes evidence stale/unverified, not the project discontinued. Preserve retired entry history.

Approval checks expected guide revision, referenced entity/claim state and evidence version. Stale proposals need recomputation/review, not last-write-wins. Approved entry/prose changes and revision/audit record commit atomically. Personal edits also create a revision; rejected proposals stay auditable. News acceptance and guide approval are separate transactions.

## Topics, sources and onboarding

- Topics have stable IDs, editable title/scope/exclusions, optional navigation parent and many-to-many entity/article/guide membership. Renames never break identifiers; avoid isolated per-topic registries.
- Sources are explicitly configured with adapters, identity/order rules, schedules and authorization. Attach to topics; submissions supply hints only. No auto-created sources/topics or autonomous discovery.
- First reader setup selects topics, sources, watchlist and quiet backfill window. Setup may also offer an optional empty/template/imported guide with criteria. Topic creation alone neither discovers feeds nor generates a guide.
- Backfill quietly by default, separated from Today, and bounded to recent history (window and per-source maximum, with skipped entries counted in the job result). Today is based on when an article was discovered, not when it was published, and a later poll never imports entries older than the source's backfill cutoff as current. Imported records remain unread; use observation-level backfill intent recorded by authorized use cases, not just age or receipt time. Historical-discovery notifications require explicit opt-in.
- Later source activation previews inputs and backfill scope. Later topic creation optionally reclassifies existing content. Later guide creation searches existing knowledge and proposes entries. Changed guide criteria trigger proposals, not destructive edits.

Backfill processing that finishes after activation must retain its original quiet policy. Do not let replay/restart transform historical imports into current alerts.

## Feedback and correction

“Already knew this” changes personal discovery acknowledgement; it does not erase the entity/event or automatically alter read/save state. “Wrong match” creates a correction request with the affected decision/evidence, not an automatic merge/split.

An approved correction explicitly reassigns/relates impacted records and invalidates affected baselines/analysis/guide proposals for re-evaluation. Preserve decision history, approved guide versions and personal prose; don't silently rewrite published advice. Show corrected/superseded news status and propose dependent guide repairs. Exact merge/split mechanics and recovery tests must be implemented before those actions are exposed.

## Retention and privacy

Retain minimum attributed passages, source URL/identity, revision fingerprint, relevant scope/time and decision provenance for audit, subject to source rights and explicit deletion requirements. Raw full-content retention is configurable; no duration selected yet. No implicit automatic purge until policy and deletion tests exist. If source restrictions require earlier deletion, disable retention for that source explicitly.

Raw-body removal must not silently destroy published provenance: preserve permitted minimal evidence or visibly mark affected records evidence-unavailable. A hash alone is not readable evidence. Redact sensitive content and don't commit corpora; no blanket full-text redistribution or paywall bypass. Backups follow retention/deletion policy; disclose residual backup retention rather than claim deletion from all copies immediately.

## Separate state axes

| Axis | Design states/outcomes |
|---|---|
| Receipt | accepted; validation/auth failures are not accepted receipts |
| Content | pending, obtaining, available, retry-pending, failed |
| Analysis | pending, running, retry-pending, completed, failed; decisions may remain uncertain |
| News publication | proposed, accepted, suppressed, superseded; all linked sources remain accessible where retained |
| Guide proposal | proposed, approved, rejected, stale |
| Execution job | pending, leased, succeeded, failed; leases recover after restart |
| Delivery | pending, attempted, delivered, failed; external retries may duplicate |

These are domain design states, not final wire enums. Completed analysis can result in duplicate/no-change, uncertainty or a proposal; it is not equivalent to news acceptance. Validation before durable receipt, transient execution failures and terminal failures are distinct. Explicit authorized retry creates/requeues attempts without rewriting immutable input.

## Atomic boundaries

1. Ingestion: receipt + supplied snapshot when present + job. URL-fetch acceptance does not require fetched body.
2. Knowledge/news acceptance: validated knowledge changes + accepted publication disposition/card (if eligible) + notification intent (if enabled) + idempotent audit/version update. Shadow proposals are not automatically public news. Deduplicated corroborating evidence may update records without another card/notification. No external calls in the transaction.
3. Guide approval: reviewed diff + expected-revision check + guide revision/audit record (+ optional configured delivery intent). No approval dependency on completing news delivery.

Recheck relevant baseline versions inside final writes and enforce identity/event uniqueness. Retry a stale analysis through re-evaluation, not by committing its old verdict. These behaviors need real PostgreSQL concurrency/recovery tests; framework-independent domain tests alone are insufficient.

## Evaluation gates

Metrics and gates live in the [roadmap](roadmap.md#evaluation-metrics). No automatic suppression or guide auto-approval without user-reviewed evaluation on real data.
