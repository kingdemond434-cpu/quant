"""IMMUTABLE FORWARD CLOCKS, ENFORCED AT THE WRITER -- churn made impossible, not reported.

THE GAP THE LEDGER NAMED (Tier-1 B20): *"a forward clock's start can still move at the writer; a
churned clock is reported rather than made impossible."* `scripts/check_forward_clock_ratchet.py`
has DETECTED silent rebases since 2026-08-27 and `shadow_forward.clock_breaches()` reads them --
after the fact, after the pre-registered days are already gone. Detection is not prevention: the
number the whole path to live capital turns on (L1.58, `days >= 14`) was still being written by a
line that could hand back today's date for a window opened three weeks ago.

THE RULE, and it is one line of arithmetic applied at the only door that writes the number:

    start(key, identity) = min(recorded_start, proposed)

A LATER proposal is REFUSED and the recorded start stands -- that is the churn, and it can no
longer happen. An EARLIER proposal is ACCEPTED and recorded, because an earlier start means the
window is OLDER than the writer thought: the sleeve is closer to its bar, never further, so the
monotone direction of this rule can only ever move a certificate TOWARD live capital. That
asymmetry is deliberate and is what makes this legal under the principal's never-reduce-
aggressiveness order: nothing here caps enrolment, refuses a sleeve, or lengthens a wait.

A NEW IDENTITY OPENS A NEW CLOCK, IT DOES NOT MOVE THE OLD ONE. When the identity hash changes --
the family's source, its behaviour, the cost model, the direction, the chart -- the old clock is
KEPT with its whole history and a fresh clock is opened beside it, with its own start, and the
lineage recorded. Before this, a changed identity meant a row whose start was simply overwritten:
the desk lost both the old window's evidence and the fact that it had ever existed.

    identity ""    inherits the key's current clock. `shadow_forward` stamps the start BEFORE it
                   can compute the registry identity (that ordering is itself a fix: the stamp
                   used to happen fifty lines after the freeze, which froze `forward_start: null`
                   permanently). A later call carrying the real identity ADOPTS the same clock
                   rather than opening a second one -- the clock's identity is learned, never
                   its start.

WHAT IT PUBLISHES. Every refused move, every new clock, every lineage, plus a verification pass
over the live shadow ledger: any key whose live `forward_start` is LATER than this ledger's is
churn that happened outside the door, and it is named in `churn_outside_the_door`.

    python desks/mt5/research/clock_ledger.py --once --budget-s 60
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LEDGER = DESK / "data" / "forward_clock_ledger.json"
SHADOW_STATES = ("shadow_state.json", "shadow_state_qquant.json", "shadow_state_scalp.json")
OUT = DESK / "reports" / "FORWARD_CLOCK_LEDGER.json"
MAX_REFUSALS = 50          # per clock, newest kept: the record is evidence, not a growing file


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def _iso(value: Any) -> str | None:
    """A comparable ISO-8601 UTC string, or None when the value is not a time."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _clock_id(key: str, identity: str) -> str:
    return f"{key}|{(identity or '')[:24]}"


def stamp(key: str, identity: str, proposed: Any, *, path: Path = LEDGER) -> dict[str, Any]:
    """THE WRITER'S DOOR. Returns the start `key` may use, which is never later than the one it
    already had. `shadow_forward` writes exactly what comes back.

    identity ""        adopt the key's current clock, whatever identity it carries
    identity unchanged the recorded start stands; a later proposal is refused and recorded
    identity new       a NEW clock opens beside the old one, which is kept intact
    """
    doc = _read(path)
    _clocks = doc.get("clocks")
    clocks: dict[str, Any] = dict(_clocks) if isinstance(_clocks, dict) else {}
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    want = _iso(proposed) or now
    ident = str(identity or "")

    current_id = None
    for cid, row in clocks.items():
        if not isinstance(row, dict) or str(row.get("key")) != key or row.get("closed"):
            continue
        if ident and str(row.get("identity") or "") not in ("", ident):
            continue
        current_id = cid
        break

    if current_id is None:
        superseded = [cid for cid, row in clocks.items()
                      if isinstance(row, dict) and str(row.get("key")) == key
                      and not row.get("closed")]
        for cid in superseded:
            clocks[cid]["closed"] = now
            clocks[cid]["closed_why"] = f"identity changed to {ident[:16]}"
        cid = _clock_id(key, ident)
        while cid in clocks:
            cid += "+"
        clocks[cid] = {"key": key, "identity": ident, "start": want, "opened_at": now,
                       "writes": 1, "refused_moves": [], "supersedes": superseded}
        doc["clocks"] = clocks
        _write(path, doc)
        return {"start": want, "clock_id": cid, "opened_new_clock": True, "refused": False,
                "supersedes": superseded,
                "why": ("a new identity opens a new clock; any previous clock for this key is "
                        "kept with its whole history" if superseded else "first clock for key")}

    row = clocks[current_id]
    have = _iso(row.get("start")) or want
    row["writes"] = int(row.get("writes") or 0) + 1
    row["last_seen"] = now
    if ident and not row.get("identity"):
        row["identity"] = ident                       # the clock learns its identity, not a start
        row["identity_learned_at"] = now
    if want > have:
        refusals = row.get("refused_moves") or []
        refusals.append({"proposed": want, "kept": have, "at": now})
        row["refused_moves"] = refusals[-MAX_REFUSALS:]
        clocks[current_id] = row
        doc["clocks"] = clocks
        _write(path, doc)
        return {"start": have, "clock_id": current_id, "opened_new_clock": False,
                "refused": True,
                "why": (f"a later start was proposed ({want}) and refused: the recorded window "
                        f"opened at {have} and pre-registered days are not destroyed")}
    if want < have:
        row["start"] = want
        row.setdefault("extensions", []).append({"was": have, "now": want, "at": now})
        row["extensions"] = row["extensions"][-MAX_REFUSALS:]
    clocks[current_id] = row
    doc["clocks"] = clocks
    _write(path, doc)
    return {"start": row["start"], "clock_id": current_id, "opened_new_clock": False,
            "refused": False,
            "why": ("an earlier start was accepted: the window is older than the writer thought, "
                    "which can only move a sleeve toward its bar" if want < have
                    else "the recorded start stands")}


