# TypeScript SDK Bug Log

Historical TypeScript E2E bugs from the retired non-staging test harness have been archived out of the public SDK guidance.

Current SDK validation uses:

1. Unit tests in the default PR gate.
2. Staging-gated consumer E2E tests when `RUN_STAGING_E2E=1`.
3. Staging-gated provider E2E tests when `RUN_STAGING_PROVIDER_E2E=1`.

Do not reintroduce non-staging gateway setup instructions into public SDK docs or tests.
