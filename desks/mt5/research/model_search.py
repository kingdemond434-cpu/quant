"""MODEL-FAMILY SEARCH as its own civilization, and the R x M compatibility search.

Tier-1 items 6 and 7. The desk has spent years breeding FACTORS and has run, for most of that
time, exactly one learner behind them. That is a search over half the space: a representation
that is dead under ridge can be alive under a boosted stump, and a family that adds nothing on
raw returns can earn its tax once the same information is ranked instead of z-scored.

WHAT RUNS HERE
  1. TEN FAMILIES, each with a factor's discipline -- lineage (`parent`), a novelty key so the
     same family is never re-tested under a new name, a declared falsifier (its tax), and a
     verdict that is allowed to be UNMEASURED. `libs/research/model_families.py` owns them.
  2. SIX REPRESENTATIONS of the SAME underlying information -- raw, z-scored, ranked,
     volatility-scaled, range/state, and path-shape. Same bars, same target, different
     coordinates, so a difference in verdict is a statement about the coordinates and nothing
     else.
  3. THE WHOLE GRID. Every (R_k, M_j) is scored on the same folds and published as a matrix. A
     representation is declared DEAD only when EVERY learner tried on it failed; with fewer than
     two learners its verdict is UNMEASURED, which is why nothing here can be buried by one
     unlucky fit.
  4. NO HEAVY LIBRARY IS REQUIRED. Every family has a pure-Python fallback; an absent sklearn /
     torch / statsmodels reads `heavy_verdict: UNMEASURED` on that family's row and the fallback
     carries the run. `--no-heavy` forces that path so the fallback is exercised on purpose.

WHAT LEAVES. A (representation, family) cell whose net gain clears the family's declared tax is
a CANDIDATE CONDITIONING MODEL -- it has no entry, no stop and no size, so it is enqueued as
`conditioning_model` in the ONE registry with its provenance and its effective trials, for the
deepening worker to write a family recipe around. Every failure emits the descendant its failure
KIND implies, into the seven queues, so a dead cell still changes the next experiment.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import coevolution_lab as CL  # noqa: E402
from libs.research import model_families as MF  # noqa: E402
from libs.research import trial_ledger as TL  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "model_search"
REPORT = _DESK / "reports" / "MODEL_SEARCH.json"
TRIALS = _DESK / "data" / "model_search_trials.jsonl"
BUDGET_S = 600.0
N_BARS = 6000
MIN_BARS = 1500
MAX_SYMBOLS = 4
HORIZON = 6
#: Representations reported per instrument; the grid is published whole regardless.
TOP = 3
UNMEASURED = CL.UNMEASURED

#: The six coordinate systems, each a function of the SAME bars and the SAME target. The point
#: of holding them fixed is that a verdict difference across a row of the matrix is a statement
#: about the coordinates, never about a different dataset.
REPRESENTATIONS: tuple[str, ...] = ("raw", "zscore", "rank", "vol_scaled", "range_state",
                                    "path_shape")


def _roll_z(s: pd.Series, w: int) -> pd.Series:
    m, sd = s.rolling(w, min_periods=w // 2).mean(), s.rolling(w, min_periods=w // 2).std()
    return (s - m) / sd.replace(0.0, np.nan)


def _roll_rank(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w, min_periods=w // 2).apply(
        lambda a: float((a[-1] > a[:-1]).mean()) if a.size > 1 else 0.5, raw=True)


def representation(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """One coordinate system over the same bars. Columns are named so the matrix is readable."""
    c = df["close"].astype(float)
    ret = np.log(c).diff()
    rng = (df["high"].astype(float) - df["low"].astype(float)) / c.replace(0.0, np.nan)
    if kind == "raw":
        out = {"r1": ret, "r6": np.log(c).diff(6), "r24": np.log(c).diff(24),
               "range": rng}
    elif kind == "zscore":
        out = {"z_r6": _roll_z(np.log(c).diff(6), 240), "z_r24": _roll_z(np.log(c).diff(24), 240),
               "z_range": _roll_z(rng, 120), "z_vol": _roll_z(ret.rolling(24).std(), 240)}
    elif kind == "rank":
        out = {"q_r6": _roll_rank(np.log(c).diff(6), 240),
               "q_r24": _roll_rank(np.log(c).diff(24), 240),
               "q_range": _roll_rank(rng, 240), "q_vol": _roll_rank(ret.rolling(24).std(), 240)}
    elif kind == "vol_scaled":
        vol = ret.rolling(24, min_periods=12).std().replace(0.0, np.nan)
        out = {"v_r1": ret / vol, "v_r6": np.log(c).diff(6) / (vol * np.sqrt(6.0)),
               "v_r24": np.log(c).diff(24) / (vol * np.sqrt(24.0)),
               "v_range": rng / vol}
    elif kind == "range_state":
        hi = df["high"].astype(float).rolling(48, min_periods=24).max()
        lo = df["low"].astype(float).rolling(48, min_periods=24).min()
        pos = (c - lo) / (hi - lo).replace(0.0, np.nan)
        spread = (df["spread"].astype(float) if "spread" in df.columns
                  else pd.Series(np.nan, index=df.index))
        out = {"pos48": pos, "rng_ratio": rng / rng.rolling(120, min_periods=60).mean(),
               "spread_z": _roll_z(spread, 240),
               "hour": pd.Series(df.index.hour.astype(float), index=df.index)}
    elif kind == "path_shape":
        sign = np.sign(ret).fillna(0.0)
        out = {"run": sign.rolling(6, min_periods=3).sum(),
               "accel": np.log(c).diff(6) - 2.0 * np.log(c).diff(3),
               "ac1": ret.rolling(48, min_periods=24).apply(
                   lambda a: float(np.corrcoef(a[:-1], a[1:])[0, 1])
                   if a.size > 2 and np.std(a[:-1]) > 0 and np.std(a[1:]) > 0 else 0.0,
                   raw=True),
               "dd": (c / c.rolling(120, min_periods=60).max() - 1.0)}
    else:
        raise ValueError(f"unknown representation {kind!r}; known: {REPRESENTATIONS}")
    return pd.DataFrame(out, index=df.index)


def _target(df: pd.DataFrame, horizon: int) -> np.ndarray:
    c = df["close"].to_numpy(dtype=float)
    fwd = np.full(c.size, np.nan)
    with np.errstate(all="ignore"):
        fwd[:-horizon] = np.log(c[horizon:] / c[:-horizon])
    return fwd


def design(df: pd.DataFrame, kind: str, horizon: int = HORIZON
           ) -> tuple[list[list[float]], list[float], list[str]] | None:
    """(rows, labels, column names) on non-overlapping targets, or None when unusable."""
    rep = representation(df, kind)
    y_raw = _target(df, horizon)
    mat = rep.to_numpy(dtype=float)
    ok = np.isfinite(mat).all(axis=1) & np.isfinite(y_raw)
    rows = np.where(ok)[0][::horizon]
    if rows.size < MF.MIN_ROWS:
        return None
    x = mat[rows]
    keep = [j for j in range(x.shape[1]) if float(np.std(x[:, j])) > 0]
    if len(keep) < 2:
        return None
    return ([[float(v) for v in r] for r in x[:, keep]],
            [1.0 if v > 0 else 0.0 for v in y_raw[rows]],
            [str(rep.columns[j]) for j in keep])


def _symbols(explicit: list[str] | None) -> tuple[list[str], dict[str, Any]]:
    have = sorted(p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet"))
    if explicit:
        return sorted({s for s in explicit if s in have}), {"source": "explicit"}
    core = [s for s in ("XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "US500", "XAGUSD") if s in have]
    pool = core or have
    if len(pool) > MAX_SYMBOLS:
        off = datetime.now(tz=UTC).timetuple().tm_yday % len(pool)
        rot = pool[off:] + pool[:off]
        return rot[:MAX_SYMBOLS], {"source": "core_rotation", "deferred": rot[MAX_SYMBOLS:]}
    return pool, {"source": "core" if core else "all_available"}


def family_census() -> dict[str, Any]:
    """The civilization's own register: lineage, novelty key, falsifier, backend verdict."""
    avail = MF.availability()
    return {name: {"tax": fam.tax, "parent": fam.parent or None,
                   "novelty_key": fam.novelty_key, "assumption": fam.assumption,
                   "mutations": list(fam.mutations),
                   "falsifier": (f"out-of-sample log-score gain must exceed the declared tax of "
                                 f"{fam.tax} nats/prediction on the same folds as its parent"),
                   **{k: avail[name][k] for k in ("backend", "heavy_verdict",
                                                  "backends_declared", "backends_present")}}
            for name, fam in MF.FAMILIES.items()}


