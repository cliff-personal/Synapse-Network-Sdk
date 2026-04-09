# Bootstrap Checklist

- Project: `synapse-network-sdk`
- Root: `/Users/cliff/workspace/agent/Synapse-Network-Sdk`
- Overall: `READY`

## Checklist
- [x] Core - Core status=HEALTHY (ok=7, warn=0, fail=0, info=0)
- [x] Planning - Planning status=HEALTHY (ok=2, warn=0, fail=0, info=0)
- [x] Integration - Integration status=HEALTHY (ok=2, warn=0, fail=0, info=0)
- [ ] Optional - Optional status=WATCH (ok=2, warn=5, fail=0, info=0)
- [x] Final verification - latest `amem doctor .` already reflects the current healthy state

## Action Sequence
1. Optional (recommended): Refactor flagged functions before adding more behavior, and add a short guiding comment when complex logic must remain in place.
## Group Health
### Core
- Summary: Core status=HEALTHY (ok=7, warn=0, fail=0, info=0)
- [OK] `registry` registered as 'synapse-network-sdk'
- [OK] `active` active=true
- [OK] `root` /Users/cliff/workspace/agent/Synapse-Network-Sdk
- [OK] `python3.12` /opt/homebrew/bin/python3.12
- [OK] `mcp_package` mcp import OK
- [OK] `profile_manifest` applied profile 'python-service'
- [OK] `profile_consistency` profile 'python-service' consistency OK

### Planning
- Summary: Planning status=HEALTHY (ok=2, warn=0, fail=0, info=0)
- [OK] `planning_root` present: /Users/cliff/workspace/agent/Synapse-Network-Sdk/docs/plans
- [OK] `planning_bundle` 0 planning bundle(s) passed plan-check

### Integration
- Summary: Integration status=HEALTHY (ok=2, warn=0, fail=0, info=0)
- [OK] `bridge_instruction` /Users/cliff/workspace/agent/Synapse-Network-Sdk/.github/instructions/agents-memory-bridge.instructions.md
- [OK] `mcp_config` agents-memory server configured -> /Users/cliff/workspace/agent/Synapse-Network-Sdk/.vscode/mcp.json

### Optional
- Summary: Optional status=WATCH (ok=2, warn=5, fail=0, info=0)
- [OK] `copilot_activation` Agents-Memory activation block present -> /Users/cliff/workspace/agent/Synapse-Network-Sdk/.github/copilot-instructions.md
- [OK] `agents_read_order` AGENTS.md references current bridge and 8 managed standard(s)
- [WARN] `refactor_watch` python/examples/smoke_test.py::main high complexity (lines=101>40, locals=12>8, branches=5, missing_guiding_comment)
- [WARN] `refactor_watch` python/synapse_client/test/test_consumer_e2e.py::test_python_sdk_consumer_cold_start_e2e high complexity (lines=134>40, locals=30>8, missing_guiding_comment)
- [WARN] `refactor_watch` python/synapse_client/test/test_consumer_e2e.py::_fund_and_deposit high complexity (lines=57>40, locals=15>8, missing_guiding_comment)
- [WARN] `refactor_watch` python/synapse_client/test/test_consumer_e2e.py::test_python_sdk_credential_management_e2e high complexity (lines=75>40, locals=25>8)
- [WARN] `refactor_watch` python/synapse_client/auth.py::SynapseAuth.issue_credential high complexity (branches=7>5, lines=38, locals=8, missing_guiding_comment)
