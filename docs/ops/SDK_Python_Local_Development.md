# SDK Python Staging Development

`python/` 是 SynapseNetwork 的官方 Python SDK 分发与联调目录。当前所有公开验证都指向 staging；生产环境上线后再统一切换到 prod。

## 安装

发布包安装：

```bash
pip install synapse-client
```

开发安装：

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Staging Smoke Test

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
export SYNAPSE_ENV=staging
export SYNAPSE_AGENT_KEY="agt_xxxxx..."
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query "quotes"
```

如需输出可复现 curl：

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py --query "quotes" --print-curl
```

如已知 `service_id`：

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/smoke_test.py \
  --service-id svc_quotes_famous_top3 \
  --cost-usdc "0.001"
```

## 环境变量

1. `SYNAPSE_ENV=staging`
2. `SYNAPSE_AGENT_KEY`: Agent credential。`SYNAPSE_API_KEY` 仅作为 legacy Python fallback。

## 相关文档

1. [README.md](../../README.md)
2. [SDK Docs](../sdk/README.md)
