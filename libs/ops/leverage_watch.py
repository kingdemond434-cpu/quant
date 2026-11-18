"""Watch the trading account's leverage and name every change (CRO finding K3, 2026-11-13).

WHY. Brokers cut leverage before events and weekends. Margin feasibility for every sized order
moves with it, and until now nothing on the desk kept a reading from one pass to the next: only
`financing_lab` read `account_info().leverage`, used it for that one pass, and forgot it. A cut
was therefore visible only as orders refused for margin.

WHAT. `observe` keeps a small history (`desks/mt5/reports/ACCOUNT_LEVERAGE.json`): the last
reading, when it was read, and every change with its old and new value. A change emits an
`ACCOUNT_LEVERAGE_CHANGED` event row (priority 2, so the pager and the board see it). A pass
with no readable leverage writes nothing new and the verdict ages to STALE after
`STALE_AFTER_H`; an absent reading is never recorded as a change. The file carries the venue
label only -- no login, server or account number (the repository is public).

PER SYMBOL (folded in from #1145, 2026-11-18). A broker cuts leverage per symbol too -- gold and
the indices first -- and the account figure does not move when it does. `symbol_margins` reads,
for the core symbols and every symbol held, the venue's own margin for one lot
(`order_calc_margin`, which folds in symbol-specific leverage) and the effective leverage it
implies; `observe` keeps the last per symbol and names a move of `CHANGE_RATIO` or more as a CUT
(margin per lot up) or a RAISE (down), with its own event row.

MULTI-VENUE (ported from #1145, 2026-11-18). One file, one row per venue: `fusion` from
`research/financing_lab.py`, `ftmo` from `prop/ftmo_venue_reader.py` on the connection it already
holds (`observe_mt5`), and `e8` from `prop/e8_book.py` on the TradeLocker session that hourly pass
already opens (`observe_tradelocker`): no new login. TradeLocker's leverage and margin fields are
recorded BY KEY NAME (a value only when the key names a leverage, which is a ratio), and the read
runs under the caller's `--budget-s`.

FEASIBILITY (ported from #1145). Every order sized in the last `INTENT_DAYS` for the venue
(`order_intents.jsonl` for Fusion, `ftmo_exec_intents.jsonl`, `e8_intents.jsonl`) -- the largest
per (sleeve, symbol), the order that must still fit -- is re-margined at TODAY's margin per lot,
alone and as a book open all at once, against the margin the account may use before its
margin-call level (equity / (margin_so_call / 100) x `MAX_MARGIN_USE`), today and at half
leverage (margin per lot x `STRESS_FACTOR`). The half-leverage stress is FLAGGED only inside a
cut-prone window: Friday 12:00 UTC to the Sunday open, or a HIGH-IMPACT calendar row within
`EVENT_WINDOW_H`. Verdict per venue: GREEN / AT_RISK / UNMEASURED. A missing margin-call level,
an unreadable equity or zero matched intents is UNMEASURED, never a default and never GREEN.

PUBLIC REPOSITORY. The file carries ratios, verdicts and key names only: no equity, no money
margin amount (per lot or per order), no login, server or account number.

This is a REPORT. It sets no cap, no size and no veto (GROWTH_GOVERNANCE): the allocator already
reads the live leverage through `financing_lab.load_terms` on every pass.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "desks" / "mt5" / "data"
REPORT = ROOT / "desks" / "mt5" / "reports" / "ACCOUNT_LEVERAGE.json"
CALENDARS = DATA / "calendars"
#: Where each venue's sized orders are journalled.
INTENT_FILES: dict[str, Path] = {"fusion": DATA / "order_intents.jsonl",
                                 "ftmo": DATA / "ftmo_exec_intents.jsonl",
                                 "e8": DATA / "e8_intents.jsonl"}
VENUES = tuple(INTENT_FILES)
INTENT_DAYS = 30
#: Share of the margin the account carries before its margin call a book may use. The same
#: constant the allocator's survival envelope uses for margin.
MAX_MARGIN_USE = 0.50
STRESS_FACTOR = 2.0          # margin per lot doubles = leverage halves
EVENT_WINDOW_H = 24
HIGH_IMPACT = frozenset({"high", "3", "red", "h"})

STALE_AFTER_H = 36.0
MAX_CHANGES_KEPT = 200
#: The symbols always read, so one the desk has not traded this month is still watched.
CORE_SYMBOLS = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
                "NZDUSD", "EURJPY", "GBPJPY", "AUDJPY", "US500", "US30", "US100", "GER40",
                "UK100", "JP225", "XTIUSD", "XBRUSD")
#: A margin-per-lot move at or beyond this ratio is a CUT (up) or RAISE (down) of leverage.
CHANGE_RATIO = 1.15


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and v == v and v > 0 else None


def symbol_margins(mt5: Any, symbols: Any) -> dict[str, dict[str, Any]]:
    """{symbol: margin per lot buy/sell, contract size, effective leverage}, read-only from an
    attached MetaTrader5 module. Sends nothing; a symbol it cannot read is left out."""
    out: dict[str, dict[str, Any]] = {}
    for sym in dict.fromkeys(str(s).upper() for s in symbols if s):
        try:
            info = mt5.symbol_info(sym)
            if info is None:
                continue
            if getattr(info, "visible", True) is False:
                # Only a symbol outside Market Watch is selected: a select on a visible symbol
                # is a write to the terminal for nothing.
                with contextlib.suppress(Exception):
                    mt5.symbol_select(sym, True)
            tick = mt5.symbol_info_tick(sym)
            ask = _num(getattr(tick, "ask", None)) if tick is not None else None
            bid = _num(getattr(tick, "bid", None)) if tick is not None else None
            row: dict[str, Any] = {"contract_size": _num(getattr(info, "trade_contract_size",
                                                                 None))}
            for side, otype, px in (("buy", getattr(mt5, "ORDER_TYPE_BUY", 0), ask),
                                    ("sell", getattr(mt5, "ORDER_TYPE_SELL", 1), bid)):
                row[f"margin_per_lot_{side}"] = (_num(mt5.order_calc_margin(otype, sym, 1.0, px))
                                                 if px else None)
            m, cs = row["margin_per_lot_buy"], row["contract_size"]
            row["effective_leverage"] = round(cs * ask / m, 2) if m and cs and ask else None
        except Exception:
            continue
        if row.get("margin_per_lot_buy"):
            out[sym] = row
    return out


def _public_symbol(row: Mapping[str, Any]) -> dict[str, Any]:
    """What a symbol row may publish: ratios and the contract size, never a money margin."""
    return {k: row.get(k) for k in ("effective_leverage", "contract_size")
            if row.get(k) is not None}


def _symbol_changes(prev: dict[str, Any], now_rows: dict[str, dict[str, Any]],
                    at: str) -> list[dict[str, Any]]:
    """A CUT or RAISE per symbol whose effective leverage moved by CHANGE_RATIO or more. Read off
    the effective leverage (notional / margin per lot), so a price move alone is not a change and
    no money amount needs keeping from one pass to the next."""
    out = []
    for sym, row in now_rows.items():
        old = _num((prev.get(sym) or {}).get("effective_leverage"))
        new = _num(row.get("effective_leverage"))
        if old is None or new is None:
            continue
        ratio = old / new                      # > 1: margin per lot up = leverage cut
        if ratio >= CHANGE_RATIO or ratio <= 1.0 / CHANGE_RATIO:
            out.append({"at": at, "symbol": sym, "from": old, "to": new,
                        "ratio": round(ratio, 3), "direction": "CUT" if ratio > 1 else "RAISED",
                        "effective_leverage": new})
    return out


# ---------------------------------------------------------------- sized orders and feasibility
def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def sized_orders(path: Path, now: datetime,
                 days: int = INTENT_DAYS) -> dict[tuple[str, str], dict[str, Any]]:
    """{(sleeve, symbol): {lot, side}}: every order SIZED in the window (a positive lot), kept as
    each sleeve's largest on each symbol -- the order that must still fit."""
    since = now - timedelta(days=days)
    out: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        fh = path.open(encoding="utf-8")
    except OSError:
        return out
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or not r.get("symbol"):
                continue
            t = _ts(r.get("time") or r.get("at"))
            lot = _num(r.get("lot"))
            if t is None or t < since or t > now + timedelta(hours=1) or lot is None:
                continue
            k = (str(r.get("sleeve") or "?"), str(r["symbol"]).upper())
            side = "sell" if str(r.get("side") or "").lower().startswith("sell") else "buy"
            if k not in out or lot > out[k]["lot"]:
                out[k] = {"lot": lot, "side": side}
    return out


