---
name: database-migration-review
description: Review migrations, constraints and recovery safety.
allowed-tools: Read, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Database Migration Review

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

- Models/migrations agree; inspect dependency ordering, unique keys, FK behavior, indexes, nullability and existing-data assumptions.
- Preserve revisions/evidence/claim relations; prevent destructive cascades or silent identity/history loss.
- Evaluate table locks, duration, backfill batching, concurrent index restrictions and expand/backfill/contract compatibility.
- Embedding dimension/model changes require explicit staged re-index and reader/worker compatibility, never mixed search.
- Job leasing, duplicate workers and stale baseline writes validated using PostgreSQL semantics rather than SQLite.
- Assess rollback or documented forward recovery and verified logical backup/restore; irreversible migration is explicit.
- Inspect migration code before execution: no production DB, real corpus writes or destructive reverse migration tests. Exercise only authorized disposable PostgreSQL with realistic sanitized data; report unavailable DB as blocked.

## Pitfalls

A model verdict is not evidence; a fake-provider test does not establish live model accuracy. Tool hints do not sandbox shell commands. Do not label unexecuted checks as passing or introduce fixes during review.

## Verification

Every finding has an inspected source location and plausible reproduction. All commands and unavailable checks are disclosed; no state, secrets, deployment, commits or external content were changed as a review side effect.
