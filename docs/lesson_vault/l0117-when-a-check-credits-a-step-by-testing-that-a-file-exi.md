---
id: L0117
cost: blind
tags: ["governance", "fences"]
enforced_by: tests/scripts/test_promotion_gate.py::test_output_name_does_not_collide_with_the_hourly_ladder_writer
---

# L0117

When a check credits a step by testing that a FILE EXISTS, prove that step is the file's only writer. A second script writing the same name turns the existence test into a permanent pass, and the no-op it was meant to catch becomes invisible.

## Evidence

scripts/promotion_gate.py wrote data/promotion_gate.json, the name check_promotion_gate.py rewrites hourly; run_cadence credited promotion-gate every cycle while the eight-gate barrier had judged 0 candidates ever (R0353)

## Enforced by

`tests/scripts/test_promotion_gate.py::test_output_name_does_not_collide_with_the_hourly_ladder_writer`

## Tags

#governance #fences

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
