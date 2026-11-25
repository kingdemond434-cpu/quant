"""ONE TRIGGER, EVERY ALLOCATOR: re-solve the moment the account changes, not only on the hour.

The principal, 2026-11-13: the allocators recompute on an event as well as on their clock, and
this applies to ALL of them. The hourly solve stays as the baseline. This organ watches the
published account and certificate state, names what changed, and starts each SUBSCRIBED
allocator's own registered task at once (`schtasks /Run`), so the solve that runs is exactly the
one the clock would have run, just sooner. It never sizes, never sends an order, and never edits
a limit or a permission: the allocator it starts applies every survival rail it always applies.

THE EVENTS (each a diff of a published snapshot against the last one this organ saw):
  FILL            the account's open positions changed (a fill, a stop, a target, a close);
  ORDER           new acknowledged rows on the order door for that account's callers;
  DAILY_ROOM      the share of the day's loss limit already used crossed a quarter step,
                  either way (equity moving toward the daily limit, or recovering from it);
  PHASE           the challenge phase changed (phase1 -> phase2 -> funded);
  NEW_CERTIFIED   the certified roster gained a certificate (every subscriber).

A first sighting records the snapshot and starts nothing. An unreadable source is UNMEASURED for
that subscriber, never a quiet "nothing changed".

SUBSCRIBERS are rows of `SUBSCRIBERS`: the allocator's task, which account events it hears,
and its debounce. Another allocator subscribes by adding a row (the growth allocator's owner adds
its own). A subscriber started less than its debounce ago keeps its events PENDING and is
started on the first pass after the gap, so a burst of fills costs one re-solve, not ten.

Clock: `prop/ftmo_venue_reader.py` calls `run()` at the end of every pass (every 5 minutes).
Writes `reports/ALLOCATOR_TRIGGERS.json`, `data/allocator_triggers_state.json` and appends each
dispatch to `data/allocator_triggers.jsonl`.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPORTS, DATA = BASE / "reports", BASE / "data"
OUT = REPORTS / "ALLOCATOR_TRIGGERS.json"
STATE = DATA / "allocator_triggers_state.json"
LEDGER = DATA / "allocator_triggers.jsonl"
FTMO_STATE = REPORTS / "FTMO_ACCOUNT_STATE.json"
E8_EXEC = REPORTS / "E8_EXEC.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
DOOR = DATA / "order_door_ledger.jsonl"
DOOR_TAIL_BYTES = 2_000_000
#: The firm's daily loss limits as fractions of the reference balance (prop_challenge_allocator
#: rules: FTMO 5% of the initial balance; E8 measures from the day's start in e8_guard).
FTMO_DAILY = 0.05
ROOM_STEP = 0.25

#: subscriber -> (registered task, the account whose events it hears or None for all, debounce s)
SUBSCRIBERS: dict[str, tuple[str, str | None, int]] = {
    "ftmo_allocator": ("MT5-FTMO-Allocator", "ftmo", 600),
    "e8_book": ("E8-Book", "e8", 600),
    "fusion_allocator": ("MT5-AllocatorFast", "fusion", 300),
}
#: order-door caller prefixes per account
CALLERS = {"ftmo": ("ftmo",), "e8": ("e8",), "fusion": ("gateway", "mt5desk")}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _bucket(used_share: float) -> int:
    return int(max(0.0, min(used_share, 1.0)) / ROOM_STEP)


def _positions_sig(rows: Any) -> str:
    if not isinstance(rows, list):
        return ""
    keys = sorted(f"{r.get('symbol')}|{r.get('side')}|{r.get('volume')}" for r in rows
                  if isinstance(r, dict))
    return hashlib.sha256("\n".join(keys).encode()).hexdigest()[:16]


def ftmo_snapshot(doc: Any) -> dict[str, Any] | None:
    """Phase, position signature and daily-room bucket off FTMO_ACCOUNT_STATE.json."""
    if not isinstance(doc, dict) or doc.get("status") not in ("OK", "UNMEASURED") \
            or "equity" not in doc:
        return None
    try:
        initial, start = float(doc["initial_balance"]), float(doc["day_start_balance"])
        used = max(0.0, start - float(doc["equity"])) / (FTMO_DAILY * initial)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return {"phase": doc.get("phase"), "positions": _positions_sig(doc.get("open_positions")),
            "room_bucket": _bucket(used)}


def e8_snapshot(doc: Any) -> dict[str, Any] | None:
    """Daily-room bucket off E8_EXEC.json's guard (room to the day's floor against its depth)."""
    g = (doc or {}).get("guard") if isinstance(doc, dict) else None
    if not isinstance(g, dict):
        return None
    try:
        start, room = float(g["day_start"]), float(g["room_to_daily_floor"])
        depth = start - (float(g["equity"]) - room)          # day_start - daily floor
        used = 1.0 - room / depth if depth > 0 else 0.0
    except (KeyError, TypeError, ValueError):
        return None
    return {"room_bucket": _bucket(used), "phase": g.get("phase")}


def roster_snapshot(doc: Any) -> dict[str, Any] | None:
    surv = (doc or {}).get("survivors") if isinstance(doc, dict) else None
    if not isinstance(surv, dict):
        return None
    return {"n": len(surv), "keys": sorted(surv)}


def door_counts(path: Path | None = None) -> dict[str, str] | None:
    """Acknowledged order-door rows per account, off the ledger's tail (None when unreadable)."""
    path = path or DOOR
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            fh.seek(max(0, path.stat().st_size - DOOR_TAIL_BYTES))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    out = dict.fromkeys(CALLERS, 0)
    last = dict.fromkeys(CALLERS, "")
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("outcome") not in ("acknowledged", "ok", "sent"):
            continue
        pre = str(r.get("caller") or "").split(":")[0].split("_")[0]
        for acct, prefixes in CALLERS.items():
            if pre in prefixes:
                out[acct] += 1
                last[acct] = max(last[acct], str(r.get("at") or ""))
    # A plain string, never hash(): str hashing is salted per process.
    return {a: f"{out[a]}|{last[a]}" for a in CALLERS}


