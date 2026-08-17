"""SIGNAL_INFORMATION_GATE (Jesse-style rule significance, strengthened).

Does the ENTRY TIMING itself contain information, ignoring exits/sizing?

Per strategy cell (sym.fam.side):
  - rebuild signals via the hunt's own family functions
  - forward log-return over horizons 1/2/5/10 bars conditioned on entry bar
  - LONG / SHORT separated
  - empirical null: block-bootstrap (block 5) reshuffles of the signal bar
    indices, 999 reps
  - p = (1 + #null_mean >= obs_mean) / (reps + 1), two-sided
  - verdict per side: INFORMED (p<0.05 at any horizon, n>=60), NULL, SPARSE

A signal failing at 1-bar may carry information at a different horizon; the
gate reports the full profile instead of a single pass/fail.

Usage: python signal_gate.py <hunt_module> [sym [sym ...]]
Writes: reports/signal_gate_<hunt>.json
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

HORIZONS = (1, 2, 5, 10)
REPS = 999
BLOCK = 5


def gate_cell(c: np.ndarray, sig_times: list, n_min: int = 60) -> dict | None:
    """Forward-return information test for one cell. sig_times = pandas indices
    of the signal bars (already shifted by the engine convention: +1)."""
    c = np.asarray(c, dtype=float)
    n = len(c)
    if len(sig_times) < n_min:
        return {"n": len(sig_times), "verdict": "SPARSE", "horizons": {}}
    lc = np.log(c)
    bars = np.array([s for s in sig_times if 1 <= s < n - max(HORIZONS)], dtype=int)
    if len(bars) < n_min:
        return {"n": len(bars), "verdict": "SPARSE", "horizons": {}}
    rng = np.random.default_rng(7)
    out = {}
    informed = False
    for h in HORIZONS:
        fwd = lc[bars + h] - lc[bars]
        obs = fwd.mean()
        nblk = int(np.ceil(len(bars) / BLOCK))
        null = np.empty(REPS)
        for r in range(REPS):
            starts = rng.integers(0, n - h - 1, size=nblk)
            perm = np.concatenate([np.arange(s, s + BLOCK) for s in starts])[:len(bars)]
            null[r] = lc[perm + h] - lc[perm]
            null[r] = null[r].mean()
        p_up = float((1 + (null >= obs).sum()) / (REPS + 1))
        p_dn = float((1 + (null <= obs).sum()) / (REPS + 1))
        p = min(p_up, p_dn)
        out[h] = {"mean_log_ret": float(obs), "p_two_sided": p,
                  "null_mean": float(null.mean()), "null_p05": float(np.percentile(null, 5)),
                  "null_p95": float(np.percentile(null, 95))}
        if p < 0.05:
            informed = True
    return {"n": len(bars), "verdict": "INFORMED" if informed else "NULL", "horizons": out}


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python signal_gate.py <hunt_module> [sym ...]")
        return 1
    mod = importlib.import_module(sys.argv[1])
    fams = mod.FAMILIES
    syms = sys.argv[2:] or mod.SYMS
    log = open(BASE / "logs" / "signal_gate_console.txt", "w", encoding="utf-8")

    def tprint(*a) -> None:
        m = " ".join(str(x) for x in a)
        print(m, flush=True)
        log.write(m + "\n")
        log.flush()

    tprint(f"{'cell':<36} {'n':>5} {'verdict':<8} horizons(p):")
    report: dict = {"hunt": sys.argv[1], "cells": []}
    import pandas as pd
    from mt5desk import families
    from run_hunt17 import resample
    for sym in syms:
        fp = BASE / "data" / "universe" / f"{sym}_H1.parquet"
        if not fp.exists():
            continue
        h1 = families._h1(pd.read_parquet(fp))
        h4, d1 = resample(h1)
        c = h4["close"].to_numpy(float)
        for fname, fn in fams.items():
            for side in (1, -1):
                tag = f"{sym}.{fname}.{'L' if side > 0 else 'S'}"
                try:
                    sigs = fn(h4, d1, side)
                except Exception as e:
                    tprint(f"{tag:<36} ERROR {e!r}")
                    continue
                sig_times = []
                idx = h4.index
                for s in sigs:
                    loc = int(np.searchsorted(idx.to_numpy().astype("datetime64[ns]").astype("int64"),
                                              pd.Timestamp(s.time).value))
                    sig_times.append(loc + 1)
                g = gate_cell(c, sig_times)
                if g is None:
                    continue
                ps = " ".join(f"h{h}:{g['horizons'][h]['p_two_sided']:.3f}" for h in HORIZONS
                              if h in g["horizons"])
                tprint(f"{tag:<36} {g['n']:5d} {g['verdict']:<8} {ps}")
                report["cells"].append({"cell": tag, "side": "LONG" if side > 0 else "SHORT", **g})
    (BASE / "reports" / f"signal_gate_{sys.argv[1].replace('run_', '')}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    tprint(f"\nINFORMED: {sum(1 for c in report['cells'] if c['verdict'] == 'INFORMED')} "
           f"/ {len(report['cells'])} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())