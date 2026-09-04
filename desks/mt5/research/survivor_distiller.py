"""The survivor prior: what the desk's certificates have in common, and the neighbours they imply.

    prior[family][param]   = (median, IQR) among CERTIFIED  vs  among FAILED/BURIED,
                             separation = |median_c - median_f| / pooled IQR
    motifs[family]         = the categorical values and hold/session clusters survivors share
    neighbours(cert)       = K untested cells one grid step from the certificate, stepped
                             TOWARD the survivor median, never into a region the graph holds

WHY A PRIOR AND NOT A SWEEP. Sixty-six certificates and thirty thousand failures are not a
sample of the same distribution: the survivors sit where the failures thin out, and the
parameter directions along which they separate -- a horizon of one bar rather than twelve, a
band at the top decile rather than the bottom -- are the desk's own measured knowledge of where
edges live on these instruments. A proposer that re-sweeps the whole grid spends the
multiplicity charge learning that again; one that steps from a survivor toward the survivor
median spends three trials per certificate on the cells most likely to be a second survivor.
Everything stepped is still a trial: every mutation screened is deflated with the rest, the
proposal bar is the shared one, and the gauntlet's ten gates are untouched.

THE OPERATORS ARE NAMED so `mutation_yield` can bill them: `step_<param>_up`,
`step_<param>_down`, `swap_<param>`. Its weights file, when present, biases WHICH parameter
this module perturbs first; it never changes what a screen or a gate requires.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import proposer_common as pc  # noqa: E402

SOURCE = "survivor_distiller"
REPORT = _DESK / "reports" / "SURVIVOR_DISTILLER.json"
CANON = _DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
GRAPH = _DESK / "data" / "hypothesis_graph.jsonl"
WEIGHTS = _DESK / "data" / "mutation_operator_weights.json"
K_NEIGHBOURS = 3
MAX_TASKS = 25
MIN_BARS = 3000
#: Parameters that NAME the cell (its instrument, its peers, its data source) or are execution
#: plumbing. Perturbing one produces a different hypothesis, not a neighbour of this one.
FROZEN = frozenset({"atr_n", "symbol", "input_symbol", "input_source", "factor_symbols",
                    "peer_symbol", "extra", "factors"})
#: Numeric in type, categorical in meaning: a side is a choice, not a magnitude.
CATEGORICAL = frozenset({"side"})
HOLD_PARAMS = ("horizon", "ttl_bars", "hold_bars", "wait_bars", "hold_days")
SESSION_PARAMS = ("selector", "condition", "session", "range_start", "signal_at")
_NULL_SCREEN = {"n_independent": 0, "gross_per_trade": 0.0, "t_gross": 0.0,
                "clears_cost": False, "refused_unfillable": 0, "screened": False}


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


# ------------------------------------------------------------------------------------------
# Parameters as coordinates
# ------------------------------------------------------------------------------------------

def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def flatten(params: dict[str, Any]) -> tuple[dict[str, float], dict[str, str]]:
    """Numeric leaves (a numeric list becomes `name.i`) and categorical leaves, by name."""
    num: dict[str, float] = {}
    cat: dict[str, str] = {}
    for k, v in (params or {}).items():
        if k in CATEGORICAL:
            cat[k] = json.dumps(v, default=str)
        elif _is_num(v):
            num[k] = v
        elif isinstance(v, (list, tuple)) and v and all(_is_num(x) for x in v):
            for i, x in enumerate(v):
                num[f"{k}.{i}"] = x
        else:
            cat[k] = json.dumps(v, sort_keys=True, default=str)
    return num, cat


def _with_numeric(params: dict[str, Any], name: str, value: float) -> dict[str, Any]:
    out = json.loads(json.dumps(params, default=str))
    head, _, tail = name.rpartition(".")
    if head and tail.isdigit() and isinstance(out.get(head), list):
        lst = list(out[head])
        lst[int(tail)] = value
        out[head] = lst
    else:
        out[name] = value
    return out


def _with_categorical(params: dict[str, Any], name: str, value_json: str) -> dict[str, Any]:
    out = json.loads(json.dumps(params, default=str))
    out[name] = json.loads(value_json)
    return out


# ------------------------------------------------------------------------------------------
# The inputs: certificates and the graph
# ------------------------------------------------------------------------------------------

def _graph_rows(skipped: dict[str, str]) -> list[dict[str, Any]]:
    try:
        from libs.research.hypothesis_graph import Graph
        rows = Graph(GRAPH).rows()
    except Exception as exc:
        skipped["hypothesis_graph"] = f"unreadable: {type(exc).__name__}: {exc}"
        return []
    if not rows:
        skipped["hypothesis_graph"] = f"no rows at {GRAPH}"
    return rows


def _current(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if isinstance(r, dict) and r.get("id"):
            out[str(r["id"])] = r
    return out


def _mechanism(cert: dict[str, Any], family: str, sym: str) -> str:
    for cand in (cert.get("mechanism"), (cert.get("shadow_spec") or {}).get("mechanism"),
                 ((cert.get("gates") or {}).get("economic_prior") or {}).get("message")):
        if isinstance(cand, str) and cand.strip():
            return f"{family} on {sym}: {cand.strip()}"
    return f"{family} on {sym}: certified {str(cert.get('gated_at') or '')[:10]}"


def load_certified(canon: dict[str, Any], current: dict[str, dict[str, Any]],
                   skipped: dict[str, str]) -> list[dict[str, Any]]:
    """Every certified cell with exact params: the canon first, then graph CERTIFIED nodes the
    canon does not carry. A certificate without params cannot be stepped from and says so."""
    from libs.research.hypothesis_graph import node_id

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, cert in (canon.get("survivors") or {}).items():
        if not isinstance(cert, dict):
            continue
        spec = cert.get("shadow_spec") or {}
        sym = str(cert.get("sym") or spec.get("symbol") or "").upper()
        fam = str(spec.get("family") or cert.get("family") or "")
        params = spec.get("params") if isinstance(spec.get("params"), dict) else None
        if not sym or not fam:
            skipped[f"canon:{key}"] = "certificate names no symbol/family"
            continue
        if params is None:
            skipped[f"canon:{key}"] = "certificate carries no exact params to step from"
            continue
        nid = node_id(sym, fam, params)
        if nid in seen:
            continue
        seen.add(nid)
        out.append({"key": str(key), "id": nid, "symbol": sym, "family": fam,
                    "params": dict(params), "gated_at": str(cert.get("gated_at") or ""),
                    "selector": spec.get("selector"), "condition": spec.get("condition"),
                    "mechanism": _mechanism(cert, fam, sym)})
    for nid, r in current.items():
        if r.get("fate") != "CERTIFIED" or nid in seen or not isinstance(r.get("params"), dict):
            continue
        seen.add(nid)
        sym, fam = str(r.get("symbol") or "").upper(), str(r.get("family") or "")
        out.append({"key": f"graph:{nid}", "id": nid, "symbol": sym, "family": fam,
                    "params": dict(r["params"]), "gated_at": str(r.get("at") or ""),
                    "selector": None, "condition": None,
                    "mechanism": f"{fam} on {sym}: {str(r.get('why') or 'certified')[:160]}"})
    return out


# ------------------------------------------------------------------------------------------
# (a) the prior, (b) the motifs
# ------------------------------------------------------------------------------------------

def _dist(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "iqr": None}
    if len(values) < 2:
        return {"n": 1, "median": float(values[0]), "iqr": 0.0}
    q = statistics.quantiles(values, n=4, method="inclusive")
    return {"n": len(values), "median": round(float(statistics.median(values)), 6),
            "iqr": round(float(q[2] - q[0]), 6)}


def survivor_prior(certified: list[dict[str, Any]],
                   failed: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per family, per numeric param: where the survivors sit versus where the failures sit."""
    vals: dict[str, dict[str, dict[str, list[float]]]] = {}
    for tag, rows in (("certified", certified), ("failed", failed)):
        for r in rows:
            num, _ = flatten(r.get("params") or {})
            fam = str(r.get("family") or "")
            for k, v in num.items():
                if k.split(".")[0] in FROZEN:
                    continue
                slot = vals.setdefault(fam, {}).setdefault(k, {"certified": [], "failed": []})
                slot[tag].append(v)
    prior: dict[str, dict[str, Any]] = {}
    for fam, by_param in vals.items():
        for k, d in by_param.items():
            c, f = _dist(d["certified"]), _dist(d["failed"])
            sep: float | None = None
            degenerate = False
            if c["median"] is not None and f["median"] is not None:
                pooled = 0.5 * (float(c["iqr"]) + float(f["iqr"]))
                gap = abs(float(c["median"]) - float(f["median"]))
                if pooled > 0:
                    sep = round(gap / pooled, 4)
                else:
                    # Both sides sit on single grid values: a relative gap, flagged, rather than
                    # a division by zero pretending to be an infinite separation.
                    degenerate = True
                    scale = max(abs(float(c["median"])), abs(float(f["median"])), 1e-9)
                    sep = round(gap / scale, 4)
            prior.setdefault(fam, {})[k] = {"certified": c, "failed": f, "separation": sep,
                                            "iqr_degenerate": degenerate}
    return prior


