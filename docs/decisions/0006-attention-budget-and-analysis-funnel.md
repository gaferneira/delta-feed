# ADR 0006: Attention budget and analysis funnel

**Status:** Proposed. Delivery phases and implementation notes live in the [roadmap](../roadmap.md#adr-0006-attention-budget-and-analysis-funnel).

## Context

The first real run registered 9 starter-pack sources and imported 2,495 articles, reaching back to December 2015. Measured on that data (2026-11-03):

| Window | Articles |
|---|---|
| Last 24 hours | 11 |
| Last 7 days | 64 |
| Last 30 days | 172 |

Two problems hide behind that number:

1. **Backfill is unbounded.** A source's first poll imports every entry in its feed, however old ([content/rss.py](../../backend/src/delta_feed/content/rss.py)).
2. **Daily volume grows with sources and is uneven.** About 10 articles a day today, but one source (OpenAI news) produced 45% of the last month.

Running a local generative model on every article does not scale either: thousands of articles would take hours of inference. The product's goal is quality over quantity, and its worst failure is a missed important event ([product.md](../product.md), [roadmap evaluation metrics](../roadmap.md#evaluation-metrics)).

## Decision

**Limit attention, not ingestion.** Every current article is ingested and stays reachable. What is limited is what Today shows and how much model work runs.

### 1. Bounded backfill

A source's first poll imports only recent history: entries published within the backfill window (default 30 days) and at most a per-source maximum (default 20), whichever is smaller. Skipped entries are counted in the job result, so the bound is auditable, never silent. The window is the "quiet backfill window" that [content policy](../content-policy.md#topics-sources-and-onboarding) already assigns to first setup.

The first poll stores a **backfill cutoff on the source**, and later polls never import entries published before it as current. It is stored rather than derived, so changing the window setting later cannot reopen old history. When the per-source maximum trims entries inside the window, the cutoff rises past the newest trimmed entry, so what the cap left out is history too.

### 2. A daily budget for Today

Today here means the landing page, which [ADR 0008](0008-delta-page-and-feed.md) turns into the Delta page.

- Today is based on when an article was discovered, not when it was published.
- Today shows a ranked budget of cards (default 12, configurable). The rest of the day's articles stay one click away ("More from today") and in All Content. Nothing is hidden by the budget.
- **Source diversity:** a single source fills at most a fixed share of the budget (default 3 cards), so one prolific publisher cannot crowd out the rest.
- **Ranking inputs:** recency and source diversity, preferences ([ADR 0007](0007-preference-signals-and-transparent-ranking.md)), delivery level ([ADR 0005](0005-progressive-onboarding.md#delivery-levels)), novelty and event significance.
- Cards are per article, as decided in [ADR 0008](0008-delta-page-and-feed.md); grouping several articles about one event is deferred there.

### 3. The analysis funnel

Each stage is cheaper than the next and narrows what reaches it:

| Stage | Work | Generative model | Trigger |
|---|---|---|---|
| 1. Ingest | Fetch, dedupe by URL and content hash | No | Worker, on poll |
| 2. Cheap filters | Muted topics and sources, backfill flag | No | After ingest |
| 3. Relevance | Embedding similarity to selected topics and known entities, plus preference weights | Embeddings only | After ingest |
| 4. Extraction | Entities and scoped claims | **Yes** | Worker job, gated by stage 3 and the daily model budget |
| 5. Novelty | Claims compared against the registry and the reader's familiarity | Only to adjudicate ambiguous matches | After extraction |
| 6. Ranking | Budget, diversity, reasons | No | When the feed is read |

Rules for model work:

- **The model runs in the worker, triggered by ingestion,** as an `analysis.extract` job. It never runs while a page is being read.
- **A daily model budget** (a count of extraction jobs, configurable) bounds cost. When it is exhausted, remaining articles wait for the next day's budget or stay unanalysed.
- **Priority:** `notify` topics first, then by relevance score, then recency.
- **Backfill is not analysed by default.** Analysing history is an explicit, bounded action. Exception: [ADR 0008](0008-delta-page-and-feed.md#4-cold-start-the-quiet-backfill-seeds-the-baseline) extracts the bounded quiet backfill at the lowest priority to seed the baseline, without producing cards.
- **Unanalysed is a visible state, never a hidden one.** An article the funnel did not reach is shown as unanalysed, consistent with "unknown/failure stays reviewable".

### 4. Shadow mode first

Filtering decisions (stages 2, 3 and 5) are recorded with their reason and shown as "would have been filtered" before they hide anything. Hiding is enabled per rule only after the decisions are evaluated against real reading data, starting with the [baseline corpus](../baseline-corpus.md) daily logs.

## Consequences

- Volume stops being a function of how many sources exist; attention and model cost become explicit, configurable budgets.
- Today can omit an important article that ranks below the budget. Mitigations: overflow is one click away, `notify` and security events outrank everything else, and evaluation measures misses before any hiding is enabled.
- Adds job types, a budget ledger and per-article analysis states.

## Deferred

Exact defaults (window, per-source maximum, budget sizes, diversity share), the model budget's unit (jobs or tokens), the embedding model, relevance thresholds, the significance taxonomy, and how a reader changes the budgets.
