---
id: L0177
cost: blind
tags: ["gates"]
enforced_by: tests/ops/test_ci_gate_timeouts.py::TestTheCompilePassIsGated::test_run_ci_has_a_compile_step
---

# L0177

Syntax-check with compile(), never ast.parse or a linter. 'await' outside 'async' -- the whole symbol-table class -- is accepted by every AST-level tool, so ruff, mypy, pytest --co AND ast.parse all pass on a file that 'import' cannot load.

## Evidence

2026-08-26: scripts/liquidation_listener.py held 'await asyncio.sleep(30)' in a plain def; ruff on that HEAD file printed 'All checks passed!' while the desk-wide CI sat RED 21h. Adding compileall to ops/gates.sh found 2 MORE files that had never been importable.

## Enforced by

`tests/ops/test_ci_gate_timeouts.py::TestTheCompilePassIsGated::test_run_ci_has_a_compile_step`

## Tags

#gates

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
