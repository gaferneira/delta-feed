# Delta Feed

A self-hosted reader that shows what is new to you. It breaks each article into the things it mentions and what it says about them, compares that with what earlier articles already said, and shows only the difference.

> **Status: early, runs locally, not deployed.** The pipeline from RSS to a Delta card works on real articles with a local model. The Delta and Names screens exist; daily use has not started. See [docs/status.md](docs/status.md).

## The problem

- A ten-item roundup contains one project you have not seen.
- Five articles announce the same release.
- An RSS reader shows all of them and leaves the comparison to you.

## How it works

1. **Ingest.** RSS feeds are polled on a schedule; you can also submit an article by hand.
2. **Extract.** A model you choose (local by default) lists the things an article mentions and its claims about them, each with the sentence it came from.
3. **Review names.** A name the system has not seen waits for you, once: track it, mark it the same as something already tracked, or ignore it. Nothing joins your baseline unreviewed.
4. **Compare.** Each claim is checked against what is already known about that thing: duplicate, new, changed, conflicting, or not sure.
5. **Read.** Delta shows one card per article with only the claims that are not duplicates. Feed lists every article, so nothing is hidden.

A second feature, living guides, keeps your own reference articles as structured entries and proposes changes with evidence. Nothing changes without your approval.

## Quick start (local development)

Needs [uv](https://docs.astral.sh/uv/) and Node 22.

```sh
cp .env.example .env     # then set the model provider if you want analysis
make init                # install dependencies, migrate, create the first user
make dev                 # backend :8000, worker, frontend :4321
```

Open <http://localhost:4321>. Without a model configured, the reader works as a plain feed reader. Commands, settings and conventions are in [docs/development.md](docs/development.md).

## Documentation

| Read this | To find |
|---|---|
| [docs/product.md](docs/product.md) | Who it is for, the daily loop, what is out of scope |
| [docs/status.md](docs/status.md) | What works, how it was verified, known problems |
| [docs/architecture.md](docs/architecture.md) | The pipeline as built, where the code lives, the rules it keeps |
| [docs/roadmap.md](docs/roadmap.md) | What is next and which decisions are open |
| [docs/development.md](docs/development.md) | Setup, commands, settings, how to contribute a change |
| [docs/README.md](docs/README.md) | The full index, including decisions and designs |

[AGENTS.md](AGENTS.md) holds the rules for coding assistants.

## Data and privacy

Everything stays in your own database. No cloud inference runs unless you configure it; a hosted endpoint receives article text. Source excerpts, credentials and private configuration are never committed.

## License

Copyright © 2026 Gabriel Neira. [GNU Affero General Public License v3.0](LICENSE): use, modify and redistribute freely; a modified version that you distribute or offer over a network must publish its source under the same license.
