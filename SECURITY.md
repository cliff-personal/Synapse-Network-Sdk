# Security Policy

## Public Preview Boundary

The SDK defaults to the Synapse public preview gateway:

```text
https://api-staging.synapse-network.ai
```

Staging is for test assets and integration trials. Production credentials, production private keys, and live-funds workflows must only be used after the official production gateway DNS and `/health` endpoint are verified.

## Secrets

Never commit or publish:

- Agent credentials
- JWT access tokens
- Provider secrets
- Wallet private keys
- Wallet mnemonics
- RPC provider API keys
- Production logs containing request headers or authorization data

Use environment variables, a secret manager, or your runtime platform's encrypted secret store.

## If a Credential Leaks

1. Stop using the leaked credential immediately.
2. Rotate or revoke it from the Synapse control plane when available.
3. Remove the leaked value from logs, screenshots, PRs, issues, and agent context.
4. Treat any related wallet or provider key as compromised if it was exposed together with the credential.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the project maintainers instead of opening a public GitHub issue with exploit details or secrets.

Include:

- Affected SDK language and version or commit SHA
- Gateway environment used (`local`, `staging`, or `prod`)
- Minimal reproduction steps
- Whether any credentials, private keys, or funds may be exposed

Do not include real secrets in the report body. If secret material was exposed, say so and coordinate secure transfer or revocation with the maintainers.

## Release Checks

Before publishing an SDK release, run:

```bash
git ls-files | rg '(^|/)\\.env|private|secret|key|pem|wallet|mnemonic|credential' | rg -v '(^|/)\\.env\\.example$'
rg 'gateway\\.synapse\\.network' .
```

The first command should not show committed secret-bearing files after the `.env.example` allowlist. The second command should not show SDK references to the stale gateway domain.
