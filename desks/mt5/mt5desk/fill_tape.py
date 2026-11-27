"""THE FILL TAPE: one row per deal, written at the moment of the fill, by every executor.

WHY (root cause R5, 2026-11-27). Cost and loss learning waited for live fills, and nothing wrote
a fill in a form they could read: the E8 deal ledger was silent from 10-16, the FTMO lane had no
slip file at all, and the E8 gold bracket ran on a 24.13-point default taken from one logged
event (`E8_GOLD_SLIP.json`, UNMEASURED, n=0). The door ledger did hold each MT5 send's request
price and the venue's fill price, but no organ derived a cost from it, and a resting stop entry
(E8 gold, any pending order) fills long after its send, where the door never sees it.

WHAT A ROW IS (schema `fill-tape-v1`): book, venue, lane, symbol, side, the INTENDED price (the
request price for a market deal; the resting order's own price for a stop/limit entry), the FILL
price, the bid/ask at the send when it was read, spread, and signed slip. Slip follows the desk's
one convention (`libs/execution/fill_corpus`): a signed FRACTION of the intended price, positive =
worse for the trader (a buy filled above, a sell filled below). `slip_px` is the same in price
units. A field that was not read is null and the row says why in `unmeasured`; nothing is
defaulted to zero, because a zero slip is a measurement.

WRITERS: `order_door.send` (every MT5 market deal: FTMO executor, FTMO follower, Fusion gateway)
and `prop.e8_fills.observe` (every E8 position the first time it is seen, priced against its
matched SENT stop entry). READERS: `summarise()` -> `data/PROP_SLIP.json`, one block per book and
symbol, which the cost and learning organs read instead of a default.

NOTHING HERE MAY COST AN ORDER: `record()` never raises and never retries; a failed write is
counted in the returned flag and nothing else happens. Rows carry no account identifier.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import statistics
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "fill-tape-v1"
DESK = Path(__file__).resolve().parents[1]
TAPE = DESK / "data" / "fill_tape.jsonl"
SUMMARY = DESK / "data" / "PROP_SLIP.json"
#: Keys a row may never carry (the prop ledger's rule): the tape is shared research input.
BANNED = ("account", "login", "username", "password", "acc_num", "account_id")


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def book_of(caller: str) -> str:
    """The book a door caller trades for. `ftmo_*` -> ftmo, `e8_*` -> e8, else fusion."""
    c = str(caller or "").lower()
    if c.startswith("ftmo"):
        return "ftmo"
    if c.startswith("e8"):
        return "e8"
    return "fusion"


def slip(side: str, intended: float | None, fill: float | None) -> tuple[float | None,
                                                                       float | None]:
    """(slip_frac, slip_px), positive = worse for the trader; (None, None) when unpriceable."""
    s = str(side or "").lower()
    if intended is None or fill is None or not intended > 0 or not fill > 0 \
            or s not in ("buy", "sell"):
        return None, None
    px = (fill - intended) if s == "buy" else (intended - fill)
    return round(px / intended, 8), round(px, 6)


def row(*, book: str, venue: str, lane: str, symbol: Any, side: str, intended: Any,
        fill: Any, volume: Any = None, bid: Any = None, ask: Any = None, deal: Any = None,
        kind: str = "entry", at: datetime | None = None,
        provenance: str = "") -> dict[str, Any]:
    """One fill-tape-v1 row. Pure."""
    ip, fp, b, a = _f(intended), _f(fill), _f(bid), _f(ask)
    s = str(side or "").lower()
    sf, sp = slip(s, ip, fp)
    unmeasured = []
    if sf is None:
        unmeasured.append("slip: intended or fill price unreadable")
    spread = round(a - b, 6) if a is not None and b is not None and a >= b > 0 else None
    if spread is None:
        unmeasured.append("spread: no quote read at the send")
    return {"schema": SCHEMA, "at": (at or datetime.now(UTC)).isoformat(timespec="seconds"),
            "book": str(book), "venue": str(venue), "lane": str(lane),
            "symbol": str(symbol or "").upper() or None, "side": s, "kind": str(kind),
            "intended": ip, "fill": fp, "volume": _f(volume), "bid": b, "ask": a,
            "spread_px": spread, "slip_frac": sf, "slip_px": sp,
            "deal": None if deal is None else str(deal), "provenance": provenance,
            "unmeasured": unmeasured}


def record(r: Mapping[str, Any], *, path: Path | None = None) -> bool:
    """Append one row (O_APPEND, one line). Never raises; False when it was not written."""
    try:
        if any(k in r for k in BANNED):
            return False
        p = path or TAPE
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0),
                     0o644)
        try:
            os.write(fd, (json.dumps(dict(r), default=str, sort_keys=True) + "\n")
                     .encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except Exception:                   # a recorder never costs the order
        return False


def read(path: Path | None = None) -> list[dict[str, Any]]:
    """Every readable row, deduplicated on book:deal (rows without a deal are all kept)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = (path or TAPE).read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for ln in lines:
        with contextlib.suppress(ValueError):
            d = json.loads(ln)
            if not isinstance(d, dict) or d.get("schema") != SCHEMA:
                continue
            key = f"{d.get('book')}:{d.get('deal')}" if d.get("deal") else ""
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            out.append(d)
    return out


def _q(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))]


def summarise(rows: Iterable[Mapping[str, Any]], *,
              now: datetime | None = None) -> dict[str, Any]:
    """Per book and symbol: n, median / p90 slip (fraction and price), median spread. A book
    with no priced fill is UNMEASURED with n 0, never a zero cost."""
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for r in rows:
        groups.setdefault((str(r.get("book")), str(r.get("symbol"))), []).append(r)
    books: dict[str, dict[str, Any]] = {}
    for (book, sym), rs in sorted(groups.items()):
        sf = [float(r["slip_frac"]) for r in rs if _f(r.get("slip_frac")) is not None]
        sp = [float(r["slip_px"]) for r in rs if _f(r.get("slip_px")) is not None]
        spr = [float(r["spread_px"]) for r in rs if _f(r.get("spread_px")) is not None]
        books.setdefault(book, {})[sym] = {
            "n_rows": len(rs), "n_priced": len(sf),
            "status": "MEASURED" if sf else "UNMEASURED",
            "slip_frac_median": round(statistics.median(sf), 8) if sf else None,
            "slip_frac_p90": round(_q(sf, 0.9), 8) if sf else None,
            "slip_px_median": round(statistics.median(sp), 6) if sp else None,
            "slip_px_p90": round(_q(sp, 0.9), 6) if sp else None,
            "spread_px_median": round(statistics.median(spr), 6) if spr else None,
            "last_at": max(str(r.get("at") or "") for r in rs)}
    return {"schema": "prop-slip-v1",
            "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
            "source": "data/fill_tape.jsonl", "books": books,
            "convention": "slip > 0 is worse for the trader; fraction of the intended price"}


def publish(*, tape: Path | None = None, out: Path | None = None,
            now: datetime | None = None) -> dict[str, Any]:
    """Write PROP_SLIP.json from the tape (atomic replace). Never raises."""
    doc = summarise(read(tape), now=now)
    with contextlib.suppress(Exception):
        p = out or SUMMARY
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
    return doc
