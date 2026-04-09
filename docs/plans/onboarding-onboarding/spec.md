---
created_at: 2026-04-09
updated_at: 2026-04-09
doc_status: active
---

# Spec

## Task

Shared Engineering Brain onboarding: onboarding

## Problem

- 当前问题是什么？

## Goal

- 这次变更要达成什么结果？

## Non-Goals

- 这次不解决什么？

## Acceptance Criteria

- [ ] 有明确可验证的功能结果
- [ ] 有对应 docs / code / tests 同步要求
- [ ] 验收标准可被测试或命令验证

## Onboarding Inputs
- state file: `.agents-memory/onboarding-state.json`

```json
[
  {
    "name": "Core",
    "status": "HEALTHY",
    "summary": "Core status=HEALTHY (ok=7, warn=0, fail=0, info=0)",
    "checks": [
      {
        "status": "OK",
        "key": "registry",
        "detail": "registered as 'synapse-network-sdk'"
      },
      {
        "status": "OK",
        "key": "active",
        "detail": "active=true"
      },
      {
        "status": "OK",
        "key": "root",
        "detail": "."
      },
      {
        "status": "OK",
        "key": "python3.12",
        "detail": "/opt/homebrew/bin/python3.12"
      },
      {
        "status": "OK",
        "key": "mcp_package",
        "detail": "mcp import OK"
      },
      {
        "status": "OK",
        "key": "profile_manifest",
        "detail": "applied profile 'python-service'"
      },
      {
        "status": "OK",
        "key": "profile_consistency",
        "detail": "profile 'python-service' consistency OK"
      }
    ]
  },
  {
    "name": "Planning",
    "status": "HEALTHY",
    "summary": "Planning status=HEALTHY (ok=2, warn=0, fail=0, info=0)",
    "checks": [
      {
        "status": "OK",
        "key": "planning_root",
        "detail": "present: ./docs/plans"
      },
      {
        "status": "OK",
        "key": "planning_bundle",
        "detail": "0 planning bundle(s) passed plan-check"
      }
    ]
  },
  {
    "name": "Integration",
    "status": "HEALTHY",
    "summary": "Integration status=HEALTHY (ok=2, warn=0, fail=0, info=0)",
    "checks": [
      {
        "status": "OK",
        "key": "bridge_instruction",
        "detail": "./.github/instructions/agents-memory-bridge.instructions.md"
      },
      {
        "status": "OK",
        "key": "mcp_config",
        "detail": "agents-memory server configured -> ./.vscode/mcp.json"
      }
    ]
  },
  {
    "name": "Optional",
    "status": "WATCH",
    "summary": "Optional status=WATCH (ok=2, warn=5, fail=0, info=0)",
    "checks": [
      {
        "status": "OK",
        "key": "copilot_activation",
        "detail": "Agents-Memory activation block present -> ./.github/copilot-instructions.md"
      },
      {
        "status": "OK",
        "key": "agents_read_order",
        "detail": "AGENTS.md references current bridge and 8 managed standard(s)"
      },
      {
        "status": "WARN",
        "key": "refactor_watch",
        "detail": "python/examples/smoke_test.py::main high complexity (lines=101>40, locals=12>8, branches=5, missing_guiding_comment)"
      },
      {
        "status": "WARN",
        "key": "refactor_watch",
        "detail": "python/synapse_client/test/test_consumer_e2e.py::test_python_sdk_consumer_cold_start_e2e high complexity (lines=134>40, locals=30>8, missing_guiding_comment)"
      },
      {
        "status": "WARN",
        "key": "refactor_watch",
        "detail": "python/synapse_client/test/test_consumer_e2e.py::_fund_and_deposit high complexity (lines=57>40, locals=15>8, missing_guiding_comment)"
      },
      {
        "status": "WARN",
        "key": "refactor_watch",
        "detail": "python/synapse_client/test/test_consumer_e2e.py::test_python_sdk_credential_management_e2e high complexity (lines=75>40, locals=25>8)"
      },
      {
        "status": "WARN",
        "key": "refactor_watch",
        "detail": "python/synapse_client/auth.py::SynapseAuth.issue_credential high complexity (branches=7>5, lines=38, locals=8, missing_guiding_comment)"
      }
    ]
  }
]
```
