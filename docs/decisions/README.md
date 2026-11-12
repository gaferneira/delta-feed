# Decisions

One record per decision that is hard to reverse: context, decision, consequences. Delivery order lives in the [roadmap](../roadmap.md); what is built lives in [status](../status.md).

| ADR | Decision | Status | Built |
|---|---|---|---|
| [0001](0001-modular-monolith.md) | One repository, one database, single user | Accepted | Yes |
| [0002](0002-astro-django-ninja.md) | Astro reader, Django Ninja API | Accepted | Yes |
| [0003](0003-selective-hexagonal-backend.md) | Pure core for novelty rules, plain Django elsewhere | Accepted | Yes |
| [0004](0004-content-and-ingestion-defaults.md) | Shadow mode, reviewed guide edits, explicit ingestion | Accepted | Partly |
| [0005](0005-progressive-onboarding.md) | Short setup, familiarity learned while reading | Proposed | Setup only |
| [0006](0006-attention-budget-and-analysis-funnel.md) | Limit attention and model work, not ingestion | Proposed | Bounds and extraction |
| [0007](0007-preference-signals-and-transparent-ranking.md) | Explicit signals, explainable ranking | Proposed | No |
| [0008](0008-delta-page-and-feed.md) | Delta cards per article, Feed hides nothing | Proposed | Delta and Names built; Feed rework not |
| [0009](0009-guide-proposal-resolution-policies.md) | Guide proposals are manual only | Proposed | No |
| [0010](0010-postgres-required-pgvector-deferred.md) | PostgreSQL for real use, no vector search yet | Proposed | SQLite only so far |

Not yet recorded as ADRs, decided during the first real run (2026-11-12): unknown names wait for manual review; a name matches an entity regardless of type; malformed model items are dropped and counted instead of failing the article.

To add one: copy the shape of an existing record, number it next, link it here.
