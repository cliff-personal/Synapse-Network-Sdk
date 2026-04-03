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
