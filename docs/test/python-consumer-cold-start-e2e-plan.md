# Python SDK — Consumer Cold-Start E2E 自动化测试方案

> 目标：验证 Python SDK 能从 **新建钱包** 开始，完整走通  
> `钱包创建 -> 链上充值 -> 网关登录 -> 确认入账 -> 创建 agent -> 服务发现 -> 服务调用 -> 余额减少`

---

## 1. 测试范围

| # | 阶段 | 验证点 |
|---|---|---|
| 1 | 创建钱包 | `Account.create()` 生成全新 EOA |
| 2 | ETH 注入 | Deployer 给新钱包转 0.5 ETH 作为 gas |
| 3 | USDC Mint | Deployer 调 `MockUSDC.mint()` 给新钱包注入 10 USDC |
| 4 | 链上充值 | 新钱包 `approve + deposit` 到 `SynapseCore` |
| 5 | 登录 | `SynapseAuth.from_private_key()` 完成 challenge/sign/verify |
| 6 | JWT 缓存 | 连续 `get_token()` 返回同一 token |
| 7 | 充值登记 | `register_deposit_intent(txHash, amount)` |
| 8 | 充值确认 | `confirm_deposit(intentId, eventKey)` |
| 9 | 余额生效 | `consumerAvailableBalance >= 9.9` |
| 10 | Provider 注册服务 | 通过 provider wallet 注册 mock 服务 |
| 11 | 创建 agent | `issue_credential()` 成功，返回 agent token |
| 12 | 列举 credential | `list_credentials()` 能找到刚创建的 agent |
| 13 | 服务发现 | `client.discover()` 返回服务列表，包含刚注册服务 |
| 14 | 调用 | `client.invoke(serviceId, payload, cost_usdc=...)` 返回 `SUCCEEDED/SETTLED` |
| 15 | Receipt | `client.get_invocation()` 能按 invocation id 取回状态 |
| 16 | 余额扣减 | 调用后余额小于调用前余额 |

---

## 2. 依赖环境

| 组件 | 地址 | 说明 |
|---|---|---|
| Hardhat node | `http://127.0.0.1:8545` | 本地链 |
| Gateway | `http://127.0.0.1:8000` | Synapse gateway |
| Mock Provider | `http://127.0.0.1:9399` | 测试内启动的 HTTP server |

合约配置来自：

1. `/home/alex/Documents/cliff/Synapse-Network/services/user-front/src/contract-config.json`
2. `/home/alex/Documents/cliff/Synapse-Network/services/user-front/src/MockUSDCABI.json`
3. `/home/alex/Documents/cliff/Synapse-Network/services/user-front/src/SynapseCoreABI.json`

---

## 3. 关键角色

| 角色 | 来源 | 作用 |
|---|---|---|
| Deployer | Hardhat #0 | 转 ETH、mint USDC |
| Provider | Hardhat #2 | 注册测试服务 |
| Fresh Consumer | `eth_account.Account.create()` | 本次测试主角 |

---

## 4. 测试文件

1. `python/synapse_client/test/test_auth_unit.py`
2. `python/synapse_client/test/test_client_unit.py`
3. `python/synapse_client/test/test_consumer_e2e.py`

---

## 5. 运行命令

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_auth_unit.py synapse_client/test/test_client_unit.py -q
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_consumer_e2e.py -q -s
```

---

## 6. 验收标准

1. 全部 unit test 通过
2. Python 冷启动 e2e 通过
3. `charged_usdc > 0`
4. `consumer_available_balance` 在调用后下降
5. 测试总时长稳定在本地 30 秒内
