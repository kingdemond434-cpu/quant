"""WHAT THE CROSS-ACCOUNT FENCE REFUSED, PRICED FROM BARS (report-only).

THE BLOCK EVENTS, by lane (where each logs a refusal of `cross_account.opposite_block`):
  * Fusion gateway, gold brackets: `mt5desk/gateway.py` place_bracket -> `_record_decision(...,
    reason="cross_account_opposite")` into data/decision_ledger.jsonl (with price/sl/tp/lot), and
    `fusion_rails.line("cross_account_opposite", ...)` into data/fusion_book_rails.jsonl (risk held
    back, no geometry; billed by missed_growth's `fusion_book_rails`, never summed with this).
  * E8-Gold: `prop/e8_gold.py:1458-1462` RAIL_BLOCKED `cross_account_opposite` rows in
    data/e8_gold_intents.jsonl -- WITHOUT entry/stop/target: UNMEASURED_NO_GEOMETRY (named gap).
  * FTMO follower: `_skip(..., "opposite_exposure")` (ftmo_follower.py:1056-1060). That is FTMO's
    OWN follow-E8 rule, not the cross-account fence: kind `ftmo_follow_rule`, side often "?".

KINDS. `fence_block` = a real opposite-side refusal; `fail_closed` = the lock was held or a book was
unreadable/stale/absent (e8_gold.py:1446-1449, gateway.py:4160) -- the fence refusing for want of
a reading, not because of a position; `ftmo_follow_rule` as above. Only `fence_block` is billed as
the fence's cost.

THE CLOCK (audit MF1). The M1 parquets are stamped on the BROKER's wall clock (UTC+2 winter /
UTC+3 summer; research/bars_state.py:16-28). The refusal time and the gold book's 19:30 UTC close
are converted with `bars_state.utc_to_broker`; with no server anchor the row is UNMEASURED. A bar
stamp is its OPEN; bars opening before the refusal minute are not used, and the time exit is the
close of the last bar that ENDS at or before 19:30 UTC.

PRICES (S1). Bars are bid. ask = bid + spread x point (the parquet's `spread` column, point from
universe.json digits). Buy entries and every exit of a SHORT (its stop and target) test against
ask; sell entries and every exit of a LONG test against bid. That is MT5's convention (a long
closes at bid). The audit text named "long SLs against ask"; this follows MT5 and says so.

OCO (MF2). The refused leg is not traded alone in the counterfactual: the bracket's PLACED sibling
(same sleeve and day, the other side, from the decision ledger) is simulated on the same bars, and
`gateway.cancel_filled_gold_siblings` (gateway.py:1756) cancels the unfilled half of a filled
bracket; and `gold_oco`'s one-gold-direction-a-day lock (its direction state) cancels every leg
against the first fill on ANY account. If the sibling fills first (same bar counts as first), or
the day's direction was set the other way at or before the refused leg's fill, the row is
`cancelled_by_oco` with r = 0. An unreadable direction state is UNMEASURED.

Final rows append once to reports/fence_missed_trades.jsonl; PENDING rows (bars do not yet reach
the exit) are re-tried. reports/FENCE_MISSED_TRADES.json is MEASURED only when a row is priced.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

Row = dict[str, Any]
DESK = Path(__file__).resolve().parent.parent
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))
OUT = DESK / "reports" / "fence_missed_trades.jsonl"
SUMMARY = DESK / "reports" / "FENCE_MISSED_TRADES.json"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
E8_INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
FTMO_INTENTS = DESK / "data" / "ftmo_follower_intents.jsonl"
CERT_BOOK = DESK / "data" / "CERT_BOOK_LIVE.json"
UNI = DESK / "data" / "universe"
CLOSE_UTC = (19, 30)
BAR = timedelta(minutes=1)
UNMEASURED = "UNMEASURED"
FAIL_CLOSED_MARKS = ("fail closed", "placement lock", "unreadable", "absent", "not read",
                     "old (limit", "unknown now", "malformed", "another account")
_NOT_READ = object()
MAX_BAR_GAP = timedelta(minutes=75)
try:
    from mt5desk.gold_oco import KEEP_DAYS as OCO_KEEP_DAYS
except Exception:                                   # pragma: no cover - import-time fallback
    OCO_KEEP_DAYS = 7
RETRY = ("PENDING", "UNMEASURED_NO_BARS", "UNMEASURED_NO_ANCHOR", "UNMEASURED_OCO",
         "UNMEASURED_BAR_GAP")


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


def _utc(s: object) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def kind_of(why: object) -> str:
    """A real opposite-side block, or the fence failing closed for want of a reading."""
    w = str(why or "").lower()
    if "holds or rests" in w and "fail closed" not in w:
        return "fence_block"
    return "fail_closed" if any(m in w for m in FAIL_CLOSED_MARKS) else "unclassified"


def events(decisions: Iterable[Row] | None = None, e8: Iterable[Row] | None = None,
           ftmo: Iterable[Row] | None = None) -> list[Row]:
    """One event per (account, sleeve, side, day): the first refusal of that leg that day."""
    decisions = list(_jsonl(DECISIONS) if decisions is None else decisions)
    e8 = _jsonl(E8_INTENTS) if e8 is None else e8
    ftmo = _jsonl(FTMO_INTENTS) if ftmo is None else ftmo
    out: dict[str, Row] = {}
    placed: dict[tuple[str, str, str], Row] = {}
    for r in decisions:
        if r.get("taken") or r.get("outcome") == "EXECUTED":
            placed.setdefault((str(r.get("sleeve") or r.get("strategy_id")), str(r.get("side")),
                               str(r.get("time") or r.get("decided_at") or "")[:10]), r)

    def put(acct: str, sleeve: str, side: str, at: str, row: Row, symbol: str,
            kind: str) -> None:
        eid = f"{acct}|{sleeve}|{side}|{at[:10]}"
        if eid in out:
            return
        ev: Row = {"event_id": eid, "account": acct, "sleeve": sleeve, "side": side, "at": at,
                   "symbol": symbol, "kind": kind, "price": _f(row.get("price")),
                   "sl": _f(row.get("sl")), "tp": _f(row.get("tp")), "lot": _f(row.get("lot")),
                   "risk_frac": _f(row.get("risk_frac")),
                   "risk_usd": _f(row.get("missed_growth_risk_usd")),
                   "why": row.get("detail") or row.get("why"), "sibling": None}
        other = {"buy_stop": "sell_stop", "sell_stop": "buy_stop"}.get(side)
        sib = placed.get((sleeve, other, at[:10])) if other and acct == "fusion" else None
        if sib is not None:
            ev["sibling"] = {"side": other, "price": _f(sib.get("price")),
                             "at": sib.get("time") or sib.get("decided_at")}
        out[eid] = ev

    for r in decisions:
        if r.get("reason") == "cross_account_opposite" or \
                r.get("first_blocking_gate") == "cross_account_opposite":
            put("fusion", str(r.get("sleeve") or r.get("strategy_id")), str(r.get("side")),
                str(r.get("time") or r.get("decided_at") or ""), r,
                str(r.get("symbol") or "XAUUSD"), kind_of(r.get("detail") or r.get("why")))
    for r in e8:
        if r.get("rail") == "cross_account_opposite":
            put("e8", str(r.get("window")), str(r.get("side")), str(r.get("at") or ""), r,
                str(r.get("symbol") or "XAUUSD"), kind_of(r.get("why")))
    for r in ftmo:
        if r.get("reason") == "opposite_exposure":
            put("ftmo", str(r.get("window")), str(r.get("side") or "?"), str(r.get("at") or ""),
                r, str(r.get("symbol") or "XAUUSD"), "ftmo_follow_rule")
    return sorted(out.values(), key=lambda e: e["at"])


def _meta(symbol: str) -> Row:
    try:
        u = json.loads((UNI / "universe.json").read_text("utf-8"))
        m = u.get(symbol) if isinstance(u, dict) else None
        return m if isinstance(m, dict) else {}
    except (OSError, ValueError):
        return {}


def _point(symbol: str) -> float | None:
    d = _meta(symbol).get("digits")
    return 10.0 ** -int(d) if isinstance(d, int) else None


def _anchor() -> Any:
    try:
        from research import bars_state as bs
    except Exception:
        return None
    return bs if bs.ANCHOR is not None else None


def _fills(side: str, price: float, bid_h: float, bid_l: float, sp: float) -> bool:
    long = side.startswith("buy")
    hi, lo = (bid_h + sp, bid_l + sp) if long else (bid_h, bid_l)
    if side.endswith("_stop"):
        return hi >= price if long else lo <= price
    return lo <= price if long else hi >= price


def counterfactual(ev: Mapping[str, Any], bars: Any, *, point: float | None = None,
                   clock: Any = _NOT_READ, directions: Any = _NOT_READ) -> Row:
    """{status, r, exit, ...} for one refused pending entry, by the bracket rules."""
    side = str(ev.get("side") or "")
    p, sl, tp = ev.get("price"), ev.get("sl"), ev.get("tp")
    if side not in ("buy_stop", "sell_stop", "buy_limit", "sell_limit"):
        return {"status": "UNMEASURED_SIDE_UNKNOWN", "r": None,
                "why": f"side {side!r} is not a pending entry"}
    if p is None or sl is None or tp is None or abs(p - sl) == 0:
        return {"status": "UNMEASURED_NO_GEOMETRY", "r": None,
                "why": "the refusal row carries no entry/stop/target"}
    clock = _anchor() if clock is _NOT_READ else clock
    if clock is None:
        return {"status": "UNMEASURED_NO_ANCHOR", "r": None,
                "why": "no server anchor: broker-stamped bars cannot be placed in UTC"}
    if directions is _NOT_READ:
        try:
            from mt5desk import gold_oco as oco
            directions, _ = oco.read_directions()
        except Exception:
            directions = None
    if directions is None:
        return {"status": "UNMEASURED_OCO", "r": None,
                "why": "the gold_oco direction state is unreadable"}
    if bars is None or len(bars) == 0:
        return {"status": "UNMEASURED_NO_BARS", "r": None, "why": "no M1 bars for the symbol"}
    t0 = _utc(ev.get("at"))
    if t0 is None:
        return {"status": "UNMEASURED_NO_TIME", "r": None, "why": "unreadable refusal time"}
    close = t0.replace(hour=CLOSE_UTC[0], minute=CLOSE_UTC[1], second=0, microsecond=0)
    if close <= t0:
        close += timedelta(days=1)
    t0w, closew = clock.utc_to_broker(t0), clock.utc_to_broker(close)
    if t0w is None or closew is None:
        return {"status": "UNMEASURED_NO_ANCHOR", "r": None, "why": "anchor conversion failed"}
    idx = bars.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    start = t0w.replace(second=0, microsecond=0)
    if start < t0w:
        start += BAR
    last_open = closew - BAR
    if idx.max() < last_open:
        return {"status": "PENDING", "r": None, "why": "bars do not yet reach the close"}
    mask = (idx >= start) & (idx <= last_open)
    w = bars[mask]
    walls = idx[mask]
    # COVERAGE (audit v3 must-fix 1): an empty or holed window is not "never filled". The bars
    # must reach from the refusal minute to the last bar before the close with no hole longer
    # than MAX_BAR_GAP (wide enough for the daily rollover break, narrow enough for a lost day
    # or a feed that starts mid-afternoon); otherwise UNMEASURED_BAR_GAP, retried next run.
    if len(walls) == 0:
        return {"status": "UNMEASURED_BAR_GAP", "r": None, "why": "no bars in the window"}
    edges = [walls[0] - start, last_open - walls[-1]]
    holes = [walls[k + 1] - walls[k] for k in range(len(walls) - 1)]
    worst = max([*edges, *holes])
    if worst > MAX_BAR_GAP:
        return {"status": "UNMEASURED_BAR_GAP", "r": None,
                "why": f"a {worst} hole in the bars between the refusal and the close"}
    if "spread" in w.columns and point is None:
        return {"status": "UNMEASURED_NO_POINT", "r": None, "why": "no point size for spread"}
    sp_col = (w["spread"].astype(float) * float(point or 0.0)).tolist() if "spread" in w.columns \
        else [0.0] * len(w)
    his, los, cls = (w["high"].astype(float).tolist(), w["low"].astype(float).tolist(),
                     w["close"].astype(float).tolist())
    long = side.startswith("buy")
    risk = abs(p - sl)

    def first(side_: str, price: float) -> int | None:
        for k in range(len(w)):
            if _fills(side_, price, his[k], los[k], sp_col[k]):
                return k
        return None

    k0 = first(side, p)
    if k0 is None:
        return {"status": "MEASURED", "filled": False, "exit": "never_filled", "r": 0.0}
    fill_wall = walls[k0].to_pydatetime()
    fill_utc = clock.broker_to_utc(fill_wall)
    sib = ev.get("sibling") or {}
    if sib.get("price") is not None:
        ks = first(str(sib["side"]), float(sib["price"]))
        if ks is not None and ks <= k0:
            return {"status": "MEASURED", "filled": False, "exit": "cancelled_by_oco",
                    "r": 0.0, "cancelled_by": "sibling", "sibling_fill": str(walls[ks])}
    want = "long" if long else "short"
    for d in (t0w.date().isoformat(),):        # gold_oco keys days by the BROKER date
        e = (directions or {}).get(d)
        if not isinstance(e, dict):
            continue
        dtn = str(e.get("direction") or "").lower()
        dtn = "long" if dtn in ("long", "buy") else "short" if dtn in ("short", "sell") else dtn
        at = _utc(e.get("first_fill_at"))
        if dtn and dtn != want and (at is None or fill_utc is None or at <= fill_utc):
            return {"status": "MEASURED", "filled": False, "exit": "cancelled_by_oco", "r": 0.0,
                    "cancelled_by": f"gold_oco direction {dtn} ({e.get('first_fill_lane')})"}
    for k in range(k0, len(w)):
        bid_h, bid_l, s = his[k], los[k], sp_col[k]
        if long:
            sl_hit, tp_hit = bid_l <= sl, bid_h >= tp
        else:
            sl_hit, tp_hit = bid_h + s >= sl, bid_l + s <= tp
        if sl_hit:
            return {"status": "MEASURED", "filled": True, "filled_at_broker": str(fill_wall),
                    "exit": "sl", "exit_at_broker": str(walls[k]), "r": -1.0}
        if tp_hit:
            return {"status": "MEASURED", "filled": True, "filled_at_broker": str(fill_wall),
                    "exit": "tp", "exit_at_broker": str(walls[k]),
                    "r": round(abs(tp - p) / risk, 6)}
    last = cls[-1] if long else cls[-1] + sp_col[-1]
    r = ((last - p) if long else (p - last)) / risk
    return {"status": "MEASURED", "filled": True, "filled_at_broker": str(fill_wall),
            "exit": "time", "exit_at_broker": str(walls[-1]), "r": round(r, 6)}


def risk_usd(ev: Mapping[str, Any]) -> float | None:
    if ev.get("risk_usd") is not None:
        return float(ev["risk_usd"])
    c = _f(_meta(str(ev.get("symbol") or "").upper()).get("contract_size")) or \
        (100.0 if str(ev.get("symbol") or "").upper() == "XAUUSD" else None)
    if c and ev.get("lot") is not None and ev.get("price") is not None and ev.get("sl") is not None:
        return round(abs(float(ev["price"]) - float(ev["sl"])) * float(ev["lot"]) * c, 4)
    return None


def risk_frac(ev: Mapping[str, Any], cert: Mapping[str, Any]) -> float | None:
    if ev.get("risk_frac") is not None:
        return float(ev["risk_frac"])
    import re
    book = cert.get(str(ev.get("account"))) or {}
    s = str(ev.get("sleeve") or "")
    for k in (s, re.sub(r"_v\d+$", "", s)):
        v = _f(book.get(k)) if isinstance(book, dict) else None
        if v:
            return v
    return None


def load_m1(symbol: str) -> Any:
    try:
        import pandas as pd
        df = pd.read_parquet(UNI / f"{symbol}_M1.parquet")
    except Exception:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, errors="coerce"))
    return df[~df.index.isna()].sort_index()


def run(*, evs: list[Row] | None = None, bars_for: Any = None, out: Path = OUT,
        summary: Path = SUMMARY, clock: Any = _NOT_READ, directions: Any = _NOT_READ,
        cert: Mapping[str, Any] | None = None, now: datetime | None = None) -> Row:
    evs = events() if evs is None else evs
    now = now or datetime.now(tz=UTC)
    bars_for = bars_for or load_m1
    if cert is None:
        try:
            cert = json.loads(CERT_BOOK.read_text("utf-8"))
        except (OSError, ValueError):
            cert = {}
    done = {r.get("event_id") for r in _jsonl(out)}
    cache: dict[str, Any] = {}
    appended, pending, gaps = [], [], []
    for ev in evs:
        if ev["event_id"] in done:
            continue
        t = _utc(ev.get("at"))
        if t is not None and now - t > timedelta(days=OCO_KEEP_DAYS):
            # gold_oco keeps KEEP_DAYS of direction state; past it the OCO cannot be judged.
            # A TERMINAL row, written once (the done-set skips it after), so a leg that was
            # never priced -- expired, or gapped until it expired -- stops re-entering pending.
            appended.append({**ev, "status": "UNMEASURED_OCO_EXPIRED", "r": None,
                             "terminal": True, "missed_usd": None,
                             "why": f"older than gold_oco KEEP_DAYS={OCO_KEEP_DAYS}",
                             "measured_utc": now.isoformat(timespec="seconds")})
            gaps.append(ev["event_id"])
            continue
        sym = str(ev.get("symbol") or "XAUUSD").upper()
        if sym not in cache:
            cache[sym] = bars_for(sym)
        pt = _point(sym) or (0.01 if sym == "XAUUSD" else None)
        cf = counterfactual(ev, cache[sym], point=pt, clock=clock, directions=directions)
        if cf["status"] in RETRY:
            pending.append({**ev, **cf})
            continue
        ru = risk_usd(ev)
        row = {**ev, **cf, "risk_usd": ru, "risk_frac": risk_frac(ev, cert or {}),
               "missed_usd": (None if cf.get("r") is None or ru is None
                              else round(float(cf["r"]) * ru, 4)),
               "measured_utc": datetime.now(tz=UTC).isoformat(timespec="seconds")}
        if cf["status"].startswith("UNMEASURED"):
            gaps.append(ev["event_id"])
        appended.append(row)
    if appended:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            for r in appended:
                fh.write(json.dumps(r, default=str) + "\n")
    rows = _jsonl(out)
    priced = [r for r in rows if r.get("status") == "MEASURED" and r.get("r") is not None]
    by_kind: dict[str, int] = {}
    for r in priced:
        by_kind[str(r.get("kind"))] = by_kind.get(str(r.get("kind")), 0) + 1
    usd = [float(r["missed_usd"]) for r in priced if r.get("missed_usd") is not None]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "report_only": True, "events": len(evs), "appended": len(appended),
           "pending": pending, "pending_count": len(pending),
           "no_geometry": gaps, "no_geometry_count": len(gaps),
           "rows": len(rows), "priced_rows": len(priced), "priced_by_kind": by_kind,
           "sum_missed_usd": round(sum(usd), 4),
           "sum_missed_usd_by_kind": {k: round(sum(float(r["missed_usd"]) for r in priced
                                                   if str(r.get("kind")) == k
                                                   and r.get("missed_usd") is not None), 4)
                                      for k in by_kind},
           "sum_r": round(sum(float(r["r"]) for r in priced), 6),
           "verdict": "MEASURED" if priced else UNMEASURED}
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = run()
    print(f"fence_missed_trades: {doc['events']} event(s), {doc['appended']} appended, "
          f"{doc['pending_count']} pending, {doc['priced_rows']} priced, {doc['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
