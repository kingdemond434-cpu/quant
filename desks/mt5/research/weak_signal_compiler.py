"""Compile sub-cost predictors into one candidate that can cover its costs -- and prove it forward.

    members  = validity-passing, power-deficient cells from the last gauntlet sweep
    train    = first WALK-FORWARD block: shrunk weights from each member's signal-bar returns
    test     = every later block: the FROZEN combination's forward return, net of cost
    propose  = only if the out-of-sample combination clears cost AND deflates AND beats its
               strongest single member out of sample

THE LAST CONDITION IS THE ONE THAT MATTERS. An "ensemble" that is really its best member with
decoration is the best member with a bigger search behind it. It must be worth more than any one
of its parts, out of sample, or it is not an ensemble.

WHERE MEMBERS COME FROM. `reports/universal_gates_external.json` records every cell the gauntlet
built and which gates it failed. A cell that passed every VALIDITY gate and failed only POWER
gates -- deflated_sharpe, expected_value -- is a predictor with too little edge to stand alone,
which is exactly Brown's cloud cover. Those are the members. Cells that failed validity are not:
a leak combined with a leak is a leak.

THE WEIGHTS ARE RIDGE-SHRUNK TOWARD EQUAL. With a few hundred trades per member and dozens of
members, unconstrained weights would fit the training block and nothing else. The shrinkage
constant is the same n/(n+k) idiom as everywhere else, on the member's own training trade count.

PROPOSES ONLY. The compiled ensemble is donated as an EXACT_RECIPE candidate for the `ensemble`
family with its members and frozen weights as params. The gauntlet judges it as one cell.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import proposer_common as pc  # noqa: E402

SOURCE = "weak_signal_ensemble"
REPORT = _DESK / "reports" / "weak_signal_compiler.json"
GATES = _DESK / "reports" / "universal_gates_external.json"
POWER_GATES = frozenset({"deflated_sharpe", "expected_value", "in_sample_screen"})
MAX_MEMBERS = 24
MIN_MEMBERS = 4
K_WEIGHT = 40.0
N_BLOCKS = 4
THRESHOLDS = (0.3, 0.5, 0.7)


def power_deficient(max_per_symbol: int = MAX_MEMBERS) -> dict[str, list[dict]]:
    """symbol -> member cells that passed every validity gate and failed only power gates."""
    try:
        doc = json.loads(GATES.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, list[dict]] = {}
    for v in doc.get("verdicts") or []:
        if not isinstance(v, dict) or v.get("unmeasured"):
            continue
        gates = v.get("gates") or {}
        failed = {k for k, g in gates.items() if isinstance(g, dict) and g.get("passed") is False}
        if not failed or not failed <= POWER_GATES:
            continue
        sym = str(v.get("sym") or v.get("symbol") or "")
        fam = str(v.get("family") or "")
        params = v.get("params") or {}
        if not sym or not fam or fam == "ensemble":
            continue
        out.setdefault(sym, []).append({"symbol": sym, "family": fam, "params": dict(params),
                                        "sharpe": float((gates.get("in_sample_screen") or {})
                                                        .get("sharpe") or 0.0)})
    for sym in out:
        out[sym] = sorted(out[sym], key=lambda m: -abs(m["sharpe"]))[:max_per_symbol]
    return out


def _runner_factory(meta: dict):
    """A member-signal builder that goes through the gauntlet's own cell construction."""
    def _run(symbol: str, family: str, params: dict, df: pd.DataFrame):
        try:
            from external_gauntlet import build_cell
            fn, kwargs = build_cell(symbol, family, params, meta, df)
        except Exception:                                        # noqa: BLE001
            return []
        if fn is None:
            return []
        try:
            return fn(df, **kwargs)
        except Exception:                                        # noqa: BLE001
            return []
    return _run


