---
id: L0144
cost: capital
tags: ["merge"]
enforcement_retired: tests/execution/test_carry_entry_gate.py::test_fence_reads_all_time_key_not_the_rolling_one -- deleted with the retired crypto desk (MT5 universe mandate 2026-08-18); the property is no longer enforced by anything, so this lesson is back at full weight
---

# L0144

A PERSISTENTLY RED TEST IS A DISABLED GATE, so triage red by SUBJECT before blaming the environment. A merge that keeps one lineage's tests and the other's code leaves the tests asserting the truth and the code contradicting it -- the suite tells you exactly what was lost, and the longer it stays red the more readers learn to discount it. Diff the failing test's expectations against the module it imports, and if the module lacks a symbol the test names, git log -S that symbol to find the commit that removed it.

## Evidence

2026-08-13: tests/execution/test_carry_entry_gate.py asserted the fence reads bleeding_symbols; scripts/run_trade_forensics.py had 0 occurrences of it. git show per-sha: a0026d98 producer=2 reader=2, merge 8b981a50 producer=0 reader=0. The structural-bleed denylist ran on the 14d rolling window for 8 days -- web/trade_forensics.json worst_symbols == [] against 6 all-time bleeders (NOMUSDT -149.4bps, COMPUSDT -106.4, ONEUSDT -92.4, 1000CATUSDT -74.6, BNBUSDT -65.8, PEOPLEUSDT -62.4), so the fence denied 0 of 6 while the book was paused on a drawdown.

## Tags

#merge

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
