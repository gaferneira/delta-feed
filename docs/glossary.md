# Glossary

One word per idea. Use these terms consistently in docs, code and UI.

## Content

- **Source:** a configured origin of content (an RSS feed, an external collector, manual submission) with its own adapter, schedule and authorization.
- **Collector:** an external program, such as n8n, that submits observations through the ingestion API.
- **Observation:** one sighting of a document from a source at a point in time. The same article seen twice is two observations.
- **Receipt:** the durable record that an ingestion request was accepted.
- **Article:** a source document, identified by its source plus URL or external ID.
- **Revision:** an immutable version of an article's content. Changed content creates a new revision; unchanged content shares one.
- **Backfill:** importing recent history when a source is added: at most the last 30 days and 20 items per source by default. It stays quiet (out of Today) and unread, and the reader labels it "Earlier".

## Knowledge

- **Entity:** something whose identity the system tracks: a tool, library, project, product, hardware item or reusable practice. A practice ("code review before merge") and a concrete implementation of it are different entities.
- **Identity key:** a strong, namespaced identifier for an entity, such as a repository or package name. Names alone are not identity keys.
- **Alias:** another name for an entity. Helps find candidates; never proves identity.
- **Claim:** one atomic statement a source makes about an entity, with scope (version, platform, availability), times and evidence. A claim records what a source said, not that it is true.
- **Evidence:** the source passage that supports a claim.
- **Baseline:** the accepted entities and claims that new content is compared against. It has three sources: entities from the user's guides (familiar at entity level only, since a guide entry does not say which claims the user knows), claims extracted from the quiet backfill, and claims from articles already analysed. A claim joins the baseline once it is accepted as validated knowledge. An entity with no baseline claims is a *first sighting*, not "new".
- **Delta:** how a new claim relates to the baseline: duplicate, novel, refinement or contradiction.
- **Topic:** a label for an area of interest, many-to-many with entities, articles and guides. Not a separate identity registry.

## Reader

- **Discovery:** an entity that is new to you.
- **First sighting:** an entity with no baseline claims yet, so all its claims count as new. Not the same as a discovery: an entity from your guides can be a first sighting without being new to you.
- **Delta card:** one card per article on the Delta page, built only from that article's non-duplicate claims: what is new, its evidence, and its source ([ADR 0008](decisions/0008-delta-page-and-feed.md)).
- **Event:** grouped coverage of one change across several articles. Deferred: the reader shows per-article cards ([ADR 0008](decisions/0008-delta-page-and-feed.md)).
- **Watchlist:** entities you explicitly want updates about. A ranking signal for the Delta page ([ADR 0007](decisions/0007-preference-signals-and-transparent-ranking.md)), not a page of its own.
- **Uncertain:** a decision the system could not make safely. It stays visible and reviewable.
- **Shadow mode:** analysis runs and proposes what to publish or suppress, but nothing is hidden automatically; proposals are labelled and inspectable.
- **Suppression:** hiding an item from reader views because it is not new. Never deletes anything; off by default.

## Guides

- **Guide:** your own living article for a purpose, such as "Raspberry Pi home automation" or "Recommended skills every project should have", made of structured entries plus your own prose.
- **Guide entry:** one recommended entity or practice within a guide, with suitability, requirements, caveats and evidence.
- **Personal prose:** text you wrote in a guide. Never overwritten by generated content.

## Processing

- **Proposal:** a model-suggested outcome (a news disposition or a guide edit) awaiting acceptance. Models only ever propose.
- **Correction:** a reviewed change to identity decisions (merge, split, reassign), recorded as new history rather than rewriting old history.
- **Analysis run:** one execution of extraction and matching, with its prompt, schema, model and index versions recorded.
- **Job:** a durable unit of background work with leases and retries.
