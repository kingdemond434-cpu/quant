"""Unknown-unknowns to cells: EXECUTE what the anomaly miner found, charge it for the whole
search it was selected from, and send what cannot be executed to be NAMED.

THE GAP THIS CLOSES. `libs.research.anomaly_miner` scans the desk's own bars for conditional
structure and emits ANOMALIES -- (symbol, condition, horizon, effect, n, t) -- never candidates.
Measured on the latest scan (2026-09-04 08:34): 30 symbols, 3,177,084 cells, 3,629 reportable,
3,090 of them past |t| >= 3 and n >= 60. An anomaly is an observation. It becomes something the
gauntlet can judge only when it is executed as trades, net of the round trip, and deflated by
everything that was looked at -- and that step had no owner.

WHAT MAKES A CONDITION EXECUTABLE, and it is not a guess. The miner's condition string is
`<primitive>_q<lo>-<hi>` where `<primitive>` is a name `edge_search.build_primitives` supplies,
and `family_discovered(feature, band, horizon, side)` is the desk's existing executor for exactly
that shape: it looks the primitive up in the same builder, recomputes the band, opens a position
whenever the condition holds and holds it for the horizon. Every field is copied from the
measurement -- side is the SIGN of the measured effect, hold is the measured horizon -- so nothing
here invents a family or a parameter. A condition whose primitive does not resolve (an acquired
`ext_` series absent on this tree, an interaction the memory-bounded pool did not form), or whose
shape is not a single-feature recipe (the 71 lead-lag rows carry a correlation, not an entry
threshold), is UNEXECUTABLE HERE and goes to the deepening queue as kind `anomaly`, carrying the
miner's question and the note that a mechanism must be NAMED before it can be a candidate.

DEFLATION COUNTS EVERY TRIAL, INCLUDING THE MINER'S. `proposer_common.deflate` charges a row for
the rows in its own sweep; that is not enough here, because each anomaly was already the winner
of the miner's search over its symbol -- 9,000-36,000 cells -- and that width is carried on the
row as `selection_trials`. So every row is charged n_sweep + selection_trials, then the family's
lifetime count on top, and `proposed` needs the sweep-deflated t over PROPOSE_T exactly as the
other proposers do. Near-duplicates (one feature and side measured at several bands and horizons)
are collapsed to the strongest first, the way `compile_anomalies` does, so the docket is not
spent re-testing one effect; the collapsed rows are counted, never dropped silently. Regions the
hypothesis graph has already buried are not re-proposed: the revival engine owns second looks.

WHAT LEAVES. Survivors are donated under SOURCE `anomaly_factory` as EXACT_RECIPE cells of family
`discovered`; the mechanism on the candidate is the adapter's when one matched and an explicit
STATISTICAL_ONLY statement when none did, so the economic_prior gate sees the truth rather than
a story. The gauntlet judges them like everything else; nothing here has authority.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402

from libs.research import anomaly_miner as am  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research.multiplicity import deflate_t  # noqa: E402

SOURCE = "anomaly_factory"
FAMILY = "discovered"
KIND = "anomaly"
REPORT = _DESK / "reports" / "ANOMALY_FACTORY.json"
#: The miner's own reporting floors, quoted rather than restated so the two cannot drift apart.
MIN_T = float(am.REPORT_T)
MIN_N = int(am.MIN_N)
#: Naming tasks per run. The queue is worked by a paid seat; the strongest unexecutable anomalies
#: go first and the rest are deferred to the next scan, which will re-find them if they persist.
MAX_TASKS = 40
#: Bars used to learn the primitive VOCABULARY (names only). The names build_primitives supplies
#: do not depend on the frame's length, so a short tail answers "does this primitive exist here"
#: without paying the 4.3s full-frame build twice per symbol.
VOCAB_BARS = 600
#: The miner's own floor for scanning a frame at all; below it there is nothing to execute on.
MIN_BARS = 1200
_COND = re.compile(r"^(?P<feature>.+)_q(?P<lo>[0-9.]+)-(?P<hi>[0-9.]+)$")


def parse_condition(condition: str) -> tuple[str, tuple[float, float]] | None:
    """`<primitive>_q<lo>-<hi>` -> (primitive, (lo, hi)); anything else has no recipe here."""
    m = _COND.match(str(condition or ""))
    if not m:
        return None
    try:
        lo, hi = float(m.group("lo")), float(m.group("hi"))
    except ValueError:
        return None
    if not (0.0 <= lo < hi <= 1.0):
        return None
    return m.group("feature"), (lo, hi)


def _side(mean_bp: Any) -> int:
    """Direction is the SIGN OF THE MEASURED EFFECT. Never a preference, never a default."""
    return 1 if float(mean_bp or 0.0) >= 0 else -1


def _extra_for(d: Any) -> dict[str, Any]:
    """The acquired series the miner conditioned on, so `ext_` primitives resolve here as there."""
    try:
        from research.acquire_datasets import acquired_series
        return dict(acquired_series(d.index))
    except Exception:
        return {}


def _vocabulary(d: Any, sym: str, extra: dict[str, Any]) -> set[str]:
    try:
        from research.edge_search import build_primitives
        return set(build_primitives(d.tail(VOCAB_BARS), sym, extra))
    except Exception:
        return set()


def _buried_index() -> tuple[dict[tuple[str, str, int], int], str]:
    """(symbol, feature, side) -> how many times the graph buried a `discovered` cell there.

    Band- and horizon-agnostic on purpose: one feature and side measured at another band is the
    re-parameterisation the revival engine forbids, not a new hypothesis.
    """
    try:
        from libs.research.hypothesis_graph import Graph
        buried = Graph().buried()
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"
    idx: dict[tuple[str, str, int], int] = {}
    for rows in buried.values():
        for r in rows:
            p = r.get("params") or {}
            if str(r.get("family")) == FAMILY and isinstance(p, dict) and p.get("feature"):
                key = (str(r.get("symbol")).upper(), str(p["feature"]), _side(p.get("side", 1)))
                idx[key] = idx.get(key, 0) + 1
    return idx, ""


def _family_trials() -> int:
    try:
        from libs.research.experiment_ledger import family_trials
        return int(family_trials(FAMILY))
    except Exception:
        return 0


def _mechanism(a: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The adapter's named cause when one matches; otherwise an explicit STATISTICAL_ONLY.

    No economic story is invented. A candidate that reaches the gauntlet unnamed must say so on
    its face, so the economic_prior gate refuses it for the right reason.
    """
    try:
        from libs.research.mechanism_adapters import explain
        causes = (explain(a) or {}).get("candidate_explanations") or []
    except Exception:
        causes = []
    if causes:
        c = causes[0]
        return (f"{c.get('mechanism')}: {c.get('causal_story')}",
                {"mechanism_status": "ADAPTER_NAMED", "falsifier": c.get("falsifier"),
                 "payer": c.get("payer"), "adapters_matched": len(causes)})
    t = float(a.get("t_stat") or 0.0)
    effect, base = float(a.get("mean_bp") or 0.0), float(a.get("baseline_bp") or 0.0)
    return (f"STATISTICAL_ONLY -- {a.get('condition')} on {a.get('symbol')} conditions "
            f"{a.get('horizon')}-bar forward returns ({effect:+.1f}bp against a {base:+.1f}bp "
            f"baseline, miner |t|={abs(t):.1f}); no mechanism named. The economic_prior gate "
            "must be answered by the naming queue, not by this proposer.",
            {"mechanism_status": "UNNAMED", "falsifier": None, "payer": None,
             "adapters_matched": 0})


