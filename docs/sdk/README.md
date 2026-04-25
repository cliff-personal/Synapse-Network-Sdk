<p align="center">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

# Synapse SDK Docs Hub

This directory is the SDK-side source of truth for capabilities, integration guides, provider onboarding, and test plans.

## Docs Index

1. [SDK Capability Inventory](./capability_inventory.md)
2. [Agent Map](../agent-map/README.md)
3. [Agent Map JSON](../agent-map/index.json)
4. [TypeScript Integration Guide](./typescript_integration.md)
5. [TypeScript Provider Integration Guide](./typescript_provider_integration.md)
6. [Python Integration Guide](./python_integration.md)
7. [Python Provider Integration Guide](./python_provider_integration.md)
8. [Python Local Development](../ops/SDK_Python_Local_Development.md)
9. [TypeScript Consumer E2E Plan](../test/consumer-e2e-plan.md)
10. [TypeScript Provider Onboarding E2E Plan](../test/typescript-provider-onboarding-e2e-plan.md)
11. [Python Consumer Cold-Start E2E Plan](../test/python-consumer-cold-start-e2e-plan.md)
12. [Python Provider Onboarding E2E Plan](../test/python-provider-onboarding-e2e-plan.md)

## Current Position

The SDK currently has three explicit public surfaces:

1. `SynapseClient`: agent runtime quickstart. After receiving an `agt_xxx` key, call discovery/search -> invoke -> receipt.
2. `SynapseAuth`: owner control plane for wallet auth, credential issuance, key rotation, and owner finance helpers.
3. `SynapseProvider`: provider publishing facade from `auth.provider()` for provider secrets, service registration, lifecycle, health, earnings, and withdrawal helpers.

Provider remains an owner-scoped supply-side role. `SynapseProvider` improves discoverability but does not introduce a second provider root identity.

Python quote-first methods `create_quote()`, `create_invocation()`, and `invoke_service()` are deprecated. They no longer call old endpoints and instead tell users to use discovery/search + `invoke(..., cost_usdc=...)`.

## Staging Docs

The productized Gateway runbook lives in staging docs:

1. SDK Hub: https://staging.synapse-network.ai/docs/sdk
2. Python SDK: https://staging.synapse-network.ai/docs/sdk/python
3. TypeScript SDK: https://staging.synapse-network.ai/docs/sdk/typescript

Production docs are reserved until production DNS, `/health`, and docs deployment are verified.

## Agent-First Onboarding Flow

The top README prioritizes the shortest TTFC path:

1. Connect wallet in Gateway Dashboard.
2. Generate Agent Key.
3. Agent runtime uses `SynapseClient` for discovery / invoke / receipt.

Programmatic credential issuance is an advanced owner flow:

1. Owner wallet signs in.
2. Gateway returns JWT.
3. Owner reads balance / credits.
4. Owner issues agent credential.

If the owner wallet has no balance, use services where `price_usdc == 0` as the smoke path. Paid services require owner balance, credits, or credential credit limit.

Provider publishing is a separate owner-authenticated flow:

1. Owner wallet signs in through `SynapseAuth`.
2. Code calls `provider = auth.provider()`.
3. Provider issues a provider secret if needed.
4. Provider registers or updates a service manifest.
5. Provider checks service status, health history, earnings, and withdrawals from the same facade.

## Configuration Truth

Default environment is public preview/staging:

- `local`: `http://127.0.0.1:8000`
- `staging`: `https://api-staging.synapse-network.ai`
- `prod`: `https://api.synapse-network.ai`, only for real funds after official production DNS and `/health` verification.

Python:

- `api_key`: explicit parameter first, then `SYNAPSE_API_KEY`.
- `gateway_url`: explicit parameter first, then `SYNAPSE_GATEWAY`.
- `environment`: explicit parameter first, then `SYNAPSE_ENV`, then `staging`.
- `AgentWallet.connect()` no longer uses demo credential fallback; missing real credentials fail.

TypeScript:

- SDK constructors use explicit `credential` / `gatewayUrl` / `environment`.
- Applications may read env vars and pass values into the SDK.
- The SDK does not implicitly depend on Node env, so browser and Node runtimes can share the package.

## Idempotency and Retry

Runtime calls should include:

1. `request_id` / request header for gateway log correlation.
2. `idempotency_key` / `idempotencyKey` to avoid duplicate charges or duplicate execution.
3. `cost_usdc` / `costUsdc` from latest discovery price. If price changes, the gateway rejects the call and the caller should rediscover.

## Common Failures

### `api_key is required`

No `api_key` was passed and `SYNAPSE_API_KEY` is not set. New users should issue an agent credential first, then pass the returned token to `SynapseClient`.

```bash
export SYNAPSE_API_KEY='agt_xxx_your_real_key'
```

### Discovery returns 0 results

Usually this means the current gateway has no discoverable services rather than an SDK failure.

Check:

1. Provider service is `active`.
2. Target service is healthy.
3. Discovery `query` / `tags` match the service.
4. Provider onboarding appears in owner `/api/v1/services`.

### `402` or budget errors

The SDK maps `402` to balance, budget, or credential credit limit errors. Check account balance, credential budget, and daily cap rather than blindly retrying.

## Shortest Verification Path

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_client_unit.py -q
export SYNAPSE_API_KEY='agt_xxx_your_real_key'
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query 'quotes'
```

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/typescript
npm run test:unit
```
