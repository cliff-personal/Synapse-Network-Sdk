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

### 3.5 服务发现、报价、调用

```ts
const services = await client.discover({ limit: 20 });
const serviceId = services[0]?.serviceId!;

const quote = await client.quote(serviceId);
const result = await client.invoke(
  serviceId,
  { prompt: "hello" },
  {
    idempotencyKey: "job-001",
    pollTimeoutMs: 60_000,
  }
);

console.log(quote.quoteId);
console.log(result.invocationId, result.status, result.chargedUsdc);
```

## 4. 自动化验收

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/typescript
npm run lint
npm run test:e2e
npm run test:new-consumer
```

## 5. 与 Python SDK 的当前对比

| 能力 | TypeScript | Python |
|---|---|---|
| Owner 登录 | yes | yes |
| 充值登记 | yes | yes |
| Credential 颁发 | yes | yes |
| Discover / Quote / Invoke | yes | yes |
| 新钱包冷启动 E2E | yes | yes |
| API 风格一致性 | 基准实现 | 已补齐 TS 风格别名 |

