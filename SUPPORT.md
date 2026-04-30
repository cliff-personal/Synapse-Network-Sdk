# Support

## Public Preview Support

The SDK is currently documented for staging public preview:

- Gateway: `https://api-staging.synapse-network.ai`
- App docs: `https://staging.synapse-network.ai/docs/sdk`
- Chain: Arbitrum Sepolia
- Asset: MockUSDC, not production USDC

Developers should validate integrations on staging before any future production migration.

## Before Opening an Issue

Please include:

- SDK language and version.
- Whether you are using fixed-price `invoke()` / `invoke` or token-metered `invoke_llm()` / `invokeLlm()`.
- Gateway environment, normally `staging`.
- Request ID and idempotency key if an invocation failed.
- Redacted error payloads and stack traces.

Never paste private keys, seed phrases, real credentials, or production tokens.

## Security Reports

Use `SECURITY.md` for vulnerability reports or credential exposure concerns.
