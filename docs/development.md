# Development

## Setup

Needs [uv](https://docs.astral.sh/uv/) and Node 22 (the Makefile loads it through nvm when present).

```sh
cp .env.example .env
make init     # uv sync, migrate (SQLite), create the first user, npm install
make dev      # backend :8000, worker, frontend :4321; Ctrl-C stops all three
```

`make dev` loads `.env`; variables already set in your shell win. Django itself reads only the process environment, so tests never see `.env`. To run one backend command with your settings: `cd backend && uv run --env-file ../.env python manage.py <command>`.

## Commands

| Command | Does |
|---|---|
| `make test` | Backend pytest and frontend vitest |
| `make lint` | Ruff on the backend |
| `make format` | Ruff format and autofix |
| `make typecheck` | TypeScript check on the frontend |
| `make build` | Astro production build |
| `make migrate` / `make makemigrations` | Apply or generate migrations |
| `make run-worker` | Worker alone: polls feeds, runs analysis jobs |
| `make setup-token` | Print a new first-run setup token |
| `make help` | Every target |

After changing a model: `cd backend && DJANGO_DEBUG=true uv run python manage.py makemigrations --check`.

## Settings

All optional, set in `.env`. Defaults in brackets.

| Variable | Purpose |
|---|---|
| `DJANGO_DEBUG` | `true` for local use. Without it, `DJANGO_SECRET_KEY` is required and cookies are `Secure` |
| `ANALYSIS_PROVIDER` | `ollama` or `openai_compatible`. Analysis runs only when the provider is configured |
| `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_MODEL`, `OPENAI_COMPAT_API_KEY` | LM Studio or another OpenAI-compatible server. A hosted endpoint receives article text |
| `OLLAMA_HOST`, `OLLAMA_MODEL` | Ollama |
| `ANALYSIS_DAILY_BUDGET` [50], `ANALYSIS_TIMEOUT_SECONDS` [300], `ANALYSIS_MAX_BODY_CHARS` [20000] | Model work limits |
| `BACKFILL_DAYS` [30], `BACKFILL_MAX_ITEMS` [20], `RSS_POLL_INTERVAL_MINUTES` [30] | Ingestion limits |
| `TODAY_BUDGET` [12], `TODAY_PER_SOURCE_CAP` [3] | Today view |
| `MENTION_UNDO_SECONDS` [20] | How long a name decision can be undone before its claims are compared |
| `DB_ENGINE` [`sqlite`], `SQLITE_PATH`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Database. `postgresql` is supported in settings and not yet tested |

The model name in `.env` must match one your server is serving; check with `curl $OPENAI_COMPAT_BASE_URL/models`.

## Making a change

1. Read [status.md](status.md) and the part of [architecture.md](architecture.md) you will touch. For ingestion or publication, also [content-policy.md](content-policy.md) and [ingestion-contract.md](ingestion-contract.md).
2. Work on a branch. Keep one migration file per commit. Use [Conventional Commits](https://www.conventionalcommits.org/).
3. For work with more than one step, keep a task file under `odd/tasks/` with the objective, scope and a checklist; tick an item only after seeing it work.
4. Run `make test`, `make lint` and, for frontend changes, `make build`.
5. Exercise the behaviour for real where you can, and say exactly what you ran. "Tests pass" and "it works on real articles" are different claims.
6. Update [status.md](status.md) when what works changes. A hard-to-reverse decision gets an ADR in [decisions/](decisions/README.md).

Never commit secrets, the dev database, downloaded articles (`local-corpus/` is ignored) or private hostnames.

## Running a model check

Live model runs are explicit, never part of the test suite. Use a copy of the database when experimenting: the dev database is a single file, `backend/db.sqlite3`.

## Review skills for Claude Code

Project skills live in `.claude/skills/`. Reviews report findings and do not change code.

| Invoke | Reviews |
|---|---|
| `/backend-code-review` | API contracts, sign-in and CSRF, writes, queries, jobs |
| `/frontend-code-review` | Server rendering, API use, phone width, accessibility |
| `/novelty-evaluation` | Identity and claim comparison changes, prompts |
| `/ingestion-security-review` | Fetching, hostile content, limits |
| `/database-migration-review` | Constraints, data changes, concurrency |
| `/implement-vertical-slice` | Builds one small feature across the needed layers |

A finding states the file and line, the failure scenario, the impact and the smallest fix.
