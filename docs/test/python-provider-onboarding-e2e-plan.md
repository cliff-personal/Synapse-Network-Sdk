# Python SDK — Provider Onboarding E2E 自动化测试方案

> 目标：验证 Python SDK 能从 **新钱包 Provider 冷启动** 开始，完整走通  
> `创建钱包 -> 登录 -> 创建 provider credentials -> 注册服务 -> 读取注册状态`

---

## 1. 测试范围

| # | 阶段 | 验证点 |
|---|---|---|
| 1 | 创建钱包 | `Account.create()` 生成全新 Provider EOA |
| 2 | 登录 | `SynapseAuth.from_private_key()` 完成 challenge/sign/verify |
| 3 | JWT 缓存 | `get_token()` 返回稳定 token |
| 4 | 创建 provider secret | `issue_provider_secret()` 成功返回 `secret.id` 与 `secretKey` |
| 5 | 查询 provider secret | `list_provider_secrets()` 能找到刚签发的 secret |
| 6 | 注册服务 | `register_provider_service()` 成功返回 `serviceId` |
| 7 | 查询 owner service list | `list_provider_services()` 包含刚注册服务 |
| 8 | 查询服务状态 | `get_provider_service_status()` 返回 lifecycle + runtime 状态 |

---

## 2. 依赖环境

| 组件 | 地址 | 说明 |
|---|---|---|
| Gateway | `http://127.0.0.1:8000` | Synapse gateway |
| Mock Provider | `http://127.0.0.1:9499` | 测试内启动的 HTTP server |

这个 Provider E2E 不依赖链上充值，因此比 consumer 链更轻、更快。

---

## 3. 关键角色

| 角色 | 来源 | 作用 |
|---|---|---|
| Fresh Provider | `eth_account.Account.create()` | 本次测试主角 |
| Mock Provider Server | test fixture | 对 `/health` 和 invoke 返回 200 |

---

## 4. 测试文件

1. `python/synapse_client/test/test_auth_unit.py`
2. `python/synapse_client/test/test_provider_e2e.py`

---

## 5. 运行命令

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_auth_unit.py -q
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_provider_e2e.py -q -s
```

---

## 6. 验收标准

1. unit test 通过
2. provider onboarding e2e 通过
3. fresh wallet 能拿到 JWT
4. provider secret 创建成功
5. service register 成功返回 `serviceId`
6. `get_provider_service_status()` 能查到刚注册服务的状态
