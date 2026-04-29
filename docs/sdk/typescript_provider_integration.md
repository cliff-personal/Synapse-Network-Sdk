# Synapse TypeScript Provider SDK Integration Guide

## 1. 目标

让 TypeScript 用户可以直接以 Provider 身份接入 Synapse，而不是自己手写：

1. 钱包 challenge / sign / verify
2. provider secret 生命周期
3. service manifest 最小注册 payload
4. 注册后的状态读取

当前 TypeScript SDK 的 provider 入口是 `auth.provider()`。它返回 `SynapseProvider` facade，但底层仍然使用 `SynapseAuth` 的 owner wallet / JWT，因为 Provider onboarding 在工程真相里属于 **owner wallet 控制面**。

---

## 2. 当前能力

这次补齐后，TypeScript SDK 已支持：

1. `auth.provider()`
2. `provider.issueSecret()`
3. `provider.listSecrets()`
4. `provider.deleteSecret()`
5. `provider.getRegistrationGuide()`
6. `provider.parseCurlToServiceManifest()`
7. `provider.registerService()`
8. `provider.listServices()`
9. `provider.getService()`
10. `provider.getServiceStatus()`
11. `provider.updateService()`
12. `provider.deleteService()`
13. `provider.pingService()`
14. `provider.getServiceHealthHistory()`
15. `provider.getEarningsSummary()`
16. `provider.getWithdrawalCapability()`
17. `provider.createWithdrawalIntent()`
18. `provider.listWithdrawals()`

这些公开方法返回命名 TypeScript interface，例如 `ProviderRegistrationGuide`、`ServiceManifestDraft`、`ProviderServiceUpdateResult`、`ProviderWithdrawalIntentResult`，不返回 raw `Record<string, unknown>`。

---

## 3. 最小接入代码

```ts
import { Wallet } from "ethers";
import { SynapseAuth } from "@synapse-network/sdk";

const wallet = new Wallet(process.env.PROVIDER_PRIVATE_KEY!);

const auth = SynapseAuth.fromWallet(wallet, {
  environment: "staging",
});

const jwt = await auth.getToken();
console.log(jwt);

const provider = auth.provider();

const issued = await provider.issueSecret({
  name: "provider-secret-prod",
  rpm: 180,
  creditLimit: 25,
  resetInterval: "monthly",
});

console.log(issued.secret.id, issued.secret.maskedKey);

const registered = await provider.registerService({
  serviceName: "SEA Invoice OCR",
  endpointUrl: "https://provider.example.com/invoke",
  basePriceUsdc: "0.008",
  descriptionForModel: "Extract structured invoice fields from invoice images.",
});

console.log(registered.serviceId);

const status = await provider.getServiceStatus(registered.serviceId);
console.log(status.lifecycleStatus, status.health.overallStatus, status.runtimeAvailable);
```

LLM services use the dedicated token-metered helper:

```ts
const llm = await provider.registerLlmService({
  serviceName: "DeepSeek Chat",
  serviceId: "svc_deepseek_chat",
  endpointUrl: "https://provider.example.com/llm/deepseek-chat",
  descriptionForModel: "OpenAI-compatible chat completion endpoint.",
  inputPricePer1MTokensUsdc: "0.140000",
  outputPricePer1MTokensUsdc: "0.280000",
  defaultMaxOutputTokens: 2048,
  maxAutoHoldUsdc: "0.050000",
  requestTimeoutMs: 120000,
});

console.log(llm.serviceId);
```

---

## 4. 设计原则

### 4.1 为什么 Provider 能力从 `SynapseAuth` 派生

因为当前工程真相是：

1. Provider 不是第二套账户体系
2. Provider role 绑定在 owner wallet scope
3. 服务注册走 bearer JWT 控制面

所以最自然的 SDK 入口就是：

`wallet -> SynapseAuth -> SynapseProvider`

`SynapseProvider` 是 provider publishing facade，不是新的 root auth。已有 `auth.registerProviderService()` 等方法继续兼容，推荐新代码使用 `provider.registerService()`。

### 4.2 最小注册输入

`provider.registerService()` 对外只要求：

1. `serviceName`
2. `endpointUrl`
3. `basePriceUsdc`
4. `descriptionForModel`

`provider.registerLlmService()` 使用同样的 owner scope，但把 `serviceKind=llm` 和
`priceModel=token_metered` 固定写入 manifest。LLM 价格必须使用
`inputPricePer1MTokensUsdc` / `outputPricePer1MTokensUsdc`，不要使用
`pricePerToken`。

SDK 自动补：

1. `serviceId` / `agentToolName`
2. 最小 input / output schema
3. `gateway_signed` auth
4. `/health` healthCheck
5. `providerProfile.displayName`
6. `payoutAccount` 默认绑定当前 wallet
7. `governance.termsAccepted = true`
8. `governance.riskAcknowledged = true`

这就是 TypeScript 版本的最低成本 Provider onboarding。

---

## 5. 当前 contract 映射

Provider 工作流文档说的是：

1. `description_for_model`
2. `service_manifest`
3. `provider_profile`
4. `payout_account`

当前 Gateway 实际接口 `POST /api/v1/services` 用的是：

1. `summary`
2. `invoke`
3. `providerProfile`
4. `payoutAccount`

TypeScript SDK 对外继续保留更产品化的 `descriptionForModel`，内部映射到 Gateway 的 `summary`。

---

## 6. 状态读取语义

`provider.getServiceStatus(serviceId)` 返回的是控制面状态，而不是 public discover 的最终可见性承诺。

当前它组合了：

1. `lifecycleStatus`
2. `runtimeAvailable`
3. `health.overallStatus`

需要讲真话：

1. `status=active` 不等于 public discover 已可见
2. public discover 还依赖健康检查与搜索索引
3. 所以 Provider onboarding 的成功标准，以 `/api/v1/services` owner list 为准

---

## 7. 对应测试

对应测试方案：

- `docs/test/typescript-provider-onboarding-e2e-plan.md`

对应 live e2e 代码：

- `typescript/tests/e2e/provider.test.ts`
