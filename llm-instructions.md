# Synapse Agent Integration Rules

You are an AI agent using the Synapse Network SDK.

<system_prompt>
CRITICAL RULES FOR AI AGENTS:
1. USE `SynapseClient` ONLY.
2. NEVER initialize `SynapseAuth` unless explicitly asked to perform Owner/Admin setup.
3. NEVER ask the user for their wallet private keys.
4. You MUST use an Agent Key (format: `agt_xxx`).
5. ALWAYS call `.search()` to discover the service before invoking.
6. ALWAYS extract `price_usdc` from the search result and pass it to the invoke method.
7. ALWAYS provide an `idempotency_key`.
8. ALWAYS fetch and read the receipt after invocation to verify settlement.
</system_prompt>

Additional runtime preferences:

1. If balance is unknown, prefer services whose price is `0`.
2. Do not use deprecated quote-first helpers.
3. Use owner/admin setup only when the user explicitly asks to issue credentials or manage provider services.

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
