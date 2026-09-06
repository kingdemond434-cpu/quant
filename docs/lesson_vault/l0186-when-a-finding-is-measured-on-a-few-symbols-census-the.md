---
id: L0186
cost: blind
tags: ["clock"]
---

# L0186

When a finding is measured on a few symbols, census the WHOLE store before generalising it -- and check the dtype, not just the values. A tz-AWARE index falsely stamped UTC absorbs tz_convert("UTC") as a SILENT NO-OP that preserves the entire error while passing mypy, so the wrong clock is invisible to every type-level check. Also: a boundary pinned to server-local time is label-constant BY CONSTRUCTION and can never identify the offset -- only a PRICE-anchored fit to an externally-timed event discriminates.

## Evidence

desks/mt5/data/universe/*_H1.parquet 2026-08-27 census: 24 tz-aware / 173 tz-naive (= GAP #148 split). R0660 was measured on XAUUSD+EURUSD+USDJPY, all 3 in the aware 24 (12% of lake). Re-confirmed on the naive half: LBMA platinum_pm 14:00 London vs XPTUSD_H1 n=609, bar 15 sd 26.3bps summer/34.9 winter vs 60-115 adjacent. FX Friday-last label = 23 in EVERY US/EU DST mismatch window 2025-2026 => non-discriminating; the 08-26 week-boundary argument withdrawn.

## Tags

#clock

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0027-a-constant-that-was-never-measured-is-a-guess-wearing-]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
