"""ONE LIVE ROSTER: every position-taking lane on every account is a row (root R10, 2026-11-27).

WHY. "Live" had two registries, and every monitor read the empty one. sleeves.json held 0 LIVE
while the E8 gold book filled at 05:06Z on 11-27; placement_interlock, regime_state (live n = 0
on 176 sleeves), decay, the loss learner and markout all key on sleeves.json or the Fusion
ledger, and even the zero-live pager read E8's non-gold book only, so the one account trading
real money sat outside every monitor.

WHAT A ROW IS: account, lane, sleeve, symbol, certificate key, size source, fraction, and what
the account holds on that symbol right now (`open_side`, from the cross-account book). Built
from the book EACH EXECUTOR TRADES (never inferred from another account's):
  e8 gold      reports/E8_GOLD.json      every window with a live sizing source this pass
  e8 sleeves   reports/E8_BOOK.json      the certified non-gold book prop/e8_executor reads
  ftmo         reports/FTMO_ALLOCATOR.json  positive executable fractions, deployable
  fusion       data/sleeves.json         LIVE rows (probe rows included); PAUSED when unfunded
A source that is absent, torn or past its shelf life is named in `sources` with its status and
contributes no rows: UNMEASURED is never read as an empty book (L1.28a).

READERS: `rows(account=None)` from reports/LIVE_ROSTER.json. Monitors and learners read this,
not sleeves.json, so an account with money can never sit outside them again. Measurement only:
it opens, closes and sizes nothing. Never raises.
"""
from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
OUT = DESK / "reports" / "LIVE_ROSTER.json"
E8_GOLD = DESK / "reports" / "E8_GOLD.json"
E8_BOOK = DESK / "reports" / "E8_BOOK.json"
FTMO_BOOK = DESK / "reports" / "FTMO_ALLOCATOR.json"
SLEEVES = DESK / "data" / "sleeves.json"
PAUSE = DESK / "data" / "GATEWAY_PAUSED"
#: E8-Gold writes its report every pass (minutes); the books are rebuilt hourly.
GOLD_MAX_AGE_S = 2 * 3600.0
BOOK_MAX_AGE_S = 6 * 3600.0
#: E8-Gold sizing sources that carry no risk this pass.
ZERO_SOURCES = frozenset({"pinned_zero", "void", "absent", "none", "zero", "unmeasured"})


def _sr() -> Any:
    from mt5desk import state_rows
    return state_rows


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _row(account: str, lane: str, sleeve: Any, symbol: Any, *, cert: Any = None,
         source: str = "", frac: Any = None, state: str = "LIVE") -> dict[str, Any]:
    return {"account": account, "lane": lane, "sleeve": str(sleeve), "symbol":
            str(symbol or "").upper() or None, "cert_key": cert if isinstance(cert, str) else
            (cert or {}).get("cell") if isinstance(cert, dict) else None,
            "size_source": source, "fraction": _f(frac), "state": state}


def e8_gold(now: datetime, path: Path | None = None) -> tuple[list[dict[str, Any]], dict]:
    got = _sr().load_doc(path or E8_GOLD, max_age_s=GOLD_MAX_AGE_S, now=now)
    if not got.usable or got.doc is None:
        return [], {"status": got.status, "why": got.why}
    doc = got.doc
    placed = {str(p.get("window")) for p in doc.get("placed") or [] if isinstance(p, dict)}
    src = doc.get("sizing_source") if isinstance(doc.get("sizing_source"), dict) else {}
    kelly = doc.get("kelly_risk") if isinstance(doc.get("kelly_risk"), dict) else {}
    out = []
    for w, s in sorted(src.items()):
        if str(s).lower() in ZERO_SOURCES or "zero" in str(s).lower():
            continue
        out.append(_row("e8", "e8_gold", f"gold_{w}", "XAUUSD", source=str(s),
                        frac=kelly.get(w), state="PLACED" if w in placed else "LIVE"))
    return out, {"status": got.status, "rows": len(out)}


def e8_book(now: datetime, path: Path | None = None) -> tuple[list[dict[str, Any]], dict]:
    got = _sr().load_doc(path or E8_BOOK, max_age_s=BOOK_MAX_AGE_S, now=now)
    if not got.usable or got.doc is None:
        return [], {"status": got.status, "why": got.why}
    out = []
    for s in got.doc.get("sleeves") or []:
        if not isinstance(s, dict):
            continue
        name = s.get("key") or s.get("name") or f"{s.get('symbol')}.{s.get('family')}"
        out.append(_row("e8", "e8_executor", name, s.get("symbol"), cert=s.get("certificate")
                        or s.get("key"), source="e8_book",
                        frac=s.get("risk_frac") or s.get("fraction")))
    return out, {"status": got.status, "rows": len(out)}


