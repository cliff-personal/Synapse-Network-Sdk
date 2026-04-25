#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from uuid import uuid4

from synapse_client import SynapseAuth, resolve_gateway_url
from synapse_client.exceptions import AuthenticationError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register a provider service on the SynapseNetwork staging gateway.",
    )
    parser.add_argument(
        "--provider-private-key",
        default=os.getenv("SYNAPSE_PROVIDER_PRIVATE_KEY", "").strip(),
        help="Provider/owner wallet private key. Defaults to SYNAPSE_PROVIDER_PRIVATE_KEY.",
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
        "--endpoint-url",
        required=True,
        help="Public HTTPS provider invoke endpoint reachable by the staging gateway.",
    )
    parser.add_argument(
        "--service-name",
        default="Synapse SDK Example Provider",
        help="Human-readable provider service name.",
    )
    parser.add_argument(
        "--description",
        default="Example provider service registered from the Synapse Python SDK.",
        help="Model-facing service description.",
    )
    parser.add_argument(
        "--price-usdc",
        default="0",
        help="Fixed service price in USDC. Defaults to 0 for staging smoke tests.",
    )
    parser.add_argument(
        "--provider-display-name",
        default="Synapse SDK Example Provider",
        help="Display name shown for the provider profile.",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=["sdk", "example", "provider"],
        help="Optional service tags.",
    )
    parser.add_argument(
        "--secret-name",
        default="sdk-provider-example",
        help="Provider control-plane secret name.",
    )
    return parser.parse_args()


def print_json(label: str, payload: object) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=False, indent=2)}")


def validate_args(args: argparse.Namespace) -> int:
    if not args.provider_private_key:
        print("SYNAPSE_PROVIDER_PRIVATE_KEY or --provider-private-key is required.", file=sys.stderr)
        return 2
    endpoint_url = args.endpoint_url.strip()
    if not endpoint_url.startswith("https://"):
        print(
            "--endpoint-url must be a public HTTPS URL. The staging gateway cannot invoke localhost.",
            file=sys.stderr,
        )
        return 2
    return 0


def main() -> int:
    args = parse_args()
    invalid = validate_args(args)
    if invalid:
        return invalid

    gateway_url = resolve_gateway_url(environment=args.environment, gateway_url=args.gateway_url)
    print(f"Gateway: {gateway_url}")
    print("Mode: provider publishing")

    try:
        auth = SynapseAuth.from_private_key(
            args.provider_private_key,
            gateway_url=gateway_url,
            timeout_sec=30,
        )
        token = auth.get_token()
        print(f"Owner wallet: {auth.wallet_address}")
        print(f"JWT acquired: {bool(token)}")

        provider = auth.provider()
        secret = provider.issue_secret(
            name=args.secret_name,
            rpm=180,
            creditLimit=25.0,
        )
        print(f"Provider secret id: {secret.secret.id}")
        print(f"Provider secret masked key: {secret.secret.masked_key or '<returned once>'}")

        registered = provider.register_service(
            service_name=args.service_name,
            endpoint_url=args.endpoint_url.strip(),
            base_price_usdc=args.price_usdc,
            description_for_model=args.description,
            provider_display_name=args.provider_display_name,
            tags=args.tags,
            governance_note=f"sdk provider staging example {uuid4().hex[:8]}",
        )
        print(f"Registered service id: {registered.service_id}")
        print_json("Registered service", registered.model_dump(by_alias=True, exclude_none=True))

        status = provider.get_service_status(registered.service_id)
        print_json("Provider service status", status.model_dump(by_alias=True, exclude_none=True))
        print("Provider staging onboarding completed.")
        return 0
    except AuthenticationError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Provider onboarding failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
