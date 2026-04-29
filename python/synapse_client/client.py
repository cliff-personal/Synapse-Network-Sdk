import os
import time
from typing import Any, Dict, Optional, Union
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
    DiscoveryEmptyExplanation,
    DiscoveryResponse,
    GatewayHealthResult,
    InvocationResponse,
    QuoteResponse,
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
        self.api_key = str(api_key or os.getenv("SYNAPSE_API_KEY", "") or "").strip()
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
            raise self._payment_error(error_code, message)

        if response.status_code == 422 and error_code == "PRICE_MISMATCH":
            raise self._price_mismatch_error(response, message)

        if isinstance(default_error, DiscoveryError):
            raise DiscoveryError(message)
        raise InvokeError(message)

    @staticmethod
    def _payment_error(error_code: str, message: str) -> Exception:
        if error_code in {"BUDGET_EXHAUSTED", "CREDENTIAL_CREDIT_LIMIT_EXCEEDED"}:
            return InsufficientFundsError(message)
        return BudgetExceededError(message)

    @classmethod
    def _price_mismatch_error(cls, response: requests.Response, message: str) -> PriceMismatchError:
        detail = cls._response_payload(response).get("detail") or {}
        if not isinstance(detail, dict):
            return PriceMismatchError(message, expected_price_usdc=0, current_price_usdc=0)
        return PriceMismatchError(
            message,
            expected_price_usdc=float(detail.get("expectedPriceUsdc") or 0),
            current_price_usdc=float(detail.get("currentPriceUsdc") or 0),
        )

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

    def check_gateway_health(self) -> GatewayHealthResult:
        """Check the public gateway health endpoint without consuming agent budget."""
        response = requests.get(
            f"{self.gateway_url}/health",
            timeout=self.timeout_sec,
        )
        self._raise_for_error(response, InvokeError("gateway health check failed"))
        return GatewayHealthResult(**self._response_payload(response))

    @staticmethod
    def explain_discovery_empty_result(
        *,
        query: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> DiscoveryEmptyExplanation:
        """Return agent-friendly diagnostics for an empty discovery result."""
        reasons = [
            "No provider service matched the current discovery filters.",
            "The matching provider may be inactive, unhealthy, or not yet registered in this environment.",
            "The agent credential may target a different environment than the provider service.",
        ]
        suggestions = [
            "Retry with a broader query and no tags.",
            "Confirm SYNAPSE_ENV / gateway_url matches the provider registration environment.",
            "Ask the provider owner to verify service status and health history.",
        ]
        return DiscoveryEmptyExplanation(
            query=query or "",
            tags=tags or [],
            possibleReasons=reasons,
            suggestions=suggestions,
        )

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
        cost_usdc: Optional[Union[float, str]] = None,
        max_cost_usdc: Optional[Union[float, str]] = None,
        idempotency_key: Optional[str] = None,
        response_mode: str = "sync",
        poll_timeout_sec: int = 90,
        request_id: Optional[str] = None,
        _allow_missing_cost_usdc: bool = False,
    ) -> InvocationResponse:
        """Invoke a service with price assertion.

        Pass ``cost_usdc`` — the price the agent observed in discovery.
        Gateway returns 422 ``PRICE_MISMATCH`` (raises ``PriceMismatchError``) if
        the live price has changed — re-discover and retry.
        """
        if not service_id or not service_id.strip():
            raise ValueError("service_id is required")
        if cost_usdc is None and not _allow_missing_cost_usdc:
            raise ValueError("cost_usdc is required for fixed-price API services. Use invoke_llm() for LLM services.")

        invocation_key = (idempotency_key or f"invoke-{uuid4().hex}").strip()
        runtime_payload = RuntimePayload(body=payload or {})
        body = {
            "serviceId": service_id.strip(),
            "idempotencyKey": invocation_key,
            "payload": runtime_payload.model_dump(by_alias=True),
            "responseMode": response_mode,
        }
        if cost_usdc is not None:
            body["costUsdc"] = round(float(cost_usdc), 6)
        if max_cost_usdc is not None:
            body["maxCostUsdc"] = str(max_cost_usdc)
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

    def invoke_llm(
        self,
        service_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        max_cost_usdc: Optional[Union[float, str]] = None,
        idempotency_key: Optional[str] = None,
        poll_timeout_sec: int = 90,
        request_id: Optional[str] = None,
    ) -> InvocationResponse:
        """Invoke a token-metered LLM service.

        ``cost_usdc`` is intentionally not used for LLM services. If
        ``max_cost_usdc`` is omitted, Gateway performs automatic
        pre-authorization and only captures final Provider-reported usage.
        """
        runtime_payload = payload or {}
        if runtime_payload.get("stream") is True:
            raise InvokeError("LLM_STREAMING_NOT_SUPPORTED: stream=True is not supported for token-metered billing.")
        return self.invoke(
            service_id,
            runtime_payload,
            max_cost_usdc=max_cost_usdc,
            idempotency_key=idempotency_key,
            response_mode="sync",
            poll_timeout_sec=poll_timeout_sec,
            request_id=request_id,
            _allow_missing_cost_usdc=True,
        )

    def invoke_with_rediscovery(
        self,
        service_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        query: Optional[str] = None,
        tags: Optional[list[str]] = None,
        cost_usdc: float,
        max_rediscovery_retries: int = 1,
        idempotency_key: Optional[str] = None,
        response_mode: str = "sync",
        poll_timeout_sec: int = 90,
        request_id: Optional[str] = None,
    ) -> InvocationResponse:
        """Invoke once, then handle PRICE_MISMATCH by re-discovering and retrying once by default."""
        try:
            return self.invoke(
                service_id,
                payload,
                cost_usdc=cost_usdc,
                idempotency_key=idempotency_key,
                response_mode=response_mode,
                poll_timeout_sec=poll_timeout_sec,
                request_id=request_id,
            )
        except PriceMismatchError as exc:
            if max_rediscovery_retries <= 0:
                raise

            live_price = self._rediscovered_price(
                service_id,
                fallback_price=float(exc.current_price_usdc or 0),
                query=query,
                tags=tags,
                request_id=request_id,
            )
            if live_price <= 0:
                raise

            return self.invoke(
                service_id,
                payload,
                cost_usdc=live_price,
                idempotency_key=idempotency_key,
                response_mode=response_mode,
                poll_timeout_sec=poll_timeout_sec,
                request_id=request_id,
            )

    def _rediscovered_price(
        self,
        service_id: str,
        *,
        fallback_price: float,
        query: Optional[str],
        tags: Optional[list[str]],
        request_id: Optional[str],
    ) -> float:
        services = self.search(
            query or service_id,
            limit=10,
            tags=tags,
            request_id=request_id,
        )
        for service in services:
            if getattr(service, "service_id", "") == service_id or getattr(service, "serviceId", "") == service_id:
                return float(service.price_usdc) if service.price_usdc is not None else fallback_price
        return fallback_price


from .wallet import AgentWallet  # noqa: E402, F401
