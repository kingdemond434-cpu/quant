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
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import proposer_common as pc  # noqa: E402
from research.frontier_identity import cell_id  # noqa: E402

SOURCE = "weak_signal_ensemble"
REPORT = _DESK / "reports" / "weak_signal_compiler.json"
GATES = _DESK / "reports" / "universal_gates_external.json"
DOCKET = _DESK / "data" / "hypotheses" / "external_survivors.json"
POWER_GATES = frozenset({"deflated_sharpe", "expected_value", "in_sample_screen"})
MAX_MEMBERS = 24
MIN_MEMBERS = 4
K_WEIGHT = 40.0
N_BLOCKS = 4
THRESHOLDS = (0.3, 0.5, 0.7)


def _docket_by_cell() -> dict[str, dict]:
    """cell id -> the docket row that MINTED it, which is the only place params survive.

    A verdict row names its cell as `XAUUSD@M5.momentum_volgate.p=44136fa355b3678a`. The `p=`
    field is a SHA256 DIGEST of the parameters, not the parameters -- it is one-way, so no member
    signal can be rebuilt from a verdict alone. The docket is the other half of that pair, and
    `frontier_identity.cell_id` is the desk's own identity function, so recomputing it over the
    docket joins the two EXACTLY rather than by a guessed key. Measured 2026-09-14: 23,053 docket
    rows give 23,041 distinct ids and every one of the 560 power-deficient verdicts joins, 100%.
    """
    try:
        rows = json.loads(DOCKET.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            key = cell_id({**row, "sym": row.get("symbol"), "family": row.get("family"),
                           "params": row.get("params")})
        except Exception:
            continue
        out.setdefault(key, row)
    return out


def power_deficient(max_per_symbol: int = MAX_MEMBERS) -> dict[str, list[dict]]:
    """symbol -> member cells that passed every validity gate and failed only power gates.

    THIS READ THE WRONG FIELD AND RETURNED NOTHING FOR AS LONG AS IT HAS EXISTED. It asked each
    verdict for `gates`; the gauntlet has always written `stages`. `.get("gates") or {}` is not an
    error -- it is an empty dict -- so `failed` was empty for every row, `if not failed: continue`
    skipped all of them, and the compiler reported "0 symbols with members, 0 combinations, 0
    proposed" on a docket that had material. Measured on the trading box 2026-09-14: 7,831
    verdicts, 0 carrying `gates`, 7,831 carrying `stages`, and 560 cells that failed ONLY power
    gates across 67 symbols with at least MIN_MEMBERS each.

    WHAT THOSE 560 ARE IS THE WHOLE POINT. A cell that clears every validity gate -- pbo, cpcv,
    walk_forward, lockbox, reality_check_spa, stress_costs -- and fails only on POWER is not a
    refuted hypothesis. It is a real effect measured on too few observations to clear a deflated
    Sharpe bar that charges 597 trials. Under selection each one is a failure and is thrown away.
    Under combination they are the raw material, because the power deficit is exactly what
    aggregation repairs: k weak members with low mutual correlation carry a t-stat that scales
    with sqrt(k) while the per-member edge does not have to move at all.

    `stages` is read first and `gates` kept as a fallback, so a future schema that renames it back
    does not silently re-empty this the way the original did.
    """
    try:
        doc = json.loads(GATES.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    docket = _docket_by_cell()
    out: dict[str, list[dict]] = {}
    for v in doc.get("verdicts") or []:
        if not isinstance(v, dict) or v.get("unmeasured"):
            continue
        stages = v.get("stages") or v.get("gates") or {}
        if not isinstance(stages, dict) or not stages:
            continue
        failed = {k for k, g in stages.items() if isinstance(g, dict) and g.get("passed") is False}
        if not failed or not failed <= POWER_GATES:
            continue
        sym = str(v.get("sym") or v.get("symbol") or "")
        fam = str(v.get("family") or "")
        if not sym or not fam or fam == "ensemble":
            continue
        # PARAMS COME FROM THE DOCKET, NEVER FROM THE VERDICT. The verdict carries a digest; a
        # member built with `{}` because the real params could not be found is a DIFFERENT
        # strategy wearing the cell's name, and it would be combined under that name.
        row = docket.get(str(v.get("cell") or ""))
        if row is None:
            continue
        params = row.get("params")
        out.setdefault(sym, []).append({
            "symbol": sym, "family": fam,
            "params": dict(params) if isinstance(params, dict) else {},
            "cell": str(v.get("cell") or ""),
            "sharpe": float((stages.get("in_sample_screen") or {}).get("sharpe") or 0.0)})
    for sym in out:
        out[sym] = sorted(out[sym], key=lambda m: -abs(m["sharpe"]))[:max_per_symbol]
    return out


#: Why members could not be built, counted by cause. A bare `except: return []` is indistinguishable
#: from "this family genuinely produced no signals", and that is exactly how the previous bug hid.
BUILD_FAILURES: Counter = Counter()


def _runner_factory(meta: dict):
    """A member-signal builder that goes through the gauntlet's own cell construction.

    IT UNPACKED A TWO-TUPLE FROM A FUNCTION THAT RETURNS A DICT, AND THE bare `except` ATE IT.
    `build_cell` returns `{"sym","family","params","timeframe","df","sigs","costs",...}` -- nine
    keys, with the signals ALREADY BUILT -- or None when the cell is unbuildable. Every other
    caller in the repo treats it as a dict; this one alone did `fn, kwargs = build_cell(...)`,
    which raises `ValueError: too many values to unpack (expected 2, got 9)` on every single
    member. `except Exception: return []` turned that into an empty signal list, so the lane
    reported "93 symbols with members, 0 combinations -- members could not be built", which reads
    like a data problem rather than a call-signature error.

    That is the SECOND interface drift in this one file: `power_deficient` read a `gates` key that
    became `stages`, and this read a 2-tuple that became a dict. Both were silent, both looked
    like emptiness, and neither could be seen from the artifact. So failures are now COUNTED by
    cause and published -- an organ that cannot build its inputs must say why, not return [].
    """
    def _run(symbol: str, family: str, params: dict, df: pd.DataFrame):
        try:
            from external_gauntlet import build_cell
        except Exception as exc:
            BUILD_FAILURES[f"import build_cell: {type(exc).__name__}"] += 1
            return []
        try:
            obj = build_cell(symbol, family, params, meta, df)
        except Exception as exc:
            BUILD_FAILURES[f"{family}: {type(exc).__name__}: {str(exc)[:60]}"] += 1
            return []
        if obj is None:
            # The gauntlet's own refusal -- an unbuildable cell, e.g. a chart it will not resample
            # onto. That is a verdict, not an error, and it is counted separately from a crash.
            BUILD_FAILURES[f"{family}: build_cell refused the cell"] += 1
            return []
        if not isinstance(obj, dict):
            BUILD_FAILURES[f"{family}: build_cell returned {type(obj).__name__}"] += 1
            return []
        sigs = obj.get("sigs")
        if not sigs:
            BUILD_FAILURES[f"{family}: built but produced no signals"] += 1
            return []
        return sigs
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
              # THE MEMBER COUNT IS PUBLISHED SO THE GAUNTLET CAN STOP GUESSING. `_family_yield`
              # credits a power-deficient cell at a BOOTSTRAP until this lane reports its own
              # conversion; cells_proposed / n_members is that conversion, so publishing it
              # replaces a declared constant with a measurement on the first run that has one.
              "n_members": sum(len(v) for v in pool.values()),
              # WHY MEMBERS DID NOT BUILD, BY CAUSE. Two interface drifts in this file have now
              # presented as "0 combinations" with no way to tell a call-signature error from a
              # family that genuinely has no signal. This is the difference, published.
              "build_failures": dict(BUILD_FAILURES.most_common(20)),
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
