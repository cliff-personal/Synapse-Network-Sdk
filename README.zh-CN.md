<p align="center">
  <a href="./README.md">English</a> · <strong>简体中文</strong>
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

面向 AI Agent 和开发者的 SynapseNetwork Python / TypeScript / Go / Java / .NET SDK。

SynapseNetwork 让 Agent 可以发现服务、通过 gateway 调用服务，并用可审计 receipt 完成结算验证。最快接入路径是：

1. 从 Synapse Gateway Dashboard 获取 Agent Key（`agt_xxx`）。
2. 创建 `SynapseClient`。
3. 搜索服务、调用服务、读取 receipt。

> Public Preview 默认使用 `staging`，对应 `https://api-staging.synapse-network.ai`。
> 生产环境上线后，再把公开示例和测试统一切换到 `prod`。

## Staging Public Preview

当前公开开发者接入统一走 staging：

- Gateway：`https://api-staging.synapse-network.ai`
- App docs：[staging.synapse-network.ai/docs/sdk](https://staging.synapse-network.ai/docs/sdk)
- 链：Arbitrum Sepolia 测试网
- 资产：MockUSDC，用于接入测试，不是生产 USDC

推荐路径：

1. 在 staging Gateway Dashboard 连接钱包。
2. 获取或签发 Agent Key，并设置为 `SYNAPSE_AGENT_KEY`。
3. 设置 `SYNAPSE_ENV=staging`。
4. 先调用免费服务；如需付费测试，先准备 MockUSDC 测试余额。
5. 跑通一次 fixed-price API invoke 和一次 token-metered LLM invoke。
6. 读取 invocation receipt，确认结算元数据。

开发者应先在 staging 验证通过。Production docs 与示例会在生产 DNS、合约、gateway health 和 docs deployment 验证后再统一切换。

## 选择你的接入路径

| 目标 | 使用 |
|---|---|
| 把 SynapseNetwork 接入 Cursor、Claude Desktop、LangChain 等 Agent framework | 官方 MCP server：`@synapse-network-ai/mcp-server`，设置 `SYNAPSE_AGENT_KEY=agt_xxx` |
| 在应用代码里直接调用服务 | 本 SDK 的 `SynapseClient` |
| 签发 Agent Key 或发布 Provider API | 高级 owner/provider API：`SynapseAuth` 和 `auth.provider()` |

## 两种调用模式

| 模式 | 适用场景 | SDK 方法 | 必传费用参数 | 计费结果 |
|---|---|---|---|---|
| Fixed-price API invoke | marketplace 发现的普通 API 服务 | Python/TypeScript `invoke()`、Go `Invoke()`、Java `invoke()`、.NET `InvokeAsync()` | 传最新 discovery price：`cost_usdc` / `costUsdc` / `CostUSDC` / `CostUsdc` | 如果 live price 已变化，Gateway 用 `PRICE_MISMATCH` 拒绝 |
| Token-metered LLM invoke | `serviceKind=llm` 且 `priceModel=token_metered` 的 LLM 服务 | Python `invoke_llm()`、TypeScript `invokeLlm()`、Go `InvokeLLM()`、Java `invokeLlm()`、.NET `InvokeLlmAsync()` | 不传 fixed-price cost；可选上限是 `max_cost_usdc` / `maxCostUsdc` / `MaxCostUSDC` / `MaxCostUsdc` | Gateway 先冻结上限，再按 Provider 返回的 final token usage 扣费 |

不要用浮点数重新计算金额。调用时传 discovery 得到的价格或预算上限；SDK 方法支持时优先使用字符串金额，例如 `"0.05"`。

## Gateway 文档

| 页面 | 链接 | 状态 |
|---|---|---|
| SDK Hub | [staging.synapse-network.ai/docs/sdk](https://staging.synapse-network.ai/docs/sdk) | Public Preview |
| Python SDK | [staging.synapse-network.ai/docs/sdk/python](https://staging.synapse-network.ai/docs/sdk/python) | Public Preview |
| TypeScript SDK | [staging.synapse-network.ai/docs/sdk/typescript](https://staging.synapse-network.ai/docs/sdk/typescript) | Public Preview |
| 生产文档 | 生产文档上线前预留 | Reserved |

## Gateway 运行环境

| 环境 | Gateway URL | 用途 |
|---|---|---|
| `staging` | `https://api-staging.synapse-network.ai` | Public preview、测试资产和接入试跑 |

解析优先级：

1. 显式 `gateway_url` / `gatewayUrl`
2. 显式 `environment`
3. 仅 Python：`SYNAPSE_GATEWAY`
4. 仅 Python：`SYNAPSE_ENV`
5. 默认：`staging`

SDK 不会自动探测 DNS，也不会在环境之间自动 fallback。这样可以避免生产凭据或资金被错误路由到其他 gateway。

## 选择你的 SDK 入口

| 目标 | 使用 | 凭据 |
|---|---|---|
| 让 Agent 调用服务 | `SynapseClient` | Agent Key（`agt_xxx`） |
| 签发、轮换、撤销 Agent Key | `SynapseAuth` | Owner wallet / JWT |
| 发布和管理 Provider API | `SynapseProvider`，通过 `auth.provider()` 获取 | Owner wallet / JWT |

Provider 是 owner scope 下的供给侧角色，不是第二套根账户体系。普通 Agent runtime 代码保持使用 `SynapseClient`；只有注册或运营 SynapseNetwork 服务时才使用 `SynapseProvider`。

## 官方 SDK 覆盖范围

| 语言 | 包路径 | 当前覆盖 |
|---|---|---|
| Python | `python/` | Consumer、owner auth、provider publishing |
| TypeScript | `typescript/` | Consumer、owner auth、provider publishing |
| Go | `go/` | Consumer、owner auth、provider publishing |
| Java/JVM | `java/` | Consumer、owner auth、provider publishing；Kotlin 可直接调用 Java SDK |
| .NET | `dotnet/` | Consumer、owner auth、provider publishing |

五种 SDK 都覆盖同一组公开能力：Agent runtime、owner wallet auth、credential 管理、balance/deposit helper、usage/finance 读取，以及 provider lifecycle/withdrawal helper。方法命名遵循各语言习惯，但 Gateway contract 和金额规则保持一致。

## 各 SDK 示例

所有 runnable examples 默认使用 staging，并读取 `SYNAPSE_AGENT_KEY`。

| SDK | 免费 fixed-price smoke | LLM smoke | 完整 E2E |
|---|---|---|---|
| Python | `PYTHONPATH=python python3 python/examples/free_service_smoke.py` | `PYTHONPATH=python python3 python/examples/llm_smoke.py` | `PYTHONPATH=python python3 python/examples/e2e.py` |
| TypeScript | `npm run example:free --prefix typescript` | `npm run example:llm --prefix typescript` | `npm run example:e2e --prefix typescript` |
| Go | `go -C go run ./examples/free_service_smoke` | `go -C go run ./examples/llm_smoke` | `go -C go run ./examples/e2e` |
| Java/JVM | `mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.FreeServiceSmoke` | `mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.LlmSmoke` | `mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.E2eSmoke` |
| .NET | `dotnet run --project dotnet/examples/free-service-smoke/free-service-smoke.csproj` | `dotnet run --project dotnet/examples/llm-smoke/llm-smoke.csproj` | `dotnet run --project dotnet/examples/e2e/e2e.csproj` |

统一跑全部 SDK：

```bash
export SYNAPSE_OWNER_PRIVATE_KEY=0x...
export SYNAPSE_AGENT_KEY=agt_xxx
bash scripts/e2e/sdk_parity_e2e.sh --env staging --skip-install
```

如需测试私有 gateway，使用 `--env local` 并显式设置 `SYNAPSE_GATEWAY_URL`；`local` 不是公开 SDK environment preset。

## Agent 快速接入：Python

步骤 1：从 Synapse Gateway Dashboard 获取 Agent Key。

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

步骤 2：让 Agent 自动发现服务并开始工作。

```bash
pip install synapse-client
export SYNAPSE_ENV=staging
export SYNAPSE_AGENT_KEY=agt_xxx
```

```python
from synapse_client import SynapseClient

client = SynapseClient()

services = client.search("free", limit=10)
service = services[0]

result = client.invoke(
    service.service_id,
    {"prompt": "hello"},
    cost_usdc=str(service.price_usdc),
    idempotency_key="agent-job-001",
)

receipt = client.get_invocation(result.invocation_id)
print(receipt.invocation_id, receipt.status, receipt.charged_usdc)
```

如果钱包暂时没有余额，先选择 `price_usdc` 为 `0` 的免费服务。付费服务需要账户余额、可用 credits，以及允许本次调用的 credential budget。

## Agent 快速接入：TypeScript

步骤 1：从 Synapse Gateway Dashboard 获取 Agent Key。

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

步骤 2：把 key 传给 SDK。

npm 组织是 `synapse-network-ai`；官方包统一使用 `@synapse-network-ai/*` scope。

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

const services = await client.search("free", {
  limit: 10,
});
const service = services[0];

const result = await client.invoke(
  service.serviceId ?? service.id!,
  { prompt: "hello" },
  {
    costUsdc: String(service.pricing?.amount ?? "0"),
    idempotencyKey: "agent-job-001",
  }
);

const receipt = await client.getInvocation(result.invocationId);
console.log(receipt.invocationId, receipt.status, receipt.chargedUsdc);
```

TypeScript SDK 不会自动读取环境变量。请在你的应用中读取环境变量，然后显式传入 `environment` 或 `gatewayUrl`。

Python 默认读取 `SYNAPSE_AGENT_KEY`。`SYNAPSE_API_KEY` 只作为 legacy 兼容别名保留，新示例统一使用 `SYNAPSE_AGENT_KEY`。

### LLM 按 token 计费调用

使用 `serviceKind=llm` 和 `priceModel=token_metered` 注册的 LLM 服务，需要调用 `invoke_llm()` / `invokeLlm()`。不要传 `cost_usdc` / `costUsdc`；可以传可选的 `max_cost_usdc` / `maxCostUsdc`，也可以交给 Gateway 自动冻结。V1 会拒绝 streaming，确保 Gateway 能拿到 final usage 后再扣费。

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

## 高级用法：以代码方式签发凭据

只有当 owner/backend service 需要以代码方式签发凭据或注册 provider service 时，才使用 `SynapseAuth`。普通 Agent 运行时代码应使用已有 `agt_xxx` key 和 `SynapseClient`。

1. owner 钱包认证。
2. 签发带预算限制的 agent credential。
3. 把 credential 交给 Agent 运行时。
4. 发布 API 到 marketplace 时注册 provider service。

Python：

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    "0xYOUR_PRIVATE_KEY",
    environment="staging",
)
issued = auth.issue_credential(name="agent-preview", maxCalls=100, creditLimit=5)
print(issued.credential.id, issued.token)
```

TypeScript：

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

## Provider 发布接入

当 owner 想把自己的 API 发布成 SynapseNetwork service 时，使用 `SynapseProvider`。它是 owner-authenticated provider 控制面方法的 facade，已有 `SynapseAuth` 方法继续兼容。

Python：

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

TypeScript：

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

凭据处理和漏洞报告请查看 [SECURITY.md](./SECURITY.md)。

## Python 示例

Python examples 默认面向 staging，位于 `python/examples`。

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
```

在 staging 注册 provider service：

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/provider_staging_onboarding.py \
  --provider-private-key "$SYNAPSE_PROVIDER_PRIVATE_KEY" \
  --endpoint-url "https://your-provider.example.com/invoke" \
  --service-name "Weather API" \
  --description "Returns weather data for a city." \
  --price-usdc 0
```

使用已有 Agent Key 调用 provider service：

```bash
export SYNAPSE_AGENT_KEY=agt_xxx
PYTHONPATH="$PWD" .venv/bin/python examples/consumer_call_provider.py \
  --service-id "weather_api" \
  --payload-json '{"prompt":"hello"}'
```

创建新的 staging wallet、签发 Agent Key，并调用免费服务：

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/consumer_wallet_to_invoke.py \
  --query "free"
```

## 当前 API 边界

当前已支持：

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

公开 owner/provider helper 返回 `UsageLogList`、`ProviderRegistrationGuide`、`ProviderWithdrawalIntentResult` 等命名 SDK 对象，而不是 raw map。

尚未封装：

- Refunds、notifications、community、event APIs
- 链上 deposit transaction signing helpers

完整能力清单见 [docs/sdk/capability_inventory.md](./docs/sdk/capability_inventory.md)。

Finance 和 withdrawal helper 只是显式 API wrapper。SDK 不会代表 Agent 自动转移资金、签名交易或提交高影响资金操作。

## 开发

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

MIT License。更多信息见 `LICENSE`。
