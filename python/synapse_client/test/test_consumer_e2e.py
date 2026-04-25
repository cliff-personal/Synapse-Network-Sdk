from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

import pytest
import requests

from synapse_client import SynapseAuth, SynapseClient

pytest.importorskip("eth_account")
pytest.importorskip("web3")

from eth_account import Account
from web3 import Web3


GATEWAY_URL = "http://127.0.0.1:8000"
RPC_URL = "http://127.0.0.1:8545"
DEPOSIT_USDC = 10
MOCK_PROVIDER_PORT = 9399

DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
PROVIDER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ea870594801966b8ea0ec4f"

REPO_ROOT = Path(__file__).resolve().parents[4] / "Synapse-Network"
CONTRACT_CONFIG_PATH = REPO_ROOT / "services/user-front/src/contract-config.json"
MOCK_USDC_ABI_PATH = REPO_ROOT / "services/user-front/src/MockUSDCABI.json"
SYNAPSE_CORE_ABI_PATH = REPO_ROOT / "services/user-front/src/SynapseCoreABI.json"

SESSION_ID = uuid4().hex[:8]
SERVICE_NAME = f"py_sdk_e2e_{SESSION_ID}"
CRED_NAME = f"py-sdk-cred-{SESSION_ID}"


def _load_json(path: Path):
    return json.loads(path.read_text())


def _wait_for(predicate, timeout_sec: float = 30.0, interval_sec: float = 1.0, message: str = "condition not met"):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval_sec)
    raise AssertionError(message)


def _raw_signed(signed_tx):
    raw = getattr(signed_tx, "raw_transaction", None)
    if raw is None:
        raw = getattr(signed_tx, "rawTransaction", None)
    if raw is None:
        raise AttributeError("Signed transaction does not expose raw_transaction/rawTransaction")
    return raw


def _send_transaction(w3: Web3, account, tx: dict):
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(_raw_signed(signed))
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)


def _normalized_tx_hash(value) -> str:
    if isinstance(value, bytes):
        hex_value = value.hex()
    else:
        hex_value = str(value)
    return hex_value if hex_value.startswith("0x") else f"0x{hex_value}"


def _fund_and_deposit(w3: Web3, fresh_account, deployer_account, amount_usdc: int) -> str:
    config = _load_json(CONTRACT_CONFIG_PATH)
    mock_usdc_abi = _load_json(MOCK_USDC_ABI_PATH)
    synapse_core_abi = _load_json(SYNAPSE_CORE_ABI_PATH)
    chain_id = int(w3.eth.chain_id)
    gas_price = int(w3.eth.gas_price)

    usdc = w3.eth.contract(address=Web3.to_checksum_address(config["MockUSDC"]), abi=mock_usdc_abi)
    core = w3.eth.contract(address=Web3.to_checksum_address(config["SynapseCore"]), abi=synapse_core_abi)

    decimals = int(usdc.functions.decimals().call())
    amount_wei = int(amount_usdc * (10 ** decimals))

    deployer_nonce = w3.eth.get_transaction_count(deployer_account.address, "pending")
    _send_transaction(
        w3,
        deployer_account,
        {
            "to": fresh_account.address,
            "value": w3.to_wei(0.5, "ether"),
            "nonce": deployer_nonce,
            "gas": 21_000,
            "gasPrice": gas_price,
            "chainId": chain_id,
        },
    )
    deployer_nonce += 1

    mint_tx = usdc.functions.mint(fresh_account.address, amount_wei).build_transaction(
        {
            "from": deployer_account.address,
            "nonce": deployer_nonce,
            "gasPrice": gas_price,
            "chainId": chain_id,
            "gas": 300_000,
        }
    )
    _send_transaction(w3, deployer_account, mint_tx)

    fresh_nonce = w3.eth.get_transaction_count(fresh_account.address, "pending")
    approve_tx = usdc.functions.approve(core.address, amount_wei).build_transaction(
        {
            "from": fresh_account.address,
            "nonce": fresh_nonce,
            "gasPrice": gas_price,
            "chainId": chain_id,
            "gas": 300_000,
        }
    )
    _send_transaction(w3, fresh_account, approve_tx)
    fresh_nonce += 1

    deposit_tx = core.functions.deposit(amount_wei).build_transaction(
        {
            "from": fresh_account.address,
            "nonce": fresh_nonce,
            "gasPrice": gas_price,
            "chainId": chain_id,
            "gas": 500_000,
        }
    )
    receipt = _send_transaction(w3, fresh_account, deposit_tx)
    return _normalized_tx_hash(receipt["transactionHash"])


class _MockProviderHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        return

    def _write_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._write_json(200, {"status": "healthy"})

    def do_POST(self):  # noqa: N802
        self._write_json(200, {"result": "python-sdk e2e mock response"})


