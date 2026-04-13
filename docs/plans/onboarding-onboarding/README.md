---
created_at: 2026-04-09
updated_at: 2026-04-09
doc_status: active
---

# Shared Engineering Brain onboarding: onboarding

这是当前任务的 planning bundle。

建议使用顺序：

1. 先写 `spec.md`
2. 再补 `plan.md`
3. 再确认 `task-graph.md`
4. 最后在 `validation.md` 里写最小验证路线

## Onboarding State
- state file: `.agents-memory/onboarding-state.json`
- bootstrap ready: `yes`
- bootstrap complete: `yes`
- next group: `Refactor`
- next key: `refactor_bundle`
- next command: `python3 scripts/memory.py refactor-bundle . --token hotspot-8ec9b16a0f08`
- verify with: `amem doctor .`
- done when: `amem doctor .` no longer reports `python/examples/smoke_test.py::main` as the top refactor hotspot.
