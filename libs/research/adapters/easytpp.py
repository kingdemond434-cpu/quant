"""EasyTPP adapter -- the bundle's large-move events (|r| > 2 sigma) exported as the
EasyTPP event-sequence DATASET (time_since_start, time_since_last_event, type_event) per
symbol, with the empirical inter-event statistics as a representation. The trainer needs
a YAML experiment config and is not driven from this adapter; the dataset is its input.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "easytpp"
CAPABILITY_FAMILY = "point_process"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 6


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    tpp = A.library("easy_tpp")
    if tpp is None:
        return A.unmeasured(SYSTEM, bundle, "easy_tpp is not importable here (pip install "
                                            "easy-tpp==0.3.0)")
    import numpy as np
    datasets: list[dict[str, Any]] = []
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        r = f.log_returns()
        if r.shape[0] < 300:
            continue
        sd = float(np.std(r))
        idx = np.flatnonzero(np.abs(r) > 2.0 * sd)
        if idx.shape[0] < 5:
            continue
        gaps = np.diff(idx).astype(float)
        seq = [{"time_since_start": float(i - idx[0]), "time_since_last_event": float(g),
                "type_event": int(r[i] > 0)} for i, g in zip(idx[1:], gaps, strict=True)]
        datasets.append({"kind": "event_sequence", "symbol": f.symbol, "format": "easy_tpp",
                         "n_events": len(seq), "event_types": {"0": "down", "1": "up"},
                         "threshold": "2 sigma of H1 log returns", "sequence": seq[-200:]})
        reps.append({"kind": "inter_event_statistics", "symbol": f.symbol,
                     "mean_gap_bars": float(gaps.mean()), "cv_gap": float(gaps.std()
                                                                          / max(gaps.mean(),
                                                                                1e-12)),
                     "clustering": float((gaps <= 3).mean()),
                     "representation": "a coefficient of variation above 1 says large moves "
                                       "cluster (self-exciting); a Hawkes fit is the next step"})
    return A.packet(SYSTEM, bundle, trials=0, datasets=datasets, representations=reps,
                    note="dataset export; the EasyTPP trainer is a YAML-configured run")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
