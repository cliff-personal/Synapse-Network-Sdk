# Synapse Python Provider SDK Integration Guide

## 1. 目标

让 Provider 以最低成本接入 Synapse 控制面，而不是自己手搓：

1. 钱包 challenge / sign / verify
2. provider secret 生命周期
3. service manifest 最小注册 payload
4. 注册后状态查询

当前 Python SDK 的 provider 入口是 `auth.provider()`。它返回 `SynapseProvider` facade，但底层仍然使用 `SynapseAuth` 的 owner wallet / JWT，因为 Provider onboarding 在工程真相里属于 **owner wallet 控制面**。

---

## 2. 当前能力

这次补齐后，Python SDK 的 Provider 面已经支持：

1. `auth.provider()`
2. `provider.issue_secret()`
3. `provider.list_secrets()`
4. `provider.delete_secret()`
5. `provider.get_registration_guide()`
6. `provider.parse_curl_to_service_manifest()`
7. `provider.register_service()`
8. `provider.list_services()`
9. `provider.get_service()`
10. `provider.get_service_status()`
11. `provider.update_service()`
12. `provider.delete_service()`
13. `provider.ping_service()`
14. `provider.get_service_health_history()`
15. `provider.get_earnings_summary()`
16. `provider.get_withdrawal_capability()`
17. `provider.create_withdrawal_intent()`
18. `provider.list_withdrawals()`

---

## 3. 最小接入代码

完整 staging 示例脚本：

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python examples/provider_staging_onboarding.py \
  --provider-private-key "$SYNAPSE_PROVIDER_PRIVATE_KEY" \
  --endpoint-url "https://your-provider.example.com/invoke" \
  --service-name "Weather API" \
  --description "Returns weather data for a city." \
  --price-usdc 0
```

注意：staging gateway 必须能访问 provider endpoint，所以 `--endpoint-url` 应使用公网 HTTPS URL，不能使用 `localhost`。

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    "0xYOUR_PROVIDER_PRIVATE_KEY",
    environment="staging",
)

jwt = auth.get_token()
print(jwt)

provider = auth.provider()

secret = provider.issue_secret(
    name="provider-secret-prod",
    rpm=180,
    creditLimit=25.0,
)
print(secret.secret.id, secret.secret.masked_key)

registered = provider.register_service(
    service_name="SEA Invoice OCR",
    endpoint_url="https://provider.example.com/invoke",
    base_price_usdc="0.008",
    description_for_model="Extract structured invoice fields from invoice images.",
)

print(registered.service_id)

status = provider.get_service_status(registered.service_id)
print(status.lifecycle_status, status.health.overall_status, status.runtime_available)
```

---

## 4. SDK 设计原则

### 4.1 为什么 provider 能力从 `SynapseAuth` 派生

因为当前工程真相是：

1. Provider 不是另一套根账户体系
2. Provider role 绑定在 owner wallet scope
3. 服务注册接口使用 bearer JWT

所以 Provider onboarding 不需要第二套认证 client。`SynapseProvider` 是从 `SynapseAuth` 派生的 provider publishing facade，用来把 provider 工作流从 owner credential 管理中分出来。

### 4.2 最小注册输入

`provider.register_service()` 对外只要求：

1. `service_name`
2. `endpoint_url`
3. `base_price_usdc`
4. `description_for_model`

SDK 自动补：

1. `service_id` / `agentToolName`
2. 最小 input / output schema
3. `gateway_signed` auth
4. `/health` healthCheck
5. `providerProfile.displayName`
6. `payoutAccount` 默认绑定当前 wallet
7. `governance.termsAccepted = true`
8. `governance.riskAcknowledged = true`

这就是“最低成本接入”的核心。

---

## 5. 当前 contract 映射

Provider 工作流文档里常说：

1. `description_for_model`
2. `service_manifest`
3. `provider_profile`
4. `payout_account`

而当前 Gateway 真接口 `POST /api/v1/services` 使用的是：

1. `summary`
2. `invoke`
3. `providerProfile`
4. `payoutAccount`

Python SDK 处理方式：

1. 对外继续用更产品化的 `description_for_model`
2. 内部映射到当前 Gateway contract 的 `summary`
3. 现有 `auth.register_provider_service()` 继续兼容，推荐新代码使用 `provider.register_service()`

---

## 6. 状态读取语义

`provider.get_service_status(service_id)` 返回的是控制面状态，而不是 public discovery SLA 承诺。

当前它组合了：

1. `lifecycleStatus`
2. `runtimeAvailable`
3. `health.overallStatus`

需要讲真话：

1. `status=active` 不等于一定已经对 public discover 可见
2. public discover 还依赖健康检查和搜索索引
3. 因此 provider onboarding 的成功标准，以 owner 自己的 `/api/v1/services` 列表为准

---

## 7. 对应测试

对应测试方案见：

- `docs/test/python-provider-onboarding-e2e-plan.md`

对应 live e2e 代码：

- `python/synapse_client/test/test_provider_e2e.py`