def ftmo(now: datetime, path: Path | None = None) -> tuple[list[dict[str, Any]], dict]:
    got = _sr().load_doc(path or FTMO_BOOK, max_age_s=BOOK_MAX_AGE_S, now=now)
    if not got.usable or got.doc is None:
        return [], {"status": got.status, "why": got.why}
    if got.doc.get("deployable", True) is False:
        return [], {"status": got.status, "rows": 0, "why": "not deployable"}
    out = [_row("ftmo", "ftmo_executor", k, str(k).split(".")[0], cert=k,
                source="ftmo_allocator", frac=v)
           for k, v in sorted((got.doc.get("executable") or {}).items())
           if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
    return out, {"status": got.status, "rows": len(out)}


def fusion(now: datetime, path: Path | None = None,
           pause: Path | None = None) -> tuple[list[dict[str, Any]], dict]:
    got = _sr().sleeve_rows(path or SLEEVES, now=now, publish=False)
    if not got.usable:
        return [], {"status": got.status, "why": got.why}
    paused = (pause or PAUSE).exists()
    out = [_row("fusion", "gateway", r["name"], r.get("symbol"), cert=r.get("certificate"),
                source="probe_tier" if r.get("probe") else "allocator",
                frac=r.get("risk_frac") or r.get("fraction"),
                state="PAUSED" if paused else "LIVE")
           for r in got.rows if r.get("status") == "LIVE"]
    return out, {"status": got.status, "rows": len(out), "quarantined": len(got.quarantined),
                 "paused": paused}


def _exposure(account: str, now: datetime) -> dict[str, str] | None:
    """symbol -> "long" / "short" / "both" the account holds or rests now (the cross-account
    book); None when that book is unreadable or stale."""
    with contextlib.suppress(Exception):
        from mt5desk import cross_account as xa
        book, _why = xa.read_book(account, now=now)
        if isinstance(book, dict):
            out = {}
            for sym, sides in book.items():
                lo, sh = bool((sides or {}).get("long")), bool((sides or {}).get("short"))
                if lo or sh:
                    out[xa.norm(sym)] = "both" if lo and sh else "long" if lo else "short"
            return out
    return None


def build(now: datetime | None = None, *, paths: dict[str, Path] | None = None,
          exposure: bool = True) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    p = paths or {}
    rows: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    for name, fn in (("e8_gold", lambda: e8_gold(now, p.get("e8_gold"))),
                     ("e8_book", lambda: e8_book(now, p.get("e8_book"))),
                     ("ftmo", lambda: ftmo(now, p.get("ftmo"))),
                     ("fusion", lambda: fusion(now, p.get("fusion"), p.get("pause")))):
        try:
            got, meta = fn()
        except Exception as exc:  # one source never kills the roster
            got, meta = [], {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}
        rows += got
        sources[name] = meta
    if exposure:
        held = {a: _exposure(a, now) for a in ("e8", "ftmo", "fusion")}
        for r in rows:
            book = held.get(r["account"])
            r["open_side"] = None if book is None else book.get(str(r["symbol"] or ""), "flat")
    accounts = {a: sum(r["account"] == a for r in rows) for a in ("e8", "ftmo", "fusion")}
    return {"schema": "live-roster-v1", "generated_at": now.isoformat(timespec="seconds"),
            "rows": rows, "accounts": accounts, "sources": sources,
            "consumers": "monitors and learners read rows() here, never sleeves.json alone"}


def publish(now: datetime | None = None, *, out: Path | None = None,
            doc: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    doc = doc if doc is not None else build(now, **kw)
    with contextlib.suppress(Exception):
        o = out or OUT
        o.parent.mkdir(parents=True, exist_ok=True)
        tmp = o.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(o)
    return doc


def rows(account: str | None = None, *, path: Path | None = None,
         max_age_s: float = 3 * 3600.0, now: datetime | None = None) -> list[dict[str, Any]]:
    """The roster's rows (optionally one account's). A stale or absent roster returns []: the
    caller must treat that as UNMEASURED via `status()`, never as an empty live book."""
    got = _sr().load_doc(path or OUT, max_age_s=max_age_s, now=now)
    if not got.usable or got.doc is None:
        return []
    rs = [r for r in got.doc.get("rows") or [] if isinstance(r, dict)]
    return [r for r in rs if account is None or r.get("account") == account]


def status(*, path: Path | None = None, max_age_s: float = 3 * 3600.0,
           now: datetime | None = None) -> str:
    return _sr().load_doc(path or OUT, max_age_s=max_age_s, now=now).status
