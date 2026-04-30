from __future__ import annotations

import json
import os
from uuid import uuid4

from synapse_client import SynapseClient


def main() -> None:
    client = SynapseClient(
        api_key=require_env("SYNAPSE_AGENT_KEY"),
        gateway_url=os.getenv("SYNAPSE_GATEWAY_URL") or None,
        environment="staging",
    )
    services = client.search("free", limit=25)
    service = next(
        (
            candidate
            for candidate in services
            if candidate.service_kind.lower() == "api"
            and candidate.price_model.lower() == "fixed"
            and str(candidate.pricing.amount) == "0"
        ),
        None,
    )
    if service is None:
        raise RuntimeError(
            "no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID "
            "and SYNAPSE_E2E_FIXED_COST_USDC for paid smoke tests"
        )

    result = client.invoke(
        service.service_id,
        {"prompt": "hello"},
        cost_usdc=str(service.pricing.amount),
        idempotency_key=f"python-free-smoke-{uuid4().hex}",
    )
    receipt = client.get_invocation(result.invocation_id)
    print(
        json.dumps(
            {
                "language": "python",
                "scenario": "free-service-smoke",
                "serviceId": service.service_id,
                "invocationId": result.invocation_id,
                "status": result.status,
                "chargedUsdc": str(receipt.charged_usdc),
                "receiptStatus": receipt.status,
            },
            separators=(",", ":"),
        )
    )


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


if __name__ == "__main__":
    main()
