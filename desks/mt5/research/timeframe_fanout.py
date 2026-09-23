"""THE SAME MECHANISM, MINTED ON EVERY CHART -- so the judge decides which chart pays.

THE PRINCIPAL, 2026-09-23: *"retest every certificate across timeframes ... the same mechanisms
are being tested on the wrong charts."*

THE MEASUREMENT THAT FORCES IT, and it is this desk's own. `counterfactual_timeframes` replays
222 REAL decisions -- the identical decision, stop, target and cost model -- on each chart the box
holds bars for, and publishes:

    M5    +0.869 R   over the H1 replay   (n = 41)
    M15   +0.360 R   over the H1 replay   (n = 111)
    H1     reference
    M1    UNMEASURED (no row triggered)

And the registry, counted the same morning: 16,222 of 18,201 candidates carry chart H1, 684 H4,
117 M15, and ZERO carry M5 or M1. So the chart that paid most in the desk's own replay has never
had a single cell minted on it. That is not a research result; it is a COMPILER DEFAULT that no
measurement ever informed, and it has been silently answering a question the gauntlet was never
allowed to see.

WHAT THIS ORGAN DOES. It takes work already done -- every certified mechanism in the canonical
lane (`reports/UNIVERSAL_SURVIVORS.json`) and every strong family in the docket (the registry's
own survivors and each family's best-scored representative) -- and mints the SAME spec on M1, M5,
M15, H1 and H4 as separate cells through the one door, each carrying provenance that names its
parent and the parent's chart. It changes no rule, no parameter, no symbol and no side. The only
thing that varies is the chart, which is the whole point: the judge decides which chart pays
rather than the compiler assuming.

THE TRIALS ARE CHARGED, and this is the half that makes it honest rather than free. Five charts
is five times the cells, and a multiple-testing budget that does not notice is a budget that
lies. Every minted cell becomes a `libs.research.trial_ledger.Trial` whose descriptors carry the
symbol, the chart, the session and the regime, and the pass is priced by `trial_ledger.census` --
the participation ratio, so five charts of ONE mechanism are charged as the correlated family
they are and not as five independent discoveries. Both numbers are published: `n_raw` (what the
desk would have to admit to a naive counter) and `n_effective` (what the deflated-Sharpe charge
should actually use), with the inflation between them.

NOTHING HERE IS A FILTER. No chart is preferred, none is dropped, no parent is refused and no
threshold is applied. A chart with no bars on this host still gets its cell -- the gauntlet
reports UNMEASURED for it, which is a verdict this desk trusts more than an assumption.

    python desks/mt5/research/timeframe_fanout.py --once --budget-s 240
    python desks/mt5/research/timeframe_fanout.py --once --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CTF = DESK / "reports" / "COUNTERFACTUAL_TIMEFRAMES.json"
CURSOR = DESK / "data" / "timeframe_fanout_cursor.json"
OUT = DESK / "reports" / "TIMEFRAME_FANOUT.json"

#: Every chart the same spec is minted on. M1 and M5 are here because the registry carried NONE
#: and the replay says M5 paid most; H1 because it is the parent's own chart and the fanout must
#: include the control, or the comparison is between five new things and nothing.
CHARTS: tuple[str, ...] = ("M1", "M5", "M15", "H1", "H4")

#: Parents taken per pass from each lane, advanced by a saved cursor so every parent is reached.
#: Not a cap: a parent not reached this pass leads the next one.
PARENTS_PER_LANE_PER_PASS = 40


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def canonical_parents() -> tuple[list[dict[str, Any]], str]:
    """Every certified mechanism in the canonical lane, as a spec this organ can re-mint."""
    doc = _read(SURVIVORS, {}) or {}
    surv = doc.get("survivors") if isinstance(doc, dict) else None
    if not isinstance(surv, dict) or not surv:
        return [], ("UNMEASURED: reports/UNIVERSAL_SURVIVORS.json carries no survivors on this "
                    "host; the canonical lane cannot be re-minted from an absent lane")
    out: list[dict[str, Any]] = []
    for key, row in surv.items():
        if not isinstance(row, dict):
            continue
        _spec = row.get("shadow_spec")
        spec: dict[str, Any] = dict(_spec) if isinstance(_spec, dict) else {}
        sym = str(spec.get("symbol") or row.get("sym") or "")
        fam = str(spec.get("family") or "")
        if not sym or not fam:
            continue
        out.append({
            "lane": "canonical", "parent": str(key), "symbol": sym, "family": fam,
            "params": {k: v for k, v in spec.items()
                       if k in ("side", "selector", "condition", "hunt")},
            "session": str(spec.get("selector") or ""),
            "regime": str(spec.get("condition") or ""),
            "parent_chart": str(spec.get("chart") or "H1"),
            "mechanism": (f"certified mechanism {fam} on {sym} "
                          f"({spec.get('side') or ''} {spec.get('selector') or ''}), "
                          "re-minted on every chart so the judge picks the chart"),
        })
    return out, ""


def docket_parents(limit: int = 4000) -> tuple[list[dict[str, Any]], str]:
    """Every STRONG family row in the docket: the registry's own survivors, plus each family's
    best-scored representative so a family with no survivor yet is still asked on every chart."""
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception as exc:
        return [], f"registry unavailable: {type(exc).__name__}: {exc}"
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        q_surv = ("SELECT id, family, symbol, params_json, chart, session, regime, horizon, "
                  "mechanism, asset_class FROM research_candidates WHERE survived=1 LIMIT ?")
        # SQLite's bare-column-with-MAX idiom: one pass, the row carrying each family's best
        # score. The correlated `WHERE score = (SELECT MAX...)` form is an O(n^2) scan and took
        # longer than the whole pass budget on this box's 18,201 candidates.
        q_best = ("SELECT id, family, symbol, params_json, chart, session, regime, horizon, "
                  "mechanism, asset_class, MAX(score) AS _s FROM research_candidates "
                  "GROUP BY family LIMIT ?")
        for lane, q in (("docket_survivor", q_surv), ("docket_family_best", q_best)):
            for r in conn.execute(q, (limit,)):
                cid = str(r["id"])
                if cid in seen:
                    continue
                seen.add(cid)
                try:
                    params = json.loads(r["params_json"] or "{}")
                except ValueError:
                    params = {}
                rows.append({
                    "lane": lane, "parent": cid, "symbol": str(r["symbol"] or ""),
                    "family": str(r["family"] or ""), "params": params,
                    "session": str(r["session"] or ""), "regime": str(r["regime"] or ""),
                    "asset_class": str(r["asset_class"] or ""),
                    "parent_chart": str(r["chart"] or "H1"),
                    "mechanism": str(r["mechanism"] or f"{r['family']} on {r['symbol']}"),
                })
    except Exception as exc:
        return rows, f"registry query failed: {type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(Exception):
            conn.close()
    return [r for r in rows if r["symbol"] and r["family"]], ""


def chart_order() -> tuple[list[str], dict[str, Any]]:
    """The charts in the order the desk's OWN replay says they paid. Never a filter: every chart
    in CHARTS is minted, this only decides which is minted first when a budget runs out."""
    doc = _read(CTF, {}) or {}
    per = doc.get("per_chart") if isinstance(doc, dict) else None
    if not isinstance(per, dict):
        return list(CHARTS), {"basis": "COUNTERFACTUAL_TIMEFRAMES.json absent: registry order"}
    def _key(c: str) -> float:
        row = per.get(c) or {}
        m = row.get("mean")
        return -float(m) if isinstance(m, (int, float)) else 0.0
    return sorted(CHARTS, key=_key), {
        "basis": "reports/COUNTERFACTUAL_TIMEFRAMES.json per_chart mean, most-paying first",
        "per_chart": {c: (per.get(c) or {}).get("mean") for c in CHARTS}}


def mint(parent: dict[str, Any], charts: list[str], *, dry_run: bool) -> dict[str, Any]:
    """The same spec on every chart, each cell naming its parent. Never judges anything."""
    made = created = 0
    errors: list[str] = []
    trials: list[dict[str, Any]] = []
    for chart in charts:
        made += 1
        params = {**dict(parent.get("params") or {}), "parent_chart": parent["parent_chart"],
                  "chart": chart}
        trials.append({"trial_id": f"{parent['parent'][:28]}@{chart}",
                       "family": parent["family"],
                       "descriptors": {"symbol": parent["symbol"], "chart": chart,
                                       "session": parent.get("session") or "",
                                       "regime": parent.get("regime") or "",
                                       "asset_class": parent.get("asset_class") or ""},
                       "params": {k: v for k, v in params.items()
                                  if isinstance(v, (int, float))}})
        if dry_run:
            continue
        try:
            from libs.moat.registry import enqueue_candidate
            _cid, was_new = enqueue_candidate(
                family=parent["family"], symbol=parent["symbol"], params=params,
                origin="timeframe_fanout", mechanism=parent["mechanism"], chart=chart,
                horizon=chart, session=parent.get("session") or "",
                regime=parent.get("regime") or "",
                asset_class=parent.get("asset_class") or "",
                generator="timeframe_fanout", department="prediction",
                transformation="chart_fanout",
                parent_ids=[parent["parent"]],
                causal_rationale=parent["mechanism"],
                falsifier=(f"{parent['family']} on {parent['symbol']} has no edge at {chart} "
                           f"that it has at {parent['parent_chart']}"))
            created += int(bool(was_new))
        except Exception as exc:
            errors.append(f"{parent['parent'][:20]}@{chart}: "
                          f"{type(exc).__name__}: {str(exc)[:50]}")
    return {"emitted": made, "created": created, "errors": errors, "trials": trials}


def charge_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Price this pass's multiplicity with the desk's own effective-trial ledger.

    n_raw is every minted cell. n_effective is the participation ratio over the similarity
    matrix, so five charts of one mechanism cost less than five independent bets and MORE than
    one -- which is the true charge and the reason this is not free breadth.
    """
    if not trials:
        return {"n_raw": 0, "n_effective": 0.0, "inflation": 1.0,
                "basis": "no cell minted this pass"}
    try:
        from libs.research import trial_ledger as tl
    except Exception as exc:
        return {"n_raw": len(trials), "n_effective": None,
                "basis": f"UNMEASURED: trial_ledger unavailable ({type(exc).__name__}: {exc})"}
    rows = [tl.Trial(t["trial_id"], t["family"], t["descriptors"], t["params"])
            for t in trials]
    try:
        c = tl.census(rows)
    except Exception as exc:
        return {"n_raw": len(trials), "n_effective": None,
                "basis": f"UNMEASURED: census failed ({type(exc).__name__}: {exc})"}
    return {"n_raw": int(c.n_raw), "n_effective": round(float(c.n_effective), 2),
            "inflation": round(float(c.inflation), 3), "n_families": len(c.families),
            "basis": ("libs.research.trial_ledger.census participation ratio over this pass's "
                      "minted cells; the deflated-Sharpe charge should use n_effective")}


