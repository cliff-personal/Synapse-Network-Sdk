# Synapse SDK Docs Hub

本目录是 SDK 侧的真实能力入口，覆盖 Python、TypeScript、consumer runtime、provider onboarding 与测试计划。

## 文档入口

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

## 当前结论

SDK 当前覆盖两条主链：

1. Agent runtime quickstart：已有 `agt_xxx` 后，直接 discovery/search -> invoke -> receipt。
2. Owner advanced flow：owner auth / credential issue / provider lifecycle。

Python 旧的 quote-first 方法 `create_quote()`、`create_invocation()`、`invoke_service()` 已经废弃。它们不会再访问旧 endpoint，而是直接提示改用 discovery/search + `invoke(..., cost_usdc=...)`。

## Staging Docs

Gateway 的产品化 runbook 以 staging docs 为准：

1. SDK Hub: https://staging.synapse-network.ai/docs/sdk
2. Python SDK: https://staging.synapse-network.ai/docs/sdk/python
3. TypeScript SDK: https://staging.synapse-network.ai/docs/sdk/typescript

Production docs 先预留，等 production DNS、`/health` 和 docs deployment 验证后再作为主链路暴露。

## Agent-first 接入链路

README 顶部优先展示 TTFC 最短路径：

1. Gateway Dashboard 连接钱包
2. Generate Agent Key
3. agent runtime 使用 `SynapseClient` 执行 discovery / invoke / receipt

Programmatic credential issuance 属于 Advanced owner flow：

1. owner wallet 签名登录
2. gateway 返回 JWT
3. 读取 balance / credits
4. owner 签发 agent credential

如果 owner wallet 还没有余额，优先选择 `price_usdc == 0` 的免费服务做 smoke path。付费服务需要 owner balance、credits 或 credential credit limit 足够覆盖本次调用。

## 配置真相

默认环境是 public preview/staging：

- `local`: `http://127.0.0.1:8000`
- `staging`: `https://api-staging.synapse-network.ai`
- `prod`: `https://api.synapse-network.ai`，需等官方 production DNS 和 `/health` 验证后再用于真实资金流

Python:

- `api_key`: 显式参数优先，其次 `SYNAPSE_API_KEY`。
- `gateway_url`: 显式参数优先，其次 `SYNAPSE_GATEWAY`。
- `environment`: 显式参数优先，其次 `SYNAPSE_ENV`，最后 `staging`。
- `AgentWallet.connect()` 不再使用 demo credential fallback；缺少真实 credential 会失败。

TypeScript:

- SDK 构造函数以显式 `credential` / `gatewayUrl` / `environment` 为准。
- 应用层可以读取环境变量后传入 SDK，但 SDK 本身不隐式读取 Node env。
- SDK 本身不隐式依赖 Node 环境变量，方便浏览器和 Node 共用。

## 幂等与重试

运行时调用建议固定传：

1. `request_id` / request header，用于串联 gateway 日志。
2. `idempotency_key` / `idempotencyKey`，用于避免重复扣费或重复执行。
3. `cost_usdc` / `costUsdc`，来自最新 discovery price。若价格变化，gateway 会拒绝本次调用，调用方应重新 discovery。

## 常见故障

### `api_key is required`

没有传 `api_key`，也没有设置 `SYNAPSE_API_KEY`。新用户应先通过 `SynapseAuth` 签发 agent credential，再把返回的 token 交给 `SynapseClient`。

```bash
export SYNAPSE_API_KEY='agt_xxx_your_real_key'
```

### discovery 返回 0 个结果

通常不是 SDK 坏了，而是当前 gateway 没有 discoverable 服务。

优先检查：

1. provider service 是否 `active`
2. target 是否健康
3. discovery `query` / `tags` 是否匹配
4. provider onboarding 是否已进入 owner `/api/v1/services`

### `402` 或预算相关异常

SDK 会把 `402` 映射到余额、预算或 credential credit limit 相关异常。此时应检查账户余额、credential budget、daily cap，而不是盲目重试 SDK。

## 最短验证路径

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_client_unit.py -q
export SYNAPSE_API_KEY='agt_xxx_your_real_key'
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query '名人名言'
```

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/typescript
npm run test:unit
```
