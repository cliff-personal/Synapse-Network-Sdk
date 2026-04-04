import os
import time
from typing import Any, Dict, Optional
from uuid import uuid4

import requests

from .exceptions import (
    AuthenticationError,
    BudgetExceededError,
    DiscoveryError,
    InsufficientFundsError,
    InvokeError,
    PriceMismatchError,
    TimeoutError,
)
from .models import (
    DiscoveryResponse,
    InvocationResponse,
    RuntimePayload,
)


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "SETTLED"}


class SynapseClient:
    """Official Python client for Synapse agent discovery, quote, invoke, and receipt APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        gateway_url: str = "http://127.0.0.1:8000",
        timeout_sec: int = 30,
    ):
        # Resolve api_key from arguments or environment variable
        self.api_key = (api_key or os.getenv("SYNAPSE_API_KEY", "")).strip()
        self.gateway_url = gateway_url.rstrip("/")
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