def _enqueue(cell: dict[str, Any], sym: str, n_eff: float) -> dict[str, Any]:
    try:
        from libs.moat import registry as R
    except Exception as exc:
        return {"enqueued": False, "why": f"registry unavailable: {type(exc).__name__}: {exc}"}
    fam = MF.FAMILIES[str(cell["model"])]
    params = {"representation": cell["representation"], "columns": cell.get("columns"),
              "model_family": cell["model"], "horizon": HORIZON,
              "net_gain": cell.get("net_gain"), "backend": cell.get("backend")}
    mech = (f"{cell['model']} on the {cell['representation']} representation of {sym}: net "
            f"{float(cell.get('net_gain') or 0):+.6f} nats/prediction after the family's "
            f"declared tax of {fam.tax}")
    try:
        conn = R.connect()
        try:
            did, _ = R.record_discovery(
                source_id=f"representation:{cell['representation']}",
                source_type="representation_model_cell", mechanism=mech, origin=SOURCE,
                generator=SOURCE, assets=[sym], horizons=[HORIZON],
                exact_rule=json.dumps({"family": "conditioning_model", "params": params},
                                      sort_keys=True, default=str),
                economic_rationale=fam.assumption,
                falsifier=(f"net gain <= {fam.tax} on the next walk-forward, or another family "
                           "matching it on the same representation at a lower tax"),
                confidence=min(1.0, max(0.0, float(cell.get("net_gain") or 0.0) * 200.0)),
                payload={"cell": cell, "effective_trials": n_eff,
                         "lineage": {"parent_family": fam.parent,
                                     "novelty_key": fam.novelty_key}}, conn=conn)
            R.set_discovery_state(did, "QUEUED", possible_cells=1, generated_cells=1,
                                  compiled_cells=1, queued_cells=1, conn=conn)
            cid, created = R.enqueue_candidate(
                family="conditioning_model", symbol=sym, params=params, origin=SOURCE,
                mechanism=mech, generator=SOURCE, department="validate", discovery_id=did,
                trial_family=f"model_search:{cell['model']}", horizon=str(HORIZON),
                model_family=str(cell["model"]), effective_trials=n_eff,
                falsifier=f"net gain <= the declared tax {fam.tax} out of sample",
                exact_rules=json.dumps({"family": "conditioning_model", "params": params},
                                       default=str),
                lineage_json=json.dumps({"parent_family": fam.parent,
                                         "novelty_key": fam.novelty_key,
                                         "representation": cell["representation"],
                                         "source": SOURCE}, default=str), conn=conn)
            return {"enqueued": True, "candidate_id": cid, "created": created,
                    "discovery_id": did}
        finally:
            conn.close()
    except Exception as exc:
        return {"enqueued": False, "why": f"{type(exc).__name__}: {exc}"}


