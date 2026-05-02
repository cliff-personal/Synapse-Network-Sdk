# Synapse Python SDK Integration Guide

## 当前状态

Python SDK 覆盖当前 gateway 的 consumer/provider canonical main flow。

Consumer runtime 主链固定为：

1. owner 钱包登录
2. 创建 agent credential
3. discovery/search
4. fixed API: `invoke(service_id, payload, cost_usdc=...)`
5. LLM service: `invoke_llm(service_id, payload, max_cost_usdc=...)`
6. receipt 查询

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
2. `SYNAPSE_AGENT_KEY`
3. legacy fallback: `SYNAPSE_API_KEY`

`gateway_url` 读取顺序：

1. `gateway_url` 显式参数
2. `SYNAPSE_GATEWAY`

`environment` 读取顺序：

1. `environment` 显式参数
2. `SYNAPSE_ENV`
3. `staging`

环境 preset：

1. `staging`: `https://api-staging.synapse-network.ai`

当前 staging 使用 Arbitrum Sepolia 测试网和 MockUSDC 测试资产。MockUSDC 只用于接入验证，不是生产 USDC。

生产环境上线后，公开示例和测试再统一切换到 `prod`。

`AgentWallet.connect()` 不再使用 `demo_key` fallback。没有真实 credential 时会失败。

## Agent-first 接入链路

Fresh setup 不应从硬编码 credential 开始。`SYNAPSE_AGENT_KEY` 是 owner wallet 签发 agent credential 之后得到的 runtime token。`SYNAPSE_API_KEY` 只作为 legacy alias 保留。

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
    cost_usdc=str(service.price_usdc),
    idempotency_key="job-001",
    poll_timeout_sec=60,
)

print(result.invocation_id, result.status, result.charged_usdc)
```

如果你已经缓存了稳定 `service_id`，仍然建议先读取或保存 discovery 返回的最新价格，再传给 `cost_usdc`。gateway 会用该价格断言保护调用方，避免服务价格变化后静默扣费。

## LLM token-metered invoke

按 token 计费的 LLM 服务使用 `serviceKind=llm` 和
`priceModel=token_metered`。SDK helper 不发送 `cost_usdc`；Gateway 使用可选
`max_cost_usdc` 作为上限，或自动根据 prompt 字符数与 `max_tokens` 冻结额度，
最后只按 Provider 返回的 final `usage` 扣费。

```python
result = client.invoke_llm(
    "svc_deepseek_chat",
    {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Summarize this document."}],
        "max_tokens": 512,
        # "stream": True 会在 Synapse V1 被拒绝
    },
    max_cost_usdc="0.010000",  # optional
    idempotency_key="llm-job-001",
)

print(result.usage.input_tokens, result.usage.output_tokens)
print(result.synapse.charged_usdc, result.synapse.released_usdc)
```

超时、连接断开、SSE 响应或缺少 final `usage` 时完整释放冻结金额，不扣费。V1
绝不使用预估 hold 作为最终扣费依据。

## Python Examples

示例脚本位于 `python/examples`：

1. `free_service_smoke.py`：优先调用第一方 `svc_synapse_echo`，找不到时搜索免费 fixed-price API service、invoke、读取 receipt。
2. `llm_smoke.py`：调用 token-metered LLM，不发送 fixed-price cost。
3. `e2e.py`：完整真实 Gateway 验证并输出 JSON lines。
4. `provider_staging_onboarding.py`：使用 `SynapseAuth` + `auth.provider()` 在 staging 注册 provider service。
5. `consumer_call_provider.py`：使用已有 `SYNAPSE_AGENT_KEY=agt_xxx` 调用 provider service。
6. `consumer_wallet_to_invoke.py`：创建新的 staging wallet，签发 credential，再调用免费服务。

示例命令：

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python

PYTHONPATH="$PWD" .venv/bin/python examples/provider_staging_onboarding.py \
  --provider-private-key "$SYNAPSE_PROVIDER_PRIVATE_KEY" \
  --endpoint-url "https://your-provider.example.com/invoke" \
  --service-name "Weather API" \
  --description "Returns weather data for a city." \
  --price-usdc 0

export SYNAPSE_AGENT_KEY=agt_xxx
PYTHONPATH="$PWD" .venv/bin/python examples/free_service_smoke.py
PYTHONPATH="$PWD" .venv/bin/python examples/llm_smoke.py
PYTHONPATH="$PWD" .venv/bin/python examples/e2e.py

PYTHONPATH="$PWD" .venv/bin/python examples/consumer_call_provider.py \
  --service-id "weather_api" \
  --payload-json '{"prompt":"hello"}'

PYTHONPATH="$PWD" .venv/bin/python examples/consumer_wallet_to_invoke.py \
  --query "free"
```

## 当前 Consumer API

主推方法：

1. `search_services()`
2. `discover_services()`
3. `discover()`
4. `search()`
5. `invoke()`
6. `invoke_llm()`
7. `get_invocation()`
8. `get_invocation_receipt()`

已废弃兼容方法：

1. `create_quote()`
2. `create_invocation()`
3. `invoke_service()`
4. `quote()`

## Provider 侧接入

Provider onboarding 已拆成独立文档：

1. `docs/sdk/python_provider_integration.md`
2. `docs/test/python-provider-onboarding-e2e-plan.md`

Python SDK 当前通过 `auth.provider()` / `SynapseProvider` 支持：

1. provider secret 创建、列举、删除
2. provider registration guide 与 curl manifest 解析
3. provider 服务注册、列举、读取、更新、删除
4. provider 服务 ping、状态查询、health history
5. provider earnings 与 withdrawals helper

Owner/provider helper 返回命名 `SDKModel` 对象；例如 usage logs 返回 `UsageLogList`，registration guide 返回 `ProviderRegistrationGuide`，withdrawal intent 返回 `ProviderWithdrawalIntentResult`。公开 API 不返回 raw `dict`。

Provider onboarding 成功标准以 owner `/api/v1/services` 列表为准，不以 public discovery 为准。

## 自动化验收

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m py_compile examples/*.py
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_auth_unit.py synapse_client/test/test_client_unit.py -q
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_consumer_e2e.py -q -s
```
