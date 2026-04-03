# Synapse Python SDK Integration Guide

## 1. 当前状态

Python SDK 现在已经满足 **自动化接入** 的完整主链要求。

这次补齐后的能力：

1. Owner 钱包 challenge / sign / verify 登录
2. JWT 缓存
3. 余额读取
4. 充值登记与确认
5. Agent credential 颁发与列举
6. Discover / Quote / Invoke / Receipt
7. 新钱包冷启动 E2E
8. API 风格向 TypeScript 对齐

核心入口：

1. `python/synapse_client/auth.py`
2. `python/synapse_client/client.py`
3. `python/synapse_client/models.py`
4. `python/synapse_client/test/test_consumer_e2e.py`

## 2. 安装

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 3. 最短接入链路

### 3.1 Owner 钱包登录

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    "0xYOUR_PRIVATE_KEY",
    gateway_url="http://127.0.0.1:8000",
)

jwt = auth.get_token()
print(jwt)
```

### 3.2 读取余额

```python
balance = auth.get_balance()
print(balance.consumer_available_balance)
```

### 3.3 链上充值后登记到网关

```python
intent = auth.register_deposit_intent(tx_hash, 10)
intent_id = intent.intent.resolved_id
event_key = intent.intent.resolved_event_key or tx_hash

auth.confirm_deposit(intent_id, event_key)
```

### 3.4 颁发 Agent Credential

```python
issued = auth.issue_credential(
    name="consumer-agent-01",
    maxCalls=100,
    creditLimit=5.0,
    rpm=60,
)

print(issued.credential.id, issued.token)
```

### 3.5 Consumer Runtime 调用

```python
from synapse_client import SynapseClient

client = SynapseClient(
    api_key=issued.token,
    gateway_url="http://127.0.0.1:8000",
)

services = client.discover(limit=20)
service_id = services[0].service_id

quote = client.quote(service_id)
invocation = client.invoke(
    service_id,
    {"prompt": "hello"},
    idempotency_key="job-001",
    poll_timeout_sec=60,
)

receipt = client.get_invocation(invocation.invocation_id)
print(quote.quote_id, invocation.status, receipt.status)
```

## 4. TypeScript 对齐点

Python SDK 新增了下面这组 TS 风格 alias，减少双语言接入心智切换：

1. `discover()`
2. `search()`
3. `quote()`
4. `invoke()`
5. `get_invocation()`

底层兼容旧接口，下面这些名字依然可用：

1. `discover_services()`
2. `search_services()`
3. `create_quote()`
4. `invoke_service()`
5. `get_invocation_receipt()`

## 5. 自动化验收

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_auth_unit.py synapse_client/test/test_client_unit.py -q
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_consumer_e2e.py -q -s
```

## 6. 结论

和 TypeScript SDK 对比，Python SDK 在这次改造前 **不满足** 从 owner 钱包登录开始的自动化接入；改造后，已经满足：

1. 创建钱包
2. 登录
3. 充值
4. 创建 agent credential
5. 服务发现
6. 服务调用
7. receipt 查询
8. 余额验证

## 7. Provider 侧接入

Provider onboarding 已经拆成独立文档，见：

- `docs/sdk/python_provider_integration.md`
- `docs/test/python-provider-onboarding-e2e-plan.md`

现在 Python SDK 也支持：

1. provider secret 创建与列举
2. provider 服务注册
3. provider 服务状态查询
