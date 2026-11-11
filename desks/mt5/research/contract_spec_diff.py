"""K2: THE BROKER'S CONTRACT SPECS AGAINST WHAT THE CODE ASSUMES, EVERY DAY.

WHY (CRO noon pass, 2026-11-11). Every cost the gauntlet charges, every certificate's cost basis
and every carry estimate is computed from `data/universe/universe.json`: contract size, tick
size, tick value, minimum lot, lot step, digits, profit currency and swap mode. The gateway sizes a
live order from the terminal's own `symbol_info`, so a live ticket is priced right on the day; the
research that chose to trade it is not. If the broker changes a contract (a CFD re-based from 100 to
10 units, a minimum lot raised, a swap mode switched from points to annual percent), the registry
goes on describing the old instrument and nothing compares the two. `refresh_cost_fields` only
FILLS a missing tick value; it never notices a present value that has gone wrong.

WHAT IS COMPARED. The broker's side is the newest live row per symbol from the contract-terms
tape (`data/tape/contract_terms/*.parquet`), written hourly by `mt5desk.tape` from the connected
Fusion terminal. A row only counts when it carries `quote_time_utc` within FRESH_H: a terminal
that has lost its connection still answers `symbol_info` from cache, and a cached value is not
the broker's word. The code's side is the registry row for the same symbol.

  exact      contract_size, tick_size, digits, volume_min, currency_profit, swap_mode,
             swap_rollover3days -- these are properties of the contract, so any difference is
             a mismatch.
  tolerance  tick_value moves with the exchange rate whenever the profit currency is not the
             account's (EUR). A move over TICK_VALUE_TOL is a stale cost basis; an exact
             comparison would cry wolf every day. For EUR-profit symbols it is exact.
  state      trade_mode 0 (DISABLED) or 3 (CLOSE-ONLY) on a LIVE symbol: the broker has told every
             holder to get out, and the desk would otherwise learn it from a rejected order.
             swap_mode outside what `carry_state` can resolve (0, 1, 5) on a live symbol: its
             carry is UNMEASURED, so the carry legs are pricing it at nothing.
  absent     trading hours and volume_step: the MetaTrader5 Python API exposes no session table
             and the tape does not record the lot step, so both are reported UNMEASURED by name
             rather than passed as matching.

WHAT IT FIXES. With --apply, every exact or tolerance mismatch is written into the registry
through `universe_registry.merge` (source "contract_spec_diff"), the same merge-never-clobber
writer every producer uses, so a degenerate broker reading can never delete a good value. The
fix is the broker's own number. Two guards stop a bad reading from rewriting the desk:
  * only fresh, evidenced rows are used (above);
  * if more than MASS_CHANGE_FRAC of compared symbols disagree on one field at once, that is a
    terminal or tape fault, not the broker re-papering half its book: nothing on that field
    is written and the alarm says so.
A mismatch on a LIVE symbol also raises data/CONTRACT_SPEC_ALARM.txt (the issue board reads it).
The alarm is removed on the first clean pass. Changing a live symbol's registry row changes the cost
basis its sleeves were certified on, which is what should happen: a sleeve certified on a
contract the broker no longer offers is certified on a fiction, and the judge re-tests it on the
real one.

Output: reports/CONTRACT_SPEC_DIFF.json every run. Daily via daily_cycle step
`contract_spec_diff`, right after `cost_fields`.
"""
from __future__ import annotations

import contextlib
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
TERMS = DESK / "data" / "tape" / "contract_terms"
REGISTRY = DESK / "data" / "universe" / "universe.json"
OUT = DESK / "reports" / "CONTRACT_SPEC_DIFF.json"
ALARM = DESK / "data" / "CONTRACT_SPEC_ALARM.txt"

ACCOUNT_CCY = "EUR"
FRESH_H = 72.0                 # a weekend is ~49 h of no quotes; 72 h still names a dead terminal
TERMS_DAYS = 4                 # tape files read (newest first)
TICK_VALUE_TOL = 0.05
MASS_CHANGE_FRAC = 0.20
MASS_CHANGE_MIN = 5            # below this many symbols a "mass" change is just a few changes
CARRY_RESOLVABLE = frozenset({0, 1, 5})
EXACT = ("contract_size", "tick_size", "digits", "volume_min", "currency_profit",
         "swap_mode", "swap_rollover3days")
UNMEASURED_FIELDS = {
    "trading_hours": "the MetaTrader5 Python API exposes no session table (SymbolInfoSessionTrade "
                     "is MQL5-only) and no recorder captures one",
    "volume_step": "the contract-terms tape does not record volume_step",
}


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _same(field: str, broker: Any, code: Any) -> bool:
    if field == "currency_profit":
        return str(broker or "").strip().upper() == str(code or "").strip().upper()
    b, c = _num(broker), _num(code)
    if b is None or c is None:
        return b is None and c is None
    return math.isclose(b, c, rel_tol=1e-9, abs_tol=1e-12)


