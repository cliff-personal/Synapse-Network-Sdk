# Synapse SDK Docs Hub

This directory is the SDK-side source of truth for capabilities, integration guides, provider onboarding, and test plans.

本目录是 SDK 侧的真实能力入口，覆盖能力清单、接入指南、provider onboarding 与测试计划。

English appears first. Chinese follows each major section.

英文在前，中文说明紧随其后。

## Docs Index

文档入口。

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

## Current Position

当前结论。

The SDK currently covers two main flows:

SDK 当前覆盖两条主链：

1. Agent runtime quickstart: after receiving an `agt_xxx` key, call discovery/search -> invoke -> receipt.
2. Owner advanced flow: owner auth / credential issuance / provider lifecycle.

1. Agent runtime quickstart：已有 `agt_xxx` 后，直接 discovery/search -> invoke -> receipt。
2. Owner advanced flow：owner auth / credential issue / provider lifecycle。

Python quote-first methods `create_quote()`, `create_invocation()`, and `invoke_service()` are deprecated. They no longer call old endpoints and instead tell users to use discovery/search + `invoke(..., cost_usdc=...)`.

Python 旧的 quote-first 方法 `create_quote()`、`create_invocation()`、`invoke_service()` 已经废弃。它们不会再访问旧 endpoint，而是直接提示改用 discovery/search + `invoke(..., cost_usdc=...)`。

## Staging Docs

Staging 产品文档。

The productized Gateway runbook lives in staging docs:

Gateway 的产品化 runbook 以 staging docs 为准：

1. SDK Hub: https://staging.synapse-network.ai/docs/sdk
2. Python SDK: https://staging.synapse-network.ai/docs/sdk/python
3. TypeScript SDK: https://staging.synapse-network.ai/docs/sdk/typescript

Production docs are reserved until production DNS, `/health`, and docs deployment are verified.

Production docs 先预留，等 production DNS、`/health` 和 docs deployment 验证后再作为主链路暴露。

## Agent-First Onboarding Flow

Agent-first 接入链路。

The top README prioritizes the shortest TTFC path:

README 顶部优先展示 TTFC 最短路径：

1. Connect wallet in Gateway Dashboard.
2. Generate Agent Key.
3. Agent runtime uses `SynapseClient` for discovery / invoke / receipt.

1. Gateway Dashboard 连接钱包。
2. Generate Agent Key。
3. agent runtime 使用 `SynapseClient` 执行 discovery / invoke / receipt。

Programmatic credential issuance is an advanced owner flow:

Programmatic credential issuance 属于 Advanced owner flow：

1. Owner wallet signs in.
2. Gateway returns JWT.
3. Owner reads balance / credits.
4. Owner issues agent credential.

1. owner wallet 签名登录。
2. gateway 返回 JWT。
3. 读取 balance / credits。
4. owner 签发 agent credential。

If the owner wallet has no balance, use services where `price_usdc == 0` as the smoke path. Paid services require owner balance, credits, or credential credit limit.

如果 owner wallet 还没有余额，优先选择 `price_usdc == 0` 的免费服务做 smoke path。付费服务需要 owner balance、credits 或 credential credit limit 足够覆盖本次调用。

## Configuration Truth

配置真相。

Default environment is public preview/staging:

默认环境是 public preview/staging：

- `local`: `http://127.0.0.1:8000`
- `staging`: `https://api-staging.synapse-network.ai`
- `prod`: `https://api.synapse-network.ai`, only for real funds after official production DNS and `/health` verification.

- `local`: `http://127.0.0.1:8000`，用于本地 gateway 开发。
- `staging`: `https://api-staging.synapse-network.ai`，用于 public preview、测试资产和接入试跑。
- `prod`: `https://api.synapse-network.ai`，需等官方 production DNS 和 `/health` 验证后再用于真实资金流。

Python:

- `api_key`: explicit parameter first, then `SYNAPSE_API_KEY`.
- `gateway_url`: explicit parameter first, then `SYNAPSE_GATEWAY`.
- `environment`: explicit parameter first, then `SYNAPSE_ENV`, then `staging`.
- `AgentWallet.connect()` no longer uses demo credential fallback; missing real credentials fail.

Python：

- `api_key`: 显式参数优先，其次 `SYNAPSE_API_KEY`。
- `gateway_url`: 显式参数优先，其次 `SYNAPSE_GATEWAY`。
- `environment`: 显式参数优先，其次 `SYNAPSE_ENV`，最后 `staging`。
- `AgentWallet.connect()` 不再使用 demo credential fallback；缺少真实 credential 会失败。

TypeScript:

- SDK constructors use explicit `credential` / `gatewayUrl` / `environment`.
- Applications may read env vars and pass values into the SDK.
- The SDK does not implicitly depend on Node env, so browser and Node runtimes can share the package.

TypeScript：

- SDK 构造函数以显式 `credential` / `gatewayUrl` / `environment` 为准。
- 应用层可以读取环境变量后传入 SDK。
- SDK 本身不隐式依赖 Node 环境变量，方便浏览器和 Node 共用。

## Idempotency and Retry

幂等与重试。

Runtime calls should include:

运行时调用建议固定传：

1. `request_id` / request header for gateway log correlation.
2. `idempotency_key` / `idempotencyKey` to avoid duplicate charges or duplicate execution.
3. `cost_usdc` / `costUsdc` from latest discovery price. If price changes, the gateway rejects the call and the caller should rediscover.

1. `request_id` / request header，用于串联 gateway 日志。
2. `idempotency_key` / `idempotencyKey`，用于避免重复扣费或重复执行。
3. `cost_usdc` / `costUsdc`，来自最新 discovery price。若价格变化，gateway 会拒绝本次调用，调用方应重新 discovery。

## Common Failures

常见故障。

### `api_key is required`

No `api_key` was passed and `SYNAPSE_API_KEY` is not set. New users should issue an agent credential first, then pass the returned token to `SynapseClient`.

没有传 `api_key`，也没有设置 `SYNAPSE_API_KEY`。新用户应先签发 agent credential，再把返回的 token 交给 `SynapseClient`。

```bash
export SYNAPSE_API_KEY='agt_xxx_your_real_key'
```

### Discovery returns 0 results

Discovery 返回 0 个结果。

Usually this means the current gateway has no discoverable services rather than an SDK failure.

通常不是 SDK 坏了，而是当前 gateway 没有 discoverable 服务。

Check:

优先检查：

1. Provider service is `active`.
2. Target service is healthy.
3. Discovery `query` / `tags` match the service.
4. Provider onboarding appears in owner `/api/v1/services`.

1. provider service 是否 `active`。
2. target 是否健康。
3. discovery `query` / `tags` 是否匹配。
4. provider onboarding 是否已进入 owner `/api/v1/services`。

### `402` or budget errors

`402` 或预算相关异常。

The SDK maps `402` to balance, budget, or credential credit limit errors. Check account balance, credential budget, and daily cap rather than blindly retrying.

SDK 会把 `402` 映射到余额、预算或 credential credit limit 相关异常。此时应检查账户余额、credential budget、daily cap，而不是盲目重试 SDK。

## Shortest Verification Path

最短验证路径。

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
