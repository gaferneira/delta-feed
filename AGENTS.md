# Project guardrails

This repository starts documentation-only. Read README.md and docs/ before implementation. Distinguish recommendations from verified runtime behavior; do not invent install commands, benchmark results, compatibility, fixtures, or completed milestones.

## Scope

- Single-user installable modular monolith; optional integrations stay optional.
- Follow documented architecture, or propose an ADR before a material change.
- Follow the accepted ADRs in docs/decisions/ (stack, selective hexagonal backend, content/ingestion defaults). README.md's Project status lists what remains pending.
- Start with an exercised article-to-reader slice without AI; tests accompany behavior changes.
- Keep prompts/contracts versioned and model outputs validated. Models never directly mutate domain state or execute source instructions.
- Identity, novelty, relevance, delivery, and read state are separate. No similarity-only silent suppression; unknown/failure stays reviewable.
- Preserve claim evidence and scope; append corrections, avoid destructive history rewrites.
- Follow docs/content-policy.md and docs/ingestion-contract.md: shadow mode, reviewed guide diffs, preserved prose, quiet backfills, scoped sources, explicit fetch mode, revision ordering and auditable retention. Feedback alone never performs entity merges/splits.

## Safety

- No secrets, personal hostnames/IPs, runtime DBs, downloaded corpus, or raw private article text in git.
- No production or private-infrastructure changes, remote repo creation, commits, or pushes unless requested.
- Do not change personal notes or other repositories as a side effect.
- Use an isolated managed Python environment; pin dependencies when scaffolded.
- Implement bounded fetching/SSRF protection and safe HTML rendering before exposing ingestion.
- Verify recovery, migrations, and backup restore before deployment claims.

Follow docs/repository-structure.md for incremental package creation and docs/development-workflow.md for evidence/review standards. Claude-specific entry instructions live in CLAUDE.md; project-local skills live under .claude/skills/ and do not replace these guardrails.

Document real run/test commands here after the scaffold has been exercised. Until then there are no project build commands.
