# Glossary

One word per idea. Use these terms in docs, code and UI.

## Content

- **Source:** a configured origin of content, such as an RSS feed.
- **Article:** a source document, identified by its source plus URL.
- **Revision:** an immutable version of an article's text. Changed text creates a new revision.
- **Backfill:** recent history imported when a source is added (30 days, 20 items by default). It adds to the baseline and never produces cards.

## Knowledge

- **Entity:** a named thing the system tracks: a tool, library, project, product, device, model, service or practice.
- **Alias:** another name for an entity. Linking a name to an entity adds it as an alias.
- **Mention:** one appearance of a name in an article's extraction output.
- **Name to review:** a mention that matched no entity, or more than one. Its claims wait until you decide what it is: **track** it (start a record for a new entity), mark it the **same as** an entity already tracked, or **ignore** it. You decide once per name. This says which thing a name is, not whether its news is new; news about tracked things appears on Delta.
- **Claim:** one statement an article makes about an entity: a predicate, a value, a scope (version, platform, availability) and evidence. It records what the source said, not that it is true.
- **Evidence:** the sentence, copied verbatim from the article, that supports a claim.
- **Baseline:** the active claims already recorded for an entity. New claims are compared with it.
- **Fingerprint:** a hash of entity, predicate, value and scope. Two claims with the same fingerprint are duplicates.
- **Topic:** a label for an area of interest. Not a separate registry of entities.

## Comparison results

- **New:** nothing in the baseline covers it.
- **First sighting:** the entity had no claims yet, so its claims are new by definition. Not the same as new to you.
- **Changed** (`refinement`): adds detail to a known claim.
- **Conflicts** (`contradiction`): disagrees with a known claim.
- **Duplicate:** already in the baseline. Not shown on Delta.
- **Not sure** (`unsure`): the system could not decide. Always shown.

## Reader

- **Delta card:** one card per article, built only from its claims that are not duplicates.
- **Delta:** the page of Delta cards.
- **Feed:** the page that lists every article.
- **Event:** one change covered by several articles. Not modelled yet; see the [roadmap](roadmap.md#open-decisions).
- **Shadow mode:** analysis proposes, nothing is hidden automatically.

## Guides

- **Guide:** your own reference article for a purpose, made of structured entries and your own writing.
- **Guide entry:** one recommended entity or practice in a guide.
- **Proposal:** a suggested guide change waiting for your approval.

## Processing

- **Analysis run:** one model task on one article revision, with its prompt, schema and model versions.
- **Job:** a durable unit of background work with a lease and retries.
