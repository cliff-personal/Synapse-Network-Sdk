from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4

import pytest

from synapse_client import SynapseAuth

pytest.importorskip("eth_account")

from eth_account import Account


GATEWAY_URL = "http://127.0.0.1:8000"
MOCK_PROVIDER_PORT = 9499
SESSION_ID = uuid4().hex[:8]
SERVICE_NAME = f"Python Provider OCR {SESSION_ID}"


class _MockProviderHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        return

    def _write_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._write_json(200, {"status": "healthy"})

    def do_POST(self):  # noqa: N802
        self._write_json(200, {"result": "provider-sdk e2e mock response"})


@pytest.fixture(scope="module")
def mock_provider_server():
    server = HTTPServer(("127.0.0.1", MOCK_PROVIDER_PORT), _MockProviderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{MOCK_PROVIDER_PORT}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.e2e
def test_python_sdk_provider_onboarding_e2e(mock_provider_server):
    fresh_provider = Account.create(f"provider-e2e-{SESSION_ID}")
    provider_auth = SynapseAuth.from_private_key(
        fresh_provider.key.hex(),
        gateway_url=GATEWAY_URL,
        timeout_sec=30,
    )

    token = provider_auth.get_token()
    assert isinstance(token, str) and len(token) > 20

    issued = provider_auth.issue_provider_secret(
        name=f"python-provider-secret-{SESSION_ID}",
        rpm=180,
        creditLimit=25.0,
    )
    assert issued.secret.id
    assert issued.secret.secret_key.startswith("agt_")
    assert issued.secret.owner_address == fresh_provider.address.lower()

    registered = provider_auth.register_provider_service(
        service_name=SERVICE_NAME,
        endpoint_url=mock_provider_server,
        base_price_usdc="0.002",
        description_for_model="Extract structured invoice fields for provider onboarding e2e.",
        provider_display_name=f"Python Provider {SESSION_ID}",
        governance_note="python provider sdk e2e",
    )
    assert registered.status == "success"
    assert registered.service_id

    services = provider_auth.list_provider_services()
    service_ids = [service.service_id for service in services]
    assert registered.service_id in service_ids

    status = provider_auth.get_provider_service_status(registered.service_id)
    assert status.service_id == registered.service_id
    assert status.lifecycle_status in {"active", "draft", "paused"}
    assert status.health.overall_status in {"healthy", "unknown", "degraded"}
