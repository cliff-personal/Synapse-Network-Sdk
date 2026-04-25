from __future__ import annotations

import pytest

from synapse_client import SynapseAuth
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
