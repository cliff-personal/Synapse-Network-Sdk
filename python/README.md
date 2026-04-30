# sdk-python

`python/` 是 Synapse 的官方 Python SDK 分发与联调目录。

## 文档入口

1. 总入口：`docs/sdk/README.md`
2. Python 接入：`docs/sdk/python_integration.md`
3. Python Provider 接入：`docs/sdk/python_provider_integration.md`
4. TypeScript 接入：`docs/sdk/typescript_integration.md`
5. Staging 开发与验证：`docs/ops/SDK_Python_Staging_Development.md`
6. Python 冷启动 E2E：`docs/test/python-consumer-cold-start-e2e-plan.md`
7. Python Provider Onboarding E2E：`docs/test/python-provider-onboarding-e2e-plan.md`
8. Python bugfix：`docs/bugfix/python/bugs.md`

## 常用命令

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/python
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query "名人名言"
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_auth_unit.py synapse_client/test/test_client_unit.py synapse_client/test/test_consumer_e2e.py synapse_client/test/test_provider_e2e.py -q -s
```

## 说明

本文件现在只保留项目入口信息。  
完整接入、自动化 E2E、bugfix 记录统一维护在根 `docs/`。
