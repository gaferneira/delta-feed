---
name: backend-code-review
description: Review Django backend correctness and reliability.
allowed-tools: Read, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Backend Code Review

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

- Django Ninja routers use explicit input/output schemas, pagination and status/error contracts; endpoints call domain services, not long inference tasks. OpenAPI/TypeScript contracts stay in sync and responses do not expose internal fields.
- Authn/authz, object ownership, session cookie/SSR forwarding and collector scoped tokens are explicit. Test unsafe browser requests with Django Client(enforce_csrf_checks=True); Ninja shortcut clients alone do not prove CSRF behavior. Verify installed-version behavior including login, logout and unauthenticated routes.
- No implicit trust of forwarded identity or arbitrary cookies/headers. Astro cannot bypass domain permissions; GET requests never mutate reading state.
- Transactional receipts/jobs, scoped idempotency conflict handling, explicit URL-fetch/provided-content contracts and authorized source/status access; updates revisioned rather than lost, delayed observations never blindly win.
- Review docs/content-policy.md: news/analysis/guide states independent, shadow proposals not automatic publication, quiet backfill retained through retries, feedback distinct from correction. Guide approval checks current revision and preserves prose/evidence/history.
- Entity/claim writes through explicit domain services; no network/model calls inside transactions; stale-state recheck before publication.
- PostgreSQL constraints/locking and concurrent workers; lease expiry and retry safety; no exactly-once delivery claims.
- Query counts/N+1 behavior, pagination, indexes with evidence; no speculative performance rewrites.
- Provider proposals validated; provenance/scope retained, no implicit cloud fallback or similarity-only suppression.
- Tests cover success, invalid/auth failure, duplicate, concurrent/restart and provider failure paths relevant to the change.

## Pitfalls

A model verdict is not evidence; a fake-provider test does not establish live model accuracy. Tool hints do not sandbox shell commands. Do not label unexecuted checks as passing or introduce fixes during review.

## Verification

Every finding has an inspected source location and plausible reproduction. All commands and unavailable checks are disclosed; no state, secrets, deployment, commits or external content were changed as a review side effect.
