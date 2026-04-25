#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from uuid import uuid4

from synapse_client import SynapseClient, resolve_gateway_url
from synapse_client.exceptions import SynapseClientError


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "SETTLED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call a provider service through SynapseNetwork using an Agent Key.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SYNAPSE_API_KEY", "").strip(),
        help="Agent credential. Defaults to SYNAPSE_API_KEY.",
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
        "--service-id",
        default="",
        help="Known provider service id. If omitted, the script searches with --query.",
    )
    parser.add_argument(
        "--query",
        default="free",
        help="Discovery query used when --service-id is omitted.",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="Optional discovery tags.",
    )
    parser.add_argument(
        "--cost-usdc",
        type=float,
        default=None,
        help="Price assertion. Required only when --service-id skips discovery.",
    )
    parser.add_argument(
        "--payload-json",
        default='{"prompt":"hello from Synapse SDK consumer example"}',
        help="JSON object payload sent to the provider service.",
    )
    parser.add_argument(
        "--idempotency-key",
        default="",
        help="Invocation idempotency key. Auto-generated when omitted.",
    )
    parser.add_argument(
        "--request-id",
        default="",
        help="Request id for gateway log correlation. Auto-generated when omitted.",
    )
    return parser.parse_args()


def print_json(label: str, payload: object) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=False, indent=2)}")


def parse_payload(raw: str) -> dict:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--payload-json must decode to a JSON object")
    return payload


def resolve_service(client: SynapseClient, args: argparse.Namespace, request_id: str) -> tuple[str, float]:
    service_id = args.service_id.strip()
    if service_id:
        if args.cost_usdc is None:
            raise ValueError("--cost-usdc is required when --service-id skips discovery")
        return service_id, float(args.cost_usdc)

    discovery = client.search_services(
        query=args.query,
        tags=args.tags,
        page=1,
        page_size=10,
        request_id=request_id,
    )
    print(f"Discovery count: {discovery.count}")
    for service in discovery.services:
        print(f"- {service.service_id} | {service.service_name} | {service.pricing.amount} {service.pricing.currency}")
    if not discovery.services:
        diagnostics = client.explain_discovery_empty_result(query=args.query, tags=args.tags)
        print_json("Discovery diagnostics", diagnostics)
        raise RuntimeError("No provider service matched the discovery query")

    selected = discovery.services[0]
    if selected.price_usdc is None:
        raise RuntimeError(f"Selected service has no parseable price: {selected.service_id}")
    return selected.service_id, float(selected.price_usdc)


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("SYNAPSE_API_KEY or --api-key is required.", file=sys.stderr)
        return 2
    try:
        payload = parse_payload(args.payload_json)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    gateway_url = resolve_gateway_url(environment=args.environment, gateway_url=args.gateway_url)
    request_id = args.request_id.strip() or f"sdk-consumer-{uuid4().hex[:12]}"
    idempotency_key = args.idempotency_key.strip() or f"{request_id}-invoke"
    client = SynapseClient(api_key=args.api_key, gateway_url=gateway_url)

    print(f"Gateway: {gateway_url}")
    print(f"Request id: {request_id}")
    print(f"Idempotency key: {idempotency_key}")
    print_json("Payload", payload)

    try:
        service_id, cost_usdc = resolve_service(client, args, request_id)
        print(f"Selected service id: {service_id}")
        print(f"Price assertion: {cost_usdc:.6f} USDC")

        invocation = client.invoke(
            service_id,
            payload=payload,
            cost_usdc=cost_usdc,
            idempotency_key=idempotency_key,
            request_id=request_id,
            poll_timeout_sec=60,
        )
        if invocation.status not in TERMINAL_STATUSES and invocation.invocation_id:
            invocation = client.wait_for_invocation(invocation.invocation_id, max_wait_sec=60)
        receipt = client.get_invocation(invocation.invocation_id)
        print_json("Invocation", invocation.model_dump(by_alias=True, exclude_none=True))
        print_json("Receipt", receipt.model_dump(by_alias=True, exclude_none=True))
        return 0
    except SynapseClientError as exc:
        print(f"Consumer provider call failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Consumer provider example failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
