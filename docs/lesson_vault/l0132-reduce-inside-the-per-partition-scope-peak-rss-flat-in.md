---
id: L0132
cost: wasted
tags: ["memory"]
enforcement_retired: tests/research/test_orderbook_state_screen.py::test_peak_memory_does_not_grow_with_partition_count -- deleted with the retired crypto desk (MT5 universe mandate 2026-08-18); the property is no longer enforced by anything, so this lesson is back at full weight
---

# L0132

Reduce INSIDE the per-partition scope: peak RSS FLAT in the file budget means the LOAD PATH, not the budget, is the cost.

## Evidence

screen_orderbook_state held ~23MB of parsed dicts per partition (~550MB/day-cell), OOM-killed at every budget; deriving per partition took peak to a flat 255-258MB, bit-identical (per-row maps + one STABLE sort). Commit 02f2e24a.

## Tags

#memory

## Related

- [[l0129-never-read-a-clean-git-status-as-evidence-your-output-]]
- [[l0177-syntax-check-with-compile-never-ast-parse-or-a-linter-]]
- [[l0225-a-date-stamp-that-records-that-a-job-ran-never-what-it]]
