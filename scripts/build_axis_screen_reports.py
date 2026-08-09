#!/usr/bin/env python3
"""Assemble reports/axis_screens/{oi_ls_daily,binance_metrics}.json from the raw trial log.

Adds two derived corrections the harness cannot make for itself and that MUST accompany its
numbers here:
  * horizon-corrected Sharpe -- stage_a_screen hardcodes sqrt(365) annualisation, which
    over-annualises a non-overlapping h-day grid by sqrt(h).
  * effective-n IC t-stat -- the harness's n is SYMBOL-DAYS on a stacked panel. Symbols within a
    date are highly correlated, so the independent-observation count is ~the number of DATES.
    Using n_symbol_days would inflate every t-stat by ~sqrt(139).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path("/home/quant/quant-platform")
OUT = ROOT / "reports/axis_screens"
raw = json.loads((OUT / "_raw_trials.json").read_text("utf-8"))
TRIALS = raw["trials"]
N_TRIALS_TOTAL = raw["n_trials"]
DATES = {1: 1878, 5: 375, 20: 93}


def enrich(t: dict[str, Any]) -> dict[str, Any]:
    h = t.get("horizon_days", 1)
    o = dict(t)
    if "sharpe_momentum" in t:
        o["sharpe_momentum_horizon_corrected"] = round(t["sharpe_momentum"] / np.sqrt(h), 3)
        o["sharpe_reversal_horizon_corrected"] = round(t["sharpe_reversal"] / np.sqrt(h), 3)
    if "ic" in t and "|" in t.get("name", "") and "BTC_abs" not in t.get("name", ""):
        eff = DATES.get(h, t.get("n", 1))
        o["effective_n_dates"] = eff
        o["ic_tstat_effective_n"] = round(float(t["ic"] * np.sqrt(eff)), 2)
    elif "ic" in t:
        o["effective_n_dates"] = t.get("n", 0)
        o["ic_tstat_effective_n"] = round(float(t["ic"] * np.sqrt(max(t.get("n", 1), 1))), 2)
    return o


oi = [enrich(t) for t in TRIALS if "BTC_abs" not in t["name"]]
bm = [enrich(t) for t in TRIALS if "BTC_abs" in t["name"]]

ALIGNMENT = (
 "VERIFIED, NOT ASSUMED. (a) The archive `date` is a UTC calendar day and matches both the 1d "
 "kline UTC day and the live forward collector -- proven by shift-sensitivity: corr(archive OI, "
 "forward snapshot) peaks at shift 0 for all 5 probe symbols and degrades at +/-1d "
 "(BTC 0.475/0.846/0.747, ETH 0.328/0.840/0.478, SOL 0.948/0.992/0.978, XRP 0.722/0.978/0.834, "
 "ADA 0.113/0.905/0.324 for shifts -1/0/+1). No timezone offset. "
 "(b) The `oi`/`oi_first` pair encodes an INTRA-DAY alignment subtlety, confirmed against "
 "scripts/dl_oi_ls_universe.py:pull_metrics: `oi`/`ls`/`taker` are the MEAN of all 288 5-min "
 "buckets from 00:00 to 23:55 UTC of day t (an average spanning the whole of day t, complete "
 "only at 23:55 UTC), while `oi_first`/`ls_first` are the single 00:00:00 UTC bucket -- the "
 "FIRST observation of day t, i.e. information known at the START of day t. "
 "(c) Proof of (b): the live collector snapshots at ~00:0x UTC; corr(forward 00:0x snapshot, "
 "archive `oi_first`) = 0.9994-0.9999 across all 5 probe symbols, versus 0.79-0.99 against the "
 "archive daily MEAN `oi`. The reconstruction is exact. "
 "(d) LOOK-AHEAD CONTROL: pairing `oi[t]` (a whole-day average) with the day-t return "
 "(close t-1 -> close t) is CONTEMPORANEOUS and was never done. Every signal dated t is used "
 "only to predict close(t) -> close(t+h); stage_a_screen enforces this structurally by "
 "predicting target_ret[t+1] from signal[t]. Worst case the signal is complete at 23:55 UTC and "
 "entry is at the 23:59:59.999 close -- a 5-minute lead. The `M1_lsfirst_level` / "
 "`M2_oifirst_growth` constructions re-run the same mechanisms on the 00:00 snapshot, which is "
 "~24h stale at entry and therefore immune even to that 5-minute objection; they agree with the "
 "daily-mean versions (both null), so no result here depends on the 5-minute window."
)

CAVEAT = (
 "TWO HARNESS CAVEATS, declared rather than patched (the harness is audited and was not "
 "modified): (1) stage_a_screen hardcodes sqrt(365) annualisation, so on the non-overlapping "
 "5d/20d grids its Sharpe is inflated by sqrt(h) -- the horizon-corrected value is reported "
 "alongside every trial, and its SUSPECT-LOOKAHEAD Sharpe>6 rail is correspondingly "
 "over-sensitive at 20d. (2) On a stacked panel its `n` is SYMBOL-DAYS; symbols within a date "
 "are strongly correlated, so the independent-observation count is the number of DATES. Every "
 "IC t-stat below uses the date count, not the symbol-day count -- otherwise every t-stat would "
 "be inflated by ~sqrt(139)=11.8x."
)

# ---------------------------------------------------------------- oi_ls_daily
(OUT / "oi_ls_daily.json").write_text(json.dumps({
 "axis": "oi_ls_daily",
 "updated": "2026-07-26",
 "stage": "A (zero promotion authority)",
 "verdict": "NEGATIVE -- ALL 42 CONSTRUCTIONS FAIL. NO FORWARD CLOCK STARTED.",
 "universe": {"symbols": 139, "dates": 1879, "range": ["2021-06-01", "2026-07-23"],
              "survivorship": "tranche-1 cohort enumerated from the archive's OWN S3 listing "
                              "(includes delisted symbols), not from today's live universe -- "
                              "the cross-section is what actually existed at each date"},

 "mechanism_prior": {
  "stated_before_screening": True,
  "M1_crowded_positioning_liquidation_cascade":
   "The global long/short ACCOUNT ratio measures how one-sided retail positioning is. When a "
   "symbol's crowd is extremely long relative to peers, the marginal buyer is exhausted and the "
   "downside is convex: a modest adverse move forces liquidations that beget further "
   "liquidations. Crowding should therefore mean-revert, and the crowded name should "
   "UNDERPERFORM its peers.",
  "M2_OI_build_without_price_confirmation_fragile_leverage":
   "Open interest rising while price does NOT confirm means new leverage is being added into a "
   "move the market is not validating. That leverage is fragile -- it is stop-loss fuel. OI "
   "built AGAINST the price move marks trapped positions specifically.",
  "M3_taker_flow_imbalance_informed_aggression":
   "The taker buy/sell volume ratio measures who is willing to CROSS THE SPREAD. Aggressive "
   "takers pay for immediacy, which is what informed traders do when they have a short-lived "
   "edge. Sustained taker imbalance should therefore lead relative returns.",
  "why_cross_sectional": "All three are statements about one symbol RELATIVE TO OTHER SYMBOLS "
   "(who is more crowded, whose leverage is more fragile, where is aggression concentrated). "
   "The 139-symbol breadth is the axis's real advantage, so the target is the cross-sectionally "
   "demeaned return and the book is a rank-based long/short spread -- NOT a next-day BTC timing "
   "signal, which is the dev-momentum mistake this desk made standing law."},

 "alignment_declaration": ALIGNMENT,
 "harness_caveats": CAVEAT,

 "method": {
  "screen": "libs.research.axis_screen.stage_a_screen ONLY (angle-20 de-contamination gate "
            "baked in, never bypassed). Nothing outside the harness produced a verdict.",
  "target": "cross-sectionally demeaned (relative) return, per date, across the 139-symbol panel",
  "horizons": "1d / 5d / 20d, NON-OVERLAPPING sampling (no overlapping-window t-stat inflation)",
  "signal_normalisation_primary": "cross-sectional rank -> normal scores (van der Waerden) per "
                                  "date, which is exactly the 'rank the symbols' construction "
                                  "the cross-sectional mandate specifies; the harness then "
                                  "applies its own trailing-20 z on top",
  "signal_normalisation_secondary": "raw level with the harness's trailing-20 z as the only "
                                    "normalisation ('extreme vs its OWN history'), target still "
                                    "cross-sectionally relative",
  "change_window": "changes are computed over the SAME h-period as the horizon -- no free lag "
                   "parameter was introduced or tuned",
  "panel_stacking": "symbol-major stack; the harness's rolling z-window and its np.roll forward "
                    "return bleed across 139 block boundaries. Reported per trial as "
                    "boundary_bleed_frac (~1.5% of rows at 1d, larger at 20d). Cross-sectional "
                    "normalisation puts all symbols on one scale so the bleed adds noise rather "
                    "than signal -- it is conservative, it cannot manufacture an edge.",
  "sharpe_interpretation": "the harness's sign(z)*fwd Sharpe on a stacked panel is the PER-NAME, "
                           "UNDIVERSIFIED long/short Sharpe, ~sqrt(N_eff) below the diversified "
                           "book. Conservative. A separate DESCRIPTIVE (never a verdict) "
                           "diversified top-vs-bottom-decile spread is recorded alongside."},

 "trial_accounting": {
  "constructions": 10, "normalisations": 2, "horizons": 3, "targets": 2,
  "trials_this_axis": len(oi),
  "trials_all_axes_this_session": N_TRIALS_TOTAL,
  "note": "Every cell of the pre-declared grid was executed and is logged below, including the "
          "target control against ABSOLUTE return. Nothing was run and discarded. Because 42 "
          "trials were run on this axis, any nominal pass would have had to clear a "
          "multiplicity-deflated bar -- none came close enough for that to matter."},

 "results_summary": {
  "verdicts": {"SCREEN-WEAK": sum(1 for t in oi if t["verdict"] == "SCREEN-WEAK"),
               "TIMING-ARTIFACT": sum(1 for t in oi if t["verdict"] == "TIMING-ARTIFACT"),
               "SCREEN-INTERESTING": sum(1 for t in oi if t["verdict"] == "SCREEN-INTERESTING")},
  "largest_abs_ic": max(abs(t.get("ic", 0)) for t in oi),
  "largest_abs_ic_trial": max(oi, key=lambda t: abs(t.get("ic", 0)))["name"],
  "reading": "Every IC is inside noise. The largest |IC| on the axis is 0.045 at 20d, where the "
             "effective sample is 93 dates -- an IC t-stat of -0.43. At 1d the largest |IC| is "
             "0.008 (t=0.35 on 1878 dates). No horizon-corrected per-name Sharpe exceeds 0.36. "
             "The three defensible mechanisms are not merely unproven here; they are flat."},

 "notable_negative_findings": [
  {"finding": "The LS ratio is substantially a RESTATEMENT of the contemporaneous price move at "
              "medium horizons, not an independent positioning read.",
   "evidence": "M1_ls_change|xsrank|rel|20d was the only construction on this axis to trip the "
               "de-contamination gate: same_period_corr = -0.294 against the 20d limit of 0.20. "
               "Its descriptive decile spread (-1.77% per 20d, the mechanism-predicted "
               "direction) is therefore NOT evidence for the crowding mechanism -- the gate "
               "caught it as the coinbase/turkey failure mode. The crowd chases price, so LS "
               "change and the concurrent return move together; what looks like a crowding "
               "signal is ~30% concurrent price, i.e. a price-family effect in an LS costume. "
               "This is exactly the artifact the angle-20 gate exists to catch.",
   "lesson": "Any future positioning construction on this axis must be orthogonalised to the "
             "contemporaneous return BEFORE it is screened, or it will keep re-discovering "
             "medium-term price reversal and mislabelling it as crowding."},
  {"finding": "OI growth is contaminated by concurrent price in the same way, with the opposite "
              "sign.",
   "evidence": "M2_oi_growth same_period_corr = +0.132 (1d), +0.224 (5d), +0.253/+0.319 (20d, "
               "raw-z variant) -- OI and price rise together. The pre-registered "
               "sign(dP)*sign(dOI) divergence construction is the correct defence against this "
               "and indeed shows the lowest contamination of the M2 family (+0.063 at 1d), but "
               "it is also flat (IC -0.002)."},
  {"finding": "The relative-vs-absolute target choice was not the binding constraint.",
   "evidence": "The three ABSOLUTE-return controls are as flat as their relative counterparts "
               "(|IC| <= 0.005). The mandate is right that cross-sectional relative is the "
               "mechanism-appropriate target, but on this axis the signals carry no information "
               "about EITHER target. The null is about the signals, not the framing."},
  {"finding": "The alignment-robustness constructions agree with their daily-mean twins.",
   "evidence": "M1_lsfirst_level tracks M1_ls_level and M2_oifirst_growth tracks M2_oi_growth at "
               "every horizon, both null. No conclusion depends on the 5-minute gap between the "
               "23:55 UTC signal completion and the 23:59:59 close."}],

 "blocked_prior_work": {
  "what": "scripts/backfill_oi_ls_oos.py (the pre-registered CROSS-SECTIONAL held-out OOS for "
          "the oi_divergence and ls_contrarian sleeves) had never been run to completion -- "
          "reports/reconstructed_oos/oi_ls_cross_sectional.json did not exist. It was run as "
          "part of this screen and ABORTED on its own diff-verify gate.",
  "abort_message": "ABORT: reconstruction misaligned vs forward truth "
                   "{'oi_corr': 0.840, 'ls_corr': 0.780} (bithumb/timezone class)",
  "diagnosis": "FALSE POSITIVE -- a gate CALIBRATION defect, not a misalignment. diff_verify "
               "compares the forward collector's single point-in-time snapshot against the "
               "archive's 24h MEAN (`oi`), which is a like-for-unlike comparison over only 25 "
               "overlapping days on a range-bound level. Comparing like-for-like -- the "
               "collector's 00:0x UTC snapshot against the archive's 00:00 bucket `oi_first` -- "
               "gives corr 0.9994-0.9999 on all five probe symbols, and the median relative "
               "difference on `oi` is already only 0.56-0.94% (units match exactly: contracts "
               "vs contracts). Shift-sensitivity independently rules out a day offset.",
  "action_taken": "The gate was NOT weakened or bypassed -- that is not this screen's authority. "
                  "The defect is reported for the gate's owner.",
  "recommended_fix": "In scripts/backfill_oi_ls_oos.py:diff_verify, compare the forward snapshot "
                     "against `oi_first`/`ls_first` (matching the collector's ~00:0x UTC "
                     "sampling time) instead of against the daily means `oi`/`ls`. The 0.90/0.60 "
                     "thresholds are then meaningful; against a daily mean they are not.",
  "consequence": "The pre-registered 2-trial OOS for the two derivative sleeves remains "
                 "UNRESOLVED. This Stage-A screen does not substitute for it: it covers a much "
                 "wider grid but has no pre-registration, so its 42 trials carry a "
                 "multiple-testing penalty the 2-trial OOS would not."},

 "screen_outputs": oi,

 "next_step": "Do NOT start a forward clock and do NOT re-screen these constructions -- 42 "
              "trials across three mechanisms, two normalisations, two targets and three "
              "horizons is a thorough refutation, and running more variants on the same data is "
              "the breadth-mining this desk has already refuted 420 times. Two concrete "
              "follow-ups, in priority order: (1) fix the diff_verify field mismatch and let the "
              "pre-registered 2-trial cross-sectional OOS actually run -- it is the one test on "
              "this axis that carries no multiplicity penalty, and it is currently blocked by a "
              "bug rather than by evidence; (2) if the positioning mechanisms are to be revisited "
              "at all, the missing ingredient is not another construction but a different FIELD "
              "-- the top-trader ratios (see the binance_metrics screen), which separate "
              "informed from retail positioning and are not present in oi_ls_daily.",

 "authority": "Stage A only. ZERO promotion authority. No clock earned, none started."
}, indent=1), encoding="utf-8")

# ---------------------------------------------------------------- binance_metrics
(OUT / "binance_metrics.json").write_text(json.dumps({
 "axis": "binance_metrics",
 "updated": "2026-07-26",
 "stage": "A (zero promotion authority)",
 "verdict": "REJECTED -- the harness's nominal SCREEN-INTERESTING does not survive adversarial "
            "review. NO FORWARD CLOCK STARTED.",
 "coverage": {"symbols": 1, "symbol": "BTCUSDT", "days": 435,
              "range": ["2023-01-01", "2024-03-10"], "files": 435,
              "note": "Despite 435 files this axis is ONE symbol. It is the raw 5-min metrics "
                      "archive that oi_ls_daily was itself built from, so `sum_open_interest`, "
                      "`count_long_short_ratio` and `sum_taker_long_short_vol_ratio` are "
                      "REDUNDANT with oi_ls_daily and were not re-screened."},

 "mechanism_prior": {
  "stated_before_screening": True,
  "what_is_genuinely_new_here":
   "Two fields exist in this archive that oi_ls_daily does NOT carry: "
   "`count_toptrader_long_short_ratio` and `sum_toptrader_long_short_ratio`, the positioning of "
   "the top 20% of accounts by margin balance. Together with the retail-wide "
   "`count_long_short_ratio` they permit a SMART-MONEY vs RETAIL construction that is impossible "
   "on any other axis here. A third new quantity is the intra-day OI path (23:55 vs 00:00), "
   "which oi_ls_daily compresses to a mean and a first bucket.",
  "M4_smart_money_vs_retail":
   "Large, well-capitalised accounts survive by being right; the retail crowd is the liquidity "
   "they trade against. When top traders are positioned LONG while the retail crowd is SHORT, "
   "the informed side is on the long side and price should follow it. The spread between the two "
   "ratios isolates the disagreement, cancelling the market-wide positioning level.",
  "M5_intraday_OI_drift":
   "OI built during the session and still held into the close is leverage that survived the "
   "day's shakeouts -- a cleaner read on conviction than the daily mean, which mixes positions "
   "that were opened and closed intraday.",
  "declared_low_prior": "ONE symbol means NO cross-section is available, so the only possible "
   "target is BTC's own absolute return -- precisely the next-day-single-asset-timing shape the "
   "mandate flags as the dev-momentum mistake. The prior was declared low BEFORE screening, and "
   "the screen was run anyway so that the result would be recorded rather than assumed."},

 "alignment_declaration":
  "Same convention as oi_ls_daily and verified by the same evidence. The 5-min buckets run "
  "00:00 to 23:55 UTC of day t; the daily aggregate is therefore complete at 23:55 UTC and is "
  "used only to predict close(t) -> close(t+h) against the 23:59:59.999 UTC futures close. "
  "M5_oi_intraday_drift uses the 23:55 bucket over the 00:00 bucket, both strictly within day t. "
  "No same-day return is ever paired with a same-day aggregate; stage_a_screen enforces the "
  "t -> t+1 direction structurally.",
 "harness_caveats": CAVEAT,

 "trial_accounting": {"constructions": 3, "horizons": 2, "trials_this_axis": len(bm),
                      "trials_all_axes_this_session": N_TRIALS_TOTAL,
                      "note": "20d was not run: 435 days / 20 = 21 non-overlapping periods, "
                              "below the harness's n>=30 floor. Declared, not silently dropped."},

 "screen_outputs": bm,

 "adversarial_review_of_the_nominal_pass": {
  "trial": "M4_smart_minus_retail_count|BTC_abs|1d",
  "harness_result": {"ic": 0.104, "sharpe_momentum": 1.99, "same_period_corr": -0.026,
                     "residual_ic": 0.103, "n": 413, "verdict": "SCREEN-INTERESTING"},
  "checks_run": [
   {"check": "shift-sensitivity (mandatory before trusting anything strong)",
    "result": "IC by signal lag: -1d = -0.027, 0d = +0.103, +1d = +0.067, +2d = +0.004",
    "reading": "PASSES. A misalignment artifact spikes at one lag with nothing adjacent, or is "
               "stronger at a NEGATIVE lag. This decays smoothly forward from a lag-0 peak, "
               "which is what a slow-moving positioning variable should do. Not a look-ahead bug."},
   {"check": "de-contamination (angle-20 gate)",
    "result": "same_period_corr = -0.026, residual_ic 0.103 vs raw ic 0.104",
    "reading": "PASSES cleanly. The signal is not a restatement of the concurrent move."},
   {"check": "long-bias / beta decomposition",
    "result": "49.4% of days long (near neutral, so not a disguised long-only book), BUT BTC "
              "buy-and-hold Sharpe over the identical 413 days is +2.37 versus the signal "
              "book's +1.99. Long-day subset mean +55.5 bps, short-day subset mean +4.7 bps.",
    "reading": "FAILS. The book earns almost everything on its long days and its short leg is a "
               "drag (shorting days that average +4.7 bps loses money). It is a partially "
               "successful market-timing filter in a violent bull market, and it does not beat "
               "simply holding the asset over the only window it has."},
   {"check": "multiple-testing deflation (libs.validation.dsr)",
    "result": "DSR = 0.0000 at n_trials=48 (sr0 threshold 0.332); DSR = 0.037 even at "
              "n_trials=6, counting only this axis's own trials. IC t-stat = 2.11 on 413 days "
              "against a Bonferroni requirement of ~3.3 for 48 trials.",
    "reading": "FAILS decisively, and would fail even if this axis had been screened alone."},
   {"check": "regime coverage",
    "result": "435 consecutive days, 2023-01-01 to 2024-03-10: the post-FTX recovery straight "
              "through the spot-ETF rally. First-half book Sharpe +1.43, second-half +2.51.",
    "reading": "FAILS. One monotonic uptrend is one regime. The rising sub-period Sharpe is "
               "consistent with the signal simply working better as the trend strengthened."}],
  "conclusion": "REJECTED. The mechanism is NOT refuted -- the de-contamination and "
                "shift-sensitivity results are genuinely clean, which is more than any "
                "oi_ls_daily construction managed. But this DATA cannot test it: one asset, one "
                "regime, 413 usable days, and a 48-trial multiplicity burden that a t-stat of "
                "2.11 cannot carry. Promoting it would be exactly the phantom-edge manufacture "
                "the discipline forbids."},

 "other_nominal_pass": {
  "trial": "M5_oi_intraday_drift|BTC_abs|5d",
  "result": "ic 0.058, harness sharpe_reversal -1.64, n=65",
  "rejected_because": "n=65 gives an IC t-stat of 0.47, and the harness's sqrt(365) "
                      "annualisation overstates a 5-day-grid Sharpe by sqrt(5)=2.24x, so the "
                      "true figure is ~0.73. Statistically empty; the SCREEN-INTERESTING label "
                      "is an artifact of thresholds designed for daily data."},

 "timing_artifacts_caught": "Both 5d M4 constructions tripped the de-contamination gate "
                            "(same_period_corr +0.506 and +0.285) -- over a 5-day window the "
                            "positioning aggregate and the concurrent return overlap heavily. "
                            "The gate worked.",

 "next_step": "Do NOT start a clock and do NOT screen further constructions on 435 days of one "
              "symbol -- more variants on this sample can only manufacture multiplicity. The "
              "single highest-value follow-up on any of these three axes is a DATA action, not "
              "an analysis action: extend scripts/dl_oi_ls_universe.py:pull_metrics to also "
              "persist `count_toptrader_long_short_ratio` and `sum_toptrader_long_short_ratio` "
              "(both are already present in every archive CSV it parses and are currently "
              "discarded) across the full 139-symbol tranche-1 cohort and its full 2021-2026 "
              "history. That converts the one mechanism here that passed de-contamination and "
              "shift-sensitivity from an untestable single-asset timing signal into a "
              "cross-sectional asset-selection signal with 139-symbol breadth and five years of "
              "regimes -- the shape this desk can actually test. Only then does it deserve a "
              "pre-registered screen.",

 "authority": "Stage A only. ZERO promotion authority. No clock earned, none started."
}, indent=1), encoding="utf-8")
print("wrote oi_ls_daily.json, binance_metrics.json")
print("oi_ls trials:", len(oi), "| binance_metrics trials:", len(bm))
