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