def motifs(certified: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """What survivors of a family share: co-occurring categorical values, hold and session
    clusters. Descriptive -- a motif is a hypothesis about the family, not a trial."""
    out: dict[str, dict[str, Any]] = {}
    per_fam: dict[str, list[dict[str, Any]]] = {}
    for c in certified:
        per_fam.setdefault(str(c["family"]), []).append(c)
    for fam, certs in per_fam.items():
        pairs: Counter[tuple[str, str]] = Counter()
        holds: dict[str, Counter[str]] = {}
        sessions: Counter[str] = Counter()
        singles: Counter[str] = Counter()
        for c in certs:
            num, cat = flatten(c.get("params") or {})
            items = sorted(f"{k}={v}" for k, v in cat.items() if k not in FROZEN)
            for k in SESSION_PARAMS:
                v = c.get(k) if k in ("selector", "condition") else (c.get("params") or {}).get(k)
                if v is not None:
                    sessions[f"{k}={v}"] += 1
            for k in HOLD_PARAMS:
                if k in num:
                    holds.setdefault(k, Counter())[str(num[k])] += 1
            singles.update(items)
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    pairs[(a, b)] += 1
        out[fam] = {"n": len(certs),
                    "categorical": [[k, n] for k, n in singles.most_common(12)],
                    "pairs": [[a, b, n] for (a, b), n in pairs.most_common(12) if n >= 2],
                    "hold_clusters": {k: dict(v.most_common(6)) for k, v in holds.items()},
                    "session_clusters": dict(sessions.most_common(8))}
    return out


# ------------------------------------------------------------------------------------------
# (c) the neighbours
# ------------------------------------------------------------------------------------------

def grid_values(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[float]]]:
    """The grid the desk has actually enumerated, per family and numeric param -- a step is a
    move to the next value on it, which is what `REGION_WIDTH` buckets and the sweeps mean."""
    grid: dict[str, dict[str, set[float]]] = {}
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("params"), dict):
            continue
        num, _ = flatten(r["params"])
        fam = str(r.get("family") or "")
        for k, v in num.items():
            grid.setdefault(fam, {}).setdefault(k, set()).add(float(v))
    return {fam: {k: sorted(v) for k, v in by.items()} for fam, by in grid.items()}


