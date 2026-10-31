---
name: implement-vertical-slice
description: Build one tested end-to-end product slice.
disable-model-invocation: true
---

# Implement Vertical Slice

## When to Use

Use when the user explicitly requests an implementation with an acceptance scenario. Do not use for read-only review or production deployment. Requires an agreed scope; it does not authorize commits or external changes.

## Procedure

1. Read instructions and docs; inspect $ARGUMENTS, files and git state. Define observable success and failure cases, current/planned distinction and smallest required modules. First slice is Django-owned login → article submission/persistence → Astro SSR feed → Django Ninja save/read → persisted reload, without AI. Follow the accepted ADRs and design the required detailed ports/schema within scope before implementation.
2. Choose/verify compatible tool versions if scaffolding, use isolated managed dependencies, then add a failing behavior test before the implementation where applicable. Document missing prerequisites instead of guessing run commands.
3. Implement only the required app modules in docs/repository-structure.md. Keep source/provider adapters optional; domain writes validated/transactional and network calls outside transactions. Do not precreate every planned package.
4. Run targeted tests, applicable PostgreSQL integration and browser checks using disposable data. Inspect errors, fix demonstrated issues, re-run. Source/model responses are untrusted data.
5. Perform domain-appropriate review and fix verified blockers within scope. Update docs/commands with real exercised behavior; major deviations need an ADR.
6. Report files, commands/results, remaining risks and next milestone. No production or personal-notes changes, credentials, live inference spend, remote creation, commit or push without explicit approval.

## Pitfalls

Do not hide uncertainty to satisfy a demo, ship placeholder APIs as complete, use SQLite to prove PostgreSQL locking, or enable suppression/cloud fallback implicitly. Planned deployment files are not proof of a working install.

## Verification

Acceptance and failure scenarios have executed evidence; docs match the artifact; git state accounts for every change and unrelated work is preserved. If prerequisites block execution, identify the blocker explicitly rather than claim completion.
