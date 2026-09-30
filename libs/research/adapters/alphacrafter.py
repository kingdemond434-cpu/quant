"""AlphaCrafter adapter (REBUILT, numpy only) -- the discovery -> REGIME-AWARE SELECTION ->
execution harness rebuilt as a conditional measurement: bars are labelled by trailing volatility
tercile, and the lag-1 return autocorrelation is measured INSIDE each regime. The regime where
reversion is strongest is donated with its label attached, because a mechanism that only lives
in one regime is a different hypothesis from one that does not."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alphacrafter"
CAPABILITY_FAMILY = "regime_selection"
LICENCE_EXPECTED = "N/A (published architecture)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 240]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 240 bars")
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        r = f.log_returns()
        vol = A.realised_vol(r, 24)
        ok = np.isfinite(vol[:-1]) & np.isfinite(r[1:]) & np.isfinite(r[:-1])
        if int(ok.sum()) < 90:
            continue
        v, prev, nxt = vol[:-1][ok], r[:-1][ok], r[1:][ok]
        edges = np.percentile(v, [33.3, 66.7])
        labels = np.digitize(v, edges)
        rows: list[dict[str, Any]] = []
        for lab, name in enumerate(("low_vol", "mid_vol", "high_vol")):
            m = labels == lab
            trials += 1
            if int(m.sum()) < 30 or float(np.std(prev[m])) <= 0 or float(np.std(nxt[m])) <= 0:
                rows.append({"regime": name, "n": int(m.sum()), "autocorr_lag1": None})
                continue
            ac = float(np.corrcoef(prev[m], nxt[m])[0, 1])
            rows.append({"regime": name, "n": int(m.sum()), "autocorr_lag1": ac,
                         "mean_abs_return": float(np.mean(np.abs(nxt[m]))),
                         "vol_range": [float(v[m].min()), float(v[m].max())]})
        reps.append({"kind": "regime_conditional_autocorrelation", "symbol": f.symbol,
                     "regimes": rows, "window": 24,
                     "representation": ("lag-1 return autocorrelation inside each trailing-vol "
                                        "tercile: where the mechanism lives, not whether")})
        measured = [r_ for r_ in rows if r_["autocorr_lag1"] is not None]
        if not measured:
            continue
        pick = min(measured, key=lambda r_: float(r_["autocorr_lag1"]))
        ac = float(pick["autocorr_lag1"])
        family = "vol_mean_reversion" if ac < 0 else "momentum_volgate"
        cands.append(A.candidate(
            family, [f.symbol],
            f"{f.symbol} H1: inside the {pick['regime']} regime (n={pick['n']}) the lag-1 "
            f"return autocorrelation is {ac:+.4f} -- a regime-conditional "
            f"{'reversion' if ac < 0 else 'continuation'} hypothesis, not an unconditional one",
            horizon=bundle.horizons[0], source=SYSTEM,
            evidence={"regime": pick["regime"], "autocorr_lag1": ac, "n": pick["n"],
                      "regimes": rows, "method": "trailing-vol tercile conditioning, numpy"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "no frame carried enough bars per regime")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(reps)} frames split into vol terciles")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
