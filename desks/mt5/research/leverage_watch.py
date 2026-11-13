"""K3: THE ACCOUNTS' LEVERAGE, READ EVERY DAY -- and what a cut does to every sized order.

    Finding K3 (Stop the live desk bleeding; GAP_MAP, 2026-11-13): "nothing reads the trading
    accounts' leverage each day; a broker leverage cut before an event or weekend silently changes
    margin feasibility for every sized order."

WHY. Brokers and prop firms cut leverage without notice: before a central-bank decision, an
election, a long weekend, or per symbol (gold and indices first). The desk's sizing is in heat
(risk at the stop), so a cut does not change the lot the allocator wants -- it changes whether the
account can CARRY that lot. A sized order that no longer fits is rejected at the venue (retcode
10019, no money) or, worse, fits alone and not beside the others, so the second leg of a book is
refused and the book trades a fragment of what was certified. Nothing measured any of it.

WHAT IT DOES. Two halves, because the terminal is reachable only where the terminal runs:

  READ   `record_mt5(mt5)` is called by the processes that already hold a terminal
         (`ops/publish_account_state.py`, `prop/ftmo_venue_reader.py`). It reads, read-only:
         account leverage, margin mode, stop-out and margin-call levels, and for every symbol the
         desk sizes: contract size, the venue's own margin for one lot each side
         (`order_calc_margin`, which already folds in symbol-specific leverage), and the
         symbol's initial/maintenance margin fields. `record_tradelocker()` does the same for E8
         (TradeLocker has no terminal; HTTP, read-only, the adapter's own rate-limit budget).
         A snapshot is appended to `data/leverage_history.jsonl` when anything changed or an hour
         passed -- so a cut is seen within the reader's own cadence (5 min for FTMO).
         The account is named by venue only; no login, no key, nothing identifying.

  ASSESS `python research/leverage_watch.py --once` (hourly leg, no terminal needed) reads the
         history and the sized intents of the last 30 days, and publishes
         `reports/LEVERAGE_WATCH.json`:
           * per venue: leverage now, 24 h ago and 7 d ago; every CUT / RAISE in the window,
             account-level and per symbol (margin per lot moving by >= 15%)
           * feasibility: every sleeve's largest recent sized order re-margined at TODAY's
             margin per lot, summed as if all were open at once, against the margin the account
             can carry before its margin-call level -- per order and for the book
           * stress: the same at half today's leverage (the typical pre-event/weekend cut), and
             whether we are in such a window now (Friday from 12:00 UTC to the Sunday open, or a
             high-impact event within 24 h from `data/calendars`)
           * status GREEN / AMBER / RED with the reason, and UNMEASURED per venue when the
             history is absent or older than its cadence allows

AUTHORITY. None. It changes no limit, no lot and no permission (those stay the principal's). The
consumer is the halt/rail layer and the allocator's margin clause, which already measure margin
live at solve time; this adds the history, the per-symbol view and the forward stress they lack.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
REPORTS = DESK / "reports"
HISTORY = DATA / "leverage_history.jsonl"
OUT = REPORTS / "LEVERAGE_WATCH.json"
CALENDARS = DATA / "calendars"
INTENT_FILES: dict[str, Path] = {
    "main": DATA / "order_intents.jsonl",
    "ftmo": DATA / "ftmo_exec_intents.jsonl",
    "e8": DATA / "e8_intents.jsonl",
}
#: The symbols always read, so a symbol the desk has not traded this month is still watched.
CORE_SYMBOLS = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
                "NZDUSD", "EURJPY", "GBPJPY", "AUDJPY", "US500", "US30", "US100", "GER40",
                "UK100", "JP225", "XTIUSD", "XBRUSD")
#: A margin-per-lot move at or beyond this ratio is a CUT (up) or RAISE (down) of leverage.
CHANGE_RATIO = 1.15
#: Re-record an unchanged snapshot at least this often, so staleness is distinguishable from
#: "nothing changed".
HEARTBEAT_S = 3600
#: An assessment needs a snapshot this fresh per venue, else that venue is UNMEASURED.
FRESH_S = 6 * 3600
INTENT_DAYS = 30
#: History retention: the 7-day change window and the 24 h / 7 d comparisons need far less.
RETENTION_DAYS = 45
MAX_ROWS = 20_000
STRESS_FACTOR = 2.0          # margin per lot doubles = leverage halves
EVENT_WINDOW_H = 24
#: Do not let a stress or concurrent book use more than this share of the margin the account
#: can carry before margin call. Same constant the allocator's survival envelope uses for margin.
MAX_MARGIN_USE = 0.50


def _now() -> datetime:
    return datetime.now(UTC)


def venue_label(server: str | None, company: str | None = None) -> str:
    s = f"{server or ''} {company or ''}".lower()
    if "ftmo" in s:
        return "ftmo"
    if "fusion" in s:
        return "fusion"
    if "e8" in s or "tradelocker" in s:
        return "e8"
    return (server or "unknown").split("-")[0].lower() or "unknown"


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ---------------------------------------------------------------------------- READ
def symbols_to_read(extra: Iterable[str] = ()) -> list[str]:
    syms = set(CORE_SYMBOLS) | {str(s).upper() for s in extra}
    since = _now() - timedelta(days=INTENT_DAYS)
    for p in INTENT_FILES.values():
        for r in _intents(p, since):
            syms.add(str(r["symbol"]).upper())
    return sorted(syms)


def mt5_snapshot(mt5: Any, symbols: Sequence[str]) -> dict[str, Any] | None:
    """One read-only snapshot from an attached MetaTrader5 module. Never sends anything."""
    acc = mt5.account_info()
    if acc is None:
        return None
    sym_rows: dict[str, Any] = {}
    for sym in symbols:
        info = mt5.symbol_info(sym)
        if info is None:
            continue
        with contextlib.suppress(Exception):
            if not getattr(info, "visible", True):
                mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        ask = _f(getattr(tick, "ask", None)) if tick is not None else None
        bid = _f(getattr(tick, "bid", None)) if tick is not None else None
        row: dict[str, Any] = {
            "contract_size": _f(getattr(info, "trade_contract_size", None)),
            "margin_initial": _f(getattr(info, "margin_initial", None)),
            "margin_maintenance": _f(getattr(info, "margin_maintenance", None)),
            "margin_hedged": _f(getattr(info, "margin_hedged", None)),
            "volume_min": _f(getattr(info, "volume_min", None)),
            "price": ask,
        }
        for side, otype, px in (("buy", getattr(mt5, "ORDER_TYPE_BUY", 0), ask),
                                ("sell", getattr(mt5, "ORDER_TYPE_SELL", 1), bid)):
            m = None
            if px:
                with contextlib.suppress(Exception):
                    m = _f(mt5.order_calc_margin(otype, sym, 1.0, px))
            row[f"margin_per_lot_{side}"] = m
        if row["margin_per_lot_buy"] and row["contract_size"] and ask:
            notional = row["contract_size"] * ask
            row["effective_leverage"] = notional / row["margin_per_lot_buy"]
        sym_rows[sym] = row
    server = str(getattr(acc, "server", "") or "")
    return {
        "at": _now().isoformat(timespec="seconds"),
        "venue": venue_label(server, str(getattr(acc, "company", "") or "")),
        "server": server, "platform": "mt5",
        "currency": str(getattr(acc, "currency", "") or ""),
        "leverage": _f(getattr(acc, "leverage", None)),
        "margin_mode": getattr(acc, "margin_mode", None),
        "margin_so_call": _f(getattr(acc, "margin_so_call", None)),
        "margin_so_so": _f(getattr(acc, "margin_so_so", None)),
        "margin_so_mode": getattr(acc, "margin_so_mode", None),
        "equity": _f(getattr(acc, "equity", None)),
        "margin": _f(getattr(acc, "margin", None)),
        "margin_free": _f(getattr(acc, "margin_free", None)),
        "symbols": sym_rows,
    }


def tradelocker_snapshot(venue: Any, symbols: Sequence[str]) -> dict[str, Any]:
    """E8 on TradeLocker: whatever leverage and margin fields the API publishes, by name only.
    Fields the API does not carry are absent, never guessed."""
    st = dict(venue._api.get_account_state())
    acct = {k: _f(v) for k, v in st.items()
            if any(t in str(k).lower() for t in ("leverage", "margin", "equity", "balance"))
            and _f(v) is not None}
    sym_rows: dict[str, Any] = {}
    for sym in symbols:
        try:
            det = venue.details(sym)
        except Exception:
            continue
        row = {k: _f(v) for k, v in dict(det).items()
               if any(t in str(k).lower() for t in ("leverage", "margin", "contract", "lotsize"))
               and _f(v) is not None}
        if row:
            sym_rows[sym] = row
    lev = next((v for k, v in acct.items() if "leverage" in k.lower()), None)
    return {"at": _now().isoformat(timespec="seconds"), "venue": "e8", "platform": "tradelocker",
            "leverage": lev, "account_fields": acct, "symbols": sym_rows,
            "equity": acct.get("equity") or acct.get("projectedBalance")}


def _fingerprint(snap: Mapping[str, Any]) -> str:
    keys = ("leverage", "margin_so_call", "margin_so_so", "margin_mode")
    parts = [str(snap.get(k)) for k in keys]
    for s, r in sorted((snap.get("symbols") or {}).items()):
        m = r.get("margin_per_lot_buy") or r.get("margin_initial") or r.get("leverage")
        if m:
            parts.append(f"{s}:{float(m) / max(float(r.get('price') or 1.0), 1e-12):.6g}")
    return "|".join(parts)


def last_snapshot(venue: str, path: Path = HISTORY) -> dict[str, Any] | None:
    last = None
    for r in _read_jsonl(path):
        if r.get("venue") == venue:
            last = r
    return last


def record(snap: dict[str, Any] | None, path: Path = HISTORY) -> bool:
    """Append when anything changed or the heartbeat is due. Returns True when written."""
    if not snap:
        return False
    prev = last_snapshot(str(snap.get("venue")), path)
    fp = _fingerprint(snap)
    if prev is not None:
        try:
            age = (datetime.fromisoformat(str(snap["at"]))
                   - datetime.fromisoformat(str(prev["at"]))).total_seconds()
        except (KeyError, ValueError):
            age = float("inf")
        if prev.get("fingerprint") == fp and age < HEARTBEAT_S:
            return False
    snap = {**snap, "fingerprint": fp}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(snap, default=str) + "\n")
    _trim(path)
    return True


def _trim(path: Path, keep_days: int = RETENTION_DAYS, max_rows: int = MAX_ROWS) -> None:
    """Bounded by construction: past `max_rows`, keep only the last `keep_days` (never the latest
    snapshot of a venue, so a venue that went quiet is still seen as stale, not as absent)."""
    rows = _read_jsonl(path)
    if len(rows) <= max_rows:
        return
    cut = _now() - timedelta(days=keep_days)
    last_by_venue = {str(r.get("venue")): i for i, r in enumerate(rows)}
    kept = [r for i, r in enumerate(rows)
            if (_ts(r.get("at")) or cut) >= cut or i in set(last_by_venue.values())]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(r, default=str) + "\n" for r in kept)
    os.replace(tmp, path)


def record_mt5(mt5: Any, extra_symbols: Iterable[str] = (), path: Path = HISTORY) -> str:
    """The hook for a process that already holds a terminal. Never raises; returns what it did."""
    try:
        snap = mt5_snapshot(mt5, symbols_to_read(extra_symbols))
        if snap is None:
            return "account_info unanswered; nothing recorded"
        wrote = record(snap, path)
        return (f"{snap['venue']}: leverage {snap.get('leverage')}, "
                f"{len(snap['symbols'])} symbols, {'recorded' if wrote else 'unchanged'}")
    except Exception as exc:
        return f"leverage read failed: {type(exc).__name__}"


def record_tradelocker(path: Path = HISTORY) -> str:
    try:
        from prop.tradelocker_venue import TradeLockerVenue

        venue = TradeLockerVenue().connect()
        wrote = record(tradelocker_snapshot(venue, symbols_to_read()), path)
        return f"e8: {'recorded' if wrote else 'unchanged'}"
    except Exception as exc:
        return f"e8 leverage read failed: {type(exc).__name__}"


# ---------------------------------------------------------------------------- ASSESS
def _read_jsonl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                with contextlib.suppress(ValueError):
                    r = json.loads(line)
                    if isinstance(r, dict):
                        out.append(r)
    except OSError:
        pass
    return out


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _intents(p: Path, since: datetime) -> list[dict[str, Any]]:
    out = []
    for r in _read_jsonl(p):
        t = _ts(r.get("time") or r.get("at"))
        lot = _f(r.get("lot"))
        if t is None or t < since or not lot or lot <= 0 or not r.get("symbol"):
            continue
        out.append(r)
    return out


def sized_orders(venue: str, server: str | None, now: datetime,
                 files: Mapping[str, Path] = INTENT_FILES) -> dict[tuple[str, str], dict[str, Any]]:
    """{(sleeve, symbol): {lot, side}} -- each sleeve's LARGEST sized order in the window, the one
    that must still fit. Intents are matched to the venue by their file and, for the main
    ledger, by the server they were sent to."""
    since = now - timedelta(days=INTENT_DAYS)
    rows: list[dict[str, Any]] = []
    if venue in files:
        rows = _intents(files[venue], since)
    else:
        rows = [r for r in _intents(files["main"], since)
                if not server or not r.get("server") or str(r.get("server")) == server]
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        k = (str(r.get("sleeve") or "?"), str(r["symbol"]).upper())
        lot = float(r["lot"])
        side = "sell" if str(r.get("side") or "").lower().startswith("sell") else "buy"
        if k not in out or lot > out[k]["lot"]:
            out[k] = {"lot": lot, "side": side}
    return out


def in_event_window(now: datetime, calendars: Path = CALENDARS) -> tuple[bool, str]:
    wd, h = now.weekday(), now.hour
    if (wd == 4 and h >= 12) or wd == 5 or (wd == 6 and h < 22):
        return True, "weekend window (Friday 12:00 UTC to the Sunday open)"
    horizon = now + timedelta(hours=EVENT_WINDOW_H)
    for p in sorted(calendars.glob("*.json")) if calendars.exists() else []:
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc if isinstance(doc, list) else (doc.get("events") or doc.get("rows") or [])
        for e in rows if isinstance(rows, list) else []:
            if not isinstance(e, dict):
                continue
            t = _ts(e.get("time") or e.get("at") or e.get("date") or e.get("datetime"))
            if t is not None and now <= t <= horizon:
                return True, f"{p.stem} event at {t.isoformat()}"
    return False, "no weekend and no calendared event within 24 h"


def changes(snaps: Sequence[dict[str, Any]], now: datetime, days: int = 7) -> list[dict[str, Any]]:
    """Every leverage CUT / RAISE between consecutive snapshots in the window."""
    since = now - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for a, b in pairwise(snaps):
        tb = _ts(b.get("at"))
        if tb is None or tb < since:
            continue
        la, lb = _f(a.get("leverage")), _f(b.get("leverage"))
        if la and lb and la != lb:
            out.append({"at": b["at"], "scope": "account", "from": la, "to": lb,
                        "kind": "CUT" if lb < la else "RAISE"})
        sa, sb = a.get("symbols") or {}, b.get("symbols") or {}
        for sym in set(sa) & set(sb):
            ma = _per_price(sa[sym])
            mb = _per_price(sb[sym])
            if ma and mb:
                r = mb / ma
                if r >= CHANGE_RATIO or r <= 1.0 / CHANGE_RATIO:
                    out.append({"at": b["at"], "scope": sym, "margin_ratio": round(r, 3),
                                "kind": "CUT" if r > 1 else "RAISE"})
    return out


def _per_price(row: Mapping[str, Any]) -> float | None:
    """Margin per lot per unit price: a price move alone does not read as a leverage change."""
    m = _f(row.get("margin_per_lot_buy"))
    p = _f(row.get("price"))
    if m and p:
        return m / p
    lev = _f(row.get("leverage"))
    return (1.0 / lev) if lev else None


def feasibility(snap: Mapping[str, Any], orders: Mapping[tuple[str, str], dict[str, Any]],
                stress: float = 1.0) -> dict[str, Any]:
    eq = _f(snap.get("equity"))
    used = _f(snap.get("margin")) or 0.0
    call = _f(snap.get("margin_so_call")) or 100.0
    if not eq or eq <= 0:
        return {"status": "UNMEASURED", "why": "no equity in the snapshot"}
    capacity = eq / (call / 100.0) * MAX_MARGIN_USE      # margin the book may use
    rows, unpriced, total = [], [], 0.0
    for (sleeve, sym), o in sorted(orders.items()):
        srow = (snap.get("symbols") or {}).get(sym) or {}
        mpl = _f(srow.get(f"margin_per_lot_{o['side']}")) or _f(srow.get("margin_per_lot_buy"))
        if not mpl:
            unpriced.append(f"{sleeve}:{sym}")
            continue
        need = mpl * o["lot"] * stress
        total += need
        rows.append({"sleeve": sleeve, "symbol": sym, "lot": o["lot"], "margin": round(need, 2),
                     "fits_alone": used + need <= capacity})
    infeasible = [r for r in rows if not r["fits_alone"]]
    return {"status": "MEASURED", "stress_factor": stress, "equity": eq,
            "margin_capacity": round(capacity, 2), "margin_in_use": round(used, 2),
            "book_margin_if_all_open": round(total, 2),
            "book_fits": used + total <= capacity,
            "book_use_share": round((used + total) / capacity, 4) if capacity > 0 else None,
            "orders": len(rows), "orders_infeasible_alone": infeasible,
            "unpriced_orders": unpriced}


def assess(now: datetime | None = None, history: Path = HISTORY,
           files: Mapping[str, Path] = INTENT_FILES, calendars: Path = CALENDARS
           ) -> dict[str, Any]:
    now = now or _now()
    snaps = _read_jsonl(history)
    by_venue: dict[str, list[dict[str, Any]]] = {}
    for s in snaps:
        by_venue.setdefault(str(s.get("venue")), []).append(s)
    window, window_why = in_event_window(now, calendars)
    venues: dict[str, Any] = {}
    worst = "GREEN"
    reasons: list[str] = []
    rank = {"GREEN": 0, "AMBER": 1, "RED": 2, "UNMEASURED": 1}
    for v, rows in sorted(by_venue.items()):
        rows.sort(key=lambda r: str(r.get("at")))
        cur = rows[-1]
        age = (now - (_ts(cur.get("at")) or now)).total_seconds()
        if age > FRESH_S:
            venues[v] = {"status": "UNMEASURED",
                         "why": f"last snapshot {age / 3600:.1f} h old (> {FRESH_S / 3600:.0f} h)"}
            worst = max(worst, "UNMEASURED", key=lambda s: rank[s])
            reasons.append(f"{v}: stale leverage read")
            continue

        def lev_at(hours: float, rows: list[dict[str, Any]] = rows) -> float | None:
            cut = now - timedelta(hours=hours)
            past = [r for r in rows if (_ts(r.get("at")) or now) <= cut]
            return _f(past[-1].get("leverage")) if past else None

        ch = changes(rows, now)
        orders = sized_orders(v, cur.get("server"), now, files)
        base = feasibility(cur, orders)
        stressed = feasibility(cur, orders, STRESS_FACTOR)
        cuts_24h = [c for c in ch if c["kind"] == "CUT"
                    and (_ts(c["at"]) or now) >= now - timedelta(hours=24)]
        status, why = "GREEN", "leverage steady; every sized order fits at today's margin"
        if base.get("status") == "MEASURED" and (base["orders_infeasible_alone"]
                                                 or not base["book_fits"]):
            status, why = "RED", "a sized order or the concurrent book does not fit TODAY"
        elif cuts_24h:
            status, why = "RED", f"{len(cuts_24h)} leverage cut(s) in the last 24 h"
        elif window and stressed.get("status") == "MEASURED" and not stressed["book_fits"]:
            status, why = "AMBER", f"in a cut-prone window ({window_why}) the book would not fit " \
                                   "at half leverage"
        elif base.get("unpriced_orders"):
            status, why = "AMBER", "some sized symbols have no margin reading"
        venues[v] = {"status": status, "why": why, "snapshot_at": cur.get("at"),
                     "platform": cur.get("platform"), "server": cur.get("server"),
                     "leverage_now": _f(cur.get("leverage")), "leverage_24h_ago": lev_at(24),
                     "leverage_7d_ago": lev_at(24 * 7),
                     "margin_call_level": _f(cur.get("margin_so_call")),
                     "stop_out_level": _f(cur.get("margin_so_so")),
                     "symbols_read": len(cur.get("symbols") or {}),
                     "effective_leverage_by_symbol": {
                         s: round(float(r["effective_leverage"]), 1)
                         for s, r in (cur.get("symbols") or {}).items()
                         if r.get("effective_leverage")},
                     "changes_7d": ch, "feasibility": base, "stress_half_leverage": stressed}
        if rank[status] > rank[worst]:
            worst = status
        if status != "GREEN":
            reasons.append(f"{v}: {why}")
    if not venues:
        worst, reasons = "UNMEASURED", ["no leverage snapshot on this host yet"]
    return {"at": now.isoformat(timespec="seconds"), "status": worst, "why": reasons,
            "cut_prone_window": {"now": window, "why": window_why},
            "venues": venues,
            "authority": "none: report only. No limit, lot or permission is changed here."}


def write(doc: Mapping[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, default=str)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="assess the history (no terminal)")
    ap.add_argument("--read-e8", action="store_true",
                    help="also take one read-only E8 TradeLocker snapshot first")
    ap.add_argument("--budget-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    if a.read_e8:
        last = last_snapshot("e8")
        t = _ts((last or {}).get("at"))
        if t is None or (_now() - t).total_seconds() >= HEARTBEAT_S:
            print(record_tradelocker())
    doc = assess()
    write(doc)
    print(f"leverage watch: {doc['status']} -- {'; '.join(doc['why']) or 'all venues GREEN'}")
    for v, r in doc["venues"].items():
        print(f"  {v:<8} {r['status']:<10} leverage {r.get('leverage_now')} "
              f"(24h {r.get('leverage_24h_ago')}) {r.get('why')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
