from __future__ import annotations

from typing import Any, Dict, Optional

from .client import SynapseClient, _resolve_agent_key
from .exceptions import InsufficientFundsError
from .models import InvocationResponse


class AgentWallet(SynapseClient):
    """Convenience wrapper: the 3-line DX entry point for agent developers."""

    def __init__(self, budget: float = 5.0, **kwargs: Any):
        super().__init__(**kwargs)
        self._budget_usdc = float(budget)
        self._spent_usdc: float = 0.0

    @classmethod
    def connect(
        cls,
        budget: float = 5.0,
        api_key: Optional[str] = None,
        gateway_url: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> "AgentWallet":
        api_key = _resolve_agent_key(api_key)
        return cls(budget=budget, api_key=api_key, gateway_url=gateway_url, environment=environment)

    @property
    def budget_usdc(self) -> float:
        return self._budget_usdc

    @property
    def spent_usdc(self) -> float:
        return self._spent_usdc

    @property
    def remaining_usdc(self) -> float:
        return round(self._budget_usdc - self._spent_usdc, 6)

    def invoke(
        self,
        service_id: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        cost_usdc: float = 0.0,
        **kwargs: Any,
    ) -> InvocationResponse:
        cost = float(cost_usdc)
        if self._spent_usdc + cost > self._budget_usdc:
            raise InsufficientFundsError(
                f"Budget exceeded: ${self._spent_usdc:.4f} spent + ${cost:.4f} cost > ${self._budget_usdc:.4f} budget"
            )
        result = super().invoke(service_id, payload=payload, cost_usdc=cost_usdc, **kwargs)
        self._spent_usdc = round(self._spent_usdc + float(result.charged_usdc), 6)
        return result
