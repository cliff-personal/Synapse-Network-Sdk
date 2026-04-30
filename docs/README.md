# SynapseNetwork SDK Documentation

This directory is the public documentation source for the SynapseNetwork SDK repository.

## Start Here

1. [Getting Started](./guides/getting-started.md)
2. [SDK Docs Hub](./sdk/README.md)
3. [SDK/API Parity Matrix](./sdk/api-parity-matrix.md)
4. [Quality Gates](./quality-gates.md)
5. [Agent Map](./agent-map/README.md)

## Public Preview Environment

Public developer onboarding uses staging:

- Gateway: `https://api-staging.synapse-network.ai`
- Chain: Arbitrum Sepolia testnet
- Asset: MockUSDC for integration testing, not production USDC

Production docs and examples will be switched after production DNS, gateway health, contracts, and docs deployment are verified.

## Contributor Notes

Run the SDK PR gate before opening a pull request:

```bash
bash scripts/ci/pr_checks.sh
```
