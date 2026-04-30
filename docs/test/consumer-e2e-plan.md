# TypeScript SDK — Staging Consumer E2E Plan

## Goal

Validate that an existing staging Agent Key can discover services, run a fixed-price API invoke, optionally run a token-metered LLM invoke, and read receipts against the staging gateway.

## Required Environment

| Variable | Purpose |
|---|---|
| `RUN_STAGING_E2E=1` | Opt in to live staging tests |
| `SYNAPSE_AGENT_KEY=agt_xxx` | Agent runtime credential |
| `SYNAPSE_STAGING_SERVICE_ID` | Fixed-price staging service ID |
| `SYNAPSE_STAGING_SERVICE_PRICE_USDC` | Latest discovery price for that service |
| `SYNAPSE_STAGING_LLM_SERVICE_ID` | Optional token-metered LLM service ID |
| `SYNAPSE_STAGING_LLM_MAX_COST_USDC` | Optional LLM spend cap |

## Flow

1. Create `SynapseClient({ credential, environment: "staging" })`.
2. Call `discover()` to confirm staging discovery responds.
3. Call fixed-price `invoke(serviceId, payload, { costUsdc })`.
4. Read the receipt with `getInvocation(invocationId)`.
5. If LLM env is present, call `invokeLlm(serviceId, payload, { maxCostUsdc })`.

## Run

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/typescript
npm run test:e2e
```

The test suite is skipped unless `RUN_STAGING_E2E=1` is set. PR CI keeps staging E2E out of the default gate.
