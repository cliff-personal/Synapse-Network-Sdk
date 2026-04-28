from __future__ import annotations

from typing import Any, Dict

from .exceptions import AuthenticationError
from .models import AgentCredential, CredentialStatusResult, IssueCredentialResult, UpdateCredentialResult


class CredentialManagementMixin:
    def issue_credential(self, **options: Any) -> IssueCredentialResult:
        body = self._credential_options_body(options)
        payload = self._request(
            "POST",
            "/api/v1/credentials/agent/issue",
            headers=self._authorized_headers(),
            json_body=body,
        )
        credential_payload, credential_token = self._issued_credential_payload(payload)
        credential = AgentCredential.model_validate(credential_payload)
        return IssueCredentialResult(credential=credential, token=credential.token or credential_token)

    @staticmethod
    def _credential_options_body(options: Dict[str, Any]) -> Dict[str, Any]:
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
        return body

    @staticmethod
    def _issued_credential_payload(payload: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        credential_payload = payload.get("credential")
        if not isinstance(credential_payload, dict):
            credential_payload = {}

        credential_token = _first_text(
            payload.get("token"), payload.get("credential_token"), credential_payload.get("token")
        )
        credential_id = _first_text(
            payload.get("credential_id"),
            payload.get("id"),
            credential_payload.get("credential_id"),
            credential_payload.get("id"),
        )
        _apply_credential_defaults(credential_payload, credential_id, credential_token)

        if not credential_payload:
            raise AuthenticationError(f"Credential payload missing: {payload}")
        return credential_payload, credential_token

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

    def list_active_credentials(self) -> list[AgentCredential]:
        """Return only active, non-expired credentials (active_only=true filter)."""
        payload = self._request(
            "GET",
            self._query_path("/api/v1/credentials/agent/list", {"active_only": "true"}),
            headers=self._authorized_headers(),
        )
        credentials = payload.get("credentials")
        if not isinstance(credentials, list):
            return []
        return [AgentCredential.model_validate(item) for item in credentials if isinstance(item, dict)]

    def get_credential_status(self, credential_id: str) -> CredentialStatusResult:
        """Check whether a credential is valid and usable."""
        credential_id = self._require_value(credential_id, "credential_id")
        payload = self._request(
            "GET",
            f"/api/v1/credentials/agent/{credential_id}/status",
            headers=self._authorized_headers(),
        )
        return CredentialStatusResult.model_validate(payload)

    def revoke_credential(self, credential_id: str) -> Dict[str, Any]:
        """Revoke an agent credential without deleting its audit trail."""
        credential_id = self._require_value(credential_id, "credential_id")
        return self._request(
            "POST",
            f"/api/v1/credentials/agent/{credential_id}/revoke",
            headers=self._authorized_headers(),
        )

    def rotate_credential(self, credential_id: str) -> Dict[str, Any]:
        """Rotate an agent credential and return the gateway response containing the new token."""
        credential_id = self._require_value(credential_id, "credential_id")
        return self._request(
            "POST",
            f"/api/v1/credentials/agent/{credential_id}/rotate",
            headers=self._authorized_headers(),
        )

    def delete_credential(self, credential_id: str) -> Dict[str, Any]:
        """Delete an agent credential. Use revoke_credential for emergency shutoff."""
        credential_id = self._require_value(credential_id, "credential_id")
        return self._request(
            "DELETE",
            f"/api/v1/credentials/agent/{credential_id}",
            headers=self._authorized_headers(),
        )

    def update_credential_quota(self, credential_id: str, **options: Any) -> Dict[str, Any]:
        """Update spend/call/rate quota fields for an agent credential."""
        credential_id = self._require_value(credential_id, "credential_id")
        aliases = {
            "max_calls": "maxCalls",
            "credit_limit": "creditLimit",
            "reset_interval": "resetInterval",
            "expires_at": "expiresAt",
        }
        for source, target in aliases.items():
            if source in options and target not in options:
                options[target] = options[source]
        body: Dict[str, Any] = {}
        for key in ("maxCalls", "rpm", "creditLimit", "resetInterval", "expiresAt", "expiration"):
            value = options.get(key)
            if value is not None:
                body[key] = value
        return self._request(
            "PATCH",
            f"/api/v1/credentials/agent/{credential_id}/quota",
            headers=self._authorized_headers(),
            json_body=body,
        )

    def get_credential_audit_logs(self, *, limit: int = 100) -> Dict[str, Any]:
        """Fetch credential lifecycle audit logs for the authenticated owner."""
        return self._request(
            "GET",
            self._query_path("/api/v1/credentials/agent/audit-logs", {"limit": limit}),
            headers=self._authorized_headers(),
        )

    def check_credential_status(self, credential_id: str) -> CredentialStatusResult:
        """Alias for get_credential_status()."""
        return self.get_credential_status(credential_id)

    def update_credential(self, credential_id: str, **options: Any) -> UpdateCredentialResult:
        """Update name and/or quota fields of a credential (PATCH)."""
        credential_id = self._require_value(credential_id, "credential_id")
        body: Dict[str, Any] = {}
        for key in ("name", "maxCalls", "rpm", "expiresAt", "creditLimit", "resetInterval", "expiration"):
            value = options.get(key)
            if value is not None:
                body[key] = value
        payload = self._request(
            "PATCH",
            f"/api/v1/credentials/agent/{credential_id}",
            headers=self._authorized_headers(),
            json_body=body,
        )
        credential_payload = payload.get("credential")
        if not isinstance(credential_payload, dict):
            credential_payload = {}
        return UpdateCredentialResult(
            status=str(payload.get("status", "success")),
            credential=AgentCredential.model_validate(credential_payload) if credential_payload else AgentCredential(),
        )

    def ensure_credential(
        self,
        name: str,
        **options: Any,
    ) -> str:
        """Idempotent init: return token of an existing active credential by name, or create one.

        Usage::

            token = auth.ensure_credential("my-agent", creditLimit=10.0, maxCalls=1000)

        The method:
        1. Calls ``list_active_credentials()``.
        2. Returns the token of the first credential matching *name* (if any).
        3. Otherwise issues a new credential and returns its token.

        Note: The token is only returned once at issue time. For existing
        credentials the token is NOT re-returned by the list API (it is hashed).
        A credential name match is used as a readiness signal — if you need the
        raw token again you must persist it externally on first creation.
        """
        credential = self._matching_active_credential(name)
        if credential:
            return self._usable_token_for_credential(credential)
        result = self.issue_credential(name=name, **options)
        return result.token or str(result.credential.token or "")

    def _matching_active_credential(self, name: str) -> AgentCredential | None:
        target = str(name or "").strip()
        for cred in self.list_active_credentials():
            if str(cred.name or "").strip() == target:
                return cred
        return None

    def _usable_token_for_credential(self, credential: AgentCredential) -> str:
        token = str(credential.token or "").strip()
        if token:
            return token
        rotated = self._request(
            "POST",
            f"/api/v1/credentials/agent/{credential.credential_id}/rotate",
            headers=self._authorized_headers(),
        )
        credential_payload = rotated.get("credential")
        nested_token = credential_payload.get("token") if isinstance(credential_payload, dict) else None
        return _first_text(rotated.get("token"), nested_token)


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _apply_credential_defaults(credential_payload: Dict[str, Any], credential_id: str, credential_token: str) -> None:
    if credential_id and "id" not in credential_payload:
        credential_payload["id"] = credential_id
    if credential_id and "credential_id" not in credential_payload:
        credential_payload["credential_id"] = credential_id
    if credential_token and "token" not in credential_payload:
        credential_payload["token"] = credential_token
