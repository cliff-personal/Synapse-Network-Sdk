from __future__ import annotations

from synapse_client import SynapseAuth, SynapseProvider


class DummyAuth:
    def __init__(self):
        self.calls = []

    def issue_provider_secret(self, **options):
        self.calls.append(("issue_provider_secret", options))
        return {"secret": {"id": "psk_1"}}

    def list_provider_secrets(self):
        self.calls.append(("list_provider_secrets", None))
        return []

    def delete_provider_secret(self, secret_id):
        self.calls.append(("delete_provider_secret", secret_id))
        return {"status": "deleted"}

    def get_registration_guide(self):
        self.calls.append(("get_registration_guide", None))
        return {"steps": []}

    def parse_curl_to_service_manifest(self, curl_command):
        self.calls.append(("parse_curl_to_service_manifest", curl_command))
        return {"manifest": {}}

    def register_provider_service(self, **options):
        self.calls.append(("register_provider_service", options))
        return {"serviceId": "svc_1"}

    def list_provider_services(self):
        self.calls.append(("list_provider_services", None))
        return []

    def get_provider_service(self, service_id):
        self.calls.append(("get_provider_service", service_id))
        return {"serviceId": service_id}

    def get_provider_service_status(self, service_id):
        self.calls.append(("get_provider_service_status", service_id))
        return {"serviceId": service_id}

    def update_provider_service(self, service_record_id, patch):
        self.calls.append(("update_provider_service", service_record_id, patch))
        return {"status": "updated"}

    def delete_provider_service(self, service_record_id):
        self.calls.append(("delete_provider_service", service_record_id))
        return {"status": "deleted"}

    def ping_provider_service(self, service_record_id):
        self.calls.append(("ping_provider_service", service_record_id))
        return {"status": "ok"}

    def get_provider_service_health_history(self, service_record_id, *, limit):
        self.calls.append(("get_provider_service_health_history", service_record_id, limit))
        return {"history": []}

    def get_provider_earnings_summary(self):
        self.calls.append(("get_provider_earnings_summary", None))
        return {"total": "0"}

    def get_provider_withdrawal_capability(self):
        self.calls.append(("get_provider_withdrawal_capability", None))
        return {"available": True}

    def create_provider_withdrawal_intent(self, amount_usdc, *, idempotency_key=None, destination_address=None):
        self.calls.append(("create_provider_withdrawal_intent", amount_usdc, idempotency_key, destination_address))
        return {"intentId": "wd_1"}

    def list_provider_withdrawals(self, *, limit):
        self.calls.append(("list_provider_withdrawals", limit))
        return {"withdrawals": []}


def test_provider_facade_delegates_to_owner_auth_methods():
    dummy = DummyAuth()
    provider = SynapseProvider(dummy)

    provider.issue_secret(name="provider")
    provider.list_secrets()
    provider.delete_secret("psk_1")
    provider.get_registration_guide()
    provider.parse_curl_to_service_manifest("curl https://provider.example/health")
    provider.register_service(service_name="Weather", endpoint_url="https://provider.example/invoke")
    provider.list_services()
    provider.get_service("svc_1")
    provider.get_service_status("svc_1")
    provider.update_service("rec_1", {"summary": "updated"})
    provider.delete_service("rec_1")
    provider.ping_service("rec_1")
    provider.get_service_health_history("rec_1", limit=3)
    provider.get_earnings_summary()
    provider.get_withdrawal_capability()
    provider.create_withdrawal_intent(5, idempotency_key="fixed", destination_address="0xabc")
    provider.list_withdrawals(limit=2)

    auth = SynapseAuth(wallet_address="0xabc", signer=lambda _: "0xsigned")
    assert isinstance(auth.provider(), SynapseProvider)
    assert dummy.calls == [
        ("issue_provider_secret", {"name": "provider"}),
        ("list_provider_secrets", None),
        ("delete_provider_secret", "psk_1"),
        ("get_registration_guide", None),
        ("parse_curl_to_service_manifest", "curl https://provider.example/health"),
        ("register_provider_service", {"service_name": "Weather", "endpoint_url": "https://provider.example/invoke"}),
        ("list_provider_services", None),
        ("get_provider_service", "svc_1"),
        ("get_provider_service_status", "svc_1"),
        ("update_provider_service", "rec_1", {"summary": "updated"}),
        ("delete_provider_service", "rec_1"),
        ("ping_provider_service", "rec_1"),
        ("get_provider_service_health_history", "rec_1", 3),
        ("get_provider_earnings_summary", None),
        ("get_provider_withdrawal_capability", None),
        ("create_provider_withdrawal_intent", 5, "fixed", "0xabc"),
        ("list_provider_withdrawals", 2),
    ]
