# Python SDK Bug Log

## BUG-PY-001 — 缺少 owner wallet auth / deposit / credential 管理入口

**Status:** FIXED  
**Severity:** blocking  
**Files:** `python/synapse_client/auth.py`, `python/synapse_client/models.py`, `python/synapse_client/__init__.py`

### Symptom

Python SDK 只有 `X-Credential` runtime client，没有：

1. owner wallet challenge / sign / verify
2. 余额读取
3. deposit intent / confirm
4. credential issue / list

### Root Cause

Python SDK 只实现了 agent runtime 面，没有实现 owner onboarding 面；因此无法像 TypeScript 一样从“新钱包冷启动”开始自动化接入。

### Fix

新增 `SynapseAuth`，补齐：

1. `from_private_key()`
2. `get_token()`
3. `get_balance()`
4. `register_deposit_intent()`
5. `confirm_deposit()`
6. `issue_credential()`
7. `list_credentials()`

---

## BUG-PY-002 — `eth-account` 新版 signed tx 兼容问题

**Status:** FIXED  
**Severity:** blocking e2e  
**File:** `python/synapse_client/test/test_consumer_e2e.py`

### Symptom

`SignedTransaction` 在新版本只暴露 `raw_transaction`，旧字段 `rawTransaction` 不存在，导致链上转账前直接抛异常。

### Fix

增加兼容 helper，优先读取 `raw_transaction`，再回退 `rawTransaction`。

---

## BUG-PY-003 — deposit tx hash 缺少 `0x` 前缀

**Status:** FIXED  
**Severity:** blocking e2e  
**File:** `python/synapse_client/test/test_consumer_e2e.py`

### Symptom

网关 `DepositIntentRequest` 校验失败：

```text
String should have at least 66 characters
```

### Root Cause

`web3` receipt 返回的交易哈希字符串在本测试 helper 里被直接 `.hex()`，丢掉了 `0x` 前缀。

### Fix

新增 `_normalized_tx_hash()`，统一标准化为带 `0x` 的 32-byte hex string。

---

## BUG-PY-004 — `AgentCredential.createdAt` 类型假设错误

**Status:** FIXED  
**Severity:** blocking e2e  
**File:** `python/synapse_client/models.py`

### Symptom

Pydantic 校验失败：

```text
createdAt
Input should be a valid integer
```

### Root Cause

Python SDK 把 `createdAt` 假定成 int，但网关真实返回的是 datetime string。

### Fix

把 `AgentCredential.created_at` 调整为 `Optional[int | str]`，对齐真实网关 contract。

---

## BUG-PY-005 — Python SDK 缺少 Provider onboarding 能力

**Status:** FIXED  
**Severity:** blocking provider integration  
**Files:** `python/synapse_client/auth.py`, `python/synapse_client/models.py`, `python/synapse_client/test/test_provider_e2e.py`

### Symptom

Python SDK 只能做 consumer onboarding 和 agent runtime 调用，不能：

1. 创建 provider secret
2. 通过 SDK 注册 provider service
3. 查询刚注册服务的状态

这意味着用户虽然能“消费服务”，却不能“把自己的服务挂进平台”。

### Root Cause

SDK 把 owner wallet auth 只当成 consumer control plane 用，没有继续封装 provider control plane：

1. `/api/v1/secrets/provider/issue`
2. `/api/v1/secrets/provider/list`
3. `/api/v1/services`
4. `/api/v1/services` owner list

### Fix

在 `SynapseAuth` 上新增：

1. `issue_provider_secret()`
2. `list_provider_secrets()`
3. `register_provider_service()`
4. `list_provider_services()`
5. `get_provider_service()`
6. `get_provider_service_status()`

并补充：

1. typed provider models
2. provider integration docs
3. provider onboarding e2e