def diff(prev: dict[str, Any] | None, cur: dict[str, Any] | None,
         door_prev: str | None, door_cur: str | None) -> list[str]:
    """The events between two snapshots of one account (first sighting: none)."""
    ev = []
    if door_prev is not None and door_cur is not None and door_cur != door_prev:
        ev.append("ORDER")
    if cur is None or prev is None:
        return ev
    if prev.get("positions") is not None and cur.get("positions") != prev.get("positions"):
        ev.append("FILL")
    if cur.get("room_bucket") != prev.get("room_bucket"):
        ev.append("DAILY_ROOM")
    if prev.get("phase") is not None and cur.get("phase") != prev.get("phase"):
        ev.append("PHASE")
    return ev


def _start_task(task: str) -> str:
    if sys.platform != "win32":
        return "not_windows"
    try:
        r = subprocess.run(["schtasks", "/Run", "/TN", task], capture_output=True, text=True,
                           timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"failed: {type(exc).__name__}"
    return "started" if r.returncode == 0 else f"failed: {(r.stderr or r.stdout).strip()[:80]}"


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def run(now: datetime | None = None,
        start_task: Callable[[str], str] = _start_task) -> dict[str, Any]:
    """One pass: snapshot, diff, dispatch. Never raises (the venue reader calls it)."""
    now = now or datetime.now(tz=UTC)
    try:
        raw = _read(STATE)
        state = raw if isinstance(raw, dict) else {}
        snaps = {"ftmo": ftmo_snapshot(_read(FTMO_STATE)), "e8": e8_snapshot(_read(E8_EXEC)),
                 "fusion": None}
        roster = roster_snapshot(_read(SURVIVORS))
        doors = door_counts()
        prev_snaps = state.get("snapshots") or {}
        prev_doors = state.get("doors") or {}
        events: dict[str, list[str]] = {}
        for acct in CALLERS:
            events[acct] = diff(prev_snaps.get(acct), snaps.get(acct),
                                prev_doors.get(acct), (doors or {}).get(acct))
        prev_roster = state.get("roster") or {}
        new_certs = []
        if roster is not None and prev_roster.get("keys") is not None:
            new_certs = sorted(set(roster["keys"]) - set(prev_roster["keys"]))
        pending: dict[str, list[str]] = state.get("pending") or {}
        last_start: dict[str, str] = state.get("last_start") or {}
        report_subs: dict[str, Any] = {}
        for name, (task, acct, debounce) in SUBSCRIBERS.items():
            got = list(events.get(acct, [])) if acct else sorted({e for v in events.values()
                                                                    for e in v})
            if new_certs:
                got.append("NEW_CERTIFIED")
            queue = sorted(set(pending.get(name, [])) | set(got))
            row: dict[str, Any] = {"task": task, "account": acct, "events": got,
                                   "pending": queue, "measured": acct is None
                                   or snaps.get(acct) is not None or doors is not None}
            if queue:
                since = None
                if last_start.get(name):
                    since = (now - datetime.fromisoformat(last_start[name])).total_seconds()
                if since is not None and since < debounce:
                    row["action"] = f"held {debounce - since:.0f}s (debounce)"
                else:
                    row["action"] = start_task(task)
                    if row["action"] in ("started", "not_windows"):
                        last_start[name] = now.isoformat()
                        queue = []
                        LEDGER.parent.mkdir(parents=True, exist_ok=True)
                        with LEDGER.open("a", encoding="utf-8") as fh:
                            fh.write(json.dumps({"at": now.isoformat(timespec="seconds"),
                                                 "subscriber": name, "task": task,
                                                 "events": row["pending"],
                                                 "result": row["action"]}) + "\n")
            pending[name] = queue
            report_subs[name] = row
        _atomic(STATE, {"at": now.isoformat(), "snapshots": {k: v for k, v in snaps.items()
                                                             if v is not None}
                        | {k: v for k, v in prev_snaps.items() if snaps.get(k) is None},
                        "doors": doors if doors is not None else prev_doors,
                        "roster": {"keys": roster["keys"]} if roster else prev_roster,
                        "pending": pending, "last_start": last_start})
        doc = {"generated_at": now.isoformat(timespec="seconds"), "status": "OK",
               "new_certified": len(new_certs), "subscribers": report_subs,
               "sources": {"ftmo": snaps["ftmo"] is not None, "e8": snaps["e8"] is not None,
                           "roster": roster is not None, "door": doors is not None}}
        _atomic(OUT, doc)
        return doc
    except Exception as exc:
        return {"status": "ERROR", "why": f"{type(exc).__name__}: {exc}"[:300]}
