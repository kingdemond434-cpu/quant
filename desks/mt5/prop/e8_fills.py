"""E8 FILLS LEDGER: every closed E8 position becomes one prop-fills-v1 row (box 11-24).

WHY: E8 had no fills ledger at all -- no E8 row in live_ledger_prop.jsonl and
e8_gold_exit_fills.csv stopped at 10-21 -- so E8's realised R was UNMEASURED on every day, and
nothing that sizes by fill evidence (fill-proven, the divergence cut) could see E8.

HOW, from what one E8 pass already reads (read-only, never an order):
  * Each pass `observe()` snapshots the venue's open positions and the account balance into
    STATE. A position is CLOSED only after it is absent on TWO consecutive reads (Audit MF-1:
    one empty or partial read is never a close); an empty read while positions were open and
    the balance did not move is UNMEASURED and the old snapshot is kept.
  * Its P/L is the balance delta from the last read that still held it to the confirming
    read, exact (net of fees) only when it is the ONLY position pending in that span;
    otherwise P/L is null and `pl_status` says why. Nothing is guessed.
  * Its symbol is resolved from the venue's instrument id (Audit MF-2). Its risk is
    |entry - sent stop| x qty x contract only for a symbol with a known contract AND exactly
    one SENT intent that day matching its side and lot, nearest its entry; else risk and R are
    null, UNMEASURED. R = P/L / risk when both are measured.
  * Rows are appended O_APPEND, one line each, deduplicated on book:position_id, and refuse any
    login-shaped field (the prop ledger's rule).
Never raises into the E8 pass.
"""
from __future__ import annotations

import contextlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
STATE = DESK / "data" / "e8_fills_state.json"
LEDGER = DESK / "data" / "live_ledger_prop.jsonl"
INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
SCHEMA = "prop-fills-v1"
BOOK = "e8"
CONTRACT = {"XAUUSD": 100.0}
BANNED = ("account", "login", "username", "password", "acc_num", "account_id")


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _snap(p: dict[str, Any], symbol_of: Any) -> dict[str, Any] | None:
    pid = p.get("id") if p.get("id") is not None else p.get("positionId")
    if pid is None:
        return None
    side = str(p.get("side") or "").lower()
    return {"id": str(pid), "side": "buy" if side.startswith("b") else "sell" if side else "",
            "qty": _f(p.get("qty")), "entry": _f(p.get("avgPrice") or p.get("price")),
            "symbol": symbol_of(p), "open_date": str(p.get("openDate") or "")}


