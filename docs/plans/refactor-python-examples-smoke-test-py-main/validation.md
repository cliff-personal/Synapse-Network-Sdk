---
created_at: 2026-04-09
updated_at: 2026-04-09
doc_status: active
---

# Validation Route

## Required Checks

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile $(find agents_memory scripts -name '*.py' -print)
python3 scripts/memory.py docs-check .
```

## Task-Specific Checks

- 写下本任务额外需要跑的命令

## Review Notes

- docs diff:
- code diff:
- test diff:

## Refactor Verification
- primary verification command: `amem doctor .`
- expected outcome: `python/examples/smoke_test.py::main` is no longer the first hotspot, or its issue list is smaller.

## Hotspot Snapshot
```json
{
  "identifier": "python/examples/smoke_test.py::main",
  "rank_token": "hotspot-8ec9b16a0f08",
  "relative_path": "python/examples/smoke_test.py",
  "function_name": "main",
  "qualified_name": "main",
  "line": 376,
  "status": "WARN",
  "effective_lines": 101,
  "branches": 5,
  "nesting": 2,
  "local_vars": 12,
  "has_guiding_comment": false,
  "issues": [
    "lines=101>40",
    "locals=12>8",
    "branches=5",
    "missing_guiding_comment"
  ],
  "score": 22
}
```
