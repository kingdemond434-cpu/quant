---
id: L0302
cost: blind
tags: ["ops", "deployment"]
---

# L0302

Shipping a caller before its callee is a self-inflicted outage that looks like a logic bug. Deploy the definition first, or deploy both in one transfer, and verify the import on the target before walking away.

## Evidence

2026-09-12: external_gauntlet.py shipped calling fail_closed_trial_count before gate_policy.py defining it. The gauntlet crashed with ImportError for an hour, produced no certificates, AND took the poison-canary suite down with it -- which then reported that every certificate the desk holds is void.

## Tags

#ops #deployment

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
