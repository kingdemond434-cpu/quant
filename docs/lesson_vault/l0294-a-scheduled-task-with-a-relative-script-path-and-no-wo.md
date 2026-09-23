---
id: L0294
cost: blind
tags: ["ops", "scheduler"]
---

# L0294

A scheduled task with a RELATIVE script path and no working directory never runs, and Windows reports it as 'file not found' -- which reads as a missing script rather than a missing cwd. Register every task with the ABSOLUTE interpreter and an explicit working directory.

## Evidence

2026-09-12: MT5-IdentityHealer ran `python -W ignore scripts\heal_identity_broken_clocks.py --apply` with no cwd, so the scheduler started it in System32. Result code 2 forever; 20+ forward clocks sat IDENTITY BROKEN against a healer that had NEVER ONCE RUN. The script was present and correct the whole time. Fixed -> rc=0, 'no IDENTITY_BROKEN clocks'.

## Tags

#ops #scheduler

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
