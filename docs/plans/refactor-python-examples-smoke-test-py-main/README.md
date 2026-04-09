---
created_at: 2026-04-09
updated_at: 2026-04-09
doc_status: active
---

# Refactor hotspot: python/examples/smoke_test.py::main

这是当前任务的 planning bundle。

建议使用顺序：

1. 先写 `spec.md`
2. 再补 `plan.md`
3. 再确认 `task-graph.md`
4. 最后在 `validation.md` 里写最小验证路线

## Refactor Hotspot
- hotspot: `python/examples/smoke_test.py::main`
- hotspot token: `hotspot-8ec9b16a0f08`
- current rank index: `1`
- line: `376`
- status: `WARN`
- issues: `lines=101>40, locals=12>8, branches=5, missing_guiding_comment`
- bundle entry command: `amem refactor-bundle . --token hotspot-8ec9b16a0f08`
- verify with: `amem doctor .`
