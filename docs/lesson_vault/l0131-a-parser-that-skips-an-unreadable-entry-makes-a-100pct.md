---
id: L0131
cost: blind
tags: ["data"]
enforcement_retired: tests/scripts/test_build_bars.py::test_bybit_price_time_shape_is_read_R0378 -- deleted with the retired crypto desk (MT5 universe mandate 2026-08-18); the property is no longer enforced by anything, so this lesson is back at full weight
---

# L0131

A parser that SKIPS an unreadable entry makes a 100pct schema mismatch look exactly like a quiet venue.

## Evidence

trades_from read bybit's p/T/v while the recorder wrote price/time/size: 221,000 of 221,000 sampled entries unread, the whole 10,814-partition bybit tape invisible to 3 consumers; the screen reported NO-INPUT and read as a data-poor venue. Commit 02f2e24a.

## Tags

#data

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0041-any-objective-defined-over-a-partition-can-be-gamed-by]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0073-a-rail-s-reference-point-and-a-performance-number-may-]]
- [[l0076-counting-dated-rows-is-not-counting-observations-and-t]]
- [[l0088-a-guard-that-fails-closed-on-a-missing-data-file-must-]]
- [[l0094-a-coverage-metric-pinned-exactly-constant-for-hundreds]]
- [[l0109-do-not-trust-clock-provenance-sort-key-to-linearise-a-]]
