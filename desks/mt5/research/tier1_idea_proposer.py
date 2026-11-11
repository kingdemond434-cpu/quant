"""Mint, screen and donate the Tier-1 idea cells (U1-U6, N1), so each idea is judged, not filed.

    python desks/mt5/research/tier1_idea_proposer.py --once --budget-s 600
    python desks/mt5/research/tier1_idea_proposer.py --once --force       # ignore the refresh

THE IDEAS (zuck, 2026-11-11, backlog rows U1-U6 and N1):

    U1 intraday_momentum      first window -> last window, US/EU/JP indices, gold, silver, oil
    U2 overnight_day_tug      night leg vs day leg disagree, index CFDs
    U3 implied_realised_gap   GVZ / OVX (FRED) against realised vol, gold and oil
    U4 weekend_crypto_gap     BTC/ETH CFD weekend move -> Monday session, JPY, AUD, gold, indices
    U5 equity_gap_breadth     US share-CFD opening-gap breadth -> US indices
    U6 world_macro_state      Kim-Wright 10y term premium (FRED THREEFYTP10): gold, JPY, bonds
                              -- PARKED until a first-release vintage exists (see U6_PARK)
    N1 holiday_drift          pre- and post-holiday sessions, by each index's own venue calendar

N2 (degree days) and N3 (net liquidity) are World sensor's (#903, #904) and are not minted here.

SAME CONTRACT AS EVERY PROPOSER (`proposer_common`). Each cell is run on the desk's own bars,
scored on its forward return at its own hold net of the round trip, deflated by EVERY cell this
pass tried, and only the best variant per cell that clears is donated to
`data/intelligence/tier1_ideas/`, where `miner_candidate_compiler` admits it as EXACT_RECIPE and
the gauntlet judges it under the program-wide trial charge. The screen certifies nothing.

CADENCE IS MULTIPLICITY. The grid is fixed, so re-running it every hour against the same bars
would re-donate the same survivors and re-roll nothing new. A full pass runs at most once per
REFRESH_H; the hourly leg in between writes the report with `status: FRESH` and the age, so the
leg is visibly alive without spending a new sweep. An idea whose input is absent (a FRED series
the world dataset hunter has not stored yet, a symbol with no bars on this box) is PARKED by
name with the reason, never counted as zero.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_tier1_ideas as t1  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "tier1_ideas"
LEG = "tier1_idea_proposer"
REPORT = _DESK / "reports" / "TIER1_IDEA_PROPOSER.json"
REFRESH_H = 20.0
DEFAULT_BUDGET_S = 600.0

US_INDICES = ("US500", "US30", "NAS100", "US2000")

#: U6 IS PARKED ON A POINT-IN-TIME DEFECT, NOT ON DATA. The world dataset hunter stamps a
#: series' backfilled history at period end + publication lag (`world_dataset_hunter.pit_series`),
#: and fredgraph.csv serves the CURRENT vintage. GVZ and OVX are market closes that are never
#: revised, so U3 is unaffected; THREEFYTP10 is a model estimate the Fed re-fits, so its history
#: carries revisions the desk could not have known. It is minted when a first-release vintage
#: source exists (ALFRED, Global data's FRED axis #761). Set to "" to mint it.
U6_PARK = ("THREEFYTP10 history is the current vintage stamped at its observation date "
           "(revised model output): waits for first-release vintages")


def _session(sym: str) -> dict[str, str]:
    tz, o, c, _cal = t1.SESSIONS[sym]
    return {"tz": tz, "open_at": o, "close_at": c}


def ideas() -> list[dict[str, Any]]:
    """The declared search: per idea, its family, targets and the grid charged per target."""
    eq_sessions = [s for s, v in t1.SESSIONS.items() if not s.startswith("X")]
    return [
        {"id": "U1", "family": "intraday_momentum", "targets": sorted(t1.SESSIONS),
         "fixed": _session, "grid": {"first_min": [30, 60], "last_min": [30, 60],
                                     "min_move_atr": [0.0, 0.5], "direction": ["follow"]}},
        {"id": "U2", "family": "overnight_day_tug", "targets": sorted(eq_sessions),
         "fixed": _session, "grid": {"follow": ["night", "day"], "min_day_atr": [0.5, 1.0]}},
        {"id": "U3", "family": "implied_realised_gap",
         "targets": sorted(s for v in t1.IMPLIED_FOR.values() for s in v),
         "fixed": lambda s: {"implied_series": next(k for k, v in t1.IMPLIED_FOR.items()
                                                    if s in v)},
         "inputs": lambda s: [next(k for k, v in t1.IMPLIED_FOR.items() if s in v)],
         "grid": {"band": [(1.0, 99.0), (-99.0, -1.0)], "direction": ["long", "short"],
                  "hold_bars": [24, 120]}},
        {"id": "U4", "family": "weekend_crypto_gap",
         "targets": ["USDJPY", "AUDUSD", "AUDJPY", "XAUUSD", "NAS100", "US500"],
         "fixed": lambda s: {}, "grid": {"driver_symbol": list(t1.DRIVERS),
                                         "direction": ["follow", "fade"],
                                         "require_gap_disagree": [False, True]}},
        {"id": "U5", "family": "equity_gap_breadth", "targets": list(US_INDICES),
         "fixed": _session, "grid": {"direction": ["follow", "fade"],
                                     "breadth_lo": [0.1, 0.25]}},
        {"id": "U6", "family": "world_macro_state",
         "targets": ["XAUUSD", "USDJPY", "EURUSD", "UST10Y", "UST05Y"],
         "fixed": lambda s: {"series_key": _fred_key("THREEFYTP10"), "z_obs": 250},
         "inputs": lambda s: ["THREEFYTP10"],
         "park": U6_PARK,
         "grid": {"band": [(1.0, 99.0), (-99.0, -1.0)], "direction": ["long", "short"],
                  "hold_bars": [120, 480]}},
        {"id": "N1", "family": "holiday_drift",
         "targets": sorted(s for s, v in t1.SESSIONS.items() if v[3]),
         "fixed": lambda s: {**_session(s), "calendar": t1.SESSIONS[s][3]},
         "grid": {"leg": ["pre", "post"], "direction": ["long", "short"]}},
    ]


def _fred_key(sid: str) -> str:
    from research.world_dataset_hunter import series_key
    return series_key("FRED", sid, sid)


def variants(idea: dict[str, Any], sym: str) -> list[dict[str, Any]]:
    """Every parameter set this idea charges on `sym` (the fixed session keys included)."""
    grid = idea["grid"]
    keys = list(grid)
    out = []
    for combo in itertools.product(*(grid[k] for k in keys)):
        p = dict(idea["fixed"](sym))
        for k, v in zip(keys, combo, strict=True):
            if k == "band":
                p["z_lo"], p["z_hi"] = float(v[0]), float(v[1])
            else:
                p[k] = v
        out.append(p)
    return out


def _family(name: str):
    if name == "world_macro_state":
        from mt5desk.family_world_macro import family_world_macro_state
        return family_world_macro_state
    return t1.TIER1_IDEA_FAMILIES[name]


def _missing_inputs(idea: dict[str, Any], sym: str) -> list[str]:
    need = idea.get("inputs")
    if need is None:
        return []
    return [f"FRED {sid} not yet in the world dataset store" for sid in need(sym)
            if t1.fred_series(sid) is None]


def _variant_tag(params: dict[str, Any]) -> str:
    skip = {"tz", "open_at", "close_at", "series_key", "z_obs", "calendar", "implied_series"}
    return ",".join(f"{k}={params[k]}" for k in sorted(params) if k not in skip)


def _prior() -> dict[str, Any]:
    try:
        doc = json.loads(REPORT.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _age_h(prior: dict[str, Any], now: datetime) -> float | None:
    try:
        at = datetime.fromisoformat(str(prior.get("swept_at")))
    except (TypeError, ValueError):
        return None
    if at.tzinfo is None:
        return None
    return (now - at).total_seconds() / 3600.0


def run(*, budget_s: float = DEFAULT_BUDGET_S, force: bool = False, dry_run: bool = False,
        now: datetime | None = None, only: list[str] | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    prior = _prior()
    age = _age_h(prior, now)
    if not force and age is not None and 0 <= age < REFRESH_H:
        doc = {**prior, "status": "FRESH", "checked_at": now.isoformat(),
               "age_h": round(age, 2),
               "rule": f"a full sweep runs at most once per {REFRESH_H:g}h (cadence is "
                       "multiplicity); this pass re-read the last sweep and spent nothing"}
        if not dry_run:
            _write(doc)
        return doc
    started = time.monotonic()
    meta = pc.universe_meta()
    rows: list[dict[str, Any]] = []
    per_idea: dict[str, dict[str, Any]] = {}
    for idea in ideas():
        if only and idea["id"] not in only:
            continue
        rec: dict[str, Any] = {"family": idea["family"], "targets": len(idea["targets"]),
                               "tested": 0, "fired": 0, "parked": {}}
        per_idea[idea["id"]] = rec
        fn = _family(idea["family"])
        for sym in idea["targets"]:
            if idea.get("park"):
                rec["parked"][sym] = str(idea["park"])
                continue
            if time.monotonic() - started > budget_s:
                rec["parked"][sym] = "sweep budget exhausted this pass"
                continue
            missing = _missing_inputs(idea, sym)
            if missing:
                rec["parked"][sym] = "; ".join(missing)
                continue
            d = pc.bars(sym)
            if d is None:
                rec["parked"][sym] = "no H1 bars for this symbol on this box"
                continue
            if len(d) < 24 * 250:
                rec["parked"][sym] = "under 250 days of H1 bars on this box"
                continue
            cost = pc.cost_frac(sym, meta, d["close"])
            if cost is None:
                rec["parked"][sym] = "no contract terms to price the round trip"
                continue
            unfillable = pc.artifact_hours(d)
            for params in variants(idea, sym):
                rec["tested"] += 1
                try:
                    sig = fn(d, **params)
                except Exception as exc:
                    rec["parked"][sym] = f"family raised {type(exc).__name__}: {exc}"[:200]
                    break
                sc = pc.screen(d, sig, cost, unfillable)
                if sc is None:
                    continue
                rec["fired"] += 1
                rows.append({"cell": f"{sym}.{idea['family']}.{idea['id']}", "idea": idea["id"],
                             "symbol": sym, "family": idea["family"], "params": params,
                             "variant": _variant_tag(params), **sc})
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    for r in proposals:
        per_idea[r["idea"]]["proposed"] = per_idea[r["idea"]].get("proposed", 0) + 1
    cands = [pc.candidate(
        SOURCE, r["symbol"], r["family"], dict(r["params"]),
        mechanism=f"Tier-1 idea {r['idea']}: {r['family']} ({r['variant']})",
        title=f"{r['cell']} {r['variant']}",
        evidence={k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                    "cost_frac", "t_gross", "t_deflated_sweep",
                                    "n_tests_sweep")},
    ) for r in proposals]
    for rec in per_idea.values():
        rec["status"] = ("PARKED" if rec["targets"] and len(rec["parked"]) == rec["targets"]
                         else "RAN")
    doc = {"generated_at": now.isoformat(), "swept_at": now.isoformat(), "status": "SWEPT",
           "leg": LEG, "tests_run": len(rows), "cells_proposed": len(proposals),
           "elapsed_s": round(time.monotonic() - started, 1), "ideas": per_idea,
           "proposals": proposals,
           "not_here": {"N2": "degree-day surprise: World sensor, #903 (noaa_forecasts)",
                        "N3": "Fed net liquidity: World sensor, #904 (macro_fair_value)"}}
    if cands and not dry_run:
        doc["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
        doc["donation"] = pc.donation_counts()
    if not dry_run:
        _write(doc)
    return doc


def _write(doc: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(REPORT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--idea", action="append", default=None)
    a = ap.parse_args()
    doc = run(budget_s=a.budget_s, force=a.force, dry_run=a.dry_run, only=a.idea)
    print(f"TIER1 IDEAS  status={doc.get('status')} tests={doc.get('tests_run', 0)} "
          f"proposed={doc.get('cells_proposed', 0)}")
    for k, v in (doc.get("ideas") or {}).items():
        print(f"  {k} {v.get('family'):22s} {v.get('status')} tested={v.get('tested')} "
              f"fired={v.get('fired')} proposed={v.get('proposed', 0)} "
              f"parked={len(v.get('parked') or {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
