---
id: L0076
cost: blind
tags: ["validation"]
---

# L0076

Counting dated rows is not counting observations, and the failure does not stay harmless. A clock re-stamping one measurement, or a signal whose sign is 0 so no position is taken, produces rows that look like accrual and then cross the sample-size bar -- at which point a zero-variance return series has t=0 and reads as a REFUTED hypothesis. A broken instrument masquerading as a dead axis is a false null, the direction that raises no alarm.

## Evidence

R0257: forward_days counted any date-keyed pair while its own comment claimed it excluded degenerate rows. 3 of 4 live forward clocks were faulty -- walcl_reserve_impulse 3 rows/1 distinct payload (daily cron vs weekly FRED release), defi_utilisation no position on 4 of 5 days, cny_premium 14 rows with a null signal field -- all reporting ACCRUING. defi was 15 flat days from publishing FAILING. Fixed 3ea1fca.

## Tags

#validation

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
