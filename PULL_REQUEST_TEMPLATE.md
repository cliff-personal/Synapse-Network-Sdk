## Summary

-

## Validation

- [ ] `bash scripts/ci/pr_checks.sh`

## Public SDK Contract Checklist

- [ ] Public examples use `SYNAPSE_AGENT_KEY`.
- [ ] Public docs/examples point to staging, Arbitrum Sepolia, and MockUSDC where environment details are needed.
- [ ] Fixed-price examples pass discovered prices as strings.
- [ ] Token-metered LLM examples use `invoke_llm()` / `invokeLlm()` without `cost_usdc` / `costUsdc`.
- [ ] Public `SynapseAuth` / `SynapseProvider` returns use named models/interfaces, not raw maps.
- [ ] No private keys, seed phrases, credentials, or production tokens are committed.
