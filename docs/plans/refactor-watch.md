# Refactor Watch

- Project: `synapse-network-sdk`
- Root: `/Users/cliff/workspace/agent/Synapse-Network-Sdk`

## Purpose

Track Python functions that are already high-complexity or are approaching the configured refactor thresholds.

## Thresholds

- Hard gate: more than 40 effective lines, more than 5 control-flow branches, nesting depth >= 4, or more than 8 local variables.
- Watch zone: around 30 effective lines, 4 branches, nesting depth 3, or 6 local variables.
- Complex logic should include a short guiding comment when it cannot be cleanly decomposed yet.

## Workflow Entry

- Primary command: `amem refactor-bundle .`
- Prefer stable targeting with: `amem refactor-bundle . --token <hotspot-token>`
- Fallback positional targeting: `amem refactor-bundle . --index <n>`
- The command creates or refreshes `docs/plans/refactor-<slug>/` using the first current hotspot as execution context.

## Hotspots

1. [WARN] `python/examples/smoke_test.py::main` line=376 metrics=(lines=101, branches=5, nesting=2, locals=12)
   - token: `hotspot-8ec9b16a0f08`
   - issues: `lines=101>40, locals=12>8, branches=5, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-8ec9b16a0f08`
2. [WARN] `python/synapse_client/test/test_consumer_e2e.py::test_python_sdk_consumer_cold_start_e2e` line=175 metrics=(lines=134, branches=0, nesting=0, locals=30)
   - token: `hotspot-402833792f1b`
   - issues: `lines=134>40, locals=30>8, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-402833792f1b`
3. [WARN] `python/synapse_client/test/test_consumer_e2e.py::_fund_and_deposit` line=77 metrics=(lines=57, branches=0, nesting=0, locals=15)
   - token: `hotspot-7f5cb8d7d075`
   - issues: `lines=57>40, locals=15>8, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-7f5cb8d7d075`
4. [WARN] `python/synapse_client/test/test_consumer_e2e.py::test_python_sdk_credential_management_e2e` line=327 metrics=(lines=75, branches=1, nesting=1, locals=25)
   - token: `hotspot-26c3a2e1a320`
   - issues: `lines=75>40, locals=25>8`
   - bundle command: `amem refactor-bundle . --token hotspot-26c3a2e1a320`
5. [WARN] `python/synapse_client/auth.py::SynapseAuth.issue_credential` line=198 metrics=(lines=38, branches=7, nesting=2, locals=8)
   - token: `hotspot-4ede4034d9f9`
   - issues: `branches=7>5, lines=38, locals=8, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-4ede4034d9f9`

## Suggested Action

1. Run `amem refactor-bundle .` to materialize the first hotspot into an executable planning bundle.
2. If a hotspot cannot be split yet, add a guiding comment that explains the main decision path and risk boundaries.
3. Re-run `amem doctor .` after the change and confirm `refactor_watch` findings shrink or disappear.
