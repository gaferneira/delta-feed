# ADR 0004: Content and ingestion defaults

**Status:** Accepted.

## Decision

Adopt explicit URL-fetch and provided-text ingestion through one authenticated asynchronous API, source-scoped authorization and collector-scoped idempotency. URL plus text is provided-text; no automatic enrichment. Plain text only initially. Retain completeness and source-revision/observation metadata; arrival order does not define newest content. Quiet backfills are explicit and preserve unread status.

Two outputs share knowledge: meaningful news/discovery events and curated living guides. Topics organize interest, not separate identity registries. Guides render structured entries, preserve personal prose and require review of proposed edits. Start news processing in shadow mode; no automatic hiding or cloud fallback.

Personal acknowledgement is separate from registry corrections. Wrong-match feedback starts review, not automatic entity merge/split. Sources/topics are explicitly administered; ingestion cannot create them implicitly. Retention is configurable and must preserve or visibly account for loss of permitted evidence.

Use separate atomic acceptance boundaries for ingestion, knowledge/news and guide approval, with stale-state checks and immutable provenance. External calls occur outside these transactions. Durable processing completion, publication, suppression and deletion are distinct concepts.

## Contracts

- [Ingestion contract](../ingestion-contract.md)
- [Content and guide policy](../content-policy.md)

## Consequences

Adds guide proposals/revisions, observation ordering, correction audit and independent state axes. Discovery and delta analysis start in shadow mode and also produce reviewable guide proposals; the staging is in the [roadmap](../roadmap.md). Guide entries are an explicit familiarity signal for novelty and can seed the Following watchlist. Guide review never blocks news acceptance. No arbitrary recommendation auto-approval or exact accuracy promises.

## Deferred

Exact DB tables/indexes and port DTOs, numerical limits/retry windows/retention durations, source ordering adapters, model selection/quality thresholds, sophisticated ranking, and offline/multi-user support. Set security/resource limits before exposing endpoints; set retention explicitly before purging or storing restricted sources.
