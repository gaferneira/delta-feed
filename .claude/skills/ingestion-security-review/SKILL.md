---
name: ingestion-security-review
description: Review content ingestion and untrusted-input safety.
allowed-tools: Read, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Ingestion Security Review

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

- Scoped revocable collector credentials, replay/idempotency, payload bounds, publication-date validation and no secrets in logs.
- Fetcher checks scheme/port, resolved addresses, every redirect and connected destination; blocks loopback/private/link-local/metadata routes by default. Assess IPv6, mapped addresses, DNS/rebinding and proxy behavior, not merely URL regex.
- Explicit private source exceptions are narrow and authorized; no broad weakening to reach local RSS.
- Bound response/decompression size, timeouts, redirects, retries/concurrency and content types; extraction failure remains inspectable.
- Model prompts treat article text as hostile data; no tools or uncontrolled source-triggered outbound calls.
- HTML/URL rendering escaped/sanitized and source rights respected; no paywall bypass.
- Prefer mocked/local controlled fixtures; do not probe real metadata/internal services or external targets to demonstrate SSRF. Report exploitability with a bounded reproducible local scenario.

## Pitfalls

A model verdict is not evidence; a fake-provider test does not establish live model accuracy. Tool hints do not sandbox shell commands. Do not label unexecuted checks as passing or introduce fixes during review.

## Verification

Every finding has an inspected source location and plausible reproduction. All commands and unavailable checks are disclosed; no state, secrets, deployment, commits or external content were changed as a review side effect.
