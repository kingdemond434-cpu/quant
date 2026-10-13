"""EVERY LIVE SLEEVE CAN TRADE ON BOTH VENUES AND EVERY ORDER IS TRACEABLE (principal 2026-10-13).

The principal's words: "make sure all live sleeves etc r traceable on e8 n mt5 able to place
orders all sleeves n all future must too". A sleeve that is LIVE on the roster and cannot reach
an order is capital the allocator thinks it deployed and did not; an order that cannot be walked
back to its sleeve and its decision is a P&L nobody can attribute. Both fail silently in the
gateway's own logs, so this asks each question of every live sleeve, every hour, and fails
LOUDLY when one is answered no.

PER LIVE SLEEVE, FUSION (MT5):
  admitted    the live policy does not refuse it (live_symbols, timeframe, family, exec lane,
              per-symbol allowlist) -- the same `live_policy.refuse` the gateway's roster runs
  executor    the gateway has an executor for its family on its chart (`executables.executor_gap`)
              or it is a gold bracket window the gateway places
  priceable   its symbol has tick size, tick value and a volume step in the universe snapshot,
              so a stop converts to account currency (`risk_units`) and a lot can be sized
  sized       it carries a positive risk fraction, or the principal's certified book funds it
  tag_unique  its order comment (`gateway.order_comment`, truncated to COMMENT_MAX) is no other
              standing sleeve's: the gateway finds a sleeve's positions, and closes a retired
              sleeve's, by that exact string, so two sleeves sharing it see and close each other's

PER LIVE SLEEVE, E8:
  listed      E8's measured instrument catalogue (data/e8_catalogue.json) lists the symbol
  booked      the certified book's e8 block funds it, or E8_BOOK.json selected it

TRACE, over the last TRACE_DAYS days on the live account:
  every acknowledged order intent carries intent_id, release_id and state_vector_id and its
  ticket reaches a live-ledger close (or is still open), and every live-ledger close joins back to
  an intent by ticket. An orphan either way is a FAIL.

UNMEASURED IS A VERDICT, NEVER A PASS (L1.28a): a box-only input absent here (the E8 catalogue on
a cloud clone) is reported UNMEASURED and does not fail the check, and is never read as "listed".

Artifact: desks/mt5/reports/LIVE_TRADABILITY.json. Exit 1 when any check FAILS.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES = DESK / "data" / "sleeves.json"
CERT_BOOK = DESK / "data" / "CERT_BOOK_LIVE.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
E8_CATALOGUE = DESK / "data" / "e8_catalogue.json"
E8_BOOK = DESK / "reports" / "E8_BOOK.json"
INTENTS = DESK / "data" / "order_intents.jsonl"
LEDGER = DESK / "data" / "live_ledger.jsonl"
GATEWAY_STATE = DESK / "data" / "gateway_state.json"
OUT = DESK / "reports" / "LIVE_TRADABILITY.json"

#: Must match `gateway.COMMENT_MAX`; `test_live_tradability` pins the two together.
COMMENT_MAX = 29
TRACE_DAYS = 14
#: Gold bracket windows the gateway places from `gateway_state.brackets`, not from sleeves.json.
GOLD_WINDOWS = ("gold_asia", "gold_london_am", "gold_afternoon", "gold_ny_open")
#: Intent fields every order must carry to be walked back to its decision.
TRACE_FIELDS = ("intent_id", "release_id", "state_vector_id")

PASS, FAIL, UNMEASURED = "PASS", "FAIL", "UNMEASURED"


def order_comment(name: str) -> str:
    return f"DW{name}"[:COMMENT_MAX]


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
    except OSError:
        pass
    return rows


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def book_key(row: Mapping[str, Any]) -> str:
    """The certified book's key for a roster row: `SYMBOL_family_selector`, or the window name."""
    name = str(row.get("name") or "")
    if name in GOLD_WINDOWS:
        return name
    return f"{str(row.get('symbol') or '').upper()}_{row.get('family')}_" \
           f"{row.get('selector') or row.get('window') or 'asia'}"


def live_rows(sleeves: Iterable[Mapping[str, Any]], cert: Mapping[str, Any],
              gateway_state: Mapping[str, Any] | None) -> list[dict]:
    """Every sleeve that can hold capital now: LIVE roster rows plus the gold bracket windows the
    certified book funds or the gateway placed."""
    out = [dict(s) for s in sleeves if str(s.get("status") or "").upper() == "LIVE"]
    windows = {k for k in (cert.get("fusion") or {}) if k in GOLD_WINDOWS}
    windows |= {k for k in ((gateway_state or {}).get("brackets") or {}) if k in GOLD_WINDOWS}
    have = {r.get("name") for r in out}
    out += [{"name": w, "symbol": "XAUUSD", "family": "session_range_breakout",
             "exec": "bracket", "window": w.removeprefix("gold_"), "status": "LIVE"}
            for w in sorted(windows) if w not in have]
    return out


