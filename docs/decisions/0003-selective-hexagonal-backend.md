# ADR 0003: Selective hexagonal backend

**Status:** Accepted.

## Decision

Keep the Django backend a modular monolith. Isolate the novelty core as framework-independent Python domain rules/value objects for scoped identity, claim relationships, uncertainty and publication eligibility. Domain code must not import Django, Ninja, HTTP clients or provider-specific response types.

Application use cases coordinate the core and small ports for content fetching, language analysis, embeddings/candidate retrieval, historical baseline loading and transactional acceptance/publication. Ninja endpoints and worker handlers invoke the same use cases. ORM/network/provider adapters implement these boundaries. Wire dependencies explicitly at the composition boundary; no dependency-injection framework initially.

Use conventional Django services/ORM for login, admin, source settings and straightforward read/save operations. Do not invent a generic repository for every table or duplicate every persistence record as a domain object. Convert to domain values where the business rules require independent representations.

## Alternatives

Full hexagonal layering adds interfaces/mapping to routine CRUD without demonstrated benefit. Conventional Django-only domain services make independent novelty evaluation and integration replacement harder. Selective boundaries preserve both testable policy and straightforward framework use.

## Verification obligations

Pure domain tests establish business-rule behavior, not persistence reliability. Real PostgreSQL integration tests must verify uniqueness, leases, stale-state rechecks, atomic publication and concurrent processing. Network/model calls occur outside long-lived database transactions; final writes revalidate relevant baseline state.

## Deferred

Atomic acceptance scopes are set in [ADR 0004](0004-content-and-ingestion-defaults.md). Detailed port payloads, persistence schemas, correction mechanics and durable job design. Acceptance does not authorize a generic framework.