def _append_trials(rows: list[dict[str, Any]]) -> str:
    try:
        TRIALS.parent.mkdir(parents=True, exist_ok=True)
        with TRIALS.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
        return ""
    except OSError as exc:
        return f"trial ledger not written: {type(exc).__name__}: {exc}"


def run(symbols: list[str] | None = None, budget_s: float = BUDGET_S,
        families: tuple[str, ...] | None = None, reps: tuple[str, ...] = REPRESENTATIONS,
        allow_heavy: bool = True, write_queue: bool = True, enqueue: bool = True,
        n_bars: int = N_BARS, report: Path | None = None) -> dict[str, Any]:
    out_path = report or REPORT
    deadline = time.monotonic() + budget_s
    todo, chosen = _symbols(symbols)
    fams = tuple(families) if families else MF.ORDER
    cells: list[dict[str, Any]] = []
    per_symbol: dict[str, Any] = {}
    queues = CL.QueueSet()
    trials: list[TL.Trial] = []
    trial_rows: list[dict[str, Any]] = []
    for sym in todo:
        if time.monotonic() > deadline:
            per_symbol[sym] = {"verdict": UNMEASURED, "why": "search budget exhausted"}
            continue
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            per_symbol[sym] = {"verdict": UNMEASURED, "why": f"under {MIN_BARS} H1 bars"}
            continue
        d = d.tail(n_bars)
        sym_cells: list[dict[str, Any]] = []
        for rep in reps:
            if time.monotonic() > deadline:
                break
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    des = design(d, rep)
                except Exception as exc:
                    per_symbol.setdefault(sym, {}).setdefault("representation_errors", {})[
                        rep] = f"{type(exc).__name__}: {exc}"
                    continue
            if des is None:
                sym_cells.append({"symbol": sym, "representation": rep, "model": None,
                                  "verdict": UNMEASURED,
                                  "why": "too few finite non-overlapping rows in this "
                                         "representation"})
                continue
            x, y, cols = des
            for fam in fams:
                if time.monotonic() > deadline:
                    break
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        r = MF.walk_forward(fam, x, y, allow_heavy=allow_heavy)
                    except Exception as exc:
                        r = {"family": fam, "verdict": "FAILED", "net_gain": None,
                             "why": f"{type(exc).__name__}: {exc}"}
                cell = {"symbol": sym, "representation": rep, "model": fam, "columns": cols,
                        **{k: r.get(k) for k in ("n", "folds", "gain", "net_gain", "tax",
                                                 "brier", "verdict", "backend",
                                                 "heavy_verdict", "why")}}
                sym_cells.append(cell)
                trials.append(TL.Trial(
                    trial_id=f"{sym}:{rep}:{fam}", family=f"model_search:{fam}",
                    descriptors={"symbol": sym, "representation": rep, "model_family": fam,
                                 "horizon": str(HORIZON)},
                    params={"n_columns": len(cols)}, declared_width=1))
        scored = [c for c in sym_cells if c.get("net_gain") is not None]
        scored.sort(key=lambda c: -float(c["net_gain"]))
        per_symbol[sym] = {**per_symbol.get(sym, {}), "verdict": "MEASURED" if scored
                           else UNMEASURED, "cells": len(sym_cells),
                           "best": scored[:TOP],
                           "n_earning": sum(1 for c in scored
                                            if c.get("verdict") == MF.POSITIVE)}
        trial_rows.append({"generated_utc": datetime.now(tz=UTC).isoformat(), "symbol": sym,
                           "cells": len(sym_cells), "source": SOURCE,
                           "n_earning": per_symbol[sym]["n_earning"]})
        cells.extend(sym_cells)
        # Every failure emits its descendant (item 10) -- a dead cell still changes the next run.
        for c in sym_cells:
            if c.get("verdict") not in (MF.POSITIVE,):
                queues.extend(CL.descendants_for(c, symbol=sym,
                                                 parent=f"{c['representation']}:{c['model']}"))

    matrix = CL.compatibility_matrix([c for c in cells if c.get("model")])
    reps_verdict = CL.dead_representations(matrix)
    census = TL.census(trials)
    winners = [c for c in cells if c.get("verdict") == MF.POSITIVE]
    winners.sort(key=lambda c: -float(c.get("net_gain") or 0.0))
    registry_rows = []
    if enqueue:
        for c in winners[:TOP * 2]:
            registry_rows.append({"symbol": c["symbol"], "representation": c["representation"],
                                  "model": c["model"], "net_gain": c.get("net_gain"),
                                  **_enqueue(c, str(c["symbol"]), census.n_effective)})
    ledger_err = _append_trials(trial_rows) if trial_rows else ""
    free_slots = max(0, int(deadline - time.monotonic()) // 60)
    doc = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "symbols": {**chosen, "n": len(todo), "swept": todo},
        "representations": list(reps), "families": list(fams),
        "allow_heavy": allow_heavy, "budget_s": budget_s, "horizon": HORIZON,
        "cells_tested": len([c for c in cells if c.get("model")]),
        "n_earning": len(winners),
        "family_census": family_census(),
        "n_families_unmeasured_heavy": sum(
            1 for v in MF.availability().values() if v["heavy_verdict"] == UNMEASURED),
        "compatibility_matrix": matrix, "representation_verdicts": reps_verdict,
        "per_symbol": per_symbol,
        "winners": [{k: c.get(k) for k in ("symbol", "representation", "model", "net_gain",
                                           "gain", "tax", "n", "backend")}
                    for c in winners[:TOP * 2]],
        "registry": registry_rows,
        "queues": {"depth": queues.depth(),
                   "idle": queues.idle_defect(free_slots=free_slots, value_floor=1.5),
                   "top": {k: [r.to_dict() for r in queues.top(k, 3)] for k in CL.QUEUE_KINDS}},
        "trials": {**census.to_dict(), "charged_by": "libs/research/trial_ledger.py",
                   "jsonl": str(TRIALS), "error": ledger_err},
        "rule": ("every (representation, family) cell is a trial charged through the ledger; a "
                 "representation is DEAD only when every learner tried on it failed, and an "
                 "absent heavy backend is UNMEASURED with the pure-Python fallback carrying "
                 "the run"),
    }
    if write_queue and queues.all_requests():
        doc["queue_merged"] = _merge(queues)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        from libs.ops import events
        events.emit("model_search", leg="model_search", cells=doc["cells_tested"],
                    earning=doc["n_earning"],
                    unmeasured_heavy=doc["n_families_unmeasured_heavy"])
    except Exception:
        pass
    return doc


