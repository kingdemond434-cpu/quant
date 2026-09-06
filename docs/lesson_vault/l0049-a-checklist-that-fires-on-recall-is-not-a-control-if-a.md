---
id: L0049
cost: blind
tags: ["verification", "design"]
---

# L0049

A checklist that fires on recall is not a control. If a review rubric is not injected at call time it works only when someone remembers it -- wire it, and audit that it still parses.

## Evidence

ADVERSARIAL_REVIEW_RUBRIC.md had ONE repo reference (a max_audit exclusion) and was injected nowhere; remembering it on 2026-08-01 caught 3 real defects in code written that morning. libs/research/review_rubric.py

## Tags

#verification #design

## Related

- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
