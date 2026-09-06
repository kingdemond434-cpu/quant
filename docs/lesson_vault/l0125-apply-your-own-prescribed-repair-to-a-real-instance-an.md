---
id: L0125
cost: blind
tags: ["governance"]
enforced_by: tests/ops/test_attrition.py::test_attempted_tally_before_first_skip_is_not_a_finding
---

# L0125

Apply your own prescribed repair to a real instance and re-run the new detector before shipping it. A fence that still fires after the exact fix it demands trains the desk to ignore it, and that is indistinguishable from never having built it.

## Evidence

L1.60 build 2026-08-12: after check_llm_routing got the prescribed "attempted += 1" above its first skip, check_denominator_attrition still reported ATTRITION on it -- the detector recognised only per-skip discard counting, never the single-tally repair its own law prescribes. Fixed by _counts_attempts_before in libs/ops/attrition.py.

## Enforced by

`tests/ops/test_attrition.py::test_attempted_tally_before_first_skip_is_not_a_finding`

## Tags

#governance

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
