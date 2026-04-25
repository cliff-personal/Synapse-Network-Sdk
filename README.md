# Synapse Network SDK

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/TypeScript-available-blue.svg" />
  <img src="https://img.shields.io/badge/Status-Public%20Preview-orange.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

Python and TypeScript SDKs for AI agents and developers building on Synapse Network.

面向 AI Agent 和开发者的 Synapse Network Python / TypeScript SDK。

English appears first. Chinese follows each major section.

英文在前，中文说明紧随其后。

Synapse lets an agent discover services, invoke them through a gateway, and settle the call with an auditable receipt. The fastest integration path is:

Synapse 让 Agent 可以发现服务、通过 gateway 调用服务，并用可审计 receipt 完成结算验证。最快接入路径是：

1. Get an Agent Key (`agt_xxx`) from the Synapse Gateway Dashboard.
2. Create a `SynapseClient`.
3. Search, invoke, and read the receipt.

1. 从 Synapse Gateway Dashboard 获取 Agent Key（`agt_xxx`）。
2. 创建 `SynapseClient`。
3. 搜索服务、调用服务、读取 receipt。

> Public Preview default: SDK examples use `staging`, backed by `https://api-staging.synapse-network.ai`.
> The `prod` preset points to `https://api.synapse-network.ai`, but production should only be used after official DNS and `/health` are live.
>
> Public Preview 默认使用 `staging`，对应 `https://api-staging.synapse-network.ai`。
> `prod` 预设指向 `https://api.synapse-network.ai`，但只有在官方 DNS 和 `/health` 验证通过后才应使用生产环境。

## Gateway Docs

Gateway 文档。

