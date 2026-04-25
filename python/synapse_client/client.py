import os
import time
from typing import Any, Dict, Optional
from uuid import uuid4

import requests

from .config import resolve_gateway_url
from .exceptions import (
    AuthenticationError,
    BudgetExceededError,
    DiscoveryError,
    InsufficientFundsError,
    InvokeError,
    PriceMismatchError,
    QuoteError,
    SynapseClientError,
    TimeoutError,
)
from .models import (
    DiscoveryResponse,
    InvocationResponse,
    RuntimePayload,
)


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "SETTLED"}
DEPRECATED_QUOTE_FLOW_MESSAGE = (
    "The current Synapse gateway uses price-asserted single-call invoke. "
    "Use discover()/search() to read the live service price, then call "
    "invoke(service_id, payload, cost_usdc=...)."
)


class SynapseClient:
    """Official Python client for Synapse agent discovery, invoke, and receipt APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        gateway_url: Optional[str] = None,
        environment: Optional[str] = None,
        timeout_sec: int = 30,
    ):
        # Resolve api_key from arguments or environment variable
        self.api_key = (api_key or os.getenv("SYNAPSE_API_KEY", "")).strip()
        self.gateway_url = resolve_gateway_url(environment=environment, gateway_url=gateway_url)
        self.timeout_sec = timeout_sec

        if not self.api_key:
            raise ValueError("api_key is required. Pass it via init or set SYNAPSE_API_KEY env var.")

    def _headers(self, request_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Credential": self.api_key,
        }
        if request_id:
            headers["X-Request-Id"] = request_id
        return headers

    @staticmethod
    def _response_payload(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    @classmethod
    def _error_message(cls, response: requests.Response, fallback: str) -> str:
        payload = cls._response_payload(response)
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("code") or fallback)
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        return response.text.strip() or fallback

    @classmethod
    def _error_code(cls, response: requests.Response) -> str:
        payload = cls._response_payload(response)
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("code") or "")
        return ""

    def _raise_for_error(self, response: requests.Response, default_error: Exception) -> None:
        if response.ok:
            return

        error_code = self._error_code(response)
        message = self._error_message(response, str(default_error))

        if response.status_code == 401:
            raise AuthenticationError(message)

        if response.status_code == 402:
            if error_code in {"BUDGET_EXHAUSTED", "CREDENTIAL_CREDIT_LIMIT_EXCEEDED"}:
                raise InsufficientFundsError(message)
            raise BudgetExceededError(message)

        if response.status_code == 422 and error_code == "PRICE_MISMATCH":
            payload = self._response_payload(response)
            detail = payload.get("detail") or {}
            if isinstance(detail, dict):
                raise PriceMismatchError(
                    message,
                    expected_price_usdc=float(detail.get("expectedPriceUsdc") or 0),
                    current_price_usdc=float(detail.get("currentPriceUsdc") or 0),
                )
            raise PriceMismatchError(message, expected_price_usdc=0, current_price_usdc=0)

        if isinstance(default_error, DiscoveryError):
            raise DiscoveryError(message)
        raise InvokeError(message)

    def search_services(
        self,
        *,
        query: Optional[str] = None,
        tags: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 10,
        sort: str = "best_match",
        request_id: Optional[str] = None,
    ) -> DiscoveryResponse:
        """Search discoverable services through the agent-facing discovery contract."""
        payload: Dict[str, Any] = {
            "tags": tags or [],
            "page": page,
            "pageSize": page_size,
            "sort": sort,
        }
        if query:
            payload["query"] = query

        response = requests.post(
            f"{self.gateway_url}/api/v1/agent/discovery/search",
            headers=self._headers(request_id=request_id),
            json=payload,
            timeout=self.timeout_sec,
        )
        self._raise_for_error(response, DiscoveryError("service discovery failed"))
        return DiscoveryResponse(**self._response_payload(response))

    def discover_services(
        self,
        intent: Optional[str] = None,
        *,
        tags: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 10,
        sort: str = "best_match",
        request_id: Optional[str] = None,
    ) -> DiscoveryResponse:
        """Backward-compatible alias for agent discovery search."""
        return self.search_services(
            query=intent,
            tags=tags,
            page=page,
            page_size=page_size,
            sort=sort,
            request_id=request_id,
        )

    def discover(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        tags: Optional[list[str]] = None,
        request_id: Optional[str] = None,
    ) -> list:
        page_size = max(1, limit)
        page = max(1, (offset // page_size) + 1)
        response = self.search_services(
            tags=tags,
            page=page,
            page_size=page_size,
            request_id=request_id,
        )
        return response.services

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        tags: Optional[list[str]] = None,
        request_id: Optional[str] = None,
    ) -> list:
        page_size = max(1, limit)
        page = max(1, (offset // page_size) + 1)
        response = self.search_services(
            query=query,
            tags=tags,
            page=page,
            page_size=page_size,
            request_id=request_id,
        )
        return response.services

    def create_quote(
        self,
        service_id: str,
        *,
        input_preview: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> "QuoteResponse":
        """Deprecated: the current gateway no longer exposes quote as a public SDK step."""
        raise QuoteError(DEPRECATED_QUOTE_FLOW_MESSAGE)

    # TS-style alias
    def quote(
        self,
        service_id: str,
        *,
        input_preview: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> "QuoteResponse":
        """Alias for create_quote()."""
        return self.create_quote(
            service_id,
            input_preview=input_preview,
            payload=payload,
            request_id=request_id,
        )

    def create_invocation(
        self,
        quote_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        idempotency_key: Optional[str] = None,
        response_mode: str = "sync",
        request_id: Optional[str] = None,
        poll_timeout_sec: int = 90,
    ) -> InvocationResponse:
        """Deprecated: the current gateway no longer accepts quoteId-based invocation."""
        raise InvokeError(DEPRECATED_QUOTE_FLOW_MESSAGE)

    def invoke_service(
        self,
        service_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        idempotency_key: Optional[str] = None,
        max_wait_sec: int = 90,
        request_id: Optional[str] = None,
    ) -> InvocationResponse:
        """Deprecated alias for the removed quote-first invocation flow."""
        raise SynapseClientError(DEPRECATED_QUOTE_FLOW_MESSAGE)

    def get_invocation_receipt(self, invocation_id: str) -> InvocationResponse:
        """Fetch the latest state for an invocation."""
        if not invocation_id or not invocation_id.strip():
            raise ValueError("invocation_id is required")

        response = requests.get(
            f"{self.gateway_url}/api/v1/agent/invocations/{invocation_id.strip()}",
            headers=self._headers(),
            timeout=self.timeout_sec,
        )
        self._raise_for_error(response, InvokeError("invocation receipt lookup failed"))
        return InvocationResponse(**self._response_payload(response))

    def get_invocation(self, invocation_id: str) -> InvocationResponse:
        return self.get_invocation_receipt(invocation_id)

    def wait_for_invocation(
        self,
        invocation_id: str,
        *,
        max_wait_sec: int = 90,
        poll_interval_sec: int = 1,
    ) -> InvocationResponse:
        """Poll receipt state until the invocation reaches a terminal status."""
        started = time.time()
        while True:
            receipt = self.get_invocation_receipt(invocation_id)
            if receipt.status in TERMINAL_STATUSES:
                return receipt
            if time.time() - started + max(1, poll_interval_sec) > max_wait_sec:
                raise TimeoutError("Synapse invocation pending timeout.")
            time.sleep(max(1, poll_interval_sec))

    def invoke(
        self,
        service_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        cost_usdc: float,
        idempotency_key: Optional[str] = None,
        response_mode: str = "sync",
        poll_timeout_sec: int = 90,
        request_id: Optional[str] = None,
    ) -> InvocationResponse:
        """Invoke a service with price assertion.

        Pass ``cost_usdc`` — the price the agent observed in discovery.
        Gateway returns 422 ``PRICE_MISMATCH`` (raises ``PriceMismatchError``) if
        the live price has changed — re-discover and retry.
        """
        if not service_id or not service_id.strip():
            raise ValueError("service_id is required")

        invocation_key = (idempotency_key or f"invoke-{uuid4().hex}").strip()
        runtime_payload = RuntimePayload(body=payload or {})
        body = {
            "serviceId": service_id.strip(),
            "idempotencyKey": invocation_key,
            "costUsdc": round(float(cost_usdc), 6),
            "payload": runtime_payload.model_dump(by_alias=True),
            "responseMode": response_mode,
        }
        response = requests.post(
            f"{self.gateway_url}/api/v1/agent/invoke",
            headers=self._headers(request_id=request_id),
            json=body,
            timeout=self.timeout_sec,
        )
        self._raise_for_error(response, InvokeError("service invocation failed"))
        invocation = InvocationResponse(**self._response_payload(response))

        if invocation.status in TERMINAL_STATUSES:
            return invocation
        return self.wait_for_invocation(invocation.invocation_id, max_wait_sec=poll_timeout_sec)


class AgentWallet(SynapseClient):
    """Convenience wrapper — the 3-line DX entry point for agent developers.

    Usage::

        from synapse_client import AgentWallet
        wallet = AgentWallet.connect(budget=5.0)         # Line 1
        svc = wallet.search_services("market data").services[0]  # Line 2
        result = wallet.invoke(svc.service_id, payload={}, cost_usdc=float(svc.price_usdc))  # Line 3
        print(result.status, result.charged_usdc)

    The ``budget`` parameter enforces a spend ceiling tracked client-side.
    When cumulative ``charged_usdc`` would exceed it, an ``InsufficientFundsError``
    is raised before the HTTP call is made.
    """

    def __init__(self, budget: float = 5.0, **kwargs):
        super().__init__(**kwargs)
        self._budget_usdc = float(budget)
        self._spent_usdc: float = 0.0

    @classmethod
    def connect(
        cls,
        budget: float = 5.0,
        api_key: Optional[str] = None,
        gateway_url: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> "AgentWallet":
        """Factory method — create and validate an AgentWallet in one call."""
        api_key = api_key or os.getenv("SYNAPSE_API_KEY", "")
        return cls(budget=budget, api_key=api_key, gateway_url=gateway_url, environment=environment)

    @property
    def budget_usdc(self) -> float:
        return self._budget_usdc

    @property
    def spent_usdc(self) -> float:
        return self._spent_usdc

    @property
    def remaining_usdc(self) -> float:
        return round(self._budget_usdc - self._spent_usdc, 6)

    def invoke(self, service_id: str, *, payload: Optional[Dict[str, Any]] = None, cost_usdc: float = 0.0, **kwargs) -> "InvocationResponse":  # type: ignore[override]
        """Invoke a service and track spend against the budget ceiling."""
        cost = float(cost_usdc)
        if self._spent_usdc + cost > self._budget_usdc:
            raise InsufficientFundsError(
                f"Budget exceeded: ${self._spent_usdc:.4f} spent + ${cost:.4f} cost > ${self._budget_usdc:.4f} budget"
            )
        result = super().invoke(service_id, payload=payload, cost_usdc=cost_usdc, **kwargs)
        self._spent_usdc = round(self._spent_usdc + float(result.charged_usdc), 6)
        return result
