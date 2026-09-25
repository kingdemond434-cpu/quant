"""THE SHORTFALL MODEL, RE-FITTED FROM REALISED FILLS -- execution priced on the desk's own tape.

THE GAP THE LEDGER NAMED (Tier-1 B22): *"order type and delay are scored at decision time; the
shortfall model is never re-fitted from realised fills."* `execution_policy.plans()` prices every
order plan against `FillSurface.expected_slip`, whose prior is HALF THE SPREAD -- a number nobody
measured, applied to every symbol, hour and size equally. `execution_twin` publishes a
recalibration block and says so in its own artifact: *"NOT WIRED -- the report is advisory until a
consumer reads it."*

THE JOIN IS THE MISSING LINK, and it is why the twin's slip columns are empty. `order_intents.jsonl`
records the price the desk INTENDED at decision time and the ticket it sent; `live_ledger.jsonl`
records the deals that came back, keyed by `entry_order` / `order` / `position_id`. The twin joined
on neither, so 92 cases carried `join_key: none` and `actual_slip_frac: null` while 151 deals sat
on disk. This joins them on the ticket and measures, per fill:

    shortfall_frac = direction x (entry_price - intended) / intended

positive = the fill was WORSE than the decision price, in fractions of price, which is the same
unit `FillSurface` and `execution_policy` already speak.

THE FIT IS HIERARCHICAL BECAUSE THE SAMPLE IS SMALL, and pretending otherwise is how an execution
model becomes folklore. A cell is (symbol, session, size bucket, order type). Its estimate is
shrunk toward the pooled mean by n / (n + K): with three fills a cell is mostly the pooled number,
with fifty it is mostly itself. Cells under `MIN_CELL` are published as UNMEASURED with their n --
never as a zero, never as the pooled number wearing a cell's name (L1.28a).

WHAT CONSUMES IT. `execution_policy.plans()` reads `expected_shortfall(...)` and uses the fitted
cost IN PLACE of the half-spread prior when the cell is MEASURED, falling back to exactly today's
behaviour when it is not. That changes WHICH ORDER TYPE wins a comparison; it changes no size, no
heat, no gate, and it can only make the comparison more honest -- a measured cost that is LOWER
than the prior makes more trades pass their utility test, not fewer.

    python desks/mt5/research/shortfall_model.py --once --budget-s 120
"""
from __future__ import annotations

import argparse
import json
import math
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

INTENTS = DESK / "data" / "order_intents.jsonl"
DEALS = DESK / "data" / "live_ledger.jsonl"
OUT = DESK / "reports" / "SHORTFALL_MODEL.json"

MIN_CELL = 5              # fills below this: the cell is UNMEASURED and the pooled number is used
MIN_POOL = 8              # fills below this: the whole model is UNMEASURED and nothing is applied
SHRINK_K = 10.0           # n / (n + K) toward the pool: three fills are mostly the pool
SIZE_EDGES = ((0.05, "xs<=0.05"), (0.20, "s<=0.20"), (1.00, "m<=1.00"), (float("inf"), "l>1.00"))
SESSIONS = ((0, 8, "asia"), (8, 13, "london"), (13, 21, "newyork"), (21, 24, "late"))


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def size_bucket(lots: float) -> str:
    for edge, name in SIZE_EDGES:
        if lots <= edge:
            return name
    return SIZE_EDGES[-1][1]


def session_of(hour: int) -> str:
    for lo, hi, name in SESSIONS:
        if lo <= hour < hi:
            return name
    return "late"


def _hour(value: Any) -> int | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC).hour
    except (TypeError, ValueError):
        return None


def _direction(side: Any) -> int:
    s = str(side or "").lower()
    if s.startswith("buy") or s in ("0", "long"):
        return 1
    if s.startswith("sell") or s in ("1", "short"):
        return -1
    return 0


