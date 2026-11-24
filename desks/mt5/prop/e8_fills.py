"""E8 FILLS LEDGER: every closed E8 position becomes one prop-fills-v1 row (box 11-24).

WHY: E8 had no fills ledger at all -- no E8 row in live_ledger_prop.jsonl and
e8_gold_exit_fills.csv stopped at 10-21 -- so E8's realised R was UNMEASURED on every day, and
nothing that sizes by fill evidence (fill-proven, the divergence cut) could see E8.

HOW, from what one E8 pass already reads (read-only, never an order):
  * Each pass `observe()` snapshots the venue's open positions and the account balance into
    STATE. A position present last pass and absent now CLOSED between the two passes.
  * Its P/L is the balance delta between the passes, which is exact (net of commission and
    swap) only when that position is the ONLY one that closed in the gap; otherwise P/L is null
    and `pl_status` says why. Nothing is guessed.
  * Its risk is |entry - sent stop| x qty x contract, the stop read from E8's own SENT intent
    for that side that day (e8_gold_intents.jsonl). R = P/L / risk when both are measured.
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


def sent_stop(intents: Path, side: str, day: str) -> float | None:
    """The stop of E8's last SENT leg on `side` ("buy"/"sell") dated `day` (YYYY-MM-DD)."""
    want = f"{side}_stop"
    stop = None
    try:
        lines = intents.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]
    except OSError:
        return None
    for ln in lines:
        with contextlib.suppress(ValueError):
            r = json.loads(ln)
            if (isinstance(r, dict) and r.get("status") == "SENT" and r.get("side") == want
                    and str(r.get("at") or "").startswith(day)):
                stop = _f(r.get("sl")) or stop
    return stop


def compose(closed: list[dict[str, Any]], pl_total: float | None, *, now: datetime,
            intents: Path = INTENTS) -> list[dict[str, Any]]:
    """prop-fills-v1 rows for the positions that closed since the last pass. Pure but for the
    intents read."""
    rows = []
    only = len(closed) == 1 and pl_total is not None
    for c in closed:
        day = (c.get("seen_at") or now.isoformat())[:10]
        sl = sent_stop(intents, c.get("side") or "", day)
        entry, qty = c.get("entry"), c.get("qty")
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


def observe(venue: Any, *, now: datetime | None = None, state: Path = STATE,
            ledger: Path = LEDGER, intents: Path = INTENTS,
            symbol_of: Any = None) -> dict[str, Any]:
    """One snapshot; append a row for every position closed since the last one. Never raises."""
    now = now or datetime.now(UTC)
    try:
        sym = symbol_of or (lambda p: "XAUUSD")
        raw = venue.positions()
        cur = {s["id"]: s for s in (_snap(p, sym) for p in raw) if s}
        bal = _f((venue.account() or {}).get("balance"))
        prev = _load(state)
        before = prev.get("positions") if isinstance(prev.get("positions"), dict) else {}
        for pid, s in cur.items():
            s["seen_at"] = (before.get(pid) or {}).get("seen_at") or now.isoformat()
        closed = [v for k, v in before.items() if k not in cur and isinstance(v, dict)]
        pbal = _f(prev.get("balance"))
        n = 0
        if closed and prev:
            pl = bal - pbal if bal is not None and pbal is not None else None
            n = append(compose(closed, pl, now=now, intents=intents), ledger)
        _save(state, {"at": now.isoformat(timespec="seconds"), "balance": bal,
                      "positions": cur})
        return {"open": len(cur), "closed": len(closed), "written": n}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
