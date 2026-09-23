---
id: L0017
cost: slow
tags: ["discovery", "design"]
enforced_by: tests/research/test_mined_evidence_priority.py::test_no_prefilter_before_the_gauntlet
---

# L0017

A pre-filter's false negatives are structurally invisible and its false positives cost one paragraph. That asymmetry decides every discovery filter: read it all, let the measured gauntlet reject.

## Evidence

principal order 2026-08-01; the scam filter was removed from all 11 miner prompts because a source discarded before reading leaves no trace to audit

## Enforced by

`tests/research/test_mined_evidence_priority.py::test_no_prefilter_before_the_gauntlet`

## Tags

#discovery #design

## Related

- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0042-a-candidate-dropped-before-scoring-is-not-a-small-loss]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