def _step(value: float, grid: list[float], up: bool) -> float | None:
    """One grid step from `value`; past the grid's edge, extrapolate by the median spacing."""
    above = [g for g in grid if g > value + 1e-12]
    below = [g for g in grid if g < value - 1e-12]
    if up and above:
        return min(above)
    if not up and below:
        return max(below)
    diffs = [b - a for a, b in pairwise(grid) if b - a > 1e-12]
    spacing = statistics.median(diffs) if diffs else (abs(value) * 0.25 or 1.0)
    out = value + spacing if up else value - spacing
    if value > 0 and out <= 0:
        return None
    return out


def _weights() -> tuple[dict[str, float], str]:
    doc = _json(WEIGHTS)
    w = {str(k): float(v) for k, v in doc.items()
         if not str(k).startswith("_") and _is_num(v) and float(v) > 0}
    if not doc:
        return {}, f"no operator weights at {WEIGHTS.name}; every operator at 1.0"
    return w, f"{len(w)} operator weights from {WEIGHTS.name}"


def _cast(value: float, like: Any) -> float | int:
    if isinstance(like, int) and not isinstance(like, bool) and float(value).is_integer():
        return int(value)
    return round(float(value), 6)


def neighbours_of(cert: dict[str, Any], prior: dict[str, dict[str, Any]],
                  grid: dict[str, dict[str, list[float]]], weights: dict[str, float],
                  survivor_values: dict[str, dict[str, Counter[str]]],
                  existing: set[str], k: int = K_NEIGHBOURS) -> list[dict[str, Any]]:
    """K untested one-step neighbours of a certificate, stepped toward the survivor median.

    Each numeric parameter is stepped toward its family's certified median (both ways when it
    sits on it); each categorical parameter may be swapped to the value most common among the
    family's survivors. A neighbour whose node already exists in the graph -- any fate -- is not
    a neighbour, it is history. Ranking: the operator's yield weight times (1 + the parameter's
    separation score), so the directions that distinguish survivors from failures are tried
    first and the operators that have paid are tried before the ones that have not.
    """
    from libs.research.hypothesis_graph import node_id

    fam, sym, params = str(cert["family"]), str(cert["symbol"]), dict(cert["params"])
    num, cat = flatten(params)
    fam_prior = prior.get(fam, {})
    fam_grid = grid.get(fam, {})
    out: list[dict[str, Any]] = []
    taken: set[str] = set()

    def _emit(new_params: dict[str, Any], op: str, score: float) -> None:
        nid = node_id(sym, fam, new_params)
        if nid in existing or nid in taken:
            return
        taken.add(nid)
        out.append({"parent": cert["key"], "parent_id": cert["id"], "symbol": sym,
                    "family": fam, "params": new_params, "operator": op, "id": nid,
                    "score": round(score, 4), "mechanism": cert["mechanism"]})

    for name, value in sorted(num.items()):
        if name.split(".")[0] in FROZEN:
            continue
        pr = fam_prior.get(name, {})
        med = (pr.get("certified") or {}).get("median")
        sep = float(pr.get("separation") or 0.0)
        directions = ([True] if med is not None and value < med else
                      [False] if med is not None and value > med else [True, False])
        for up in directions:
            nxt = _step(float(value), fam_grid.get(name, [float(value)]), up)
            if nxt is None:
                continue
            if name.split(".")[0] == "band" and not 0.0 <= nxt <= 1.0:
                continue
            op = f"step_{name.split('.')[0]}_{'up' if up else 'down'}"
            new = _with_numeric(params, name, _cast(nxt, value))
            head = name.split(".")[0]
            band = new.get(head)
            if head == "band" and isinstance(band, list) and len(band) == 2 and band[0] >= band[1]:
                continue
            _emit(new, op, weights.get(op, 1.0) * (1.0 + sep))
    for name, value in sorted(cat.items()):
        if name in FROZEN:
            continue
        seen = survivor_values.get(fam, {}).get(name)
        if not seen:
            continue
        total = sum(seen.values())
        for alt, n in seen.most_common():
            if alt != value:
                op = f"swap_{name}"
                _emit(_with_categorical(params, name, alt), op,
                      weights.get(op, 1.0) * (1.0 + n / total))
                break
    out.sort(key=lambda x: (-x["score"], x["operator"]))
    return out[:k]


