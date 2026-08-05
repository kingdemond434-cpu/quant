"""Reusable Stage-A axis-screening harness -- so every new-axis screen applies the SAME discipline
we applied to kimchi/coinbase/turkey by hand, with the de-contamination (angle-20) gate BAKED IN
and impossible to skip.

The bespoke part of onboarding a new axis (fetching a new API's history) is still per-source code,
but the ANALYTICAL LAST MILE -- z-score, IC, momentum/reversal Sharpe, same-period contamination
check, residual IC, artifact verdict, forward-clock persistence -- is identical every time and is
now this one audited function. The brain (when authed) or the CRO passes an aligned (signal, target)
series and gets the honest verdict + a started forward clock, instead of re-deriving the screen
(and re-forgetting the artifact gate) each time.

Stage-A only (two-stage law): ZERO promotion authority. A pass earns a forward clock, never capital.
Pure numpy. import from libs.research.axis_screen.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
                   zwin: int = 20, contam_max: float = 0.20, ic_min: float = 0.03,
                   sharpe_min: float = 0.5, ic_ceiling: float = 0.35,
                   sharpe_ceiling: float = 6.0, clock: str | None = None,
                   horizon_days: float = 1.0, panel_width: int = 1) -> dict[str, Any]:
    """Screen a signal against NEXT-period target returns with the mandatory angle-20 gate.

    signal[t], target_ret[t] must be aligned same-period arrays (target_ret[t] = return realised
    over period t). The function predicts target_ret[t+1] from a z-scored signal[t], and checks
    that the signal LEADS rather than COINCIDES.

    Verdict (highest-priority first):
      SUSPECT-LOOKAHEAD      -- |IC|>ic_ceiling or best timing Sharpe>sharpe_ceiling. A daily
                                z-scored signal predicting next-day return this strongly is not
                                credible at this horizon; it means the two series are misaligned
                                (timezone/candle-label lookahead: e.g. a KST-day candle whose close
                                sits ~1.6d ahead of a UTC-day close), stale-repeated, or otherwise
                                leaking future info. Caught the bithumb_KR IC-0.72/Sharpe-10 fake.
                                Treated as an artifact -- NEVER earns a clock. Re-run a +/-1 day
                                shift-sensitivity check before trusting anything that trips this.
      TIMING-ARTIFACT        -- fails de-contam: |same-period corr|>contam_max OR residual IC
                                collapses below half the raw IC (the coinbase/turkey failure mode)
      SCREEN-INTERESTING     -- |IC|>=ic_min, best timing Sharpe>=sharpe_min, passes de-contam,
                                AND the sample was POWERED enough for clearing those floors to
                                mean anything. This is the ONLY verdict that starts a forward
                                clock, so the power condition is load-bearing, not cosmetic.
      SCREEN-WEAK            -- raw signal too weak to bother, AND the test was POWERED enough to
                                say so. Only this verdict is graveyard-grade negative knowledge.
      SCREEN-UNDERPOWERED    -- the effective sample could not resolve an effect at ic_min, so the
                                reading is uninformative in EITHER direction -- whether |IC| landed
                                under the floor or over it. "Could not tell": never record it as
                                "refuted", and never start a clock on it.

    horizon_days: the period of target_ret in days. Sharpe annualises by sqrt(365/horizon_days);
      leaving this at 1 while passing 20-day returns overstates Sharpe 4.47x (pure noise then
      scores 0.55 against the 0.5 floor) and slackens the sharpe_ceiling rail by the same factor.
    panel_width: number of cross-sectional units stacked into the flat arrays (1 = single series).
      Only n_eff/power use it; it does not change IC or Sharpe.
    """
    s = np.asarray(signal, dtype="float64")
    r = np.asarray(target_ret, dtype="float64")
    fwd = np.roll(r, -1)
    z = np.zeros(len(s))
    for t in range(zwin, len(s)):
        w = s[t - zwin:t]
        sd = w.std()
        z[t] = (s[t] - w.mean()) / sd if sd > 0 else 0.0
    zv, fv, tv = z[zwin:-1], fwd[zwin:-1], r[zwin:-1]
    if len(zv) < 30 or zv.std() == 0:
        return {"name": name, "verdict": "INSUFFICIENT-DATA", "n": len(zv)}

    ic = float(np.corrcoef(zv, fv)[0, 1]) if fv.std() else 0.0
    same = float(np.corrcoef(zv, tv)[0, 1]) if tv.std() else 0.0
    b = np.polyfit(tv, zv, 1)
    zr = zv - (b[0] * tv + b[1])                       # signal orthogonalised to same-period return
    ic_res = float(np.corrcoef(zr, fv)[0, 1]) if zr.std() and fv.std() else 0.0

    # Annualisation MUST match the target's period. target_ret are horizon_days-day returns, so a
    # year holds 365/horizon_days of them, not 365. The old hardcoded sqrt(365) overstated Sharpe by
    # sqrt(horizon_days) -- 2.24x at 5d, 4.47x at 20d -- which (a) made sharpe_min trivially
    # clearable (verified: pure noise on 20d returns scored 0.55 against a 0.5 floor) and (b) left
    # the sharpe_ceiling lookahead rail ~4.5x too loose exactly where slow signals live. Found
    # independently by three screening passes, 2026-07-26.
    ann = np.sqrt(365.0 / max(float(horizon_days), 1e-9))

    def _sh(sig: np.ndarray) -> float:
        rr = np.sign(sig) * fv
        return round(float(rr.mean() / rr.std() * ann), 2) if rr.std() else 0.0
    sh_mom, sh_rev = _sh(zv), _sh(-zv)
    best = max(abs(sh_mom), abs(sh_rev))

    # POWER. Overlapping horizon_days returns sampled daily carry ~n/horizon_days independent
    # observations. Reporting a null without the power to detect a real effect is not a refutation,
    # and graveyarding it as one destroys a hypothesis class on no evidence -- the graveyard is
    # permanent, so 'we could not tell' must never be recorded as 'it is dead'.
    # panel_width divides out cross-sectional stacking: a 139-symbol panel passed as one flat array
    # has n = symbol-days, and treating those as independent inflates every t-stat by
    # sqrt(panel_width) (~11.8x at 139 -- an apparent t=3.5 is really t=0.35).
    #
    # THE DEFLATOR ONLY EVER DEFLATES. Both corrections above model DEPENDENCE between rows, so
    # each can only ever remove independent observations -- n_eff must never exceed the number of
    # observations that actually exist. The divisor was taken raw, so a SUB-DAILY horizon (
    # horizon_days < 1, which is how every tape screen calls this: screen_moat.py passes
    # h/86400.0) made it a MULTIPLIER: at 60s bars horizon_days=6.9e-4, so n=10k was reported as
    # n_eff=14.4M and min_detectable_ic=0.0005. `powered` then came back true for free, which is
    # the exact inverse of the failure this block was written to prevent -- it was built so an
    # underpowered null could not be recorded as a refutation, and instead it was certifying
    # every sub-daily cell as powered no matter how little data stood behind it. Clamping at 1.0
    # makes non-overlapping bars carry n independent observations, which is what they are.
    #
    # CLAMP THE TWO FACTORS SEPARATELY, NEVER THEIR PRODUCT. They are independent corrections for
    # independent kinds of dependence, and clamping the product lets one cancel the other: at 60s
    # bars over a 45-symbol panel, horizon_days*panel_width = 0.031, which clamps to 1.0 and
    # silently discards the 45x cross-sectional stacking correction entirely. Each factor floors
    # at "no correction" on its own, then they compose.
    deflator = max(float(horizon_days), 1.0) * max(int(panel_width), 1)
    n_eff = max(len(zv) / deflator, 1.0)
    min_detectable_ic = float(1.96 / np.sqrt(n_eff))
    # 'powered' asks whether the SAMPLE could have detected an effect worth caring about (ic_min),
    # NOT whether the observed IC happens to be large. Only under the former does a null mean
    # "looked and it is not there"; under the latter every null would be self-certifying.
    powered = min_detectable_ic <= ic_min

    # LOOKAHEAD RAIL. A signal observed at t should not know MORE about t+1 than about t: for a
    # genuine lead, forward IC is normally weaker than the contemporaneous relationship. A whole-
    # period misalignment produces the opposite signature -- strong forward IC with near-zero
    # same-period corr -- and slips under a global ic_ceiling wherever honest contemporaneous
    # correlation is already high (measured ~0.34 on macro->crypto, vs a 0.35 ceiling). Flagged as
    # a diagnostic; ic_ceiling stays caller-tunable per axis rather than one global guess.
    ic_exceeds_contemporaneous = abs(ic) > max(abs(same), ic_min) * 1.5 and abs(ic) >= 0.15

    decontam_fail = abs(same) > contam_max or abs(ic_res) < 0.5 * abs(ic)
    implausible = abs(ic) > ic_ceiling or best > sharpe_ceiling    # alignment/lookahead rail
    if implausible or ic_exceeds_contemporaneous:
        verdict = "SUSPECT-LOOKAHEAD"                  # bithumb-class: too strong to be real
    elif best < sharpe_min or abs(ic) < ic_min:
        # Distinguish 'tested and refuted' from 'could not have detected it'. Only the former is
        # graveyard-grade negative knowledge.
        verdict = "SCREEN-WEAK" if powered else "SCREEN-UNDERPOWERED"
    elif decontam_fail:
        verdict = "TIMING-ARTIFACT"                    # angle-20 gate -- coinbase/turkey class
    elif not powered:
        # POWER CUTS BOTH WAYS. 'powered' used to gate only the negative branch, so a cell that
        # cleared ic_min/sharpe_min on a sample the harness had ALREADY declared blind was still
        # labelled SCREEN-INTERESTING -- announcing a find through the same instrument that just
        # reported it could not see. Origin cell:
        #   try_premium::T2_usdt_try_premium_vs_fxlake_eurcross::h20d
        #   n=77 ic=-0.0543 n_eff=3.9 min_detectable_ic=0.9989 powered=false sharpe_reversal=0.87
        # -- |IC| ~18x BELOW the harness's own detection floor, read as INTERESTING. At that n_eff
        # ~17% of pure-noise draws clear both floors, so the label was a coin flip with a name.
        # It matters because SCREEN-INTERESTING is the sole trigger for a forward clock (below),
        # and clocks are capped at MAX_FORWARD_SLOTS=12 and Holm-corrected: a slot spent on noise
        # BOTH burns a scarce slot AND raises the confirmation bar for every genuine candidate.
        # Below the detection floor the honest verdict is the one the negative branch already
        # gets -- could not tell -- NOT a kill (nothing was refuted) and NOT a find. Ordered after
        # decontam_fail so the angle-20 artifact gate keeps its precedence; neither branch can
        # reach SCREEN-INTERESTING, so this can only ever tighten the screen.
        verdict = "SCREEN-UNDERPOWERED"
    else:
        verdict = "SCREEN-INTERESTING"

    out = {"name": name, "n": len(zv), "ic": round(ic, 4),
           "sharpe_momentum": sh_mom, "sharpe_reversal": sh_rev,
           "same_period_corr": round(same, 3), "residual_ic": round(ic_res, 4),
           "decontam_passed": not decontam_fail, "implausible_leak": implausible,
           "horizon_days": float(horizon_days), "panel_width": int(panel_width),
           "n_eff": round(n_eff, 1),
           "min_detectable_ic": round(min_detectable_ic, 4), "powered": powered,
           "ic_exceeds_contemporaneous": ic_exceeds_contemporaneous,
           "verdict": verdict, "current_z": round(float(z[-1]), 3),
           "stage": "A (zero promotion authority)"}

    if clock and verdict == "SCREEN-INTERESTING":
        p = Path(clock)
        today = datetime.now(tz=UTC).date().isoformat()
        prev = p.read_text("utf-8").splitlines() if p.exists() else []
        if not prev or json.loads(prev[-1]).get("date") != today:
            with p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"date": today, "z20": out["current_z"],
                                     "screen": out}) + "\n")
    return out


# --------------------------------------------------------------- target/horizon sweep ----------
#: The mandated sweep grid. Targets and horizons are BOTH swept because the constitution's
#: TARGET/HORIZON SWEEP DUTY forbids the next-day-absolute reflex: an asset-SELECTION signal is
#: mechanically a cross-sectional claim and can read as pure noise against an absolute target,
#: which is how the dev-momentum episode lost a real mechanism.
DEFAULT_HORIZONS: tuple[int, ...] = (1, 5, 20)
DEFAULT_TARGETS: tuple[str, ...] = ("absolute", "cross_sectional")


def _period_returns(prices: np.ndarray, h: int) -> np.ndarray:
    """h-period returns in the alignment `stage_a_screen` CONTRACTS FOR, shape (T, N).

    THE HARNESS SHIFTS THE TARGET ITSELF -- `fwd = np.roll(r, -1)` -- so its argument is the
    return realised over period t (contemporaneous with signal[t]), and it predicts r[t+1]. Handing
    it an already-forward return double-shifts, testing signal[t] against the return from t+1 to
    t+1+h and leaving a one-period hole that no data ever fills. That is not merely lossy: it
    destroyed a true IC of ~0.45 into 0.004 in this module's own synthetic test, so a real
    mechanism would have been graveyarded as noise.

    So row t holds the return over the h periods ENDING at t (i.e. from t-h to t), which makes the
    harness's r[t+1] exactly the return from t to t+h -- strictly future relative to signal[t].
    Overlapping and daily-sampled is deliberate: it is what the harness's power model assumes, and
    it deflates n by horizon_days to recover the independent count.
    """
    out = np.full(prices.shape, np.nan, dtype="float64")
    if h < len(prices):
        out[h:] = prices[h:] / prices[:-h] - 1.0
    return out


def target_horizon_sweep(
    signal: np.ndarray, prices: np.ndarray, *, name: str,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    targets: Sequence[str] = DEFAULT_TARGETS,
    min_cross_section: int = 5,
    **screen_kwargs: Any,
) -> dict[str, Any]:
    """Screen one signal across the FULL {target} x {horizon} grid, counting every cell as a trial.

    THE WHOLE POINT IS THE DENOMINATOR. Running six cells and reporting the best one is a
    garden-of-forking-paths search with the forks left out of the write-up -- the single easiest
    way to manufacture a phantom edge while believing you found one. So this returns every cell it
    ran, and `n_trials` is the count of cells ATTEMPTED, not the count that produced a verdict:
    a cell dropped for thin data was still a fork in the path and still costs multiplicity budget.
    Feed `n_trials` straight to `deflated_sharpe_ratio`.

    signal, prices: aligned (T, N) panels -- rows are periods, columns are instruments. A 1-D
    array is treated as a single-instrument panel, for which the cross_sectional target is
    undefined and is skipped with a reason rather than silently returning noise.

    targets:
      "absolute"        -- the instrument's own forward return. A TIMING claim.
      "cross_sectional" -- forward return minus the cross-sectional mean of that period. A
                           SELECTION claim, and the mechanism-appropriate target for any signal
                           that ranks instruments against each other.

    Cells are stacked panel-wise and screened as one flat sample with panel_width=N, so the
    cross-sectional correlation that would otherwise inflate every t-stat by sqrt(N) is deflated
    out inside the harness.
    """
    sig = np.asarray(signal, dtype="float64")
    px = np.asarray(prices, dtype="float64")
    if sig.ndim == 1:
        sig = sig.reshape(-1, 1)
    if px.ndim == 1:
        px = px.reshape(-1, 1)
    if sig.shape != px.shape:
        raise ValueError(f"signal {sig.shape} and prices {px.shape} must be the same panel shape")
    n_inst = sig.shape[1]

    cells: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    attempted = 0
    for target in targets:
        for h in horizons:
            attempted += 1
            cell = f"{name}|{target}|{h}d"
            if target == "cross_sectional" and n_inst < min_cross_section:
                # NOT a quiet drop: a skipped cell is still a fork that was considered, so it is
                # named, and it still counts in n_trials above.
                skipped.append({"cell": cell, "target": target, "horizon_days": h,
                                "reason": f"cross-section of {n_inst} < min {min_cross_section}"})
                continue
            fwd = _period_returns(px, h)
            if target == "cross_sectional":
                # Sum/count rather than nanmean: the trailing h rows are all-NaN by construction,
                # and nanmean warns ("Mean of empty slice") on exactly those rows. They are then
                # masked out below anyway, so the warning is pure noise -- but a warning that is
                # always present is a warning nobody reads when it starts meaning something.
                ok = np.isfinite(fwd)
                valid = ok.sum(axis=1)
                total = np.where(ok, fwd, 0.0).sum(axis=1)
                mean = total / np.maximum(valid, 1)
                tgt = fwd - mean[:, None]
                tgt[valid < min_cross_section] = np.nan   # too thin a cross-section to demean
            else:
                tgt = fwd
            # FLATTEN INSTRUMENT-MAJOR (order="F"), never row-major. `stage_a_screen` z-scores
            # with a ROLLING TIME-SERIES window, so each instrument's history must be contiguous
            # in the flat array. C-order flattening interleaves them -- at 12 instruments a
            # zwin=20 window then spans under two periods and silently becomes a CROSS-SECTIONAL
            # z-score, which is a different statistic against a different null. Caught by
            # test_cross_sectional_target_finds_a_selection_signal_absolute_misses, where it
            # dragged a true IC of ~0.45 down to noise. Residual: the first `zwin` points of each
            # instrument are normalised partly against the previous instrument's tail --
            # zwin/T per instrument (0.4% at T=5000), and it cannot induce a spurious lead
            # because the contaminating values are unrelated to this instrument's target.
            mask = np.isfinite(sig) & np.isfinite(tgt)
            s_flat = sig.ravel(order="F")[mask.ravel(order="F")]
            t_flat = tgt.ravel(order="F")[mask.ravel(order="F")]
            if len(s_flat) < 3:
                skipped.append({"cell": cell, "target": target, "horizon_days": h,
                                "reason": f"only {len(s_flat)} aligned finite observations"})
                continue
            res = stage_a_screen(s_flat, t_flat, name=cell, horizon_days=float(h),
                                 panel_width=n_inst, **screen_kwargs)
            res.update({"target": target, "n_instruments": n_inst})
            cells.append(res)

    interesting = [c for c in cells if c["verdict"] == "SCREEN-INTERESTING"]
    return {
        "name": name,
        "grid": {"targets": list(targets), "horizons": [int(h) for h in horizons]},
        "n_trials": attempted,
        "n_screened": len(cells),
        "n_skipped": len(skipped),
        "skipped": skipped,
        "cells": cells,
        "n_interesting": len(interesting),
        # NAMED, not returned alone -- the caller still gets every cell, so a reader can always
        # see how many forks the winner beat.
        "best_cell": max(cells, key=lambda c: abs(c["ic"]))["name"] if cells else None,
        "dsr_note": (f"feed n_trials={attempted} to deflated_sharpe_ratio; reporting any single "
                     "cell without this denominator is a forking-paths result, not an edge"),
        "stage": "A (zero promotion authority -- a pass earns a forward clock, never capital)",
    }
