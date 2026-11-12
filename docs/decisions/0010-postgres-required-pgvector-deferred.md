# ADR 0010: PostgreSQL required for deployment, pgvector deferred

**Status:** Proposed. Amends the database choice in [ADR 0001](0001-modular-monolith.md).

## Context

[ADR 0001](0001-modular-monolith.md) selects one PostgreSQL + pgvector database. The code runs on SQLite by default for development and tests, and switches to PostgreSQL with `DB_ENGINE=postgresql`. Two questions came up while reviewing the core idea:

- Is SQLite acceptable for real use, on a homelab server?
- Does the first release need pgvector?

Worker job leasing (`select_for_update(skip_locked=True)`) and claim classification (an entity-level `select_for_update` in `record_claim`) rely on row locks so two worker jobs cannot both classify the same claim as new. SQLite does not honour these locks, and the repository's own tests note that its test database cannot model simultaneous writers. Entity embeddings are stored portably as JSON vectors (`EntityEmbedding`) and candidates are ranked in Python; nothing populates them in the pipeline yet. Claims are compared within one entity's baseline, which is typically a small set.

## Decision

1. **One database, always.** No split across engines or by data type.
2. **PostgreSQL is required for any deployment or daily-trial use.** SQLite remains supported only for local development and automated tests, where no concurrent workers run.
3. **pgvector is optional until embeddings are used.** The first release compares claims within an entity's baseline and does not need database-side vector search; entity candidate search uses the existing JSON-vector ranking. The extension is added by a migration when an embedding feature is built and evaluated, not before.
4. **No platform compatibility claim is made until tested**, per the [stack notes](../architecture.md#stack).

## Consequences

- Concurrency guarantees hold in the only mode used for real data.
- The standalone install stays a Compose stack with a database service; there is no single-file option.
- Tests on SQLite do not prove locking behaviour, so concurrency tests must also run against PostgreSQL before the trial.
- Lighter initial database requirements, since the vector extension is not needed yet.

## Deferred

Whether embeddings are ever needed, and the embedding model and index type.
