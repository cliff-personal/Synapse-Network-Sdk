# Python SDK — Staging Consumer E2E Plan

## Goal

Validate that an existing staging Agent Key can invoke staging services through the Python SDK. This replaces the old cold-start chain flow; funding, wallet setup, and credential issuance are handled before the test.

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

1. Create `SynapseClient(api_key=..., environment="staging")`.
2. Call fixed-price `invoke(service_id, payload, cost_usdc=...)`.
3. Read the receipt with `get_invocation_receipt(invocation_id)`.
4. If LLM env is present, call `invoke_llm(service_id, payload, max_cost_usdc=...)`.

## Run

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_consumer_e2e.py -q -s
```

The test suite is skipped unless `RUN_STAGING_E2E=1` is set. PR CI keeps staging E2E out of the default gate.
