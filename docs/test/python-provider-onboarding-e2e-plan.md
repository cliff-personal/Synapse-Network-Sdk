# Python SDK — Staging Provider E2E Plan

## Goal

Validate provider onboarding against staging with a real provider wallet and a public HTTPS provider endpoint.

## Required Environment

| Variable | Purpose |
|---|---|
| `RUN_STAGING_PROVIDER_E2E=1` | Opt in to live staging provider tests |
| `SYNAPSE_PROVIDER_PRIVATE_KEY` | Provider owner private key for staging |
| `SYNAPSE_PROVIDER_ENDPOINT_URL` | Public HTTPS endpoint reachable by staging |

## Flow

1. Authenticate with `SynapseAuth.from_private_key(..., environment="staging")`.
2. Issue a provider secret.
3. Register a provider service with the public HTTPS endpoint.
4. List services and read service status.

## Run

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_provider_e2e.py -q -s
```

The test suite is skipped unless `RUN_STAGING_PROVIDER_E2E=1` is set.
