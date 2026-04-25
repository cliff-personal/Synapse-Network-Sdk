# Synapse Network SDK

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/TypeScript-available-blue.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

Official Python and TypeScript SDKs for the Synapse Network gateway.

The current SDKs focus on the canonical consumer/provider main flow:

1. Authenticate an owner wallet and issue an agent credential.
2. Discover services through the gateway.
3. Invoke a selected service with the discovered USDC price.
4. Read the invocation receipt.
5. Register provider services through the owner/provider control plane.

Legacy quote-first runtime APIs are no longer the public gateway contract. Use discovery/search plus `invoke(..., cost_usdc=...)` instead.

## Quickstart: Python Consumer

```python
from synapse_client import SynapseClient

client = SynapseClient(
    api_key="agt_xxx",
    gateway_url="http://127.0.0.1:8000",
)

services = client.search("market data", limit=10)
service = services[0]

result = client.invoke(
    service.service_id,
    {"prompt": "hello"},
    cost_usdc=float(service.price_usdc),
    idempotency_key="job-001",
)

print(result.invocation_id, result.status, result.charged_usdc)
```

Python config resolution:

- `api_key`: explicit argument, then `SYNAPSE_API_KEY`.
- `gateway_url`: explicit argument, then `SYNAPSE_GATEWAY`, then `http://127.0.0.1:8000`.

## Quickstart: TypeScript Consumer

```ts
import { SynapseClient } from "@synapse-network/sdk";

const client = new SynapseClient({
  credential: "agt_xxx",
  gatewayUrl: process.env.SYNAPSE_GATEWAY ?? "http://127.0.0.1:8000",
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
    idempotencyKey: "job-001",
  }
);

console.log(result.invocationId, result.status, result.chargedUsdc);
```

TypeScript is explicit-config only: pass `credential` and `gatewayUrl` from your application environment.

## Provider Flow

Provider onboarding is handled through `SynapseAuth`:

1. Authenticate the owner/provider wallet.
2. Issue or list provider secrets.
3. Register/list/get provider services.
4. Treat owner `/api/v1/services` as the onboarding source of truth.

## Documentation

- `python/`: Python SDK implementation and examples.
- `typescript/`: TypeScript SDK implementation and tests.
- `docs/sdk/README.md`: SDK docs hub.
- `docs/sdk/capability_inventory.md`: current supported and unsupported gateway capabilities.

For the gateway and provider service implementation, see the sibling `Synapse-Network` and `Synapse-Network-Provider` repositories.

## License

MIT License. See `LICENSE` for more information.
