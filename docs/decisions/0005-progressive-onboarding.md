# ADR 0005: Progressive onboarding and familiarity

**Status:** Proposed. Delivery phases and implementation notes live in the [roadmap](../roadmap.md#adr-0005-progressive-onboarding).

## Context

Novelty means "new to you", so Delta Feed needs a per-user baseline of what the reader already knows. A long upfront questionnaire is a barrier for people who just cloned the repository, and people recognize what they know far more reliably than they recall it from a blank list. With no baseline at all, though, every item looks new, and the first days are noisy.

[Content policy](../content-policy.md#topics-sources-and-onboarding) already requires a first reader setup (topics, sources, watchlist, quiet backfill) and an "already knew this" action. This ADR decides how those combine.

## Decision

Keep the required setup minimal, and build familiarity progressively while reading.

0. **Account (first run only):** when no user exists, the reader asks for a one-time setup token printed in the server logs, then creates the first account. Without the token, whoever reaches a fresh instance first could claim it. The token expires, is stored only as a hash, and can be rotated from the command line when the logs are lost.
1. **Setup (required, about a minute):** pick topics, choose sources. Starter packs suggest sources for a topic; none are pre-selected, because packs are expected to grow. Setup is skippable, and the chosen sources get the usual quiet backfill.
2. **First-session triage (optional):** after the quiet backfill, show the entities most mentioned in the reader's *own* sources and let them tap the ones they already know.
3. **While reading (ongoing):** "Already knew this" on a card, plus a roundup shortcut ("I knew all of these except…"), records familiarity.
4. **Import (any time):** a CSV in the [known template](../templates/known.csv) columns (documented in [baseline-corpus.md](../baseline-corpus.md#step-1-write-your-baseline)), through a management command first and the UI later.
5. **Nudges (later):** repeated dismissals of the same entity produce a *suggestion* to mark it familiar. The reader always confirms.

Rules:

- **One reader in the UI, per-user data underneath.** Every piece of personal state (read, save, guides, familiarity, delivery levels) is keyed by user; sources, articles and entities stay a shared registry. This keeps a second household reader possible without migrations. It is not multi-tenancy: no user management, invites or roles until a real need exists.
- **Familiarity is per user and separate from the registry.** It never edits, merges or splits an `Entity`. It stays independent of relevance, read state and following, as [product.md](../product.md#independent-concepts) requires.
- **Levels:** `heard` or `use`, with no record meaning unknown. Delivery priority is a separate axis (see below).
- **Familiarity is entity-level, not claim-level.** Knowing an entity removes it from Discoveries, but meaningful updates about it (claims, releases, security, deprecations) stay eligible.
- **Append-only, with provenance.** Every change records its origin (`setup_triage`, `card_feedback`, `roundup_bulk`, `import`, `guide`, `nudge`) and can be undone. Nothing is inferred silently.
- **Not retroactive.** Marking something familiar affects future classification; it does not hide content already delivered.
- **Calibration is visible.** Until the baseline is established, Discoveries says it is still learning what the reader knows. The exit criterion is set from trial data.
- **Starter packs are reviewed data:** versioned TOML (read with the standard library, no new dependency) with a topic plus suggested feeds, contributed by pull request and validated through the bounded fetcher. They contain no entity lists, because triage uses the reader's own backfill instead.

### Delivery levels

Priority is set per **topic**; an **entity** inherits its topics' level unless the reader overrides it. When an entity belongs to several topics, the highest level applies.

| Level | Feed | Notification |
|---|---|---|
| `notify` | Shown, ordered first | For significant events only |
| `show` (default) | Shown | None |
| `mute` | Not shown in Today, Discoveries or Following; still listed in All Content with the reason | None |

- **Ordering:** within each topic group, `notify` items come before `show` items, then the usual time order applies. This is an explicit preference, not learned ranking, and it never hides `show` items.
- **Significant events** are releases, status changes (for example beta to GA), security advisories and deprecations. Routine mentions of a `notify` entity appear in the feed without a notification.
- **Mute is not suppression.** Muted items stay inspectable. Security advisories about an entity the reader `use`s still surface even when muted.
- **Notifications are optional.** `notify` affects ordering from day one; sending notifications requires a configured integration.
- Delivery level is independent of familiarity: a reader can `use` something and keep it at `show`.

## Consequences

- Adds `Topic`, per-user familiarity and per-user delivery levels; familiarity becomes an input to novelty classification, and delivery level an input to feed ordering.
- Onboarding stays short and every step is skippable. The cost is a noisy first week, softened by quiet backfill, triage and the calibration label.
- Starter packs give the community a contribution path that contains no private data.

## Deferred

Exact schemas and API shapes, the triage list size, the calibration exit criterion, nudge thresholds, the starter-pack schema version and review rules, the significant-event taxonomy, and notification batching and quiet hours.