def join(intents: list[dict[str, Any]], deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Realised fills: one row per intent whose ticket appears in the deal tape.

    THE KEY IS THE TICKET, tried in three places because MT5 reports the same order under
    `entry_order` for the deal that opened a position, `order` for the deal itself and
    `position_id` for the position -- and which one is present depends on how the order filled."""
    by_ticket: dict[int, dict[str, Any]] = {}
    for deal in deals:
        for k in ("entry_order", "order", "position_id"):
            v = deal.get(k)
            try:
                t = int(v)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            by_ticket.setdefault(t, deal)
    out: list[dict[str, Any]] = []
    for i in intents:
        try:
            ticket = int(i.get("ticket"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        d = by_ticket.get(ticket)
        if d is None:
            continue
        try:
            intended = float(i.get("intended"))  # type: ignore[arg-type]
            fill = float(d.get("entry_price") if d.get("entry_price") is not None
                         else d.get("fill_price"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(intended) and math.isfinite(fill)) or intended <= 0:
            continue
        direction = _direction(i.get("side")) or _direction(d.get("side"))
        if direction == 0:
            continue
        hour = _hour(i.get("time") or d.get("time"))
        try:
            lots = float(i.get("lot") or d.get("volume") or 0.0)
        except (TypeError, ValueError):
            lots = 0.0
        order_type = str(i.get("order_type")
                         or ("pending_stop" if "stop" in str(i.get("side") or "") else "market"))
        out.append({
            "ticket": ticket, "symbol": str(i.get("symbol") or d.get("symbol") or "?"),
            "side": i.get("side"), "direction": direction, "lots": lots,
            "order_type": order_type,
            "hour": hour, "session": session_of(hour) if hour is not None else "unknown",
            "size_bucket": size_bucket(lots),
            "intended": intended, "fill": fill,
            "shortfall_frac": direction * (fill - intended) / intended,
            "time": i.get("time") or d.get("time"),
        })
    return out


def _stats(vals: list[float]) -> dict[str, Any]:
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": None, "se": None, "sd": None}
    mean = sum(vals) / n
    if n == 1:
        return {"n": 1, "mean": mean, "se": None, "sd": None}
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    sd = math.sqrt(var)
    return {"n": n, "mean": mean, "se": sd / math.sqrt(n), "sd": sd}


def fit(fills: list[dict[str, Any]]) -> dict[str, Any]:
    """Pooled estimate plus one shrunk estimate per (symbol, session, size, order type)."""
    pool = _stats([float(f["shortfall_frac"]) for f in fills])
    cells: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[float]] = {}
    for f in fills:
        key = f"{f['symbol']}|{f['session']}|{f['size_bucket']}|{f['order_type']}"
        groups.setdefault(key, []).append(float(f["shortfall_frac"]))
    pooled_mean = float(pool["mean"]) if pool["mean"] is not None else 0.0
    for key, vals in sorted(groups.items()):
        st = _stats(vals)
        n = int(st["n"])
        w = n / (n + SHRINK_K)
        shrunk = w * float(st["mean"] or 0.0) + (1.0 - w) * pooled_mean
        cells[key] = {
            **st, "shrunk_mean": shrunk, "weight_on_cell": round(w, 4),
            "verdict": "MEASURED" if n >= MIN_CELL else "UNMEASURED",
            "why": (None if n >= MIN_CELL else
                    f"{n} fill(s) in this cell, under the floor of {MIN_CELL}; the pooled "
                    f"estimate is what a consumer gets"),
        }
    return {
        "pooled": {**pool, "verdict": "MEASURED" if int(pool["n"]) >= MIN_POOL else "UNMEASURED",
                   "min_pool": MIN_POOL},
        "cells": cells, "shrink_k": SHRINK_K, "min_cell": MIN_CELL,
        "unit": "fraction of price, positive = the fill was worse than the decision price",
    }


def expected_shortfall(symbol: str, hour: int, lots: float, order_type: str,
                       doc: dict[str, Any] | None = None) -> tuple[float | None, str]:
    """THE CONSUMER'S DOOR. `execution_policy.plans()` calls this and uses the fitted cost in
    place of the half-spread prior when it is measured.

    Returns (None, why) when nothing is measured -- the caller then behaves EXACTLY as it did
    before this organ existed. An absent artifact is never a cost of zero."""
    d: dict[str, Any] | None = dict(doc) if doc is not None else None
    if d is None:
        try:
            loaded = json.loads(OUT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, "no SHORTFALL_MODEL.json on this host"
        d = loaded if isinstance(loaded, dict) else None
    if d is None:
        return None, "SHORTFALL_MODEL.json is not an object"
    model = d.get("model") if isinstance(d, dict) else None
    if not isinstance(model, dict):
        return None, "artifact carries no model block"
    pooled = model.get("pooled") or {}
    if str(pooled.get("verdict")) != "MEASURED":
        return None, (f"pooled sample is {pooled.get('n')} fill(s), under the floor of "
                      f"{pooled.get('min_pool')}")
    key = f"{symbol}|{session_of(int(hour))}|{size_bucket(float(lots))}|{order_type}"
    cell = (model.get("cells") or {}).get(key)
    if isinstance(cell, dict) and cell.get("shrunk_mean") is not None:
        return float(cell["shrunk_mean"]), (
            f"cell {key} n={cell.get('n')} ({cell.get('verdict')}), shrunk toward the pool at "
            f"weight {cell.get('weight_on_cell')}")
    return float(pooled.get("mean") or 0.0), (
        f"no fill in cell {key}; pooled estimate over {pooled.get('n')} fill(s)")


def build(budget_s: float = 120.0) -> dict[str, Any]:
    t0 = time.monotonic()
    intents, deals = _rows(INTENTS), _rows(DEALS)
    fills = join(intents, deals)
    model = fit(fills)
    by_symbol: dict[str, int] = {}
    for f in fills:
        by_symbol[f["symbol"]] = by_symbol.get(f["symbol"], 0) + 1
    measured_cells = [k for k, v in model["cells"].items() if v["verdict"] == "MEASURED"]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": ("OK" if model["pooled"]["verdict"] == "MEASURED" else "UNMEASURED"),
        "n_intents": len(intents), "n_deals": len(deals), "n_joined_fills": len(fills),
        "join_rule": ("intent.ticket == deal.entry_order | deal.order | deal.position_id; the "
                      "twin joined on none of these, which is why its slip columns were empty"),
        "by_symbol": by_symbol,
        "n_cells": len(model["cells"]), "n_cells_measured": len(measured_cells),
        "model": model,
        "worst_cells": sorted(
            ({"cell": k, **v} for k, v in model["cells"].items() if v["verdict"] == "MEASURED"),
            key=lambda r: -float(r.get("shrunk_mean") or 0.0))[:8],
        "consumers": [
            "desks/mt5/mt5desk/execution_policy.py plans() -> expected_shortfall(): the fitted "
            "cost replaces the half-spread prior for MARKET and STOP when it is measured, and "
            "falls back to the prior otherwise",
            "reports/SHORTFALL_MODEL.json -> the per-cell record the twin's recalibration block "
            "could not produce without the ticket join",
        ],
        "boundary": (
            "A COST, NOT A CAP. This changes which ORDER TYPE wins a utility comparison; it sets "
            "no size, no heat and no gate, and a measured cost below the half-spread prior makes "
            "MORE trades clear their utility test rather than fewer."),
        "seconds": round(time.monotonic() - t0, 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"shortfall model: could not write {OUT}: {exc}")
        return 1
    p = doc["model"]["pooled"]
    print(f"shortfall model: {doc['n_joined_fills']} fill(s) joined from {doc['n_intents']} "
          f"intent(s) and {doc['n_deals']} deal(s); pooled {p['verdict']} "
          f"mean={p['mean'] if p['mean'] is None else round(float(p['mean']), 8)} n={p['n']}")
    for row in doc["worst_cells"]:
        print(f"   {row['cell'][:54]:<54} n={row['n']:<3} "
              f"shrunk={float(row['shrunk_mean']):+.8f}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
