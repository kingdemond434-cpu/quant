#!/usr/bin/env python3
"""FILL-HOUR REPRICE: every certificate priced at the spread of the hour it fills, and a shifted
fill tried wherever that hour is a dead book.

WHAT WAS WRONG, measured on the live account 2026-10-07..13. EURZAR and USDZAR overnight gap
decay went LIVE on 10-07 and placed no order in six days. Their signals fired every morning; the
venue refused every send with retcode 10016, and the intents show why:

    USDZAR BUY  intended (ask) 16.26835   tp 16.24435   -> the ask is already PAST the target
    EURZAR BUY  intended (ask) 18.77740   tp 18.74606

The family fills at broker hour 01. There the exotic crosses quote 4-6x their pooled median
(`data/cost_surface.json`: USDZAR p50 1,496 pts against 329 pooled, EURZAR 1,438 against 312),
so the "gap" the family fades is mostly the bid side of a rollover spread, and the target sits
inside the spread. The certificate and the forward clock were priced on the POOLED spread, so on
paper the sleeve made +0.25R and in the market it could never fill. A sleeve that fires and can
never fill is eligible-not-live, which the principal counts as a flaw.

WHAT THIS DOES, once per REFRESH_S on the box (where the bars are):

1. REPRICE. Every certificate is replayed twice through the gauntlet's own `build_cell`: once at
   the pooled scalar (`costs_for`) and once at its own fill hour (the surface spread `build_cell`
   charges when the surface is present), each also at the 2x round-trip stress. A certificate
   whose fill-hour spread exceeds the pooled one by more than REPRICE_RATIO is IN SCOPE, and its
   verdict is NEGATIVE_AT_FILL_HOUR when its fill-hour expectancy is <= 0. EURZAR and USDZAR are
   always in scope. Absence is never clean: no surface, no bars or no fill hour is UNMEASURED.

2. SHIFT THE FILL. For an in-scope certificate of a family that can move its entry
   (SHIFTABLE), child cells enter at the first liquid hour instead: London open (broker 10) and
   the NY overlap (broker 15). They are replayed here as a screen and DONATED to the gauntlet
   through `proposer_common.donate` with `parent_cell` and `trial_family` set to the parent, so
   they are judged as children of one trial family under the Tier S bar, charged once. Whether
   one replaces the dead lane is the gauntlet's verdict, never this module's.

Writes `reports/FILL_HOUR_REPRICE.json`. Exit 1 when a LIVE sleeve's certificate is
NEGATIVE_AT_FILL_HOUR: that is the alarm the allocator and the promoter must act on.

Run:  python desks/mt5/research/fill_hour_reprice.py [--force]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "FILL_HOUR_REPRICE.json"
DONATED = BASE / "data" / "fill_shift_donations.json"
SLEEVES = BASE / "data" / "sleeves.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
#: The certificates' own gate records, read for the cost-stress check (the box's sweep first).
SURVIVOR_FILES = (BASE / "reports" / "UNIVERSAL_SURVIVORS.json",
                  BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json")
SURFACE = BASE / "data" / "cost_surface.json"

#: Fill-hour over pooled spread above which a certificate is repriced (coordinator, 2026-10-13).
REPRICE_RATIO = 1.5
#: Always in scope, whatever their ratio reads: the two sleeves that never filled.
ALWAYS = frozenset({"EURZAR", "USDZAR"})
#: Broker hours of the first liquid books, on the broker's NY+7 clock. The London-NY overlap
#: starts 08:00 New York = broker 15 all year by construction. London opens 08:00 London =
#: broker 10, except in the one or two weeks a year when London and New York change their clocks
#: on different Sundays (it is broker 11 then, and broker 10 is the hour before the open). The
#: surface measures USDZAR p50 154 pts at 10 and 138 at 15, against 1,496 at 01.
SHIFT_HOURS = {"london_open": 10, "ny_overlap": 15}
#: Families whose entry can be moved without changing the signal, and the parameter that moves it.
SHIFTABLE = {"overnight_gap_decay": "entry_hour"}
#: Replays are heavy (bars per symbol, three cost models per certificate); hourly would waste
#: the box. Six hours keeps every certificate repriced four times a day.
REFRESH_S = 6 * 3600
SOURCE = "fill_shift"


def _now() -> datetime:
    return datetime.now(UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def stats(rs: list[float]) -> dict[str, Any]:
    """n, mean R and t of a trade list; UNMEASURED below two trades."""
    n = len(rs)
    if n < 2:
        return {"n": n, "exp_r": (rs[0] if rs else None), "t": None,
                "status": "UNMEASURED: fewer than two trades"}
    mu = sum(rs) / n
    var = sum((r - mu) ** 2 for r in rs) / (n - 1)
    t = mu / math.sqrt(var / n) if var > 0 else None
    return {"n": n, "exp_r": round(mu, 4), "t": (round(t, 3) if t is not None else None),
            "status": "MEASURED"}


def ratio_of(surface: dict[str, Any] | None, meta: dict[str, Any], sym: str,
             hour: int | None) -> tuple[float | None, float | None, float | None]:
    """(fill-hour spread, pooled spread, ratio) in points; None where either side is unknown.

    ONE COST SOURCE (judge thread, #389): when `research.entry_hour_cost` is present the hour
    charge is its `hour_spread_pts` (recency-preferred, thin hours shrunk) and the pooled side is
    the surface's own `pooled_median_spread_pts` (the median of its measured hourly p50s), never
    the registry scalar, which #389 measured as >2x off on 45 symbols. Before #389 lands this
    reads the surface cell and the registry, as it always did."""
    if hour is None:
        return None, None, None
    pooled = None
    try:
        from research.entry_hour_cost import hour_spread_pts  # type: ignore[import-not-found, unused-ignore]
    except ImportError:
        from research.cost_surface import spread_pts
        fill = spread_pts(surface or {}, sym, hour) if surface else None
    else:
        fill = hour_spread_pts(surface, sym, int(hour))[0] if surface else None
        own = (((surface or {}).get("symbols") or {}).get(sym) or {}).get(
            "pooled_median_spread_pts")
        pooled = float(own) if isinstance(own, (int, float)) and own > 0 else None
    if pooled is None:
        pooled = float((meta.get(sym) or {}).get("median_spread_pts") or 0) or None
    r = (fill / pooled) if fill and pooled else None
    return fill, pooled, (round(r, 3) if r is not None else None)


def verdict_of(in_scope: bool, fill: dict[str, Any]) -> str:
    if not in_scope:
        return "OUT_OF_SCOPE"
    if fill.get("status") != "MEASURED":
        return f"UNMEASURED: {fill.get('status')}"
    return "NEGATIVE_AT_FILL_HOUR" if float(fill["exp_r"]) <= 0 else "SURVIVES_FILL_HOUR"


def cost_never_charged(survivors: Any) -> dict[str, dict[str, Any]] | None:
    """Certificates whose 3x cost stress did not lower their expectancy: no cost was ever
    charged, so their EV is a zero-spread number and reads UNMEASURED at real cost.

    Measured 2026-10-13: all 22 certified `discovered` cells and the AUDCHF, CADCHF and GBPCHF
    gap-decay cells have exp_x3 >= ev (the registry priced those pairs at 0-1 point against a
    12-46 point fill-hour book). The discovered family lost -0.14R/trade live against +0.28R
    certified; AUDCHF lost -0.68R over 10 forward trades.

    A certificate missing either number cannot show its cost bit, so it is listed UNMEASURED,
    never passed as clean; a non-positive EV is listed as its own verdict, never dropped. A file
    with no `survivors` map returns None: the caller reads that as UNMEASURED.
    """
    rows = survivors.get("survivors") if isinstance(survivors, dict) else None
    if not isinstance(rows, dict):
        return None
    out: dict[str, dict[str, Any]] = {}
    for key, row in rows.items():
        gates = row.get("gates") if isinstance(row, dict) else None
        if not isinstance(gates, dict):
            out[str(key)] = {"verdict": "UNMEASURED: no gates on the certificate"}
            continue
        ev = (gates.get("expected_value") or {}).get("ev")
        x3 = (gates.get("stress_costs") or {}).get("exp_x3")
        if not isinstance(ev, (int, float)) or not isinstance(x3, (int, float)):
            out[str(key)] = {"ev": ev, "exp_x3": x3,
                             "verdict": "UNMEASURED: ev or exp_x3 missing"}
        elif ev <= 0:
            out[str(key)] = {"ev": float(ev), "exp_x3": float(x3),
                             "verdict": "NON_POSITIVE_EV"}
        elif x3 >= ev:
            out[str(key)] = {"ev": float(ev), "exp_x3": float(x3),
                             "verdict": "COST_NEVER_CHARGED"}
    return out


def roster_certificates() -> dict[str, dict[str, str]]:
    """certificate cell -> {sleeve, status} for every LIVE or STANDBY roster row. A STANDBY row
    is one promoter reading from LIVE, so a cost-never-charged certificate there is flagged too."""
    doc = _read(SLEEVES) or {}
    out: dict[str, dict[str, str]] = {}
    for r in doc.get("sleeves") or []:
        status = str(r.get("status") or "").upper() if isinstance(r, dict) else ""
        if status in ("LIVE", "STANDBY"):
            cert = r.get("certificate")
            cell = str((cert or {}).get("cell") if isinstance(cert, dict) else cert or "")
            if cell and out.get(cell, {}).get("status") != "LIVE":
                out[cell] = {"sleeve": str(r.get("name") or ""), "status": status}
    return out


def charge_check(doc: dict[str, Any]) -> int:
    """Write the cost-never-charged section into `doc`; return how many certificates it flags.

    Runs before every early exit of `run`, so a host with no cost surface or no gauntlet import
    still reports which certificates were never charged a cost."""
    rows = next((r for r in (cost_never_charged(_read(f)) for f in SURVIVOR_FILES)
                 if r is not None), None)
    if rows is None:
        doc["cost_never_charged"] = "UNMEASURED: no survivors map on this host"
        return 0
    roster = roster_certificates()
    doc["cost_never_charged"] = {
        k: {**v, "sleeve": (roster.get(k) or {}).get("sleeve"),
            "roster_status": (roster.get(k) or {}).get("status")}
        for k, v in sorted(rows.items())}
    flagged = 0
    for key, row in doc["cost_never_charged"].items():
        if row["verdict"] != "COST_NEVER_CHARGED":
            continue
        flagged += 1
        if row["roster_status"]:
            doc["alarm"].append({"certificate": key, "sleeve": row["sleeve"],
                                 "roster_status": row["roster_status"],
                                 "why": "3x cost stress did not lower EV: cost never charged"})
    return flagged


def live_certificates() -> dict[str, str]:
    """certificate cell -> LIVE sleeve name, from the roster."""
    doc = _read(SLEEVES) or {}
    out: dict[str, str] = {}
    for r in doc.get("sleeves") or []:
        if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE":
            cert = r.get("certificate")
            cell = str((cert or {}).get("cell") if isinstance(cert, dict) else cert or "")
            if cell:
                out[cell] = str(r.get("name") or "")
    return out


def child_params(parent: dict[str, Any], family: str, hour: int) -> dict[str, Any]:
    return {**parent, SHIFTABLE[family]: int(hour)}


def _replay(eg: Any, sym: str, fam: str, params: dict[str, Any], meta: dict[str, Any]
            ) -> dict[str, Any]:
    """Pooled, fill-hour and 2x fill-hour expectancy of one cell, through the gauntlet's builder."""
    from mt5desk.engine import run_backtest
    cell = eg.build_cell(sym, fam, dict(params), meta)
    if not cell or cell.get("sigs") is None:
        why = getattr(eg, "LAST_BUILD_FAILURE", None) or "build_cell returned no signals"
        return {"status": f"UNMEASURED: {why}"}
    df, sigs = cell["df"], cell["sigs"]
    out: dict[str, Any] = {"fill_hour": cell.get("_fill_hour"),
                           "cost_basis": cell.get("_cost_basis"), "signals": len(sigs)}
    fill_costs = cell["costs"]
    for label, costs in (("at_pooled", eg.costs_for(sym, meta)), ("at_fill_hour", fill_costs),
                         ("at_fill_hour_2x", fill_costs.stressed(2.0))):
        res = run_backtest(df, sigs, costs)
        out[label] = stats([float(t.r_multiple) for t in res.trades])
        out[label]["unfilled"] = len(getattr(res, "geometry_rejections", []) or [])
    if not str(out["cost_basis"] or "").startswith("fill_hour"):
        # The builder fell back to the pooled scalar: there is no fill-hour price to compare.
        out["at_fill_hour"] = {"status": f"UNMEASURED: cost basis {out['cost_basis']}"}
        out["at_fill_hour_2x"] = dict(out["at_fill_hour"])
    return out


def run(force: bool = False) -> int:
    prev = _read(OUT) or {}
    try:
        age = (_now() - datetime.fromisoformat(str(prev.get("generated_at")))).total_seconds()
    except (TypeError, ValueError):
        age = None
    if not force and age is not None and 0 <= age < REFRESH_S:
        print(f"fill_hour_reprice: fresh ({age / 3600:.1f}h old); next pass after "
              f"{REFRESH_S / 3600:.0f}h")
        return 1 if prev.get("alarm") else 0

    doc: dict[str, Any] = {"generated_at": _now().isoformat(), "reprice_ratio": REPRICE_RATIO,
                           "shift_hours": SHIFT_HOURS, "certificates": {}, "children": {},
                           "alarm": [], "donated": 0}
    n_unbitten = charge_check(doc)
    meta = _read(UNIVERSE)
    surface = _read(SURFACE)
    if not isinstance(meta, dict) or not isinstance(surface, dict):
        doc["status"] = ("UNMEASURED: " + ("no universe registry" if not isinstance(meta, dict)
                                           else "no cost surface") + " on this host")
        OUT.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"fill_hour_reprice: {doc['status']}")
        return 1 if doc["alarm"] else 0
    try:
        import external_gauntlet as eg  # type: ignore[import-not-found]

        from research.portfolio_gap import load_survivors
    except Exception as exc:                          # pragma: no cover - box path only
        doc["status"] = f"UNMEASURED: import failed ({type(exc).__name__}: {exc})"
        OUT.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"fill_hour_reprice: {doc['status']}")
        return 1 if doc["alarm"] else 0

    live = live_certificates()
    donated = _read(DONATED) or {}
    candidates: list[dict[str, Any]] = []
    for sv in load_survivors():
        key, sym, fam = str(sv.get("key") or ""), str(sv.get("symbol") or ""), \
            str(sv.get("family") or "")
        if not key or not sym or not fam or key in doc["certificates"]:
            continue
        params = dict(sv.get("params") or {})
        try:
            rep = _replay(eg, sym, fam, params, meta)
        except Exception as exc:
            rep = {"status": f"UNMEASURED: {type(exc).__name__}: {exc}"}
        hour = rep.get("fill_hour")
        fill_pts, pooled_pts, ratio = ratio_of(surface, meta, sym, hour)
        in_scope = sym.upper() in ALWAYS or (ratio is not None and ratio > REPRICE_RATIO)
        row = {"symbol": sym, "family": fam, "params": params, "fill_hour": hour,
               "spread_fill_pts": fill_pts, "spread_pooled_pts": pooled_pts, "ratio": ratio,
               "in_scope": in_scope, "live_sleeve": live.get(key), **rep}
        row["verdict"] = verdict_of(in_scope,
                                    rep.get("at_fill_hour") or {"status": rep.get("status")})
        doc["certificates"][key] = row
        if row["verdict"] == "NEGATIVE_AT_FILL_HOUR" and live.get(key):
            doc["alarm"].append({"certificate": key, "sleeve": live[key],
                                 "exp_r_fill_hour": rep["at_fill_hour"]["exp_r"]})
        if not in_scope or fam not in SHIFTABLE:
            continue
        for label, h in SHIFT_HOURS.items():
            cp = child_params(params, fam, h)
            ckey = f"{key}|{SHIFTABLE[fam]}={h}"
            try:
                crep = _replay(eg, sym, fam, cp, meta)
            except Exception as exc:
                crep = {"status": f"UNMEASURED: {type(exc).__name__}: {exc}"}
            doc["children"][ckey] = {"parent": key, "shift": label, "symbol": sym,
                                     "family": fam, "params": cp, **crep}
            if ckey in donated:
                continue
            candidates.append({"key": ckey, "symbol": sym, "family": fam, "params": cp,
                               "parent": key, "label": label, "hour": h,
                               "screen": (crep.get("at_fill_hour") or {}).get("exp_r")})
    if candidates:
        doc["donated"] = donate(candidates, donated)
    n_neg = sum(1 for r in doc["certificates"].values()
                if r["verdict"] == "NEGATIVE_AT_FILL_HOUR")
    n_scope = sum(1 for r in doc["certificates"].values() if r["in_scope"])
    doc["status"] = "ALARM" if doc["alarm"] else "OK"
    doc["summary"] = {"certificates": len(doc["certificates"]), "in_scope": n_scope,
                      "negative_at_fill_hour": n_neg, "children": len(doc["children"]),
                      "live_negative": sum(1 for a in doc["alarm"] if "why" not in a),
                      "cost_never_charged": n_unbitten}
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"fill_hour_reprice: {len(doc['certificates'])} certificates, {n_scope} in scope, "
          f"{n_neg} negative at their fill hour, {len(doc['alarm'])} of them LIVE; "
          f"{len(doc['children'])} shifted-fill children, {doc['donated']} donated")
    return 1 if doc["alarm"] else 0


