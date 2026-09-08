---
id: L0269
cost: the desk's most important state dimension unjudged since it was written
tags: ["broker-clock", "session", "state-admission", "fallbacks"]
---

# L0269

A fallback chain whose only writer never fires is a chain with one tier. `session_phase.broker_utc_offset_h` resolved live terminal -> data/broker_clock.json -> None, and that file names the gateway as its only writer and had never been written -- so off the box the answer was always None, `state_admission` reported session as a gap, and conditional allocation ran on weekday (RETAIN_SHRUNK, no measurable gain) and event (1 bucket). The offset was in the desk's own bars the whole time: the daily rollover trough is the sharpest feature of any FX day. When a fallback depends on a producer, TEST THAT THE PRODUCER HAS RUN, and prefer a tier that derives from data the desk already holds over one that needs a machine it does not have.

## Evidence

10 majors place the volume trough at stamp hour 00 (8-14% of the median hour), unanimously +2 vs the 22:00 UTC rollover; session went UNJUDGED -> RETAIN_SHRUNK, 8 buckets, 258 test trades, t=-1.57

## Tags

#broker-clock #session #state-admission #fallbacks

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0010-textbook-mechanisms-on-daily-bars-are-picked-clean-spe]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