def _load(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def sent_stop(intents: Path, side: str, day: str, *, qty: float | None = None,
              entry: float | None = None) -> float | None:
    """The stop of E8's SENT leg on `side` ("buy"/"sell") dated `day` that matches `qty` and is
    nearest `entry`; None when no leg matches or two match equally well (never a guess)."""
    leg = sent_leg(intents, side, day, qty=qty, entry=entry)
    return None if leg is None else leg[1]


def sent_leg(intents: Path, side: str, day: str, *, qty: float | None = None,
             entry: float | None = None) -> tuple[float, float] | None:
    """(entry price, stop) of the matching SENT leg, by the rule in `sent_stop`."""
    want = f"{side}_stop"
    try:
        lines = intents.read_text(encoding="utf-8", errors="replace").splitlines()[-4000:]
    except OSError:
        return None
    cands: dict[tuple[float, float], float] = {}
    for ln in lines:
        with contextlib.suppress(ValueError):
            r = json.loads(ln)
            if not (isinstance(r, dict) and r.get("status") == "SENT" and r.get("side") == want
                    and str(r.get("at") or "").startswith(day)):
                continue
            sl, px, lot = _f(r.get("sl")), _f(r.get("price")), _f(r.get("lot"))
            if sl is None or px is None:
                continue
            if qty is not None and lot is not None and abs(lot - qty) > 1e-9:
                continue
            cands[(px, sl)] = sl
    if not cands:
        return None
    if entry is None:
        return next(iter(cands)) if len(cands) == 1 else None
    ranked = sorted(cands, key=lambda k: abs(k[0] - entry))
    if len(ranked) > 1 and abs(ranked[0][0] - entry) == abs(ranked[1][0] - entry):
        return None
    return ranked[0]


def compose(closed: list[dict[str, Any]], pl_total: float | None, *, now: datetime,
            intents: Path = INTENTS, only: bool | None = None) -> list[dict[str, Any]]:
    """prop-fills-v1 rows for confirmed closes. Pure but for the intents read."""
    rows = []
    only = (len(closed) == 1 if only is None else only) and pl_total is not None
    for c in closed:
        day = (c.get("seen_at") or now.isoformat())[:10]
        entry, qty = c.get("entry"), c.get("qty")
        sl = (sent_stop(intents, c.get("side") or "", day, qty=qty, entry=entry)
              if CONTRACT.get(str(c.get("symbol") or "").upper()) else None)
        contract = CONTRACT.get(str(c.get("symbol") or "").upper())
        risk = (round(abs(entry - sl) * qty * contract, 2)
                if entry and sl and qty and contract else None)
        pl = round(pl_total, 2) if only else None
        rows.append({
            "schema": SCHEMA, "book": BOOK, "venue": "tradelocker", "lane": "e8_gold",
            "provenance": "e8_fills:position_disappeared+balance_delta",
            "recorded_at": now.isoformat(timespec="seconds"), "symbol": c.get("symbol"),
            "side": 1 if c.get("side") == "buy" else 0, "volume": qty, "entry_price": entry,
            "sl": sl, "entry_time": c.get("open_date") or c.get("seen_at"),
            "exit_time_bound": now.isoformat(timespec="seconds"),
            "risk_quote": risk, "pl_net_quote": pl,
            "pl_status": ("MEASURED: balance delta, net of fees" if only else
                          f"UNMEASURED: {len(closed)} positions closed in one pass gap"
                          if pl_total is not None else "UNMEASURED: balance unreadable"),
            "r_multiple": round(pl / risk, 4) if pl is not None and risk else None,
            "risk_status": ("MEASURED: matched SENT intent" if risk else
                            "UNMEASURED: unknown symbol/contract or no single matching intent"),
            "r_basis": "net P/L (balance delta) / (|entry - sent stop| x qty x contract)",
            "quote_ccy": "USD", "position_id": c.get("id"), "account_kind": "prop"})
    return rows


def append(rows: list[dict[str, Any]], path: Path = LEDGER) -> int:
    for r in rows:
        for banned in BANNED:
            if banned in r:
                raise ValueError(f"refusing a prop ledger row carrying {banned!r}")
    have: set[str] = set()
    if path.exists():
        for ln in path.read_text("utf-8", errors="replace").splitlines():
            with contextlib.suppress(ValueError):
                d = json.loads(ln)
                if isinstance(d, dict):
                    have.add(f"{d.get('book')}:{d.get('position_id')}")
    new = [r for r in rows if f"{BOOK}:{r.get('position_id')}" not in have]
    if not new:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0),
                 0o644)
    try:
        for r in new:
            os.write(fd, (json.dumps(r, default=str, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return len(new)


def _symbol_resolver(venue: Any) -> Any:
    """instrument id -> desk symbol from the venue's own catalogue; None when unknown."""
    rev: dict[int, str] = {}
    with contextlib.suppress(Exception):
        rev = {int(v): str(k).upper() for k, v in (getattr(venue, "_by_key", None) or {}).items()}

    def of(p: dict[str, Any]) -> str | None:
        iid = p.get("tradableInstrumentId")
        try:
            return rev.get(int(iid)) if iid is not None else None
        except (TypeError, ValueError):
            return None
    return of


TAPE_NAME = "fill_tape.jsonl"


def tape_new_entries(cur: dict[str, Any], before: dict[str, Any], missing: dict[str, Any], *,
                     now: datetime, intents: Path, tape: Path) -> int:
    """ROOT R5 (2026-11-27): a position seen for the FIRST time is an E8 entry fill. One
    fill-tape row each: intended = its matched SENT stop-entry price (null when no single leg
    matches, never a guess), fill = the venue's avgPrice. Never raises."""
    n = 0
    with contextlib.suppress(Exception):
        from mt5desk import fill_tape as ft
        for pid, s in cur.items():
            if pid in before or pid in missing:
                continue
            day = str(s.get("seen_at") or now.isoformat())[:10]
            leg = sent_leg(intents, str(s.get("side") or ""), day, qty=s.get("qty"),
                           entry=s.get("entry"))
            lane = "e8_gold" if str(s.get("symbol") or "").upper() == "XAUUSD" else "e8_sleeve"
            n += ft.record(ft.row(book=BOOK, venue="tradelocker", lane=lane,
                                  symbol=s.get("symbol"), side=str(s.get("side") or ""),
                                  intended=None if leg is None else leg[0],
                                  fill=s.get("entry"), volume=s.get("qty"), deal=pid,
                                  kind="entry", at=now,
                                  provenance="e8_fills:position_first_seen"), path=tape)
    return n


def observe(venue: Any, *, now: datetime | None = None, state: Path = STATE,
            ledger: Path = LEDGER, intents: Path = INTENTS,
            symbol_of: Any = None, tape: Path | None = None) -> dict[str, Any]:
    """One snapshot; a row for every close confirmed on two reads. Never raises."""
    now = now or datetime.now(UTC)
    try:
        sym = symbol_of or _symbol_resolver(venue)
        raw = venue.positions()
        cur = {s["id"]: s for s in (_snap(p, sym) for p in raw) if s}
        bal = _f((venue.account() or {}).get("balance"))
        prev = _load(state)
        before = prev.get("positions") if isinstance(prev.get("positions"), dict) else {}
        missing = prev.get("missing") if isinstance(prev.get("missing"), dict) else {}
        prev_missing = dict(missing)
        pbal = _f(prev.get("balance"))
        if not cur and before and bal is not None and pbal is not None and bal == pbal:
            return {"open": None, "closed": 0, "written": 0,
                    "status": "UNMEASURED: empty read with an unchanged balance; snapshot kept"}
        for pid, s in cur.items():
            s["seen_at"] = ((before.get(pid) or (missing.get(pid) or {}).get("snap") or {})
                            .get("seen_at") or now.isoformat())
        missing = {k: v for k, v in missing.items() if k not in cur and isinstance(v, dict)}
        for pid, s in before.items():
            if pid not in cur and isinstance(s, dict) and pid not in missing:
                missing[pid] = {"snap": s, "count": 0, "balance_before": pbal}
        for v in missing.values():
            v["count"] = int(v.get("count") or 0) + 1
        confirmed = {k: v for k, v in missing.items() if v["count"] >= 2}
        n = 0
        if confirmed:
            alone = len(missing) == 1
            b0 = _f(next(iter(confirmed.values())).get("balance_before")) if alone else None
            pl = bal - b0 if alone and bal is not None and b0 is not None else None
            n = append(compose([v["snap"] for v in confirmed.values()], pl, now=now,
                               intents=intents, only=alone), ledger)
            missing = {k: v for k, v in missing.items() if k not in confirmed}
        tp = tape if tape is not None else state.parent / TAPE_NAME
        taped = tape_new_entries(cur, before, prev_missing, now=now, intents=intents, tape=tp)
        with contextlib.suppress(Exception):
            # The per-account slip the cost organs read (every book on the tape, not only E8).
            from mt5desk import fill_tape as _ft
            _ft.publish(tape=tp, out=tp.parent / "PROP_SLIP.json", now=now)
        _save(state, {"at": now.isoformat(timespec="seconds"), "balance": bal,
                      "positions": cur, "missing": missing})
        return {"open": len(cur), "closed": len(confirmed), "pending": len(missing),
                "written": n, "taped": taped}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
