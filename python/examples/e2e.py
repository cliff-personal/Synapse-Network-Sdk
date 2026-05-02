from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from typing import Any
from uuid import uuid4

from synapse_client import AuthenticationError, InvokeError, SynapseClient

SYNAPSE_ECHO_SERVICE_ID = "svc_synapse_echo"
DEFAULT_FIXED_PAYLOAD = {
    "message": "hello from Synapse SDK smoke",
    "metadata": {"scenario": "fixed-price"},
}
DEFAULT_LLM_PAYLOAD = {"messages": [{"role": "user", "content": "hello"}]}


def main() -> None:
    client = new_client(require_env("SYNAPSE_AGENT_KEY"))
    local_negative(client)
    client.check_gateway_health()
    emit("health", status="ok")

    if not env_bool("SYNAPSE_E2E_SKIP_AUTH_NEGATIVE"):
        auth_negative()

    service_id, cost_usdc, fixed_payload = fixed_target(client)
    fixed_result = client.invoke(
        service_id,
        fixed_payload,
        cost_usdc=cost_usdc,
        idempotency_key=idempotency_key("python", "fixed"),
    )
    fixed_receipt = await_receipt(client, fixed_result.invocation_id)
    emit(
        "fixed-price",
        status=fixed_result.status,
        invocation_id=fixed_result.invocation_id,
        charged_usdc=str(fixed_receipt.charged_usdc),
        receipt_status=fixed_receipt.status,
        service_id=service_id,
    )

    if env_bool("SYNAPSE_E2E_FREE_ONLY"):
        return

    llm_service_id = env_default("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat")
    max_cost_usdc = env_default("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000")
    llm_result = client.invoke_llm(
        llm_service_id,
        json_payload("SYNAPSE_E2E_LLM_PAYLOAD_JSON", DEFAULT_LLM_PAYLOAD),
        max_cost_usdc=max_cost_usdc,
        idempotency_key=idempotency_key("python", "llm"),
    )
    llm_receipt = await_receipt(client, llm_result.invocation_id)
    charged_usdc = str(llm_receipt.charged_usdc or llm_result.charged_usdc)
    if Decimal(charged_usdc) > Decimal(max_cost_usdc):
        fail(f"llm chargedUsdc {charged_usdc} exceeds maxCostUsdc {max_cost_usdc}")
    emit(
        "llm",
        status=llm_result.status,
        invocation_id=llm_result.invocation_id,
        charged_usdc=charged_usdc,
        receipt_status=llm_receipt.status,
        service_id=llm_service_id,
    )


def new_client(credential: str) -> SynapseClient:
    return SynapseClient(
        api_key=credential,
        gateway_url=os.getenv("SYNAPSE_GATEWAY_URL") or None,
        environment="staging",
    )


def local_negative(client: SynapseClient) -> None:
    expect_error(
        lambda: client.invoke("svc_local", {}, cost_usdc=None),
        ValueError,
        "fixed-price invoke without cost_usdc should fail locally",
    )
    expect_error(
        lambda: client.invoke_llm("svc_llm", {"stream": True}),
        InvokeError,
        "LLM stream=True should fail locally",
    )
    emit("local-negative", status="ok")


def auth_negative() -> None:
    invalid_client = new_client("agt_invalid")
    expect_error(
        lambda: invalid_client.invoke("svc_invalid_auth_probe", {}, cost_usdc="0"),
        AuthenticationError,
        "invalid credential should fail with AuthenticationError",
    )
    emit("auth-negative", status="ok")


def fixed_target(client: SynapseClient) -> tuple[str, str, dict[str, Any]]:
    payload = json_payload("SYNAPSE_E2E_FIXED_PAYLOAD_JSON", DEFAULT_FIXED_PAYLOAD)
    configured_service_id = os.getenv("SYNAPSE_E2E_FIXED_SERVICE_ID", "").strip()
    if configured_service_id:
        configured_cost = os.getenv("SYNAPSE_E2E_FIXED_COST_USDC", "").strip()
        if not configured_cost:
            fail("SYNAPSE_E2E_FIXED_COST_USDC is required when SYNAPSE_E2E_FIXED_SERVICE_ID is set")
        return configured_service_id, configured_cost, payload

    services = client.search(SYNAPSE_ECHO_SERVICE_ID, limit=10)
    for service in services:
        amount = str(service.pricing.amount)
        if (
            service.service_id == SYNAPSE_ECHO_SERVICE_ID
            and service.service_kind.lower() == "api"
            and service.price_model.lower() == "fixed"
            and Decimal(amount) == Decimal("0")
        ):
            return service.service_id, amount, payload

    services = client.search("free", limit=25)
    for service in services:
        amount = str(service.pricing.amount)
        if (
            service.service_id
            and service.service_kind.lower() == "api"
            and service.price_model.lower() == "fixed"
            and Decimal(amount) == Decimal("0")
        ):
            return service.service_id, amount, payload
    fail(
        "no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID, "
        "SYNAPSE_E2E_FIXED_COST_USDC, and SYNAPSE_E2E_FIXED_PAYLOAD_JSON"
    )
    raise RuntimeError("unreachable")


def await_receipt(client: SynapseClient, invocation_id: str):
    if not invocation_id:
        fail("invoke returned empty invocationId")
    deadline = time.monotonic() + env_int("SYNAPSE_E2E_RECEIPT_TIMEOUT_S", 60)
    while True:
        receipt = client.get_invocation(invocation_id)
        if receipt.invocation_id and receipt.invocation_id != invocation_id:
            fail(f"receipt invocationId mismatch: got {receipt.invocation_id} want {invocation_id}")
        if receipt.status in {"SUCCEEDED", "SETTLED"}:
            return receipt
        if time.monotonic() > deadline:
            fail(f"receipt {invocation_id} did not reach a terminal status, last status={receipt.status}")
        time.sleep(2)


def json_payload(name: str, fallback: dict[str, Any]) -> dict[str, Any]:
    raw = os.getenv(name)
    if not raw:
        return fallback
    value = json.loads(raw)
    if not isinstance(value, dict):
        fail(f"{name} must be a JSON object")
    return value


def emit(
    scenario: str,
    *,
    status: str,
    invocation_id: str = "",
    charged_usdc: str = "",
    receipt_status: str = "",
    service_id: str = "",
) -> None:
    event = {
        "language": "python",
        "scenario": scenario,
        "status": status,
        "invocationId": invocation_id,
        "chargedUsdc": charged_usdc,
        "receiptStatus": receipt_status,
        "serviceId": service_id,
    }
    print(json.dumps({key: value for key, value in event.items() if value}, separators=(",", ":")))


def expect_error(action, expected_type: type[BaseException], message: str) -> None:
    try:
        action()
    except expected_type:
        return
    except Exception as exc:
        fail(f"{message}; got {type(exc).__name__}: {exc}")
    fail(message)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        fail(f"{name} is required")
    return value


def env_default(name: str, fallback: str) -> str:
    return os.getenv(name, "").strip() or fallback


def env_int(name: str, fallback: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return fallback
    try:
        value = int(raw)
    except ValueError:
        return fallback
    return value if value > 0 else fallback


def env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y"}


def idempotency_key(language: str, scenario: str) -> str:
    run_id = os.getenv("E2E_RUN_ID", "").strip()
    prefix = f"{run_id}-{language}-e2e" if run_id else f"{language}-e2e"
    return f"{prefix}-{scenario}-{uuid4().hex}"


def fail(message: str) -> None:
    print(f"python e2e failed: {message}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
