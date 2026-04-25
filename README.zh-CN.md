<p align="center">
  <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

# SynapseNetwork SDK

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/TypeScript-available-blue.svg" />
  <img src="https://img.shields.io/badge/Status-Public%20Preview-orange.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

面向 AI Agent 和开发者的 SynapseNetwork Python / TypeScript SDK。

SynapseNetwork 让 Agent 可以发现服务、通过 gateway 调用服务，并用可审计 receipt 完成结算验证。最快接入路径是：

1. 从 Synapse Gateway Dashboard 获取 Agent Key（`agt_xxx`）。
2. 创建 `SynapseClient`。
3. 搜索服务、调用服务、读取 receipt。

> Public Preview 默认使用 `staging`，对应 `https://api-staging.synapse-network.ai`。
> `prod` 预设指向 `https://api.synapse-network.ai`，但只有在官方 DNS 和 `/health` 验证通过后才应使用生产环境。

## Gateway 文档

| 页面 | 链接 | 状态 |
|---|---|---|
| SDK Hub | [staging.synapse-network.ai/docs/sdk](https://staging.synapse-network.ai/docs/sdk) | Public Preview |
| Python SDK | [staging.synapse-network.ai/docs/sdk/python](https://staging.synapse-network.ai/docs/sdk/python) | Public Preview |
| TypeScript SDK | [staging.synapse-network.ai/docs/sdk/typescript](https://staging.synapse-network.ai/docs/sdk/typescript) | Public Preview |
| 生产文档 | 生产文档上线前预留 | Reserved |

## Gateway 运行环境

| 环境 | Gateway URL | 用途 |
|---|---|---|
| `staging` | `https://api-staging.synapse-network.ai` | Public preview、测试资产和接入试跑 |
| `local` | `http://127.0.0.1:8000` | 本地 gateway 开发 |
| `prod` | `https://api.synapse-network.ai` | 生产预设，等待官方 DNS 和 health 验证 |

解析优先级：

1. 显式 `gateway_url` / `gatewayUrl`
2. 显式 `environment`
3. 仅 Python：`SYNAPSE_GATEWAY`
4. 仅 Python：`SYNAPSE_ENV`
5. 默认：`staging`

SDK 不会自动探测 DNS，也不会在环境之间自动 fallback。这样可以避免生产凭据或资金被错误路由到其他 gateway。

## 选择你的 SDK 入口

| 目标 | 使用 | 凭据 |
|---|---|---|
| 让 Agent 调用服务 | `SynapseClient` | Agent Key（`agt_xxx`） |
| 签发、轮换、撤销 Agent Key | `SynapseAuth` | Owner wallet / JWT |
| 发布和管理 Provider API | `SynapseProvider`，通过 `auth.provider()` 获取 | Owner wallet / JWT |

Provider 是 owner scope 下的供给侧角色，不是第二套根账户体系。普通 Agent runtime 代码保持使用 `SynapseClient`；只有注册或运营 SynapseNetwork 服务时才使用 `SynapseProvider`。

## Agent 快速接入：Python

步骤 1：从 Synapse Gateway Dashboard 获取 Agent Key。

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

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

如果钱包暂时没有余额，先选择 `price_usdc` 为 `0` 的免费服务。付费服务需要账户余额、可用 credits，以及允许本次调用的 credential budget。

## Agent 快速接入：TypeScript

步骤 1：从 Synapse Gateway Dashboard 获取 Agent Key。

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

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

TypeScript SDK 不会自动读取环境变量。请在你的应用中读取环境变量，然后显式传入 `environment` 或 `gatewayUrl`。

## 高级用法：以代码方式签发凭据

只有当 owner/backend service 需要以代码方式签发凭据或注册 provider service 时，才使用 `SynapseAuth`。普通 Agent 运行时代码应使用已有 `agt_xxx` key 和 `SynapseClient`。

1. owner 钱包认证。
2. 签发带预算限制的 agent credential。
3. 把 credential 交给 Agent 运行时。
4. 发布 API 到 marketplace 时注册 provider service。

Python：

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    "0xYOUR_PRIVATE_KEY",
    environment="staging",
)
issued = auth.issue_credential(name="agent-preview", maxCalls=100, creditLimit=5)
print(issued.credential.id, issued.token)
```

TypeScript：

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

## Provider 发布接入

当 owner 想把自己的 API 发布成 SynapseNetwork service 时，使用 `SynapseProvider`。它是 owner-authenticated provider 控制面方法的 facade，已有 `SynapseAuth` 方法继续兼容。

Python：

```python
from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key("0xYOUR_PRIVATE_KEY", environment="staging")
provider = auth.provider()

secret = provider.issue_secret(name="weather-api")
guide = provider.get_registration_guide()
service = provider.register_service(
    service_name="Weather API",
    endpoint_url="https://provider.example.com/invoke",
    base_price_usdc="0.001",
    description_for_model="Returns weather data for a city.",
)
status = provider.get_service_status(service.service_id)
```

TypeScript：

```ts
import { Wallet } from "ethers";
import { SynapseAuth } from "@synapse-network/sdk";

const auth = SynapseAuth.fromWallet(new Wallet(process.env.OWNER_PRIVATE_KEY!), {
  environment: "staging",
});
const provider = auth.provider();

const secret = await provider.issueSecret({ name: "weather-api" });
const guide = await provider.getRegistrationGuide();
const service = await provider.registerService({
  serviceName: "Weather API",
  endpointUrl: "https://provider.example.com/invoke",
  basePriceUsdc: "0.001",
  descriptionForModel: "Returns weather data for a city.",
});
const status = await provider.getServiceStatus(service.serviceId);
```

凭据处理和漏洞报告请查看 [SECURITY.md](./SECURITY.md)。

## Python 示例

Python examples 默认面向 staging，位于 `python/examples`。

```bash
cd /Users/cliff/workspace/agent/Synapse-Network-Sdk/python
```

在 staging 注册 provider service：

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/provider_staging_onboarding.py \
  --provider-private-key "$SYNAPSE_PROVIDER_PRIVATE_KEY" \
  --endpoint-url "https://your-provider.example.com/invoke" \
  --service-name "Weather API" \
  --description "Returns weather data for a city." \
  --price-usdc 0
```

使用已有 Agent Key 调用 provider service：

```bash
export SYNAPSE_API_KEY=agt_xxx
PYTHONPATH="$PWD" .venv/bin/python examples/consumer_call_provider.py \
  --service-id "weather_api" \
  --payload-json '{"prompt":"hello"}'
```

创建新的 staging wallet、签发 Agent Key，并调用免费服务：

```bash
PYTHONPATH="$PWD" .venv/bin/python examples/consumer_wallet_to_invoke.py \
  --query "free"
```

## 当前 API 边界

当前已支持：

- Consumer discovery/search
- Price-asserted invoke
- Price-mismatch rediscovery helper
- Invocation receipt lookup
- Gateway health and empty-discovery diagnostics
- Owner auth and credential issue/list/update/revoke/rotate/delete/quota/audit logs
- Balance, voucher, usage, finance audit, and risk overview helpers
- Provider publishing facade through `auth.provider()`
- Provider secret issue/list/delete
- Provider service register/list/get/status/update/delete/ping/registration guide/health history
- Provider earnings and withdrawal intent/list/capability helpers

尚未封装：

- Refunds、notifications、community、event APIs
- 链上 deposit transaction signing helpers

完整能力清单见 [docs/sdk/capability_inventory.md](./docs/sdk/capability_inventory.md)。

Finance 和 withdrawal helper 只是显式 API wrapper。SDK 不会代表 Agent 自动转移资金、签名交易或提交高影响资金操作。

## 开发

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

MIT License。更多信息见 `LICENSE`。
