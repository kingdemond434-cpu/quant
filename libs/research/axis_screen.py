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
                   sharpe_min: float = 0.5, clock: str | None = None) -> dict[str, Any]:
    """Screen a signal against NEXT-period target returns with the mandatory angle-20 gate.

    signal[t], target_ret[t] must be aligned same-period arrays (target_ret[t] = return realised
    over period t). The function predicts target_ret[t+1] from a z-scored signal[t], and checks
    that the signal LEADS rather than COINCIDES.

    Verdict:
      SCREEN-INTERESTING     -- |IC|>=ic_min, best timing Sharpe>=sharpe_min, AND passes de-contam
      TIMING-ARTIFACT        -- fails de-contam: |same-period corr|>contam_max OR residual IC
                                collapses below half the raw IC (the coinbase/turkey failure mode)
      SCREEN-WEAK            -- raw signal too weak to bother
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

    def _sh(sig: np.ndarray) -> float:
        rr = np.sign(sig) * fv
        return round(float(rr.mean() / rr.std() * np.sqrt(365)), 2) if rr.std() else 0.0
    sh_mom, sh_rev = _sh(zv), _sh(-zv)
    best = max(abs(sh_mom), abs(sh_rev))

    decontam_fail = abs(same) > contam_max or abs(ic_res) < 0.5 * abs(ic)
    if best < sharpe_min or abs(ic) < ic_min:
        verdict = "SCREEN-WEAK"
    elif decontam_fail:
        verdict = "TIMING-ARTIFACT"                    # angle-20 gate -- coinbase/turkey class
    else:
        verdict = "SCREEN-INTERESTING"

    out = {"name": name, "n": len(zv), "ic": round(ic, 4),
           "sharpe_momentum": sh_mom, "sharpe_reversal": sh_rev,
           "same_period_corr": round(same, 3), "residual_ic": round(ic_res, 4),
           "decontam_passed": not decontam_fail, "verdict": verdict,
           "current_z": round(float(z[-1]), 3), "stage": "A (zero promotion authority)"}

    if clock and verdict == "SCREEN-INTERESTING":
        p = Path(clock)
        today = datetime.now(tz=UTC).date().isoformat()
        prev = p.read_text("utf-8").splitlines() if p.exists() else []
        if not prev or json.loads(prev[-1]).get("date") != today:
            with p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"date": today, "z20": out["current_z"],
                                     "screen": out}) + "\n")
    return out
