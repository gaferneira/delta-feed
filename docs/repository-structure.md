# Repository structure

Status: target layout only. Only docs and Claude skills exist now; see [project status](../README.md#project-status). Do not create placeholder source packages or deploy files to match this tree.

## Target layout

```text
delta-feed/
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── .gitignore
├── .claude/skills/                 # Six existing project review/implementation skills
├── docs/
│   ├── product.md
│   ├── architecture.md
│   ├── content-policy.md
│   ├── ingestion-contract.md
│   ├── technology.md
│   ├── repository-structure.md
│   ├── development-workflow.md
│   ├── roadmap.md
│   └── decisions/
├── starter-packs/                 # Reviewed TOML topic + feed packs offered at onboarding (README inside)
├── frontend/                      # Planned Astro project; no code yet
│   ├── package.json
│   ├── package-lock.json
│   ├── astro.config.mjs
│   ├── tsconfig.json
│   ├── public/                    # Static non-private assets
│   ├── src/
│   │   ├── pages/                 # SSR reader routes; no private build-time data
│   │   ├── layouts/
│   │   ├── components/            # Astro cards/navigation/status UI
│   │   ├── islands/               # Only as real client-state behavior requires
│   │   ├── styles/                # Design tokens and component CSS
│   │   └── lib/api/
│   │       ├── server.ts          # Server-only backend/session client
│   │       ├── browser.ts         # Same-origin fetch/error/CSRF handling
│   │       └── generated/         # Ignored reproducible OpenAPI types
│   └── tests/                     # Frontend unit/component tests
├── backend/                       # Planned Django/Ninja project
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── manage.py
│   ├── src/delta_feed/
│   │   ├── config/                # Django settings/URLs/ASGI/WSGI
│   │   ├── api.py                 # NinjaAPI and router composition
│   │   ├── core/                   # Framework-free novelty/guide policy only (ADR 0003)
│   │   ├── application/            # Use cases, meaningful ports, accepted DTOs
│   │   ├── adapters/               # External/ORM port implementations only as needed
│   │   ├── accounts/              # Django auth/preferences, onboarding state; not custom sessions
│   │   ├── content/               # Sources/articles/revisions/ingestion contracts; source registration use case
│   │   ├── knowledge/             # Identities/topics/claims/evidence; Topic model and starter-pack loader
│   │   ├── analysis/              # Pipeline, policy and run provenance
│   │   │   ├── contracts/          # Provider output validation, not core types
│   │   │   └── prompts/            # Versioned analysis task input
│   │   ├── guides/                 # Curated entries/proposals/prose/revisions
│   │   ├── reader/                # Card/read/save/feedback domain state, not UI
│   │   ├── jobs/                  # Durable scheduling/leases/retry mechanics
│   │   └── delivery/              # Optional outbox/transports
│   └── tests/
│       ├── unit/
│       ├── integration/           # Disposable real PostgreSQL; provider fakes
│       └── fixtures/              # Licensed or labeled synthetic cases
├── tests/e2e/                     # Planned browser tests across frontend/API
├── evaluation/                    # Planned manifests/labels/runner; raw corpus private
├── deploy/                        # Planned images/Compose/same-origin proxy config
├── scripts/                       # Add only exercised generation/maintenance commands
└── .github/workflows/             # Add only verified checks/build jobs
```

Each project owns its dependencies and lockfile; no root npm workspace is needed initially. Decide e2e runner/dependency ownership when scaffolded and avoid duplicate Playwright installations. Generation must happen before frontend type-check/build; ignored generated files cannot be assumed to exist in fresh clones or image builds.

## Backend ownership and dependency direction

Business modules own Django records and ordinary CRUD. The target dependency direction is application → core, adapters → application ports/core, and inbound Ninja/worker handlers → application use cases. core contains plain Python rules/value objects without Django/Ninja/Pydantic/network imports. application ports use explicit framework-independent DTOs; adapters convert ORM/provider values. config/composition wires adapters explicitly. Avoid circular imports and do not mirror every ORM model with a repository/domain class. These paths are target guidance, not created packages.

core/, application/ and adapters/ hold only the novelty pipeline and guide policy described in ADR 0003. Everything else, including ordinary CRUD for content, knowledge, reader and accounts, lives in its business module as plain Django. Rule of thumb: if a rule does not need to run without Django, it belongs in its business module, not core/.

- content owns source/article revisions and ingestion; collectors/API share the same use case. Source registration (and its one-time quiet backfill job) is one use case shared by the Sources API and onboarding.
- knowledge owns entity identities, topics, evidence and scoped claims. `Topic` (shared, stable slug, many-to-many with `content.Source`) and the strict loader for `starter-packs/` live here; `STARTER_PACKS_DIR` overrides the directory.
- analysis owns task schemas, prompts and run provenance; application coordinates core policy and adapters for extraction/matching/acceptance. Provider proposals are not direct writes.
- guides owns curated definitions, entries, personal prose, proposed changes and revisions; approved changes use expected-revision checks in a separate use case/transaction.
- reader owns publication/read/save/feedback data; Astro owns its presentation.
- jobs owns allowlisted durable handlers/leases, not business verdicts.
- delivery owns outbox attempts; external sends are outside transactions.
- accounts reuses Django auth. It also owns per-user onboarding state (`ReaderProfile`, `TopicSelection`) and the onboarding use case, which calls content's source registration and knowledge's topics. API routes are thin adapters; backend authz remains mandatory.

Django models/migrations stay in business modules; nontrivial knowledge reads/acceptance use adapters that satisfy application ports. Simple CRUD can remain Django services. Atomic scopes follow docs/content-policy.md; explicit transaction-owning adapters/services, no generic unit-of-work framework initially. No source-to-inference or UI-to-database shortcuts. Avoid circular dependencies, holding transactions across remote calls, or a giant utils module.

## Contracts and tests

Ninja routers and external schemas belong to relevant backend modules (api.py/schemas.py where suitable); central api.py assembles routes. Analysis/contracts owns model-result schemas separately. Generate TypeScript from OpenAPI, not from ORM internal models. Generated types are reproducible build output; explicit schema-generation command and drift checks are required once implemented.

Unit tests exercise pure behavior; integration tests cover persistence/Ninja contracts/auth/jobs with PostgreSQL; frontend tests cover client behavior; browser e2e covers actual SSR/session/CSRF/mutations. Ninja shortcut test clients alone do not prove cookie/CSRF correctness. Live inference evaluations are opt-in; deterministic CI uses fakes.

Package versioned prompts and test their availability in the backend image. Astro server code/secrets must not enter browser bundles. No application Django templates/static reader layer; Django-owned auth/admin may still use framework templates.

## Incremental creation

Apply accepted ADRs/content policy, then scaffold minimum frontend pages/client and backend config/auth/content/reader needed for login → submit → persist → SSR feed → save/read → reload. Add other modules only with their exercised slice. Versions, auth routing and deploy commands remain pending verification, not working artifacts.
