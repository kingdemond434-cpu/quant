#!/usr/bin/env python3
"""COST SURFACES -- the whole round trip, keyed by where, when, how big, how wild, which way, how.

    key   = instrument x session x size bucket x volatility bucket x direction x order type
    terms = spread, commission, swap, slippage, latency, fill probability, adverse selection

WHAT EXISTED, AND WHY IT WAS NOT THIS. The desk's cost model is a SPREAD x HOUR surface
(`cost_surface.py` -> `data/cost_surface.json`, from the bars' own spread column). It is dense
and it is one term. The terms a live order actually pays were each measured somewhere else and
never joined: commission and swap per deal in `live_ledger.jsonl`, requested-versus-filled
slippage, latency and the quote at decision in `fill_corpus.jsonl` (written by
`fill_recorder.py`), fill/no-fill per intent in the same corpus (`fill_attribution.py` reads it),
and post-fill markouts in its `markout_*_r` columns. Nothing answered "what does a 0.3-lot short
stop order on EURGBP in the London session, on a high-vol day, cost in total?" This does.

MEASURED WHERE THERE ARE FILLS, UNMEASURED WHERE THERE ARE NOT (L1.28a). A term carries a value
only when at least `MIN_N` real observations sit in its cell. Below that the term is
`UNMEASURED` with its n, never zero -- a zero cost is the number that manufactures survivors.
`cost_for()` then backs off (drop order type and vol/size, then the session, then everything
but the instrument), and for SPREAD alone falls to the documented PRIOR: the symbol's own
spread x hour model, the session median of its measured hourly p50s, then the registry's pooled
`median_spread_pts`. Every answer names the level it came from.

PUBLISH ONLY. Nothing here changes what the gauntlet (`external_gauntlet.costs_for`, sealed),
the engine or the gateway charges. The artifact lists each consumer that SHOULD adopt
`cost_for()` and marks it NOT_ADOPTED until that consumer's own change lands -- the adoption is
a separate, reviewable act, and for the sealed judge it needs the principal's re-sign.

KNOWN LIMITATION, stated: the corpus records `hour` in UTC while the prior's hours are the bar
tape's broker clock (UTC+2/+3). Sessions are four wide phases so a 2-3 h skew moves at most the
boundary hours; the artifact carries the note so no consumer mistakes it for exact.

    python desks/mt5/research/cost_surfaces.py --once
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
CORPUS = DATA / "fill_corpus.jsonl"
LEDGER = DATA / "live_ledger.jsonl"
PRIOR = DATA / "cost_surface.json"
UNIVERSE = DATA / "universe" / "universe.json"
OUT = DESK / "reports" / "COST_SURFACES.json"

SCHEMA = "cost-surfaces-1"
#: Observations a term needs in a cell before it may carry a number.
MIN_N = 3
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
#: The four trading phases the desk names everywhere else (cost_surface._PHASES).
PHASES = ((0, 7, "asia"), (7, 12, "london"), (12, 17, "ny"), (17, 24, "late"))
TERMS = ("spread_points", "commission_r", "swap_r", "slippage_points", "slippage_r",
         "latency_ms", "fill_probability", "reject_rate", "adverse_selection_r")
#: Backoff: which key fields each level keeps (the rest become "*").
LEVELS = (
    ("exact", ("instrument", "session", "size", "vol", "direction", "order_type")),
    ("instrument_session_direction_order", ("instrument", "session", "direction", "order_type")),
    ("instrument_session", ("instrument", "session")),
    ("instrument", ("instrument",)),
)
KEY_FIELDS = LEVELS[0][1]

#: Who should read `cost_for()` instead of today's spread-only charge. Recorded, not changed.
CONSUMERS = (
    {"consumer": "desks/mt5/scripts/external_gauntlet.py:costs_for",
     "today": "one pooled median_spread_pts per symbol x mult; no hour, size, side or order type",
     "adopt": "add slippage_r + commission_r + swap_r for the cell's session and order type",
     "blocker": "IMMUTABLE (scripts/check_immutable_evaluator.py): needs the principal's re-sign"},
    {"consumer": "desks/mt5/mt5desk/engine.py:run_backtest (per_oz_cost)",
     "today": "one per-cell round trip charged identically at every fill",
     "adopt": "price each fill at cost_for(symbol, fill hour, lots, vol, side, order type)",
     "blocker": "changes every judged cell's R; route through the gauntlet's re-sign"},
    {"consumer": "desks/mt5/research/net_edge_spine.py:spread_term",
     "today": "EXECUTION_COST_SURFACE.json (crossing) + FUSION_COST commission",
     "adopt": "read slippage/latency/adverse-selection terms the crossing surface lacks",
     "blocker": "none -- a research reader; adopt when a cell is MEASURED"},
    {"consumer": "desks/mt5/research/pf_allocator.py (cost_r)",
     "today": "modelled cost_r with a world cost-uncertainty draw",
     "adopt": "replace the draw's centre with cost_for totals where MEASURED",
     "blocker": "sizing path: two-sided evidence required (GROWTH_GOVERNANCE Rule 1)"},
    {"consumer": "desks/mt5/mt5desk/gateway.py (order placement)",
     "today": "spread-at-decision recorded, not priced",
     "adopt": "choose order type by cost_for fill_probability x slippage",
     "blocker": "live money path; adopt only after a shadow A/B"},
    {"consumer": "desks/mt5/mt5desk/fill_surface.py",
     "today": "ridge/logistic fit over markout rows, spread-model prior",
     "adopt": "use this surface's MEASURED cells as the fit's grouped target",
     "blocker": "none"},
)


# ------------------------------------------------------------------------------ readers
def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    return out


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _f(v: object) -> float | None:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _hour(stamp: object) -> int | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).hour
    except ValueError:
        return None


# ------------------------------------------------------------------------------ keys
def session_of(hour: int | None) -> str:
    if hour is None:
        return "unknown"
    for lo, hi, name in PHASES:
        if lo <= int(hour) % 24 < hi:
            return name
    return "late"


def order_type_of(raw: object) -> str:
    s = str(raw or "").lower()
    if not s:
        return "unknown"
    if "limit" in s:
        return "limit"
    if "stop" in s:
        return "stop"
    if "market" in s:
        return "market"
    return "unknown"


def direction_of(d: object) -> str:
    x = _f(d)
    if x is None or x == 0:
        return "unknown"
    return "long" if x > 0 else "short"


def tercile_edges(values: Iterable[float | None]) -> list[float]:
    """Bucket edges DERIVED from the desk's own traded values, never a copied ladder.
    Fewer than nine observations evidence no terciles: one bucket."""
    v = sorted(x for x in values if x is not None and x > 0)
    if len(v) < 9:
        return []
    q = statistics.quantiles(v, n=3)
    return [round(q[0], 8), round(q[1], 8)]


def bucket(x: float | None, edges: list[float]) -> str:
    if x is None or x <= 0:
        return "unknown"
    if not edges:
        return "all"
    if x <= edges[0]:
        return "low"
    if x <= edges[1]:
        return "mid"
    return "high"


# ------------------------------------------------------------------------------ observations
def _risk_account(row: dict[str, Any], meta: dict[str, Any]) -> float | None:
    """A deal's risk in account currency: stop distance / tick_size x tick_value x lots."""
    entry, sl, vol = _f(row.get("entry_price")), _f(row.get("sl")), _f(row.get("volume"))
    m = meta.get(str(row.get("symbol") or "")) or {}
    ts, tv = _f(m.get("tick_size")), _f(m.get("tick_value"))
    if entry is None or not sl or not vol or vol <= 0 or not ts or not tv or ts <= 0 or tv <= 0:
        return None
    risk = abs(entry - sl) / ts * tv * vol
    return risk if risk > 0 else None


