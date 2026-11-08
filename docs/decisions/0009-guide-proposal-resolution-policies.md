# ADR 0009: Guide proposal resolution policies

**Status:** Proposed.

## Context

Guide proposals ([content policy](../content-policy.md)) need a human decision: approve or reject. The cost scales with how many guides a user watches. If proposals pile up unreviewed, the queue becomes another inbox of wasted time, and Delta Feed is meant for self-hosters whose tolerance for review work varies.

Silence must not become consent by accident. A wrong version number or a wrongly "abandoned" tool would enter a guide with no human having looked at it.

There is also no real data yet on how many proposals the system produces or how often they are accepted, so any policy beyond manual review would be designed blind.

## Decision

1. **Manual is the only policy in the initial guide release.** Every model-proposed edit waits for an explicit approve or reject. This matches the content policy.
2. **Keep the queue small instead of adding automation.**
   - At most one live proposal per guide entry; a newer proposal for the same entry supersedes the older one.
   - The user can reject proposals in bulk, for example everything older than N days.
   - Proposals are derived and can be regenerated, so rejecting or superseding one loses no knowledge.
3. **Record decision data from day one:** proposal kind, decision, and time to decision, so later policies rest on real acceptance data.
4. **Expire-to-dismissed and auto-accept are deferred.** If added, expiry means *dismissed* (never accepted) and is a distinct `expired` state, not `rejected`. Auto-accept would be opt-in and limited to structured fields with cited evidence, with undoable revisions, and gated on shadow-mode evidence: record what it would have accepted and compare it with the later manual decision, counting only explicit user decisions. A new ADR is required before either ships.

## Consequences

- Behaviour matches the current guardrails; nothing changes a guide without a human decision.
- The queue can still grow for a user who stops reviewing. Supersession and bulk reject reduce that without hiding anything.
- Decision data collected now makes a later policy decision measurable.

## Deferred

Expire-to-dismissed, auto-accept, the default and range of N, per-guide versus global scope, and digest or notification behaviour.