def _high_impact(row: Mapping[str, Any], default: Any = None) -> bool:
    v = row.get("impact", row.get("importance", default))
    return str(v).strip().lower() in HIGH_IMPACT


def in_cut_window(now: datetime, calendars: Path = CALENDARS) -> dict[str, Any]:
    """Friday 12:00 UTC to the Sunday open, or a HIGH-IMPACT calendar row inside EVENT_WINDOW_H.
    A row counts only when it (or its file) is tagged high impact: an untagged row is not one."""
    wd, h = now.weekday(), now.hour
    if (wd == 4 and h >= 12) or wd == 5 or (wd == 6 and h < 22):
        return {"now": True, "why": "weekend window (Friday 12:00 UTC to the Sunday open)"}
    horizon = now + timedelta(hours=EVENT_WINDOW_H)
    files = sorted(calendars.glob("*.json")) if calendars.is_dir() else []
    n_high = 0
    for p in files:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        file_impact = doc.get("impact") if isinstance(doc, dict) else None
        rows = doc if isinstance(doc, list) else (doc.get("events") or doc.get("rows") or [])
        for e in rows if isinstance(rows, list) else []:
            if not isinstance(e, dict) or not _high_impact(e, file_impact):
                continue
            n_high += 1
            t = _ts(e.get("time") or e.get("at") or e.get("datetime"))
            if t is not None and now <= t <= horizon:
                return {"now": True, "why": f"high-impact {p.stem} event at "
                                            f"{t.isoformat(timespec='minutes')}"}
    return {"now": False, "why": f"no weekend and no high-impact calendar row within "
                                 f"{EVENT_WINDOW_H} h ({n_high} high-impact row(s) in "
                                 f"{len(files)} calendar file(s))"}


