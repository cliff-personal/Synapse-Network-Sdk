# Synapse Python SDK Integration Guide

## 当前状态

Python SDK 覆盖当前 gateway 的 consumer/provider canonical main flow。

Consumer runtime 主链固定为：

1. owner 钱包登录
2. 创建 agent credential
3. discovery/search
4. `invoke(service_id, payload, cost_usdc=...)`
5. receipt 查询

旧的 quote-first 方法 `create_quote()`、`create_invocation()`、`invoke_service()` 已废弃，不再访问旧 endpoint。调用这些方法会直接提示改用 discovery/search + price-asserted invoke。

Staging 产品化 runbook:

1. https://staging.synapse-network.ai/docs/sdk/python
2. SDK Hub: https://staging.synapse-network.ai/docs/sdk

Production docs 先预留，等 production DNS、`/health` 和 docs deployment 验证后再作为主链路暴露。

## 安装

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 配置

`SynapseClient` 读取顺序：

1. `api_key` 显式参数
2. `SYNAPSE_API_KEY`

`gateway_url` 读取顺序：

1. `gateway_url` 显式参数
2. `SYNAPSE_GATEWAY`

`environment` 读取顺序：

1. `environment` 显式参数
2. `SYNAPSE_ENV`
3. `staging`

环境 preset：

1. `local`: `http://127.0.0.1:8000`
2. `staging`: `https://api-staging.synapse-network.ai`
3. `prod`: `https://api.synapse-network.ai`，需等官方 production DNS 和 `/health` 验证后再用于真实资金流

`AgentWallet.connect()` 不再使用 `demo_key` fallback。没有真实 credential 时会失败。

## Agent-first 接入链路

Fresh setup 不应从 `SYNAPSE_API_KEY` 开始。`SYNAPSE_API_KEY` 是 owner wallet 签发 agent credential 之后得到的 runtime token。

固定顺序：

1. owner wallet 登录并拿到 JWT
2. 读取 balance / credits
3. 签发 agent credential
4. agent runtime 用 credential 搜索服务、调用服务、读取 receipt

如果 owner wallet 还没有余额，可以先选择 `price_usdc == 0` 的免费服务做 smoke path；`price_usdc > 0` 的服务需要先有可用余额、credits 或足够的 credential credit limit。

## Owner 钱包登录

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    "0xYOUR_PRIVATE_KEY",
    environment="staging",
)

jwt = auth.get_token()
print(jwt)
```

## 余额、充值与 Credential

```python
balance = auth.get_balance()
print(balance.consumer_available_balance)

intent = auth.register_deposit_intent(tx_hash, 10)
intent_id = intent.intent.resolved_id
event_key = intent.intent.resolved_event_key or tx_hash
auth.confirm_deposit(intent_id, event_key)

issued = auth.issue_credential(
    name="consumer-agent-01",
    maxCalls=100,
    creditLimit=5.0,
    rpm=60,
)

print(issued.credential.id, issued.token)
```

## Consumer Runtime 调用

```python
from synapse_client import SynapseClient

client = SynapseClient(
    api_key=issued.token,
    environment="staging",
)

services = client.search("market data", limit=20, tags=["finance"])
service = services[0]

result = client.invoke(
    service.service_id,
    {"prompt": "hello"},
    cost_usdc=float(service.price_usdc),
    idempotency_key="job-001",
    poll_timeout_sec=60,
)

print(result.invocation_id, result.status, result.charged_usdc)
```

如果你已经缓存了稳定 `service_id`，仍然建议先读取或保存 discovery 返回的最新价格，再传给 `cost_usdc`。gateway 会用该价格断言保护调用方，避免服务价格变化后静默扣费。

## 当前 Consumer API

主推方法：

1. `search_services()`
2. `discover_services()`
3. `discover()`
4. `search()`
5. `invoke()`
6. `get_invocation()`
7. `get_invocation_receipt()`

已废弃兼容方法：

1. `create_quote()`
2. `create_invocation()`
3. `invoke_service()`
4. `quote()`

## Provider 侧接入

Provider onboarding 已拆成独立文档：

1. `docs/sdk/python_provider_integration.md`
2. `docs/test/python-provider-onboarding-e2e-plan.md`

Python SDK 当前支持：

1. provider secret 创建与列举
2. provider 服务注册
3. provider 服务状态查询

Provider onboarding 成功标准以 owner `/api/v1/services` 列表为准，不以 public discovery 为准。

## 自动化验收

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_auth_unit.py synapse_client/test/test_client_unit.py -q
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_consumer_e2e.py -q -s
```
