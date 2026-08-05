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
    # ...and it can NEVER EXCEED THE ROWS ACTUALLY OBSERVED. The divisor above is an OVERLAP
    # deflator: it exists to shrink n when horizon_days>1 sampled daily. At horizon_days<1 it
    # inverts and MULTIPLIES -- measured 2026-08-05 on the first intraday caller: 4,314 five-minute
    # bars reported n_eff=1,236,384, which drives min_detectable_ic to ~0.002 and makes `powered`
    # unconditionally True. That is the phantom-edge direction (a null gets recorded as
    # SCREEN-WEAK/graveyard-grade, and a noise cell can clear the power gate on the way to
    # SCREEN-INTERESTING and burn one of twelve Holm-corrected slots). screen_moat.py has been
    # passing horizon_days=6.9e-4 since it was written -- n_eff inflated ~1449x -- and
    # collect_perpdex_funding passes 1/3. Bounding by len(zv) can only ever LOWER n_eff, so it can
    # only ever tighten the screen; at horizon_days>=1 the bound is inactive and nothing changes.
    n_eff = max(min(float(len(zv)),
                    len(zv) / max(float(horizon_days) * max(int(panel_width), 1), 1e-9)), 1.0)
    min_detectable_ic = float(1.96 / np.sqrt(n_eff))
    # 'powered' asks whether the SAMPLE could have detected an effect worth caring about (ic_min),
    # NOT whether the observed IC happens to be large. Only under the former does a null mean
    # "looked and it is not there"; under the latter every null would be self-certifying.
    powered = min_detectable_ic <= ic_min

    # LOOKAHEAD RAIL, part 2: forward-exceeds-contemporaneous. A whole-period misalignment (a
    # KST-day candle labelled a UTC day, a close timestamped a bar early) produces strong forward
    # IC with weak same-period corr, and slips under the global ic_ceiling wherever honest
    # contemporaneous correlation is already high (measured ~0.34 on macro->crypto vs a 0.35
    # ceiling). BUT that same signature is the DEFINING SHAPE of a genuine leading indicator --
    # capital flows in at t, price answers at t+1 -- so the bare excess must not kill (2026-07-29:
    # it briefly did, and read SUSPECT-LOOKAHEAD onto the live kimchi axis directly above its own
    # shift test printing "no lookahead pattern"). Kill authority needs corroboration on BOTH of:
    #   RESOLVED: the excess clears the sampling-noise band for a correlation difference at this
    #     n_eff (1.96*sqrt(2/n_eff)); an unresolved excess at n_eff=121 is a costume, not a leak.
    #   TRANSLATES: misalignment has a fingerprint mechanism lacks -- lag the signal ONE period
    #     and a leaked series turns its forward skill into contemporaneous skill (same_lag1 jumps,
    #     ic_lag1 collapses), while a genuine lead just decays smoothly. corr(z[t-1], .) below.
    # Uncorroborated cases keep the annotation and fall through to the ordinary gates, where a
    # thin lead lands on SCREEN-UNDERPOWERED: clock keeps accruing, nothing killed, nothing found.
    ic_exceeds_contemporaneous = abs(ic) > max(abs(same), ic_min) * 1.5 and abs(ic) >= 0.15
    z1v = np.roll(z, 1)[zwin:-1]                       # signal lagged one period
    ic_lag1 = float(np.corrcoef(z1v, fv)[0, 1]) if z1v.std() and fv.std() else 0.0
    same_lag1 = float(np.corrcoef(z1v, tv)[0, 1]) if z1v.std() and tv.std() else 0.0
    shift_translates = (abs(same_lag1) > max(abs(ic_lag1), ic_min) * 1.5
                        and abs(same_lag1) > 0.5 * abs(ic))
    excess = abs(ic) - max(abs(same), ic_min) * 1.5
    resolved = excess > 1.96 * float(np.sqrt(2.0 / n_eff))

    # THE SHARPE RAIL IS CALIBRATED FOR DAILY DATA AND DOES NOT TRANSFER -- SO IT IS RESCALED HERE,
    # NOT AT EACH CALLER. `sharpe_ceiling=6.0` assumes horizon_days=1, and _sh ANNUALISES by
    # sqrt(365/horizon_days), so at 60s the factor is ~725 and PURE NOISE scored sharpe_reversal
    # 53.4 -> SUSPECT-LOOKAHEAD on six hypotheses whose ICs were 0.01-0.08. screen_moat.py found
    # that and fixed it in its own call site; the liquidation-reversion screen then hit the
    # identical wall from scratch, which is the tell that a correction living in one caller's
    # comment is not a control (it fires on recall). Rescaling by the same sqrt(1/horizon) the
    # annualisation applies keeps the rail at CONSTANT PER-PERIOD STRICTNESS instead of tightening
    # it 725-fold by accident. The IC ceiling is left ALONE at every horizon: a correlation does
    # not annualise, so 0.35 means the same thing at 60s as at a day.
    eff_sharpe_ceiling = float(sharpe_ceiling)
    if float(horizon_days) < 1.0:
        eff_sharpe_ceiling *= float(np.sqrt(1.0 / max(float(horizon_days), 1e-9)))

    decontam_fail = abs(same) > contam_max or abs(ic_res) < 0.5 * abs(ic)
    implausible = abs(ic) > ic_ceiling or best > eff_sharpe_ceiling   # alignment/lookahead rail
    if implausible or (ic_exceeds_contemporaneous and resolved and shift_translates):
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
           "sharpe_ceiling_applied": round(eff_sharpe_ceiling, 2),
           "n_eff": round(n_eff, 1),
           "min_detectable_ic": round(min_detectable_ic, 4), "powered": powered,
           "ic_exceeds_contemporaneous": ic_exceeds_contemporaneous,
           "ic_lag1": round(ic_lag1, 4), "same_lag1": round(same_lag1, 4),
           "shift_translates": shift_translates,
           "excess_resolved": resolved,
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
