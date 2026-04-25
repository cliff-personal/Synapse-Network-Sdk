from __future__ import annotations

import pytest

from synapse_client import SynapseAuth, SynapseProvider
from synapse_client.exceptions import AuthenticationError


class DummyResponse:
    def __init__(self, *, status_code: int = 200, json_data=None, text: str = "", ok: bool | None = None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text
        self.ok = ok if ok is not None else 200 <= status_code < 300

    def json(self):
        return self._json_data


def test_authenticate_runs_challenge_sign_verify_and_caches(monkeypatch):
    calls = []

    def fake_request(method, url, headers, json, timeout):
        calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        if url.endswith("/api/v1/auth/challenge?address=0xabc"):
            return DummyResponse(json_data={
                "success": True,
                "challenge": "sign-me",
                "domain": "a2a-pay-network",
            })
        return DummyResponse(json_data={
            "success": True,
            "access_token": "jwt-token",
            "token_type": "bearer",
            "expires_in": 3600,
        })

    monkeypatch.setattr("synapse_client.auth.requests.request", fake_request)

    signed_messages = []

    auth = SynapseAuth(
        wallet_address="0xAbC",
        signer=lambda message: signed_messages.append(message) or "0xsigned",
        gateway_url="http://127.0.0.1:8000",
        timeout_sec=9,
    )

    token1 = auth.get_token()
    token2 = auth.get_token()

    assert token1 == "jwt-token"
    assert token2 == "jwt-token"
    assert signed_messages == ["sign-me"]
    assert calls == [
        {
            "method": "GET",
            "url": "http://127.0.0.1:8000/api/v1/auth/challenge?address=0xabc",
            "headers": {"Content-Type": "application/json"},
            "json": None,
            "timeout": 9,
        },
        {
            "method": "POST",
            "url": "http://127.0.0.1:8000/api/v1/auth/verify",
            "headers": {"Content-Type": "application/json"},
            "json": {
                "wallet_address": "0xabc",
                "message": "sign-me",
                "signature": "0xsigned",
            },
            "timeout": 9,
        },
    ]


def test_auth_defaults_to_staging_gateway(monkeypatch):
    monkeypatch.delenv("SYNAPSE_GATEWAY", raising=False)
    monkeypatch.delenv("SYNAPSE_ENV", raising=False)

    auth = SynapseAuth(
        wallet_address="0xAbC",
        signer=lambda message: "0xsigned",
    )

    assert auth.gateway_url == "https://api-staging.synapse-network.ai"


def test_issue_credential_and_balance_use_bearer_token(monkeypatch):
    calls = []

    def fake_request(method, url, headers, json, timeout):
        calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        if url.endswith("/api/v1/auth/challenge?address=0xabc"):
            return DummyResponse(json_data={
                "success": True,
                "challenge": "sign-me",
                "domain": "a2a-pay-network",
            })
        if url.endswith("/api/v1/auth/verify"):
            return DummyResponse(json_data={
                "success": True,
                "access_token": "jwt-token",
                "token_type": "bearer",
                "expires_in": 3600,
            })
        if url.endswith("/api/v1/credentials/agent/issue"):
            return DummyResponse(json_data={
                "credential": {
                    "id": "cred-123",
                    "token": "agt-123",
                    "name": "bot-1",
                    "status": "active",
                },
            })
        return DummyResponse(json_data={
            "status": "success",
            "balance": {
                "ownerBalance": "9.99",
                "consumerAvailableBalance": "9.98",
                "providerReceivable": "0",
                "platformFeeAccrued": "0.01",
            },
        })

    monkeypatch.setattr("synapse_client.auth.requests.request", fake_request)

    auth = SynapseAuth(
        wallet_address="0xabc",
        signer=lambda _: "0xsigned",
        gateway_url="http://127.0.0.1:8000",
        timeout_sec=12,
    )

    issued = auth.issue_credential(name="bot-1", creditLimit=5.0, maxCalls=100)
    balance = auth.get_balance()

    assert issued.token == "agt-123"
    assert issued.credential.id == "cred-123"
    assert str(balance.consumer_available_balance) == "9.98"
    assert calls[2]["headers"]["Authorization"] == "Bearer jwt-token"
    assert calls[3]["headers"]["Authorization"] == "Bearer jwt-token"


def test_register_and_confirm_deposit(monkeypatch):
    calls = []

    def fake_request(method, url, headers, json, timeout):
        calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        if url.endswith("/api/v1/auth/challenge?address=0xabc"):
            return DummyResponse(json_data={"success": True, "challenge": "sign-me", "domain": "a2a-pay-network"})
        if url.endswith("/api/v1/auth/verify"):
            return DummyResponse(json_data={"success": True, "access_token": "jwt-token", "token_type": "bearer", "expires_in": 3600})
        if url.endswith("/api/v1/balance/deposit/intent"):
            return DummyResponse(json_data={
                "status": "success",
                "tx_hash": "0xabc",
                "intent": {"id": "intent-1", "eventKey": "evt-1", "txHash": "0xabc"},
            })
        return DummyResponse(json_data={
            "status": "success",
            "intent": {"id": "intent-1", "eventKey": "evt-1"},
        })

    monkeypatch.setattr("synapse_client.auth.requests.request", fake_request)

    auth = SynapseAuth(
        wallet_address="0xabc",
        signer=lambda _: "0xsigned",
    )

    intent = auth.register_deposit_intent("0x" + "1" * 64, 10)
    confirmed = auth.confirm_deposit("intent-1", "evt-1")

    assert intent.intent.resolved_id == "intent-1"
    assert intent.intent.resolved_event_key == "evt-1"
    assert confirmed.intent.resolved_id == "intent-1"
    assert calls[2]["headers"]["X-Idempotency-Key"]


def test_auth_error_raises_authentication_error(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.auth.requests.request",
        lambda method, url, headers, json, timeout: DummyResponse(
            status_code=401,
            json_data={"detail": "bad signature"},
            text="bad signature",
            ok=False,
        ),
    )

    auth = SynapseAuth(wallet_address="0xabc", signer=lambda _: "0xsigned")

    with pytest.raises(AuthenticationError, match="bad signature"):
        auth.get_token()


def test_issue_provider_secret_and_list_provider_secrets(monkeypatch):
    calls = []

    def fake_request(method, url, headers, json, timeout):
        calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        if url.endswith("/api/v1/auth/challenge?address=0xabc"):
            return DummyResponse(json_data={"success": True, "challenge": "sign-me", "domain": "a2a-pay-network"})
        if url.endswith("/api/v1/auth/verify"):
            return DummyResponse(json_data={"success": True, "access_token": "jwt-token", "token_type": "bearer", "expires_in": 3600})
        if url.endswith("/api/v1/secrets/provider/issue"):
            return DummyResponse(json_data={
                "status": "success",
                "secret": {
                    "id": "psk_123",
                    "name": "provider-key",
                    "ownerAddress": "0xabc",
                    "secretKey": "agt_provider_123",
                    "maskedKey": "agt_provider...",
                    "status": "active",
                    "rpm": 180,
                    "creditLimit": 25.0,
                    "resetInterval": "monthly",
                    "createdAt": "2026-04-03T10:00:00Z",
                },
            })
        return DummyResponse(json_data={
            "status": "success",
            "secrets": [
                {
                    "id": "psk_123",
                    "name": "provider-key",
                    "ownerAddress": "0xabc",
                    "maskedKey": "agt_provider...",
                    "status": "active",
                    "rpm": 180,
                    "creditLimit": 25.0,
                    "resetInterval": "monthly",
                    "createdAt": "2026-04-03T10:00:00Z",
                }
            ],
        })

    monkeypatch.setattr("synapse_client.auth.requests.request", fake_request)

    auth = SynapseAuth(wallet_address="0xabc", signer=lambda _: "0xsigned")
    issued = auth.issue_provider_secret(name="provider-key", rpm=180, creditLimit=25.0)
    listed = auth.list_provider_secrets()

    assert issued.secret.id == "psk_123"
    assert issued.secret.secret_key == "agt_provider_123"
    assert listed[0].id == "psk_123"
    assert calls[2]["headers"]["Authorization"] == "Bearer jwt-token"
    assert calls[3]["headers"]["Authorization"] == "Bearer jwt-token"


def test_register_provider_service_derives_defaults_and_reads_status(monkeypatch):
    calls = []

    def fake_request(method, url, headers, json, timeout):
        calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        if url.endswith("/api/v1/auth/challenge?address=0xabc"):
            return DummyResponse(json_data={"success": True, "challenge": "sign-me", "domain": "a2a-pay-network"})
        if url.endswith("/api/v1/auth/verify"):
            return DummyResponse(json_data={"success": True, "access_token": "jwt-token", "token_type": "bearer", "expires_in": 3600})
        if url.endswith("/api/v1/services") and method == "POST":
            return DummyResponse(json_data={
                "status": "success",
                "serviceId": "sea_invoice_ocr",
                "service": {
                    "serviceId": "sea_invoice_ocr",
                    "ownerAddress": "0xabc",
                    "serviceName": "SEA Invoice OCR",
                    "summary": "Extract invoice fields.",
                    "status": "active",
                    "isActive": True,
                    "pricing": {"amount": "0.008", "currency": "USDC"},
                    "health": {"overallStatus": "healthy", "healthyTargets": 1, "totalTargets": 1, "runtimeAvailable": True},
                    "runtimeAvailable": True,
                    "invoke": {"method": "POST", "targets": [{"url": "https://provider.example.com/invoke"}], "request": {}, "response": {}},
                },
            })
        return DummyResponse(json_data={
            "status": "success",
            "services": [
                {
                    "serviceId": "sea_invoice_ocr",
                    "ownerAddress": "0xabc",
                    "serviceName": "SEA Invoice OCR",
                    "summary": "Extract invoice fields.",
                    "status": "active",
                    "isActive": True,
                    "pricing": {"amount": "0.008", "currency": "USDC"},
                    "health": {"overallStatus": "healthy", "healthyTargets": 1, "totalTargets": 1, "runtimeAvailable": True},
                    "runtimeAvailable": True,
                    "invoke": {"method": "POST", "targets": [{"url": "https://provider.example.com/invoke"}], "request": {}, "response": {}},
                }
            ],
        })

    monkeypatch.setattr("synapse_client.auth.requests.request", fake_request)

    auth = SynapseAuth(wallet_address="0xabc", signer=lambda _: "0xsigned")
    registered = auth.register_provider_service(
        service_name="SEA Invoice OCR",
        endpoint_url="https://provider.example.com/invoke",
        base_price_usdc="0.008",
        description_for_model="Extract invoice fields.",
    )
    status = auth.get_provider_service_status("sea_invoice_ocr")

    assert registered.service_id == "sea_invoice_ocr"
    assert registered.service.service_id == "sea_invoice_ocr"
    assert status.service_id == "sea_invoice_ocr"
    assert status.lifecycle_status == "active"
    assert status.runtime_available is True
    assert calls[2]["json"]["agentToolName"] == "sea_invoice_ocr"
    assert calls[2]["json"]["payoutAccount"]["payoutAddress"] == "0xabc"
    assert calls[2]["json"]["healthCheck"]["path"] == "/health"


def test_credential_lifecycle_and_owner_observability_helpers(monkeypatch):
    calls = []

    def fake_request(method, url, headers, json, timeout):
        calls.append({"method": method, "url": url, "headers": headers, "json": json})
        if url.endswith("/api/v1/auth/challenge?address=0xabc"):
            return DummyResponse(json_data={"success": True, "challenge": "sign-me", "domain": "a2a-pay-network"})
        if url.endswith("/api/v1/auth/verify"):
            return DummyResponse(json_data={"success": True, "access_token": "jwt-token", "token_type": "bearer", "expires_in": 3600})
        return DummyResponse(json_data={"status": "success", "credentialId": "cred_1"})

    monkeypatch.setattr("synapse_client.auth.requests.request", fake_request)

    auth = SynapseAuth(wallet_address="0xabc", signer=lambda _: "0xsigned", gateway_url="http://127.0.0.1:8000")
    auth.revoke_credential("cred_1")
    auth.rotate_credential("cred_1")
    auth.update_credential_quota("cred_1", credit_limit=5, rpm=60)
    auth.delete_credential("cred_1")
    auth.get_credential_audit_logs(limit=25)
    auth.get_owner_profile()
    auth.get_usage_logs(limit=10)
    auth.get_finance_audit_logs(limit=7)
    auth.get_risk_overview()

    urls = [call["url"] for call in calls[2:]]
    methods = [call["method"] for call in calls[2:]]
    assert methods[:4] == ["POST", "POST", "PATCH", "DELETE"]
    assert urls[0].endswith("/api/v1/credentials/agent/cred_1/revoke")
    assert urls[1].endswith("/api/v1/credentials/agent/cred_1/rotate")
    assert urls[2].endswith("/api/v1/credentials/agent/cred_1/quota")
    assert calls[4]["json"] == {"rpm": 60, "creditLimit": 5}
    assert urls[4].endswith("/api/v1/credentials/agent/audit-logs?limit=25")
    assert urls[5].endswith("/api/v1/auth/me")
    assert urls[6].endswith("/api/v1/usage/logs?limit=10")
    assert urls[7].endswith("/api/v1/finance/audit-logs?limit=7")
    assert urls[8].endswith("/api/v1/finance/risk-overview")


def test_provider_lifecycle_and_finance_helpers(monkeypatch):
    calls = []

    def fake_request(method, url, headers, json, timeout):
        calls.append({"method": method, "url": url, "headers": headers, "json": json})
        if url.endswith("/api/v1/auth/challenge?address=0xabc"):
            return DummyResponse(json_data={"success": True, "challenge": "sign-me", "domain": "a2a-pay-network"})
        if url.endswith("/api/v1/auth/verify"):
            return DummyResponse(json_data={"success": True, "access_token": "jwt-token", "token_type": "bearer", "expires_in": 3600})
        return DummyResponse(json_data={"status": "success"})

    monkeypatch.setattr("synapse_client.auth.requests.request", fake_request)

    auth = SynapseAuth(wallet_address="0xabc", signer=lambda _: "0xsigned", gateway_url="http://127.0.0.1:8000")
    auth.delete_provider_secret("psk_1")
    auth.get_registration_guide()
    auth.parse_curl_to_service_manifest("curl https://provider.example/health")
    auth.update_provider_service("svc_rec_1", {"summary": "updated"})
    auth.delete_provider_service("svc_rec_1")
    auth.ping_provider_service("svc_rec_1")
    auth.get_provider_service_health_history("svc_rec_1", limit=12)
    auth.get_provider_earnings_summary()
    auth.get_provider_withdrawal_capability()
    auth.create_provider_withdrawal_intent(10, idempotency_key="provider-withdraw-fixed")
    auth.list_provider_withdrawals(limit=5)
    auth.redeem_voucher("ABC123DEF456", idempotency_key="voucher-fixed-1234")

    urls = [call["url"] for call in calls[2:]]
    assert urls[0].endswith("/api/v1/secrets/provider/psk_1")
    assert urls[1].endswith("/api/v1/services/registration-guide")
    assert urls[2].endswith("/api/v1/services/parse-curl")
    assert calls[4]["json"] == {"curlCommand": "curl https://provider.example/health"}
    assert urls[3].endswith("/api/v1/services/svc_rec_1")
    assert urls[5].endswith("/api/v1/services/svc_rec_1/ping")
    assert urls[6].endswith("/api/v1/services/svc_rec_1/health/history?limitPerTarget=12")
    assert urls[7].endswith("/api/v1/providers/earnings/summary")
    assert urls[8].endswith("/api/v1/providers/withdrawals/capability")
    assert urls[9].endswith("/api/v1/providers/withdrawals/intent")
    assert calls[11]["headers"]["X-Idempotency-Key"] == "provider-withdraw-fixed"
    assert urls[10].endswith("/api/v1/providers/withdrawals?limit=5")
    assert urls[11].endswith("/api/v1/balance/vouchers/redeem")


def test_provider_facade_delegates_to_owner_auth_methods():
    class DummyAuth:
        def __init__(self):
            self.calls = []

        def issue_provider_secret(self, **options):
            self.calls.append(("issue_provider_secret", options))
            return {"secret": {"id": "psk_1"}}

        def list_provider_secrets(self):
            self.calls.append(("list_provider_secrets", None))
            return []

        def delete_provider_secret(self, secret_id):
            self.calls.append(("delete_provider_secret", secret_id))
            return {"status": "deleted"}

        def get_registration_guide(self):
            self.calls.append(("get_registration_guide", None))
            return {"steps": []}

        def parse_curl_to_service_manifest(self, curl_command):
            self.calls.append(("parse_curl_to_service_manifest", curl_command))
            return {"manifest": {}}

        def register_provider_service(self, **options):
            self.calls.append(("register_provider_service", options))
            return {"serviceId": "svc_1"}

        def list_provider_services(self):
            self.calls.append(("list_provider_services", None))
            return []

        def get_provider_service(self, service_id):
            self.calls.append(("get_provider_service", service_id))
            return {"serviceId": service_id}

        def get_provider_service_status(self, service_id):
            self.calls.append(("get_provider_service_status", service_id))
            return {"serviceId": service_id}

        def update_provider_service(self, service_record_id, patch):
            self.calls.append(("update_provider_service", service_record_id, patch))
            return {"status": "updated"}

        def delete_provider_service(self, service_record_id):
            self.calls.append(("delete_provider_service", service_record_id))
            return {"status": "deleted"}

        def ping_provider_service(self, service_record_id):
            self.calls.append(("ping_provider_service", service_record_id))
            return {"status": "ok"}

        def get_provider_service_health_history(self, service_record_id, *, limit):
            self.calls.append(("get_provider_service_health_history", service_record_id, limit))
            return {"history": []}

        def get_provider_earnings_summary(self):
            self.calls.append(("get_provider_earnings_summary", None))
            return {"total": "0"}

        def get_provider_withdrawal_capability(self):
            self.calls.append(("get_provider_withdrawal_capability", None))
            return {"available": True}

        def create_provider_withdrawal_intent(self, amount_usdc, *, idempotency_key=None, destination_address=None):
            self.calls.append(("create_provider_withdrawal_intent", amount_usdc, idempotency_key, destination_address))
            return {"intentId": "wd_1"}

        def list_provider_withdrawals(self, *, limit):
            self.calls.append(("list_provider_withdrawals", limit))
            return {"withdrawals": []}

    dummy = DummyAuth()
    provider = SynapseProvider(dummy)

    provider.issue_secret(name="provider")
    provider.list_secrets()
    provider.delete_secret("psk_1")
    provider.get_registration_guide()
    provider.parse_curl_to_service_manifest("curl https://provider.example/health")
    provider.register_service(service_name="Weather", endpoint_url="https://provider.example/invoke")
    provider.list_services()
    provider.get_service("svc_1")
    provider.get_service_status("svc_1")
    provider.update_service("rec_1", {"summary": "updated"})
    provider.delete_service("rec_1")
    provider.ping_service("rec_1")
    provider.get_service_health_history("rec_1", limit=3)
    provider.get_earnings_summary()
    provider.get_withdrawal_capability()
    provider.create_withdrawal_intent(5, idempotency_key="fixed", destination_address="0xabc")
    provider.list_withdrawals(limit=2)

    auth = SynapseAuth(wallet_address="0xabc", signer=lambda _: "0xsigned")
    assert isinstance(auth.provider(), SynapseProvider)
    assert dummy.calls == [
        ("issue_provider_secret", {"name": "provider"}),
        ("list_provider_secrets", None),
        ("delete_provider_secret", "psk_1"),
        ("get_registration_guide", None),
        ("parse_curl_to_service_manifest", "curl https://provider.example/health"),
        ("register_provider_service", {"service_name": "Weather", "endpoint_url": "https://provider.example/invoke"}),
        ("list_provider_services", None),
        ("get_provider_service", "svc_1"),
        ("get_provider_service_status", "svc_1"),
        ("update_provider_service", "rec_1", {"summary": "updated"}),
        ("delete_provider_service", "rec_1"),
        ("ping_provider_service", "rec_1"),
        ("get_provider_service_health_history", "rec_1", 3),
        ("get_provider_earnings_summary", None),
        ("get_provider_withdrawal_capability", None),
        ("create_provider_withdrawal_intent", 5, "fixed", "0xabc"),
        ("list_provider_withdrawals", 2),
    ]
