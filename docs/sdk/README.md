<p align="center">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

# Synapse SDK Docs Hub

This directory is the SDK-side source of truth for capabilities, integration guides, provider onboarding, and test plans.

## Docs Index

1. [SDK Capability Inventory](./capability_inventory.md)
2. [SDK/API Parity Matrix](./api-parity-matrix.md)
3. [Agent Map](../agent-map/README.md)
4. [Agent Map JSON](../agent-map/index.json)
5. [TypeScript Integration Guide](./typescript_integration.md)
6. [TypeScript Provider Integration Guide](./typescript_provider_integration.md)
7. [Python Integration Guide](./python_integration.md)
8. [Python Provider Integration Guide](./python_provider_integration.md)
9. [Go Integration Guide](./go_integration.md)
10. [Java/JVM Integration Guide](./java_integration.md)
11. [.NET Integration Guide](./dotnet_integration.md)
12. [SDK Parity E2E](#sdk-parity-e2e)
13. [Python Staging Development](../ops/SDK_Python_Staging_Development.md)
14. [TypeScript Consumer E2E Plan](../test/consumer-e2e-plan.md)
15. [TypeScript Provider Onboarding E2E Plan](../test/typescript-provider-onboarding-e2e-plan.md)
16. [Python Consumer Cold-Start E2E Plan](../test/python-consumer-cold-start-e2e-plan.md)
17. [Python Provider Onboarding E2E Plan](../test/python-provider-onboarding-e2e-plan.md)

## Current Position

The SDK currently has three explicit public surfaces:

1. `SynapseClient`: agent runtime quickstart. After receiving an `agt_xxx` key, call discovery/search -> invoke -> receipt.
2. `SynapseAuth`: owner control plane for wallet auth, credential issuance, key rotation, and owner finance helpers.
3. `SynapseProvider`: provider publishing facade from `auth.provider()` for provider secrets, service registration, lifecycle, health, earnings, and withdrawal helpers.

Provider remains an owner-scoped supply-side role. `SynapseProvider` improves discoverability but does not introduce a second provider root identity.

Go, Java/JVM, and .NET now expose the same public capability families as Python and TypeScript: `SynapseClient` agent runtime, `SynapseAuth` owner wallet auth, credential management, balance/deposit helpers, usage/finance reads, and `SynapseProvider` provider publishing/withdrawal helpers.

Owner/provider helper returns are typed SDK objects. Do not document or add public `SynapseAuth` / `SynapseProvider` methods that return raw Python `dict`, TypeScript `Record<string, unknown>`, Go `map[string]any`, Java `JsonNode`/`Map`, or .NET `JsonElement`/`Dictionary` as the top-level result; add a named result model/interface/struct/record instead.

Python quote-first methods `create_quote()`, `create_invocation()`, and `invoke_service()` are deprecated. They no longer call old endpoints and instead tell users to use discovery/search + `invoke(..., cost_usdc=...)` for fixed-price APIs.

LLM services use `serviceKind=llm` + `priceModel=token_metered`. Runtime code should call `invoke_llm()` / `invokeLlm()` and read `usage` plus `synapse` billing metadata. Do not pass `cost_usdc` / `costUsdc` for LLM calls; pass optional `max_cost_usdc` / `maxCostUsdc` or let Gateway compute the automatic hold. Streaming is disabled in V1.

Consumer docs should present two invocation modes:

| Mode | SDK method | Cost input |
|---|---|---|
| Fixed-price API | Python/TypeScript `invoke()`, Go `Invoke()`, Java `invoke()`, .NET `InvokeAsync()` | latest discovery price as string money |
| Token-metered LLM | Python `invoke_llm()`, TypeScript `invokeLlm()`, Go `InvokeLLM()`, Java `invokeLlm()`, .NET `InvokeLlmAsync()` | optional cap as string money; never send fixed-price cost |

## SDK Parity E2E

The real Gateway E2E entrypoint for all five SDKs is:

```bash
export SYNAPSE_OWNER_PRIVATE_KEY='0x...'
export SYNAPSE_AGENT_KEY='agt_xxx_your_real_key'
bash scripts/e2e/sdk_parity_e2e.sh --env staging
```

The script first verifies owner login, credential issue, balance, usage logs, and provider registration guide through each selected SDK's `SynapseAuth` / `SynapseProvider` surface. It then runs the shared runtime E2E for health, discovery, fixed-price invoke, receipt lookup, token-metered LLM invoke, validation failures, and invalid credential handling.

For a private test gateway, use:

```bash
export SYNAPSE_OWNER_PRIVATE_KEY='0x...'
export SYNAPSE_GATEWAY_URL='https://your-private-gateway.example.com'
bash scripts/e2e/sdk_parity_e2e.sh --env local
```

This does not reintroduce a public local environment preset. The local target is only an explicit URL override for test automation. The script may install missing local toolchains; .NET is pinned to SDK 8.0 under `$HOME/.synapse-network-sdk-e2e/dotnet` if needed.

By default the fixed-price path first selects the Synapse first-party smoke service `svc_synapse_echo`, then falls back to any free fixed-price API service. If staging has neither, set `SYNAPSE_E2E_FIXED_SERVICE_ID`, `SYNAPSE_E2E_FIXED_COST_USDC`, and `SYNAPSE_E2E_FIXED_PAYLOAD_JSON` explicitly.

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

- `staging`: `https://api-staging.synapse-network.ai`
- Chain: Arbitrum Sepolia testnet
- Asset: MockUSDC for integration testing, not production USDC

Production launch will switch public examples and tests from `staging` to `prod`.

Python:

- `api_key`: explicit parameter first, then `SYNAPSE_AGENT_KEY`, then legacy `SYNAPSE_API_KEY`.
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
3. For fixed-price APIs, pass `cost_usdc` / `costUsdc` from latest discovery price. Smoke examples default to `svc_synapse_echo`, a free first-party echo service that returns the JSON object payload unchanged. If price changes, the gateway rejects the call and the caller should rediscover.
4. For token-metered LLM services, call `invoke_llm()` / `invokeLlm()` with optional `max_cost_usdc` / `maxCostUsdc`; final Provider `usage` drives the actual charge.

## Common Failures

### `api_key is required`

No `api_key` was passed and `SYNAPSE_AGENT_KEY` is not set. New users should issue an agent credential first, then pass the returned token to `SynapseClient`. `SYNAPSE_API_KEY` remains a legacy fallback for older Python users, but new docs and examples should use `SYNAPSE_AGENT_KEY`.

```bash
export SYNAPSE_AGENT_KEY='agt_xxx_your_real_key'
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

From the repository root:

```bash
cd python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_client_unit.py -q
export SYNAPSE_AGENT_KEY='agt_xxx_your_real_key'
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query 'quotes'
```

```bash
cd typescript
npm run test:unit
```

Runnable examples exist for every SDK:

```bash
export SYNAPSE_AGENT_KEY='agt_xxx_your_real_key'
PYTHONPATH=python python3 python/examples/free_service_smoke.py
npm run example:free --prefix typescript
go -C go run ./examples/free_service_smoke
mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.FreeServiceSmoke
dotnet run --project dotnet/examples/free-service-smoke/free-service-smoke.csproj
```
