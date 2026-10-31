# Technology selection

Status: selections are decided but not implemented or compatibility-tested. See [project status](../README.md#project-status) and the [ADRs](decisions/).

| Responsibility | Selection | Reason / trade-off |
|---|---|---|
| Reader frontend | Astro SSR + TypeScript + CSS | Content-first layouts and selective interactivity; requires a frontend build and runtime. Personalized feeds render on demand, not static rebuilds. |
| Frontend runtime | Node adapter candidate | Self-hosted SSR packaging; adapter/runtime versions verified at scaffold time. |
| Interactive UI | Small scripts/islands; React optional | Do not hydrate the entire reader by default. No HTMX layer. Offline queued actions are not an MVP promise. |
| API | Django Ninja | Typed Pydantic-based input/output contracts and OpenAPI, integrated with Django. Authz, object ownership and failure semantics still our responsibility. |
| Backend | Python + Django | ORM, migrations, sessions/auth and admin. Ninja endpoints and worker invoke backend services; selective framework-independent core/application ports with concrete adapter boundaries are defined in the target layout; detailed DTOs and schemas are implemented per slice. |
| Database | Dedicated PostgreSQL + pgvector | Relational and vector state together; no SQLite/Qdrant synchronization requirement. |
| Worker | Django command + durable DB jobs | Same backend image, separate process; own modest leasing/retry semantics initially. |
| API types | OpenAPI-generated TypeScript | openapi-typescript candidate; lock tool and verify regeneration in CI. Separate generation from small handwritten fetch client. Types do not provide runtime validation. |
| Source adapters | feedparser, HTTPX, trafilatura candidates | RSS, bounded fetch/extraction; not arbitrary JS/paywall coverage. |
| Analysis validation | Pydantic | Separate versioned model-task schemas; no blind reuse of external API schemas. |
| Inference | Direct Ollama first | Configurable providers; no implicit paid/cloud fallback, no agent required. |
| Embeddings | bge-m3 candidate | Evaluate and pin digest/dimension; re-index explicitly on change. |
| Python tooling | uv, pytest, Ruff | Managed locked dependencies and deterministic tests. |
| Frontend tooling | npm + lockfile, Astro check/TypeScript, Vitest candidate | Verify commands when scaffolded; avoid several package managers. |
| Browser tests | Playwright | SSR/login/API mutations, mobile UX, source safety and private cache behavior. |
| Packaging | Compose: frontend, api, worker, db, same-origin proxy | Astro image plus shared backend API/worker image; use generic routing, not required host-specific services. |

## Alternatives

- Django templates/HTMX: simpler single runtime; not selected (see ADR 0002).
- React SPA/Next.js: not selected; reconsider if persistent client/offline interaction becomes central.
- FastAPI: unnecessary alongside Django Ninja and Django ORM/auth.
- DRF: richer API conventions but not required for our bounded typed API.
- SQLite/Qdrant, Celery/Redis and LiteLLM: deferred pending demonstrated operational need.
- External agent runtimes: optional adapter only after verified isolation/authentication/response contract/provider permission.

## Version policy

Verify supported Python/Django/Ninja/Pydantic/Postgres/pgvector and Node/Astro/adapter combinations before scaffold. Lock both dependency environments and pin image versions. No floating production images, guessed compatibility, or untested ARM64/AMD64 claims.

## Auth and deployment

See [architecture: frontend/API boundary and authentication](architecture.md#frontendapi-boundary-and-authentication) and [deployment and operations](architecture.md#deployment-and-operations).
