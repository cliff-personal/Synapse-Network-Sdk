#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from synapse_client import SynapseAuth, SynapseClient, resolve_gateway_url
from synapse_client.exceptions import SynapseClientError

try:
    from eth_account import Account
except ImportError:  # pragma: no cover - exercised by users without dev extras
    Account = None  # type: ignore[assignment]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a staging owner wallet, issue an agent credential, and invoke a free service.",
    )
    parser.add_argument(
        "--environment",
        default=os.getenv("SYNAPSE_ENV", "staging").strip() or "staging",
        help="Gateway environment preset. Defaults to staging.",
    )
    parser.add_argument(
        "--gateway-url",
        default=os.getenv("SYNAPSE_GATEWAY", "").strip(),
        help="Gateway base URL. Overrides --environment.",
    )
    parser.add_argument(
        "--query",
        default="free",
        help="Discovery query. Defaults to free.",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="Optional discovery tags.",
    )
    parser.add_argument(
        "--payload-json",
        default='{"prompt":"hello from a fresh Synapse SDK wallet"}',
        help="JSON object payload sent to the selected service.",
    )
    parser.add_argument(
        "--allow-paid",
        action="store_true",
        help="Allow invoking paid services. By default this example only calls price_usdc == 0 services.",
    )
    parser.add_argument(
        "--credential-name",
        default="sdk-fresh-wallet-example",
        help="Name for the agent credential issued by the fresh owner wallet.",
    )
    return parser.parse_args()


def print_json(label: str, payload: object) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=False, indent=2)}")


def parse_payload(raw: str) -> dict:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--payload-json must decode to a JSON object")
    return payload


def price_string(service_price: object) -> str:
    return str(service_price if service_price is not None else "0")


def is_zero_usdc(amount: str) -> bool:
    try:
        return Decimal(amount) == Decimal("0")
    except (InvalidOperation, TypeError):
        return False


def main() -> int:
    if Account is None:
        print("eth-account is required. Install dev extras: python -m pip install -e '.[dev]'", file=sys.stderr)
        return 2

    args = parse_args()
    try:
        payload = parse_payload(args.payload_json)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    gateway_url = resolve_gateway_url(environment=args.environment, gateway_url=args.gateway_url)
    fresh_account = Account.create(f"synapse-sdk-example-{uuid4().hex}")
    request_id = f"sdk-wallet-{uuid4().hex[:12]}"
    print(f"Gateway: {gateway_url}")
    print(f"Fresh owner wallet: {fresh_account.address}")
    print("Private key is generated in memory for this example. Fund this wallet before paid calls.")

    try:
        auth = SynapseAuth.from_private_key(
            fresh_account.key.hex(),
            gateway_url=gateway_url,
            timeout_sec=30,
        )
        token = auth.get_token()
        print(f"JWT acquired: {bool(token)}")

        balance = auth.get_balance()
        print_json("Owner balance", balance.model_dump(by_alias=True, exclude_none=True))

        issued = auth.issue_credential(
            name=args.credential_name,
            maxCalls=100,
            creditLimit=0 if not args.allow_paid else 5,
            rpm=60,
        )
        print(f"Issued credential id: {issued.credential.id or issued.credential.credential_id}")
        print("Issued credential token starts with:", issued.token[:8])

        client = SynapseClient(api_key=issued.token, gateway_url=gateway_url)
        discovery = client.search_services(
            query=args.query,
            tags=args.tags,
            page=1,
            page_size=20,
            request_id=request_id,
        )
        print(f"Discovery count: {discovery.count}")
        if not discovery.services:
            print_json("Discovery diagnostics", client.explain_discovery_empty_result(query=args.query, tags=args.tags))
            return 1

        selected = None
        for service in discovery.services:
            price = price_string(service.price_usdc)
            print(f"- {service.service_id} | {service.service_name} | {price} USDC")
            if selected is None and (args.allow_paid or is_zero_usdc(price)):
                selected = service

        if selected is None:
            print(
                "No free service found. Re-run with --allow-paid after funding this wallet or widening credential budget.",
                file=sys.stderr,
            )
            return 1

        cost_usdc = price_string(selected.price_usdc)
        idempotency_key = f"{request_id}-invoke"
        invocation = client.invoke(
            selected.service_id,
            payload=payload,
            cost_usdc=cost_usdc,
            idempotency_key=idempotency_key,
            request_id=request_id,
            poll_timeout_sec=60,
        )
        receipt = client.get_invocation(invocation.invocation_id)
        print_json("Invocation", invocation.model_dump(by_alias=True, exclude_none=True))
        print_json("Receipt", receipt.model_dump(by_alias=True, exclude_none=True))
        return 0
    except SynapseClientError as exc:
        print(f"Fresh wallet consumer flow failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Fresh wallet example failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
