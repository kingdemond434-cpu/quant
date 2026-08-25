# AUDIT: NZDJPY.dow_effect implausible R (gap register #125) — 2026-08-25

**Verdict: R multiples on the MONDAY side of every `dow_effect` sleeve are denominator-inflated
by construction; the +50.1R-class headline is fiction in R units. Do not rank or admit on them.**

## Evidence (ledger_NZDJPY_dow_effect.json, trade-by-trade vs the family code)

| trade | entry_time (UTC) | side | entry→exit | r_multiple | implied stop_dist |
|---|---|---|---|---|---|
| 1 | 2026-08-17 01:00 (Mon) | long | 93.65 → 93.9366 (+28.7 pips) | **+5.81R** | **4.9 pips** |
| 2 | 2026-08-20 01:00 (Thu) | short | 93.657 → 94.0078 (−35.1 pips) | −1.09R | 32.3 pips |

Same sleeve, 6.6× different implied stop. Mechanism, located in code:

1. `mt5desk/families.py:family_dow_effect` fires at `ts.hour == 0` and sets
   `stop_dist = 1.2 * ATR(20)` where `_atr` is an EWM over trailing H1 true ranges
   (`families.py:24`). At Monday 00:00 the trailing window is weekend/Friday-close bars with
   near-zero TR, so the EWM has decayed toward zero — the Monday stop is manufactured tight,
   and R = move/stop_dist is manufactured large. Thursday entries (full-week ATR) are sane.
   A day-of-week family whose R denominator is itself a function of day-of-week is
   self-confounded: the "Monday effect" measured in R is partly the ATR artifact.
2. Zero cost in replay: trade 1's ratio is exactly 0.2866/0.0493 = 5.81, so the engine's
   `r -= per_oz_cost/stop_dist` term (engine.py:222) contributed nothing → `per_oz_cost = 0`
   in this replay path. At NZDJPY's ~2-pip spread on a 4.9-pip stop, cost alone is ≈0.4R per
   side — precisely the term that would have deleted the fiction.

## Dispositions

- The sleeve's ledger stays (append-only evidence); this note rides beside it. Any scorer
  reading `dow_effect` ledgers must exclude or re-denominate Monday cells until the family fix
  lands.
- Family fix (structural, NOT applied here because it changes the candidate's identity and the
  promoter/shadow_admission files are under active sibling edit): floor the stop economically,
  e.g. `stop_dist = max(1.2*ATR, k*current_spread)` or compute ATR over trading bars only.
  That is a NEW construction version and must be preregistered + trial-charged as such.
- Same exposure class: every family entering at fixed clock hours near the weekly open with
  trailing-ATR stops (`monday_gap` most of all — it trades the gap bar BY DESIGN).
