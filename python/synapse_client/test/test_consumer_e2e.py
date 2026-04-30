from __future__ import annotations

import os
from uuid import uuid4

import pytest

from synapse_client import SynapseClient

pytestmark = pytest.mark.e2e


def _staging_consumer_env() -> dict[str, str]:
    if os.getenv("RUN_STAGING_E2E") != "1":
        pytest.skip("set RUN_STAGING_E2E=1 to run staging consumer e2e tests")

    required = {
        "SYNAPSE_AGENT_KEY": os.getenv("SYNAPSE_AGENT_KEY", "").strip(),
        "SYNAPSE_STAGING_SERVICE_ID": os.getenv("SYNAPSE_STAGING_SERVICE_ID", "").strip(),
        "SYNAPSE_STAGING_SERVICE_PRICE_USDC": os.getenv("SYNAPSE_STAGING_SERVICE_PRICE_USDC", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"missing staging consumer e2e env: {', '.join(missing)}")
    return required


def test_python_sdk_staging_fixed_price_invoke_e2e():
    env = _staging_consumer_env()
    client = SynapseClient(
        api_key=env["SYNAPSE_AGENT_KEY"],
        environment="staging",
        timeout_sec=30,
    )

    invocation = client.invoke(
        env["SYNAPSE_STAGING_SERVICE_ID"],
        payload={"prompt": "python sdk staging e2e"},
        cost_usdc=env["SYNAPSE_STAGING_SERVICE_PRICE_USDC"],
        idempotency_key=f"py-staging-e2e-{uuid4().hex[:12]}",
        poll_timeout_sec=60,
    )

    assert invocation.invocation_id
    assert invocation.status in {"SUCCEEDED", "SETTLED"}

    receipt = client.get_invocation_receipt(invocation.invocation_id)
    assert receipt.invocation_id == invocation.invocation_id
    assert receipt.status in {"SUCCEEDED", "SETTLED"}


def test_python_sdk_staging_llm_token_metered_e2e():
    if os.getenv("RUN_STAGING_E2E") != "1":
        pytest.skip("set RUN_STAGING_E2E=1 to run staging consumer e2e tests")

    agent_key = os.getenv("SYNAPSE_AGENT_KEY", "").strip()
    service_id = os.getenv("SYNAPSE_STAGING_LLM_SERVICE_ID", "").strip()
    max_cost_usdc = os.getenv("SYNAPSE_STAGING_LLM_MAX_COST_USDC", "0.010000").strip()
    if not agent_key or not service_id:
        pytest.skip("missing SYNAPSE_AGENT_KEY or SYNAPSE_STAGING_LLM_SERVICE_ID")

    client = SynapseClient(api_key=agent_key, environment="staging", timeout_sec=30)
    invocation = client.invoke_llm(
        service_id,
        payload={"messages": [{"role": "user", "content": "hello from python staging e2e"}]},
        max_cost_usdc=max_cost_usdc,
        idempotency_key=f"py-staging-llm-e2e-{uuid4().hex[:12]}",
        poll_timeout_sec=60,
    )

    assert invocation.invocation_id
    assert invocation.status in {"SUCCEEDED", "SETTLED"}
    assert invocation.synapse is not None
