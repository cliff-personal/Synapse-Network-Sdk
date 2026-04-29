from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import Field

from .models import AgentCredential, ProviderService, SDKModel


class AuthLogoutResult(SDKModel):
    status: str = "success"
    success: Optional[bool] = None


class OwnerProfile(SDKModel):
    profile: Dict[str, Any] = Field(default_factory=dict)
    owner_address: Optional[str] = Field(default=None, alias="ownerAddress")
    wallet_address: Optional[str] = Field(default=None, alias="walletAddress")


class CredentialRevokeResult(SDKModel):
    status: str = "success"
    credential_id: str = Field(default="", alias="credentialId")
    credential: Optional[AgentCredential] = None


class CredentialRotateResult(SDKModel):
    status: str = "success"
    credential_id: str = Field(default="", alias="credentialId")
    token: str = ""
    credential: Optional[AgentCredential] = None


class CredentialDeleteResult(SDKModel):
    status: str = "success"
    credential_id: str = Field(default="", alias="credentialId")


class CredentialQuotaUpdateResult(SDKModel):
    status: str = "success"
    credential_id: str = Field(default="", alias="credentialId")
    credential: Optional[AgentCredential] = None


class CredentialAuditLogList(SDKModel):
    logs: List[Dict[str, Any]] = Field(default_factory=list)


class VoucherRedeemResult(SDKModel):
    status: str = "success"
    voucher_code: Optional[str] = Field(default=None, alias="voucherCode")


class UsageLogList(SDKModel):
    logs: List[Dict[str, Any]] = Field(default_factory=list)


class FinanceAuditLogList(SDKModel):
    logs: List[Dict[str, Any]] = Field(default_factory=list)


class RiskOverview(SDKModel):
    risk: Optional[Any] = None


class ProviderSecretDeleteResult(SDKModel):
    status: str = "success"
    secret_id: str = Field(default="", alias="secretId")


class ProviderRegistrationGuide(SDKModel):
    steps: List[Any] = Field(default_factory=list)
    requirements: Dict[str, Any] = Field(default_factory=dict)


class ServiceManifestDraft(SDKModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    manifest: Dict[str, Any] = Field(default_factory=dict)


class ProviderServiceUpdateResult(SDKModel):
    status: str = "success"
    service: Optional[ProviderService] = None


class ProviderServiceDeleteResult(SDKModel):
    status: str = "success"
    service_id: str = Field(default="", alias="serviceId")


class ProviderServicePingResult(SDKModel):
    status: str = "success"
    health: Dict[str, Any] = Field(default_factory=dict)


class ProviderServiceHealthHistory(SDKModel):
    history: List[Dict[str, Any]] = Field(default_factory=list)


class ProviderEarningsSummary(SDKModel):
    total: Optional[Decimal | float | int | str] = None


class ProviderWithdrawalCapability(SDKModel):
    available: Optional[bool] = None


class ProviderWithdrawalIntentResult(SDKModel):
    status: str = "success"
    intent_id: str = Field(default="", alias="intentId")
    amount_usdc: Optional[Decimal | float | int | str] = Field(default=None, alias="amountUsdc")
    intent: Dict[str, Any] = Field(default_factory=dict)


class ProviderWithdrawalList(SDKModel):
    withdrawals: List[Dict[str, Any]] = Field(default_factory=list)
