# Product

## Who it is for

One technical person who follows a handful of feeds about software, AI and home-automation hardware, and already knows most of what those feeds repeat. Topics are configuration, not built-in categories.

## The daily loop

1. Open **Delta**. Each card is one article, reduced to the claims that are new, changed or in conflict with what earlier articles said, with the sentence each came from.
2. Review the **names** that are waiting. For a name the system has not seen, say once what it is: something to track, another name for something already tracked, or nothing worth tracking. Until then its claims stay out of your baseline.
3. Open **Feed** when you want everything. It lists every article, including those with nothing new, not yet analysed, or failed.

Why not an RSS reader: it shows every article and leaves you to find the one new item in a roundup, or to notice that the fifth report of a release adds nothing.

## Pages

| Page | Shows |
|---|---|
| Delta | Articles with at least one claim that is not a duplicate. Marking one read or saving it removes the card (with Undo) and keeps it out of Delta |
| Feed | Every article, newest first |
| Names | Names found in articles that the system does not know yet, waiting for your one-time decision |
| Saved | Your reading queue |
| Guides | Your own reference articles as structured entries, with proposed changes to review |

## Promises

- **Nothing is hidden.** Delta is a view; Feed always has the full list.
- **Unsure stays visible.** A claim the system cannot place is shown as "not sure", never dropped as a duplicate.
- **Evidence for every claim.** A claim without a verbatim sentence from the article is discarded.
- **You approve changes.** Names, guide edits and corrections wait for your decision.
- **Your model, your data.** Local model by default; no cloud inference unless configured.

## Independent concepts

These are separate and must not be merged in code or UI:

- **Identity**: which thing a name refers to.
- **Novelty**: whether a claim is already in the baseline.
- **Relevance**: whether you care.
- **Delivery**: whether and where it is shown.
- **Read state**: whether you opened it.

Indexed is not read. Familiar is not unimportant: a security advisory about something you use is still shown.

## Living guides

A guide is your own article for a purpose ("Raspberry Pi home automation"), kept as structured entries plus your own writing. When news shows that an entry should be added, updated, warned about or retired, the system proposes the change with evidence. Your text is never overwritten. Guide review never delays news.

Guides are a second feature on the same data. They are not part of the daily loop above.

## Out of scope

Multi-user hosting, a hosted service, autonomous source discovery, arbitrary scraping, paywall bypass, model-written article summaries, automatic hiding of articles, and learned recommendation systems.
