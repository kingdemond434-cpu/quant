"""ZERO LIVE ON A TRADING DAY IS A MONEY-PATH PAGE (pass rule I2 CONVERSION, 2026-11-25).

Standing rule (zuck, 2026-11-25 01:53Z): every certified, non-exotic survivor flows to every
account by itself. On 11-25 the box held 0 LIVE sleeves on Fusion, 0 selected on E8 and an
allocator book four days stale, and the only place that said so was one report line in
`scripts/check_desk_health.py` (Fusion's sleeves.json only, never paged). This organ reads each
account's own book once an hour and pages Claude (provenance._page: enqueue-only outbox, delivered
by MT5-BoxHeartbeat) when a FUNDED account trades nothing on a market day, naming its stop.

PER ACCOUNT, FROM THE BOOK THAT ACCOUNT'S EXECUTOR TRADES (never inferred from another's):
  e8      reports/E8_BOOK.json      `sleeves` (the certified non-gold book prop/e8_executor reads)
  ftmo    reports/FTMO_ALLOCATOR.json `executable` positive fractions with `deployable` true
  fusion  data/sleeves.json         LIVE rows; data/GATEWAY_PAUSED present reads PAUSED (Fusion
          is unfunded by the principal's withdrawal), which is reported and never paged.
An unreadable or stale (> BOOK_MAX_AGE_H) book is UNMEASURED, and UNMEASURED on a market day pages
too: a book nobody can read is an account nobody can show is trading (L1.28a).

WHAT IT NEVER DOES: open, close or size anything. It reads files and writes one report,
reports/ZERO_LIVE_PAGE.json, which the Hourly pass board reads.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "ZERO_LIVE_PAGE.json"
E8_BOOK = DESK / "reports" / "E8_BOOK.json"
FTMO_BOOK = DESK / "reports" / "FTMO_ALLOCATOR.json"
SLEEVES = DESK / "data" / "sleeves.json"
PAUSE = DESK / "data" / "GATEWAY_PAUSED"
#: E8_BOOK is rebuilt every pass and the executor itself refuses a book older than 2h; the
#: allocators run hourly. Six hours is several missed rebuilds, never one late one.
BOOK_MAX_AGE_H = 6.0
ALERT_ID = "zero_live_on_trading_day"

LIVE, ZERO, PAUSED, UNMEASURED = "LIVE", "ZERO_LIVE", "PAUSED", "UNMEASURED"


def market_day(now: datetime) -> bool:
    """FX trades Sunday 22:00 UTC to Friday 22:00 UTC; a market day is any UTC hour inside it."""
    wd, h = now.weekday(), now.hour
    if wd == 5:
        return False
    if wd == 6:
        return h >= 22
    return not (wd == 4 and h >= 22)


def _read(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, f"{path.name} unreadable ({type(exc).__name__})"


def _age_h(stamp: Any, now: datetime) -> float | None:
    try:
        at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if at.tzinfo is None:
        return None
    return (now - at).total_seconds() / 3600.0


def _top(rows: Any, key: str = "why", n: int = 3) -> list[str]:
    counts: dict[str, int] = {}
    for r in rows if isinstance(rows, list) else []:
        w = str((r.get(key) if isinstance(r, dict) else r) or "")[:120]
        if w:
            counts[w] = counts.get(w, 0) + 1
    return [f"{w} (x{c})" for w, c in sorted(counts.items(), key=lambda kv: -kv[1])[:n]]


def e8(now: datetime, path: Path | None = None) -> dict[str, Any]:
    doc, why = _read(path or E8_BOOK)
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "why": why or "E8_BOOK.json is not an object"}
    age = _age_h(doc.get("generated_utc"), now)
    if age is None or age > BOOK_MAX_AGE_H:
        return {"status": UNMEASURED, "why": f"E8_BOOK.json is stale or unstamped (age {age})"}
    n = len(doc.get("sleeves") or [])
    if n:
        return {"status": LIVE, "n": n, "age_h": round(age, 2)}
    stops = [f"n_certified {doc.get('n_certified')}, n_tradeable {doc.get('n_tradeable')}"]
    stops += _top(doc.get("blocked_by_integrity"))
    cuts = ((doc.get("stress") or {}).get("cuts") or [])
    if cuts:
        stops.append(f"stress cap cut {len(cuts)} sleeve(s)")
    return {"status": ZERO, "n": 0, "age_h": round(age, 2), "stops": stops}


def ftmo(now: datetime, path: Path | None = None) -> dict[str, Any]:
    doc, why = _read(path or FTMO_BOOK)
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "why": why or "FTMO_ALLOCATOR.json is not an object"}
    age = _age_h(doc.get("generated_utc") or doc.get("at") or doc.get("generated_at"), now)
    if age is None or age > BOOK_MAX_AGE_H:
        return {"status": UNMEASURED, "why": f"FTMO_ALLOCATOR.json is stale or unstamped "
                                              f"(age {age})"}
    ex = {c: v for c, v in (doc.get("executable") or {}).items()
          if isinstance(v, (int, float)) and v > 0}
    if ex and doc.get("deployable", True) is not False:
        return {"status": LIVE, "n": len(ex), "age_h": round(age, 2)}
    stops = [f"status {doc.get('status')}", f"deployable {doc.get('deployable')}"]
    for ph, blk in (doc.get("phases") or {}).items():
        if isinstance(blk, dict) and blk.get("status") not in (None, "OK"):
            stops.append(f"{ph}: {blk.get('status')}")
    return {"status": ZERO, "n": 0, "age_h": round(age, 2), "stops": stops}


def fusion(path: Path | None = None, pause: Path | None = None) -> dict[str, Any]:
    if (pause or PAUSE).exists():
        return {"status": PAUSED, "why": "data/GATEWAY_PAUSED present (Fusion unfunded); "
                                         "trading resumes on deposit"}
    doc, why = _read(path or SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return {"status": UNMEASURED, "why": why or "sleeves.json has no sleeve list"}
    st = [str(r.get("status") or "") for r in rows if isinstance(r, dict)]
    if st.count("LIVE"):
        return {"status": LIVE, "n": st.count("LIVE")}
    standby = [r for r in rows if isinstance(r, dict) and r.get("status") == "STANDBY"]
    return {"status": ZERO, "n": 0, "stops": [f"{len(standby)} STANDBY"] + _top(
        [(r.get("admission") or {}).get("why") for r in standby], key="why")}


def assess(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    accounts = {"e8": e8(now), "ftmo": ftmo(now), "fusion": fusion()}
    trading = market_day(now)
    down = sorted(a for a, v in accounts.items() if v["status"] in (ZERO, UNMEASURED))
    page = trading and bool(down)
    return {"at": now.isoformat(timespec="seconds"), "market_day": trading,
            "accounts": accounts, "not_trading": down, "page": page,
            "status": ("PAGE" if page else "OK" if trading else "CLOSED"),
            "consumer": "the Hourly pass board reads reports/ZERO_LIVE_PAGE.json; the page goes "
                        "to Claude through provenance._page"}


def _send(doc: dict[str, Any]) -> dict[str, Any]:
    """Page (or clear) through provenance._page. Never raises; returns what it answered."""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops import provenance
        fn = getattr(provenance, "_page", None)
        if not callable(fn):
            return {"sent": False, "why": "provenance._page absent on this tree"}
        if doc["page"]:
            lines = []
            for a in doc["not_trading"]:
                v = doc["accounts"][a]
                lines.append(f"{a}: {v['status']} -- {v.get('why') or '; '.join(v.get('stops') or [])}")
            sig = "|".join(f"{a}:{doc['accounts'][a]['status']}" for a in doc["not_trading"])
            res = fn(ALERT_ID, "OPEN", sig,
                     f"MONEY PATH: {', '.join(doc['not_trading'])} trading nothing on a market day",
                     "\n".join(lines)[:1500])
        else:
            res = fn(ALERT_ID, "OK", "trading", "MONEY PATH: every funded account has a live book",
                     "zero-live page cleared")
        return res if isinstance(res, dict) else {"sent": False, "why": "no answer"}
    except Exception as exc:
        return {"sent": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


def main(argv: list[str] | None = None) -> int:
    doc = assess()
    doc["pager"] = _send(doc) if "--no-page" not in (argv or sys.argv[1:]) else {"sent": False,
                                                                                  "why": "--no-page"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("status", "not_trading", "market_day")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
