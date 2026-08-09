# Pre-registration — the principal's discretionary playbook and tier list, as testable hypotheses

**Written 2026-08-04, before any of the named structures below has been backtested on this desk.**
The principal supplied (a) a full "Quant Alpha Playbook" (XAUUSD-derived, ported to BTCUSDT) and
(b) a tier list of discretionary methodologies, with the order to test them. This document
converts both into pre-registered hypotheses so that whatever the gauntlet later says, the
thresholds were fixed BEFORE the first backtest. Every hypothesis below goes through the standard
gauntlet — per-candidate Romano-Wolf/CSCV, walk-forward, fragility, baselines — at the standard
α=0.05. Nothing here is exempt from anything.

## REJECTED ON ARRIVAL — the sizing module, under R0143

The playbook's sizing (100× leverage, $40 fixed risk per trade, TP1 3.5R / TP2 6R) is REJECTED
as a sizing rule and will not be tested, implemented, or shadowed. R0143 is categorical: the desk
rejects leverage-raising recommendations and CAGR targets; size is owned by the desk's
fractional-Kelly under the evidence-tier ladder, and a structure that only "works" at 100× is a
ruin machine wearing a strategy's clothes (log(0) = −∞ terminates the objective). The playbook's
STRUCTURE — entries, filters, exits — is testable and is registered below with desk sizing.

## H1 — Structural-level fade with RSI-extreme filter (playbook core)

- **Mechanism claim**: at levels touched ≥2 times (structural S/R), counter-trend entries win
  when momentum is exhausted (RSI beyond an extreme) because resting liquidity absorbs the push.
- **Pre-registered form**: level = swing high/low touched ≥2 times within a 90-day window at
  ≤0.3×ATR(14) tolerance; entry = touch + RSI(14) ≥70 (fade short) or ≤30 (fade long); exit =
  opposite structural level or 2×ATR stop, whichever first. Daily and 4h bars, the 10-symbol OKX
  universe, pooled by mechanism.
- **Kill filters carried over as REGIME GATES (testable, not sizing)**: no entries within 30 min
  of tier-1 scheduled news; skip when |funding| > 3× its 90-day median; skip when realized vol
  (24h) > 2× its 90-day median; these are hypotheses about WHEN the mechanism fails, and each is
  tested as an on/off ablation, never assumed.

## H2 — Breakout with volume confirmation (playbook core)

- **Mechanism claim**: range breaks accompanied by ≥1.5× average volume continue; breaks without
  volume mean-revert (failed auction).
- **Pre-registered form**: Bollinger(20,2) or Donchian(20) break + volume ≥1.5×SMA20(volume);
  trail = Parabolic SAR (default 0.02/0.2) as the EXIT structure under test; partials at fixed R
  multiples are an exit-shape ablation, not a sizing rule.

## H3–H11 — the tier list, in the principal's priority order

| # | methodology | pre-registered testable core | status |
|---|-------------|------------------------------|--------|
| H3 | ICT/SMC liquidity concepts | `libs/ict` detectors (FVG, order blocks, BOS/CHOCH, liquidity sweeps) — cross-sectional screen already cadenced (`ict-screen`) | LANDS WITH THIS MERGE |
| H4 | Auction Market Theory / Volume Profile | POC/VAH/VAL reversion + acceptance/rejection; needs volume-at-price → moat L2 tape | BLOCKED: recorder bringup (operator) |
| H5 | Order flow / CVD | delta divergence at structural levels; needs tick tape → moat recorder | BLOCKED: recorder bringup (operator) |
| H6 | Wyckoff | spring/upthrust after accumulation/distribution ranges; OHLCV-testable | READY |
| H7 | VWAP | session-VWAP reversion and VWAP-slope trend filter; OHLCV+volume-testable | READY |
| H8 | Supply/demand zones | departure-base-return zone retests; OHLCV-testable (zone = base before impulsive move) | READY |
| H9 | Opening-range breakout | UTC-session ORB with volume filter; crypto has no bell — session definitions (00:00 UTC, US open, Asia open) are pre-registered as the ONLY three tested | READY |
| H10 | Volatility compression | BB squeeze / NR7 → expansion direction; OHLCV-testable | READY |
| H11 | Mean reversion (band fades) | zscore fades at band extremes | REGISTERED LAST deliberately: L0054 (three independent methods rank mean-reversion last on crypto); it is tested, not skipped — the prior affects EFFORT ORDER, never the bar |

## The multiplicity ledger, declared now

Every hypothesis above enters the SAME campaign accounting: each (mechanism × parameter variant ×
symbol) candidate is counted in n_trials, pooled-by-mechanism rows are the certification view, and
no hypothesis is dropped from the count after the fact. This paragraph exists so the trial count
cannot later be argued down to whatever subset looked best (THREE_MECHANISM_PREREGISTRATION.md
states the same rule and the same reason).

## What would falsify the playbook's core claims

H1 dies if the fade's pooled edge is indistinguishable from the unconditional short-vol payoff it
resembles (beats_baselines + fragility catch this). H2 dies if volume confirmation adds nothing
over the bare break (the ablation is pre-registered). The kill filters die individually if their
ablation shows no conditional loss avoided. Each falsification is a RESULT — it retires search
space and feeds the graveyard, which is the second-most-valuable outcome after a survivor.
