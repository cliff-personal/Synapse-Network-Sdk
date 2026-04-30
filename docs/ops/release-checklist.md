# Release Checklist

Use this checklist for SDK releases and public documentation updates.

## Preflight

- [ ] `bash scripts/ci/pr_checks.sh` passes.
- [ ] `.github/workflows/ci.yml` and `.github/workflows/pr-ci.yml` are current.
- [ ] 更新 CHANGELOG.md with the release date and developer-visible changes.
- [ ] Public examples use `SYNAPSE_AGENT_KEY`.
- [ ] Public examples use `SYNAPSE_ENV=staging` until production launch.
- [ ] Fixed-price examples pass string money from discovery.
- [ ] Token-metered LLM examples use `invoke_llm()` / `invokeLlm()` without fixed `cost_usdc` / `costUsdc`.
- [ ] Public owner/provider returns are named SDK models/interfaces, not raw maps.

## Staging Verification

- [ ] Staging gateway health is verified.
- [ ] Arbitrum Sepolia and MockUSDC language is current.
- [ ] One fixed-price staging invoke is verified.
- [ ] One token-metered LLM staging invoke is verified when a staging LLM service is available.
- [ ] Receipt lookup is verified.

## Production Switch

Do not switch public examples from staging to production until production DNS, gateway health, contracts, docs deployment, and release notes are verified together.

## Publish

- [ ] Create and push the Git tag.
- [ ] Publish the GitHub Release with install notes and staging/prod status.
