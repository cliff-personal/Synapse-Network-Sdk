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

1. [WARN] `python/examples/consumer_wallet_to_invoke.py::main` line=74 metrics=(lines=78, branches=7, nesting=3, locals=18)
   - token: `hotspot-664c48761084`
   - issues: `lines=78>40, branches=7>5, locals=18>8, nesting=3, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-664c48761084`
2. [WARN] `python/examples/smoke_test.py::main` line=345 metrics=(lines=104, branches=6, nesting=2, locals=13)
   - token: `hotspot-8ec9b16a0f08`
   - issues: `lines=104>40, branches=6>5, locals=13>8, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-8ec9b16a0f08`
3. [WARN] `python/examples/consumer_call_provider.py::main` line=116 metrics=(lines=42, branches=4, nesting=2, locals=10)
   - token: `hotspot-c6270384bbbf`
   - issues: `lines=42>40, locals=10>8, branches=4, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-c6270384bbbf`
4. [WARN] `python/synapse_client/test/test_consumer_e2e.py::test_python_sdk_consumer_cold_start_e2e` line=174 metrics=(lines=135, branches=0, nesting=0, locals=30)
   - token: `hotspot-402833792f1b`
   - issues: `lines=135>40, locals=30>8, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-402833792f1b`
5. [WARN] `python/examples/provider_staging_onboarding.py::main` line=91 metrics=(lines=46, branches=2, nesting=1, locals=9)
   - token: `hotspot-41fb390a7399`
   - issues: `lines=46>40, locals=9>8, missing_guiding_comment`
   - bundle command: `amem refactor-bundle . --token hotspot-41fb390a7399`

## Suggested Action

1. Run `amem refactor-bundle .` to materialize the first hotspot into an executable planning bundle.
2. If a hotspot cannot be split yet, add a guiding comment that explains the main decision path and risk boundaries.
3. Re-run `amem doctor .` after the change and confirm `refactor_watch` findings shrink or disappear.