def _code_value(row: dict[str, Any], field: str) -> Any:
    if field == "volume_min" and row.get("volume_min") is None:
        return row.get("min_volume")
    return row.get(field)


def _broker_usable(field: str, value: Any) -> bool:
    """A broker value worth comparing: present, and not the degenerate zero of an unread field."""
    if value is None:
        return False
    if field == "currency_profit":
        return isinstance(value, str) and len(value.strip()) == 3
    v = _num(value)
    if v is None:
        return False
    if field in ("swap_mode", "swap_rollover3days", "digits"):
        return v >= 0
    return v > 0


def latest_terms(frames: list[Any], now: datetime) -> dict[str, dict[str, Any]]:
    """Newest row per symbol whose quote is fresh. `frames` are DataFrames from the tape."""
    best: dict[str, dict[str, Any]] = {}
    cut = now - timedelta(hours=FRESH_H)
    for df in frames:
        for row in df.to_dict("records"):
            sym = str(row.get("symbol") or "")
            q = row.get("quote_time_utc")
            try:
                qt = datetime.fromisoformat(str(q)) if q is not None else None
            except ValueError:
                qt = None
            if not sym or qt is None:
                continue
            if qt.tzinfo is None:
                qt = qt.replace(tzinfo=UTC)
            if qt < cut:
                continue
            seen = str(row.get("observed_at") or "")
            if sym not in best or seen > str(best[sym].get("observed_at") or ""):
                best[sym] = row
    return best


def compare(terms: dict[str, dict[str, Any]], registry: dict[str, Any],
            live: set[str]) -> dict[str, Any]:
    """Pure: every mismatch, every live-state alert, and the fixes the broker's numbers imply."""
    mismatches: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    fixes: dict[str, dict[str, Any]] = {}
    compared: dict[str, int] = {}
    missing_in_registry = sorted(s for s in terms if not isinstance(registry.get(s), dict))
    for sym in sorted(terms):
        row = registry.get(sym)
        if not isinstance(row, dict):
            continue
        b = terms[sym]
        is_live = sym in live
        for field in EXACT:
            bv, cv = b.get(field), _code_value(row, field)
            if not _broker_usable(field, bv):
                continue
            compared[field] = compared.get(field, 0) + 1
            if cv is not None and _same(field, bv, cv):
                continue
            mismatches.append({"symbol": sym, "field": field, "broker": bv, "code": cv,
                               "live": is_live,
                               "kind": "absent_in_code" if cv is None else "differs"})
            fixes.setdefault(sym, {})[field] = (str(bv).strip().upper()
                                                if field == "currency_profit" else _num(bv))
        btv, ctv = _num(b.get("tick_value")), _num(row.get("tick_value"))
        if btv is not None and btv > 0:
            compared["tick_value"] = compared.get("tick_value", 0) + 1
            fx_free = str(b.get("currency_profit") or "").upper() == ACCOUNT_CCY
            tol = 1e-9 if fx_free else TICK_VALUE_TOL
            drift = None if not ctv else abs(btv - ctv) / ctv
            if ctv is None or ctv <= 0 or (drift is not None and drift > tol):
                mismatches.append({"symbol": sym, "field": "tick_value", "broker": btv,
                                   "code": ctv, "live": is_live,
                                   "drift": round(drift, 4) if drift is not None else None,
                                   "kind": "stale_fx" if not fx_free else "differs"})
                fixes.setdefault(sym, {})["tick_value"] = btv
        if is_live:
            tm = b.get("trade_mode")
            if tm is not None and _num(tm) in (0.0, 3.0):
                alerts.append({"symbol": sym, "alert": "trade_mode",
                               "value": int(_num(tm) or 0),
                               "meaning": "DISABLED" if _num(tm) == 0 else "CLOSE-ONLY"})
            sm = _num(b.get("swap_mode"))
            if sm is not None and int(sm) not in CARRY_RESOLVABLE:
                alerts.append({"symbol": sym, "alert": "swap_mode_unresolvable",
                               "value": int(sm),
                               "meaning": "carry_state resolves modes 0, 1 and 5 only; this "
                                          "symbol's carry is UNMEASURED"})
    # THE MASS-CHANGE GUARD: one field disagreeing on a large share of the book at once is a
    # reading fault. Its fixes are withheld and named.
    withheld: dict[str, int] = {}
    for field, n in compared.items():
        bad = sum(1 for m in mismatches if m["field"] == field and m["kind"] != "absent_in_code")
        if bad >= MASS_CHANGE_MIN and bad > MASS_CHANGE_FRAC * n:
            withheld[field] = bad
            for sym in list(fixes):
                fixes[sym].pop(field, None)
                if not fixes[sym]:
                    del fixes[sym]
    live_mm = [m for m in mismatches if m["live"]]
    return {"mismatches": mismatches, "live_mismatches": live_mm, "alerts": alerts,
            "fixes": fixes, "withheld_fields": withheld, "compared": compared,
            "missing_in_registry": missing_in_registry,
            "live_symbols_without_terms": sorted(s for s in live if s not in terms)}


