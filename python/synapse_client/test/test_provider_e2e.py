from __future__ import annotations

import os
from uuid import uuid4

import pytest

from synapse_client import SynapseAuth

pytestmark = pytest.mark.e2e


def _staging_provider_env() -> dict[str, str]:
    if os.getenv("RUN_STAGING_PROVIDER_E2E") != "1":
        pytest.skip("set RUN_STAGING_PROVIDER_E2E=1 to run staging provider e2e tests")

    required = {
        "SYNAPSE_PROVIDER_PRIVATE_KEY": os.getenv("SYNAPSE_PROVIDER_PRIVATE_KEY", "").strip(),
        "SYNAPSE_PROVIDER_ENDPOINT_URL": os.getenv("SYNAPSE_PROVIDER_ENDPOINT_URL", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"missing staging provider e2e env: {', '.join(missing)}")
    if not required["SYNAPSE_PROVIDER_ENDPOINT_URL"].startswith("https://"):
        pytest.skip("SYNAPSE_PROVIDER_ENDPOINT_URL must be a public HTTPS endpoint")
    return required


def test_python_sdk_staging_provider_onboarding_e2e():
    env = _staging_provider_env()
    session_id = uuid4().hex[:8]
    provider_auth = SynapseAuth.from_private_key(
        env["SYNAPSE_PROVIDER_PRIVATE_KEY"],
        environment="staging",
        timeout_sec=30,
    )

    token = provider_auth.get_token()
    assert isinstance(token, str) and len(token) > 20

    issued = provider_auth.issue_provider_secret(
        name=f"python-provider-secret-{session_id}",
        rpm=180,
        creditLimit=25.0,
    )
    assert issued.secret.id
    assert issued.secret.secret_key.startswith("agt_")

    registered = provider_auth.register_provider_service(
        service_name=f"Python Provider Staging {session_id}",
        endpoint_url=env["SYNAPSE_PROVIDER_ENDPOINT_URL"],
        base_price_usdc="0.002",
        description_for_model="Staging provider onboarding e2e service.",
        provider_display_name=f"Python Provider {session_id}",
        governance_note="python provider sdk staging e2e",
    )
    assert registered.service_id

    services = provider_auth.list_provider_services()
    assert registered.service_id in [service.service_id for service in services]

    status = provider_auth.get_provider_service_status(registered.service_id)
    assert status.service_id == registered.service_id
