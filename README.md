# Delta Feed

A self-hosted reader with two jobs: show you what is actually new (unfamiliar projects and meaningful updates) without repeating what you already know, and keep your own reference articles up to date.

> **Status:** design only. There is no application, API, installable image or deployment yet. See [Project status](#project-status).

## The problem

A ten-item roundup may contain only one project you haven't seen. Five articles may announce the same feature. Reading all of them to find the one new thing is wasted time.

Meanwhile, the articles you actually rely on, such as "Recommended skills every project should have" or "Raspberry Pi projects for home automation", go stale quietly: a recommended tool gets a major release, another is abandoned, a better option appears.

## What Delta Feed does

- **News about new things.** It breaks articles into the things they mention (tools, libraries, projects, hardware, practices) and the claims they make about them ("version 2 adds ARM support", "now generally available"). It compares those against what it has already seen and surfaces the genuine discoveries and changes, always linked to the original sources. When it is unsure, it says so; it never silently hides content.
- **Living guides.** You keep your own articles as structured entries plus your own writing. When the news shows that an entry should be added, updated, warned about or retired, Delta Feed proposes the change with evidence. Nothing changes until you approve it, and your own text is never overwritten.

The two reinforce each other: news produces guide proposals, and what is already in your guides tells Delta Feed what you know and care about.

Software, AI and home-automation hardware are the first interests, but topics are configuration, not hardcoded categories.

## MVP

- Responsive web reader with Today, Discoveries, Following, Saved and All Content views.
- Built-in RSS/Atom, manual submission, and an authenticated ingestion API for external collectors such as n8n.
- Entity resolution using strong identifiers, similarity candidates and bounded model adjudication.
- Claim comparison that respects version, platform and availability, with source evidence.
- Read/save state plus "already knew this" and "wrong match" feedback.
- Pending, failed, uncertain and suppressed content stays inspectable.
- Guides: manual structured entries with your notes and revision history first; reviewed, evidence-backed update proposals once analysis exists.
- Configurable inference and embedding providers; local Ollama first.

Out of scope: multi-user hosting, autonomous browsing or source discovery, arbitrary scraping, and complex recommendation systems.


## How it will work

- **Reader:** Astro, server-rendered, TypeScript.
- **API and backend:** Django, with Django Ninja for the JSON API. Django also handles login, the database layer and business logic.
- **Storage:** PostgreSQL with pgvector.
- **Background worker:** a separate Python process sharing the backend image.
- **Models:** a local Ollama instance by default; no cloud inference unless you explicitly configure it.

Everything ships as one repository and one Compose installation. Built-in RSS and direct Ollama support make it standalone; FreshRSS, n8n, Telegram and agent runtimes are optional integrations, never requirements.

## Project status

This section is the single place that tracks project status; other documents link here.

- **Decided:** standalone modular monolith ([ADR 0001](docs/decisions/0001-modular-monolith.md)), Astro + Django Ninja ([ADR 0002](docs/decisions/0002-astro-django-ninja.md)), selective hexagonal backend ([ADR 0003](docs/decisions/0003-selective-hexagonal-backend.md)), content and ingestion defaults ([ADR 0004](docs/decisions/0004-content-and-ingestion-defaults.md)).
- **Pending:** database schema, port payloads, numerical limits and retention windows, dependency versions.
- **Not yet exercised:** any code, install, run or test command. The stack has not been compatibility-tested.

**Next step:** [Milestone 0](docs/roadmap.md#milestone-0-real-examples): collect real articles, write down the reader cards you would expect from them, and capture one or two of your guides with the changes you would expect. Then build the smallest authenticated submit → persist → render → read/save slice without AI, followed by manual guides. Model analysis comes after, in shadow mode.

There are intentionally no installation commands yet; they will be added once a scaffold has actually been run.

## Documentation

1. [Glossary](docs/glossary.md)
2. [Product scope and acceptance](docs/product.md)
3. [Architecture and reliability](docs/architecture.md)
4. [Technology selection](docs/technology.md)
5. [Architecture decisions](docs/decisions/)
6. [Repository layout and module ownership](docs/repository-structure.md)
7. [Development workflow and Claude skills](docs/development-workflow.md)
8. [Roadmap and evaluation](docs/roadmap.md)
9. [Ingestion contract](docs/ingestion-contract.md)
10. [Content, guide and publication policy](docs/content-policy.md)

[AGENTS.md](AGENTS.md) defines implementation guardrails for coding assistants.

## Data and privacy

The application database owns articles, identities, claims, jobs, feedback and reading state. Git owns code, tests, technical decisions and deployment instructions. Personal planning lives outside this repository, and the news stream is never copied automatically into personal notes.

No cloud inference is enabled implicitly. Source excerpts, credentials and private infrastructure configuration must never be committed.

## License

Copyright © 2026 Gabriel Neira. Licensed under the [GNU Affero General Public License v3.0](LICENSE).

You may use, modify and redistribute Delta Feed freely. If you distribute a modified version, or let others use it over a network, you must make its source available under the same license.