def _task(a: dict[str, Any], why: str) -> dict[str, Any]:
    t = float(a.get("t_stat") or 0.0)
    h = int(a.get("horizon") or 0)
    sym, cond = str(a.get("symbol")), str(a.get("condition"))
    effect = (f"{float(a['mean_bp']):+.1f}bp against a {float(a.get('baseline_bp') or 0):+.1f}bp "
              "baseline" if a.get("mean_bp") is not None
              else f"corr {float(a.get('corr') or 0):+.3f}")
    return {"source": SOURCE, "kind": KIND,
            "title": f"NAME IT: {sym} {cond} h={h} |t|={abs(t):.1f}",
            "description": (f"{a.get('question') or ''} Condition: {cond}; horizon: {h} bars; "
                            f"t={t:+.2f}; n={a.get('n')}; effect: {effect}. Not executable here: "
                            f"{why}. A MECHANISM MUST BE NAMED, with evidence and a falsifier, "
                            "before this can become a candidate -- an anomaly is an observation, "
                            "and the compiler refuses a correlation wearing a story."),
            "symbols": [sym] + ([str(a["against"])] if a.get("against") else []),
            "family": None,
            "params": {"condition": cond, "horizon": h, "t_stat": t, "n": a.get("n"),
                       "mean_bp": a.get("mean_bp"), "corr": a.get("corr"),
                       "against": a.get("against"), "family_hint": a.get("family_hint"),
                       "selection_trials": a.get("selection_trials")},
            "status": None,
            "consumer": ("deepening_worker (anomaly) -> a NAMED mechanism with a falsifier; only "
                         "then a family recipe for the gauntlet")}