def _member_returns(d: pd.DataFrame, sigs, hold: int) -> pd.Series:
    """Signed forward log return at each signal bar, on the bar index. 0 where no signal."""
    c = d["close"].astype(float).to_numpy()
    o = d["open"].astype(float).to_numpy()
    pos = {ts: i for i, ts in enumerate(d.index)}
    out = pd.Series(0.0, index=d.index)
    for s in sigs:
        i = pos.get(s.time)
        if i is None or i + 1 + hold >= len(c) or o[i + 1] <= 0:
            continue
        out.iloc[i] = np.log(c[min(i + 1 + hold, len(c) - 1)] / o[i + 1]) * int(s.side)
    return out


def compile_symbol(sym: str, members: list[dict], meta: dict, hold: int = 12,
                   budget_s: float = 600.0) -> list[dict]:
    d = pc.bars(sym)
    if d is None or len(d) < 24 * 400:
        return []
    cost = pc.cost_frac(sym, meta, d["close"])
    if cost is None:
        return []
    unfillable = pc.artifact_hours(d)
    runner = _runner_factory(meta)
    started = time.monotonic()
    sig_by_member: dict[int, list] = {}
    for k, m in enumerate(members):
        if time.monotonic() - started > budget_s:
            break
        sigs = runner(m["symbol"], m["family"], m["params"], d)
        if len(sigs) >= 20:
            sig_by_member[k] = sigs
    if len(sig_by_member) < MIN_MEMBERS:
        return []
    keep = sorted(sig_by_member)
    ret = pd.DataFrame({k: _member_returns(d, sig_by_member[k], hold) for k in keep})
    n = len(d)
    edges = [int(n * i / N_BLOCKS) for i in range(N_BLOCKS + 1)]
    rows = []
    for thr in THRESHOLDS:
        oos_all: list[float] = []
        best_single_oos: list[float] = []
        weights_used = None
        for b in range(1, N_BLOCKS):
            tr = ret.iloc[edges[0]:edges[b]]
            te_idx = d.index[edges[b]:edges[b + 1]]
            # SHRUNK WEIGHTS: each member's mean return at its own signal bars, shrunk toward
            # zero by its trade count, then normalised. Sign carries direction; magnitude carries
            # how much it has earned the right to vote.
            w = []
            for k in keep:
                col = tr[k]
                act = col[col != 0.0]
                mu = float(act.mean()) if act.size else 0.0
                lam = act.size / (act.size + K_WEIGHT)
                w.append(lam * mu)
            w = np.asarray(w)
            if not np.any(w != 0.0):
                continue
            w = w / (np.abs(w).sum() or 1.0)
            weights_used = [round(float(x), 6) for x in w]
            # Frozen combination on the test block: vote at each bar, trade when it crosses.
            from mt5desk.family_ensemble import family_ensemble
            mem = [dict(members[k]) for k in keep]
            sub = d.loc[: te_idx[-1]]
            sigs = family_ensemble(sub, members=mem, weights=list(w), threshold=thr,
                                   hold_bars=hold,
                                   _runner=lambda s_, f_, p_, df_, _c={k: sig_by_member[k]
                                                                        for k in keep}, _m=mem:
                                   _c[[i for i, mm in enumerate(_m)
                                       if mm["symbol"] == s_ and mm["family"] == f_
                                       and mm["params"] == p_][0]] if any(
                                       mm["symbol"] == s_ and mm["family"] == f_
                                       and mm["params"] == p_ for mm in _m) else [])
            sigs = [s for s in sigs if s.time >= te_idx[0]]
            sc = pc.screen(d, sigs, cost, unfillable)
            if sc:
                oos_all.append(sc["net_per_trade"] * sc["n_independent"])
            # The strongest single member on the SAME test block, by training Sharpe.
            best_k = max(keep, key=lambda k: abs(float(tr[k][tr[k] != 0].mean() or 0.0))
                         if (tr[k] != 0).any() else 0.0)
            single = pc.screen(d, [s for s in sig_by_member[best_k] if s.time >= te_idx[0]
                                   and s.time <= te_idx[-1]], cost, unfillable)
            if single:
                best_single_oos.append(single["net_per_trade"] * single["n_independent"])
        if weights_used is None:
            continue
        full_sigs = None
        try:
            from mt5desk.family_ensemble import family_ensemble as fe
            full_sigs = fe(d, members=[dict(members[k]) for k in keep],
                           weights=[float(x) for x in weights_used], threshold=thr,
                           hold_bars=hold,
                           _runner=lambda s_, f_, p_, df_, _c=sig_by_member, _keep=keep,
                           _m=members: _c[next(k for k in _keep if _m[k]["symbol"] == s_
                                              and _m[k]["family"] == f_
                                              and _m[k]["params"] == p_)])
        except StopIteration:
            full_sigs = []
        sc = pc.screen(d, [s for s in (full_sigs or []) if s.time >= d.index[edges[1]]],
                       cost, unfillable)
        if sc is None:
            continue
        oos_total = float(np.sum(oos_all)) if oos_all else float("nan")
        single_total = float(np.sum(best_single_oos)) if best_single_oos else float("nan")
        rows.append({"cell": f"{sym}.ensemble@{thr}", "symbol": sym, "threshold": thr,
                     "hold_bars": hold, "n_members": len(keep),
                     "members": [dict(members[k]) for k in keep], "weights": weights_used,
                     "oos_net_total": round(oos_total, 8),
                     "best_single_oos_net_total": round(single_total, 8),
                     "beats_best_member": bool(np.isfinite(oos_total) and np.isfinite(single_total)
                                               and oos_total > single_total), **sc})
    return rows