def donate(cands: list[dict[str, Any]], ledger: dict[str, Any]) -> int:
    """Hand the children to the gauntlet as members of their parent's trial family."""
    import proposer_common as pc  # type: ignore[import-not-found]
    rows = []
    for c in cands:
        row = pc.candidate(
            SOURCE, c["symbol"], c["family"], c["params"], "overnight_liquidity_shift",
            f"shifted fill [{c['label']}] {c['family']} on {c['symbol']} (child of {c['parent']})",
            {"parent_cell": c["parent"], "trial_family": c["parent"], "kind_of_move": "fill_shift",
             "variant": c["label"], "fill_hour": c["hour"], "screen_exp_r": c["screen"],
             "why": ("the parent fills in a dead book where the spread exceeds its target; the "
                     "child enters at the first liquid hour of the same day")})
        row.update({"kind": "hypothesis", "symbols": [c["symbol"]]})
        rows.append(row)
    pc.donate(SOURCE, rows, tests_run=len(rows))
    n = int(pc.donation_counts().get("donated") or 0)
    if n == len(rows):
        stamp = _now().isoformat()
        for c in cands:
            ledger[c["key"]] = stamp
        DONATED.write_text(json.dumps(ledger, indent=1, sort_keys=True), "utf-8")
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--force", action="store_true", help="ignore the refresh interval")
    return run(force=ap.parse_args(argv).force)


if __name__ == "__main__":
    raise SystemExit(main())
