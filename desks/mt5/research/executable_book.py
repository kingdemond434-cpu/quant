"""EXECUTABLE BOOK -- the allocator's continuous book against the one the venue will hold.

ALLOC-05/06/15/17/18/23. Reads `reports/pf_allocation.json` (per-sleeve heat), the sleeve and
universe registries, the gateway's state and the H1 bars, and publishes
`reports/EXECUTABLE_BOOK.json`:

  * per-sleeve continuous vs executable lots/heat and why size was lost (step, minimum, unpriced);
  * E[log W]/day of both books on the same daily R matrix -- the price of discreteness;
  * equity allocation, stop-risk heat, risk budget, notional exposure, margin usage, labelled;
  * per-symbol netting (gross vs net lots, orders saved), attribution kept;
  * heat reserved by resting/pending orders, and the free heat left under the operative ceiling;
  * which sleeves sit outside their trading session right now;
  * measured per-sleeve turnover cost in R next to the allocator's single constant.

REPORT ONLY. It sizes nothing, no organ reads it for sizing, and it cannot move the heat law.
A sleeve whose stop, tick economics or venue grid is unreadable is UNPRICED and named, never
priced off a guess. STOP BASIS: the registry carries no stop distance for most sleeves, so the
stop is `stop_atr` (default 1) x ATR(14) on the symbol's H1 bars, and every row says so.

    python desks/mt5/research/executable_book.py [--json] [--no-write]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import executable_book as xb  # noqa: E402

DATA = DESK / "data"
REPORTS = DESK / "reports"
OUT = REPORTS / "EXECUTABLE_BOOK.json"
ALLOCATION = REPORTS / "pf_allocation.json"
VERSION = 1
#: ATR look-back for the stop proxy, the 14-bar window Wilder derived the ATR on and the one every
#: ATR-stop sleeve on this desk was certified with.
ATR_BARS = 14


def _json(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def _bars(symbol: str) -> tuple[float | None, float | None]:
    """(last close, ATR(14)) from the H1 bars on this host, or (None, None)."""
    uni = DATA / "universe"
    for path in (uni / f"{symbol}_H1.parquet", uni / f"{symbol}_H1.csv"):
        if not path.exists():
            continue
        try:
            import pandas as pd
            cols = ["high", "low", "close"]
            df = (pd.read_parquet(path, columns=cols) if path.suffix == ".parquet"
                  else pd.read_csv(path, usecols=cols)).dropna().tail(ATR_BARS + 1)
        except Exception:
            return None, None
        if len(df) < ATR_BARS + 1:
            return None, None
        h, lo, c = (df[k].to_numpy(float) for k in cols)
        tr = np.maximum(h[1:] - lo[1:], np.maximum(abs(h[1:] - c[:-1]), abs(lo[1:] - c[:-1])))
        return float(c[-1]), float(tr.mean())
    return None, None


def specs_for(names: list[str], rows: dict[str, dict[str, Any]],
              reg: dict[str, Any]) -> tuple[dict[str, xb.SleeveSpec], dict[str, str]]:
    specs: dict[str, xb.SleeveSpec] = {}
    basis: dict[str, str] = {}
    for n in names:
        row = rows.get(n) or {}
        sym = str(row.get("symbol") or n.split("_")[0]).strip()
        u = reg.get(sym) or {}
        price, atr = _bars(sym)
        k = _f(row.get("stop_atr")) or _f((row.get("params") or {}).get("stop_atr")) or 1.0
        side_raw = str(row.get("side") or row.get("direction") or "").upper()
        side = -1.0 if side_raw in ("SHORT", "SELL") else (1.0 if side_raw in ("LONG", "BUY")
                                                           else 0.0)
        specs[n] = xb.SleeveSpec(
            name=n, symbol=sym, side=side,
            stop_dist=(k * atr) if atr else None,
            tick_value=_f(u.get("tick_value")), tick_size=_f(u.get("tick_size")),
            volume_min=_f(u.get("volume_min")), volume_step=_f(u.get("volume_step")),
            contract_size=_f(u.get("contract_size")), price=price,
            asset_class=str(u.get("asset_class") or ""))
        basis[n] = (f"{k:g} x H1 ATR({ATR_BARS})" if atr else "no H1 bars on this host")
    return specs, basis


def _daily_r(names: list[str]) -> tuple[np.ndarray, list[str], str]:
    try:
        from research import pf_allocator as pa
        daily, _fwd = pa.build_evidence()
    except (Exception, SystemExit) as exc:
        # `build_evidence` REFUSES with SystemExit when the hunt report is absent: the growth
        # comparison is then UNMEASURED and the rest of the report still publishes.
        return np.empty((0, 0)), [], f"no evidence matrix ({type(exc).__name__})"
    cols = [n for n in names if n in daily.columns]
    if not cols:
        return np.empty((0, 0)), [], "no booked sleeve in the evidence matrix"
    return daily[cols].to_numpy(float), cols, ""


def _turnover(names: list[str]) -> dict[str, Any]:
    try:
        from research import pf_allocator as pa
        costs = pa._execution_costs(names)
        const = float(pa.TURNOVER_COST_R)
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}"}
    per = {n: v.get("cost_r") for n, v in costs.items()
           if n != "summary" and isinstance(v, dict) and v.get("source") == "MEASURED"}
    vals = [float(v) for v in per.values() if isinstance(v, (int, float))]
    return {"status": "MEASURED" if vals else "UNMEASURED", "constant_r": const,
            "measured_cost_r": per, "n_measured": len(vals), "n_booked": len(names),
            "median_measured_r": float(np.median(vals)) if vals else None,
            "max_measured_r": max(vals) if vals else None,
            "note": ("SHADOW. The no-trade rule still charges the constant; a per-symbol charge "
                     "replaces it only after a growth comparison shows it raises E[log W].")}


def build(alloc: dict[str, Any], sleeves: dict[str, dict[str, Any]], reg: dict[str, Any],
          state: dict[str, Any], *, daily: tuple[np.ndarray, list[str], str] | None = None,
          now: datetime | None = None, turnover: dict[str, Any] | None = None,
          margin: float | None = None) -> dict[str, Any]:
    book = {str(k): float(v) for k, v in (alloc.get("book") or {}).items()
            if isinstance(v, (int, float)) and float(v) > 0}
    equity = _f(state.get("equity")) or 0.0
    if not book or equity <= 0:
        return {"status": "UNMEASURED",
                "why": "no allocated book" if not book else "no equity in gateway_state"}
    names = sorted(book)
    specs, basis = specs_for(names, sleeves, reg)
    rows = {n: {**xb.executable(book[n], equity, specs[n]), "stop_basis": basis[n]}
            for n in names}
    executed = {n: float(r.get("heat_executable") or 0.0) for n, r in rows.items()}
    r, cols, why = daily if daily is not None else _daily_r(names)
    growth = (xb.growth_gap(r, cols, book, executed) if cols
              else {"status": "UNMEASURED", "why": why})

    from libs.portfolio.netting import SleeveIntent, net_intents, netting_summary
    intents = [SleeveIntent(n, specs[n].symbol, specs[n].side * float(rows[n]["lots_executable"]))
               for n in names if specs[n].side and rows[n].get("lots_executable")]
    steps = {s.symbol: float(s.volume_step) for s in specs.values() if s.volume_step}
    netted = net_intents(intents, volume_step=steps) if intents else ()
    netting = {**netting_summary(netted), "n_directional": len(intents),
               "n_two_sided_unknown": sum(1 for n in names if not specs[n].side),
               "symbols": {t.symbol: {"gross": t.gross_lots, "net": t.target_lots,
                                      "contributors": t.n_contributors} for t in netted}}

    tick = {s.symbol: (float(s.tick_value), float(s.tick_size)) for s in specs.values()
            if s.tick_value and s.tick_size}
    for sym, u in reg.items():
        if sym not in tick and _f(u.get("tick_value")) and _f(u.get("tick_size")):
            tick[sym] = (float(u["tick_value"]), float(u["tick_size"]))
    symbol_of = {w: "XAUUSD" for w in (state.get("brackets") or {}) if str(w).startswith("gold")}
    reserve = xb.reserved_heat(xb.bracket_orders(state, symbol_of), tick, equity)
    ceiling = _f(((alloc.get("heat") or {}).get("envelope") or {}).get("operative_ceiling"))
    used = sum(executed.values())
    free = (None if ceiling is None or reserve.get("reserved_heat") is None
            else round(ceiling - used - float(reserve["reserved_heat"]), 8))

    try:
        from libs.research import market_constitution as mc
        sessions = xb.session_states(specs, mc.venue_fusion(), now or datetime.now(UTC),
                                     mc.instrument_class_of, mc.state_at)
    except Exception as exc:
        sessions = {"status": "UNMEASURED", "why": type(exc).__name__}

    status_counts: dict[str, int] = {}
    for row in rows.values():
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    return {
        "status": "MEASURED", "equity": equity, "n_booked": len(names),
        "status_counts": status_counts,
        "heat": {"continuous": round(sum(book.values()), 8), "executable": round(used, 8),
                 "lost_to_grid": round(sum(book.values()) - used, 8),
                 "reserved_by_orders": reserve.get("reserved_heat"),
                 "operative_ceiling": ceiling, "free_after_reservation": free},
        "growth": growth, "exposures": xb.labelled_exposures(rows, specs, equity, margin),
        "netting": netting, "reservation": reserve, "sessions": sessions,
        "turnover_cost": turnover if turnover is not None else _turnover(names),
        "sleeves": rows,
    }


def run(*, write: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    reg_doc = _json(DATA / "universe" / "universe.json")
    reg = reg_doc.get("symbols", reg_doc) if isinstance(reg_doc, dict) else {}
    sl = _json(DATA / "sleeves.json").get("sleeves") or []
    sleeves = {str(r.get("name")): r for r in sl if isinstance(r, dict)}
    body = build(_json(ALLOCATION), sleeves, reg if isinstance(reg, dict) else {},
                 _json(DATA / "gateway_state.json"))
    doc = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "version": VERSION,
           "authority": "none -- a report; it sizes nothing and no organ reads it for sizing",
           **body, "elapsed_s": round(time.monotonic() - t0, 2)}
    doc.setdefault("growth", {"status": "UNMEASURED"})
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        tmp.replace(OUT)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    doc = run(write=not args.no_write)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        g = doc.get("growth") or {}
        h = doc.get("heat") or {}
        print(f"EXECUTABLE BOOK {doc.get('status')}: heat {h.get('continuous')} -> "
              f"{h.get('executable')} reserved={h.get('reserved_by_orders')} "
              f"discreteness/day={g.get('discreteness_cost_per_day')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
