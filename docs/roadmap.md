# Roadmap

What is next, in order, and what is undecided. What already works is in [status.md](status.md).

Principle: foundations before screens. A screen starts only when the API it shows exists and has been exercised.

## Now

1. **Use the Delta and Names screens for real**: run `make dev` with the worker for a few days and note what slows the name review down. Spec of what was built: [odd/tasks/delta-and-names-screens.md](../odd/tasks/delta-and-names-screens.md).

## Next

2. **A replay command**: give it article ids, it runs extraction and comparison and prints the classifications. This is the five-minute test for any model.
3. **Try a larger model** on the two known cases: the security incident covered by four articles, and the roundup published in two feeds.
4. **Decide the event question** (below) from that result.
5. **Run the worker for a week** on real feeds and read the cards daily.

## Open decisions

| Decision | Options | Blocks |
|---|---|---|
| Repeated coverage of one event lands on different entities | A larger model may be enough; otherwise compare whole articles before the per-entity step | Readiness check, ranking, harness thresholds |
| Which model to require | Decided after step 3 | Deployment guidance |
| Extraction order | Newest first (today), or oldest first so the first report gets the credit and history seeds the baseline | Trial quality |
| Landing page | Build the readiness check and banner, or make Delta home once it has a card | Unit 3 remainder |
| Guides in the first trial | In, or wait | ADR 0009 work |
| Today budget code | Remove once Delta exists, or keep | Feed rework |
| A card with only "not sure" claims | Show on Delta (today), or Feed only | Delta screen |
| Web fonts | Load DM Sans and Manrope (a request to a font host), self-host them, or keep system fonts | Screens |

## Later

In rough order; each needs the items above.

- Feed rework: one list with filters, claim counts and matched duplicates per row; remove Today, Earlier and All.
- Article detail ("Why this card?") and "I already knew this".
- Evaluation harness on a labelled corpus ([Milestone 0](#milestone-0-real-examples)).
- Guide proposal supersession, bulk reject and decision data.
- Deployment: PostgreSQL, Compose, HTTPS, backup and restore, then the first daily trial on a server.
- Ranking, delivery levels, notifications, collector API, event grouping.

## Plans behind the decisions

ADRs record decisions; their delivery phases are here.

### ADR 0005: Progressive onboarding

[ADR 0005](decisions/0005-progressive-onboarding.md).

| Phase | Scope | State |
|---|---|---|
| Account and setup | One-time setup token, first account, topics and starter-pack feeds | Built |
| Familiarity core | Per-user familiarity with history, "already knew this", import from CSV | Not built |
| Triage and bulk | Most-mentioned entities after backfill, roundup shortcut | Not built |
| Nudges and notifications | Suggestions from repeated dismissals, notifications | Not built |

### ADR 0006: Attention budget and analysis funnel

[ADR 0006](decisions/0006-attention-budget-and-analysis-funnel.md).

| Phase | Scope | State |
|---|---|---|
| A. Bounds | Bounded backfill, recurring polling, Today budget | Built |
| B. Model work | Extraction job, daily budget, priority, unanalysed state | Built, run on real articles |
| C. Relevance | Embeddings at ingest, relevance gate before extraction | Not built |
| D. Ranking | Novelty and significance in ranking, card reasons | Not built |
| E. Enforcement | Turn shadow rules into real filtering | Not built |

### ADR 0007: Preference signals and transparent ranking

[ADR 0007](decisions/0007-preference-signals-and-transparent-ranking.md). Not built. Slices: card feedback with topic and source weights; delivery levels and a preferences page; entity-level signals; an exploration slot with a shadow report.

### ADR 0008: Delta page and Feed

[ADR 0008](decisions/0008-delta-page-and-feed.md). Units refer to the [novelty-first reading design](designs/delta-feed-novelty-first-reading.md).

| Step | Scope | State |
|---|---|---|
| Unit 1 | Mentions, claim fields, fingerprint, claim writer | Built |
| Unit 2 | Comparison tiers and jobs | Built, run on real articles |
| Unit 3 | Delta API | Built. Readiness, landing preference and Feed additions not built |
| Unit 4 | Guide proposal supersession, bulk reject, decision data | Not built |
| Unit 5 | Screens | Delta and Names built; Feed rework, banner and guide surfaces not built |
| Unit 6 | Evaluation harness | Not built |
| Tuning | Ranking on Delta, model-written headline, primary sources first | Not built |
| Event grouping | Across articles | See open decisions |

## Milestone 0: Real examples

Evaluation needs real ground truth: what one reader already knew, and what they judged new while reading. [baseline-corpus.md](baseline-corpus.md) is the procedure. Cover mostly-known roundups, renames, forks, repeated announcements, beta to GA changes, contradictions and irrelevant novelty, from more than one kind of source. Keep copyrighted article text local; public fixtures are licensed excerpts or clearly labelled synthetic cases. No labelled corpus exists yet.

### Evaluation metrics

False merges and misses of entities, missed important events, repeated cards, claim classification precision and recall, unsupported claims, the "not sure" rate, name-queue size per day, latency and cost. Targets are set only after reviewing real data. Model-reported confidence and generic similarity thresholds are never release gates.