def run(symbols: list[str] | None = None, budget_s: float = 2400.0) -> dict:
    meta = pc.universe_meta()
    pool = power_deficient()
    if symbols:
        want = {s.upper() for s in symbols}
        pool = {s: m for s, m in pool.items() if s.upper() in want}
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    started = time.monotonic()
    for sym, members in sorted(pool.items(), key=lambda kv: -len(kv[1])):
        if time.monotonic() - started > budget_s:
            skipped[sym] = "budget exhausted"
            continue
        if len(members) < MIN_MEMBERS:
            skipped[sym] = f"{len(members)} power-deficient members, needs {MIN_MEMBERS}"
            continue
        got = compile_symbol(sym, members, meta, budget_s=max(60.0, budget_s / max(1, len(pool))))
        if not got:
            skipped[sym] = "members could not be built or combination never traded"
        rows.extend(got)
    rows = pc.deflate(rows)
    for r in rows:
        r["proposed"] = bool(r.get("proposed") and r.get("beats_best_member"))
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "ensemble",
        {"members": r["members"], "weights": r["weights"], "threshold": r["threshold"],
         "hold_bars": r["hold_bars"]},
        mechanism=(f"{r['n_members']} sub-cost predictors combined by frozen shrunk weights; "
                   f"the combination clears cost out of sample where no member does alone"),
        title=f"{r['cell']} {r['n_members']} members",
        evidence={k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                    "cost_frac", "t_gross", "t_deflated_sweep", "n_tests_sweep",
                                    "oos_net_total", "best_single_oos_net_total")},
    ) for r in proposals]
    report = {"generated_at": datetime.now(tz=UTC).isoformat(),
              "symbols_with_members": len(pool), "tests_run": len(rows),
              "cells_proposed": len(proposals), "skipped": skipped,
              "proposals": proposals, "all": rows,
              "member_source": str(GATES),
              "note": ("members are cells that passed every validity gate and failed only "
                       "power gates; an ensemble is proposed only if it beats its strongest "
                       "member out of sample")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if cands:
        report["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=2400.0)
    a = ap.parse_args()
    rep = run(symbols=a.symbol, budget_s=a.budget_s)
    print(f"WEAK-SIGNAL COMPILER  {rep['symbols_with_members']} symbols with members, "
          f"{rep['tests_run']} combinations, {rep['cells_proposed']} proposed")
    for r in rep["proposals"]:
        print(f"  {r['cell']:26s} members={r['n_members']:2d} n={r['n_independent']:4d} "
              f"net={r['net_per_trade']:+.6f} t={r['t_gross']:+.2f} "
              f"t_defl={r['t_deflated_sweep']:+.2f} beats_best={r['beats_best_member']}")
    for k, v in list(rep["skipped"].items())[:8]:
        print(f"  skipped {k}: {v}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