def _survivor_values(certified: list[dict[str, Any]]) -> dict[str, dict[str, Counter[str]]]:
    out: dict[str, dict[str, Counter[str]]] = {}
    for c in certified:
        _, cat = flatten(c.get("params") or {})
        for k, v in cat.items():
            out.setdefault(str(c["family"]), {}).setdefault(k, Counter())[v] += 1
    return out


# ------------------------------------------------------------------------------------------
# Screening, donation, tasks
# ------------------------------------------------------------------------------------------

def _family_fn(name: str) -> Any:
    """The compiler's own registration test: `families_orthogonal` first, then `families`."""
    try:
        from mt5desk import families_orthogonal as fo
        fn = fo.ORTHOGONAL_FAMILIES.get(name)
        if fn is None:
            from mt5desk import families
            fn = getattr(families, f"family_{name}", None)
    except ImportError:
        return None
    return fn if callable(fn) else None


def _screen_symbol(sym: str, muts: list[dict[str, Any]], meta: dict[str, Any],
                   skipped: dict[str, str]) -> list[dict[str, Any]] | None:
    """Rows for every mutation of one symbol that was actually looked at; None when the symbol
    itself could not be screened here (no bars, no cost), in which case nothing was a trial."""
    d = pc.bars(sym)
    if d is None or len(d) < MIN_BARS:
        skipped[sym] = "no H1 bars on this box" if d is None else f"under {MIN_BARS} H1 bars"
        return None
    cost = pc.cost_frac(sym, meta, d["close"])
    if cost is None:
        skipped[sym] = "no contract terms to price the round trip"
        return None
    unf = pc.artifact_hours(d)
    rows: list[dict[str, Any]] = []
    for m in muts:
        cell = f"{sym}.{m['family']}.{m['operator']}"
        fn = _family_fn(str(m["family"]))
        if fn is None:
            skipped[f"{cell}:{m['id']}"] = "family not registered on this tree"
            continue
        try:
            sig = fn(d, **m["params"])
        except Exception as exc:
            skipped[f"{cell}:{m['id']}"] = f"family raised {type(exc).__name__}: {exc}"[:160]
            continue
        if not sig:
            skipped[f"{cell}:{m['id']}"] = "family produced no signals"
            continue
        sc = pc.screen(d, sig, cost, unf)
        # A SCREEN THAT LOOKED AND FOUND TOO FEW TRADES IS STILL A TRIAL. It is carried at t = 0
        # so it is counted in the deflation of the ones that cleared, never proposed itself.
        body = dict(sc) if sc else {**_NULL_SCREEN, "net_per_trade": round(-cost, 8),
                                    "cost_frac": round(cost, 8)}
        rows.append({"cell": cell, "symbol": sym, "family": m["family"], "params": m["params"],
                     "parent": m["parent"], "operator": m["operator"], "id": m["id"],
                     "mechanism": m["mechanism"], "screened": bool(sc), **body})
    return rows