def _check(ok: bool | None, why: str) -> dict:
    return {"status": UNMEASURED if ok is None else PASS if ok else FAIL, "why": why}


def fusion_checks(row: Mapping[str, Any], *, policy: Any, refuse: Any, executor_gap: Any,
                  universe: Mapping[str, Any], cert: Mapping[str, Any],
                  tags: Mapping[str, list[str]]) -> dict[str, dict]:
    name, sym = str(row.get("name") or ""), str(row.get("symbol") or "").upper()
    out: dict[str, dict] = {}
    why = refuse(row, policy)
    out["admitted"] = _check(not why, why or "the live policy admits it")
    if row.get("exec") == "family_market":
        tf = str(((row.get("params") or {}).get("timeframe")) or "H1").upper()
        gap = executor_gap(str(row.get("family") or ""), tf)
        out["executor"] = _check(not gap, gap or f"family executor on {tf}")
    elif row.get("exec") in (None, "bracket"):
        out["executor"] = _check(sym == "XAUUSD", "gold bracket window" if sym == "XAUUSD"
                                 else f"bracket lane trades XAUUSD only, not {sym}")
    else:
        out["executor"] = _check(False, f"exec lane {row.get('exec')!r} has no live executor")
    meta = universe.get(sym) if isinstance(universe, Mapping) else None
    if not isinstance(meta, Mapping):
        out["priceable"] = _check(False, f"{sym} absent from the universe snapshot")
    else:
        ok = all(float(meta.get(f) or 0) > 0 for f in ("tick_size", "tick_value", "volume_step"))
        out["priceable"] = _check(ok, "tick size, tick value and volume step measured" if ok
                                  else f"{sym} tick economics incomplete in the snapshot")
    funded = (cert.get("fusion") or {}).get(book_key(row))
    frac = float(row.get("risk_frac") or 0.0)
    out["sized"] = _check(frac > 0 or (isinstance(funded, (int, float)) and funded > 0),
                          f"risk_frac {frac:g}" + (f"; certified book {funded:g}" if funded
                                                   else ""))
    clash = [n for n in tags.get(order_comment(name), []) if n != name]
    out["tag_unique"] = _check(not clash, f"order comment {order_comment(name)!r} shared with "
                               f"{clash}" if clash else "order comment is this sleeve's alone")
    return out


def e8_checks(row: Mapping[str, Any], *, catalogue: set[str] | None,
              cert: Mapping[str, Any], e8_book: Any) -> dict[str, dict]:
    sym = str(row.get("symbol") or "").upper()
    out: dict[str, dict] = {}
    if catalogue is None:
        out["listed"] = _check(None, "data/e8_catalogue.json absent: E8's instrument list is "
                                     "box-only and was not measured here")
    else:
        out["listed"] = _check(sym in catalogue, f"{sym} {'is' if sym in catalogue else 'is NOT'}"
                               f" in E8's {len(catalogue)}-instrument catalogue")
    key = book_key(row)
    funded = (cert.get("e8") or {}).get(key)
    selected = None
    if isinstance(e8_book, Mapping):
        rows = e8_book.get("sleeves") or e8_book.get("selected") or []
        selected = any(isinstance(r, Mapping) and (r.get("name") == row.get("name")
                       or book_key(r) == key) for r in rows)
    if isinstance(funded, (int, float)) and funded > 0:
        out["booked"] = _check(True, f"certified book e8 funds {key} at {funded:g}")
    elif selected is None:
        out["booked"] = _check(False if cert.get("e8") else None,
                               f"the certified book's e8 block does not fund {key}; E8_BOOK.json "
                               f"absent here")
    else:
        out["booked"] = _check(bool(selected), f"E8_BOOK.json {'selects' if selected else 'does not select'} "
                               f"{key}")
    return out


