# ADR 0007: Preference signals and transparent ranking

**Status:** Proposed. Delivery slices live in the [roadmap](../roadmap.md#adr-0007-preference-signals-and-transparent-ranking).

## Context

[ADR 0006](0006-attention-budget-and-analysis-funnel.md) gives Today a daily budget, so the order of articles decides what the reader sees. That order must reflect what this reader cares about. [Product scope](../product.md#independent-concepts) requires starting from explicit preferences and watchlists, not opaque learned ranking, and the [content policy](../content-policy.md#feedback-and-correction) keeps personal feedback separate from registry corrections.

When this was decided, the only things that could be learned from without a model were the topics chosen at onboarding (so every article has topics through its source) and per-article read and save state. There was no feedback action, no delivery level ([ADR 0005](0005-progressive-onboarding.md#delivery-levels)), no entity-level familiarity and no extraction output.

## Decision

Learn preferences from **signals the reader gives on purpose**, turn them into a **transparent score**, and show the reasons on every card.

### Signals

| Signal | Strength | Target |
|---|---|---|
| Delivery level (`notify` / `show` / `mute`) | Explicit rule | Topic, entity, source |
| "Not interested" on a card | Strong negative | The card's source and topics |
| "More like this" on a card | Strong positive | The card's source and topics |
| "Already knew this" | Familiarity, not interest | The card's entities ([ADR 0005](0005-progressive-onboarding.md)) |
| Save | Weak positive | Source and topics |
| Open the original | Weak positive | Source and topics |

Reading time, scroll depth and other passive tracking are not collected: they are noisy and invasive, and a personal tool does not need them.

### Rules

- **Append-only events.** Every signal is stored as an event with its origin and time, and can be undone. Learned weights are derived from events and can be recomputed or reset at any time.
- **A transparent linear score**, not a black box: named components (topic weight, source weight, delivery level, novelty, significance, recency), each bounded, with older feedback decaying over time.
- **Reasons on every card.** The top contributing components are shown, for example "AI · you marked similar items as useful" or "New · you follow Ollama".
- **Feedback never mutes on its own.** Repeated negative feedback about a source or topic produces a suggestion to mute it, which the reader confirms (the same rule as ADR 0005 nudges).
- **Overrides stay on top.** `notify` items, security advisories and deprecations about things the reader uses rank above learned weights.
- **An exploration slot.** One or two cards a day come from below the cut line, so the feed can't narrow itself into a bubble. They are labeled as such.
- **A preferences page.** The reader can see every learned weight, the events behind it, and undo or reset them.
- **Interest is not familiarity.** "Not interested" lowers rank; "already knew this" changes novelty. They are separate events and never imply each other.

## Consequences

- Ranking is explainable and reversible; the cost is less automatic adaptation than a learned model would give.
- Until entity-level signals exist (they need extraction), ranking learns at topic and source level only, which is coarse: a source that publishes both wanted and unwanted items can only be ranked as a whole.
- Adds preference events, derived weights and card explanations to the reader module.

## Deferred

Component weights and their bounds, the decay half-life, the exploration share, how weak signals compare with strong ones, and whether learned weights ever move items between delivery levels (current answer: no, only suggestions).