def start_for(key: str, identity: str = "", *, path: Path = LEDGER) -> str | None:
    """The recorded start for a key's live clock, without writing anything."""
    doc = _read(path)
    for row in (doc.get("clocks") or {}).values():
        if not isinstance(row, dict) or str(row.get("key")) != key or row.get("closed"):
            continue
        if identity and str(row.get("identity") or "") not in ("", identity):
            continue
        return _iso(row.get("start"))
    return None


def verify(path: Path = LEDGER) -> dict[str, Any]:
    """Every live shadow row against the ledger: a LATER live start is churn outside the door."""
    doc = _read(path)
    clocks = doc.get("clocks") or {}
    by_key: dict[str, str] = {}
    for row in clocks.values():
        if isinstance(row, dict) and not row.get("closed"):
            s = _iso(row.get("start"))
            if s:
                by_key[str(row.get("key"))] = s
    churn: list[dict[str, Any]] = []
    checked = 0
    unledgered = 0
    for name in SHADOW_STATES:
        state = _read(DESK / "data" / name)
        rows = state.get("sleeves") if isinstance(state.get("sleeves"), dict) else state
        if not isinstance(rows, dict):
            continue
        for key, st in rows.items():
            if not isinstance(st, dict) or not st.get("forward_start"):
                continue
            checked += 1
            live = _iso(st.get("forward_start"))
            have = by_key.get(str(key))
            if have is None:
                unledgered += 1
                continue
            if live and live > have:
                churn.append({"ledger": name, "key": key, "ledger_start": have,
                              "live_start": live})
    return {"n_checked": checked, "n_unledgered": unledgered,
            "churn_outside_the_door": churn,
            "rule": ("a live forward_start LATER than the ledger's means something wrote the "
                     "clock without passing through stamp(); the ledger's start is the truth")}


def build(budget_s: float = 60.0, path: Path = LEDGER) -> dict[str, Any]:
    t0 = time.monotonic()
    doc = _read(path)
    clocks = doc.get("clocks") or {}
    live = {cid: r for cid, r in clocks.items() if isinstance(r, dict) and not r.get("closed")}
    closed = {cid: r for cid, r in clocks.items() if isinstance(r, dict) and r.get("closed")}
    refused = sum(len(r.get("refused_moves") or []) for r in clocks.values()
                  if isinstance(r, dict))
    extended = sum(len(r.get("extensions") or []) for r in clocks.values() if isinstance(r, dict))
    v = verify(path)
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": ("OK" if clocks else "UNMEASURED"),
        "n_clocks": len(clocks), "n_live": len(live), "n_closed_by_identity": len(closed),
        "n_refused_moves": refused, "n_earlier_starts_accepted": extended,
        "verification": v,
        "ledger": str(path),
        "oldest_live": min((str(r.get("start")) for r in live.values()), default=None),
        "rule": ("start = min(recorded, proposed) for an unchanged identity; a new identity "
                 "opens a NEW clock and keeps the old one. A later start is impossible at the "
                 "writer, not merely reported after it happened."),
        "consumers": [
            "desks/mt5/research/shadow_forward.py -> stamp(): the only line that writes "
            "forward_start now returns the ledger's start",
            "desks/mt5/research/promoter.py (sealed, unchanged) reads forward_start downstream, "
            "so days_active is computed on a window that cannot be rebased",
            "desks/mt5/research/quantbench.py case QB003 replays the monotonicity every hour",
        ],
        "boundary": (
            "NOTHING IS CAPPED, REFUSED OR SLOWED. The only refusal this organ can make is of a "
            "LATER start, which destroys pre-registered days; an EARLIER start is always "
            "accepted. Enrolment is untouched: every sleeve that would have been enrolled is "
            "still enrolled, on a clock that can only be the same age or older."),
        "seconds": round(time.monotonic() - t0, 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=60.0)
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, path=a.ledger)
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"clock ledger: could not write {OUT}: {exc}")
        return 1
    v = doc["verification"]
    print(f"clock ledger: {doc['n_live']} live clock(s), {doc['n_closed_by_identity']} closed by "
          f"an identity change, {doc['n_refused_moves']} refused move(s), "
          f"{doc['n_earlier_starts_accepted']} earlier start(s) accepted")
    print(f"  verification: {v['n_checked']} live row(s) checked, "
          f"{len(v['churn_outside_the_door'])} churned outside the door, "
          f"{v['n_unledgered']} not yet in the ledger")
    for row in v["churn_outside_the_door"][:8]:
        print(f"   CHURN {row['key'][:48]:<48} ledger={row['ledger_start']} "
              f"live={row['live_start']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
