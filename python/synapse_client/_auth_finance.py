from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from .models import BalanceSummary, DepositConfirmResult, DepositIntentResult


class FinanceManagementMixin:
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

    def redeem_voucher(self, voucher_code: str, *, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Redeem a voucher into the authenticated owner balance."""
        voucher_code = self._require_value(voucher_code, "voucher_code")
        return self._request(
            "POST",
            "/api/v1/balance/vouchers/redeem",
            headers={
                **self._authorized_headers(),
                "X-Idempotency-Key": idempotency_key or f"voucher-{uuid4().hex}",
            },
            json_body={"voucherCode": voucher_code},
        )

    def get_usage_logs(self, *, limit: int = 100) -> Dict[str, Any]:
        """Fetch owner usage logs for observability and billing review."""
        return self._request(
            "GET",
            self._query_path("/api/v1/usage/logs", {"limit": limit}),
            headers=self._authorized_headers(),
        )

    def get_finance_audit_logs(self, *, limit: int = 100) -> Dict[str, Any]:
        """Fetch finance audit logs. High-impact finance actions remain explicit."""
        return self._request(
            "GET",
            self._query_path("/api/v1/finance/audit-logs", {"limit": limit}),
            headers=self._authorized_headers(),
        )

    def get_risk_overview(self) -> Dict[str, Any]:
        """Return the owner finance risk overview."""
        return self._request(
            "GET",
            "/api/v1/finance/risk-overview",
            headers=self._authorized_headers(),
        )
