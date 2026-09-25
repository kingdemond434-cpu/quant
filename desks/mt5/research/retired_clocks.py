"""RETIRED CLOCKS LEAVE THE LIVE STORE -- one retirement vocabulary, one append-only ledger.

    python desks/mt5/research/retired_clocks.py --once            # evacuate (hourly, via repair())
    python desks/mt5/research/retired_clocks.py --query GBPJPY    # the history, by any substring

THE DEFECT THIS CLOSES, measured on the trading box vmi3571445 2026-09-23.
`reports/CERTIFICATE_TRUTH.json` reported 42 divergences, 35 of them fatal -- 23 BANNED_CLOCK and
12 UNBACKED_CLOCK, every one of them a row in `reports/shadow/shadow_state.json` whose own status
field ALREADY said it was retired (`RETIRED_NO_CERTIFICATE`). Nothing was wrong with those clocks
that the desk had not already fixed: `research/clock_liveness.py` had taken every one of their
clocks away hours earlier through `clock_certificate.retire_unbacked`. They kept reporting as live
divergences for two compounding reasons, and both are vocabulary, not evidence:

  1. THE RETIREMENT WORD WAS NOT IN THE READER'S DICTIONARY. `certificate_truth.TERMINAL` was an
     EXACT-MATCH set holding `RETIRED`, `RETIRED_ORPHAN`, `RETIRED_GATE_FAIL` and
     `RETIRED_UNRECONSTRUCTIBLE` -- and `clock_certificate` writes `RETIRED_NO_CERTIFICATE`, which
     is in none of them. So the audit judged every row that organ retired as a running clock.
     `shadow_forward._is_terminal` and `clock_liveness.TERMINAL_PREFIXES` had it right all along
     with a PREFIX rule; two readers of the same rows used exact match and got a different answer.
  2. THE COUNT THEREFORE FLAPPED. `forward_reconcile` re-stamps some of the same rows
     `RETIRED_ORPHAN`, which the exact-match set DID hold. Measured within eleven minutes on the
     box: 35 fatal at 19:59:17 and 0 fatal at 20:09:59, the same rows, the same evidence, a
     different status string written by a different hourly leg. A fence whose verdict depends on
     which leg ran last is not measuring anything.

THE RULE. A retirement is recognised by its PREFIX, never by a spelling an organ has to remember,
so the next organ that invents `RETIRED_BECAUSE_X` is understood by every reader on the day it
ships. And a retired row does not stay where live rows live: it is appended, whole, to
`data/retired_clocks.jsonl` and removed from the clock store, leaving a tombstone in
`retired_clocks` so a reader can still tell the key apart from one that never existed.

NOTHING IS DESTROYED AND NOTHING IS HIDDEN. The ledger is append-only and carries the row as it
stood -- key, store, family, symbol, selector, status, the reason, when it was retired, and the
accrued forward evidence it lost (`n`, `days`, `cum_r`, `first_entry`..`last_entry`) -- which is
the cost `clock_certificate` already states in its own law: "accrued time on an unbacked clock is
DISCARDED and cannot be inherited". It was never written down anywhere before; now it is, and
`--query` reads it back.

WHAT THIS IS NOT. It does not retire anything, ever. It moves rows some other organ has ALREADY
retired, so no clock is stopped here, no count is lowered, no certificate is touched and the live
book is not read. A cell that certifies again gets a NEW clock from zero on the next
`shadow_forward` pass -- the desk's standing law, unchanged, and the tombstone does not block it.

THE REGISTRY IS DELIBERATELY NOT EVACUATED. `data/sleeve_registry.json` is the freeze-then-verify
record, and `sleeve_registry.freeze()` is idempotent BY THE ROW'S PRESENCE: delete a retired row
and the next freeze re-mints it LIVE with a new `forward_start`, which is the silent clock re-base
that destroyed the desk's whole forward book three times in 32 hours on 2026-08-27. The audit
already filters that store to `status == "LIVE"`, so a retired row there is invisible to it
anyway. The evidence stays; only the shadow clock stores are evacuated.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]

#: Statuses that mean "this row is not a live claim" -- matched by PREFIX, so `RETIRED_ORPHAN`,
#: `RETIRED_NO_CERTIFICATE` and anything an organ invents tomorrow are all understood. This is the
#: union of the three vocabularies the desk already carried (`shadow_forward._TERMINAL_STATUSES`,
#: `clock_liveness.TERMINAL_PREFIXES`, `forward_reconcile.TERMINAL`), typed once.
TERMINAL_PREFIXES = ("RETIRED", "VOID", "KILL", "KILLED", "DEAD", "REJECTED", "REFUSED",
                     "QUARANTINED", "QUARANT", "PROMOTED", "IDENTITY_BROKEN",
                     "PROMOTION CANDIDATE")
#: The subset that EVACUATES. A retirement is over; a refusal, a quarantine or a promotion is a
#: standing state the organ that wrote it still reads, so those rows stay exactly where they are.
RETIREMENT_PREFIXES = ("RETIRED", "VOID")

#: Every shadow clock store, and the container its rows live in. The canonical clock store
#: (`data/sleeve_registry.json`) is NOT here -- see the module docstring.
CLOCK_STORES = ("reports/shadow/shadow_state.json",
                "reports/shadow/qquant_shadow_state.json",
                "reports/shadow/scalp_shadow_state.json",
                "reports/shadow/external_shadow_state.json",
                "reports/shadow/precert_shadow_state.json")
#: The append-only history. A row leaves the live store only by arriving here first.
LEDGER = "data/retired_clocks.jsonl"
#: The tombstone container written back into the clock store: a key that was retired is not the
#: same answer as a key that never existed, and a reader in the file must be able to tell them
#: apart without opening the ledger.
TOMBSTONE = "retired_clocks"
#: Fields of the accrued forward evidence the retirement discarded, recorded so the cost is
#: auditable instead of merely stated (`clock_certificate.retire_unbacked`'s own law).
ACCRUED = ("n", "n_historical", "cum_r", "max_dd_r", "exp_r", "days_active", "first_entry",
           "last_entry", "forward_start", "enrolled_at", "sleeve_id", "e_status")
#: Where an organ records WHY it retired the row. The first one present wins; a row that names
#: none is recorded as UNMEASURED, never as "no reason" (L1.28a).
REASON_FIELDS = ("status_why", "retire_reason", "retired_reason", "last_error", "quarantine_reason")
WHEN_FIELDS = ("status_at", "retired_at", "last_attempt_at", "updated_at")


def _up(status: object) -> str:
    return str(status or "").strip().upper()


def _matches(status: object, prefixes: tuple[str, ...]) -> bool:
    """PLAIN prefix, the rule `clock_liveness.is_terminal` already uses.

    `shadow_forward._is_terminal` requires `NAME` or `NAME_...`, which reads `VOIDED_BY_ACCOUNT`
    as a live clock because the word is inflected rather than suffixed. A reader deciding "does
    this row still claim to be running" must err toward believing the organ that wrote the word:
    the cost of reading a stopped clock as stopped is nil, and the cost of the opposite is the 35
    permanent divergences this module exists to end.
    """
    text = _up(status)
    return bool(text) and any(text.startswith(p) for p in prefixes)


def is_terminal(status: object) -> bool:
    """True when `status` means the row is not a live claim. PREFIX rule, never exact match."""
    return _matches(status, TERMINAL_PREFIXES)


def is_retired(status: object) -> bool:
    """True when `status` is a RETIREMENT -- the subset that leaves the live clock store."""
    return _matches(status, RETIREMENT_PREFIXES)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> dict[str, Any] | None:
    """The document, or None when absent or unreadable -- never {} for either (L1.28a)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _atomic(path: Path, doc: Any, indent: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=indent, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _first(row: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for f in fields:
        v = row.get(f)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _identity(key: str, row: dict[str, Any]) -> dict[str, Any]:
    """symbol/family/selector for the ledger row, from the row's own fields then its key shape.

    `certificate_truth.parse_clock_key` is the ONE key grammar this desk writes; it is imported,
    never re-implemented, so the history joins on the same identity the audit and the promoter use.
    A key with no shape leaves the three fields None, which is UNMEASURED and is recorded as such.
    """
    out: dict[str, Any] = {"symbol": row.get("symbol"), "family": row.get("family"),
                           "selector": row.get("selector") or row.get("window")
                           or row.get("session")}
    if not out["symbol"] or not out["family"]:
        try:
            from certificate_truth import (  # type: ignore[import-not-found]
                parse_clock_key,
            )
        except ImportError:                                   # pragma: no cover - standalone use
            try:
                from research.certificate_truth import parse_clock_key
            except ImportError:
                return out
        parsed = parse_clock_key(key) or {}
        for k in ("symbol", "family", "selector"):
            if not out.get(k):
                out[k] = parsed.get(k)
    return out


def ledger_row(store: str, key: str, row: dict[str, Any], stamp: str) -> dict[str, Any]:
    """One history entry: what it was, why it stopped, when, and the evidence it lost."""
    ident = _identity(key, row)
    accrued = {f: row[f] for f in ACCRUED if f in row}
    return {"at": stamp, "store": store, "key": key,
            "symbol": ident.get("symbol"), "family": ident.get("family"),
            "selector": ident.get("selector"),
            "status": row.get("status"),
            "reason": _first(row, REASON_FIELDS) or "UNMEASURED: the row names no retirement "
                                                    "reason",
            "retired_at": _first(row, WHEN_FIELDS) or "UNMEASURED",
            "retired_by": row.get("retired_by") or row.get("status_by") or "UNMEASURED",
            "accrued": accrued,
            "accrued_days": accrued.get("days_active"),
            "accrued_trades": accrued.get("n"),
            "canonical_identity": row.get("canonical_identity"),
            "moved_by": "research/retired_clocks.py",
            "row": row}


def _containers(doc: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    """(container, label) for every place a clock row lives in a state document."""
    out: list[tuple[dict[str, Any], str]] = [(doc, "")]
    sub = doc.get("sleeves")
    if isinstance(sub, dict):
        out.append((sub, "sleeves"))
    return out


def append(base: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p = base / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")


def evacuate(base: Path | None = None, now: str | None = None,
             stores: tuple[str, ...] = CLOCK_STORES) -> dict[str, Any]:
    """Move every ALREADY-RETIRED row out of the shadow clock stores into the ledger.

    Append first, remove second: a crash between the two duplicates a history row, which is
    harmless and visible, while the other order loses the evidence outright.
    """
    root = Path(base or DESK)
    stamp = now or _now()
    out: dict[str, Any] = {"at": stamp, "moved": 0, "by_store": {}, "wrote": [],
                           "ledger": LEDGER, "unreadable": [],
                           "rule": ("a retirement is recognised by its PREFIX "
                                    f"({'/'.join(RETIREMENT_PREFIXES)}) and the row leaves the "
                                    "live clock store for an append-only ledger; nothing is "
                                    "retired here and nothing is destroyed")}
    for rel in stores:
        p = root / rel
        if not p.exists():
            continue
        doc = _read(p)
        if doc is None:
            out["unreadable"].append(rel)          # unreadable is never "nothing to move"
            continue
        name = p.stem
        moved: list[dict[str, Any]] = []
        for container, _label in _containers(doc):
            for key in [k for k, v in list(container.items())
                        if isinstance(v, dict) and "status" in v and is_retired(v.get("status"))]:
                row = container.pop(key)
                moved.append(ledger_row(name, str(key), row, stamp))
        if not moved:
            continue
        append(root, moved)
        stones = doc.setdefault(TOMBSTONE, {})
        if not isinstance(stones, dict):
            stones = {}
            doc[TOMBSTONE] = stones
        for r in moved:
            stones[r["key"]] = {"at": stamp, "status": r["status"], "reason": r["reason"],
                                "accrued_days": r["accrued_days"],
                                "accrued_trades": r["accrued_trades"], "ledger": LEDGER}
        doc["retired_clocks_moved_at"] = stamp
        _atomic(p, doc)
        out["moved"] += len(moved)
        out["by_store"][name] = len(moved)
        out["wrote"].append(rel)
    return out


def query(base: Path | None = None, text: str | None = None, store: str | None = None,
          family: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """The history, newest last, filtered by any substring of the key/symbol/family/reason."""
    p = Path(base or DESK) / LEDGER
    rows: list[dict[str, Any]] = []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return rows
    needle = (text or "").strip().lower()
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        if store and str(r.get("store") or "") != store:
            continue
        if family and str(r.get("family") or "").lower() != family.strip().lower():
            continue
        if needle:
            hay = " ".join(str(r.get(k) or "") for k in
                           ("key", "symbol", "family", "selector", "status", "reason", "store"))
            if needle not in hay.lower():
                continue
        rows.append({k: v for k, v in r.items() if k != "row"})
    return rows[-limit:] if limit and limit > 0 else rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one evacuation pass")
    ap.add_argument("--query", default=None, help="read the history back by substring")
    ap.add_argument("--store", default=None)
    ap.add_argument("--family", default=None)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--base", type=Path, default=DESK, help="desk root (tests)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.query is not None or a.store or a.family:
        rows = query(a.base, a.query, a.store, a.family, a.limit)
        if a.json:
            print(json.dumps(rows, indent=1, default=str))
        else:
            for r in rows:
                print(f"{r.get('at')}  {r.get('store'):<22} {r.get('status'):<24} "
                      f"days={r.get('accrued_days')} n={r.get('accrued_trades')}  {r.get('key')}")
            print(f"{len(rows)} row(s) from {LEDGER}")
        return 0
    acts = evacuate(a.base)
    if a.json:
        print(json.dumps(acts, indent=1, default=str))
    else:
        print(f"retired_clocks: moved {acts['moved']} row(s) {acts['by_store']} -> {LEDGER}"
              + (f"; UNREADABLE {acts['unreadable']}" if acts["unreadable"] else ""))
    return 0


if __name__ == "__main__":
    for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    raise SystemExit(main())
