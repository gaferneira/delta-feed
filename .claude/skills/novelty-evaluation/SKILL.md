---
name: novelty-evaluation
description: Evaluate identity and claim novelty regressions.
allowed-tools: Read, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Novelty Evaluation

## When to Use

Use for explicitly requested reviews/evaluations in this domain or matching code changes. Do not use as authority to implement fixes, deploy, commit, or modify external systems.

## Scope

Review $ARGUMENTS. If no scope is provided, inspect current local changes and state what was included. Read-only findings by default; test commands require disposable state and reviewed side effects. Use only run/test commands documented in CLAUDE.md or README.md; if none exist, report checks as not run.

## Procedure

1. Read AGENTS.md, CLAUDE.md and the relevant docs. Inspect current state and the requested files/base; if HEAD is absent, review untracked files explicitly rather than a fictitious diff.
2. Apply the checklist below to real evidence. Distinguish current files from planned architecture. Missing implementation is not automatically a defect in documentation-only scope.
3. Run only applicable existing local checks after inspecting their commands/side effects. Use disposable data; no production actions or live/paid inference without explicit authorization. If unavailable, report blocked/not run.
4. Report scope and actionable findings ordered by severity, each with actual file:line, failure scenario, impact, minimal fix and regression test. Separate proven defects from risks. Include exact verification commands/results and limitations.

## Checklist

- Corpus contains real evidence and explicit known baseline; restricted full text stays local; synthetic scenarios labeled.
- Exact names/aliases not confused with scoped strong identifiers; forks/similar tools and cross-topic matches remain distinct.
- Candidate retrieval omissions do not prove novelty; uncertain state remains possible; evaluate false merges/missed discoveries separately from false-new repetition.
- Claims include version/platform/availability and source; beta/GA, out-of-order announcements, contradictions/refinements and security events tested.
- Prompt/schema/model/digest/index versions recorded; vector spaces never mixed; held-out examples stay outside tuning.
- Relevance, registry-known, delivered and read are independently evaluated.
- Default deterministic fixtures/fakes; live provider runs require explicit scope/budget/privacy approval. Report actual numerators/denominators and failures, not guessed accuracy or self-reported confidence.
- Guide recommendations are contextual, not merely novel. Evaluate suitability, evidence freshness, stale diffs and preservation of personal prose. Older discoveries are not breaking news; delayed/backfilled input must not trigger false corrections or alerts.
- Proposed suppression stays shadow mode until user-reviewed criteria are met; no changes to publication settings as an evaluation side effect.

## Pitfalls

A model verdict is not evidence; a fake-provider test does not establish live model accuracy. Tool hints do not sandbox shell commands. Do not label unexecuted checks as passing or introduce fixes during review.

## Verification

Every finding has an inspected source location and plausible reproduction. All commands and unavailable checks are disclosed; no state, secrets, deployment, commits or external content were changed as a review side effect.
