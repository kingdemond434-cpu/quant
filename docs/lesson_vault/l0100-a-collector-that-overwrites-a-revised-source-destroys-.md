---
id: L0100
cost: blind
tags: ["collector"]
---

# L0100

A collector that OVERWRITES a revised source destroys data nobody can re-buy, and no freshness fence can see it: the file is young, well-formed and passes every check on the day it is written. Ask of any collector: does re-running it LOSE anything? An idempotent overwrite is only safe when the source never restates.

## Evidence

2026-08-12 R0316: scripts/collect_fred_macro.py did _ARCHIVE.write_text() plus a rolling 1200-day observation_start, so each daily run destroyed the prior vintage of M2SL/WALCL -- series FRED restates. ~1 month of free daily vintages already lost. Its own docstring called the overwrite 'idempotent, self-healing'. Found by scoping a ledger row, not by any fence.

## Tags

#collector

## Related

- [[l0010-textbook-mechanisms-on-daily-bars-are-picked-clean-spe]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