def feasibility(account: Mapping[str, Any], margins: Mapping[str, Mapping[str, Any]],
                orders: Mapping[tuple[str, str], Mapping[str, Any]],
                stress: float = 1.0) -> dict[str, Any]:
    """Re-margin every sized order at today's margin per lot (x `stress`), alone and as a book,
    against the margin the account may use before its margin call. Returns SHARES of that
    capacity and verdict inputs only -- never the equity or a money amount."""
    eq = _num(account.get("equity"))
    call = _num(account.get("margin_so_call"))
    used = account.get("margin")
    used_f = float(used) if isinstance(used, (int, float)) and used == used and used >= 0 else 0.0
    if eq is None:
        return {"status": "UNMEASURED", "why": "no equity read from the account"}
    if call is None:
        return {"status": "UNMEASURED", "why": "the account publishes no margin_so_call; it is "
                                              "never defaulted"}
    if account.get("margin_so_mode") not in (None, 0):
        return {"status": "UNMEASURED", "why": "the margin-call level is in money, not percent"}
    if not orders:
        return {"status": "UNMEASURED", "why": f"no order sized for this venue in the last "
                                              f"{INTENT_DAYS} days"}
    capacity = eq / (call / 100.0) * MAX_MARGIN_USE
    infeasible, unpriced, priced, worst, total = [], [], 0, 0.0, 0.0
    for (sleeve, sym), o in sorted(orders.items()):
        row = margins.get(sym) or {}
        mpl = _num(row.get(f"margin_per_lot_{o.get('side')}")) or _num(
            row.get("margin_per_lot_buy"))
        if mpl is None:
            unpriced.append(f"{sleeve}:{sym}")
            continue
        need = mpl * float(o["lot"]) * stress
        priced += 1
        total += need
        share = (used_f + need) / capacity
        worst = max(worst, share)
        if share > 1.0:
            infeasible.append(f"{sleeve}:{sym}")
    if not priced:
        return {"status": "UNMEASURED", "why": "no sized order's symbol has a margin reading",
                "unpriced_orders": unpriced}
    book = (used_f + total) / capacity
    return {"status": "MEASURED", "stress_factor": stress, "orders": priced,
            "worst_order_use_share": round(worst, 4), "book_use_share": round(book, 4),
            "book_fits": book <= 1.0, "orders_infeasible_alone": infeasible,
            "unpriced_orders": unpriced}


