<p align="center">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="./assets/synapse-network-logo.svg" alt="SynapseNetwork logo" width="440" />
</p>

# SynapseNetwork SDK

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/TypeScript-available-blue.svg" />
  <img src="https://img.shields.io/badge/Go-preview-blue.svg" />
  <img src="https://img.shields.io/badge/Java-17+-blue.svg" />
  <img src="https://img.shields.io/badge/.NET-8.0-blue.svg" />
  <img src="https://img.shields.io/badge/Status-Public%20Preview-orange.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

Python, TypeScript, Go, Java, and .NET SDKs for AI agents and developers building on SynapseNetwork.

<!-- @synapse-context:quickstart -->

SynapseNetwork lets an agent discover services, invoke them through a gateway, and settle the call with an auditable receipt. The fastest integration path is:

1. Get an Agent Key (`agt_xxx`) from the Synapse Gateway Dashboard.
2. Create a `SynapseClient`.
3. Search, invoke, and read the receipt.

> Public Preview default: SDK examples use `staging`, backed by `https://api-staging.synapse-network.ai`.
> After production launch, replace the public examples and tests with the `prod` environment.

## Staging Public Preview

Today, public developer onboarding runs on staging:

- Gateway: `https://api-staging.synapse-network.ai`
- App docs: [staging.synapse-network.ai/docs/sdk](https://staging.synapse-network.ai/docs/sdk)
- Chain: Arbitrum Sepolia testnet
- Asset: MockUSDC for integration testing, not production USDC

Recommended path:

1. Connect a wallet in the staging Gateway Dashboard.
2. Get or issue an Agent Key and export it as `SYNAPSE_AGENT_KEY`.
3. Set `SYNAPSE_ENV=staging`.
4. Use the free first-party `svc_synapse_echo` smoke service first, or fund staging balance with MockUSDC before paid test calls.
5. Run one fixed-price API invoke and one token-metered LLM invoke.
6. Read the invocation receipt and verify settlement metadata.

Developers should pass staging before any future production migration. Production docs and examples stay reserved until production DNS, contracts, gateway health, and docs deployment are verified.

## Choose Your Integration Path

| Goal | Use |
|---|---|
| Connect SynapseNetwork to an agent framework such as Cursor, Claude Desktop, or LangChain | Official MCP server: `@synapse-network-ai/mcp-server` with `SYNAPSE_AGENT_KEY=agt_xxx` |
| Write application code that invokes services directly | This SDK with `SynapseClient` |
| Issue Agent Keys or publish provider APIs | Advanced owner/provider APIs: `SynapseAuth` and `auth.provider()` |

## Two Invocation Modes

| Mode | Use for | SDK method | Required cost parameter | Billing result |
|---|---|---|---|---|
| Fixed-price API invoke | Normal API services discovered from the marketplace | Python/TypeScript `invoke()`, Go `Invoke()`, Java `invoke()`, .NET `InvokeAsync()` | Pass latest discovery price as `cost_usdc` / `costUsdc` / `CostUSDC` / `CostUsdc` | Gateway rejects with `PRICE_MISMATCH` if the live price changed |
| Token-metered LLM invoke | LLM services registered with `serviceKind=llm` and `priceModel=token_metered` | Python `invoke_llm()`, TypeScript `invokeLlm()`, Go `InvokeLLM()`, Java `invokeLlm()`, .NET `InvokeLlmAsync()` | Do not pass fixed-price cost; optional cap is `max_cost_usdc` / `maxCostUsdc` / `MaxCostUSDC` / `MaxCostUsdc` | Gateway holds a cap, then charges final provider-reported token usage |

Do not recompute money with floating-point math. Pass discovered prices and spend caps through exactly; prefer string amounts such as `"0.05"` when the SDK method accepts strings.

## Gateway Docs

| Surface | Link | Status |
|---|---|---|
| SDK Hub | [staging.synapse-network.ai/docs/sdk](https://staging.synapse-network.ai/docs/sdk) | Public Preview |
| Python SDK | [staging.synapse-network.ai/docs/sdk/python](https://staging.synapse-network.ai/docs/sdk/python) | Public Preview |
| TypeScript SDK | [staging.synapse-network.ai/docs/sdk/typescript](https://staging.synapse-network.ai/docs/sdk/typescript) | Public Preview |
| Production docs | Reserved until production docs are live | Reserved |

## Gateway Environments

| Environment | Gateway URL | Intended use |
|---|---|---|
| `staging` | `https://api-staging.synapse-network.ai` | Public preview, test assets, integration trials |

Resolution rules:

1. Explicit `gateway_url` / `gatewayUrl`
2. Explicit `environment`
3. Python only: `SYNAPSE_GATEWAY`
4. Python only: `SYNAPSE_ENV`
5. Default: `staging`

The SDK never probes DNS and never falls back between environments automatically. This prevents production credentials or funds from being routed to the wrong gateway.

## Choose Your SDK Surface

| Goal | Use | Credential |
|---|---|---|
| Let an agent call services | `SynapseClient` | Agent Key (`agt_xxx`) |
| Issue, rotate, or revoke agent keys | `SynapseAuth` | Owner wallet / JWT |
| Publish and manage provider APIs | `SynapseProvider` via `auth.provider()` | Owner wallet / JWT |

Provider is an owner-scoped supply-side role, not a separate root account. Keep ordinary agent runtime code on `SynapseClient`; use `SynapseProvider` only when you are registering or operating services exposed through SynapseNetwork.

## Official SDK Coverage

| Language | Package path | Current coverage |
|---|---|---|
| Python | `python/` | Consumer, owner auth, provider publishing |
| TypeScript | `typescript/` | Consumer, owner auth, provider publishing |
| Go | `go/` | Consumer, owner auth, provider publishing |
| Java/JVM | `java/` | Consumer, owner auth, provider publishing; Kotlin can call the Java SDK |
| .NET | `dotnet/` | Consumer, owner auth, provider publishing |

All five SDKs expose the same public capability families: agent runtime, owner wallet auth, credential management, balance/deposit helpers, usage/finance reads, and provider lifecycle/withdrawal helpers. The exact naming follows each language's conventions, but the Gateway contract and money rules stay consistent.

## Examples By SDK

All runnable examples default to staging and read `SYNAPSE_AGENT_KEY`.
The fixed-price smoke examples first call `svc_synapse_echo`, then fall back to another free fixed-price service if echo is unavailable.

| SDK | Free fixed-price smoke | LLM smoke | Full E2E |
|---|---|---|---|
| Python | `PYTHONPATH=python python3 python/examples/free_service_smoke.py` | `PYTHONPATH=python python3 python/examples/llm_smoke.py` | `PYTHONPATH=python python3 python/examples/e2e.py` |
| TypeScript | `npm run example:free --prefix typescript` | `npm run example:llm --prefix typescript` | `npm run example:e2e --prefix typescript` |
| Go | `go -C go run ./examples/free_service_smoke` | `go -C go run ./examples/llm_smoke` | `go -C go run ./examples/e2e` |
| Java/JVM | `mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.FreeServiceSmoke` | `mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.LlmSmoke` | `mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.E2eSmoke` |
| .NET | `dotnet run --project dotnet/examples/free-service-smoke/free-service-smoke.csproj` | `dotnet run --project dotnet/examples/llm-smoke/llm-smoke.csproj` | `dotnet run --project dotnet/examples/e2e/e2e.csproj` |

To run every SDK through the same real Gateway E2E harness:

```bash
export SYNAPSE_OWNER_PRIVATE_KEY=0x...
export SYNAPSE_AGENT_KEY=agt_xxx
bash scripts/e2e/sdk_parity_e2e.sh --env staging --skip-install
```

For a private gateway test target, use `--env local` with an explicit `SYNAPSE_GATEWAY_URL`; `local` is not a public SDK environment preset.

## Agent Quickstart: Python

Step 1: get your Agent Key from the Synapse Gateway Dashboard.

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

Step 2: let your agent discover and work.

```bash
pip install synapse-client
export SYNAPSE_ENV=staging
export SYNAPSE_AGENT_KEY=agt_xxx
```

```python
from synapse_client import SynapseClient

client = SynapseClient()

services = client.search("svc_synapse_echo", limit=10)
service = services[0]

result = client.invoke(
    service.service_id,
    {"message": "hello from Synapse SDK smoke", "metadata": {"scenario": "quickstart"}},
    cost_usdc=str(service.price_usdc),
    idempotency_key="agent-job-001",
)

receipt = client.get_invocation(result.invocation_id)
print(receipt.invocation_id, receipt.status, receipt.charged_usdc)
```

If your wallet has no balance yet, start with services whose `price_usdc` is `0`. Paid services require funded balance, available credits, and a credential budget that allows the call.

## Agent Quickstart: TypeScript

Step 1: get your Agent Key from the Synapse Gateway Dashboard.

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

Step 2: pass the key to the SDK.

The npm organization is `synapse-network-ai`; use the `@synapse-network-ai/*` scope for official packages.

```bash
npm install @synapse-network-ai/sdk
```

```ts
import { SynapseClient } from "@synapse-network-ai/sdk";

const agentKey = process.env.SYNAPSE_AGENT_KEY;
if (!agentKey) {
  throw new Error("SYNAPSE_AGENT_KEY is required");
}

const client = new SynapseClient({
  credential: agentKey,
  environment: "staging",
});

const services = await client.search("svc_synapse_echo", {
  limit: 10,
});
const service = services[0];

const result = await client.invoke(
  service.serviceId ?? service.id!,
  { message: "hello from Synapse SDK smoke", metadata: { scenario: "quickstart" } },
  {
    costUsdc: String(service.pricing?.amount ?? "0"),
    idempotencyKey: "agent-job-001",
  }
);

const receipt = await client.getInvocation(result.invocationId);
console.log(receipt.invocationId, receipt.status, receipt.chargedUsdc);
```

TypeScript does not read environment variables by itself. Read them in your app and pass `environment` or `gatewayUrl` explicitly.

Python reads `SYNAPSE_AGENT_KEY` by default. `SYNAPSE_API_KEY` remains a legacy compatibility alias, but new examples should use `SYNAPSE_AGENT_KEY`.

### LLM token-metered calls

LLM services registered with `serviceKind=llm` and `priceModel=token_metered` use `invoke_llm()` / `invokeLlm()`. Do not pass `cost_usdc` / `costUsdc`; pass optional `max_cost_usdc` / `maxCostUsdc` or let Gateway compute the automatic hold. Streaming is rejected in V1 so Gateway can capture final usage safely.

```python
result = client.invoke_llm(
    "svc_deepseek_chat",
    {"messages": [{"role": "user", "content": "hello"}], "max_tokens": 512},
    max_cost_usdc="0.010000",
)
print(result.usage.input_tokens, result.synapse.charged_usdc, result.synapse.released_usdc)
```

```ts
const result = await client.invokeLlm(
  "svc_deepseek_chat",
  { messages: [{ role: "user", content: "hello" }], max_tokens: 512 },
  { maxCostUsdc: "0.010000" }
);
console.log(result.usage?.inputTokens, result.synapse?.chargedUsdc, result.synapse?.releasedUsdc);
```

## Advanced: Programmatic Credential Issuance

Use `SynapseAuth` only when an owner/backend service needs to issue credentials or register provider services programmatically. Ordinary agent runtime code should use `SynapseClient` with an existing `agt_xxx` key.

1. Authenticate an owner wallet.
2. Issue an agent credential with spending limits.
3. Hand that credential to an agent runtime.
4. Register provider services when publishing APIs to the marketplace.

Python:

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    "0xYOUR_PRIVATE_KEY",
    environment="staging",
)
issued = auth.issue_credential(name="agent-preview", maxCalls=100, creditLimit=5)
print(issued.credential.id, issued.token)
```

TypeScript:

```ts
import { Wallet } from "ethers";
import { SynapseAuth } from "@synapse-network-ai/sdk";

const wallet = new Wallet(process.env.OWNER_PRIVATE_KEY!);
const auth = SynapseAuth.fromWallet(wallet, { environment: "staging" });
const issued = await auth.issueCredential({
  name: "agent-preview",
  maxCalls: 100,
  creditLimit: 5,
});
console.log(issued.credential.id, issued.token);
```

## Provider Publishing

Use `SynapseProvider` when an owner wants to publish an API as a SynapseNetwork service. It is a facade over owner-authenticated provider control-plane methods, so existing `SynapseAuth` methods remain supported.

Python:

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key("0xYOUR_PRIVATE_KEY", environment="staging")
provider = auth.provider()

secret = provider.issue_secret(name="weather-api")
guide = provider.get_registration_guide()
service = provider.register_service(
    service_name="Weather API",
    endpoint_url="https://provider.example.com/invoke",
    base_price_usdc="0.001",
    description_for_model="Returns weather data for a city.",
)
status = provider.get_service_status(service.service_id)
```

TypeScript:

```ts
import { Wallet } from "ethers";
import { SynapseAuth } from "@synapse-network-ai/sdk";

const auth = SynapseAuth.fromWallet(new Wallet(process.env.OWNER_PRIVATE_KEY!), {
  environment: "staging",
});
const provider = auth.provider();

const secret = await provider.issueSecret({ name: "weather-api" });
const guide = await provider.getRegistrationGuide();
const service = await provider.registerService({
  serviceName: "Weather API",
  endpointUrl: "https://provider.example.com/invoke",
  basePriceUsdc: "0.001",
  descriptionForModel: "Returns weather data for a city.",
});
const status = await provider.getServiceStatus(service.serviceId);
```

Credential handling and vulnerability reporting live in [SECURITY.md](./SECURITY.md).

## Python Examples

The Python examples are staging-first and live under `python/examples`.

```bash
cd python
```

Run consumer smoke examples:

```bash
export SYNAPSE_AGENT_KEY=agt_xxx
PYTHONPATH="$PWD" .venv/bin/python examples/free_service_smoke.py
PYTHONPATH="$PWD" .venv/bin/python examples/llm_smoke.py
PYTHONPATH="$PWD" .venv/bin/python examples/e2e.py
```

Register a provider service on staging:

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/provider_staging_onboarding.py \
  --provider-private-key "$SYNAPSE_PROVIDER_PRIVATE_KEY" \
  --endpoint-url "https://your-provider.example.com/invoke" \
  --service-name "Weather API" \
  --description "Returns weather data for a city." \
  --price-usdc 0
```

Call a provider service with an existing Agent Key:

```bash
export SYNAPSE_AGENT_KEY=agt_xxx
PYTHONPATH="$PWD" .venv/bin/python examples/consumer_call_provider.py \
  --service-id "weather_api" \
  --payload-json '{"prompt":"hello"}'
```

Create a fresh staging wallet, issue an Agent Key, and invoke a free service:

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/consumer_wallet_to_invoke.py \
  --query "free"
```

## Current API Boundary

Supported today:

- Consumer discovery/search
- Price-asserted invoke
- Price-mismatch rediscovery helper
- Invocation receipt lookup
- Gateway health and empty-discovery diagnostics
- Owner auth and credential issue/list/update/revoke/rotate/delete/quota/audit logs
- Balance, voucher, usage, finance audit, and risk overview helpers
- Provider publishing facade through `auth.provider()`
- Provider secret issue/list/delete
- Provider service register/list/get/status/update/delete/ping/registration guide/health history
- Provider earnings and withdrawal intent/list/capability helpers

Public owner/provider helpers return named SDK objects such as `UsageLogList`, `ProviderRegistrationGuide`, and `ProviderWithdrawalIntentResult`, not raw maps.

Not yet wrapped:

- Refunds, notifications, community, and event APIs
- On-chain deposit transaction signing helpers

See [docs/sdk/capability_inventory.md](./docs/sdk/capability_inventory.md) for the detailed inventory.

Finance and withdrawal helpers are explicit API wrappers only. The SDK will not automatically move funds, sign transactions, or submit high-impact financial actions on behalf of an agent.

## Development

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_client_unit.py synapse_client/test/test_auth_unit.py -q
```

```bash
cd typescript
npm install
npm run test:unit
npm run lint
```

## License

MIT License. See `LICENSE` for more information.
