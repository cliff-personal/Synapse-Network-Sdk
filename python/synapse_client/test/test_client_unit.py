from __future__ import annotations

import pytest

from synapse_client import AgentWallet, SynapseClient
from synapse_client.exceptions import (
    AuthenticationError,
    DiscoveryError,
    InsufficientFundsError,
    InvokeError,
    PriceMismatchError,
    QuoteError,
    SynapseClientError,
    TimeoutError,
)


class DummyResponse:
    def __init__(self, *, status_code: int = 200, json_data=None, text: str = "", ok: bool | None = None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text
        self.ok = ok if ok is not None else 200 <= status_code < 300

    def json(self):
        return self._json_data


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)

    with pytest.raises(ValueError, match="api_key is required"):
        SynapseClient(api_key="")


def test_client_uses_synapse_gateway_env(monkeypatch):
    monkeypatch.setenv("SYNAPSE_GATEWAY", "https://gateway.example")
    client = SynapseClient(api_key="agt_test")

    assert client.gateway_url == "https://gateway.example"


def test_agent_wallet_connect_requires_real_credential(monkeypatch):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)

    with pytest.raises(ValueError, match="api_key is required"):
        AgentWallet.connect()


def test_discover_services_passes_intent_and_parses_response(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return DummyResponse(
            json_data={
                "requestId": "disc_123",
                "page": 1,
                "pageSize": 10,
                "totalCount": 1,
                "hasMore": False,
                "count": 1,
                "results": [
                    {
                        "serviceId": "svc_quotes_famous_top3",
                        "serviceName": "Quotes Famous Top3",
                        "pricing": {"amount": "0.05", "currency": "USDC"},
                        "summary": "Return top 3 famous quotes.",
                        "tags": ["quotes", "top3"],
                        "status": "online",
                        "health": {
                            "overallStatus": "healthy",
                            "healthyTargets": 1,
                            "totalTargets": 1,
                        },
                        "invoke": {"method": "POST", "request": {}, "response": {}},
                        "quoteTemplate": {
                            "serviceId": "svc_quotes_famous_top3",
                            "inputPreview": {"contentType": "application/json", "payloadSchema": {"body": {}}, "sample": {"body": {}}},
                            "responseMode": "sync",
                        },
                    }
                ],
            }
        )

    monkeypatch.setattr("synapse_client.client.requests.post", fake_post)

    client = SynapseClient(api_key="agt_test", gateway_url="http://127.0.0.1:8000", timeout_sec=12)
    result = client.discover_services(intent="quotes", tags=["quotes"])

    assert result.count == 1
    assert result.request_id == "disc_123"
    assert result.page == 1
    assert result.page_size == 10
    assert result.total_count == 1
    assert result.has_more is False
    assert result.services[0].serviceId == "svc_quotes_famous_top3"
    assert str(result.services[0].price_usdc) == "0.05"
    assert calls == [
        {
            "url": "http://127.0.0.1:8000/api/v1/agent/discovery/search",
            "headers": {
                "Content-Type": "application/json",
                "X-Credential": "agt_test",
            },
            "json": {
                "query": "quotes",
                "tags": ["quotes"],
                "page": 1,
                "pageSize": 10,
                "sort": "best_match",
            },
            "timeout": 12,
        }
    ]


def test_discover_services_raises_discovery_error_on_failure(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda url, headers, json, timeout: DummyResponse(status_code=500, text="boom", ok=False),
    )

    client = SynapseClient(api_key="agt_test")

    with pytest.raises(DiscoveryError, match="boom"):
        client.discover_services(intent="quotes")


def test_create_quote_is_deprecated(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda *args, **kwargs: pytest.fail("deprecated quote flow must not call gateway"),
    )
    client = SynapseClient(api_key="agt_test")

    with pytest.raises(QuoteError, match="price-asserted single-call invoke"):
        client.create_quote("svc_quotes_famous_top3", payload={"text": "hello"})


def test_create_invocation_is_deprecated(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda *args, **kwargs: pytest.fail("deprecated invocation flow must not call gateway"),
    )
    client = SynapseClient(api_key="agt_test")

    with pytest.raises(InvokeError, match="price-asserted single-call invoke"):
        client.create_invocation("qt_abc", {"key": "val"}, idempotency_key="ik_test")


def test_invoke_service_is_deprecated(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda *args, **kwargs: pytest.fail("deprecated invoke_service flow must not call gateway"),
    )
    client = SynapseClient(api_key="agt_test")

    with pytest.raises(SynapseClientError, match="price-asserted single-call invoke"):
        client.invoke_service("svc_1", {"prompt": "test"}, idempotency_key="ik_chain")


def test_wait_for_invocation_raises_timeout_when_pending_exceeds_budget(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.client.requests.get",
        lambda url, headers, timeout: DummyResponse(
            json_data={"invocationId": "inv_123", "status": "PENDING", "chargedUsdc": 0.0}
        ),
    )
    monkeypatch.setattr("synapse_client.client.time.sleep", lambda seconds: None)

    timeline = iter([0, 2, 4])
    monkeypatch.setattr("synapse_client.client.time.time", lambda: next(timeline))

    client = SynapseClient(api_key="agt_test")

    with pytest.raises(TimeoutError, match="pending timeout"):
        client.wait_for_invocation("inv_123", max_wait_sec=3)


def test_alias_methods_delegate_to_runtime_client(monkeypatch):
    client = SynapseClient(api_key="agt_test")

    monkeypatch.setattr(
        client,
        "search_services",
        lambda **kwargs: type(
            "Resp",
            (),
            {
                "services": ["svc-1", "svc-2"],
            },
        )(),
    )
    monkeypatch.setattr(
        client,
        "get_invocation_receipt",
        lambda invocation_id: {"invocationId": invocation_id},
    )

    assert client.discover(limit=20) == ["svc-1", "svc-2"]
    assert client.search("quotes", limit=20) == ["svc-1", "svc-2"]
    assert client.get_invocation("inv-123") == {"invocationId": "inv-123"}


@pytest.mark.parametrize(
    ("status_code", "json_data", "error_type", "match"),
    [
        (401, {"detail": {"code": "CREDENTIAL_INVALID", "message": "bad key"}}, AuthenticationError, "bad key"),
        (402, {"detail": {"code": "BUDGET_EXHAUSTED", "message": "budget empty"}}, InsufficientFundsError, "budget empty"),
        (500, {}, InvokeError, "upstream exploded"),
    ],
)
def test_invoke_maps_error_status_codes(monkeypatch, status_code, json_data, error_type, match):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda url, headers, json, timeout: DummyResponse(status_code=status_code, json_data=json_data, text="upstream exploded", ok=False),
    )
    client = SynapseClient(api_key="agt_test")
    with pytest.raises(error_type, match=match):
        client.invoke(service_id="svc_1", payload={"text": "hi"}, cost_usdc=0.05)


