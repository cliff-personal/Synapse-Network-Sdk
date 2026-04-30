<p align="center">
  <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

# Synapse SDK 文档 Hub

本目录是 SDK 侧的真实能力入口，覆盖能力清单、接入指南、provider onboarding 与测试计划。

## 文档入口

1. [SDK Capability Inventory](./capability_inventory.md)
2. [Agent Map](../agent-map/README.md)
3. [Agent Map JSON](../agent-map/index.json)
4. [TypeScript Integration Guide](./typescript_integration.md)
5. [TypeScript Provider Integration Guide](./typescript_provider_integration.md)
6. [Python Integration Guide](./python_integration.md)
7. [Python Provider Integration Guide](./python_provider_integration.md)
8. [Python Staging Development](../ops/SDK_Python_Local_Development.md)
9. [TypeScript Consumer E2E Plan](../test/consumer-e2e-plan.md)
10. [TypeScript Provider Onboarding E2E Plan](../test/typescript-provider-onboarding-e2e-plan.md)
11. [Python Consumer Cold-Start E2E Plan](../test/python-consumer-cold-start-e2e-plan.md)
12. [Python Provider Onboarding E2E Plan](../test/python-provider-onboarding-e2e-plan.md)

## 当前结论

SDK 当前有三个明确的公开入口：

1. `SynapseClient`：Agent runtime quickstart。已有 `agt_xxx` 后，直接 discovery/search -> invoke -> receipt。
2. `SynapseAuth`：Owner control plane，用于 wallet auth、credential issuance、key rotation 和 owner finance helper。
3. `SynapseProvider`：通过 `auth.provider()` 获取的 provider publishing facade，用于 provider secret、service registration、lifecycle、health、earnings 和 withdrawal helper。

Provider 仍然是 owner scope 下的供给侧角色。`SynapseProvider` 只是让 provider 接入更容易发现，不引入第二套 provider root 身份。

Owner/provider helper 的返回值必须是命名 SDK 对象。不要新增或记录返回 raw Python `dict` / TypeScript `Record<string, unknown>` 的公开 `SynapseAuth` / `SynapseProvider` 方法；应先新增命名 result model/interface。

Python 旧的 quote-first 方法 `create_quote()`、`create_invocation()`、`invoke_service()` 已经废弃。它们不会再访问旧 endpoint，而是直接提示普通 fixed-price API 改用 discovery/search + `invoke(..., cost_usdc=...)`。

LLM 服务使用 `serviceKind=llm` + `priceModel=token_metered`。Runtime 代码应调用 `invoke_llm()` / `invokeLlm()`，并读取返回里的 `usage` 与 `synapse` 计费元数据。LLM 调用不要传 `cost_usdc` / `costUsdc`；可以传可选的 `max_cost_usdc` / `maxCostUsdc`，也可以交给 Gateway 自动冻结。V1 禁用 streaming。

Consumer 文档应统一呈现两种调用模式：

| 模式 | SDK 方法 | 费用输入 |
|---|---|---|
| Fixed-price API | Python `invoke()` / TypeScript `invoke()` | 最新 discovery price：`cost_usdc` / `costUsdc` |
| Token-metered LLM | Python `invoke_llm()` / TypeScript `invokeLlm()` | 可选上限：`max_cost_usdc` / `maxCostUsdc`；不要发送 `cost_usdc` / `costUsdc` |

## Staging 产品文档

Gateway 的产品化 runbook 以 staging docs 为准：

1. SDK Hub: https://staging.synapse-network.ai/docs/sdk
2. Python SDK: https://staging.synapse-network.ai/docs/sdk/python
3. TypeScript SDK: https://staging.synapse-network.ai/docs/sdk/typescript

Production docs 先预留，等 production DNS、`/health` 和 docs deployment 验证后再作为主链路暴露。

## Agent-first 接入链路

README 顶部优先展示 TTFC 最短路径：

1. Gateway Dashboard 连接钱包。
2. Generate Agent Key。
3. agent runtime 使用 `SynapseClient` 执行 discovery / invoke / receipt。

Programmatic credential issuance 属于 Advanced owner flow：

1. owner wallet 签名登录。
2. gateway 返回 JWT。
3. 读取 balance / credits。
4. owner 签发 agent credential。

如果 owner wallet 还没有余额，优先选择 `price_usdc == 0` 的免费服务做 smoke path。付费服务需要 owner balance、credits 或 credential credit limit 足够覆盖本次调用。

Provider publishing 是另一条 owner-authenticated flow：

1. Owner wallet 通过 `SynapseAuth` 登录。
2. 代码调用 `provider = auth.provider()`。
3. Provider 按需签发 provider secret。
4. Provider 注册或更新 service manifest。
5. Provider 通过同一个 facade 查询 service status、health history、earnings 和 withdrawals。

## 配置真相

默认环境是 public preview/staging：

- `staging`: `https://api-staging.synapse-network.ai`，用于 public preview、测试资产和接入试跑。

生产环境上线后，再把公开示例和测试从 `staging` 统一切到 `prod`。

Python：

- `api_key`: 显式参数优先，其次 `SYNAPSE_AGENT_KEY`，最后是 legacy `SYNAPSE_API_KEY`。
- `gateway_url`: 显式参数优先，其次 `SYNAPSE_GATEWAY`。
- `environment`: 显式参数优先，其次 `SYNAPSE_ENV`，最后 `staging`。
- `AgentWallet.connect()` 不再使用 demo credential fallback；缺少真实 credential 会失败。

TypeScript：

- SDK 构造函数以显式 `credential` / `gatewayUrl` / `environment` 为准。
- 应用层可以读取环境变量后传入 SDK。
- SDK 本身不隐式依赖 Node 环境变量，方便浏览器和 Node 共用。

## 幂等与重试

运行时调用建议固定传：

1. `request_id` / request header，用于串联 gateway 日志。
2. `idempotency_key` / `idempotencyKey`，用于避免重复扣费或重复执行。
3. 普通 fixed-price API 传 `cost_usdc` / `costUsdc`，来自最新 discovery price。若价格变化，gateway 会拒绝本次调用，调用方应重新 discovery。
4. 按 token 计费的 LLM 服务调用 `invoke_llm()` / `invokeLlm()`，可选传 `max_cost_usdc` / `maxCostUsdc`；最终按 Provider 返回的 `usage` 精准扣费。

## 常见故障

### `api_key is required`

没有传 `api_key`，也没有设置 `SYNAPSE_AGENT_KEY`。新用户应先签发 agent credential，再把返回的 token 交给 `SynapseClient`。`SYNAPSE_API_KEY` 仅作为旧 Python 用户的 legacy fallback 保留，新文档和示例统一使用 `SYNAPSE_AGENT_KEY`。

```bash
export SYNAPSE_AGENT_KEY='agt_xxx_your_real_key'
```

### Discovery 返回 0 个结果

通常不是 SDK 坏了，而是当前 gateway 没有 discoverable 服务。

优先检查：

1. provider service 是否 `active`。
2. target 是否健康。
3. discovery `query` / `tags` 是否匹配。
4. provider onboarding 是否已进入 owner `/api/v1/services`。

### `402` 或预算相关异常

SDK 会把 `402` 映射到余额、预算或 credential credit limit 相关异常。此时应检查账户余额、credential budget、daily cap，而不是盲目重试 SDK。

## 最短验证路径

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_client_unit.py -q
export SYNAPSE_AGENT_KEY='agt_xxx_your_real_key'
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query '名人名言'
```

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/typescript
npm run test:unit
```
