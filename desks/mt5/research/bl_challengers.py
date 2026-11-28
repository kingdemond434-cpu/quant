"""Black-Litterman / MVO challengers and the allocation perturbation test, measured hourly.

    python research/bl_challengers.py [--budget-s 600] [--max-windows 52]

Mandate 2026-10-06 D15 (audit repair #7), BACKLOG W0: "Black-Litterman / MVO challengers +
perturbation test". Jev was dropped on 2026-11-11 ("replicated without it"); view D reads the
desk's own world-state probabilities (`pf_allocator.regime_state`, `SleeveEvidence.macro_w`).
The arithmetic lives in `libs/portfolio/black_litterman.py` and `libs/portfolio/perturbation.py`.

THREE MEASUREMENTS, ONE ARTIFACT (`reports/BL_CHALLENGERS.json`):

  1. NOW. The seven D15 books (A existing allocator, B + BL equilibrium prior, C + confidence-
     weighted certified views, D + world-state views, E BL only, F MVO, G shuffled-view control)
     built at the incumbent book's total heat on today's evidence and scored on ONE world
     population (`robust_elog.score_book`): robust score, mean and CVaR log growth.
  2. FORWARD. A walk-forward over the desk's daily matrix, exactly the design of
     `research/input_ablation.py`: at each rebalance day the evidence is rebuilt from history up
     to that day, every arm builds its book, and the book is held over the next `HORIZON` days of
     REALISED returns. Per arm: realised log growth, Sharpe, max drawdown, tail (CVaR), turnover
     and its cost, concentration (HHI), weight stability (mean L1 move window to window), and a
     paired verdict against A (`input_ablation.paired_verdict`). G is the control: a D that does
     not beat G has no information in its views.
  3. PERTURBATION. Every class in `perturbation.CLASSES` against A, D, E and F on today's
     evidence; the allocator's excess instability and the SHADOW authority flag.

AUTHORITY: NONE. Challenger, never primary (D15). Nothing here changes a book, a heat or the proof
in `allocator_proof.contest`; the report is evidence for whoever later wires a promotion, and the
allocator stays sovereign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import black_litterman as bl  # noqa: E402
from libs.portfolio import perturbation as pt  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    WorldConfig,
    optimise,
    sample_worlds,
    score_book,
)

OUT = BASE / "reports" / "BL_CHALLENGERS.json"
CACHE = BASE / "data" / "pf_allocator_cache" / "bl_challengers_cache.json"
ALLOC = BASE / "reports" / "pf_allocation.json"

#: The walk-forward shares input_ablation's clock so the two reports read on the same windows.
HORIZON = 5
STEP = HORIZON
WARMUP = 250
MAX_WINDOWS = 52
BUDGET_S = 600.0
N_WORLDS = 128
N_ROWS = 256
#: Bump when an arm's definition or a metric changes; cached windows from another version are
#: re-solved, never reused.
VERSION = 1
#: The perturbation is re-measured at most this often. DERIVATION: it reads today's evidence only,
#: which changes with the daily matrix; once a day keeps it current at a seventh of the cost.
PERTURB_EVERY_S = 24 * 3600
#: Books the perturbation test runs: the sovereign allocator, the world-state BL arm, the textbook
#: BL book and the MVO baseline -- the three D15 asks and the book they challenge.
PERTURB_BOOKS = ("A_allocator", "D_bl_world_state_views", "E_bl_only", "F_mvo")


def _heat_target() -> float:
    from research.heat_policy import HEAT_TARGET
    return float(HEAT_TARGET)


def incumbent() -> tuple[dict[str, float], float]:
    """The published book and its total heat; the 20% floor when none is readable."""
    try:
        doc = json.loads(ALLOC.read_text("utf-8"))
        book = {str(k): float(v) for k, v in (doc.get("book") or {}).items() if float(v) > 0}
        tot = float((doc.get("heat") or {}).get("total") or sum(book.values()))
        if book and tot > 0:
            return book, tot
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {}, _heat_target()


def _solver(total: float, bounds: Mapping[str, float] | None, seed: int):
    def solve(ev_t: Sequence[Any], probs: Sequence[tuple[str, float]] = (),
              labels: Sequence[str] = (), seed_: int | None = None,
              bounds_: Mapping[str, float] | None = None) -> dict[str, float]:
        cfg = WorldConfig(seed=seed if seed_ is None else seed_, n_worlds=N_WORLDS,
                          n_rows=N_ROWS, regime_labels=tuple(labels), regime_probs=tuple(probs))
        b = bounds_ if bounds_ is not None else bounds
        return optimise(list(ev_t), hard_cap=total, target=total, cfg=cfg,
                        max_per_sleeve=dict(b) if b else None).heat
    return solve


def _bounds(daily: pd.DataFrame, total: float) -> dict[str, float]:
    from research import pf_allocator as pa
    from research.heat_policy import per_sleeve_bounds
    return per_sleeve_bounds(pa.worst_dd_r(daily), total)


def _regime(daily: pd.DataFrame, asof: str | None = None
            ) -> tuple[tuple[str, ...], tuple[tuple[str, float], ...]]:
    try:
        from research import pf_allocator as pa
        labels, probs, _ = pa.regime_state(daily, asof=asof)
        return tuple(labels), tuple(probs)
    except Exception:
        return (), ()


def now_books(ev: Sequence[Any], daily: pd.DataFrame, held: Mapping[str, float],
              total: float, *, seed: int = 0) -> dict[str, Any]:
    labels, probs = _regime(daily)
    bounds = _bounds(daily, total)
    solve = _solver(total, bounds, seed)
    books, b = bl.arm_books(ev, total, lambda e: solve(e, probs, labels), w_ref=held,
                            regime_labels=labels, regime_probs=dict(probs))
    cfg = WorldConfig(seed=seed, n_worlds=N_WORLDS, n_rows=N_ROWS,
                      regime_labels=labels, regime_probs=probs)
    worlds = sample_worlds(list(ev), cfg)
    scored = {}
    for arm, book in books.items():
        s = score_book(list(ev), book, cfg=cfg, worlds=worlds)
        scored[arm] = {k: (round(v, 8) if isinstance(v, float) and math.isfinite(v) else v)
                       for k, v in s.items()}
        scored[arm]["n_funded"] = int(sum(1 for v in book.values() if v > 1e-9))
        scored[arm]["top"] = dict(sorted(((k, round(v, 6)) for k, v in book.items()),
                                         key=lambda kv: -kv[1])[:8])
    return {"total_heat": round(total, 6), "regime_probs": dict(probs),
            "beliefs": {"tau": b.tau, "delta": round(b.delta, 6), "n_views": b.n_views,
                        "prior_source": "incumbent book" if held else "equal heat"},
            "arms": scored, "books": books}


def walk_forward(daily: pd.DataFrame, trials: Mapping[str, int], total: float, *,
                 max_windows: int | None, deadline: float | None, cache: dict[str, Any],
                 persist, seed: int = 0) -> dict[str, Any]:
    from research import input_ablation as ia
    build = ia._evidence_asof(trials)
    idx = [str(d)[:10] for d in daily.index]
    ends = list(range(WARMUP, len(idx) - HORIZON + 1, STEP))
    if max_windows is not None:
        ends = ends[-max_windows:]
    rows: list[dict[str, Any]] = []
    pending = hits = 0
    prev: dict[str, dict[str, float]] = {}
    for k in ends:
        asof = idx[k - 1]
        hist = daily.iloc[:k]
        key = hashlib.sha256(json.dumps(
            [VERSION, asof, [str(c) for c in hist.columns], seed, total,
             hashlib.sha256(np.ascontiguousarray(hist.to_numpy(dtype=float)).tobytes()
                            ).hexdigest(), ia.trials_read(trials)],
            default=str).encode()).hexdigest()
        books = cache.get(key)
        if isinstance(books, dict) and books:
            hits += 1
        elif deadline is not None and time.time() > deadline:
            pending += 1
            continue
        else:
            ev = build(hist)
            labels, probs = _regime(hist, asof=asof)
            solve = _solver(total, _bounds(hist, total), seed)
            ref = prev.get("A_allocator") or {}
            books, _b = bl.arm_books(ev, total,
                                     lambda e, p=probs, lb=labels, sv=solve: sv(e, p, lb),
                                     w_ref=ref, regime_labels=labels, regime_probs=dict(probs))
            cache[key] = books
            persist()
        fwd = daily.iloc[k:k + HORIZON]
        names = [str(c) for c in fwd.columns]
        mets = {a: bl.book_metrics(b, fwd.to_numpy(dtype=float), names, prev=prev.get(a))
                for a, b in books.items()}
        rows.append({"asof": asof, "metrics": mets})
        prev = {a: dict(b) for a, b in books.items()}
    return {"rows": rows, "pending_windows": pending, "cache_hits": hits}


def summarise(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    from research import input_ablation as ia
    arms = sorted({a for r in rows for a in r["metrics"]})
    out: dict[str, Any] = {}
    inputs = [a for a in arms if a != "A_allocator"]
    for a in arms:
        ms = [r["metrics"][a] for r in rows if a in r["metrics"]]
        lg = [m["log_growth"] for m in ms]
        fin = [x for x in lg if math.isfinite(x)]
        turn = [m["turnover"] for m in ms if math.isfinite(m["turnover"])]
        d = {"n_windows": len(ms), "ruined_windows": len(lg) - len(fin),
             "total_log_growth": round(float(sum(fin)), 8) if fin else None,
             "mean_window_log_growth": round(float(np.mean(fin)), 8) if fin else None,
             "sharpe_window": (round(float(np.mean(fin) / np.std(fin, ddof=1)), 4)
                               if len(fin) > 2 and np.std(fin, ddof=1) > 0 else None),
             "worst_window_drawdown_log": round(max((m["max_drawdown_log"] for m in ms),
                                                    default=0.0), 8),
             "mean_cvar_daily": round(float(np.mean([m["cvar_daily"] for m in ms])), 8)
             if ms else None,
             "weight_stability_mean_turnover": round(float(np.mean(turn)), 6) if turn else None,
             "mean_hhi": round(float(np.mean([m["hhi"] for m in ms])), 6) if ms else None}
        if a in inputs:
            pairs = [(r["metrics"][a]["log_growth"] if a in r["metrics"] else None,
                      r["metrics"]["A_allocator"]["log_growth"]
                      if "A_allocator" in r["metrics"] else None) for r in rows]
            d["vs_allocator"] = ia.paired_verdict(pairs, n_inputs=len(inputs))
        out[a] = d
    if "D_bl_world_state_views" in out and "G_shuffled_views" in out:
        pairs = [(r["metrics"].get("D_bl_world_state_views", {}).get("log_growth"),
                  r["metrics"].get("G_shuffled_views", {}).get("log_growth")) for r in rows]
        out["D_bl_world_state_views"]["vs_shuffled_control"] = ia.paired_verdict(pairs)
    return out


def perturbation(ev: Sequence[Any], daily: pd.DataFrame, held: Mapping[str, float],
                 total: float, *, seed: int = 0) -> dict[str, Any]:
    labels, probs = _regime(daily)
    bounds = _bounds(daily, total)
    solve = _solver(total, bounds, seed)
    n_obs = int(daily.shape[0])

    def arm(name: str):
        def f(ev_p: Sequence[Any], ctx: Mapping[str, Any]) -> Mapping[str, float]:
            p, s, bd = ctx.get("regime_probs") or probs, int(ctx.get("seed", seed)), \
                ctx.get("bounds") or bounds
            books, _ = bl.arm_books(
                ev_p, total, lambda e: solve(e, p, labels, s, bd), w_ref=held,
                regime_labels=labels, regime_probs=dict(p))
            if name not in books:
                raise ValueError(f"{name} not buildable on this evidence")
            return books[name]
        return f
    return pt.measure(list(ev), {n: arm(n) for n in PERTURB_BOOKS}, seed=seed,
                      regime_probs=probs, regime_n_obs=n_obs, bounds=bounds)


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def run(max_windows: int | None = MAX_WINDOWS, budget_s: float | None = BUDGET_S
        ) -> dict[str, Any]:
    from research import input_ablation as ia
    from research import pf_allocator as pa
    t0 = time.time()
    deadline = (t0 + budget_s) if budget_s else None
    daily, _fwd = pa.build_evidence(force=False)
    daily = daily.sort_index()
    trials = pa.search_trials()
    held, total = incumbent()
    ev = ia._evidence_asof(trials)(daily)
    prev_doc = _read(OUT)
    doc: dict[str, Any] = {"generated_utc": datetime.now(UTC).isoformat(), "version": VERSION,
                           "authority": "none: challenger, never primary (mandate D15)",
                           "jev": "dropped 2026-11-11; view D = own regime posterior + macro "
                                  "kernel", "arms": list(bl.ARMS), "n_sleeves": len(ev)}
    try:
        now = now_books(ev, daily, held, total)
        now.pop("books", None)
        doc["now"] = now
    except Exception as exc:
        doc["now"] = {"error": f"{type(exc).__name__}: {exc}"}
    cache_doc = _read(CACHE)
    cache = dict(cache_doc.get("windows") or {}) if cache_doc.get("version") == VERSION else {}

    def persist() -> None:
        ia._write_json(CACHE, {"version": VERSION, "windows": cache})

    wf = walk_forward(daily, trials, total, max_windows=max_windows, deadline=deadline,
                      cache=cache, persist=persist)
    persist()
    doc["forward"] = {"horizon_days": HORIZON, "n_windows": len(wf["rows"]),
                      "pending_windows": wf["pending_windows"], "cache_hits": wf["cache_hits"],
                      "arms": summarise(wf["rows"])}
    last = prev_doc.get("perturbation") or {}
    age = time.time() - float(last.get("measured_epoch") or 0.0)
    if age >= PERTURB_EVERY_S and (deadline is None or time.time() < deadline):
        try:
            p = perturbation(ev, daily, held, total)
            p["measured_epoch"] = time.time()
            doc["perturbation"] = p
        except Exception as exc:
            doc["perturbation"] = {"error": f"{type(exc).__name__}: {exc}",
                                   "measured_epoch": last.get("measured_epoch")}
    else:
        doc["perturbation"] = last or {"status": "PENDING", "why": "budget spent this pass"}
    doc["status"] = ("UNMEASURED" if not wf["rows"]
                     else "PARTIAL" if wf["pending_windows"] else "MEASURED")
    doc["elapsed_s"] = round(time.time() - t0, 1)
    ia._write_json(OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-windows", type=int, default=MAX_WINDOWS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    doc = run(a.max_windows, a.budget_s)
    print(f"bl challengers {doc['status']}: {doc['forward']['n_windows']} window(s), "
          f"{doc['forward']['pending_windows']} pending")
    for arm, v in doc["forward"]["arms"].items():
        vs = (v.get("vs_allocator") or {}).get("verdict", "-")
        print(f"{arm}: total log growth {v.get('total_log_growth')} vs A: {vs}")
    auth = (doc.get("perturbation") or {}).get("authority") or {}
    print(f"perturbation: allocator would lose authority (shadow) = "
          f"{auth.get('would_lose_authority')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