# ---------------------------------------------------------------------------
# cost_usdc path — single-call /agent/invoke
# ---------------------------------------------------------------------------


def test_invoke_with_cost_usdc_calls_agent_invoke_endpoint(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return DummyResponse(
            json_data={"invocationId": "inv_cost", "status": "SUCCEEDED", "chargedUsdc": 0.05}
        )

    monkeypatch.setattr("synapse_client.client.requests.post", fake_post)
    client = SynapseClient(api_key="agt_test")
    result = client.invoke("svc_1", {"text": "hi"}, cost_usdc=0.05, idempotency_key="k1")

    assert len(calls) == 1
    assert calls[0]["url"].endswith("/api/v1/agent/invoke")
    assert calls[0]["json"]["costUsdc"] == pytest.approx(0.05)
    assert calls[0]["json"]["serviceId"] == "svc_1"
    assert result.invocation_id == "inv_cost"


def test_invoke_with_cost_usdc_sends_payload_body(monkeypatch):
    captured = []

    def fake_post(url, headers, json, timeout):
        captured.append(json)
        return DummyResponse(
            json_data={"invocationId": "inv_b", "status": "SUCCEEDED", "chargedUsdc": 0.10}
        )

    monkeypatch.setattr("synapse_client.client.requests.post", fake_post)
    client = SynapseClient(api_key="agt_test")
    client.invoke("svc_2", {"prompt": "test"}, cost_usdc=0.10, idempotency_key="ik2")

    assert captured[0]["payload"]["body"] == {"prompt": "test"}
    assert captured[0]["costUsdc"] == pytest.approx(0.10)


def test_invoke_with_cost_usdc_raises_price_mismatch_error(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda url, headers, json, timeout: DummyResponse(
            status_code=422,
            ok=False,
            json_data={
                "detail": {
                    "code": "PRICE_MISMATCH",
                    "message": "Price changed",
                    "expectedPriceUsdc": 0.05,
                    "currentPriceUsdc": 0.15,
                }
            },
        ),
    )
    client = SynapseClient(api_key="agt_test")

    with pytest.raises(PriceMismatchError) as exc_info:
        client.invoke("svc_x", {}, cost_usdc=0.05, idempotency_key="k_pm")

    assert exc_info.value.expected_price_usdc == pytest.approx(0.05)
    assert exc_info.value.current_price_usdc == pytest.approx(0.15)
