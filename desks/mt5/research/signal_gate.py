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

Usage: python signal_gate.py <hunt_module> [report_json [sym ...]]
  report_json: optional reports/hunt18_*.json experiment -> gates ONLY that
  experiment's (fam, side, params) across the universe (or listed syms),
  using the hunt's own signal rebuild. Without a report, gates every family
  with default params (generic mode).
Writes: reports/signal_gate_<stem>.json
"""

from __future__ import annotations

import importlib
import json
import sys
import time
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
        hi = n - h - BLOCK
        if hi < 1:
            continue
        starts = rng.integers(0, hi, size=(REPS, nblk))
        perm = (starts[:, :, None] + np.arange(BLOCK)).reshape(REPS, -1)[:, :len(bars)]
        fwd_null = lc[perm + h] - lc[perm]
        null = fwd_null.mean(axis=1)
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
        print("usage: python signal_gate.py <hunt_module> [report_json [sym ...]]")
        return 1
    mod = importlib.import_module(sys.argv[1])
    fams = mod.FAMILIES
    log = open(BASE / "logs" / "signal_gate_console.txt", "w", encoding="utf-8")

    def tprint(*a) -> None:
        m = " ".join(str(x) for x in a)
        print(m, flush=True)
        log.write(m + "\n")
        log.flush()

    report_path = sys.argv[2] if len(sys.argv) > 2 else None
    syms = sys.argv[3:] if report_path else sys.argv[2:]
    import pandas as pd
    from mt5desk import families
    from run_hunt17 import resample
    from datetime import datetime, timezone

    def run_tasks(tasks: list[tuple[str, int, dict]], stem: str,
                  syms: list[str]) -> int:
        out_path = BASE / "reports" / f"signal_gate_{stem}.json"
        done_tags: set[str] = set()
        report: dict = {"hunt": sys.argv[1], "experiment": stem, "cells": []}
        if out_path.exists():
            try:
                prev = json.loads(out_path.read_text(encoding="utf-8"))
                report = prev
                done_tags = {c.get("cell") for c in prev.get("cells", [])}
            except Exception:
                pass
        tprint(f"gating {len(tasks)} task(s) on {len(syms)} syms -> "
               f"reports/signal_gate_{stem}.json (resume {len(done_tags)} cells)")
        for sym in syms:
            fp = BASE / "data" / "universe" / f"{sym}_H1.parquet"
            if not fp.exists():
                continue
            h1 = families._h1(pd.read_parquet(fp))
            h4, d1 = resample(h1)
            c = h4["close"].to_numpy(float)
            for fname, side, params in tasks:
                fn = fams[fname]
                tag = f"{sym}.{fname}.{side}"
                if tag in done_tags:
                    continue
                try:
                    sigs = fn(h4, d1, side, **params) if params else fn(h4, d1, side)
                except Exception as e:
                    tprint(f"{tag:<36} ERROR {e!r}")
                    continue
                if sigs:
                    idx = h4.index
                    arr_i = idx.to_numpy().astype("datetime64[ns]").astype("int64")
                    sig_vals = np.array([pd.Timestamp(s.time).value for s in sigs],
                                        dtype="int64")
                    sig_times = (np.searchsorted(arr_i, sig_vals) + 1).tolist()
                else:
                    sig_times = []
                try:
                    g = gate_cell(c, sig_times)
                except Exception as e:
                    tprint(f"{tag:<36} GATE-ERROR {e!r}")
                    continue
                if g is None:
                    continue
                ps = " ".join(f"h{h}:{g['horizons'][h]['p_two_sided']:.3f}" for h in HORIZONS
                              if h in g["horizons"])
                tprint(f"{tag:<36} {g['n']:5d} {g['verdict']:<8} {ps}")
                report["cells"].append(
                    {"cell": tag, "side": "LONG" if side > 0 else "SHORT", **g})
                (BASE / "reports" / f"signal_gate_{stem}.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8")
        (BASE / "reports" / f"signal_gate_{stem}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        (BASE / "reports" / f"DONE_signal_gate_{stem}").write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        tprint(f"\nINFORMED: {sum(1 for c in report['cells'] if c['verdict'] == 'INFORMED')} "
               f"/ {len(report['cells'])} cells")
        return 0

    def tasks_from_report(rp: Path, syms_override: list[str]) -> tuple[list, str, list] | None:
        try:
            exp = json.loads(rp.read_text(encoding="utf-8"))
        except Exception as e:
            tprint(f"{rp.name}: unreadable {e!r}")
            return None
        fam = exp.get("fam") or exp.get("family")
        side = 1 if (exp.get("side") or "LONG") == "LONG" else -1
        params = dict(exp.get("params") or {})
        if not params and exp.get("param") is not None:
            pl = mod.PARAMS.get(fam)
            if pl:
                params = dict(pl[int(exp["param"])])
        if fam not in fams:
            tprint(f"unknown family {fam} in {rp.name}")
            return None
        exp_syms = set()
        for c in exp.get("all", []) + exp.get("cells", []):
            if isinstance(c, dict):
                exp_syms.add(str(c.get("sym") or c.get("cell", "")).split(".")[0])
            else:
                exp_syms.add(str(c).split(".")[0])
        return [(fam, side, params)], rp.stem, (syms_override or sorted(exp_syms))

    if report_path and report_path != "-":
        rp = Path(report_path)
        if not rp.is_absolute() and not rp.parts[0] == "reports":
            rp = BASE / "reports" / rp
        elif not rp.is_absolute():
            rp = BASE / rp
        t = tasks_from_report(rp, syms)
        if t is None:
            return 1
        return run_tasks(*t)

    while True:
        exps = sorted((BASE / "reports").glob("hunt18_*.json"))
        if exps:
            processed = 0
            for p in exps:
                dm = BASE / "reports" / f"DONE_signal_gate_{p.stem}"
                if dm.exists():
                    continue
                t = tasks_from_report(p, sys.argv[2:] or None)
                if t is not None:
                    run_tasks(*t)
                    processed += 1
            if processed == 0:
                tprint("all hunt18 experiments already gated")
        else:
            tprint("no hunt18 experiments yet")
        # Reports arrive asynchronously from the experiment worker. Poll cheaply once per minute;
        # an unconditional hour made a completed hypothesis wait up to 59 minutes for validation.
        time.sleep(60)

    tasks = [(f, 1, {}) for f in fams] + [(f, -1, {}) for f in fams]
    stem = sys.argv[1].replace("run_", "")
    return run_tasks(tasks, stem, syms or mod.SYMS)


if __name__ == "__main__":
    sys.exit(main())