@pytest.fixture(scope="module")
def mock_provider_server():
    server = HTTPServer(("127.0.0.1", MOCK_PROVIDER_PORT), _MockProviderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{MOCK_PROVIDER_PORT}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.e2e
def test_python_sdk_consumer_cold_start_e2e(mock_provider_server):
    assert CONTRACT_CONFIG_PATH.exists(), f"missing contract config: {CONTRACT_CONFIG_PATH}"

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    assert w3.is_connected(), "Hardhat RPC is not reachable"

    deployer_account = Account.from_key(DEPLOYER_KEY)
    provider_account = Account.from_key(PROVIDER_KEY)
    fresh_account = Account.create()

    fresh_auth = SynapseAuth.from_private_key(
        fresh_account.key.hex(),
        gateway_url=GATEWAY_URL,
        timeout_sec=30,
    )
    provider_auth = SynapseAuth.from_private_key(
        PROVIDER_KEY,
        gateway_url=GATEWAY_URL,
        timeout_sec=30,
    )

    tx_hash = _fund_and_deposit(w3, fresh_account, deployer_account, DEPOSIT_USDC)
    token = fresh_auth.get_token()
    assert isinstance(token, str) and len(token) > 20
    assert fresh_auth.get_token() == token

    intent_resp = fresh_auth.register_deposit_intent(tx_hash, DEPOSIT_USDC)
    assert intent_resp.status == "success"
    intent_id = intent_resp.intent.resolved_id
    event_key = intent_resp.intent.resolved_event_key or tx_hash
    assert intent_id, f"missing deposit intent id: {intent_resp.model_dump(by_alias=True)}"

    confirm_resp = fresh_auth.confirm_deposit(intent_id, event_key)
    assert confirm_resp.status == "success"

    balance_after_deposit = _wait_for(
        lambda: (
            fresh_auth.get_balance()
            if float(fresh_auth.get_balance().consumer_available_balance or 0) >= DEPOSIT_USDC * 0.99
            else None
        ),
        timeout_sec=20,
        interval_sec=1.5,
        message="deposit never became spendable in gateway balance",
    )
    available_after_deposit = float(balance_after_deposit.consumer_available_balance or 0)
    assert available_after_deposit >= DEPOSIT_USDC * 0.99

    provider_token = provider_auth.get_token()
    create_service_resp = requests.post(  # type: ignore[name-defined]
        f"{GATEWAY_URL}/api/v1/services",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider_token}",
        },
        json={
            "agentToolName": SERVICE_NAME,
            "serviceName": f"Python SDK E2E Service {SESSION_ID}",
            "role": "Provider",
            "status": "active",
            "isActive": True,
            "pricing": {"amount": "0.001", "currency": "USDC"},
            "summary": "Python SDK automated e2e integration test service",
            "tags": ["py-sdk", "e2e", "test"],
            "auth": {"type": "gateway_signed"},
            "invoke": {
                "method": "POST",
                "targets": [{"url": mock_provider_server}],
                "request": {"body": {"type": "object", "properties": {"prompt": {"type": "string"}}}},
                "response": {"body": {"type": "object", "properties": {"result": {"type": "string"}}}},
            },
            "healthCheck": {
                "path": "/health",
                "method": "GET",
                "timeoutMs": 3000,
                "successCodes": [200],
                "healthyThreshold": 1,
                "unhealthyThreshold": 3,
            },
            "payoutAccount": {
                "payoutAddress": provider_account.address.lower(),
                "chainId": int(w3.eth.chain_id),
                "settlementCurrency": "USDC",
            },
            "providerProfile": {"displayName": f"Python SDK E2E Provider {SESSION_ID}"},
            "governance": {"termsAccepted": True, "riskAcknowledged": True},
        },
        timeout=30,
    )
    assert create_service_resp.ok, create_service_resp.text
    service_payload = create_service_resp.json()
    service_id = (
        service_payload.get("serviceId")
        or service_payload.get("id")
        or service_payload.get("service_id")
        or (service_payload.get("service") or {}).get("serviceId")
        or (service_payload.get("service") or {}).get("id")
        or SERVICE_NAME
    )
    assert service_id
    time.sleep(2)

    issue_result = fresh_auth.issue_credential(
        name=CRED_NAME,
        maxCalls=100,
        creditLimit=5.0,
        rpm=60,
    )
    assert issue_result.token
    listed_credentials = fresh_auth.list_credentials()
    assert CRED_NAME in [credential.name for credential in listed_credentials]

    client = SynapseClient(api_key=issue_result.token, gateway_url=GATEWAY_URL, timeout_sec=30)
    services = client.discover_services(page_size=50)
    ids = [service.service_id for service in services.services]
    assert ids
    assert service_id in ids
    discovered_service = next(service for service in services.services if service.service_id == service_id)
    assert discovered_service.price_usdc is not None

    balance_before_invoke = float(fresh_auth.get_balance().consumer_available_balance or 0)

    invocation = client.invoke(
        service_id,
        payload={"prompt": "python-sdk e2e automated test"},
        cost_usdc=float(discovered_service.price_usdc),
        idempotency_key=f"py-sdk-e2e-{SESSION_ID}",
        poll_timeout_sec=60,
    )
    assert invocation.invocation_id
    assert invocation.status in {"SUCCEEDED", "SETTLED"}
    assert invocation.charged_usdc > 0
    assert invocation.result

    receipt = client.get_invocation_receipt(invocation.invocation_id)
    assert receipt.invocation_id == invocation.invocation_id
    assert receipt.status in {"SUCCEEDED", "SETTLED"}

    balance_after_invoke = _wait_for(
        lambda: (
            fresh_auth.get_balance()
            if float(fresh_auth.get_balance().consumer_available_balance or 0) < balance_before_invoke
            else None
        ),
        timeout_sec=20,
        interval_sec=1.5,
        message="post-invocation balance never decreased",
    )
    assert float(balance_after_invoke.consumer_available_balance or 0) < balance_before_invoke


