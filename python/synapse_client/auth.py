from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

import requests

from .exceptions import AuthenticationError
from .models import (
    AgentCredential,
    BalanceSummary,
    ChallengeResponse,
    DepositConfirmResult,
    DepositIntentResult,
    IssueCredentialResult,
    IssueProviderSecretResult,
    ProviderSecret,
    ProviderService,
    ProviderServiceRegistrationResult,
    ProviderServiceStatus,
    TokenResponse,
)

SignerFn = Callable[[str], str]


class SynapseAuth:
    """Wallet-based owner auth + credential + balance management for Synapse."""

    def __init__(
        self,
        *,
        wallet_address: str,
        signer: SignerFn,
        gateway_url: str = "http://127.0.0.1:8000",
        timeout_sec: int = 30,
    ) -> None:
        normalized = str(wallet_address or "").strip().lower()
        if not normalized:
            raise ValueError("wallet_address is required")

        self.wallet_address = normalized
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self._signer = signer
        self._token: str | None = None
        self._token_expires_at: float = 0

    @classmethod
    def from_private_key(
        cls,
        private_key: str,
        *,
        gateway_url: str = "http://127.0.0.1:8000",
        timeout_sec: int = 30,
    ) -> "SynapseAuth":
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
        except ImportError as exc:
            raise ImportError(
                "SynapseAuth.from_private_key requires eth-account. Install with `pip install -e \".[dev]\"`."
            ) from exc

        account = Account.from_key(private_key)

        def signer(message: str) -> str:
            signed = Account.sign_message(
                encode_defunct(text=message),
                private_key=private_key,
            )
            return signed.signature.hex()

        return cls(
            wallet_address=account.address,
            signer=signer,
            gateway_url=gateway_url,
            timeout_sec=timeout_sec,
        )

    def _authorized_headers(self) -> Dict[str, str]:
        token = self.get_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    @staticmethod
    def _default_service_id(service_name: str) -> str:
        normalized = (
            str(service_name or "")
            .strip()
            .lower()
            .replace(" ", "_")
        )
        chars = []
        previous_is_sep = False
        for char in normalized:
            if char.isalnum():
                chars.append(char)
                previous_is_sep = False
                continue
            if char in {"-", "_"} and not previous_is_sep:
                chars.append("_")
                previous_is_sep = True
        result = "".join(chars).strip("_")
        while "__" in result:
            result = result.replace("__", "_")
        return result or f"service_{uuid4().hex[:8]}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = requests.request(
            method,
            f"{self.gateway_url}{path}",
            headers={
                "Content-Type": "application/json",
                **(headers or {}),
            },
            json=json_body,
            timeout=self.timeout_sec,
        )

        try:
            data = response.json()
            payload = data if isinstance(data, dict) else {}
        except ValueError:
            payload = {}

        if not response.ok:
            detail = payload.get("detail")
            if isinstance(detail, dict):
                message = str(detail.get("message") or detail.get("code") or response.text)
            elif isinstance(detail, str) and detail.strip():
                message = detail.strip()
            else:
                message = response.text.strip() or f"HTTP {response.status_code}"
            raise AuthenticationError(message)
        return payload

    def authenticate(self, force_refresh: bool = False) -> str:
        now = time.time()
        if (
            not force_refresh
            and self._token
            and now < max(0, self._token_expires_at - 30)
        ):
            return self._token

        challenge_payload = self._request(
            "GET",
            f"/api/v1/auth/challenge?address={self.wallet_address}",
        )
        challenge = ChallengeResponse.model_validate(challenge_payload)
        if not challenge.success or not challenge.challenge:
            raise AuthenticationError("Challenge request did not return a usable challenge")

        signature = self._signer(challenge.challenge)
        token_payload = self._request(
            "POST",
            "/api/v1/auth/verify",
            json_body={
                "wallet_address": self.wallet_address,
                "message": challenge.challenge,
                "signature": signature,
            },
        )
        token_response = TokenResponse.model_validate(token_payload)
        if not token_response.success or not token_response.access_token:
            raise AuthenticationError("Auth verify did not return an access token")

        self._token = token_response.access_token
        self._token_expires_at = now + max(0, token_response.expires_in)
        return self._token

    def get_token(self) -> str:
        return self.authenticate()

    def logout(self) -> Dict[str, Any]:
        payload = self._request(
            "POST",
            "/api/v1/auth/logout",
            headers=self._authorized_headers(),
        )
        self._token = None
        self._token_expires_at = 0
        return payload

    def issue_credential(self, **options: Any) -> IssueCredentialResult:
        body: Dict[str, Any] = {}
        for key in ("name", "maxCalls", "creditLimit", "resetInterval", "rpm", "expiresInSec", "expiration"):
            value = options.get(key)
            if value is not None:
                body[key] = value

        payload = self._request(
            "POST",
            "/api/v1/credentials/agent/issue",
            headers=self._authorized_headers(),
            json_body=body,
        )

        credential_payload = payload.get("credential")
        if not isinstance(credential_payload, dict):
            credential_payload = {}

        credential_token = str(
            payload.get("token")
            or payload.get("credential_token")
            or credential_payload.get("token")
            or ""
        )
        credential_id = str(
            payload.get("credential_id")
            or payload.get("id")
            or credential_payload.get("credential_id")
            or credential_payload.get("id")
            or ""
        )
        if credential_id and "id" not in credential_payload:
            credential_payload["id"] = credential_id
        if credential_id and "credential_id" not in credential_payload:
            credential_payload["credential_id"] = credential_id
        if credential_token and "token" not in credential_payload:
            credential_payload["token"] = credential_token

        if not credential_payload:
            raise AuthenticationError(f"Credential payload missing: {payload}")

        credential = AgentCredential.model_validate(credential_payload)
        return IssueCredentialResult(credential=credential, token=credential.token or credential_token)

    def issue_provider_secret(self, **options: Any) -> IssueProviderSecretResult:
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

    def list_credentials(self) -> list[AgentCredential]:
        payload = self._request(
            "GET",
            "/api/v1/credentials/agent/list",
            headers=self._authorized_headers(),
        )
        credentials = payload.get("credentials")
        if not isinstance(credentials, list):
            return []
        return [AgentCredential.model_validate(item) for item in credentials if isinstance(item, dict)]

    def get_balance(self) -> BalanceSummary:
        payload = self._request(
            "GET",
            "/api/v1/balance",
            headers=self._authorized_headers(),
        )
        balance_payload = payload.get("balance")
        if not isinstance(balance_payload, dict):
            balance_payload = payload
        return BalanceSummary.model_validate(balance_payload)

    def register_deposit_intent(
        self,
        tx_hash: str,
        amount_usdc: float,
        *,
        idempotency_key: Optional[str] = None,
    ) -> DepositIntentResult:
        payload = self._request(
            "POST",
            "/api/v1/balance/deposit/intent",
            headers={
                **self._authorized_headers(),
                "X-Idempotency-Key": idempotency_key or f"deposit-{uuid4().hex}",
            },
            json_body={
                "txHash": tx_hash,
                "amountUsdc": amount_usdc,
            },
        )
        return DepositIntentResult.model_validate(payload)

    def confirm_deposit(self, intent_id: str, event_key: str, confirmations: int = 1) -> DepositConfirmResult:
        payload = self._request(
            "POST",
            f"/api/v1/balance/deposit/intents/{intent_id}/confirm",
            headers=self._authorized_headers(),
            json_body={
                "eventKey": event_key,
                "confirmations": confirmations,
            },
        )
        return DepositConfirmResult.model_validate(payload)

    def set_spending_limit(self, spending_limit_usdc: float | None) -> Dict[str, Any]:
        body = (
            {"allowUnlimited": True}
            if spending_limit_usdc is None
            else {"spendingLimitUsdc": spending_limit_usdc, "allowUnlimited": False}
        )
        return self._request(
            "PUT",
            "/api/v1/balance/spending-limit",
            headers=self._authorized_headers(),
            json_body=body,
        )

    def register_provider_service(
        self,
        *,
        service_name: str,
        endpoint_url: str,
        base_price_usdc: float | str,
        description_for_model: str,
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
        resolved_service_name = str(service_name or "").strip()
        resolved_endpoint = str(endpoint_url or "").strip()
        resolved_summary = str(description_for_model or "").strip()
        if not resolved_service_name:
            raise ValueError("service_name is required")
        if not resolved_endpoint:
            raise ValueError("endpoint_url is required")
        if not resolved_summary:
            raise ValueError("description_for_model is required")

        resolved_service_id = str(service_id or "").strip() or self._default_service_id(
            resolved_service_name
        )
        body = {
            "serviceId": resolved_service_id,
            "agentToolName": resolved_service_id,
            "serviceName": resolved_service_name,
            "role": "Provider",
            "status": status,
            "isActive": is_active,
            "pricing": {
                "amount": str(base_price_usdc),
                "currency": "USDC",
            },
            "summary": resolved_summary,
            "tags": tags or [],
            "auth": {"type": "gateway_signed"},
            "invoke": {
                "method": endpoint_method,
                "targets": [{"url": resolved_endpoint}],
                "timeoutMs": request_timeout_ms,
                "request": {
                    "body": input_schema
                    or {"type": "object", "properties": {}, "required": []}
                },
                "response": {
                    "body": output_schema
                    or {"type": "object", "properties": {}}
                },
            },
            "healthCheck": {
                "path": health_path,
                "method": health_method,
                "timeoutMs": health_timeout_ms,
                "successCodes": [200],
                "healthyThreshold": 1,
                "unhealthyThreshold": 3,
            },
            "providerProfile": {
                "displayName": str(provider_display_name or resolved_service_name).strip()
                or resolved_service_name,
            },
            "payoutAccount": {
                "payoutAddress": str(payout_address or self.wallet_address).strip()
                or self.wallet_address,
                "chainId": chain_id,
                "settlementCurrency": settlement_currency,
            },
            "governance": {
                "termsAccepted": True,
                "riskAcknowledged": True,
                "note": governance_note,
            },
        }
        payload = self._request(
            "POST",
            "/api/v1/services",
            headers=self._authorized_headers(),
            json_body=body,
        )
        return ProviderServiceRegistrationResult.model_validate(payload)

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
