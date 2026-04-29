from __future__ import annotations

from typing import Any, Dict

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


class SynapseProvider:
    """Provider publishing facade backed by an authenticated SynapseAuth owner.

    Provider is an owner-scoped supply-side role in SynapseNetwork. This facade
    keeps provider onboarding discoverable without introducing a second auth
    root or breaking the existing SynapseAuth methods.
    """

    def __init__(self, auth: Any) -> None:
        self._auth = auth

    def issue_secret(self, **options: Any) -> IssueProviderSecretResult:
        return self._auth.issue_provider_secret(**options)

    def list_secrets(self) -> list[ProviderSecret]:
        return self._auth.list_provider_secrets()

    def delete_secret(self, secret_id: str) -> ProviderSecretDeleteResult:
        return self._auth.delete_provider_secret(secret_id)

    def get_registration_guide(self) -> ProviderRegistrationGuide:
        return self._auth.get_registration_guide()

    def parse_curl_to_service_manifest(self, curl_command: str) -> ServiceManifestDraft:
        return self._auth.parse_curl_to_service_manifest(curl_command)

    def register_service(self, **options: Any) -> ProviderServiceRegistrationResult:
        return self._auth.register_provider_service(**options)

    def register_llm_service(self, **options: Any) -> ProviderServiceRegistrationResult:
        return self._auth.register_llm_service(**options)

    def list_services(self) -> list[ProviderService]:
        return self._auth.list_provider_services()

    def get_service(self, service_id: str) -> ProviderService:
        return self._auth.get_provider_service(service_id)

    def get_service_status(self, service_id: str) -> ProviderServiceStatus:
        return self._auth.get_provider_service_status(service_id)

    def update_service(self, service_record_id: str, patch: Dict[str, Any]) -> ProviderServiceUpdateResult:
        return self._auth.update_provider_service(service_record_id, patch)

    def delete_service(self, service_record_id: str) -> ProviderServiceDeleteResult:
        return self._auth.delete_provider_service(service_record_id)

    def ping_service(self, service_record_id: str) -> ProviderServicePingResult:
        return self._auth.ping_provider_service(service_record_id)

    def get_service_health_history(self, service_record_id: str, *, limit: int = 100) -> ProviderServiceHealthHistory:
        return self._auth.get_provider_service_health_history(service_record_id, limit=limit)

    def get_earnings_summary(self) -> ProviderEarningsSummary:
        return self._auth.get_provider_earnings_summary()

    def get_withdrawal_capability(self) -> ProviderWithdrawalCapability:
        return self._auth.get_provider_withdrawal_capability()

    def create_withdrawal_intent(
        self,
        amount_usdc: float,
        *,
        idempotency_key: str | None = None,
        destination_address: str | None = None,
    ) -> ProviderWithdrawalIntentResult:
        return self._auth.create_provider_withdrawal_intent(
            amount_usdc,
            idempotency_key=idempotency_key,
            destination_address=destination_address,
        )

    def list_withdrawals(self, *, limit: int = 100) -> ProviderWithdrawalList:
        return self._auth.list_provider_withdrawals(limit=limit)
