# Synapse TypeScript SDK Integration Guide

## 1. 当前状态

TypeScript SDK 目前已经满足 **自动化接入** 的主链要求。

已覆盖能力：

1. Owner 钱包 challenge / sign / verify 登录
2. JWT 缓存
3. 链上充值后的 `deposit intent / confirm`
4. Agent credential 颁发与列举
5. 发现服务、报价、调用、轮询 receipt
6. 余额读取
7. 新用户冷启动 E2E 测试

代码入口：

1. `typescript/src/auth.ts`
2. `typescript/src/client.ts`
3. `typescript/tests/e2e/consumer.test.ts`
4. `typescript/tests/e2e/new-consumer.test.ts`

## 2. 安装

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/typescript
npm install
```

Peer dependency:

```bash
npm install ethers
```

## 3. 最短接入链路

### 3.1 Owner 钱包登录

```ts
import { Wallet } from "ethers";
import { SynapseAuth } from "@synapse-network/sdk";

const wallet = new Wallet(process.env.OWNER_PRIVATE_KEY!);
const auth = SynapseAuth.fromWallet(wallet, {
  gatewayUrl: "http://127.0.0.1:8000",
});

const jwt = await auth.getToken();
```

### 3.2 读取余额

```ts
const balance = await auth.getBalance();
console.log(balance.consumerAvailableBalance);
```

### 3.3 链上充值后登记到网关

```ts
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
```

### 3.4 创建 Agent Credential

```ts
const issued = await auth.issueCredential({
  name: "consumer-agent-01",
  maxCalls: 100,
  creditLimit: 5,
  rpm: 60,
});

const client = new SynapseClient({
  credential: issued.token,
  gatewayUrl: "http://127.0.0.1:8000",
});
```

### 3.5 服务发现与调用

Consumer 的 canonical runtime 流程是：

1. `discover()`
2. 选定 `serviceId`
3. `invoke(serviceId, payload, opts)` — SDK 在内部自动处理 quote → invoke → 轮询

如果运行时已经持有稳定 `serviceId`，可以直接跳到第 3 步。

```ts
const services = await client.discover({ limit: 20 });
const service = services.find((item) => item.serviceId || item.id);

if (!service) {
  throw new Error("No discoverable services are available yet.");
}

const serviceId = service.serviceId ?? service.id!;

// 一行搞定 — invoke() 内部自动完成 quote → invoke → settle
const result = await client.invoke(
  serviceId,
  { prompt: "hello" },
  {
    idempotencyKey: "job-001",
    pollTimeoutMs: 60_000,
  }
);

console.log(result.invocationId, result.status, result.chargedUsdc);
```

### 3.6 已知 serviceId 时直接调用

```ts
const knownServiceId = process.env.SYNAPSE_SERVICE_ID!;

// invoke() 自动处理 quote → invoke → settle，无需额外步骤
const result = await client.invoke(
  knownServiceId,
  { prompt: "hello" },
  {
    idempotencyKey: "job-known-service-001",
  }
);

console.log(result.invocationId, result.status, result.chargedUsdc);
```

### 3.7 平台免费 starter services

`Synapse-Network-Sdk` 仓库中的参考接口会被平台逐步发布为官方免费 starter services，供：

1. SDK smoke test
2. demo 调用
3. 新 consumer 的第一笔调用联调

建议：

1. 首次接入先用 `discover()` 找当前环境可用 starter service
2. 发现到目标后，把 `serviceId` 作为运行时主键缓存下来
3. 不要在代码里硬编码 provider endpoint URL，runtime 只认 `serviceId`

## 4. 自动化验收

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/typescript
npm run lint
npm test          # unit tests (no gateway needed)
npm run test:e2e
npm run test:new-consumer
```

现在 `consumer.test.ts` 与 `new-consumer.test.ts` 会显式验证：

1. `discover()` 能返回目标服务
2. 通过 discovery 选中的 `serviceId` 可以完成调用
3. 已知 `serviceId` 也可以直接完成 invoke（无需手工 quote）
4. 调用后余额会下降，receipt 可读取

## 5. 与 Python SDK 的当前对比

| 能力 | TypeScript | Python |
|---|---|---|
| Owner 登录 | yes | yes |
| 充值登记 | yes | yes |
| Credential 颁发 | yes | yes |
| Discover / Quote / Invoke | yes | yes |
| 新钱包冷启动 E2E | yes | yes |
| API 风格一致性 | 基准实现 | 已补齐 TS 风格别名 |

## 6. Provider 侧接入

TypeScript Provider onboarding 已拆成独立文档，见：

- `docs/sdk/typescript_provider_integration.md`
- `docs/test/typescript-provider-onboarding-e2e-plan.md`

现在 TypeScript SDK 也支持：

1. provider secret 创建与列举
2. provider 服务注册
3. provider 服务状态查询
