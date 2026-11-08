# ADR 0001: Cohesive standalone modular monolith

**Status:** Accepted. Database choice amended by [ADR 0010](0010-postgres-required-pgvector-deferred.md) (pgvector deferred).

## Context

The primary output is a daily web reader, not chat notifications. Installers should not need any particular private infrastructure. Entity/claim history and user feedback need coherent state; the hard problem is matching precision, not compute scale.

## Decision

One repository owns the reader, ingestion, processing, policy and persistence. Optional adapters connect external collectors (n8n, FreshRSS) and model services. Each installation is independent and single-user.

The backend is a modular monolith backed by one dedicated PostgreSQL + pgvector database, with a separate worker process sharing the backend code and image. The presentation/API stack is chosen in [ADR 0002](0002-astro-django-ninja.md); internal backend layering in [ADR 0003](0003-selective-hexagonal-backend.md).

## Alternatives

- Assembly of existing self-hosted tools (FreshRSS/n8n/Qdrant): quicker initial reuse, but split state and reader constraints undermine portability.
- Microservices/serverless: deployment and coordination costs without a matching-quality advantage.

## Consequences

We own reader UX and minimal durable job semantics. One datastore reduces consistency boundaries. Existing self-hosted tools remain reusable at the edges. No mandatory agent runtime, n8n, Qdrant, Redis or cloud provider. Revisit only with evidence: unsupported UI requirements, concurrency/resource limits, or queue reliability problems.