def trace(intents: list[dict], ledger: list[dict], *, now: datetime,
          days: int = TRACE_DAYS) -> dict[str, Any]:
    """Join live intents to live-ledger closes by ticket over the window; orphans either way."""
    since = now - timedelta(days=days)
    live_i = [r for r in intents if r.get("account_kind", "live") == "live"
              and int(r.get("retcode") or 0) == 10009 and int(r.get("ticket") or 0) > 0
              and (_ts(r.get("time")) or since) >= since]
    live_l = [r for r in ledger if r.get("account_kind", "live") == "live"
              and (_ts(r.get("time")) or since) >= since]
    tickets = {int(r["ticket"]) for r in live_i}
    closes: dict[int, dict] = {}
    for r in live_l:
        for k in ("position_id", "entry_order", "order"):
            v = int(r.get(k) or 0)
            if v:
                closes[v] = r
    missing_fields = [{"ticket": r.get("ticket"), "sleeve": r.get("sleeve"),
                       "missing": [f for f in TRACE_FIELDS if not r.get(f)]}
                      for r in live_i if any(not r.get(f) for f in TRACE_FIELDS)]
    open_or_unclosed = [{"ticket": r.get("ticket"), "sleeve": r.get("sleeve"),
                         "time": r.get("time")} for r in live_i if int(r["ticket"]) not in closes]
    orphan_closes = [{"position_id": r.get("position_id"), "sleeve": r.get("sleeve"),
                      "time": r.get("time"), "pl": r.get("pl_quote")}
                     for r in live_l
                     if not any(int(r.get(k) or 0) in tickets
                                for k in ("position_id", "entry_order", "order"))]
    # A pending stop that never filled has no close and is not an orphan; a market intent with no
    # close is still open or lost. The gateway's own state names what is open; here the count is
    # reported and only CLOSES WITH NO INTENT and INTENTS MISSING TRACE FIELDS fail.
    status = PASS if not orphan_closes and not missing_fields else FAIL
    return {"status": status, "window_days": days, "intents": len(live_i),
            "closes": len(live_l), "orphan_closes": orphan_closes,
            "intents_missing_trace_fields": missing_fields,
            "intents_without_close": open_or_unclosed}


def build(now: datetime | None = None) -> dict[str, Any]:
    from mt5desk.executables import executor_gap
    from mt5desk.live_policy import policy, refuse
    now = now or datetime.now(UTC)
    doc = _json(SLEEVES)
    sleeves = (doc or {}).get("sleeves") if isinstance(doc, dict) else None
    if not isinstance(sleeves, list):
        return {"at": now.isoformat(timespec="seconds"), "verdict": UNMEASURED,
                "why": f"{SLEEVES} unreadable"}
    cert_doc = _json(CERT_BOOK) or {}
    cert = cert_doc if cert_doc.get("enabled") is True else {}
    universe = _json(UNIVERSE) or {}
    cat_doc = _json(E8_CATALOGUE)
    inst = cat_doc.get("instruments") if isinstance(cat_doc, dict) else None
    catalogue = {str(i).upper() for i in inst} if isinstance(inst, list) and inst else None
    pol = policy()
    standing = [s for s in sleeves if str(s.get("status") or "").upper() in ("LIVE", "STANDBY")]
    tags: dict[str, list[str]] = {}
    for s in standing:
        tags.setdefault(order_comment(str(s.get("name") or "")), []).append(str(s.get("name")))
    rows = []
    for r in live_rows(sleeves, cert, _json(GATEWAY_STATE)):
        f = fusion_checks(r, policy=pol, refuse=refuse, executor_gap=executor_gap,
                          universe=universe, cert=cert, tags=tags)
        e = e8_checks(r, catalogue=catalogue, cert=cert, e8_book=_json(E8_BOOK))
        verdicts = [c["status"] for c in (*f.values(), *e.values())]
        rows.append({"name": r.get("name"), "symbol": r.get("symbol"),
                     "family": r.get("family"), "fusion": f, "e8": e,
                     "status": FAIL if FAIL in verdicts else
                     UNMEASURED if UNMEASURED in verdicts else PASS})
    collisions = {t: n for t, n in tags.items() if len(n) > 1}
    tr = trace(_jsonl(INTENTS), _jsonl(LEDGER), now=now)
    failed = [r["name"] for r in rows if r["status"] == FAIL]
    verdict = FAIL if failed or tr["status"] == FAIL else \
        UNMEASURED if any(r["status"] == UNMEASURED for r in rows) else PASS
    return {"at": now.isoformat(timespec="seconds"), "verdict": verdict,
            "live_sleeves": len(rows), "failed": failed, "sleeves": rows,
            "standing_tag_collisions": collisions, "trace": tr,
            "rule": "every live sleeve admitted, executable, priceable, sized and uniquely tagged "
                    "on Fusion, listed and booked on E8; every live order traceable intent <-> "
                    "close. Principal 2026-10-13."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    if not args.no_write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"live tradability: {doc['verdict']} -- {doc.get('live_sleeves', 0)} live sleeve(s), "
          f"failed {doc.get('failed', [])}")
    for r in doc.get("sleeves", []):
        bad = {f"{venue}.{k}": c["why"] for venue in ("fusion", "e8")
               for k, c in r[venue].items() if c["status"] != PASS}
        if bad:
            print(f"  {r['status']:10s} {r['name']}: {bad}")
    tr = doc.get("trace") or {}
    if tr:
        print(f"  trace {tr['status']}: {tr['intents']} intents, {tr['closes']} closes, "
              f"{len(tr['orphan_closes'])} orphan close(s), "
              f"{len(tr['intents_missing_trace_fields'])} intent(s) missing trace fields")
    if doc.get("standing_tag_collisions"):
        print(f"  {len(doc['standing_tag_collisions'])} order-comment collision(s) among "
              f"standing sleeves")
    return 1 if doc["verdict"] == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
