"""EFFICIENCY REGIME: where the judge finds nothing, as a feature and a stand-down proposal (idea #8).

The judge has ruled on ~1.7M cells (data/hypotheses/gate_verdict_ledger.jsonl). Where a zone --
a symbol, a symbol x session, a symbol x family -- has been judged many times and NOTHING passed,
that is our own measurement that the market there is efficient to every mechanism we know. This
leg turns that failure map into:

  zones     per zone: cells judged (latest verdict per cell), cells passed, the Beta(1+p, 1+f)
            posterior pass rate and its ratio to the desk's base rate (`efficiency`, the regime
            feature: 1.0 = as fertile as the desk average, 0 = barren).
  dead      a zone is DEAD when it has zero passes AND enough judged cells that zero passes would
            happen with < DEAD_ALPHA probability at the desk's base rate:
            n >= ln(DEAD_ALPHA) / ln(1 - p0). Fewer cells than that is UNMEASURED, never dead.
  proposal  every sleeve (forward clocks in reports/shadow/*.json, and live_ledger sleeves) whose
            zone is DEAD, as STAND_DOWN_PROPOSED. A proposal only: the allocator stays sovereign
            over sizing and nothing reads this to size (report_only, consumer null).
  test      E[log W] with and without the proposed stand-downs, on the trades the live ledger
            actually took (data/live_ledger.jsonl: r_multiple x risk_frac, summed log per day). The
            filter earns a consumer only if `without` beats `with` on the measured trades; a
            negative delta is published as the missed growth the filter would cost (Rule 1).

Box-local inputs (the ledger is 0.5 GB and gitignored); off the box every block reads UNMEASURED.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
SHADOW_DIR = BASE / "reports" / "shadow"
OUT = BASE / "reports" / "EFFICIENCY_REGIME.json"

#: P(zero passes | the zone is as fertile as the desk) below which zero passes reads DEAD.
DEAD_ALPHA = 0.05
#: Never call a zone dead on fewer cells than this, whatever the base rate says.
MIN_DEAD_N = 30
#: A live row with no risk fraction is valued at this fraction (the venue's typical per-trade risk).
DEFAULT_RISK_FRAC = 0.005
TOP_K = 200
INTENDED_CONSUMER = "allocator regime input / sleeve stand-down filter, only if the test is positive"
SESSION_TOKENS = frozenset({"asia", "london", "london_am", "afternoon", "ny", "newyork", "us",
                            "eu", "overlap", "close", "open", "pacific", "tokyo", "sydney"})


def parse_cell(cell: str) -> tuple[str, str, str] | None:
    """(symbol, family, session) from a judge cell id; session ANY when the id names none."""
    parts = str(cell or "").split(".")
    if len(parts) < 2 or not parts[0]:
        return None
    sym, fam = parts[0], parts[1].split("@")[0].split("#")[0]
    sess = "ANY"
    for p in parts[2:]:
        tok = p.split("@")[0].split("#")[0].lower()
        if tok in SESSION_TOKENS:
            sess = tok
            break
    return sym, fam, sess


def sleeve_zone(name: str, symbol: str | None = None) -> tuple[str, str]:
    """(symbol, session) for a sleeve name such as `XAUUSD.asia#rr=2.5` or `USDZAR.ogd.asia`."""
    parts = str(name or "").replace("#", ".").split(".")
    sym = symbol or parts[0]
    sess = "ANY"
    for p in parts[1:]:
        tok = p.split("@")[0].lower()
        if tok in SESSION_TOKENS:
            sess = tok
            break
        for s in SESSION_TOKENS:                       # gold_asia, gold_london_am
            if tok.endswith("_" + s) or tok == s:
                sess = s
    return str(sym).upper(), sess


def latest_verdicts(path: Path | None = None) -> dict[str, bool] | None:
    """The newest verdict per cell (the ledger appends once per change of mind)."""
    path = path or LEDGER
    if not path.exists():
        return None
    out: dict[str, bool] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            c = r.get("cell")
            if c:
                out[str(c)] = bool(r.get("passed"))
    return out


def dead_n(p0: float) -> int:
    if p0 <= 0:
        return 10**9                                   # nothing ever passes: no zone is special
    if p0 >= 1:
        return MIN_DEAD_N
    return max(MIN_DEAD_N, math.ceil(math.log(DEAD_ALPHA) / math.log(1.0 - p0)))


def zones(verdicts: dict[str, bool]) -> dict[str, Any]:
    grains: dict[str, dict[tuple[str, ...], list[int]]] = {
        "symbol": defaultdict(lambda: [0, 0]), "symbol_session": defaultdict(lambda: [0, 0]),
        "symbol_family": defaultdict(lambda: [0, 0])}
    tot = [0, 0]
    for cell, ok in verdicts.items():
        pc = parse_cell(cell)
        if pc is None:
            continue
        sym, fam, sess = pc
        for g, key in (("symbol", (sym,)), ("symbol_session", (sym, sess)),
                       ("symbol_family", (sym, fam))):
            grains[g][key][0] += 1
            grains[g][key][1] += int(ok)
        tot[0] += 1
        tot[1] += int(ok)
    p0 = tot[1] / tot[0] if tot[0] else 0.0
    nd = dead_n(p0)
    out: dict[str, Any] = {"cells": tot[0], "passed": tot[1], "base_rate": round(p0, 6),
                           "dead_min_cells": nd, "grains": {}}
    for g, tab in grains.items():
        rows = []
        for key, (n, k) in tab.items():
            post = (1 + k) / (2 + n)
            state = ("DEAD" if k == 0 and n >= nd else
                     "UNMEASURED" if k == 0 else "FERTILE")
            rows.append({"zone": ".".join(key), "n": n, "passed": k,
                         "efficiency": round(post / p0, 4) if p0 > 0 else None, "state": state})
        rows.sort(key=lambda r: (r["state"] != "DEAD", -r["n"]))
        out["grains"][g] = {"n_zones": len(rows),
                            "n_dead": sum(r["state"] == "DEAD" for r in rows),
                            "dead": [r["zone"] for r in rows if r["state"] == "DEAD"],
                            "top": rows[:TOP_K]}
    out["feature"] = {r["zone"]: r["efficiency"]
                      for r in sorted(_all(grains["symbol_session"], p0), key=lambda r: r["zone"])}
    return out


def _all(tab: dict[tuple[str, ...], list[int]], p0: float) -> list[dict[str, Any]]:
    return [{"zone": ".".join(k), "efficiency": (round(((1 + v[1]) / (2 + v[0])) / p0, 4)
                                                 if p0 > 0 else None)} for k, v in tab.items()]


def is_dead(z: dict[str, Any], sym: str, sess: str) -> bool:
    dead = set(z["grains"]["symbol_session"]["dead"]) | set(z["grains"]["symbol"]["dead"])
    return f"{sym}.{sess}" in dead or sym in dead


def forward_sleeves() -> list[dict[str, Any]]:
    out = []
    for p in sorted(SHADOW_DIR.glob("*shadow_state.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            if isinstance(v, dict) and "n" in v and "cum_r" in v:
                out.append({"sleeve": k, "clock": p.name, "n": v.get("n"),
                            "exp_r": v.get("exp_r"), "status": v.get("status")})
    return out


def live_trades(path: Path | None = None) -> list[dict[str, Any]] | None:
    path = path or LIVE_LEDGER
    if not path.exists():
        return None
    rows = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            rm = r.get("r_multiple")
            if isinstance(rm, (int, float)) and math.isfinite(rm) and r.get("entry_time"):
                rows.append(r)
    return rows


def elog_test(z: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, Any]:
    days_all: dict[str, float] = defaultdict(float)
    days_kept: dict[str, float] = defaultdict(float)
    removed = 0
    for r in trades:
        f = r.get("risk_frac")
        f = float(f) if isinstance(f, (int, float)) and 0 < f < 1 else DEFAULT_RISK_FRAC
        g = math.log(max(1e-9, 1.0 + f * float(r["r_multiple"])))
        day = str(r["entry_time"])[:10]
        days_all[day] += g
        sym, sess = sleeve_zone(str(r.get("sleeve") or ""), r.get("symbol"))
        if is_dead(z, sym, sess):
            removed += 1
        else:
            days_kept[day] += g
    if not days_all:
        return {"status": "UNMEASURED", "why": "no closed live trade with an r_multiple"}
    nd = len(days_all)
    w = sum(days_all.values()) / nd
    wo = sum(days_kept.get(d, 0.0) for d in days_all) / nd
    return {"status": "MEASURED", "n_trades": len(trades), "n_removed": removed, "n_days": nd,
            "elog_per_day_with": round(w, 7), "elog_per_day_without": round(wo, 7),
            "delta": round(wo - w, 7),
            "verdict": ("FILTER_HELPS" if wo > w else
                        "NO_EFFECT" if removed == 0 else "FILTER_COSTS_GROWTH")}


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    doc: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "report_only": True, "consumer": None,
                           "intended_consumer": INTENDED_CONSUMER,
                           "regime_axis": ("hour enters through the session named in the cell id; "
                                           "parameter regimes are hashed in the id and are not "
                                           "separable here")}
    v = latest_verdicts()
    if v is None:
        doc.update(status="UNMEASURED", why="gate verdict ledger absent on this host",
                   n_dead_zones=0)
        return doc
    z = zones(v)
    doc["zones"] = z
    fwd = forward_sleeves()
    prop = [dict(s, zone=".".join(sleeve_zone(s["sleeve"])),
                 proposal="STAND_DOWN_PROPOSED")
            for s in fwd if is_dead(z, *sleeve_zone(s["sleeve"]))]
    doc["forward_sleeves"] = len(fwd)
    doc["proposal"] = prop
    trades = live_trades()
    doc["test"] = (elog_test(z, trades) if trades is not None else
                   {"status": "UNMEASURED", "why": "live ledger absent on this host"})
    doc["n_dead_zones"] = sum(g["n_dead"] for g in z["grains"].values())
    doc["status"] = "OK"
    return doc


def write(doc: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="efficiency regime from the judge's failure map").parse_args(argv)
    doc = build()
    write(doc)
    t = (doc.get("test") or {})
    print(f"efficiency_regime: {doc['status']} dead_zones={doc.get('n_dead_zones')} "
          f"proposals={len(doc.get('proposal') or [])} test={t.get('verdict') or t.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