def verdict(today: Mapping[str, Any], stressed: Mapping[str, Any],
            window: Mapping[str, Any]) -> dict[str, Any]:
    """GREEN / AT_RISK / UNMEASURED for one venue. Absence never resolves to GREEN."""
    flagged = bool(window.get("now")) and stressed.get("status") == "MEASURED" \
        and not stressed.get("book_fits", True)
    if today.get("status") != "MEASURED":
        return {"verdict": "UNMEASURED", "why": str(today.get("why")), "stress_flagged": False}
    if today["orders_infeasible_alone"] or not today["book_fits"]:
        v, why = "AT_RISK", "a sized order or the book open at once does not fit TODAY"
    elif flagged:
        v, why = "AT_RISK", (f"in a cut-prone window ({window.get('why')}) the book would not "
                             f"fit at half leverage")
    elif today.get("unpriced_orders"):
        v, why = "UNMEASURED", "some sized symbols have no margin reading"
    else:
        v, why = "GREEN", "every sized order and the book fit at today's margin"
    return {"verdict": v, "why": why, "stress_flagged": flagged}


def assess(account: Mapping[str, Any], margins: Mapping[str, Mapping[str, Any]],
           venue: str, *, now: datetime | None = None, intents: Path | None = None,
           calendars: Path = CALENDARS) -> dict[str, Any]:
    """The published feasibility block of one venue: shares and verdicts only."""
    now = now or datetime.now(tz=UTC)
    orders = sized_orders(intents or INTENT_FILES.get(venue, DATA / f"{venue}_intents.jsonl"), now)
    window = in_cut_window(now, calendars)
    today = feasibility(account, margins, orders)
    stressed = feasibility(account, margins, orders, STRESS_FACTOR)
    return {**verdict(today, stressed, window), "assessed_at": now.isoformat(timespec="seconds"),
            "intent_days": INTENT_DAYS, "max_margin_use": MAX_MARGIN_USE,
            "cut_prone_window": window, "today": today, "half_leverage": stressed}


