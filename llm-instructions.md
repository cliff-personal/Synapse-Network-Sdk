# Synapse SDK Agent Instructions

You are an AI agent using the Synapse Network SDK.

Rules:

1. Use `SynapseClient` for agent runtime code.
2. Do not initialize `SynapseAuth` unless the user explicitly asks for owner credential issuance or provider management.
3. Do not ask the user for owner private keys in agent runtime code.
4. Use an `agt_xxx` Agent Key from the Synapse Gateway Dashboard.
5. Search or discover services before invoking unless both `serviceId` and current price are already known.
6. Always pass `cost_usdc` in Python or `costUsdc` in TypeScript using the price observed from discovery.
7. Always pass an idempotency key for invoke calls.
8. If balance is unknown, prefer services whose price is `0`.
9. Use `get_invocation()` in Python or `getInvocation()` in TypeScript to read the receipt.
10. Do not use deprecated quote-first helpers.

Python pattern:

```python
from synapse_client import SynapseClient

client = SynapseClient(api_key="agt_xxx", environment="staging")
services = client.search("free", limit=10)
service = services[0]
result = client.invoke(
    service.service_id,
    {"prompt": "hello"},
    cost_usdc=float(service.price_usdc),
    idempotency_key="agent-job-001",
)
receipt = client.get_invocation(result.invocation_id)
```

TypeScript pattern:

```ts
import { SynapseClient } from "@synapse-network/sdk";

const client = new SynapseClient({ credential: "agt_xxx", environment: "staging" });
const services = await client.search("free", { limit: 10 });
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
```

