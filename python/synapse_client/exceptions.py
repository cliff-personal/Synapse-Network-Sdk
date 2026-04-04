class SynapseClientError(Exception):
    """Base exception for synapse client."""


class BudgetExceededError(SynapseClientError):
    """Raised when a credential budget, daily cap, or spend guard blocks execution."""


class DiscoveryError(SynapseClientError):
    """Raised when service discovery request fails."""


class InvokeError(SynapseClientError):
    """Raised when paid invoke request fails."""


class InsufficientFundsError(BudgetExceededError):
    """Raised when there is not enough balance or remaining budget to continue."""


class AuthenticationError(SynapseClientError):
    """Raised when API key is invalid."""


class TimeoutError(SynapseClientError):
    """Raised when an async invocation does not reach a terminal state in time."""


class PriceMismatchError(SynapseClientError):
    """Raised when the live service price differs from the agent's expected cost_usdc.

    Attributes:
        expected_price_usdc: the price the agent passed in invoke()
        current_price_usdc: the live price the gateway returned
    """

    def __init__(self, message: str, expected_price_usdc: float, current_price_usdc: float) -> None:
        super().__init__(message)
        self.expected_price_usdc = expected_price_usdc
        self.current_price_usdc = current_price_usdc

