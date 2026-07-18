# Gap #14 — Leverage-optimizer confidence pipeline — FORENSIC ROOT CAUSE

**Date:** 2026-07-19 · **Status:** forensic complete, **NO code changed** (freeze; fix queued
post-Gate-0 per operator instruction). The executor quarantine (`_dynamic_capital` returns operator
`--capital`, ignoring `active`/notional in both directions) holds the book safe meanwhile.

## Live evidence (read fresh 2026-07-19, not from memory)
| field | value | source |
|---|---|---|
| `forward_ann_sharpe` | **16.09** | web/cashcarry_shadow.json |
| `forward_days` | 22 | web/cashcarry_shadow.json |
| molded curve span | **~2.7 days** (2026-07-16T06:37 → 2026-07-18T23:41) | live_combined_state.json `mcurve` |
| `confidence` | 0.9201 | data/leverage_target.json |
| `leverage` / `notional_per_leg` / `active` | 0.25 / 1250 / True | data/leverage_target.json |
| `growth_optimal` (kelly) | 0.0 | data/leverage_target.json |

## Root-cause chain (confirmed, not hypothesised)
1. **Variance collapse → phantom Sharpe.** The confidence is fed by the cash-carry *molded* curve
   (`live_combined_state.mcurve`, hourly) and `forward_ann_sharpe`. The molded curve smooths away
   mark-to-market/basis noise; on a delta-neutral carry the residual is near-pure funding accrual,
   so the return-stream variance collapses and the annualised Sharpe explodes to **16.09** — which
   is not an edge, it is an under-measured denominator. (A real edge Sharpe is ~0.5–2; 16 is
   physically implausible.)
2. **The shrink cannot defend a mis-measured point estimate.** `shrink_fraction = S²/(S²+SE²)`
   (libs/risk/kelly_shrink.py). With S=16.09, S²≈259 dominates any SE, so the fraction ≈ **0.92** —
   almost no shrinkage. Estimation-error shrinkage assumes the Sharpe *point estimate* is honest and
   only the *sample size* is uncertain; it has no defence against a variance-collapsed point estimate.
3. **fwd_days/return-stream source mismatch.** `shrink_fraction` uses `fwd_days=22` as the effective
   N, but the actual return stream (mcurve) is only ~2.7 days post-incident-reset. The forward-day
   counter in cashcarry_shadow.json was **not reset at the 2026-07-16 incident re-anchor**, so the
   shrink trusts 22 days of evidence on a 3-day curve — compounding (1).
4. **`_confidence` gate opened** (dynamic_leverage.py:43): fwd_sharpe>0 ✓, fwd_days≥min_days ✓,
   n_obs≥40 ✓ (hourly molded points). Gate passing let (2)'s 0.92 through.
5. **`active = confidence > 0` flips the executor off operator capital.** With conf 0.92>0, the
   optimizer wrote `active=True`; the executor then honoured `notional_per_leg` (=0.25×$5,000 floor
   =$1,250, since kelly/growth_optimal=0 → recommendation floors to `_MIN_OP`) instead of the
   operator's $4,500. **This is the mechanism of both incident #2 (over-lever) and the 07-18
   under-deploy: the same phantom confidence, pointing whichever way the floor/notional math lands.**

## Predicted in advance
The 2026-07-11 external panel (moonshotai/kimi-k2.6) named this exactly: *"Forward-Shadow Basis-Risk
Censorship … a 12.11 Sharpe is only possible if the variance denominator is dominated by smooth 8h
funding accrual while ignoring unrealized basis drift."* The desk logged the recommendation but had
not yet closed it — this forensic confirms it fired.

## Proposed fix (QUEUED post-Gate-0 — do NOT implement during freeze)
1. **Kill the variance collapse at the source:** compute the forward return stream from
   **mark-to-market mid on BOTH legs** each heartbeat (spot mark vs perp mark), not the
   funding-smoothed molded curve, so basis-drift variance enters the Sharpe denominator.
2. **Plausibility rail:** a forward Sharpe above a sane bound (≈ `min(fwd_sharpe, 2×backtest_sharpe)`,
   or a hard ceiling ~3–4) must **reduce** confidence / trip an "implausible → investigate" flag —
   never increase it. A Sharpe of 16 should freeze sizing, not activate it.
3. **Reset the forward-day counter on any incident/re-anchor** so N matches the post-reset evidence
   the return stream actually contains.
4. **Re-enable gate unchanged:** ≥30 uncontaminated live days + principal sign-off before `active`
   may drive sizing again. Until all four ship + pass property/mutation tests, the `_dynamic_capital`
   quarantine stands.
