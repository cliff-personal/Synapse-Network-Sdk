# Synapse Network SDK

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/TypeScript-available-blue.svg" />
  <img src="https://img.shields.io/badge/Status-Public%20Preview-orange.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

Python and TypeScript SDKs for AI agents and developers building on Synapse Network.

Synapse lets an agent discover services, invoke them through a gateway, and settle the call with an auditable receipt. The fastest integration path is:

1. Get an Agent Key (`agt_xxx`) from the Synapse Gateway Dashboard.
2. Create a `SynapseClient`.
3. Search, invoke, and read the receipt.

> Public Preview default: SDK examples use `staging`, backed by `https://api-staging.synapse-network.ai`.
> The `prod` preset points to `https://api.synapse-network.ai`, but production should only be used after official DNS and `/health` are live.

## Gateway Docs

| Surface | Link | Status |
|---|---|---|
| SDK Hub | [staging.synapse-network.ai/docs/sdk](https://staging.synapse-network.ai/docs/sdk) | Public Preview |
| Python SDK | [staging.synapse-network.ai/docs/sdk/python](https://staging.synapse-network.ai/docs/sdk/python) | Public Preview |
| TypeScript SDK | [staging.synapse-network.ai/docs/sdk/typescript](https://staging.synapse-network.ai/docs/sdk/typescript) | Public Preview |
| Production docs | Reserved until production docs are live | Reserved |

## Gateway Environments

| Environment | Gateway URL | Intended use |
|---|---|---|
| `staging` | `https://api-staging.synapse-network.ai` | Public preview, test assets, integration trials |
| `local` | `http://127.0.0.1:8000` | Local gateway development |
| `prod` | `https://api.synapse-network.ai` | Production preset, pending official DNS and health verification |

Resolution rules:

1. Explicit `gateway_url` / `gatewayUrl`
2. Explicit `environment`
3. Python only: `SYNAPSE_GATEWAY`
4. Python only: `SYNAPSE_ENV`
5. Default: `staging`

The SDK never probes DNS and never falls back between environments automatically. This prevents production credentials or funds from being routed to the wrong gateway.

## Agent Quickstart: Python

Step 1: get your Agent Key from the Synapse Gateway Dashboard.

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

Step 2: let your agent discover and work.

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

## Agent Quickstart: TypeScript

Step 1: get your Agent Key from the Synapse Gateway Dashboard.

`Gateway Dashboard -> Connect Wallet -> Generate Agent Key`

Step 2: pass the key to the SDK.

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

## Advanced: Programmatic Credential Issuance

Use `SynapseAuth` only when an owner/backend service needs to issue credentials or register provider services programmatically. Ordinary agent runtime code should use `SynapseClient` with an existing `agt_xxx` key.

1. Authenticate an owner wallet.
2. Issue an agent credential with spending limits.
3. Hand that credential to an agent runtime.
4. Register provider services when publishing APIs to the marketplace.

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

## Current API Boundary

Supported today:

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

- Refunds, notifications, community, and event APIs
- On-chain deposit transaction signing helpers

See [docs/sdk/capability_inventory.md](./docs/sdk/capability_inventory.md) for the detailed inventory.

Finance and withdrawal helpers are explicit API wrappers only. The SDK will not automatically move funds, sign transactions, or submit high-impact financial actions on behalf of an agent.

## Development

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
