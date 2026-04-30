from __future__ import annotations

import json
import os
from decimal import Decimal
from uuid import uuid4

from synapse_client import SynapseClient


def main() -> None:
    client = SynapseClient(
        api_key=require_env("SYNAPSE_AGENT_KEY"),
        gateway_url=os.getenv("SYNAPSE_GATEWAY_URL") or None,
        environment="staging",
    )
    service_id = os.getenv("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat")
    max_cost_usdc = os.getenv("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000")
    result = client.invoke_llm(
        service_id,
        payload({"messages": [{"role": "user", "content": "hello"}]}),
        max_cost_usdc=max_cost_usdc,
        idempotency_key=f"python-llm-smoke-{uuid4().hex}",
    )
    receipt = client.get_invocation(result.invocation_id)
    charged = Decimal(str(receipt.charged_usdc or result.charged_usdc))
    if charged > Decimal(max_cost_usdc):
        raise RuntimeError(f"chargedUsdc {charged} exceeds maxCostUsdc {max_cost_usdc}")
    print(
        json.dumps(
            {
                "language": "python",
                "scenario": "llm-smoke",
                "serviceId": service_id,
                "invocationId": result.invocation_id,
                "status": result.status,
                "chargedUsdc": str(charged),
                "receiptStatus": receipt.status,
            },
            separators=(",", ":"),
        )
    )


def payload(default_value: dict) -> dict:
    raw = os.getenv("SYNAPSE_E2E_LLM_PAYLOAD_JSON")
    if not raw:
        return default_value
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("SYNAPSE_E2E_LLM_PAYLOAD_JSON must be a JSON object")
    return value


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


if __name__ == "__main__":
    main()