def build(budget_s: float = 240.0, *, dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    charts, chart_basis = chart_order()
    canon, canon_why = canonical_parents()
    docket, docket_why = docket_parents()
    cursor = _read(CURSOR, {}) or {}
    starts: dict[str, int] = dict(cursor.get("starts") or {})

    lanes: dict[str, list[dict[str, Any]]] = {"canonical": canon}
    for r in docket:
        lanes.setdefault(r["lane"], []).append(r)

    emitted = created = 0
    per_lane: dict[str, dict[str, Any]] = {}
    all_trials: list[dict[str, Any]] = []
    errors: list[str] = []
    for lane, rows in lanes.items():
        start = int(starts.get(lane) or 0) % max(len(rows), 1)
        order = rows[start:] + rows[:start]
        n_done = lane_emitted = lane_created = 0
        for parent in order[:PARENTS_PER_LANE_PER_PASS]:
            if time.monotonic() - t0 > budget_s:
                break
            res = mint(parent, charts, dry_run=dry_run)
            n_done += 1
            lane_emitted += int(res["emitted"])
            lane_created += int(res["created"])
            all_trials.extend(res["trials"])
            errors.extend(res["errors"][:2])
        starts[lane] = start + n_done
        emitted += lane_emitted
        created += lane_created
        per_lane[lane] = {"n_parents": len(rows), "parents_this_pass": n_done,
                          "cells_emitted": lane_emitted, "cells_created": lane_created,
                          "cursor": starts[lane]}

    if not dry_run:
        _write(CURSOR, {"at": now, "starts": starts,
                        "rule": ("a cursor per lane, so every certified mechanism and every "
                                 "strong docket family is reached across passes; a parent not "
                                 "reached this pass leads the next one")})

    ledger = charge_trials(all_trials)
    unmeasured = [w for w in (canon_why, docket_why) if w]
    return {
        "at": now,
        "status": "OK" if emitted or dry_run else ("UNMEASURED" if unmeasured else "OK"),
        "charts": charts,
        "chart_order_basis": chart_basis,
        "n_parents_total": sum(len(v) for v in lanes.values()),
        "cells_emitted_this_pass": emitted,
        "cells_created_this_pass": created,
        "per_lane": per_lane,
        "trial_ledger": ledger,
        "unmeasured": unmeasured,
        "errors": errors[:10],
        "dry_run": bool(dry_run),
        "consumers": [
            "libs/moat/registry.py research_candidates -> the one gauntlet claims and judges "
            "every minted chart variant exactly as it judges its parent",
            "desks/mt5/reports/TIMEFRAME_FANOUT.json -> cells per lane per pass and the pass's "
            "n_raw/n_effective, the multiplicity the deflation charge must use",
            "desks/mt5/research/counterfactual_timeframes.py -> supplies the chart order this "
            "organ mints in; nothing is dropped, only ordered",
        ],
        "boundary": ("MINTS ONLY. No rule, parameter, symbol or side is changed; no chart is "
                     "filtered or preferred; nothing is judged, sized or vetoed here. The "
                     "per-pass budget is a wall clock, never a quota."),
        "seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run)
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"timeframe fanout: could not write {OUT}: {exc}")
        return 1
    print(f"timeframe fanout: charts {doc['charts']} over {doc['n_parents_total']} parent(s)")
    print(f"  cells emitted {doc['cells_emitted_this_pass']} "
          f"({doc['cells_created_this_pass']} new)")
    for lane, row in doc["per_lane"].items():
        print(f"   {lane:<20} parents {row['parents_this_pass']}/{row['n_parents']} "
              f"cells {row['cells_emitted']} (new {row['cells_created']})")
    tl_ = doc["trial_ledger"]
    print(f"  trials charged: n_raw {tl_['n_raw']} n_effective {tl_.get('n_effective')} "
          f"inflation {tl_.get('inflation')}")
    for w in doc["unmeasured"]:
        print(f"   UNMEASURED {w[:90]}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
