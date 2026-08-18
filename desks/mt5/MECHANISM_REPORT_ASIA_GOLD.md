> # RETRACTED 2026-08-18 — THIS REPORT IS A LOOKAHEAD ARTIFACT
>
> Every number below was produced by `mech_battery.py`, which computed its day
> states INLINE and SAME-DAY: day D was labelled from D's own 13:00–22:00 NY
> session and then used to filter D's own signals. The asia window fires at
> 07:00 UTC, so every trade here was gated by data from fifteen hours in its own
> future.
>
> `run_hunt12.day_states` had already found and fixed exactly this. Eleven
> callers picked the fix up. This script was not one of them, because it
> reimplemented the labelling instead of importing it — two implementations of
> one definition, and the wrong one wrote this file.
>
> | cell | as published | corrected |
> |---|---|---|
> | asia TREND_DAY | +0.908R, defl_t 9.85, PF 4.29 | **+0.191R, defl_t 1.30** |
> | asia NORMAL_DAY | +0.459R, defl_t 9.56 | **+0.256R, defl_t 4.59** |
> | asia FAILED_BREAK | −0.257R, defl_t −8.29, −184R DD | **+0.158R, defl_t 2.16** |
> | asia RANGE_DAY | +0.076R | **+0.210R** |
>
> Corrected, the four states pay +0.191 / +0.256 / +0.210 / +0.158 against an
> unconditional base of **+0.212R**. That is a flat line. Prior-NY displacement
> does not discriminate; the "4.3× the unconditional book at a quarter of the
> drawdown" headline was the lookahead, and the FAILED_BREAK sign inverts.
>
> **The Action section below is void.** Conditioning on this state buys nothing
> and costs half the sample. See `reports/mech_battery.json`, regenerated from
> the corrected join.

---

# MECHANISM REPORT: What makes Asia Gold work

_Generated 2026-08-17 — Mechanism Desk flagship v1. Evidence: XAUUSD H1
2018→2026, armed Asia window (07:00 bracket, rr=2, wait 12, TTL 12), live
costs, full battery incl. family-deflated t (E[max]≈1.5), 3-fold WF, 2x cost
stress. No leakage: prior-NY session (13:00-22:00 UTC, complete at 22:00) is
fully known before the 07:00 Asia signal._

## The label decomposes

"Asia gold works" was a clock label. Conditioning the SAME signals on the
prior-NY displacement state (Mechanism Desk classification) splits it:

| Prior-NY state | n | exp_R | t | defl t | PF | maxDD_R | 2x stress | WF (3 folds) | Battery |
|---|---|---|---|---|---|---|---|---|---|
| ALL (base) | 2,094 | +0.212 | 8.40 | 6.90 | 1.54 | -21.0 | +0.202 | +0.206 +0.162 +0.272 | pass |
| **TREND_DAY** (NY range > 1.5x med) | 261 | **+0.908** | 11.34 | 9.85 | **4.29** | **-5.2** | **+0.898** | +0.838 +1.075 +0.832 | **PASS** |
| **NORMAL_DAY** | 758 | +0.459 | 11.05 | 9.56 | 2.53 | -6.3 | +0.450 | +0.465 +0.408 +0.499 | **PASS** |
| RANGE_DAY (NY range < 0.75x med) | 376 | +0.076 | 1.57 | 0.08 | 1.22 | -11.1 | +0.065 | +0.046 +0.037 +0.143 | fail |
| **FAILED_BREAK** (NY swept day-before levels, closed back inside) | 700 | **-0.257** | -6.80 | -8.29 | 0.55 | -184.0 | -0.267 | all negative | strongly negative |

## Interpretation

- The Asia edge is carried by **prior-NY displacement quality**. After a
  genuine trending NY session (range expansion that closed through the prior
  day's levels), Asia continuation has exp +0.908R with PF 4.29 — 4.3x the
  unconditional book — at 1/4 the drawdown.
- After a **failed NY breakout** (sweep + reclaim = the "fake breakout"
  signature the survivor research predicted), the same Asia signal is
  actively harmful (t=-6.8, -184R DD). This independently confirms the
  Goldtrade/Reaper fake-breakout classification on our own data.
- RANGE_DAY adds nothing (edge absent, not harmful).

## Action

1. **Candidate conditioning upgrade (P1 deployable):** Asia gold trades only
   TREND_DAY + NORMAL_DAY (≈49% of days), skip RANGE_DAY, actively skip
   FAILED_BREAK. Blended expectation ≈ +0.57R vs +0.212R unconditional,
   fewer trades, ~1/4 the drawdown. State is knowable at 07:00.
   - Deployment only after the same review standards; the armed book is
     NOT changed for the 2026-08-17 open.
2. **Universe state hunt (hunt12, running):** sweep TREND/NORMAL/RANGE/
   FAILED_BREAK conditioning across all 22 symbols x 4 windows.
3. **Decay monitoring:** the state should become a tracked feature in the
   Regime/Decay desk; if the TREND_DAY premium decays, the mechanism may be
   shifting (monitor rolling exp of the gated sleeve).

## Next mechanism questions (v2)

- Is the TREND_DAY premium driven by NY trend direction (up vs down)?
- Does prior-NY *failure type* (upper vs lower sweep) matter?
- Interaction: TREND_DAY x macro_stress_hi / jpy_breadth_strong (hunt10/11
  winners) — combine the strongest orthogonal states.
- Hunt the same state across JPY complex and metals (hunt12 output).