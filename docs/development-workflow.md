# Development and Claude workflow

## Before implementation

Read product/architecture/technology/repository-structure and applicable agent instructions. Read content-policy.md and ingestion-contract.md as the accepted behavior baseline. Define one acceptance scenario and failure cases. Inspect existing files and git state; do not assume HEAD exists or silently choose a review base. Personal task tracking stays outside this repository; technical behavior/decisions belong here.

## Skills

| Invocation | Scope |
|---|---|
| /backend-code-review <files or diff base> | Django Ninja contracts, auth/CSRF, domain writes, queries and job behavior |
| /frontend-code-review <view or files> | Astro SSR/islands, TypeScript API usage, mobile/accessibility, session/cache boundaries |
| /novelty-evaluation <change or corpus> | Identity/claim policy, prompt/provider changes and evidence-backed regression evaluation |
| /ingestion-security-review <boundary> | Fetching, SSRF, hostile content, collector auth and resource bounds |
| /database-migration-review <migration> | Constraints, data/index changes, concurrency and safe migration/restore behavior |
| /implement-vertical-slice <acceptance scenario> | Small tested feature spanning only necessary layers |

Skills are project-local Claude Code instructions, not global skills or running services. Reviews/evaluation and implementation are separate: no review auto-fixes. Claude Code discovers them from .claude/skills/ (verified 2026-10-31): the five review/evaluation skills can be selected by slash command or task description; implement-vertical-slice sets disable-model-invocation and runs only when invoked explicitly.

## Review output contract

State scope, reference baseline and evidence inspected. Findings first, severity ordered: blocker/high/medium/low; each includes file:line, failure scenario, impact, proposed minimal fix and regression test. Separate verified defects from risks/questions. Finish with exact commands/results and untested areas. No findings does not imply production readiness. Do not invent line numbers or successful tests.

Tool hints in skill frontmatter pre-approve tools; they are not security isolation. Review skills pre-approve only read-only git inspection; widen allowed-tools deliberately once real test commands exist. Bash and browser interactions may have side effects. Prefer read-only inspection; run only reviewed local tests with disposable data. No paid/network model runs, destructive DB actions, deployment, secrets reads or commits without scope approval.

## Feature completion

1. Reproduce desired behavior with a failing test where applicable.
2. Implement smallest change; targeted tests pass.
3. Exercise applicable integration/browser path and failure case.
4. Perform relevant focused review; fix verified blockers and re-test.
5. Update docs and report real results, remaining limitations and changed files.

Deterministic CI uses provider fakes and disposable PostgreSQL for DB-specific behavior. Live inference evaluations are separate explicit runs with budget/privacy authorization. Versions and commands become authoritative only after exercised.

## Future additions

Add run/verify skills once commands exist, an operator runbook once deployment works, and CONTRIBUTING/SECURITY before inviting contributions. Add dedicated subagents only if isolated parallel reviews are actually needed; skills do not require subagents. Avoid speculative hooks, blanket permission bypass settings and automatic publishing/deployment.
