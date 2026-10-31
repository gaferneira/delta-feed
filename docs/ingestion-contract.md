# Ingestion contract — v1 design

**Status:** Accepted behavior and input modes; not an implemented endpoint or executable schema. Exact limits, idempotency retention and wire enums must be locked and tested during scaffolding.

## Boundary

External collectors (including n8n), manual submission and built-in RSS enter the same ingestion use case. Collectors submit observations, not prompts, novelty verdicts or guide edits. Create sources/topics explicitly through authenticated administration, not as ingestion side effects.

Proposed route: POST /api/v1/ingestions, authenticated by revocable scoped bearer credentials for collectors. Browser submissions use Django sessions and enforced CSRF. Authorize source access and status retrieval; an ingestion identifier is not an access credential. Use a required Idempotency-Key header scoped to the collector principal. Store token hashes and never log raw tokens.

## Explicit input modes

| Mode | Required | Behavior |
|---|---|---|
| fetch_url | Configured source_id and public HTTP(S) URL | Worker fetches/extracts within security/resource bounds. No supplied body allowed. |
| provided_content | Configured source_id, title, nonempty text body, completeness, and URL or stable external_id | Analyze supplied text only; URL is attribution, not fetch permission. |

URL + body is provided_content, not an implicit third mode. Never switch modes automatically or silently replace an excerpt with a fetched document. Enrichment is a separate explicit observation through the normal pipeline.

## Envelope

- source_id: stable configured source identifier authorized for the sender.
- external_id: source-scoped identity; required if URL absent. Not an idempotency key or proof of document freshness.
- url: original source URL; required in fetch mode, optional provenance in supplied-text mode. Normalize conservatively; no broad query stripping that merges different articles.
- title: optional fetch hint; required with supplied content.
- published_at: optional timezone-aware source time. Unknown stays unknown; receipt time is separate.
- topic_hints: optional existing topic IDs, never trusted classification or instructions to create topics. Reject unknown/unauthorized references with field errors.
- content (provided_content only): format=text; body; completeness=full|excerpt|unknown; optional extraction_method. Completeness is a sender assertion, retained as provenance rather than guaranteed truth.
- source_revision_id: optional opaque source version identifier, not lexically sortable by default.
- source_modified_at: optional timezone-aware source modification time.
- observed_at: optional timezone-aware collector observation time.

Server records received_at, authenticated collector and its own fingerprints. Preserve source/collector metadata but do not trust it as an authorization or freshness guarantee. Reject unknown fields, incompatible mode fields and malformed values using discriminated Pydantic/Ninja schemas. Never truncate silently. Plain text only initially; HTML/Markdown require a future explicit parsing contract.

## Examples (illustrative, not retrieved content)

```json
{
  "mode": "fetch_url",
  "source_id": "software-feed",
  "external_id": "entry-123",
  "url": "https://example.org/news/release",
  "topic_hints": ["software"]
}
```

```json
{
  "mode": "provided_content",
  "source_id": "software-feed",
  "external_id": "entry-123",
  "url": "https://example.org/news/release",
  "title": "Release announcement",
  "content": {
    "format": "text",
    "body": "Illustrative original text supplied by a collector.",
    "completeness": "excerpt",
    "extraction_method": "rss-description"
  },
  "source_revision_id": "revision-b",
  "observed_at": "2026-10-31T12:00:00Z"
}
```

## Durable acceptance and status

A new accepted submission returns 202 only after receipt, supplied snapshot (if present) and job are committed. A fetch receipt can exist before there is any article body. Proposed response includes ingestion_id, current status and status_url pointing to GET /api/v1/ingestions/{id}. Acceptance is not analysis/publication success.

Expose stages/outcomes separately: content, analysis, publication, plus retryable/terminal errors and resulting article revision/event references. Fetch failure means no obtained full article; show available metadata and error, not an invented readable body. Successful no-new-content analysis is not a processing failure. Guide proposals have their own status.

Keep status polling initially. No callback URL accepted; callbacks introduce an outbound trust boundary.

## Idempotency and article observations

- Same principal + key + normalized request fingerprint: same receipt, no second job. Return the receipt's current state even if analysis already finished.
- Same key, different payload: 409 conflict; no overwrite. Concurrent retries obey a database unique constraint.
- Different key, same article: preserve the new observation; unchanged body can share an immutable content revision. Fetch workers determine changed content, not the HTTP acceptance layer.
- Changed body: new revision and analysis; previous evidence remains addressable.
- Multiple sources covering one event: keep source documents; resolve duplicate events downstream.

n8n keys identify observations/versions, not an RSS GUID reused forever. Retain keys for a documented retry window; beyond it article/revision and publication constraints still protect domain state. Exact retention window remains to be set before enabling collectors.

## Revision ordering

Arrival order is not document version order. Preserve delayed/backfilled observations without letting them blindly replace the current revision. Prefer explicit trustworthy source version/order rules where available; collector timestamps are supporting evidence, not guaranteed truth. Opaque version IDs alone establish equality, not ordering.

If order or full-vs-excerpt relationship is ambiguous, keep both observations with uncertain precedence and do not treat the new arrival as a correction/removal. Enrichment can be a different representation of the same source version rather than proof of a newer version. Scoped claims/events may still be valid even from historical revisions; keep publication/discovery time distinct. Decide each source's ordering strategy explicitly and test delayed replay.

## Errors and resource policy

Proposed HTTP semantics: 401 unauthenticated, 403 forbidden source/status scope, 409 idempotency conflict, 413 oversized, 422 invalid schema/references, 429 rate limited, 5xx transient acceptance failure. Worker source/model failures appear on the persisted status rather than retroactively rejecting an accepted request. Safe error payloads must not expose tokens, internal URLs or source bodies.

Define and test finite byte/text limits, fetch/decompression bounds, timeouts, redirects, concurrency and retry budgets before exposure. Reject private/loopback/link-local/metadata fetch destinations by default, validating redirects and resolved/connected addresses. Do not weaken this boundary to connect n8n: it can provide content from an authorized private collector. URL provenance in provided mode is never auto-fetched.

## n8n behavior

Normalize input, pick explicit mode, supply authorized source and observation key, POST, and advance collection state only after durable acceptance. Retry uncertain network/transient failures with the same key and payload. Handle 401/403/409/413/422 as actionable errors; honor rate-limit backoff. Poll status if desired; do not resubmit a failed job with new keys as a substitute for an authorized retry action. No model invocation required in the collector.
