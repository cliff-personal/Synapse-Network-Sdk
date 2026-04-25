# SDK Agent Map

- Status: canonical
- Code paths: `llms.txt`, `AGENTS.md`, `README.md`, `SECURITY.md`, `docs/`, `python/synapse_client/`, `typescript/src/`, `scripts/ci/`
- Verified with: `bash scripts/ci/pr_checks.sh`
- Last verified against code: 2026-04-25

This directory is the task-to-file index for AI agents working in `Synapse-Network-Sdk`.

Use it before broad repository search. It keeps SDK work routed to the right Python, TypeScript, docs, and CI surfaces without forcing agents to rediscover the repo every turn.

## Files

1. [index.json](./index.json) - machine-readable domain map for agents and workflow tools.
2. This README - human-readable operating rules and maintenance notes.

## How Agents Should Use This Map

1. Read root `llms.txt`.
2. Read root `AGENTS.md`.
3. Pick the closest domain in [index.json](./index.json).
4. Open the domain `primary_files` first.
5. Run the listed validation commands for the domain.

## Domain Summary

| Domain | Use when the task mentions |
| --- | --- |
| `sdk_runtime_client` | discovery, invoke, receipt, usage, runtime errors |
| `sdk_owner_auth` | wallet auth, credential issue/list/status/quota, owner control plane |
| `sdk_provider_lifecycle` | provider secrets, service registration, service lifecycle, provider health |
| `sdk_environment_config` | staging/prod/local presets, gateway URL resolution, public preview defaults |
| `sdk_public_docs` | README, integration guides, capability inventory, examples |
| `sdk_ci_quality_gates` | GitHub Actions, shell CI scripts, coverage gates |
| `sdk_examples_and_e2e` | examples, smoke tests, onboarding e2e plans |

## Update Rules

Update [index.json](./index.json) in the same change when:

1. A canonical SDK implementation file moves.
2. A public method is added, removed, renamed, or deprecated.
3. A validation command changes.
4. A gateway endpoint contract changes.
5. The public preview environment or staging/prod guidance changes.

Do not put secrets, real tokens, private deployment URLs, or one-off incident notes in this map.

## Validation

Run:

```bash
bash scripts/ci/pr_checks.sh
node -e "JSON.parse(require('fs').readFileSync('docs/agent-map/index.json', 'utf8'))"
```