| Surface | Link | Status |
|---|---|---|
| SDK Hub | [staging.synapse-network.ai/docs/sdk](https://staging.synapse-network.ai/docs/sdk) | Public Preview |
| Python SDK | [staging.synapse-network.ai/docs/sdk/python](https://staging.synapse-network.ai/docs/sdk/python) | Public Preview |
| TypeScript SDK | [staging.synapse-network.ai/docs/sdk/typescript](https://staging.synapse-network.ai/docs/sdk/typescript) | Public Preview |
| Production docs | Reserved until production docs are live | Reserved |

## Gateway Environments

Gateway 运行环境。

| Environment | Gateway URL | Intended use |
|---|---|---|
| `staging` | `https://api-staging.synapse-network.ai` | Public preview, test assets, integration trials |
| `local` | `http://127.0.0.1:8000` | Local gateway development |
| `prod` | `https://api.synapse-network.ai` | Production preset, pending official DNS and health verification |

Resolution rules:

解析优先级：

1. Explicit `gateway_url` / `gatewayUrl`
2. Explicit `environment`
3. Python only: `SYNAPSE_GATEWAY`
4. Python only: `SYNAPSE_ENV`
5. Default: `staging`

The SDK never probes DNS and never falls back between environments automatically. This prevents production credentials or funds from being routed to the wrong gateway.

SDK 不会自动探测 DNS，也不会在环境之间自动 fallback。这样可以避免生产凭据或资金被错误路由到其他 gateway。

## Agent Quickstart: Python

Agent 快速接入：Python。

Step 1: get your Agent Key from the Synapse Gateway Dashboard.

步骤 1：从 Synapse Gateway Dashboard 获取 Agent Key。

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

Step 2: let your agent discover and work.

步骤 2：让 Agent 自动发现服务并开始工作。

```bash
pip install synapse-client
export SYNAPSE_ENV=staging
export SYNAPSE_API_KEY=agt_xxx
```

```python
from synapse_client import SynapseClient

client = SynapseClient()

services = client.search("free", limit=10)
service = services[0]

result = client.invoke(
    service.service_id,
    {"prompt": "hello"},
    cost_usdc=float(service.price_usdc),
    idempotency_key="agent-job-001",
)

receipt = client.get_invocation(result.invocation_id)
print(receipt.invocation_id, receipt.status, receipt.charged_usdc)
```

If your wallet has no balance yet, start with services whose `price_usdc` is `0`. Paid services require funded balance, available credits, and a credential budget that allows the call.

如果钱包暂时没有余额，先选择 `price_usdc` 为 `0` 的免费服务。付费服务需要账户余额、可用 credits，以及允许本次调用的 credential budget。

## Agent Quickstart: TypeScript

Agent 快速接入：TypeScript。

Step 1: get your Agent Key from the Synapse Gateway Dashboard.

步骤 1：从 Synapse Gateway Dashboard 获取 Agent Key。

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

Step 2: pass the key to the SDK.

步骤 2：把 key 传给 SDK。

```bash
npm install @synapse-network/sdk
```

```ts
import { SynapseClient } from "@synapse-network/sdk";

const client = new SynapseClient({
  credential: "agt_xxx",
  environment: "staging",
});

const services = await client.search("free", {
  limit: 10,
});
const service = services[0];

const result = await client.invoke(
  service.serviceId ?? service.id!,
  { prompt: "hello" },
  {
    costUsdc: Number(service.pricing?.amount ?? 0),
    idempotencyKey: "agent-job-001",
  }
);

const receipt = await client.getInvocation(result.invocationId);
console.log(receipt.invocationId, receipt.status, receipt.chargedUsdc);
```

TypeScript does not read environment variables by itself. Read them in your app and pass `environment` or `gatewayUrl` explicitly.

TypeScript SDK 不会自动读取环境变量。请在你的应用中读取环境变量，然后显式传入 `environment` 或 `gatewayUrl`。

## Advanced: Programmatic Credential Issuance

高级用法：以代码方式签发凭据。

Use `SynapseAuth` only when an owner/backend service needs to issue credentials or register provider services programmatically. Ordinary agent runtime code should use `SynapseClient` with an existing `agt_xxx` key.

只有当 owner/backend service 需要以代码方式签发凭据或注册 provider service 时，才使用 `SynapseAuth`。普通 Agent 运行时代码应使用已有 `agt_xxx` key 和 `SynapseClient`。

1. Authenticate an owner wallet.
2. Issue an agent credential with spending limits.
3. Hand that credential to an agent runtime.
4. Register provider services when publishing APIs to the marketplace.

1. owner 钱包认证。
2. 签发带预算限制的 agent credential。
3. 把 credential 交给 Agent 运行时。
4. 发布 API 到 marketplace 时注册 provider service。

Python:

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    "0xYOUR_PRIVATE_KEY",
    environment="staging",
)
issued = auth.issue_credential(name="agent-preview", maxCalls=100, creditLimit=5)
print(issued.credential.id, issued.token)
```

TypeScript:

```ts
import { Wallet } from "ethers";
import { SynapseAuth } from "@synapse-network/sdk";

const wallet = new Wallet(process.env.OWNER_PRIVATE_KEY!);
const auth = SynapseAuth.fromWallet(wallet, { environment: "staging" });
const issued = await auth.issueCredential({
  name: "agent-preview",
  maxCalls: 100,
  creditLimit: 5,
});
console.log(issued.credential.id, issued.token);
```

Credential handling and vulnerability reporting live in [SECURITY.md](./SECURITY.md).

凭据处理和漏洞报告请查看 [SECURITY.md](./SECURITY.md)。

## Current API Boundary

当前 API 边界。

Supported today:

当前已支持：

- Consumer discovery/search
- Price-asserted invoke
- Price-mismatch rediscovery helper
- Invocation receipt lookup
- Gateway health and empty-discovery diagnostics
- Owner auth and credential issue/list/update/revoke/rotate/delete/quota/audit logs
- Balance, voucher, usage, finance audit, and risk overview helpers
- Provider secret issue/list/delete
- Provider service register/list/get/status/update/delete/ping/registration guide/health history
- Provider earnings and withdrawal intent/list/capability helpers

Not yet wrapped:

尚未封装：

- Refunds, notifications, community, and event APIs
- On-chain deposit transaction signing helpers

See [docs/sdk/capability_inventory.md](./docs/sdk/capability_inventory.md) for the detailed inventory.

完整能力清单见 [docs/sdk/capability_inventory.md](./docs/sdk/capability_inventory.md)。

Finance and withdrawal helpers are explicit API wrappers only. The SDK will not automatically move funds, sign transactions, or submit high-impact financial actions on behalf of an agent.

Finance 和 withdrawal helper 只是显式 API wrapper。SDK 不会代表 Agent 自动转移资金、签名交易或提交高影响资金操作。

## Development

开发。

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
PYTHONPATH="$PWD" .venv/bin/python -m pytest synapse_client/test/test_client_unit.py synapse_client/test/test_auth_unit.py -q
```

```bash
cd typescript
npm install
npm run test:unit
npm run lint
```

## License

MIT License. See `LICENSE` for more information.

MIT License。更多信息见 `LICENSE`。
