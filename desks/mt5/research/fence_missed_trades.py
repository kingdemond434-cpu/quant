"""WHAT THE CROSS-ACCOUNT FENCE REFUSED, PRICED FROM BARS (report-only).

THE BLOCK EVENTS, by lane (where each logs a refusal of `cross_account.opposite_block`):
  * Fusion gateway, gold brackets: `mt5desk/gateway.py` place_bracket -> `_record_decision(...,
    reason="cross_account_opposite")` into data/decision_ledger.jsonl (with price/sl/tp/lot), and
    `fusion_rails.line("cross_account_opposite", ...)` into data/fusion_book_rails.jsonl (no
    geometry). Family market orders: `journal_refusal` + the same rails line.
  * E8-Gold: `prop/e8_gold.py` `_record({... "status": "RAIL_BLOCKED", "rail":
    "cross_account_opposite"})` into data/e8_gold_intents.jsonl -- WITHOUT entry/stop/target, so
    its counterfactual is UNMEASURED_NO_GEOMETRY until the row carries them (a named gap).
  * FTMO follower: `_skip(..., "opposite_exposure", ...)` into data/ftmo_follower_intents.jsonl,
    also without geometry.

For every refused pending entry with geometry, the M1 bars after the refusal decide: would the
stop/limit have filled before the gold book's close (19:30 UTC), and then SL first or TP first
(both inside one bar = SL, conservative), else the time exit at the close. R is signed in units of
the entry-to-stop distance. Final rows append once to reports/fence_missed_trades.jsonl; rows whose
bars do not yet reach the exit are left PENDING in reports/FENCE_MISSED_TRADES.json and re-tried.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

Row = dict[str, Any]
DESK = Path(__file__).resolve().parent.parent
OUT = DESK / "reports" / "fence_missed_trades.jsonl"
SUMMARY = DESK / "reports" / "FENCE_MISSED_TRADES.json"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
E8_INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
FTMO_INTENTS = DESK / "data" / "ftmo_follower_intents.jsonl"
UNI = DESK / "data" / "universe"
CLOSE_UTC = (19, 30)
CONTRACT = {"XAUUSD": 100.0}
UNMEASURED = "UNMEASURED"


def _jsonl(path: Path) -> list[Row]:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _f(x: object) -> float | None:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def events(decisions: Iterable[Row] | None = None, e8: Iterable[Row] | None = None,
           ftmo: Iterable[Row] | None = None) -> list[Row]:
    """One event per (account, sleeve, side, day): the first refusal of that leg that day."""
    decisions = _jsonl(DECISIONS) if decisions is None else decisions
    e8 = _jsonl(E8_INTENTS) if e8 is None else e8
    ftmo = _jsonl(FTMO_INTENTS) if ftmo is None else ftmo
    out: dict[str, Row] = {}

    def put(acct: str, sleeve: str, side: str, at: str, row: Row, symbol: str) -> None:
        eid = f"{acct}|{sleeve}|{side}|{at[:10]}"
        if eid in out:
            return
        out[eid] = {"event_id": eid, "account": acct, "sleeve": sleeve, "side": side, "at": at,
                    "symbol": symbol, "price": _f(row.get("price")), "sl": _f(row.get("sl")),
                    "tp": _f(row.get("tp")), "lot": _f(row.get("lot")),
                    "risk_usd": _f(row.get("missed_growth_risk_usd")),
                    "why": row.get("detail") or row.get("why")}

    for r in decisions:
        if r.get("reason") == "cross_account_opposite" or \
                r.get("first_blocking_gate") == "cross_account_opposite":
            put("fusion", str(r.get("sleeve") or r.get("strategy_id")), str(r.get("side")),
                str(r.get("time") or r.get("decided_at") or ""), r,
                str(r.get("symbol") or "XAUUSD"))
    for r in e8:
        if r.get("rail") == "cross_account_opposite":
            put("e8", str(r.get("window")), str(r.get("side")), str(r.get("at") or ""), r,
                str(r.get("symbol") or "XAUUSD"))
    for r in ftmo:
        if r.get("reason") == "opposite_exposure":
            put("ftmo", str(r.get("window")), str(r.get("side") or "?"), str(r.get("at") or ""),
                r, str(r.get("symbol") or "XAUUSD"))
    return sorted(out.values(), key=lambda e: e["at"])


def counterfactual(ev: Row, bars: Any) -> Row:
    """{status, filled, r, exit} for one refused pending entry, by the bracket rules."""
    side = str(ev.get("side") or "")
    p, sl, tp = ev.get("price"), ev.get("sl"), ev.get("tp")
    if p is None or sl is None or tp is None or abs(p - sl) == 0 or \
            not side.endswith(("_stop", "_limit")):
        return {"status": "UNMEASURED_NO_GEOMETRY", "r": None,
                "why": "the refusal row carries no entry/stop/target (or no pending side)"}
    if bars is None or len(bars) == 0:
        return {"status": "UNMEASURED_NO_BARS", "r": None, "why": "no M1 bars for the symbol"}
    t0 = datetime.fromisoformat(str(ev["at"]).replace("Z", "+00:00"))
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=UTC)
    close = t0.replace(hour=CLOSE_UTC[0], minute=CLOSE_UTC[1], second=0, microsecond=0)
    if close <= t0:
        close += timedelta(days=1)
    w = bars[(bars.index > t0) & (bars.index <= close)]
    if len(bars) == 0 or bars.index.max() < close:
        return {"status": "PENDING", "r": None, "why": "bars do not yet reach the close"}
    long = side.startswith("buy")
    risk = abs(p - sl)
    filled_at = None
    for ts, b in w.iterrows():
        hi, lo = float(b["high"]), float(b["low"])
        hit = (hi >= p if long else lo <= p) if side.endswith("_stop") else \
            (lo <= p if long else hi >= p)
        if filled_at is None:
            if not hit:
                continue
            filled_at = ts
        sl_hit = lo <= sl if long else hi >= sl
        tp_hit = hi >= tp if long else lo <= tp
        if sl_hit:
            return {"status": "MEASURED", "filled": True, "filled_at": str(filled_at),
                    "exit": "sl", "exit_at": str(ts), "r": -1.0}
        if tp_hit:
            return {"status": "MEASURED", "filled": True, "filled_at": str(filled_at),
                    "exit": "tp", "exit_at": str(ts), "r": round(abs(tp - p) / risk, 6)}
    if filled_at is None:
        return {"status": "MEASURED", "filled": False, "exit": "never_filled", "r": 0.0}
    last = float(w.iloc[-1]["close"])
    r = ((last - p) if long else (p - last)) / risk
    return {"status": "MEASURED", "filled": True, "filled_at": str(filled_at), "exit": "time",
            "exit_at": str(w.index[-1]), "r": round(r, 6)}


def risk_usd(ev: Row) -> float | None:
    if ev.get("risk_usd") is not None:
        return float(ev["risk_usd"])
    c = CONTRACT.get(str(ev.get("symbol") or "").upper())
    if c and ev.get("lot") is not None and ev.get("price") is not None and ev.get("sl") is not None:
        return round(abs(float(ev["price"]) - float(ev["sl"])) * float(ev["lot"]) * c, 4)
    return None


def load_m1(symbol: str) -> Any:
    try:
        import pandas as pd
        df = pd.read_parquet(UNI / f"{symbol}_M1.parquet")
    except Exception:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()].sort_index()


def run(*, evs: list[Row] | None = None, bars_for: Any = None, out: Path = OUT,
        summary: Path = SUMMARY) -> Row:
    evs = events() if evs is None else evs
    bars_for = bars_for or load_m1
    done = {r.get("event_id") for r in _jsonl(out)}
    cache: Row = {}
    appended, pending, gaps = [], [], []
    for ev in evs:
        if ev["event_id"] in done:
            continue
        sym = str(ev.get("symbol") or "XAUUSD").upper()
        if sym not in cache:
            cache[sym] = bars_for(sym)
        cf = counterfactual(ev, cache[sym])
        if cf["status"] == "PENDING" or cf["status"] == "UNMEASURED_NO_BARS":
            pending.append({**ev, **cf})
            continue
        ru = risk_usd(ev)
        row = {**ev, **cf, "risk_usd": ru,
               "missed_usd": (None if cf.get("r") is None or ru is None
                              else round(float(cf["r"]) * ru, 4)),
               "measured_utc": datetime.now(tz=UTC).isoformat(timespec="seconds")}
        if cf["status"] == "UNMEASURED_NO_GEOMETRY":
            gaps.append(ev["event_id"])
        appended.append(row)
    if appended:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            for r in appended:
                fh.write(json.dumps(r, default=str) + "\n")
    rows = _jsonl(out)
    priced = [r for r in rows if r.get("missed_usd") is not None]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "report_only": True, "events": len(evs), "appended": len(appended),
           "pending": pending, "no_geometry": gaps,
           "rows": len(rows), "priced": len(priced),
           "sum_missed_usd": round(sum(float(r["missed_usd"]) for r in priced), 4),
           "sum_r": round(sum(float(r["r"]) for r in priced), 6),
           "verdict": UNMEASURED if not rows and not evs else "MEASURED"}
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = run()
    print(f"fence_missed_trades: {doc['events']} event(s), {doc['appended']} appended, "
          f"{len(doc['pending'])} pending, sum {doc['sum_missed_usd']} USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
