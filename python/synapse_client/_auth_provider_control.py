from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from .exceptions import AuthenticationError
from .models import (
    IssueProviderSecretResult,
    ProviderEarningsSummary,
    ProviderRegistrationGuide,
    ProviderSecret,
    ProviderSecretDeleteResult,
    ProviderService,
    ProviderServiceDeleteResult,
    ProviderServiceHealthHistory,
    ProviderServicePingResult,
    ProviderServiceRegistrationResult,
    ProviderServiceStatus,
    ProviderServiceUpdateResult,
    ProviderWithdrawalCapability,
    ProviderWithdrawalIntentResult,
    ProviderWithdrawalList,
    ServiceManifestDraft,
)


class ProviderControlMixin:
    def issue_provider_secret(self, **options: Any) -> IssueProviderSecretResult:
        aliases = {
            "max_calls": "maxCalls",
            "credit_limit": "creditLimit",
            "reset_interval": "resetInterval",
            "expires_in_sec": "expiresInSec",
        }
        for source, target in aliases.items():
            if source in options and target not in options:
                options[target] = options[source]
        body: Dict[str, Any] = {}
        for key in ("name", "maxCalls", "creditLimit", "resetInterval", "rpm", "expiresInSec", "expiration"):
            value = options.get(key)
            if value is not None:
                body[key] = value

        payload = self._request(
            "POST",
            "/api/v1/secrets/provider/issue",
            headers=self._authorized_headers(),
            json_body=body,
        )
        secret_payload = payload.get("secret")
        if not isinstance(secret_payload, dict):
            secret_payload = {}
        if not secret_payload:
            raise AuthenticationError(f"Provider secret payload missing: {payload}")
        return IssueProviderSecretResult(secret=ProviderSecret.model_validate(secret_payload))

    def list_provider_secrets(self) -> list[ProviderSecret]:
        payload = self._request(
            "GET",
            "/api/v1/secrets/provider/list",
            headers=self._authorized_headers(),
        )
        secrets = payload.get("secrets")
        if not isinstance(secrets, list):
            return []
        return [ProviderSecret.model_validate(item) for item in secrets if isinstance(item, dict)]

    def delete_provider_secret(self, secret_id: str) -> ProviderSecretDeleteResult:
        """Delete a provider control-plane secret."""
        secret_id = self._require_value(secret_id, "secret_id")
        payload = self._request(
            "DELETE",
            f"/api/v1/secrets/provider/{secret_id}",
            headers=self._authorized_headers(),
        )
        return ProviderSecretDeleteResult.model_validate(payload)

    def register_provider_service(
        self,
        *,
        service_name: str,
        endpoint_url: str,
        base_price_usdc: Optional[float | str] = None,
        description_for_model: str,
        service_kind: str = "api",
        price_model: Optional[str] = None,
        input_price_per_1m_tokens_usdc: Optional[float | str] = None,
        output_price_per_1m_tokens_usdc: Optional[float | str] = None,
        default_max_output_tokens: Optional[int] = None,
        hold_buffer_multiplier: Optional[float | str] = None,
        max_auto_hold_usdc: Optional[float | str] = None,
        service_id: Optional[str] = None,
        provider_display_name: Optional[str] = None,
        payout_address: Optional[str] = None,
        chain_id: int = 31337,
        settlement_currency: str = "USDC",
        tags: Optional[list[str]] = None,
        status: str = "active",
        is_active: bool = True,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        endpoint_method: str = "POST",
        health_path: str = "/health",
        health_method: str = "GET",
        health_timeout_ms: int = 3000,
        request_timeout_ms: int = 15000,
        governance_note: Optional[str] = None,
    ) -> ProviderServiceRegistrationResult:
        service_values = self._provider_service_values(
            service_name=service_name,
            endpoint_url=endpoint_url,
            description_for_model=description_for_model,
            service_id=service_id,
        )
        body = self._provider_service_body(
            service_values=service_values,
            base_price_usdc=base_price_usdc,
            service_kind=service_kind,
            price_model=price_model,
            input_price_per_1m_tokens_usdc=input_price_per_1m_tokens_usdc,
            output_price_per_1m_tokens_usdc=output_price_per_1m_tokens_usdc,
            default_max_output_tokens=default_max_output_tokens,
            hold_buffer_multiplier=hold_buffer_multiplier,
            max_auto_hold_usdc=max_auto_hold_usdc,
            provider_display_name=provider_display_name,
            payout_address=payout_address,
            chain_id=chain_id,
            settlement_currency=settlement_currency,
            tags=tags,
            status=status,
            is_active=is_active,
            input_schema=input_schema,
            output_schema=output_schema,
            endpoint_method=endpoint_method,
            health_path=health_path,
            health_method=health_method,
            health_timeout_ms=health_timeout_ms,
            request_timeout_ms=request_timeout_ms,
            governance_note=governance_note,
        )
        payload = self._request(
            "POST",
            "/api/v1/services",
            headers=self._authorized_headers(),
            json_body=body,
        )
        return ProviderServiceRegistrationResult.model_validate(payload)

    def _provider_service_values(
        self,
        *,
        service_name: str,
        endpoint_url: str,
        description_for_model: str,
        service_id: Optional[str],
    ) -> Dict[str, str]:
        name = str(service_name or "").strip()
        endpoint = str(endpoint_url or "").strip()
        summary = str(description_for_model or "").strip()
        if not name:
            raise ValueError("service_name is required")
        if not endpoint:
            raise ValueError("endpoint_url is required")
        if not summary:
            raise ValueError("description_for_model is required")
        resolved_service_id = str(service_id or "").strip() or self._default_service_id(name)
        return {"service_id": resolved_service_id, "name": name, "endpoint": endpoint, "summary": summary}

    def _provider_service_body(
        self,
        *,
        service_values: Dict[str, str],
        base_price_usdc: Optional[float | str],
        service_kind: str,
        price_model: Optional[str],
        input_price_per_1m_tokens_usdc: Optional[float | str],
        output_price_per_1m_tokens_usdc: Optional[float | str],
        default_max_output_tokens: Optional[int],
        hold_buffer_multiplier: Optional[float | str],
        max_auto_hold_usdc: Optional[float | str],
        provider_display_name: Optional[str],
        payout_address: Optional[str],
        chain_id: int,
        settlement_currency: str,
        tags: Optional[list[str]],
        status: str,
        is_active: bool,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        endpoint_method: str,
        health_path: str,
        health_method: str,
        health_timeout_ms: int,
        request_timeout_ms: int,
        governance_note: Optional[str],
    ) -> Dict[str, Any]:
        service_id = service_values["service_id"]
        resolved_price_model = price_model or ("token_metered" if service_kind == "llm" else "fixed")
        return {
            "serviceId": service_id,
            "agentToolName": service_id,
            "serviceName": service_values["name"],
            "serviceKind": service_kind,
            "priceModel": resolved_price_model,
            "role": "Provider",
            "status": status,
            "isActive": is_active,
            "pricing": self._provider_pricing(
                price_model=resolved_price_model,
                base_price_usdc=base_price_usdc,
                input_price_per_1m_tokens_usdc=input_price_per_1m_tokens_usdc,
                output_price_per_1m_tokens_usdc=output_price_per_1m_tokens_usdc,
                default_max_output_tokens=default_max_output_tokens,
                hold_buffer_multiplier=hold_buffer_multiplier,
                max_auto_hold_usdc=max_auto_hold_usdc,
            ),
            "summary": service_values["summary"],
            "tags": tags or [],
            "auth": {"type": "gateway_signed"},
            "invoke": self._provider_invoke_config(
                endpoint_url=service_values["endpoint"],
                endpoint_method=endpoint_method,
                request_timeout_ms=request_timeout_ms,
                input_schema=input_schema,
                output_schema=output_schema,
            ),
            "healthCheck": self._provider_health_check(health_path, health_method, health_timeout_ms),
            "providerProfile": self._provider_profile(provider_display_name, service_values["name"]),
            "payoutAccount": self._provider_payout_account(payout_address, chain_id, settlement_currency),
            "governance": {
                "termsAccepted": True,
                "riskAcknowledged": True,
                "note": governance_note,
            },
        }

    def register_llm_service(self, **options: Any) -> ProviderServiceRegistrationResult:
        """Register a token-metered LLM Provider service."""
        options["service_kind"] = "llm"
        options["price_model"] = "token_metered"
        return self.register_provider_service(**options)

    @staticmethod
    def _provider_pricing(
        *,
        price_model: str,
        base_price_usdc: Optional[float | str],
        input_price_per_1m_tokens_usdc: Optional[float | str],
        output_price_per_1m_tokens_usdc: Optional[float | str],
        default_max_output_tokens: Optional[int],
        hold_buffer_multiplier: Optional[float | str],
        max_auto_hold_usdc: Optional[float | str],
    ) -> Dict[str, Any]:
        if price_model == "token_metered":
            if input_price_per_1m_tokens_usdc is None:
                raise ValueError("input_price_per_1m_tokens_usdc is required")
            if output_price_per_1m_tokens_usdc is None:
                raise ValueError("output_price_per_1m_tokens_usdc is required")
            pricing: Dict[str, Any] = {
                "priceModel": "token_metered",
                "inputPricePer1MTokensUsdc": str(input_price_per_1m_tokens_usdc),
                "outputPricePer1MTokensUsdc": str(output_price_per_1m_tokens_usdc),
                "currency": "USDC",
            }
            if default_max_output_tokens is not None:
                pricing["defaultMaxOutputTokens"] = default_max_output_tokens
            if hold_buffer_multiplier is not None:
                pricing["holdBufferMultiplier"] = hold_buffer_multiplier
            if max_auto_hold_usdc is not None:
                pricing["maxAutoHoldUsdc"] = str(max_auto_hold_usdc)
            return pricing
        if base_price_usdc is None:
            raise ValueError("base_price_usdc is required")
        return {"amount": str(base_price_usdc), "currency": "USDC"}

    @staticmethod
    def _provider_invoke_config(
        *,
        endpoint_url: str,
        endpoint_method: str,
        request_timeout_ms: int,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "method": endpoint_method,
            "targets": [{"url": endpoint_url}],
            "timeoutMs": request_timeout_ms,
            "request": {"body": input_schema or {"type": "object", "properties": {}, "required": []}},
            "response": {"body": output_schema or {"type": "object", "properties": {}}},
        }

    @staticmethod
    def _provider_health_check(health_path: str, health_method: str, health_timeout_ms: int) -> Dict[str, Any]:
        return {
            "path": health_path,
            "method": health_method,
            "timeoutMs": health_timeout_ms,
            "successCodes": [200],
            "healthyThreshold": 1,
            "unhealthyThreshold": 3,
        }

    @staticmethod
    def _provider_profile(provider_display_name: Optional[str], service_name: str) -> Dict[str, str]:
        return {"displayName": str(provider_display_name or service_name).strip() or service_name}

    def _provider_payout_account(
        self,
        payout_address: Optional[str],
        chain_id: int,
        settlement_currency: str,
    ) -> Dict[str, Any]:
        return {
            "payoutAddress": str(payout_address or self.wallet_address).strip() or self.wallet_address,
            "chainId": chain_id,
            "settlementCurrency": settlement_currency,
        }

    def list_provider_services(self) -> list[ProviderService]:
        payload = self._request(
            "GET",
            "/api/v1/services",
            headers=self._authorized_headers(),
        )
        services = payload.get("services")
        if not isinstance(services, list):
            return []
        return [ProviderService.model_validate(item) for item in services if isinstance(item, dict)]

    def get_registration_guide(self) -> ProviderRegistrationGuide:
        """Fetch the provider registration guide from the gateway control plane."""
        payload = self._request(
            "GET",
            "/api/v1/services/registration-guide",
            headers=self._authorized_headers(),
        )
        return ProviderRegistrationGuide.model_validate(payload)

    def parse_curl_to_service_manifest(self, curl_command: str) -> ServiceManifestDraft:
        """Convert a curl command into a provider service manifest draft."""
        curl_command = self._require_value(curl_command, "curl_command")
        payload = self._request(
            "POST",
            "/api/v1/services/parse-curl",
            headers=self._authorized_headers(),
            json_body={"curlCommand": curl_command},
        )
        return ServiceManifestDraft.model_validate(payload)

    def update_provider_service(self, service_record_id: str, patch: Dict[str, Any]) -> ProviderServiceUpdateResult:
        """Patch a provider service registration by gateway record ID."""
        service_record_id = self._require_value(service_record_id, "service_record_id")
        payload = self._request(
            "PUT",
            f"/api/v1/services/{service_record_id}",
            headers=self._authorized_headers(),
            json_body=patch or {},
        )
        return ProviderServiceUpdateResult.model_validate(payload)

    def delete_provider_service(self, service_record_id: str) -> ProviderServiceDeleteResult:
        """Delete a provider service registration by gateway record ID."""
        service_record_id = self._require_value(service_record_id, "service_record_id")
        payload = self._request(
            "DELETE",
            f"/api/v1/services/{service_record_id}",
            headers=self._authorized_headers(),
        )
        return ProviderServiceDeleteResult.model_validate(payload)

    def ping_provider_service(self, service_record_id: str) -> ProviderServicePingResult:
        """Force a provider service health ping."""
        service_record_id = self._require_value(service_record_id, "service_record_id")
        payload = self._request(
            "POST",
            f"/api/v1/services/{service_record_id}/ping",
            headers=self._authorized_headers(),
        )
        return ProviderServicePingResult.model_validate(payload)

    def get_provider_service_health_history(
        self, service_record_id: str, *, limit: int = 100
    ) -> ProviderServiceHealthHistory:
        """Fetch health history for a provider service."""
        service_record_id = self._require_value(service_record_id, "service_record_id")
        payload = self._request(
            "GET",
            self._query_path(f"/api/v1/services/{service_record_id}/health/history", {"limitPerTarget": limit}),
            headers=self._authorized_headers(),
        )
        return ProviderServiceHealthHistory.model_validate(payload)

    def get_provider_earnings_summary(self) -> ProviderEarningsSummary:
        """Return provider earnings summary for the authenticated owner."""
        payload = self._request(
            "GET",
            "/api/v1/providers/earnings/summary",
            headers=self._authorized_headers(),
        )
        return ProviderEarningsSummary.model_validate(payload)

    def get_provider_withdrawal_capability(self) -> ProviderWithdrawalCapability:
        """Return whether provider withdrawals are currently available."""
        payload = self._request(
            "GET",
            "/api/v1/providers/withdrawals/capability",
            headers=self._authorized_headers(),
        )
        return ProviderWithdrawalCapability.model_validate(payload)

    def create_provider_withdrawal_intent(
        self,
        amount_usdc: float,
        *,
        idempotency_key: Optional[str] = None,
        destination_address: Optional[str] = None,
    ) -> ProviderWithdrawalIntentResult:
        """Create a provider withdrawal intent. This does not auto-submit funds on-chain."""
        body: Dict[str, Any] = {"amountUsdc": amount_usdc}
        if destination_address:
            body["destinationAddress"] = destination_address
        payload = self._request(
            "POST",
            "/api/v1/providers/withdrawals/intent",
            headers={
                **self._authorized_headers(),
                "X-Idempotency-Key": idempotency_key or f"provider-withdraw-{uuid4().hex}",
            },
            json_body=body,
        )
        return ProviderWithdrawalIntentResult.model_validate(payload)

    def list_provider_withdrawals(self, *, limit: int = 100) -> ProviderWithdrawalList:
        """List provider withdrawal records."""
        payload = self._request(
            "GET",
            self._query_path("/api/v1/providers/withdrawals", {"limit": limit}),
            headers=self._authorized_headers(),
        )
        return ProviderWithdrawalList.model_validate(payload)

    def get_provider_service(self, service_id: str) -> ProviderService:
        resolved_service_id = str(service_id or "").strip()
        if not resolved_service_id:
            raise ValueError("service_id is required")
        services = self.list_provider_services()
        for service in services:
            if service.service_id == resolved_service_id:
                return service
        raise AuthenticationError(f"Provider service not found: {resolved_service_id}")

    def get_provider_service_status(self, service_id: str) -> ProviderServiceStatus:
        service = self.get_provider_service(service_id)
        return ProviderServiceStatus(
            serviceId=service.service_id,
            lifecycleStatus=service.status,
            runtimeAvailable=service.runtime_available,
            health=service.health.model_dump(by_alias=True),
        )
