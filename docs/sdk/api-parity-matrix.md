# SDK/API Parity Matrix

This matrix keeps the SDK repo aligned with the Gateway and product docs in `Synapse-Network`. Public examples should describe these SDK surfaces first; raw Gateway routes remain implementation detail unless a developer is integrating without the SDK.

Current public environment: staging on Arbitrum Sepolia with MockUSDC test assets.

## Agent Runtime

| Capability | Python SDK | TypeScript SDK | Go SDK | Java SDK | .NET SDK | Gateway route | Notes |
|---|---|---|---|---|---|---|---|
| Discover services | `discover()`, `search()` | `discover()`, `search()` | `Discover()`, `Search()` | `discover()`, `search()` | `DiscoverAsync()`, `SearchAsync()` | `POST /api/v1/agent/discovery/search` | Use before paid fixed-price calls to capture current price. |
| Fixed-price invoke | `invoke(..., cost_usdc="0.05")` | `invoke(..., { costUsdc: "0.05" })` | `Invoke(..., CostUSDC: "0.05")` | `invoke(..., costUsdc="0.05")` | `InvokeAsync(..., CostUsdc="0.05")` | `POST /api/v1/agent/invoke` | Pass string amount from discovery; do not recompute with floats. |
| Token-metered LLM invoke | `invoke_llm(..., max_cost_usdc="0.10")` | `invokeLlm(..., { maxCostUsdc: "0.10" })` | `InvokeLLM(..., MaxCostUSDC: "0.10")` | `invokeLlm(..., maxCostUsdc="0.10")` | `InvokeLlmAsync(..., MaxCostUsdc="0.10")` | `POST /api/v1/agent/invoke` | Do not send fixed-price cost; Gateway bills final provider usage. |
| Invocation receipt | `get_invocation()` / `get_invocation_receipt()` | `getInvocation()` / `getInvocationReceipt()` | `GetInvocation()` | `getInvocation()` | `GetInvocationAsync()` | `GET /api/v1/agent/invocations/{id}` | Always read receipts after invoke. |
| Gateway health | `check_gateway_health()` | `checkGatewayHealth()` | `CheckGatewayHealth()` | `health()` | `HealthAsync()` | `GET /health` | Does not consume agent budget. |

## Owner Control Plane

| Capability | Python SDK | TypeScript SDK | Gateway route |
|---|---|---|---|
| Wallet auth | `SynapseAuth.from_private_key()`, `get_token()` | `SynapseAuth.fromWallet()`, `getToken()` | `/api/v1/auth/challenge`, `/api/v1/auth/verify` |
| Agent credentials | `issue_credential()`, `list_credentials()`, `revoke_credential()`, `update_credential_quota()` | `issueCredential()`, `listCredentials()`, `revokeCredential()`, `updateCredentialQuota()` | `/api/v1/credentials/agent/*` |
| Balance and deposit | `get_balance()`, `register_deposit_intent()`, `confirm_deposit()` | `getBalance()`, `registerDepositIntent()`, `confirmDeposit()` | `/api/v1/balance*` |
| Usage and limits | `get_usage_logs()`, `set_spending_limit()` | `getUsageLogs()`, `setSpendingLimit()` | `/api/v1/usage/logs`, `/api/v1/balance/spending-limit` |

## Provider Publishing

| Capability | Python SDK | TypeScript SDK | Gateway route |
|---|---|---|---|
| Provider facade | `auth.provider()` / `SynapseProvider` | `auth.provider()` / `SynapseProvider` | Owner JWT scoped |
| Registration guide | `get_registration_guide()` | `getRegistrationGuide()` | `GET /api/v1/services/registration-guide` |
| Service lifecycle | `register_service()`, `list_services()`, `update_service()`, `delete_service()`, `ping_service()` | `registerService()`, `listServices()`, `updateService()`, `deleteService()`, `pingService()` | `/api/v1/services*` |
| Health and earnings | `get_service_status()`, `get_service_health_history()`, `get_earnings_summary()` | `getServiceStatus()`, `getServiceHealthHistory()`, `getEarningsSummary()` | `/api/v1/services/*`, `/api/v1/providers/earnings/summary` |
| Provider withdrawals | `get_withdrawal_capability()`, `create_withdrawal_intent()`, `list_withdrawals()` | `getWithdrawalCapability()`, `createWithdrawalIntent()`, `listWithdrawals()` | `/api/v1/providers/withdrawals*` |

## Documentation Rules

1. Public docs should point developers to SDK methods before raw REST routes.
2. Public docs should say staging, Arbitrum Sepolia, and MockUSDC until production launch.
3. Public docs must not show private local gateway setup as the public SDK onboarding path.
4. Public SDK examples should use `SYNAPSE_AGENT_KEY`, string money values, and named result objects.
