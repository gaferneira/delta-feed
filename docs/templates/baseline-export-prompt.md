# Baseline export prompt

Paste the prompt below into an AI assistant that keeps memory of your past conversations. Save the CSV it returns to `local-corpus/known.csv`, then verify it as described in [baseline-corpus.md](../baseline-corpus.md).

The prompt forbids guessing because a wrong "familiar" entry hides real discoveries later. Expect fewer rows than you might hope; that is intended.

````text
I'm building a baseline of the tools, projects and hardware I already know, so a news filter can tell what's genuinely new to me.

Using ONLY what you have in saved memory about me and what you can recall from our past conversations, list every tool, library, framework, project, service, hardware device or practice I've mentioned using, trying, evaluating or knowing about.

Rules:
- Do not add things I'd "probably" know. If it isn't grounded in something I told you, leave it out.
- One entity per row. Never combine two things ("Linear & Sentry" is two rows).
- Broad interests that aren't a single thing ("local LLMs", "RAG") are not rows; list them at the end instead.
- aliases: other names an article would use, separated by `;`. Never my hostnames or nicknames, and never a name shared with something else (e.g. not "Claude" for Claude Code).
- kind: one of tool, library, project, hardware, service, practice.
- familiarity: `use` if it's part of my setup, `heard` if I only discussed it, or tried it and moved on.
- last_known_state: only a version or status I mentioned (e.g. v0.9, beta, abandoned). Never guess, and never put where it's installed. Otherwise leave it blank.
- delivery: leave blank. I'll decide that myself.
- source: `memory` if from saved memory, `chat` if from conversation history, `inferred` if you're connecting dots. Be honest; I'd rather have fewer rows.
- Group rows by topics that fit what you find (e.g. AI tooling, dev tools, home automation).

Output exactly one CSV code block with this header, quoting any field that contains a comma:

topic,name,aliases,kind,familiarity,last_known_state,delivery,notes,source

After the code block, add:
- Interests: broad topics I care about that aren't single entities.
- Not interested: things I've said I dislike, dropped or don't care about (I'll set these to mute).
- Uncertain: anything you weren't sure belonged.
````

After review, check or drop every `inferred` row, fill `delivery` where you want something other than the topic default, and remove the `source` column.
