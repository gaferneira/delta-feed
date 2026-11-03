# ADR 0008: Delta page and chronological Feed

**Status:** Proposed. The delivery order lives in the [roadmap](../roadmap.md#adr-0008-delta-page-and-feed).

## Context

The reader's core pain is wading through repeated content ([product scope](../product.md)). Today, the reader lists whole articles: Today, Earlier and All. Extraction ([architecture](../architecture.md)) already produces scoped claims, and the [glossary](../glossary.md) defines a delta as how a new claim relates to the baseline: duplicate, novel, refinement or contradiction.

Two easy designs miss the point:

- **Summarise each article.** A short model-written summary still repeats what the reader already knows; it is the "list of generated summaries" that [product.md](../product.md) rules out.
- **Group deltas by event across articles.** Closer to the ideal, but it needs reliable event clustering before the main page works at all.

There is also a cold start. With an empty baseline, every claim is novel, so the first days of a delta page would look like a summary feed.

## Decision

### 1. Two pages

| Page | Shows | Order | Model |
|---|---|---|---|
| **Delta** (default after login) | Articles that have at least one non-duplicate claim, as delta cards | Ranked under the [ADR 0006](0006-attention-budget-and-analysis-funnel.md) budget and [ADR 0007](0007-preference-signals-and-transparent-ranking.md) preferences | Yes |
| **Feed** | Every current article: analysed, nothing new, unanalysed, failed | Newest first, no ranking, no budget | No |

- Delta replaces Today as the landing page. Feed absorbs the current All and Earlier lists.
- Read and save state is per article and shared by both pages.
- Feed is the trust valve: nothing the Delta page leaves out is hidden, consistent with shadow mode in the [content policy](../content-policy.md).
- Delta never fills itself with unanalysed articles. While analysis is pending or the model is unavailable, it says how many articles are waiting and links to Feed.

### 2. Delta cards are grouped per article

One card per article, not per event. A card shows:

- A short generated **delta headline**, with the original title and source as secondary text.
- One bullet per non-duplicate claim (novel, refinement, contradiction), labelled with its kind and linked to its evidence passage. Long lists collapse behind "+N more".
- The link to read the original article.

Repeated coverage is still filtered, because novelty is judged against the baseline: once one article's claims are accepted, a later article about the same event shows only the claims the first one lacked. A roundup becomes one card with only its new items.

Claims whose classification is uncertain appear on the card labelled as uncertain. A missed important event is worse than one extra bullet.

### 3. Card text comes only from non-duplicate claims

- The model that writes the headline and bullets receives **only** the article's non-duplicate claims and their evidence, never the full article. It cannot repeat what the reader already knew.
- Each bullet must reference the claim it states; output with an unreferenced bullet is rejected. Prompt and output schema are versioned like the other analysis tasks.
- Card text is derived presentation data, not knowledge. It can be regenerated and never changes claims, entities or the baseline.
- When no card text can be produced, the card falls back to the original title and the claims themselves.

### 4. Cold start: the quiet backfill seeds the baseline

The bounded quiet backfill ([ADR 0006](0006-attention-budget-and-analysis-funnel.md#1-bounded-backfill): at most 30 days and 20 articles per source) is extracted at the lowest priority of the daily model budget. Its claims enter the baseline but never produce Delta cards; the articles stay in Feed. This amends ADR 0006's "backfill is not analysed by default" for this bounded window only; analysing older history remains an explicit action.

The same extraction feeds [ADR 0005](0005-progressive-onboarding.md) triage, and "Already knew this" keeps adjusting familiarity afterwards.

## Consequences

- The landing page shows what changed, not what was published; the full stream stays one click away.
- **Whichever article is analysed first gets the credit.** A weak secondary source can carry a delta while the official announcement shows nothing new. The [roadmap](../roadmap.md#adr-0008-delta-page-and-feed) lists the mitigations; event grouping can come later without changing the card contract.
- Adds a card-text task, its stored output and a backfill extraction cost bounded by the backfill limits.
- If the reader lives in Feed, the Delta page is not doing its job. Usage of both pages is an evaluation signal in the daily trial.

## Deferred

Headline and bullet length limits, the number of bullets before collapsing, how Delta cards rank against each other beyond ADR 0006 and 0007, event grouping across articles, and whether an article with only uncertain claims belongs on Delta or only in Feed.
