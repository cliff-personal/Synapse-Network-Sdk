---
created_at: 2026-04-28
updated_at: 2026-04-28
doc_status: active
---

# SDK Quality Gates

This repository uses `bash scripts/ci/pr_checks.sh` as the single PR quality gate entrypoint. GitHub Actions and local validation must keep using that same script so PR behavior matches developer machines.

## Required Checks

- Repo hygiene: retired gateway domains, deprecated brand wording, README language split, staging defaults, and sensitive tracked filenames.
- Python: Ruff format, Ruff lint, Mypy, unit tests with coverage, source size checks, Radon cyclomatic complexity, and package build.
- TypeScript: Prettier, ESLint, `tsc --noEmit`, package build, unit tests, coverage, and duplicate-code scanning.
- Security: Bandit for Python source and `npm audit --omit=dev --audit-level=high` for production npm dependencies.

## Thresholds

- Source files must be `500` lines or fewer.
- Test files may be up to `700` lines while the suite is being decomposed.
- Python functions may have at most `40` effective logic lines.
- Python Radon complexity must stay at grade `A` or `B`; grade `C` or worse fails CI.
- TypeScript ESLint complexity must be `8` or lower.
- TypeScript functions may have at most `60` effective lines.
- Python coverage must be at least `80%`.
- TypeScript global lines, branches, functions, and statements coverage must each be at least `80%`.
- Duplicate code across `python/synapse_client` and `typescript/src` must stay at or below `3%` with a `50` token minimum clone size.

## Refactor Rules

- If a source file exceeds `500` lines, split it before adding more behavior.
- If logic appears in three places, extract a shared helper or module.
- If a function exceeds `40` Python effective lines, `60` TypeScript lines, or the complexity threshold, split pure decisions from I/O and orchestration.
- Bug fixes need regression tests. New observable behavior needs unit tests.
- Public SDK API changes must update docs and `docs/sdk/capability_inventory.md` when the implementation state changes.

## GitHub Enforcement

The `main` branch must require the PR CI status check named `SDK PR quality gates`, require the branch to be up to date, block direct pushes, and require at least one approving review before merge.
