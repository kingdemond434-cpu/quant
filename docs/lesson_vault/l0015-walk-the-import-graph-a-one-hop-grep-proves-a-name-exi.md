---
id: L0015
cost: blind
tags: ["verification"]
---

# L0015

Walk the import graph. A one-hop grep proves a name exists somewhere, never that the code path runs -- and a gate nobody calls always returns True.

## Evidence

benchmark_returns had zero production callers, so beats_baselines passed unconditionally for every candidate the desk ever screened. libs/autodiscovery/validation.py

## Tags

#verification

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
