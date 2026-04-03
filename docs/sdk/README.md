# Synapse SDK Docs Hub

本目录现在是 SDK 侧的总入口，覆盖 TypeScript、Python、测试与 bugfix。

## 1. 文档入口

1. [TypeScript Integration Guide](./typescript_integration.md)
2. [Python Integration Guide](./python_integration.md)
3. [Python Local Development](../ops/SDK_Python_Local_Development.md)
4. [TypeScript Consumer E2E Plan](../test/consumer-e2e-plan.md)
5. [Python Consumer Cold-Start E2E Plan](../test/python-consumer-cold-start-e2e-plan.md)
6. [TypeScript Bug Log](../bugfix/typeScript/bugs.md)
7. [Python Bug Log](../bugfix/python/bugs.md)

## 2. 当前结论

### TypeScript SDK

已经满足完整自动化接入，包含新用户冷启动 E2E。

### Python SDK

在这次改造前，不满足 owner onboarding 自动化接入；  
在这次改造后，已经满足：

1. 钱包登录
2. 充值登记
3. Agent credential 创建
4. 服务发现
5. 服务调用
6. receipt 查询
7. 余额验证

## 3. 当前验证结果

这次已经实跑通过：

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_auth_unit.py synapse_client/test/test_client_unit.py -q
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_consumer_e2e.py -q -s
```

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
.venv/bin/python -m build
```

如果 `python -m build` 报模块不存在，先安装：

```bash
.venv/bin/python -m pip install build
```

## 6. 运维关注点

### 6.1 入口配置

SDK 运行时主要受两个配置影响：

1. `SYNAPSE_API_KEY`
2. `gateway_url` 或 `SYNAPSE_GATEWAY` 语义上的网关地址

当前 `SynapseClient` 构造函数会自动读取：

- `SYNAPSE_API_KEY`

但 `gateway_url` 目前仍是显式参数优先，默认值为：

```text
http://127.0.0.1:8000
```

这意味着：

1. 本地联调时不传 `gateway_url` 通常没问题
2. 生产或 staging 场景必须显式传正确地址，不要默认依赖 localhost

### 6.2 幂等与重试

运维上要重点关注两个字段：

1. `request_id`
2. `idempotency_key`

建议：

1. 每次 quote / invoke 都挂稳定 `request_id`，便于串联 gateway 日志
2. 每次业务动作生成稳定 `idempotency_key`，避免重复扣费或重复执行

### 6.3 真实联调失败时先查哪里

如果 SDK 集成 demo 失败，优先按下面顺序排查：

1. Gateway 是否启动
2. API key 是否有效
3. discoverable 服务是否真的健康
4. 引用的 `service_id` 是否来自最新 discovery 结果
5. 凭据预算或余额是否足够

常见命令：

```bash
bash /home/alex/Documents/cliff/Synapse-Network/scripts/local/restart_gateway.sh
```

然后重新跑 SDK demo。

## 7. 常见故障对照表

### 7.1 出现 `ImageMagick import` 输出

原因：你在用 `sh` 执行 Python 文件。

处理：改成运行 SDK 单测、`examples/smoke_test.py`，或者用 Python 导入包，不要执行 `client.py`。

### 7.2 `api_key is required`

原因：没有传 `api_key`，也没有设置 `SYNAPSE_API_KEY`。

处理：

```bash
export SYNAPSE_API_KEY='agt_xxx_your_real_key'
```

### 7.3 discovery 返回 0 个结果

原因通常不是 SDK 坏了，而是后端没有 discoverable 服务。

优先检查：

1. 服务是否 `active`
2. target 是否健康
3. discovery query / tags 是否匹配

### 7.4 `402` 或预算相关异常

SDK 会把 `402` 映射成：

1. `InsufficientFundsError`
2. `BudgetExceededError`

这说明要查账户余额、credential 预算、daily cap，而不是继续重试 SDK。

## 8. 推荐维护原则

1. 不要把 `client.py` 做成 CLI 入口；它的职责是稳定 SDK 模块。
2. live 示例执行统一放在 `examples/`，不要混进单测目录。
3. 单测只 mock HTTP，不依赖真实 gateway。
4. live smoke test 必须是手工 opt-in，避免 CI 误连真实环境。
5. 文档、异常映射、模型字段、测试断言必须一起演进。

## 9. 最短操作路径

如果你只想快速确认 `synapse_client` 当前是否工作，按这个顺序：

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_client_unit.py -q
export SYNAPSE_API_KEY='agt_xxx_your_real_key'
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query '名人名言'
```

第一步验证 SDK 代码本身。

第二步验证 SDK 与本地 Synapse gateway 的真实联调。