def corpus_obs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One observation per intent in the fill corpus (spread, slip, latency, fill, markout)."""
    out = []
    for r in rows:
        status = str(r.get("status") or "").upper()
        point = _f(r.get("point"))
        spread = _f(r.get("spread_points_at_decision"))
        if spread is None:
            sf, mid = _f(r.get("spread_frac_at_decision")), _f(r.get("quote_mid_at_decision"))
            if sf is not None and mid and point:
                spread = sf * mid / point
        lat_parts = [_f(r.get("latency_decision_to_send_ms")), _f(r.get("latency_send_to_ack_ms")),
                     _f(r.get("latency_ack_to_fill_ms"))]
        lat = sum(x for x in lat_parts if x is not None) if any(
            x is not None for x in lat_parts) else None
        mk = _f(r.get("markout_5m_r"))
        if mk is None:
            mk = _f(r.get("markout_30s_r"))
        if mk is None:
            mk = _f(r.get("markout_5s_r"))
        hour = r.get("hour")
        hour = int(hour) if isinstance(hour, int | float) else _hour(
            r.get("filled_at") or r.get("decided_at"))
        vol = _f(r.get("vol_frac"))
        if vol is None:
            vol = _f(r.get("stop_frac"))
        out.append({
            "source": "fill_corpus",
            "instrument": str(r.get("symbol") or ""), "hour": hour,
            "lots": _f(r.get("lots")), "volx": vol,
            "direction": direction_of(r.get("direction")),
            "order_type": order_type_of(r.get("order_type") or r.get("execution_style")),
            "filled": status == "FILLED", "unfilled": status == "UNFILLED",
            "rejected": status == "REJECTED" or bool(r.get("rejected")),
            "spread_points": spread,
            "slippage_points": _f(r.get("slip_points")) if status == "FILLED" else None,
            "slippage_r": _f(r.get("slip_r")) if status == "FILLED" else None,
            "latency_ms": lat,
            "adverse_selection_r": (-mk if mk is not None else None),
        })
    return out


def ledger_obs(rows: list[dict[str, Any]], meta: dict[str, Any],
               entry_types: dict[str, str]) -> list[dict[str, Any]]:
    """One observation per closed deal: commission and swap in R (the ledger's own currency)."""
    out = []
    for r in rows:
        risk = _risk_account(r, meta)
        entry, sl = _f(r.get("entry_price")), _f(r.get("sl"))
        direction = ("unknown" if entry is None or not sl or sl == entry
                     else ("long" if sl < entry else "short"))
        comm, swap = _f(r.get("commission")), _f(r.get("swap"))
        eo = str(r.get("entry_order") or "")
        out.append({
            "source": "live_ledger",
            "instrument": str(r.get("symbol") or ""), "hour": _hour(r.get("time")),
            "lots": _f(r.get("volume")),
            "volx": (abs(entry - sl) / entry if entry and sl else None),
            "direction": direction,
            "order_type": entry_types.get(eo, "unknown"),
            # Commission and swap are COSTS; the ledger books them negative. Positive R = paid.
            "commission_r": (-comm / risk) if (comm is not None and risk) else None,
            "swap_r": (-swap / risk) if (swap is not None and risk) else None,
        })
    return out


# ------------------------------------------------------------------------------ the surface
def _term(values: list[float]) -> dict[str, Any]:
    if len(values) < MIN_N:
        return {"status": UNMEASURED, "n": len(values)}
    vs = sorted(values)
    p90 = vs[min(len(vs) - 1, int(math.ceil(0.9 * len(vs))) - 1)]
    return {"status": MEASURED, "n": len(vs), "value": round(statistics.median(vs), 6) + 0.0,
            "mean": round(statistics.fmean(vs), 6) + 0.0, "p90": round(p90, 6) + 0.0}


def _cell_terms(obs: list[dict[str, Any]]) -> dict[str, Any]:
    terms: dict[str, Any] = {}
    for t in ("spread_points", "commission_r", "swap_r", "slippage_points", "slippage_r",
              "latency_ms", "adverse_selection_r"):
        terms[t] = _term([o[t] for o in obs if o.get(t) is not None])
    corp = [o for o in obs if o["source"] == "fill_corpus"]
    decided = [o for o in corp if o["filled"] or o["unfilled"]]
    if len(decided) < MIN_N:
        terms["fill_probability"] = {"status": UNMEASURED, "n": len(decided)}
    else:
        terms["fill_probability"] = {"status": MEASURED, "n": len(decided), "value": round(
            sum(o["filled"] for o in decided) / len(decided), 4)}
    resolved = [o for o in corp if o["filled"] or o["unfilled"] or o["rejected"]]
    if len(resolved) < MIN_N:
        terms["reject_rate"] = {"status": UNMEASURED, "n": len(resolved)}
    else:
        terms["reject_rate"] = {"status": MEASURED, "n": len(resolved), "value": round(
            sum(o["rejected"] for o in resolved) / len(resolved), 4)}
    return terms


def _key(o: dict[str, Any], keep: tuple[str, ...]) -> str:
    return "|".join(str(o[f]) if f in keep else "*" for f in KEY_FIELDS)


def prior_spread(prior: dict[str, Any], universe: dict[str, Any], instrument: str,
                 session: str) -> dict[str, Any]:
    """THE DOCUMENTED PRIOR: today's spread x hour model, collapsed to the session."""
    sym = (prior.get("symbols") or {}).get(instrument) or {}
    hours = sym.get("hours") or {}
    p50s = [float(c["p50"]) for h, c in hours.items()
            if isinstance(c, dict) and c.get("status") == MEASURED and c.get("p50") is not None
            and session_of(int(h)) == session]
    if p50s:
        return {"status": "PRIOR", "value": round(statistics.median(p50s), 4),
                "basis": "cost_surface.json session median of hourly p50 (spread x hour model)",
                "n_hours": len(p50s)}
    pooled = _f(sym.get("pooled_median_spread_pts"))
    if pooled is None:
        pooled = _f((universe.get(instrument) or {}).get("median_spread_pts"))
    if pooled is not None and pooled > 0:
        return {"status": "PRIOR", "value": pooled,
                "basis": "universe.json pooled median_spread_pts (no measured hour this session)"}
    return {"status": UNMEASURED, "basis": "no measured hour and no positive pooled spread"}


def build(corpus: list[dict[str, Any]] | None = None, ledger: list[dict[str, Any]] | None = None,
          prior: dict[str, Any] | None = None,
          universe: dict[str, Any] | None = None) -> dict[str, Any]:
    corpus = _jsonl(CORPUS) if corpus is None else corpus
    ledger = _jsonl(LEDGER) if ledger is None else ledger
    prior = _json(PRIOR) if prior is None else prior
    universe = _json(UNIVERSE) if universe is None else universe
    entry_types = {str(r.get("ticket")): order_type_of(r.get("order_type"))
                   for r in corpus if r.get("ticket") is not None}
    obs = corpus_obs(corpus) + ledger_obs(ledger, universe, entry_types)
    obs = [o for o in obs if o["instrument"]]
    size_edges = tercile_edges(o["lots"] for o in obs)
    vol_edges = tercile_edges(o["volx"] for o in obs)
    for o in obs:
        o["session"] = session_of(o["hour"])
        o["size"] = bucket(o["lots"], size_edges)
        o["vol"] = bucket(o["volx"], vol_edges)
    levels: dict[str, dict[str, Any]] = {}
    for name, keep in LEVELS:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for o in obs:
            groups[_key(o, keep)].append(o)
        levels[name] = {k: {"n_obs": len(v), "terms": _cell_terms(v)}
                        for k, v in sorted(groups.items())}
    instruments = sorted(set((prior.get("symbols") or {})) | set(universe)
                         | {o["instrument"] for o in obs})
    traded = {o["instrument"] for o in obs}
    priors = {sym: {s: prior_spread(prior, universe, sym, s) for _, _, s in PHASES}
              for sym in instruments if not sym.startswith("_")}
    n_measured = sum(1 for c in levels["exact"].values()
                     for t in c["terms"].values() if t["status"] == MEASURED)
    return {
        "schema": SCHEMA,
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "key": list(KEY_FIELDS), "terms": list(TERMS), "min_n": MIN_N,
        "sessions": {name: [lo, hi] for lo, hi, name in PHASES},
        "size_bucket_edges_lots": size_edges, "vol_bucket_edges_frac": vol_edges,
        "vol_basis": "fill_corpus vol_frac, else the order's own stop distance / price",
        "sources": {"fill_corpus": str(CORPUS.relative_to(DESK.parent.parent)),
                    "live_ledger": str(LEDGER.relative_to(DESK.parent.parent)),
                    "prior": str(PRIOR.relative_to(DESK.parent.parent))},
        "n_obs": {"fill_corpus": sum(o["source"] == "fill_corpus" for o in obs),
                  "live_ledger": sum(o["source"] == "live_ledger" for o in obs)},
        "n_cells": len(levels["exact"]), "n_measured_terms_exact": n_measured,
        "instruments_traded": len(traded),
        "instruments_unmeasured": sum(1 for s in priors if s not in traded),
        "status": MEASURED if n_measured else UNMEASURED,
        "levels": levels,
        "priors": priors,
        "adoption": [dict(c, status="NOT_ADOPTED") for c in CONSUMERS],
        "limitations": ["corpus hours are UTC, prior hours are the broker tape clock (+2/+3 h)",
                        "a term below min_n is UNMEASURED and carries no value, never zero"],
    }


# ------------------------------------------------------------------------------ the API
_CACHE: dict[str, Any] = {}


def load(path: Path | None = None) -> dict[str, Any]:
    p = OUT if path is None else path
    key = str(p)
    if key not in _CACHE:
        _CACHE[key] = _json(p)
    return _CACHE[key]


def cost_for(instrument: str, *, hour: int | None = None, session: str | None = None,
             lots: float | None = None, vol_frac: float | None = None,
             direction: int | str | None = None, order_type: str | None = None,
             surface: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every cost term for one order, each with its status and the level it came from.

    Walks exact -> coarser cells; a term takes the FIRST level where it is MEASURED. SPREAD with
    no measured level takes the PRIOR (spread x hour model). Any other term with no measured
    level is UNMEASURED -- never zero. Reads nothing but the published artifact."""
    s = load() if surface is None else surface
    sess = session or session_of(hour)
    d = direction if isinstance(direction, str) else direction_of(direction)
    o = {"instrument": instrument, "session": sess,
         "size": bucket(lots, list(s.get("size_bucket_edges_lots") or [])),
         "vol": bucket(vol_frac, list(s.get("vol_bucket_edges_frac") or [])),
         "direction": d, "order_type": order_type_of(order_type)}
    levels = s.get("levels") or {}
    out: dict[str, Any] = {"key": o, "terms": {}}
    for term in TERMS:
        found = None
        for name, keep in LEVELS:
            cell = (levels.get(name) or {}).get(_key(o, keep))
            t = ((cell or {}).get("terms") or {}).get(term) or {}
            if t.get("status") == MEASURED:
                found = dict(t, level=name)
                break
        if found is None and term == "spread_points":
            pri = ((s.get("priors") or {}).get(instrument) or {}).get(sess)
            if pri and pri.get("status") == "PRIOR":
                found = dict(pri, level="prior")
        out["terms"][term] = found or {"status": UNMEASURED, "level": "none"}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=60.0)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), "utf-8")
    tmp.replace(args.out)
    print(f"cost_surfaces: {doc['status']} cells={doc['n_cells']} "
          f"measured_terms={doc['n_measured_terms_exact']} obs={doc['n_obs']} "
          f"traded={doc['instruments_traded']} unmeasured_instruments="
          f"{doc['instruments_unmeasured']} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