def _live_symbols() -> set[str]:
    try:
        sys.path.insert(0, str(DESK))
        from mt5desk.live_policy import policy
        return {str(s).upper() for s in policy().live_symbols}
    except Exception:
        return {"XAUUSD"}


def _read_terms(now: datetime) -> list[Any]:
    import pandas as pd
    files = sorted(TERMS.glob("*.parquet"))[-TERMS_DAYS:] if TERMS.is_dir() else []
    out = []
    for f in files:
        try:
            out.append(pd.read_parquet(f))
        except Exception:
            continue
    return out


def _alarm(doc: dict[str, Any]) -> bool:
    bad = doc["live_mismatches"] or doc["alerts"] or doc["withheld_fields"]
    if not bad:
        with contextlib.suppress(OSError):
            ALARM.unlink(missing_ok=True)
        return False
    lines = [f"CONTRACT SPECS DISAGREE ({doc['at']}): broker terms vs data/universe/universe.json"]
    for m in doc["live_mismatches"][:10]:
        lines.append(f"LIVE {m['symbol']} {m['field']}: broker {m['broker']} vs code {m['code']}")
    for a in doc["alerts"][:10]:
        lines.append(f"LIVE {a['symbol']} {a['alert']}={a['value']} ({a['meaning']})")
    for f, n in doc["withheld_fields"].items():
        lines.append(f"{f}: {n} symbols disagree at once -- fixes withheld as a likely reading "
                     f"fault; check the terminal and the contract-terms tape")
    ALARM.parent.mkdir(parents=True, exist_ok=True)
    ALARM.write_text("\n".join(lines) + "\n", "utf-8")
    return True


def run(apply: bool = False, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    try:
        registry = json.loads(REGISTRY.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        registry = {}
        reg_why: str | None = f"registry unreadable: {type(exc).__name__}"
    else:
        reg_why = None
    terms = latest_terms(_read_terms(now), now)
    live = _live_symbols()
    result = compare(terms, registry if isinstance(registry, dict) else {}, live)
    status = ("UNMEASURED" if reg_why or not terms else
              "MISMATCH" if result["mismatches"] or result["alerts"] else "MATCH")
    applied: dict[str, list[str]] = {}
    if apply and status == "MISMATCH" and result["fixes"]:
        sys.path.insert(0, str(DESK))
        from mt5desk.universe_registry import merge
        merged = merge(registry, result["fixes"], source="contract_spec_diff",
                       now=now.isoformat(timespec="seconds"))
        tmp = REGISTRY.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(merged, indent=1, sort_keys=True), "utf-8")
        tmp.replace(REGISTRY)
        applied = {s: sorted(f) for s, f in result["fixes"].items()}
    doc = {
        "at": now.isoformat(timespec="seconds"), "status": status,
        "why": reg_why or (None if terms else
                           f"no contract-terms row with a quote inside {FRESH_H:g} h in "
                           f"{TERMS}: the terms recorder or the terminal is down"),
        "venue": "Fusion (the terminal mt5desk.tape records); FTMO and E8 not yet covered",
        "symbols_with_fresh_terms": len(terms), "live_symbols": sorted(live),
        **result, "applied": applied, "applied_mode": "apply" if apply else "report-only",
        "unmeasured_fields": UNMEASURED_FIELDS,
        "tolerances": {"tick_value_rel": TICK_VALUE_TOL, "fresh_h": FRESH_H,
                       "mass_change_frac": MASS_CHANGE_FRAC},
    }
    doc["alarm_raised"] = _alarm(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    doc = run(apply="--apply" in args)
    print(f"contract spec diff: {doc['status']}; {len(doc['mismatches'])} mismatch(es) "
          f"({len(doc['live_mismatches'])} live), {len(doc['alerts'])} live alert(s), "
          f"fixed {sum(len(v) for v in doc['applied'].values())} field(s) on "
          f"{len(doc['applied'])} symbol(s); withheld {doc['withheld_fields'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
