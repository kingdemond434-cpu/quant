---
id: L0304
cost: blind
tags: ["families", "total-functions"]
---

# L0304

bool() on a pandas Index or Series RAISES rather than answering, so `if not x` on a container argument is a landmine that takes down the whole sweep. Test emptiness with len() behind an `is None` guard. A family may refuse a cell; it may not raise.

## Evidence

2026-09-12: family_event_reaction's `if not events` raised ValueError on a DatetimeIndex and MT5-Gauntlet exited 1 mid-docket, losing an hour of certificates for every OTHER cell too. A second identical landmine sat four lines below in _event_times (`for e in events or ()`), so fixing only the first moved the crash from an empty index to a non-empty one.

## Tags

#families #total-functions

## Related

- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
