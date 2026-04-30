# Synapse TypeScript SDK Integration Guide

## 当前状态

TypeScript SDK 覆盖当前 gateway 的 consumer/provider canonical main flow。

Consumer runtime 主链固定为：

1. owner 钱包登录
2. 创建 agent credential
3. discovery/search
4. fixed API: `invoke(serviceId, payload, { costUsdc })`
5. LLM service: `invokeLlm(serviceId, payload, { maxCostUsdc })`
6. receipt 查询

TypeScript SDK 不暴露 quote public API。当前 gateway 的正式运行时入口是单步 price-asserted invoke。

Staging 产品化 runbook:

1. https://staging.synapse-network.ai/docs/sdk/typescript
2. SDK Hub: https://staging.synapse-network.ai/docs/sdk

Production docs 先预留，等 production DNS、`/health` 和 docs deployment 验证后再作为主链路暴露。

## 安装

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/typescript
npm install
```

Peer dependency:

```bash
npm install ethers
```

## 配置

TypeScript SDK 使用显式配置：

```ts
const client = new SynapseClient({
  credential: issued.token,
  environment: "staging",
});
```

SDK 库内部不隐式读取环境变量；Node、browser、worker runtime 都由应用层决定如何传入配置。可用环境 preset：

1. `staging`: `https://api-staging.synapse-network.ai`

当前 staging 使用 Arbitrum Sepolia 测试网和 MockUSDC 测试资产。MockUSDC 只用于接入验证，不是生产 USDC。

生产环境上线后，公开示例和测试再统一切换到 `prod`。

显式 `gatewayUrl` 会覆盖 `environment`。

公开示例统一使用 `SYNAPSE_AGENT_KEY`：

```ts
const agentKey = process.env.SYNAPSE_AGENT_KEY;
if (!agentKey) throw new Error("SYNAPSE_AGENT_KEY is required");
```

## Agent-first 接入链路

Fresh setup 不应从 `credential: "agt_xxx"` 开始。agent credential 必须先由 owner wallet 通过 `SynapseAuth` 签发，然后再交给 `SynapseClient`。

固定顺序：

1. owner wallet 登录并拿到 JWT
2. 读取 balance / credits
3. 签发 agent credential
4. agent runtime 用 credential 搜索服务、调用服务、读取 receipt

如果 owner wallet 还没有余额，可以先选择 `price_usdc == 0` 的免费服务做 smoke path；`price_usdc > 0` 的服务需要先有可用余额、credits 或足够的 credential credit limit。

Staging 接入建议先完成：

1. `SYNAPSE_ENV=staging`
2. `SYNAPSE_AGENT_KEY=agt_xxx`
3. 免费 fixed-price API invoke
4. MockUSDC 余额准备后的付费 fixed-price API invoke
5. token-metered LLM invoke
6. receipt 查询和结算字段核对

## Owner 钱包登录

```ts
import { Wallet } from "ethers";
import { SynapseAuth } from "@synapse-network/sdk";

const wallet = new Wallet(process.env.OWNER_PRIVATE_KEY!);
const auth = SynapseAuth.fromWallet(wallet, {
  environment: "staging",
});

const jwt = await auth.getToken();
```

## 余额、充值与 Credential

```ts
const balance = await auth.getBalance();
console.log(balance.consumerAvailableBalance);

const intent = await auth.registerDepositIntent(txHash, 10);
const intentId =
  intent.intent.id ??
  intent.intent.intentId ??
  intent.intent.depositIntentId!;
const eventKey =
  intent.intent.eventKey ??
  intent.intent.event_key ??
  txHash;

await auth.confirmDeposit(intentId, eventKey);

const issued = await auth.issueCredential({
  name: "consumer-agent-01",
  maxCalls: 100,
  creditLimit: 5,
  rpm: 60,
});
```

## 服务发现与调用

`discover()` / `search()` 发送当前 gateway 的 discovery body：

```json
{
  "query": "market data",
  "tags": ["finance"],
  "page": 1,
  "pageSize": 20,
  "sort": "best_match"
}
```

SDK 继续兼容 `limit/offset` 入参，并映射为：

1. `page = floor(offset / limit) + 1`
2. `pageSize = limit`

示例：

```ts
import { SynapseClient } from "@synapse-network/sdk";

const client = new SynapseClient({
  credential: issued.token,
  environment: "staging",
});

const services = await client.search("market data", {
  limit: 20,
  offset: 0,
  tags: ["finance"],
  sort: "best_match",
});

const service = services[0];
const serviceId = service.serviceId ?? service.id!;

const result = await client.invoke(
  serviceId,
  { prompt: "hello" },
  {
    costUsdc: String(service.pricing?.amount ?? "0"),
    idempotencyKey: "job-001",
    pollTimeoutMs: 60_000,
  }
);

console.log(result.invocationId, result.status, result.chargedUsdc);
```

## 已知 serviceId 时直接调用

```ts
const result = await client.invoke(
  process.env.SYNAPSE_SERVICE_ID!,
  { prompt: "hello" },
  {
    costUsdc: process.env.SYNAPSE_SERVICE_PRICE_USDC!,
    idempotencyKey: "job-known-service-001",
  }
);

console.log(result.invocationId, result.status, result.chargedUsdc);
```

## LLM token-metered invoke

Provider-registered LLM services use `serviceKind=llm` and
`priceModel=token_metered`. The SDK helper intentionally does not send
`costUsdc`; Gateway either uses the optional `maxCostUsdc` cap or computes an
automatic pre-authorization hold, then captures only final Provider `usage`.

```ts
const result = await client.invokeLlm(
  "svc_deepseek_chat",
  {
    model: "deepseek-chat",
    messages: [{ role: "user", content: "Summarize this document." }],
    max_tokens: 512,
    // stream: true is rejected in Synapse V1
  },
  {
    idempotencyKey: "llm-job-001",
    maxCostUsdc: "0.010000", // optional
  }
);

console.log(result.usage?.inputTokens, result.usage?.outputTokens);
console.log(result.synapse?.chargedUsdc, result.synapse?.releasedUsdc);
```

Timeouts, disconnects, SSE responses, or missing final `usage` release the
entire hold and do not charge. V1 never bills from the estimated hold.

## 当前 Consumer API

1. `discover(opts)`
2. `search(query, opts)`
3. `invoke(serviceId, payload, opts)`
4. `invokeLlm(serviceId, payload, opts)`
5. `getInvocation(invocationId)`

## Provider 侧接入

TypeScript Provider onboarding 文档：

1. `docs/sdk/typescript_provider_integration.md`
2. `docs/test/typescript-provider-onboarding-e2e-plan.md`

TypeScript SDK 当前通过 `auth.provider()` / `SynapseProvider` 支持：

1. provider secret 创建、列举、删除
2. provider registration guide 与 curl manifest 解析
3. provider 服务注册、列举、读取、更新、删除
4. provider 服务 ping、状态查询、health history
5. provider earnings 与 withdrawals helper

Owner/provider helper 返回命名 TypeScript interface；例如 usage logs 返回 `UsageLogList`，registration guide 返回 `ProviderRegistrationGuide`，withdrawal intent 返回 `ProviderWithdrawalIntentResult`。公开 API 不返回 raw `Record<string, unknown>`。

Provider onboarding 成功标准以 owner `/api/v1/services` 列表为准，不以 public discovery 为准。

## 自动化验收

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/typescript
npm run lint
npm test
npm run test:e2e
npm run test:new-consumer
```
