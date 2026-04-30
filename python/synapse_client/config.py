from __future__ import annotations

import os
from typing import Literal, Optional

SynapseEnvironment = Literal["staging", "prod"]

GATEWAY_URLS: dict[SynapseEnvironment, str] = {
    "staging": "https://api-staging.synapse-network.ai",
    "prod": "https://api.synapse-network.ai",
}

DEFAULT_ENVIRONMENT: SynapseEnvironment = "staging"


def resolve_gateway_url(
    environment: Optional[str] = None,
    gateway_url: Optional[str] = None,
) -> str:
    """Resolve a Synapse gateway URL without runtime probing or fallback."""
    explicit_url = str(gateway_url or "").strip()
    if explicit_url:
        return explicit_url.rstrip("/")

    explicit_environment = str(environment or "").strip()
    if explicit_environment:
        selected = explicit_environment.lower()
        if selected not in GATEWAY_URLS:
            valid = ", ".join(sorted(GATEWAY_URLS))
            raise ValueError(f"unsupported Synapse environment '{selected}'. Expected one of: {valid}")
        return GATEWAY_URLS[selected].rstrip("/")

    env_url = os.getenv("SYNAPSE_GATEWAY", "").strip()
    if env_url:
        return env_url.rstrip("/")

    selected = str(os.getenv("SYNAPSE_ENV", "") or DEFAULT_ENVIRONMENT).strip().lower()
    if selected not in GATEWAY_URLS:
        valid = ", ".join(sorted(GATEWAY_URLS))
        raise ValueError(f"unsupported Synapse environment '{selected}'. Expected one of: {valid}")
    return GATEWAY_URLS[selected].rstrip("/")
