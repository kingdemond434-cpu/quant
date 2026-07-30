"""Does the campaign matrix's min_len truncation explain the 0/420 significance veto?

MEASUREMENT ONLY -- changes no threshold, promotes nothing, loosens no gate.

orchestrator.py builds the campaign matrix as ``r[-min_len:]`` for every candidate, so the
WHOLE campaign is truncated to the SHORTEST member.  Measured on the real 420-candidate
campaign that produced 420-tested/0-survivors: min_len=310 while the median candidate carries
2134 observations, so 130,200 of 759,444 available observations (83%) are discarded -- and they
are discarded from exactly the statistic that is now the sole remaining blocker.  Romano-Wolf
power scales with sqrt(T); if T is short by 6.9x, a real edge cannot clear family-wise control
however good it is, and "0 survivors" would again be measuring the instrument.

This script computes the alternative windows and re-runs the SAME statistic on each, so the
next build decision rests on a number instead of an argument:

  min_len      : today's rule -- T = shortest candidate, N = all
  max_obs      : the rectangle maximising retained observations (drop the shortest candidates,
                 keep every candidate that can support the resulting window)
  max_T_at_90N : the longest window that still retains >= 90% of candidates

For each: T, N, retained observations, min adjusted p, and how many candidates Romano-Wolf
rejects at alpha=0.05.  A window is only interesting if it is BOTH longer and still honest --
dropping candidates shrinks the multiplicity family, which is why the retained-N is reported
next to every verdict rather than buried.
"""

from __future__ import annotations

import json
import pickle
import sys
import time

import numpy as np

from libs.validation.stepwise import romano_wolf_stepdown

_PKL = "_audit_prepared.pkl"


def _log(msg: str) -> None:
    print(msg, flush=True)


def _windows(lengths: np.ndarray) -> dict[str, tuple[int, int]]:
    """Candidate (T, n_kept) windows. Keeping the n longest candidates permits T = their min."""
    order = np.sort(lengths)[::-1]  # descending
    n = len(order)
    # Keeping the k longest candidates allows T = order[k-1]; retained obs = k * T.
    retained = np.array([(k + 1) * order[k] for k in range(n)])
    k_best = int(np.argmax(retained))
    k_90 = max(1, int(np.floor(0.90 * n))) - 1
    return {
        "min_len": (int(order[-1]), n),
        "max_obs": (int(order[k_best]), k_best + 1),
        "max_T_at_90N": (int(order[k_90]), k_90 + 1),
    }


def main() -> int:
    t0 = time.time()
    with open(_PKL, "rb") as fh:
        prepared = pickle.load(fh)
    series = [np.asarray(e[-1], dtype="float64") for e in prepared]
    lengths = np.array([len(s) for s in series])
    _log(f"{len(series)} candidates: min={lengths.min()} median={int(np.median(lengths))} "
         f"max={lengths.max()} total_obs={int(lengths.sum())}")

    report: dict[str, object] = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_candidates": len(series),
        "obs_available": int(lengths.sum()),
        "windows": {},
    }

    for name, (T, n_keep) in _windows(lengths).items():
        # Keep the n_keep LONGEST candidates, each truncated to its last T observations.
        keep = np.argsort(lengths)[::-1][:n_keep]
        mat = np.column_stack([series[i][-T:] for i in keep])
        t = time.time()
        res = romano_wolf_stepdown(mat)
        adj = np.asarray(res.adjusted_p)
        rej = np.asarray(res.rejected)
        row = {
            "T": T, "N": int(mat.shape[1]), "retained_obs": int(mat.size),
            "retained_frac_of_available": round(float(mat.size) / float(lengths.sum()), 4),
            "min_adjusted_p": round(float(adj.min()), 4),
            "n_rejected_at_5pct": int(rej.sum()),
            "secs": round(time.time() - t, 1),
        }
        report["windows"][name] = row  # type: ignore[index]
        _log(f"  {name:14s} T={T:5d} N={row['N']:4d} obs={row['retained_obs']:7d} "
             f"({100 * row['retained_frac_of_available']:4.1f}% of available)  "
             f"min_adj_p={row['min_adjusted_p']:.4f}  rejected={row['n_rejected_at_5pct']:3d}"
             f"  [{row['secs']}s]")

    out = "reports/matrix_window_measurement.json"
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    _log(f"wrote {out}  [total {time.time() - t0:.0f}s]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
