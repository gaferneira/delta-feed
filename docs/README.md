# Documentation

Start with the first four. Each file states facts once; the others link to it.

| File | Answers | Read it when |
|---|---|---|
| [product.md](product.md) | What is Delta Feed and what is it not? | You are new, or deciding whether a feature belongs |
| [status.md](status.md) | What works today, and how do we know? | Before trusting or claiming that something works |
| [architecture.md](architecture.md) | How does an article become a card, and where is that code? | Before changing backend or frontend code |
| [roadmap.md](roadmap.md) | What is next, and what is undecided? | Before starting new work |
| [development.md](development.md) | How do I run, test and submit a change? | Setting up, or before a commit |
| [glossary.md](glossary.md) | What does this word mean here? | A term is unclear; use these terms in code and UI |
| [content-policy.md](content-policy.md) | What may the system publish, hide or change by itself? | Touching publication, guides, feedback or retention |
| [ingestion-contract.md](ingestion-contract.md) | What may enter, and how are retries and revisions handled? | Touching ingestion or adding a collector |
| [baseline-corpus.md](baseline-corpus.md) | How do I collect real reading data for evaluation? | You want to measure or improve novelty detection |
| [decisions/](decisions/README.md) | Why was it built this way? | Before proposing a change to a past decision |
| [designs/](designs/) | Detailed plans for work not finished | Implementing that work |

## Rules for these documents

- Status lives only in [status.md](status.md). Other files say how things are meant to work.
- A decision that is hard to reverse gets an ADR in [decisions/](decisions/README.md). Order of work and tuning ideas go in [roadmap.md](roadmap.md).
- Write what was observed. Mark anything not exercised as not exercised.
- Short over complete: a table or a list before a paragraph.
