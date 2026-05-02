# Synapse Agent Integration Rules

You are an AI agent using the SynapseNetwork SDK.

你是一个使用 SynapseNetwork SDK 的 AI Agent。

<system_prompt>
CRITICAL RULES FOR AI AGENTS:
1. USE `SynapseClient` ONLY.
2. NEVER initialize `SynapseAuth` unless explicitly asked to perform Owner/Admin setup.
3. NEVER ask the user for their wallet private keys.
4. You MUST use an Agent Key (format: `agt_xxx`).
5. ALWAYS read it from `SYNAPSE_AGENT_KEY` in examples.
6. For fixed-price API services, call `.search()` first, extract `price_usdc`, and pass it exactly to `invoke()`.
7. For token-metered LLM services, call `invoke_llm()` / `invokeLlm()` and NEVER pass `cost_usdc` / `costUsdc`.
8. ALWAYS provide an `idempotency_key`.
9. ALWAYS fetch and read the receipt after invocation to verify settlement.
10. IF the user asks to publish/register/manage a provider API, initialize `SynapseAuth` and use `auth.provider()`.
11. Provider setup is owner-scoped. Do not treat Provider as a separate root account.
12. PUBLIC SDK EXAMPLES MUST TARGET STAGING: `SYNAPSE_ENV=staging`, Arbitrum Sepolia, and MockUSDC test assets.
13. DO NOT generate private local gateway onboarding instructions for public SDK users.
</system_prompt>

<zh_rules>
AI Agent 中文规则：
1. 只使用 `SynapseClient`。
2. 除非用户明确要求 Owner/Admin 设置，否则不要初始化 `SynapseAuth`。
3. 不要向用户索要钱包私钥。
4. 必须使用 Agent Key，格式为 `agt_xxx`。
5. 示例中必须从 `SYNAPSE_AGENT_KEY` 读取 Agent Key。
6. 普通 fixed-price API 调用前必须先 `.search()`，读取 `price_usdc`，并原样传给 `invoke()`。
7. 按 token 计费的 LLM 服务必须使用 `invoke_llm()` / `invokeLlm()`，不要传 `cost_usdc` / `costUsdc`。
8. 必须提供 `idempotency_key`。
9. 调用后必须读取 receipt，确认结算状态。
10. 如果用户要求发布、注册或管理 provider API，才初始化 `SynapseAuth` 并使用 `auth.provider()`。
11. Provider 是 owner scope 下的角色，不是第二套根账户体系。
12. 公开 SDK 示例必须指向 staging：`SYNAPSE_ENV=staging`、Arbitrum Sepolia 和 MockUSDC 测试资产。
13. 不要为公开 SDK 用户生成私有本地 gateway 接入说明。
</zh_rules>

Additional runtime preferences:

额外运行时建议：

1. If balance is unknown, prefer services whose price is `0`.
2. Do not use deprecated quote-first helpers.
3. Use `SynapseAuth` for owner/admin setup only when the user explicitly asks to issue credentials.
4. Use `SynapseProvider` from `auth.provider()` only when the user explicitly asks to publish or manage provider services.
5. For examples, use `python/examples/consumer_call_provider.py` to call a service, `python/examples/provider_staging_onboarding.py` to publish a provider API, and `python/examples/consumer_wallet_to_invoke.py` for a full fresh-wallet flow.

Python pattern:

Python 模式：

```python
import os

from synapse_client import SynapseClient

client = SynapseClient(api_key=os.environ["SYNAPSE_AGENT_KEY"], environment="staging")
services = client.search("free", limit=10)
service = services[0]
result = client.invoke(
    service.service_id,
    {"prompt": "hello"},
    cost_usdc=str(service.price_usdc),
    idempotency_key="agent-job-001",
)
receipt = client.get_invocation(result.invocation_id)
```

TypeScript pattern:

TypeScript 模式：

```ts
import { SynapseClient } from "@synapse-network-ai/sdk";

const agentKey = process.env.SYNAPSE_AGENT_KEY;
if (!agentKey) throw new Error("SYNAPSE_AGENT_KEY is required");

const client = new SynapseClient({ credential: agentKey, environment: "staging" });
const services = await client.search("free", { limit: 10 });
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
```

Token-metered LLM pattern:

```python
result = client.invoke_llm(
    "svc_deepseek_chat",
    {"messages": [{"role": "user", "content": "hello"}]},
    max_cost_usdc="0.010000",
    idempotency_key="llm-job-001",
)
```

```ts
const result = await client.invokeLlm(
  "svc_deepseek_chat",
  { messages: [{ role: "user", content: "hello" }] },
  { maxCostUsdc: "0.010000", idempotencyKey: "llm-job-001" }
);
```

Provider publishing pattern:

Provider 发布模式：

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key("0xOWNER_PRIVATE_KEY", environment="staging")
provider = auth.provider()
service = provider.register_service(
    service_name="Weather API",
    endpoint_url="https://provider.example.com/invoke",
    base_price_usdc="0.001",
    description_for_model="Returns weather data for a city.",
)
```

```ts
import { SynapseAuth } from "@synapse-network-ai/sdk";

const auth = SynapseAuth.fromWallet(wallet, { environment: "staging" });
const provider = auth.provider();
const service = await provider.registerService({
  serviceName: "Weather API",
  endpointUrl: "https://provider.example.com/invoke",
  basePriceUsdc: "0.001",
  descriptionForModel: "Returns weather data for a city.",
});
```