def unmeasured(why: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    return {"verdict": "UNMEASURED", "why": why, "stress_flagged": False,
            "assessed_at": now.isoformat(timespec="seconds")}


def intent_symbols(venue: str, now: datetime | None = None) -> list[str]:
    path = INTENT_FILES.get(venue)
    return sorted({s for _, s in sized_orders(path, now or datetime.now(tz=UTC))}) if path else []


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _parse(ts: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def observe(path: Path, leverage: float | None, *, venue: str = "fusion",
            now: datetime | None = None, emit: Any = None,
            symbols: dict[str, dict[str, Any]] | None = None,
            feasibility: dict[str, Any] | None = None,
            extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record one reading; return the document written (or that would stand, when unreadable).

    `feasibility` is this pass's `assess` block (UNMEASURED when not given: a pass that did not
    assess never leaves an older verdict standing as if current). `extra` adds public fields to
    the venue row (TradeLocker's key names)."""
    now = now or datetime.now(tz=UTC)
    doc = _read(path)
    raw_venues = doc.get("venues")
    venues: dict[str, Any] = raw_venues if isinstance(raw_venues, dict) else {}
    raw_row = venues.get(venue)
    row: dict[str, Any] = raw_row if isinstance(raw_row, dict) else {}
    prior = row
    raw_changes = row.get("changes")
    changes: list[Any] = raw_changes if isinstance(raw_changes, list) else []
    lev = float(leverage) if isinstance(leverage, (int, float)) and leverage > 0 else None
    prev = row.get("leverage")
    changed: dict[str, Any] | None = None
    if lev is not None:
        if isinstance(prev, (int, float)) and float(prev) != lev:
            changed = {"at": now.isoformat(timespec="seconds"), "from": float(prev), "to": lev,
                       "direction": "CUT" if lev < float(prev) else "RAISED"}
            changes = [*changes, changed][-MAX_CHANGES_KEPT:]
        row = {"leverage": lev, "read_at": now.isoformat(timespec="seconds"),
               "changes": changes}
    # The account rebuild above keeps only the account fields; the per-symbol state is read from
    # the row as it stood on disk.
    raw_syms = prior.get("symbols")
    prev_syms: dict[str, Any] = ({s: _public_symbol(r) for s, r in raw_syms.items()
                                  if isinstance(r, dict)} if isinstance(raw_syms, dict) else {})
    raw_sc = prior.get("symbol_changes")
    kept: list[Any] = raw_sc if isinstance(raw_sc, list) else []
    sym_changes: list[dict[str, Any]] = []
    if symbols:
        pub = {s: _public_symbol(r) for s, r in symbols.items()}
        sym_changes = _symbol_changes(prev_syms, pub, now.isoformat(timespec="seconds"))
        row = {**row, "symbols": {**prev_syms, **pub},
               "symbols_read_at": now.isoformat(timespec="seconds"),
               "symbol_changes": [*kept, *sym_changes][-MAX_CHANGES_KEPT:]}
    elif prev_syms:
        row = {**row, "symbols": prev_syms, "symbol_changes": kept}
    read_at = _parse(row.get("read_at"))
    age_h = None if read_at is None else round((now - read_at).total_seconds() / 3600.0, 2)
    if read_at is None:
        verdict = "UNMEASURED"
    elif age_h is not None and age_h > STALE_AFTER_H:
        verdict = "STALE"
    elif changed is not None or sym_changes:
        verdict = "CHANGED"
    else:
        verdict = "MEASURED"
    row = {**row, **(extra or {}), "verdict": verdict, "age_h": age_h,
           "feasibility": feasibility or unmeasured("not assessed on this pass", now)}
    venues = {**venues, venue: row}
    for v in VENUES:
        if v not in venues:
            venues[v] = {"verdict": "UNMEASURED",
                         "feasibility": unmeasured("no pass has recorded this venue yet", now)}
    out = {"generated_utc": now.isoformat(timespec="seconds"),
           "producer": "libs/ops/leverage_watch.py (via research/financing_lab.py, "
                       "prop/ftmo_venue_reader.py, prop/e8_book.py)",
           "stale_after_h": STALE_AFTER_H, "venues": venues,
           "feasibility_by_venue": {v: (r.get("feasibility") or {}).get("verdict", "UNMEASURED")
                                    for v, r in sorted(venues.items()) if isinstance(r, dict)},
           "boundary": "REPORT ONLY: no cap, size or veto; the allocator reads live leverage "
                       "through financing_lab.load_terms on every pass"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")   # three writers: never one tmp name
        tmp.write_text(json.dumps(out, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
    if changed is not None or sym_changes:
        try:
            if emit is None:
                from libs.ops.events import emit as emit_fn
            else:
                emit_fn = emit
            if changed is not None:
                fields: dict[str, Any] = {"producer": "research/financing_lab.py",
                                          "priority": 2, "venue": venue,
                                          "from": changed["from"], "to": changed["to"],
                                          "direction": changed["direction"]}
                emit_fn("ACCOUNT_LEVERAGE_CHANGED", **fields)
            for c in sym_changes:
                emit_fn("SYMBOL_MARGIN_CHANGED", producer="libs/ops/leverage_watch.py",
                        priority=2, venue=venue, symbol=c["symbol"], ratio=c["ratio"],
                        direction=c["direction"])
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- the venue hooks
def observe_mt5(mt5: Any, venue: str, *, path: Path = REPORT, now: datetime | None = None,
                extra_symbols: Any = (), emit: Any = None) -> str:
    """The hook for a process that already holds a terminal (FTMO's venue reader). Read-only,
    never raises; returns one line for the caller's log."""
    try:
        now = now or datetime.now(tz=UTC)
        acc = mt5.account_info()
        if acc is None:
            observe(path, None, venue=venue, now=now, emit=emit,
                    feasibility=unmeasured("account_info unanswered", now))
            return f"{venue}: account_info unanswered; UNMEASURED"
        account = {k: getattr(acc, k, None)
                   for k in ("equity", "margin", "margin_so_call", "margin_so_mode")}
        held = [getattr(p, "symbol", "") for p in (mt5.positions_get() or ())]
        rows = symbol_margins(mt5, [*CORE_SYMBOLS, *intent_symbols(venue, now), *held,
                                    *extra_symbols])
        block = assess(account, rows, venue, now=now)
        observe(path, _num(getattr(acc, "leverage", None)), venue=venue, now=now, emit=emit,
                symbols=rows or None, feasibility=block)
        return f"{venue}: leverage {getattr(acc, 'leverage', None)}, {len(rows)} symbols, " \
               f"feasibility {block['verdict']} ({block['why']})"
    except Exception as exc:
        return f"{venue}: leverage read failed ({type(exc).__name__})"


#: TradeLocker account / instrument keys worth naming; only a LEVERAGE key's value is kept.
_TL_ACCOUNT_KEYS = ("leverage", "margin")
_TL_SYMBOL_KEYS = ("leverage", "margin", "contract", "lotsize")


def _tl_read(venue: Any, symbols: list[str], deadline: float) -> dict[str, Any]:
    st = dict(venue._api.get_account_state())
    acct_keys = sorted(str(k) for k in st if any(t in str(k).lower() for t in _TL_ACCOUNT_KEYS))
    lev = next((_num(st[k]) for k in acct_keys if "leverage" in k.lower()
                and _num(st[k]) is not None), None)
    sym_keys: dict[str, list[str]] = {}
    sym_lev: dict[str, float] = {}
    for sym in symbols:
        if time.monotonic() >= deadline:
            break
        try:
            det = dict(venue.details(sym))
        except Exception:
            continue
        ks = sorted(str(k) for k in det if any(t in str(k).lower() for t in _TL_SYMBOL_KEYS))
        if ks:
            sym_keys[sym] = ks
        lv = next((_num(det[k]) for k in ks if "leverage" in k.lower()
                   and _num(det[k]) is not None), None)
        if lv is not None:
            sym_lev[sym] = lv
    return {"leverage": lev, "account_keys": acct_keys, "symbol_keys": sym_keys,
            "symbol_leverage": sym_lev, "complete": time.monotonic() < deadline}


def observe_tradelocker(venue: Any, *, budget_s: float, path: Path = REPORT,
                        now: datetime | None = None, emit: Any = None) -> str:
    """The hook for E8: reads on a TradeLocker session the caller ALREADY holds (no login here),
    bounded by `budget_s` -- the read runs on a daemon thread joined for the budget, so a hung
    HTTP call cannot hold the caller's pass. Never raises."""
    try:
        now = now or datetime.now(tz=UTC)
        listed = set(getattr(venue, "_by_key", {}) or {})
        syms = [s for s in dict.fromkeys([*intent_symbols("e8", now), *CORE_SYMBOLS])
                if not listed or s in listed]
        box: dict[str, Any] = {}
        deadline = time.monotonic() + max(0.0, float(budget_s))

        def _run() -> None:
            try:
                box["read"] = _tl_read(venue, syms, deadline)
            except Exception as exc:
                box["error"] = type(exc).__name__

        th = threading.Thread(target=_run, name="e8-leverage-read", daemon=True)
        th.start()
        th.join(max(0.0, float(budget_s)))
        read = box.get("read")
        if read is None:
            why = (f"TradeLocker read failed ({box['error']})" if "error" in box
                   else f"TradeLocker read exceeded the {budget_s:g}s budget")
            observe(path, None, venue="e8", now=now, emit=emit, feasibility=unmeasured(why, now))
            return f"e8: {why}; UNMEASURED"
        syms_pub = {s: {"effective_leverage": lv} for s, lv in read["symbol_leverage"].items()}
        why = ("TradeLocker publishes no venue margin-per-lot calculation and no margin-call "
               "level the desk reads; its leverage and margin fields are recorded by key name "
               "only, so sized E8 orders cannot be re-margined")
        observe(path, read["leverage"], venue="e8", now=now, emit=emit,
                symbols=syms_pub or None, feasibility=unmeasured(why, now),
                extra={"platform": "tradelocker",
                       "tradelocker_fields": {"account": read["account_keys"],
                                              "symbol": read["symbol_keys"],
                                              "complete_within_budget": read["complete"]}})
        return (f"e8: leverage {read['leverage']}, {len(read['symbol_keys'])} symbol(s) with "
                f"margin keys; feasibility UNMEASURED")
    except Exception as exc:
        return f"e8: leverage read failed ({type(exc).__name__})"
