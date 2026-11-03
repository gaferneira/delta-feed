# Building your baseline corpus

**Audience:** contributors who want to evaluate or improve the novelty engine. You don't need any of this just to use Delta Feed: the reader learns what you know progressively ([ADR 0005](decisions/0005-progressive-onboarding.md)).

Delta Feed decides what is new *to you*. To build and measure that, the project needs real ground truth: what a reader already knew, and what they actually judged as new while reading, including the items an engine would have missed. This is [Milestone 0](roadmap.md#milestone-0-real-examples).

It takes about 30 minutes once, then about 5 minutes a day for two weeks.

## Where your data lives

Everything personal goes in `local-corpus/` at the repository root. Git ignores it. Never commit its contents: they describe your setup and contain copies of copyrighted articles.

```text
local-corpus/
├── known.csv         # your baseline (from docs/templates/known.csv)
├── daily-log.csv     # one row per item mentioned (from docs/templates/daily-log.csv)
└── articles/         # local copies of what you read, named <date>-<slug>.md or .html
```

Set it up:

```sh
mkdir -p local-corpus/articles
cp docs/templates/known.csv docs/templates/daily-log.csv local-corpus/
```

## Step 1: write your baseline

Fill in `local-corpus/known.csv`, one row per thing you know: a tool, library, project, hardware, service or practice. Its columns match the planned `import_known` format, so this file can be imported into Delta Feed later.

| Column | Meaning |
|---|---|
| `topic` | Your grouping, for example `AI tooling` or `Home automation` |
| `name` | The thing itself. One entity per row: split "Linear & Sentry" into two rows |
| `aliases` | Other names **an article would use**, separated by `;` (for example `HA;home-assistant/core`). Not your hostnames, and not names shared with other things ("Claude" for Claude Code would match every Claude model) |
| `kind` | `tool`, `library`, `project`, `hardware`, `service` or `practice` |
| `familiarity` | `use` (part of your setup) or `heard` (you know it exists, or tried it and moved on) |
| `last_known_state` | The version or status you're aware of (`v0.9`, `beta`, `abandoned`), or blank. Not where it's installed |
| `delivery` | `notify` (ordered first, notify on significant events), `show`, or `mute`. Blank inherits the topic's level |
| `notes` | Anything else, kept short |

Example rows:

```csv
topic,name,aliases,kind,familiarity,last_known_state,delivery,notes
Home automation,Home Assistant,HA;home-assistant/core,project,use,2026.10,notify,central hub
AI tooling,Ollama,ollama/ollama,tool,use,v0.9,show,
```

Interests that aren't a single thing ("local LLMs", "RAG") are topics, not rows. Stop after 30 minutes; gaps show up during daily logging, and you add them then.

If an AI assistant already holds memory about your tools and setup, [baseline-export-prompt.md](templates/baseline-export-prompt.md) asks it to export this CSV. Verify every row it marks `inferred` before keeping it. A wrong "familiar" entry hides real discoveries later.

## Step 2: log what you read, daily

While you read (not afterwards), add one row to `local-corpus/daily-log.csv` per **item mentioned**, not per article. A roundup of ten projects gives ten rows.

| Column | Meaning |
|---|---|
| `date` | Day you read it, `YYYY-MM-DD` |
| `url` | Original article URL |
| `item` | The tool, project, hardware or practice mentioned |
| `says` | What the article claims about it, in a few words |
| `verdict` | `new`, `update`, `repeat` or `irrelevant` |
| `why` | The reason, in your words. This is the most valuable column |

Verdicts are judged against `known.csv` plus everything you logged earlier:

- **new:** you had never encountered it.
- **update:** you knew it, and this is a meaningful change (release, status change, security issue).
- **repeat:** nothing you didn't already know.
- **irrelevant:** new or not, you don't care.

When something new becomes familiar, add it to `known.csv`. Save a local copy of each article in `local-corpus/articles/`, because links rot and the text is needed later to test extraction.

## Step 3: after two weeks

1. Pick about 20 varied cases (roundups, the same announcement from several sources, beta to GA, renames, forks) and expand them into worked examples using the format in [roadmap.md](roadmap.md#milestone-0-real-examples).
2. Run a cheap baseline: your feed plus one model prompt given `known.csv`, asked to flag only new or updated items. Score it against your verdicts.

The rows where the cheap baseline fails tell you what the real pipeline must do better.

## Sharing results

Share findings, not data: verdict counts, error categories, and the reasoning patterns from your `why` column. Public fixtures must be licensed excerpts or clearly labelled synthetic scenarios (see [content-policy.md](content-policy.md)).
