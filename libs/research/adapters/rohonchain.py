"""Rohonchain adapter (REBUILT, numpy only) -- the Hawkes INTENSITY claim measured directly: are
large moves self-exciting? Events are bars whose absolute return exceeds a multiple of the
trailing vol; the adapter compares the observed clustering (the share of events within w bars of
a previous event) against the Poisson expectation for the same event rate. A ratio above one is
self-excitation; the measurement is donated, never the conclusion."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "rohonchain"
CAPABILITY_FAMILY = "causal_discovery"
LICENCE_EXPECTED = "N/A (published method)"
RUNS_WITHOUT_LIBRARY = True

K_SIGMA: tuple[float, ...] = (2.0, 3.0)
WINDOWS: tuple[int, ...] = (3, 6, 12)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 200]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 200 bars")
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        r = f.log_returns()
        vol = A.realised_vol(r, 48)
        rows: list[dict[str, Any]] = []
        for k in K_SIGMA:
            ev = np.zeros(r.shape[0], dtype=bool)
            m = np.isfinite(vol)
            ev[m] = np.abs(r[m]) > k * np.maximum(vol[m], 1e-12)
            idx = np.flatnonzero(ev)
            if idx.shape[0] < 8:
                rows.append({"k_sigma": k, "n_events": int(idx.shape[0]), "clustering": None})
                continue
            rate = idx.shape[0] / float(np.isfinite(vol).sum() or 1)
            for w in WINDOWS:
                trials += 1
                gaps = np.diff(idx)
                observed = float(np.mean(gaps <= w))
                expected = 1.0 - float((1.0 - rate) ** w)
                rows.append({"k_sigma": k, "window_bars": w, "n_events": int(idx.shape[0]),
                             "clustering": observed, "poisson_expected": expected,
                             "excitation_ratio": (observed / expected) if expected > 0 else None})
        measured = [r_ for r_ in rows if r_.get("excitation_ratio") is not None]
        reps.append({"kind": "self_excitation_profile", "symbol": f.symbol, "rows": rows,
                     "representation": ("observed clustering of large moves against the Poisson "
                                        "expectation at the same rate -- a Hawkes intensity "
                                        "read without fitting one")})
        if not measured:
            continue
        best = max(measured, key=lambda r_: abs(float(r_["excitation_ratio"]) - 1.0))
        ratio = float(best["excitation_ratio"])
        cands.append(A.candidate(
            "volume_spike" if ratio > 1.0 else "range_reversion", [f.symbol],
            f"{f.symbol} H1: moves beyond {best['k_sigma']} sigma cluster within "
            f"{best['window_bars']} bars {best['clustering']:.3f} of the time against a Poisson "
            f"expectation of {best['poisson_expected']:.3f} (ratio {ratio:.2f}, "
            f"{best['n_events']} events) -- "
            f"{'self-excitation' if ratio > 1 else 'dispersion'}",
            horizon=bundle.horizons[0], source=SYSTEM,
            evidence={"k_sigma": best["k_sigma"], "window_bars": best["window_bars"],
                      "excitation_ratio": ratio, "n_events": best["n_events"],
                      "method": "empirical inter-arrival clustering vs Poisson, numpy only"}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} (threshold, window) intensity cells")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
