from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode
from uuid import uuid4

import requests

from ._auth_credentials import CredentialManagementMixin
from ._auth_finance import FinanceManagementMixin
from ._auth_provider_control import ProviderControlMixin
from .config import resolve_gateway_url
from .exceptions import AuthenticationError
from .models import ChallengeResponse, TokenResponse

SignerFn = Callable[[str], str]


class SynapseAuth(CredentialManagementMixin, FinanceManagementMixin, ProviderControlMixin):
    """Wallet-based owner auth + credential + balance management for Synapse."""

    def __init__(
        self,
        *,
        wallet_address: str,
        signer: SignerFn,
        gateway_url: Optional[str] = None,
        environment: Optional[str] = None,
        timeout_sec: int = 30,
    ) -> None:
        normalized = str(wallet_address or "").strip().lower()
        if not normalized:
            raise ValueError("wallet_address is required")

        self.wallet_address = normalized
        self.gateway_url = resolve_gateway_url(environment=environment, gateway_url=gateway_url)
        self.timeout_sec = timeout_sec
        self._signer = signer
        self._token: str | None = None
        self._token_expires_at: float = 0

    def provider(self):
        """Return a provider publishing facade scoped to this authenticated owner."""
        from .provider import SynapseProvider

        return SynapseProvider(self)

    @classmethod
    def from_private_key(
        cls,
        private_key: str,
        *,
        gateway_url: Optional[str] = None,
        environment: Optional[str] = None,
        timeout_sec: int = 30,
    ) -> "SynapseAuth":
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
        except ImportError as exc:
            raise ImportError(
                'SynapseAuth.from_private_key requires eth-account. Install with `pip install -e ".[dev]"`.'
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
            environment=environment,
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
        normalized = str(service_name or "").strip().lower().replace(" ", "_")
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

        payload = self._json_payload(response)

        if not response.ok:
            raise AuthenticationError(self._auth_error_message(response, payload))
        return payload

    @staticmethod
    def _json_payload(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _auth_error_message(response: requests.Response, payload: Dict[str, Any]) -> str:
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("code") or response.text)
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        return response.text.strip() or f"HTTP {response.status_code}"

    @staticmethod
    def _require_value(value: str, name: str) -> str:
        resolved = str(value or "").strip()
        if not resolved:
            raise ValueError(f"{name} is required")
        return resolved

    @staticmethod
    def _query_path(path: str, params: Dict[str, Any]) -> str:
        filtered = {key: value for key, value in params.items() if value is not None}
        if not filtered:
            return path
        return f"{path}?{urlencode(filtered)}"

    def authenticate(self, force_refresh: bool = False) -> str:
        now = time.time()
        if not force_refresh and self._token and now < max(0, self._token_expires_at - 30):
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

    def get_owner_profile(self) -> Dict[str, Any]:
        """Return the authenticated owner profile."""
        return self._request(
            "GET",
            "/api/v1/auth/me",
            headers=self._authorized_headers(),
        )
