---
name: frontend-code-review
description: Review Astro reader UX, SSR and accessibility.
allowed-tools: Read, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Frontend Code Review

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

- Astro escaping and safe rendering of source/model text; inspect set:html, unsafe URL schemes and untrusted serialized island props.
- Private/personalized pages render on demand, not at build time. No cross-user shared cache or leaked session/token in HTML, logs, client bundles or hydration props. Public caching is explicitly separated.
- Astro server API client forwards only necessary session/CSRF context to a configured trusted backend. Never derives backend target from user input or forwards all incoming headers.
- Browser API mutations preserve session/CSRF, validation, stable read/save state and visible failure/retry; use generated OpenAPI types but do not treat types as runtime validation.
- Islands are small and hydrated deliberately; no whole-feed React application or overlapping HTMX layer by default. Audit navigation listeners and state reset after navigation.
- Keyboard navigation, visible focus, labels/semantic elements, contrast, useful status announcements and mobile reflow.
- Guide views preserve personal prose, show reviewable diffs and stale proposals; no misleading automatic approval or freshness after a failed link. Backfilled discoveries are separate from Today and remain unread.
- New/change/source/relevance explanations clear; publication vs discovery distinguished; suppressed/uncertain/pending originals remain reachable.
- Empty/loading/error/offline and failed-save states avoid misleading success; read != known and saved != followed.
- Exercise available browser flow at mobile and desktop sizes with sanitized/disposable content; report console/network failures. Never approve permissions or enter secrets; browser capability absence is a limitation, not a passed test.

## Pitfalls

A model verdict is not evidence; a fake-provider test does not establish live model accuracy. Tool hints do not sandbox shell commands. Do not label unexecuted checks as passing or introduce fixes during review.

## Verification

Every finding has an inspected source location and plausible reproduction. All commands and unavailable checks are disclosed; no state, secrets, deployment, commits or external content were changed as a review side effect.
