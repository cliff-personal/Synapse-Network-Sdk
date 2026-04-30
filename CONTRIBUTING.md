# Contributing

Thanks for improving the SynapseNetwork SDK. This repository is public-facing, so every change should keep the developer and AI-agent onboarding path clear, staging-first, and safe.

## Before You Start

1. Read `llms.txt`.
2. Use `SYNAPSE_AGENT_KEY` for agent runtime examples.
3. Treat `staging` as the only public preview environment.
4. Use Arbitrum Sepolia and MockUSDC in staging docs; do not document local gateway setup as the public integration path.
5. Never commit private keys, seed phrases, real credentials, or production tokens.

## Development

Python:

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

TypeScript:

```bash
cd typescript
npm install
```

## Quality Gates

Run the full PR gate before opening or updating a pull request:

```bash
bash scripts/ci/pr_checks.sh
```

Focused checks:

```bash
bash scripts/ci/repo_hygiene_checks.sh
bash scripts/ci/python_checks.sh
bash scripts/ci/typescript_checks.sh
```

## SDK Contract Rules

- Public `SynapseAuth` and `SynapseProvider` methods must return named SDK models/interfaces, not raw maps.
- Fixed-price API examples must pass discovered prices as strings, for example `cost_usdc="0.05"` or `costUsdc: "0.05"`.
- Token-metered LLM examples must use `invoke_llm()` / `invokeLlm()` and must not pass `cost_usdc` / `costUsdc`.
- New public behavior needs tests and docs in the same change.
