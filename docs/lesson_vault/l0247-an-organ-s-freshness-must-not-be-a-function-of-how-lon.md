---
id: L0247
cost: a permanent red board nobody would read
tags: ["scheduling", "staleness", "issue-board", "thresholds"]
---

# L0247

An organ's freshness must not be a function of how long some other pipeline takes. Eleven producers declared a 3600s cadence and were reachable only as legs of a 55-leg cycle that grew past an hour; issue_board is itself a leg of that cycle and runs BEFORE the reports it measures, so their measured age is one full cycle duration and they read STALLED on every pass while running perfectly. The fix is a clock of their own -- raising STALE_TOLERANCE would silence the alarm and leave the artifacts exactly as old, which is the loosening this desk does not do.

## Evidence

issue_board last wrote 12:37 and had not run again by 13:49 (72 min); four reports reported 6.6-6.7h against a 1.0h cadence

## Tags

#scheduling #staleness #issue-board #thresholds

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
