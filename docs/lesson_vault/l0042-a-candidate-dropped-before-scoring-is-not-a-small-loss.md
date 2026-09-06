---
id: L0042
cost: wasted
tags: ["statistics"]
enforced_by: tests/autodiscovery/test_gate_wiring.py::test_supplying_the_input_moves_a_gate_out_of_unmeasured
---

# L0042

A candidate dropped before scoring is not a small loss, it is an unmeasured one. Count what a filter discarded and report it, or the pipeline's own accounting hides its worst decisions.

## Evidence

ADVERSARIAL_REVIEW_RUBRIC class 8; the same asymmetry that makes a pre-filter's false negatives structurally invisible (L0017)

## Enforced by

`tests/autodiscovery/test_gate_wiring.py::test_supplying_the_input_moves_a_gate_out_of_unmeasured`

## Tags

#statistics

## Related

- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0165-enumerate-a-bulk-archive-with-curl-raw-counts-never-th]]
- [[l0182-measure-a-producer-s-health-as-usable-output-never-as-]]
- [[l0204-before-reporting-a-file-as-missing-ask-whether-this-ho]]
