from __future__ import annotations

import pytest

from synapse_client import SynapseClient
from synapse_client.exceptions import (
    AuthenticationError,
    BudgetExceededError,
    DiscoveryError,
    InsufficientFundsError,
    InvokeError,
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


def test_create_quote_posts_payload_and_returns_quote(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return DummyResponse(
            json_data={
                "requestId": "req_quote_1",
                "quoteId": "quote_123",
                "serviceId": "svc_quotes_famous_top3",
                "priceUsdc": 0.05,
                "priceModel": "fixed",
                "budgetCheck": {
                    "allowed": True,
                    "remainingBudgetUsdc": 10.0,
                    "remainingDailyLimitUsdc": 2.0,
                },
                "expiresAt": "2026-03-19T12:00:00Z",
                "idempotencyScope": "quoteId",
                "invokeConstraints": {"body": {}, "timeoutMs": 3000, "maxPayloadBytes": 4096},
            }
        )

    monkeypatch.setattr("synapse_client.client.requests.post", fake_post)

    client = SynapseClient(api_key="agt_test", timeout_sec=9)
    result = client.create_quote(
        service_id="svc_quotes_famous_top3",
        input_preview={
            "sample": {"body": {"text": "关于坚持"}},
            "payloadSchema": {"body": {"type": "object"}},
        },
        request_id="trace-123",
    )

    assert result.quote_id == "quote_123"
    assert result.price_usdc == pytest.approx(0.05)
    assert result.budget_check.allowed is True
    assert calls == [
        {
            "url": "http://127.0.0.1:8000/api/v1/agent/quotes",
            "headers": {
                "Content-Type": "application/json",
                "X-Credential": "agt_test",
                "X-Request-Id": "trace-123",
            },
            "json": {
                "serviceId": "svc_quotes_famous_top3",
                "inputPreview": {
                    "contentType": "application/json",
                    "payloadSchema": {"body": {"type": "object"}},
                    "sample": {"body": {"text": "关于坚持"}},
                },
                "responseMode": "sync",
            },
            "timeout": 9,
        }
    ]


def test_create_quote_raises_budget_exceeded_when_budget_check_denies(monkeypatch):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda url, headers, json, timeout: DummyResponse(
            json_data={
                "requestId": "req_quote_2",
                "quoteId": "quote_denied",
                "serviceId": "svc_quotes_famous_top3",
                "priceUsdc": 0.05,
                "priceModel": "fixed",
                "budgetCheck": {
                    "allowed": False,
                    "remainingBudgetUsdc": 0.01,
                    "remainingDailyLimitUsdc": 0.01,
                },
                "expiresAt": "2026-03-19T12:00:00Z",
                "idempotencyScope": "quoteId",
                "invokeConstraints": {"body": {}, "timeoutMs": 3000, "maxPayloadBytes": 4096},
            }
        ),
    )

    client = SynapseClient(api_key="agt_test")

    with pytest.raises(BudgetExceededError, match="Credential budget"):
        client.create_quote(service_id="svc_quotes_famous_top3")


@pytest.mark.parametrize(
    ("status_code", "json_data", "error_type", "message"),
    [
        (401, {"detail": {"code": "CREDENTIAL_INVALID", "message": "bad key"}}, AuthenticationError, "bad key"),
        (402, {"detail": {"code": "BUDGET_EXHAUSTED", "message": "budget empty"}}, InsufficientFundsError, "budget empty"),
        (500, {}, InvokeError, "upstream exploded"),
    ],
)
def test_create_invocation_maps_error_status_codes(monkeypatch, status_code, json_data, error_type, message):
    monkeypatch.setattr(
        "synapse_client.client.requests.post",
        lambda url, headers, json, timeout: DummyResponse(status_code=status_code, json_data=json_data, text="upstream exploded", ok=False),
    )

    client = SynapseClient(api_key="agt_test")

    with pytest.raises(error_type, match=message):
        client.create_invocation(quote_id="quote_123", payload={"text": "hi"})


def test_call_service_runs_quote_invoke_and_receipt_poll(monkeypatch):
    post_calls = []
    get_calls = []

    def fake_post(url, headers, json, timeout):
        post_calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.endswith("/api/v1/agent/quotes"):
            return DummyResponse(
                json_data={
                    "requestId": "req_quote_3",
                    "quoteId": "quote_abc",
                    "serviceId": "svc_quotes_famous_top3",
                    "priceUsdc": 0.05,
                    "priceModel": "fixed",
                    "budgetCheck": {"allowed": True, "remainingBudgetUsdc": 10.0, "remainingDailyLimitUsdc": 3.0},
                    "expiresAt": "2026-03-19T12:00:00Z",
                    "idempotencyScope": "quoteId",
                    "invokeConstraints": {"body": {}, "timeoutMs": 3000, "maxPayloadBytes": 4096},
                }
            )
        return DummyResponse(
            json_data={
                "invocationId": "inv_abc",
                "status": "PENDING",
                "chargedUsdc": 0.0,
            }
        )

    def fake_get(url, headers, timeout):
        get_calls.append({"url": url, "headers": headers, "timeout": timeout})
        return DummyResponse(
            json_data={
                "invocationId": "inv_abc",
                "status": "SUCCEEDED",
                "chargedUsdc": 0.05,
                "result": {"answer": "stay hungry"},
                "receipt": {"quoteId": "quote_abc", "invocationId": "inv_abc"},
            }
        )

    monkeypatch.setattr("synapse_client.client.requests.post", fake_post)
    monkeypatch.setattr("synapse_client.client.requests.get", fake_get)
    monkeypatch.setattr("synapse_client.client.time.sleep", lambda seconds: None)

    timeline = iter([0, 0, 1])
    monkeypatch.setattr("synapse_client.client.time.time", lambda: next(timeline))

    client = SynapseClient(api_key="agt_test", timeout_sec=9)
    result = client.call_service(
        service_id="svc_quotes_famous_top3",
        payload={"text": "关于坚持"},
        request_id="trace-123",
        idempotency_key="job-1-step-1",
    )

    assert result.content == {"answer": "stay hungry"}
    assert result.invocation_id == "inv_abc"
    assert result.quote_id == "quote_abc"
    assert result.fee_deducted == pytest.approx(0.05)
    assert post_calls == [
        {
            "url": "http://127.0.0.1:8000/api/v1/agent/quotes",
            "headers": {
                "Content-Type": "application/json",
                "X-Credential": "agt_test",
                "X-Request-Id": "trace-123",
            },
            "json": {
                "serviceId": "svc_quotes_famous_top3",
                "inputPreview": {
                    "contentType": "application/json",
                    "payloadSchema": {"body": {}},
                    "sample": {"body": {"text": "关于坚持"}},
                },
                "responseMode": "sync",
            },
            "timeout": 9,
        },
        {
            "url": "http://127.0.0.1:8000/api/v1/agent/invocations",
            "headers": {
                "Content-Type": "application/json",
                "X-Credential": "agt_test",
                "X-Request-Id": "trace-123",
            },
            "json": {
                "quoteId": "quote_abc",
                "idempotencyKey": "job-1-step-1",
                "payload": {"body": {"text": "关于坚持"}},
                "responseMode": "sync",
            },
            "timeout": 9,
        },
    ]
    assert get_calls == [
        {
            "url": "http://127.0.0.1:8000/api/v1/agent/invocations/inv_abc",
            "headers": {
                "Content-Type": "application/json",
                "X-Credential": "agt_test",
            },
            "timeout": 9,
        }
    ]


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


def test_ts_style_alias_methods_delegate_to_python_runtime_client(monkeypatch):
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
        "create_quote",
        lambda *args, **kwargs: "quote-object",
    )
    monkeypatch.setattr(
        client,
        "invoke_service",
        lambda *args, **kwargs: "invocation-object",
    )
    monkeypatch.setattr(
        client,
        "get_invocation_receipt",
        lambda invocation_id: {"invocationId": invocation_id},
    )

    assert client.discover(limit=20) == ["svc-1", "svc-2"]
    assert client.search("quotes", limit=20) == ["svc-1", "svc-2"]
    assert client.quote("svc_quotes") == "quote-object"
    assert client.invoke("svc_quotes", {"prompt": "hi"}) == "invocation-object"
    assert client.get_invocation("inv-123") == {"invocationId": "inv-123"}
