# SDK Agent Map

- Status: canonical
- Code paths: `llms.txt`, `AGENTS.md`, `README.md`, `SECURITY.md`, `docs/`, `python/synapse_client/`, `typescript/src/`, `scripts/ci/`
- Verified with: `bash scripts/ci/pr_checks.sh`
- Last verified against code: 2026-04-25

This directory is the task-to-file index for AI agents working in `Synapse-Network-Sdk`.

本目录是 AI Agent 在 `Synapse-Network-Sdk` 中工作的任务到文件索引。

README language layout:

- English default: `README.md`
- Simplified Chinese: `README.zh-CN.md`
- SDK docs English hub: `docs/sdk/README.md`
- SDK docs Simplified Chinese hub: `docs/sdk/README.zh-CN.md`
- Do not interleave English and Chinese in the same README body.

README 语言结构：

- 英文默认页：`README.md`
- 简体中文页：`README.zh-CN.md`
- SDK docs 英文页：`docs/sdk/README.md`
- SDK docs 简体中文页：`docs/sdk/README.zh-CN.md`
- 不要在同一个 README 正文中交替混排中英文。

Use it before broad repository search. It keeps SDK work routed to the right Python, TypeScript, docs, and CI surfaces without forcing agents to rediscover the repo every turn.

在大范围搜索仓库之前先使用它。它把 SDK 工作路由到正确的 Python、TypeScript、docs 和 CI 区域，避免 Agent 每一轮都重新发现仓库结构。

## Files

文件。

1. [index.json](./index.json) - machine-readable domain map for agents and workflow tools.
2. This README - human-readable operating rules and maintenance notes.

1. [index.json](./index.json) - 面向 Agent 和 workflow tool 的机器可读 domain map。
2. 本 README - 面向人类可读的操作规则和维护说明。

## How Agents Should Use This Map

Agent 如何使用本索引。

1. Read root `llms.txt`.
2. Read root `AGENTS.md`.
3. Pick the closest domain in [index.json](./index.json).
4. Open the domain `primary_files` first.
5. Run the listed validation commands for the domain.

1. 读取根目录 `llms.txt`。
2. 读取根目录 `AGENTS.md`。
3. 在 [index.json](./index.json) 中选择最接近的 domain。
4. 优先打开该 domain 的 `primary_files`。
5. 运行该 domain 列出的验证命令。

## Domain Summary

Domain 摘要。

| Domain | Use when the task mentions |
| --- | --- |
| `sdk_runtime_client` | discovery, invoke, receipt, usage, runtime errors |
| `sdk_owner_auth` | wallet auth, credential issue/list/status/quota, owner control plane |
| `sdk_provider_lifecycle` | provider facade, provider secrets, service registration, service lifecycle, provider health |
| `sdk_environment_config` | staging defaults, future prod switch, gateway URL resolution, public preview defaults |
| `sdk_public_docs` | README, integration guides, capability inventory, examples |
| `sdk_ci_quality_gates` | GitHub Actions, shell CI scripts, coverage gates |
| `sdk_examples_and_e2e` | examples, smoke tests, onboarding e2e plans |

## Update Rules

更新规则。

Update [index.json](./index.json) in the same change when:

1. A canonical SDK implementation file moves.
2. A public method is added, removed, renamed, or deprecated.
3. A validation command changes.
4. A gateway endpoint contract changes.
5. The public preview environment or staging/prod guidance changes.
6. Public SDK examples change credential names, money handling, or invocation mode guidance.

Do not put secrets, real tokens, private deployment URLs, or one-off incident notes in this map.

不要把 secret、真实 token、私有部署 URL 或一次性 incident 记录写进本索引。

## Brand Constraint

品牌约束。

Product name is SynapseNetwork. Do not rename the product to old agent-payment brand labels.

产品名是 SynapseNetwork。不要把产品命名为旧的 agent-payment 品牌词。

Describe the product as a platform where agents call APIs and make small USDC payments through blockchain-backed settlement.

产品描述应表达：Agent 通过平台调用 API，并通过区块链支持的 USDC 结算完成小额付款。

## Public Preview Constraint

公开预览约束。

Public SDK docs should target staging on Arbitrum Sepolia with MockUSDC test assets until production docs are live. Do not present private local gateway setup as the public developer onboarding path.

公开 SDK 文档在 production docs 上线前应指向 staging、Arbitrum Sepolia 和 MockUSDC 测试资产。不要把私有本地 gateway 设置作为公开开发者接入路径。

## Validation

验证。

Run:

```bash
bash scripts/ci/pr_checks.sh
node -e "JSON.parse(require('fs').readFileSync('docs/agent-map/index.json', 'utf8'))"
```