def _task(m: dict[str, Any], why: str) -> dict[str, Any]:
    return {"source": SOURCE, "kind": "mutation",
            "title": f"Mutate {m['symbol']}.{m['family']}: {m['operator']} from {m['parent']}",
            "description": (f"One-step neighbour of certified cell {m['parent']} inside the "
                            f"survivor-dense region of {m['family']}: {m['operator']} -> params "
                            f"{json.dumps(m['params'], sort_keys=True, default=str)}. Not "
                            f"screened here: {why}. Screen where bars exist, then the ordinary "
                            "gauntlet with the lifetime multiplicity charge; do not "
                            "re-parameterise further."),
            "symbols": [m["symbol"]], "family": m["family"], "params": m["params"],
            "parent": m["parent"], "operator": m["operator"], "status": None,
            "consumer": "proposers / gauntlet"}


def run(budget_s: float = 900.0, symbols: list[str] | None = None,
        write: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    skipped: dict[str, str] = {}
    canon = _json(CANON)
    if not canon:
        skipped["canon"] = f"no survivors canon at {CANON}"
    rows = _graph_rows(skipped)
    current = _current(rows)
    certified = load_certified(canon, current, skipped)
    failed = [r for r in current.values() if r.get("fate") in ("FAILED", "BURIED")]
    prior = survivor_prior(certified, failed)
    mot = motifs(certified)
    grid = grid_values(rows + certified)
    weights, weights_note = _weights()
    existing = set(current) | {c["id"] for c in certified}
    sv = _survivor_values(certified)
    todo = [c for c in certified if not symbols or c["symbol"] in {s.upper() for s in symbols}]
    neighbours: list[dict[str, Any]] = []
    for c in sorted(todo, key=lambda x: (x["symbol"], x["family"], x["key"])):
        ns = neighbours_of(c, prior, grid, weights, sv, existing)
        existing.update(n["id"] for n in ns)
        neighbours.extend(ns)

    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    meta = pc.universe_meta()
    by_sym: dict[str, list[dict[str, Any]]] = {}
    for n in neighbours:
        by_sym.setdefault(n["symbol"], []).append(n)
    screened: list[dict[str, Any]] = []
    unscreened: list[tuple[dict[str, Any], str]] = []
    for sym in sorted(by_sym):
        if sym not in have:
            skipped[sym] = "no H1 bars on this box"
            unscreened.extend((m, skipped[sym]) for m in by_sym[sym])
            continue
        if time.monotonic() - started > budget_s:
            skipped[sym] = "distiller budget exhausted"
            unscreened.extend((m, skipped[sym]) for m in by_sym[sym])
            continue
        got = _screen_symbol(sym, by_sym[sym], meta, skipped)
        if got is None:
            unscreened.extend((m, skipped.get(sym, "unscreenable")) for m in by_sym[sym])
            continue
        screened.extend(got)
    screened = pc.deflate(screened)
    proposals = pc.best_per_cell(screened)
    cands = [pc.candidate(
        SOURCE, r["symbol"], str(r["family"]), dict(r["params"]),
        mechanism=f"{r['mechanism']} (mutation: {r['operator']})",
        title=f"{r['cell']} from {r['parent']}",
        evidence={**{k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                          "cost_frac", "t_gross", "t_deflated_sweep",
                                          "n_tests_sweep", "t_deflated_lifetime",
                                          "n_tests_lifetime")},
                  "parent": r["parent"], "operator": r["operator"]}) for r in proposals]
    unscreened.sort(key=lambda x: (-x[0]["score"], x[0]["id"]))
    tasks = [_task(m, why) for m, why in unscreened[:MAX_TASKS]]
    rep: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).isoformat(), "graph_rows": len(rows),
        "certified_cells": len(certified), "certified_swept": len(todo),
        "prior": prior, "motifs": mot, "weights": weights_note,
        "neighbours_generated": len(neighbours), "tests_run": len(screened),
        "cells_proposed": len(proposals), "n_unscreened": len(unscreened),
        "n_tasks": len(tasks), "skipped": skipped, "proposals": proposals,
        "by_operator": dict(Counter(r["operator"] for r in screened)),
        "elapsed_s": round(time.monotonic() - started, 1)}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
        if cands:
            rep["donated"] = str(pc.donate(SOURCE, cands, len(screened)))
        if tasks:
            try:
                from research.regime_coverage import _merge_into_queue
                _merge_into_queue(tasks, source=SOURCE)
                rep["queued"] = len(tasks)
            except Exception as exc:
                rep["queued"] = f"FAILED: {type(exc).__name__}: {exc}"
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=900.0)
    a = ap.parse_args()
    r = run(budget_s=a.budget_s, symbols=a.symbol)
    print(f"SURVIVOR DISTILLER  {r['certified_cells']} certified, {r['neighbours_generated']} "
          f"neighbours, {r['tests_run']} tests, {r['cells_proposed']} proposed, "
          f"{r['n_tasks']} tasks queued  ({r['weights']})")
    for fam, by in r["prior"].items():
        for k, v in by.items():
            print(f"  {fam:24s} {k:12s} cert={v['certified']['median']} "
                  f"fail={v['failed']['median']} sep={v['separation']}")
    for p in r["proposals"][:10]:
        print(f"  {p['cell']:44s} t={p['t_gross']:+.2f} t_defl={p['t_deflated_sweep']:+.2f} "
              f"n={p['n_independent']}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
