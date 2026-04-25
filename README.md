# Synapse Network SDK

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/TypeScript-available-blue.svg" />
  <img src="https://img.shields.io/badge/Status-Public%20Preview-orange.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

Python and TypeScript SDKs for AI agents and developers building on Synapse Network.

Synapse lets an agent discover paid services, invoke them through a gateway, and settle the call with an auditable receipt. The SDKs cover the current canonical flow:

1. Authenticate an owner wallet and issue an agent credential.
2. Discover services through the Synapse Gateway.
3. Invoke a selected service with the USDC price observed during discovery.
4. Read the invocation receipt.
5. Register provider services through the owner/provider control plane.

> Public Preview default: SDK examples use `staging`, backed by `https://api-staging.synapse-network.ai`.
> The `prod` preset points to `https://api.synapse-network.ai`, but production should only be used after official DNS and `/health` are live.

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

```bash
pip install synapse-client
export SYNAPSE_ENV=staging
export SYNAPSE_API_KEY=agt_xxx
```

```python
from synapse_client import SynapseClient

client = SynapseClient()

services = client.search("market data", limit=10)
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

To use an explicit environment:

```python
client = SynapseClient(api_key="agt_xxx", environment="staging")
```

To use a custom gateway:

```python
client = SynapseClient(api_key="agt_xxx", gateway_url="https://your-gateway.example")
```

## Agent Quickstart: TypeScript

```bash
npm install @synapse-network/sdk
```

```ts
import { SynapseClient } from "@synapse-network/sdk";

const client = new SynapseClient({
  credential: "agt_xxx",
  environment: "staging",
});

const services = await client.search("market data", {
  limit: 10,
  tags: ["finance"],
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

## Human Developer Flow

Use `SynapseAuth` when a human developer or backend service needs to issue credentials or register provider services:

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

## Security

- Never commit API keys, JWTs, provider secrets, private keys, wallet mnemonics, or production logs.
- Treat staging credentials as test-only and production credentials as live funds.
- Use environment variables, a secret manager, or your runtime's secret store.
- Do not paste credentials into GitHub issues, pull requests, screenshots, or agent prompts.
- See [SECURITY.md](./SECURITY.md) for reporting and credential handling guidance.

Release sanity checks:

```bash
git ls-files | rg '(^|/)\\.env|private|secret|key|pem|wallet|mnemonic|credential' | rg -v '(^|/)\\.env\\.example$'
rg 'gateway\\.synapse\\.network' .
```

The first command should not show committed secret-bearing files after the `.env.example` allowlist. The second command should not show new SDK references to the stale gateway domain.

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