def _merge(queues: CL.QueueSet) -> Any:
    tasks: list[dict[str, Any]] = [{"source": SOURCE, "kind": f"{r.kind}_request", "title": r.title,
              "description": r.why, "symbols": [], "family": None,
              "params": {**r.payload, "queue": r.kind, "priority": r.priority,
                         "request_id": r.request_id},
              "status": None, "consumer": f"deepening_worker ({r.kind} queue)"}
             for r in queues.all_requests()]
    try:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source=SOURCE)
        return len(tasks)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--once", action="store_true",
                    help="one pass and exit (the scheduler's contract; this organ never loops)")
    ap.add_argument("--no-heavy", action="store_true",
                    help="refuse every heavy backend; the pure-Python fallbacks carry the run")
    ap.add_argument("--no-queue", action="store_true")
    ap.add_argument("--no-enqueue", action="store_true")
    a = ap.parse_args()
    doc = run(symbols=a.symbol, budget_s=a.budget_s, allow_heavy=not a.no_heavy,
              write_queue=not a.no_queue, enqueue=not a.no_enqueue)
    print(f"MODEL_SEARCH  {doc['symbols']['n']} symbols, {doc['cells_tested']} (R x M) cells, "
          f"{doc['n_earning']} earning, {doc['n_families_unmeasured_heavy']}/"
          f"{len(doc['families'])} families with an UNMEASURED heavy backend")
    for rep, v in (doc["representation_verdicts"] or {}).items():
        print(f"  {rep:12s} {v['verdict']:10s} learners={v['learners_tried']} "
              f"best={v.get('best_net_gain')} {v.get('best_model') or v.get('why', '')}")
    for w in doc["winners"][:5]:
        print(f"  WIN {w['symbol']:8s} {w['representation']:12s} {w['model']:18s} "
              f"net={w['net_gain']:+.6f}")
    print(f"  queues {doc['queues']['depth']} idle={doc['queues']['idle']['verdict']}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