def deflate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Charge every row for this sweep AND the miner's search over its symbol, then lifetime.

    Mirrors `proposer_common.deflate`'s fields so the compiler and the allocator read this
    proposer's rows like any other's; the only difference is that the charge is LARGER.
    """
    n = len(rows)
    life = _family_trials()
    for r in rows:
        charged = n + int(r.get("selection_trials") or 0)
        t = float(r.get("t_gross") or 0.0)
        r["n_tests_sweep"] = charged
        r["t_deflated_sweep"] = round(deflate_t(t, charged), 3)
        r["n_tests_lifetime"] = charged + life
        r["t_deflated_lifetime"] = round(deflate_t(t, charged + life), 3)
        r["proposed"] = bool(r.get("clears_cost") and r["t_deflated_sweep"] > pc.PROPOSE_T
                             and int(r.get("n_independent", 0)) >= pc.MIN_TRADES)
    return rows


def run(symbols: list[str] | None = None, budget_s: float = 1200.0,
        scan_limit: int | None = None, write_queue: bool = True) -> dict:
    started = time.monotonic()
    skipped: dict[str, int] = {}
    detail: list[dict[str, Any]] = []

    def skip(reason: str, **info: Any) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1
        if len(detail) < 60:
            detail.append({"why": reason, **info})

    # 1. THE SCAN. The miner rotates its own cursor over the universe; a failure here is a
    #    recorded reason and an empty run, never an empty report that looks like a clean one.
    try:
        scan = am.scan(symbols=symbols, limit=scan_limit)
        scan_err = ""
    except Exception as exc:
        scan, scan_err = {"anomalies": [], "trials": 0}, f"{type(exc).__name__}: {exc}"
    scan_s = time.monotonic() - started
    anomalies = [a for a in (scan.get("anomalies") or []) if isinstance(a, dict)]
    eligible = [a for a in anomalies if abs(float(a.get("t_stat") or 0.0)) >= MIN_T
                and int(a.get("n") or 0) >= MIN_N]
    if len(anomalies) > len(eligible):
        skipped[f"below the |t| >= {MIN_T:g}, n >= {MIN_N} floor"] = len(anomalies) - len(eligible)

    # 2. SHAPE. A single-feature recipe executes; anything else must be named first.
    buried, graph_err = _buried_index()
    best: dict[tuple[str, str, int], dict[str, Any]] = {}
    unexec: list[tuple[dict[str, Any], str]] = []
    collapsed = 0
    for a in eligible:
        parsed = parse_condition(str(a.get("condition") or ""))
        if parsed is None or a.get("mean_bp") is None:
            hint = a.get("family_hint")
            unexec.append((a, (f"family_hint {hint!r} carries a correlation, not a recipe: the "
                               f"{hint} family needs an entry threshold the miner did not measure"
                               if hint else "condition is not <primitive>_q<lo>-<hi>")))
            continue
        feature, _band = parsed
        key = (str(a["symbol"]).upper(), feature, _side(a["mean_bp"]))
        prev = best.get(key)
        if prev is None or abs(float(a["t_stat"])) > abs(float(prev["t_stat"])):
            collapsed += prev is not None
            best[key] = a
        else:
            collapsed += 1
    todo: dict[str, list[dict[str, Any]]] = {}
    n_buried = 0
    for (sym_u, feature, side), a in best.items():
        n_failed = buried.get((sym_u, feature, side), 0)
        if n_failed:
            n_buried += 1
            skip("region already buried in the hypothesis graph", symbol=sym_u, feature=feature,
                 side=side, n_failed=n_failed)
            continue
        todo.setdefault(str(a["symbol"]), []).append(a)

    # 3. EXECUTE, strongest symbol first, one frame in memory at a time.
    meta = pc.universe_meta()
    fam = fo.ORTHOGONAL_FAMILIES.get(FAMILY)
    rows: list[dict[str, Any]] = []
    order = sorted(todo, key=lambda s: -max(abs(float(a["t_stat"])) for a in todo[s]))
    for sym in order:
        pending = sorted(todo[sym], key=lambda a: -abs(float(a["t_stat"])))
        if fam is None:
            unexec.extend((a, f"family {FAMILY!r} is not registered on this tree")
                          for a in pending)
            continue
        if time.monotonic() - started > budget_s:
            for a in pending:
                skip("budget exhausted before execution", symbol=sym, condition=a["condition"])
            continue
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            for _ in pending:
                skip(f"under {MIN_BARS} H1 bars on this tree", symbol=sym)
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            for _ in pending:
                skip("no contract terms to price the round trip", symbol=sym)
            continue
        unf = pc.artifact_hours(d)
        need_extra = any("ext_" in str(a["condition"]) for a in pending)
        extra = _extra_for(d) if need_extra else {}
        vocab = _vocabulary(d, sym, extra)
        for a in pending:
            if time.monotonic() - started > budget_s:
                skip("budget exhausted before execution", symbol=sym, condition=a["condition"])
                continue
            feature, band = parse_condition(str(a["condition"]))  # type: ignore[misc]
            if vocab and feature not in vocab:
                unexec.append((a, (f"no primitive named {feature!r} resolves through "
                                   "edge_search.build_primitives on this tree"
                                   + (" (acquired series absent)" if "ext_" in feature else ""))))
                continue
            params = {"feature": feature, "band": [band[0], band[1]],
                      "horizon": int(a.get("horizon") or 1), "side": _side(a["mean_bp"])}
            try:
                sig = fam(d, extra=extra or None, **params)
                sc = pc.screen(d, sig, cost, unf)
            except Exception as exc:
                skip(f"execution failed: {type(exc).__name__}", symbol=sym,
                     condition=a["condition"], error=str(exc)[:160])
                continue
            row: dict[str, Any] = {
                "cell": f"{sym}.{FAMILY}.{feature}", "symbol": sym, "params": params,
                "condition": str(a["condition"]), "n_signals": len(sig),
                "anomaly": {k: a.get(k) for k in ("t_stat", "n", "mean_bp", "hit_rate",
                                                  "baseline_bp")},
                "question": a.get("question"),
                "selection_trials": int(a.get("selection_trials") or scan.get("trials") or 0)}
            if sc is None:
                # TRIED AND EMPTY IS STILL TRIED. The row stays in the sweep count with t = 0;
                # the reason is on the row so a reader can tell "no signals" from "no edge".
                row.update({"n_independent": 0, "gross_per_trade": 0.0, "net_per_trade": 0.0,
                            "cost_frac": cost, "t_gross": 0.0, "clears_cost": False,
                            "refused_unfillable": 0,
                            "why": ("family resolved no signals" if not sig else
                                    f"under {pc.MIN_TRADES} non-overlapping trades")})
            else:
                row.update(sc)
            rows.append(row)
        # BOUNDED MEMORY. family_discovered caches ~750 primitive series per frame (hundreds of
        # MB on a 53,899-bar frame) for up to eight frames; this box has 3.8GB and no swap.
        getattr(fo, "_PRIM_CACHE", {}).clear()

    # 4. DEFLATE against the whole width, propose, donate.
    rows = deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = []
    for r in proposals:
        a = {**r["anomaly"], "symbol": r["symbol"], "condition": r["condition"],
             "horizon": r["params"]["horizon"], "question": r.get("question")}
        mech, mech_ev = _mechanism(a)
        cands.append(pc.candidate(
            SOURCE, r["symbol"], FAMILY, dict(r["params"]), mechanism=mech,
            title=(f"{r['cell']} {r['condition']} h={r['params']['horizon']} "
                   f"side={r['params']['side']:+d}"),
            evidence={**{k: r.get(k) for k in ("n_independent", "gross_per_trade",
                                               "net_per_trade", "cost_frac", "t_gross",
                                               "t_deflated_sweep", "n_tests_sweep",
                                               "t_deflated_lifetime", "n_tests_lifetime",
                                               "selection_trials", "refused_unfillable")},
                      "miner": r["anomaly"], "question": r.get("question"), **mech_ev}))

    # 5. WHAT CANNOT BE EXECUTED IS NAMED FIRST. Strongest first, capped, buried skipped.
    tasks: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for a, why in sorted(unexec, key=lambda aw: -abs(float(aw[0].get("t_stat") or 0.0))):
        key = (str(a.get("symbol")).upper(), str(a.get("condition")), int(a.get("horizon") or 0))
        parsed = parse_condition(str(a.get("condition") or ""))
        if parsed and a.get("mean_bp") is not None and buried.get(
                (key[0], parsed[0], _side(a["mean_bp"]))):
            n_buried += 1
            skip("region already buried in the hypothesis graph", symbol=key[0],
                 condition=key[1])
            continue
        if key in seen:
            continue
        seen.add(key)
        if len(tasks) >= MAX_TASKS:
            skip(f"naming queue capped at {MAX_TASKS} per run; deferred", symbol=key[0],
                 condition=key[1])
            continue
        tasks.append(_task(a, why))
    by_reason: dict[str, int] = {}
    for _a, why in unexec:
        head = why.split(":")[0]
        by_reason[head] = by_reason.get(head, 0) + 1

    with_trades = [r for r in rows if int(r.get("n_independent", 0)) > 0]
    rep = {"generated_at": datetime.now(tz=UTC).isoformat(),
           "tests_run": len(rows), "cells_proposed": len(proposals),
           "executable": {"n": len(rows), "with_trades": len(with_trades),
                          "clearing_cost": sum(1 for r in rows if r.get("clears_cost")),
                          "top": [{k: r.get(k) for k in (
                              "cell", "condition", "params", "n_independent", "t_gross",
                              "t_deflated_sweep", "n_tests_sweep", "selection_trials",
                              "clears_cost", "proposed", "why")}
                              for r in sorted(rows, key=lambda r: -float(
                                  r.get("t_deflated_sweep") or -99.0))[:25]]},
           "unexecutable": {"n": len(unexec), "tasks": len(tasks), "by_reason": by_reason,
                            "cap": MAX_TASKS},
           "skipped": {"reasons": skipped, "detail": detail},
           "anomalies_in": len(anomalies), "eligible": len(eligible),
           "collapsed_near_duplicates": collapsed, "buried": n_buried,
           "hypothesis_graph": graph_err or "ok",
           "scan": {"symbols_scanned": scan.get("symbols_scanned"), "trials": scan.get("trials"),
                    "cross_sectional_trials": scan.get("cross_sectional_trials"),
                    "seconds": round(scan_s, 1), "error": scan_err},
           "proposals": proposals, "budget_s": budget_s,
           "floors": {"t": MIN_T, "n": MIN_N, "propose_t": pc.PROPOSE_T,
                      "min_trades": pc.MIN_TRADES},
           "rule": ("every executed anomaly is a row charged n_sweep + the miner's "
                    "selection_trials for its symbol, then the family's lifetime count; "
                    f"proposed needs clears_cost, deflated t > {pc.PROPOSE_T} and "
                    f">= {pc.MIN_TRADES} trades. Unexecutable anomalies become `{KIND}` tasks: a "
                    "mechanism must be NAMED before they can be candidates.")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    if cands:
        rep["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    # A failed scan must not erase the last real run's naming tasks.
    if write_queue and not scan_err:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source=SOURCE)
            rep["queue_merged"] = True
        except Exception as exc:
            rep["queue_merged"] = f"{type(exc).__name__}: {exc}"
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=1200.0)
    ap.add_argument("--scan-limit", type=int, default=None)
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    r = run(symbols=a.symbol, budget_s=a.budget_s, scan_limit=a.scan_limit,
            write_queue=not a.no_queue)
    print(f"ANOMALY FACTORY  {r['anomalies_in']} anomalies, {r['eligible']} eligible, "
          f"{r['tests_run']} executed, {r['cells_proposed']} proposed, "
          f"{r['unexecutable']['tasks']} naming tasks ({r['unexecutable']['n']} unexecutable), "
          f"{r['buried']} buried, scan {r['scan']['seconds']}s"
          + (f"  SCAN ERROR: {r['scan']['error']}" if r["scan"]["error"] else ""))
    for x in r["executable"]["top"][:10]:
        print(f"  {x['cell']:44s} t={x['t_gross']:+.2f} t_defl={x['t_deflated_sweep']:+.2f} "
              f"n={x['n_independent']:4d} charged={x['n_tests_sweep']}"
              + (f"  {x['why']}" if x.get("why") else ""))
    for k, v in r["skipped"]["reasons"].items():
        print(f"  skipped {v}: {k}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