@pytest.mark.e2e
def test_python_sdk_credential_management_e2e():
    """Tests for new credential management APIs:
    - list_active_credentials (active_only=true)
    - get_credential_status
    - update_credential (name + quota PATCH)
    - ensure_credential (idempotent init)
    """
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    assert w3.is_connected(), "Hardhat RPC is not reachable"

    deployer_account = Account.from_key(DEPLOYER_KEY)
    fresh_account = Account.create()
    mgmt_cred_name = f"sdk-mgmt-{SESSION_ID}"

    fresh_auth = SynapseAuth.from_private_key(
        fresh_account.key.hex(),
        gateway_url=GATEWAY_URL,
        timeout_sec=30,
    )

    # Fund + deposit (tiny amount, just enough to have an owner account)
    tx_hash = _fund_and_deposit(w3, fresh_account, deployer_account, DEPOSIT_USDC)
    token = fresh_auth.get_token()
    assert isinstance(token, str) and len(token) > 20

    intent_resp = fresh_auth.register_deposit_intent(tx_hash, DEPOSIT_USDC)
    assert intent_resp.status == "success"
    confirm_resp = fresh_auth.confirm_deposit(
        intent_resp.intent.resolved_id,
        intent_resp.intent.resolved_event_key or tx_hash,
    )
    assert confirm_resp.status == "success"

    # ── 1. Issue a credential ──────────────────────────────────────────────────
    issue_result = fresh_auth.issue_credential(
        name=mgmt_cred_name,
        maxCalls=300,
        creditLimit=3.0,
        rpm=30,
    )
    assert issue_result.token, "credential token missing"
    cred_id = issue_result.credential.credential_id or issue_result.credential.id
    assert cred_id, "credential_id missing"

    # ── 2. list_active_credentials returns the new credential ─────────────────
    active_creds = fresh_auth.list_active_credentials()
    active_names = [c.name for c in active_creds]
    assert mgmt_cred_name in active_names, (
        f"'{mgmt_cred_name}' not in active_only list: {active_names}"
    )
    for c in active_creds:
        assert c.status == "active", f"non-active in active_only result: {c}"

    # ── 3. get_credential_status returns valid=True ────────────────────────────
    status_result = fresh_auth.get_credential_status(cred_id)
    assert status_result.valid is True, f"expected valid=True: {status_result.model_dump()}"
    assert status_result.credential_status == "active"
    assert status_result.is_expired is False
    assert status_result.calls_exhausted is False
    assert status_result.credential_id == cred_id

    # ── 4. update_credential renames + changes maxCalls ───────────────────────
    new_name = f"{mgmt_cred_name}-updated"
    update_result = fresh_auth.update_credential(cred_id, name=new_name, maxCalls=600)
    assert update_result.status == "success"
    assert update_result.credential.name == new_name, (
        f"name not updated: {update_result.credential.name}"
    )
    assert update_result.credential.max_calls == 600, (
        f"maxCalls not updated: {update_result.credential.max_calls}"
    )

    # ── 5. active_only list reflects the rename ────────────────────────────────
    active_after_update = fresh_auth.list_active_credentials()
    names_after = [c.name for c in active_after_update]
    assert new_name in names_after, (
        f"renamed credential not in active_only list: {names_after}"
    )

    # ── 6. ensure_credential is idempotent — same name = rotate for token ─────
    token_a = fresh_auth.ensure_credential(new_name, maxCalls=600, creditLimit=3.0)
    assert token_a, "ensure_credential should return a token"
    # Second call should also return a token (rotate path)
    token_b = fresh_auth.ensure_credential(new_name, maxCalls=600, creditLimit=3.0)
    assert token_b, "ensure_credential second call should return a token"

    # ── 7. ensure_credential creates new credential when name doesn't exist ───
    brand_new_name = f"sdk-ensure-new-{SESSION_ID}"
    token_new = fresh_auth.ensure_credential(brand_new_name, maxCalls=50, creditLimit=1.0)
    assert token_new, f"ensure_credential should issue a new credential for '{brand_new_name}'"
    # Verify it's now in active list
    active_final = fresh_auth.list_active_credentials()
    final_names = [c.name for c in active_final]
    assert brand_new_name in final_names, (
        f"ensure_credential-created credential not found: {final_names}"
    )
