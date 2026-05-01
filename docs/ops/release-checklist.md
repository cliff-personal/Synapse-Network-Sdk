# Release Checklist

Use this checklist for SDK releases and public documentation updates.

## Preflight

- [ ] `bash scripts/ci/pr_checks.sh` passes.
- [ ] Read `docs/ops/sdk-release-runbook.md`.
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

- [ ] Initialize the SDK release train in Synapse-Network-Growing `/releases` -> `SDK Packages`.
- [ ] Dry-run each selected package through `.github/workflows/publish-sdk.yml`.
- [ ] Publish each selected package through `.github/workflows/publish-sdk.yml`.
- [ ] For Go, verify the subdirectory module tag uses `go/vX.Y.Z`.
- [ ] Publish the GitHub Release with package URLs, install notes, and public-preview status.
- [ ] Do not describe SDK packages as staging/prod deployments; SDK packages only have registry channels.
