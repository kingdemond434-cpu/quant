---
id: L0209
cost: blind
---

# L0209

Offset-scan every externally-sourced price tape against desk truth before adoption, and measure liveness/cadence on the SERIES you will use, never on its file or its metadata.

## Evidence

HF CarlosSilva1/xauusd-ticks (cc-by-4.0, ms bid/ask) ships timestamps 2h behind UTC, undocumented: ingested as-is a model stamped 08:00 reads 10:00 prices -- a look-ahead that fails toward a FALSE POSITIVE. Only a -4h..+2h scan vs desks/mt5/data/universe/XAUUSD_H1.parquet found it (+2h mean -0.111 sd 0.138; all other offsets sd>6); the -0.111 residual is half the desk's own spread and confirms desk close=bid. Same run: Bundesbank BBMMU declares FREQ=D and P1D but holds 76 obs at 35-56 day gaps (ECB maintenance periods), and its bank-only ON series died 2023-10-31 INSIDE a file live to 2026-07-28 -- I computed a clean-looking +4.5bp ESTR tracking result on the dead series before checking its last observation.

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
