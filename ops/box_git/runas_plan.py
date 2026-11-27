"""BOOT r24: the run-as migrator's decisions, pure and tested. guard\\runas\\migrate.ps1 (SYSTEM,
pinned, task QuantGuard-RunAs every 5 min) does only what this module returns.

THE BOUNDS (Audit Q1, 2026-11-27 13:30Z), each pinned by a test:
  1. It changes ONLY the principal of tasks whose action runs the live tree (LIVE_TREE), never an
     action, argument, trigger or any other task.
  2. Its only direction is TO quantrun. Before a move it snapshots each task's exact principal;
     rollback restores that snapshot and nothing else.
  3. After a move it is idle: later cycles only check (`proof`), never re-register.
  4. The probe (runas_probe.py) has no order path.
  5. It lives in guard\\ and is reviewed at its sha.

STATES (guard\\runas\\state.json): PROBE -> (A pass) WAIT_WINDOW -> MOVED -> WATCH -> DONE, or
BLOCKED (both probes failed: nothing moves, the seat CLEAR stays required), ROLLED_BACK.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

RUN_USER = "quantrun"
LIVE_TREE = re.compile(r"(?i)C:\\opt\\quant|desks\\mt5")
#: May stay elevated: owner-installed movers and pinned guard tasks, which execute no head code.
ALLOWED_ELEVATED = frozenset({"QuantForge-BootMove", "QuantForge-Pin", "QuantGuard-RunAs",
                              "QuantGuard-Risk"})
#: Never moved (it must restart the gateway and reseal as SYSTEM), but NOT allowed elevated either:
#: today it runs Adopt-And-Seal.ps1 and adopt_guard.py from the live tree, which is head code
#: (Audit (b)). So the proof stays "not independent" until a pinned adopter replaces it (r24.1).
NEVER_MOVE = frozenset({"MT5-AdoptRelease"})
ELEVATED = frozenset({"SYSTEM", "NT AUTHORITY\\SYSTEM", "S-1-5-18", "ADMINISTRATOR"})
PROOF_MAX_AGE = timedelta(minutes=15)
#: (r24.1, zuck 13:51Z "I don't want it even once a month") the seat CLEAR switches off by
#: itself after this long of unbroken independent proof, and back on at the first bad one.
FLIP_AFTER = timedelta(days=7)
WATCH_FOR = timedelta(hours=6)
HEARTBEAT_MAX = timedelta(minutes=15)
REJECTS_MAX = 3


def runs_live_tree(task: Mapping[str, Any]) -> bool:
    acts = task.get("actions") or []
    blob = " ".join(f"{a.get('execute', '')} {a.get('arguments', '')} {a.get('workdir', '')}"
                    for a in acts)
    return bool(LIVE_TREE.search(blob))


def _user(task: Mapping[str, Any]) -> str:
    return str((task.get("principal") or {}).get("user") or "").split("\\")[-1].upper() or "?"


def elevated(task: Mapping[str, Any]) -> bool:
    u = _user(task)
    return u in {x.split("\\")[-1] for x in ELEVATED} or \
        str((task.get("principal") or {}).get("runlevel") or "").lower() == "highest"


def to_move(tasks: Iterable[Mapping[str, Any]]) -> list[str]:
    """Bound 1: the tasks whose principal moves. Every task running the live tree that is not
    already quantrun and is not on the allowed list. A task whose actions cannot be read is NOT
    moved (it is reported by proof as unmeasured instead)."""
    return sorted(str(t["name"]) for t in tasks
                  if t.get("actions") is not None and runs_live_tree(t)
                  and _user(t) != RUN_USER.upper()
                  and str(t["name"]) not in ALLOWED_ELEVATED | NEVER_MOVE)


def snapshot(tasks: Iterable[Mapping[str, Any]], names: Sequence[str]) -> dict[str, Any]:
    """Bound 2: each moved task's exact old principal, written BEFORE any move."""
    keep = set(names)
    return {str(t["name"]): dict(t.get("principal") or {}) for t in tasks if t["name"] in keep}


def new_principal() -> dict[str, str]:
    return {"user": RUN_USER, "logon": "S4U", "runlevel": "Limited"}


def in_window(now: datetime) -> bool:
    """The weekend closure: Fri 22:00 UTC to Sun 21:00 UTC (FX and metals closed)."""
    wd, h = now.weekday(), now.hour + now.minute / 60
    return (wd == 4 and h >= 22) or wd == 5 or (wd == 6 and h < 21)


def probe_mode(a1: Mapping[str, Any] | None, a2: Mapping[str, Any] | None) -> str | None:
    """'attach' (terminals stay, python moves), 'portable' (both move) or None (nothing moves)."""
    if a1 and a1.get("ok"):
        return "attach"
    if a2 and a2.get("ok"):
        return "portable"
    return None


def step(state: Mapping[str, Any], now: datetime, *, probes: Mapping[str, Any],
         window: bool | None = None) -> tuple[str, str]:
    """(next state, the action migrate.ps1 takes). Bound 3: from MOVED onward the only actions are
    'check' and 'rollback'; nothing re-registers."""
    s = str(state.get("state") or "PROBE")
    w = in_window(now) if window is None else window
    if s == "PROBE":
        if not probes:
            return "PROBE", "probe"
        mode = probe_mode(probes.get("attach"), probes.get("portable"))
        return ("WAIT_WINDOW", f"wait:{mode}") if mode else ("BLOCKED", "alarm")
    if s == "WAIT_WINDOW":
        return ("MOVED", f"move:{state.get('mode')}") if w else ("WAIT_WINDOW", "wait")
    if s in {"MOVED", "WATCH"}:
        return "WATCH", "check"
    return s, "check"  # DONE, BLOCKED, ROLLED_BACK: checks only


def watch_verdict(moved_at: datetime, now: datetime, *, market_open_since: datetime | None,
                  heartbeat_at: datetime | None, consecutive_rejects: int) -> str:
    """During the first WATCH_FOR of OPEN market after a move: 'rollback' on a stale heartbeat or
    REJECTS_MAX rejects in a row; 'done' once the watch has passed; else 'ok'."""
    if market_open_since is None or now < market_open_since:
        return "ok"
    if now - max(market_open_since, moved_at) > WATCH_FOR:
        return "done"
    if heartbeat_at is None or now - heartbeat_at > HEARTBEAT_MAX:
        return "rollback"
    if consecutive_rejects >= REJECTS_MAX:
        return "rollback"
    return "ok"


def elevated_processes(procs: Iterable[Mapping[str, Any]], live: str = r"C:\opt\quant",
                       allowed_roots: Sequence[str] = (r"C:\ProgramData\QuantBox\guard",)
                       ) -> list[str]:
    """(Audit C5) The process-level half of the proof: running processes owned by SYSTEM or
    Administrator whose command line or working folder is in the live tree. MetaQuotes'
    terminal64 is not repository code; anything run from the pinned guard folder is allowed."""
    out = []
    lv = live.lower()
    for p in procs:
        owner = str(p.get("user") or "").split("\\")[-1].upper()
        if owner not in {"SYSTEM", "ADMINISTRATOR"}:
            continue
        name = str(p.get("name") or "").lower()
        if name == "terminal64.exe":
            continue
        cmd = str(p.get("cmdline") or "").lower()
        cwd = str(p.get("cwd") or "").lower()
        if any(r.lower() in cmd for r in allowed_roots):
            continue
        if lv in cmd or cwd.startswith(lv):
            out.append(f"{p.get('pid')} {name} ({owner})")
    return sorted(out)


def proof(tasks: Iterable[Mapping[str, Any]], write_probes: Mapping[str, bool],
          terminal_checks: Mapping[str, bool], now: datetime,
          processes: Sequence[str] | None = None) -> dict[str, Any]:
    """What guard\\RUN_AS.json says (Audit MF-A/MF-B/Q2). `independent` is true only when no
    live-tree task outside the allowed list is elevated, no task is unreadable, every write probe
    as quantrun was DENIED (value True means denied), and every terminal check holds (no EA, no DLL
    imports)."""
    rows = list(tasks)
    bad = sorted(str(t["name"]) for t in rows if t.get("actions") is not None
                 and runs_live_tree(t) and elevated(t) and t["name"] not in ALLOWED_ELEVATED)
    unread = sorted(str(t["name"]) for t in rows if t.get("actions") is None)
    writable = sorted(k for k, denied in write_probes.items() if not denied)
    term_bad = sorted(k for k, ok in terminal_checks.items() if not ok)
    procs = list(processes) if processes is not None else ["UNMEASURED"]
    ok = (not bad and not unread and not writable and not term_bad and bool(write_probes)
          and not procs)
    return {"at": now.astimezone(UTC).isoformat(timespec="seconds"), "independent": ok,
            "elevated_live_tree": bad, "unreadable_tasks": unread,
            "writable_by_quantrun": writable, "terminal_checks_failed": term_bad,
            "elevated_processes": procs}


def independent_since(history: Iterable[str], now: datetime) -> datetime | None:
    """The start of the CURRENT unbroken run of independent proofs in RUN_AS_HISTORY.jsonl: no
    failing row and no gap longer than PROOF_MAX_AGE inside it, and its last row fresh. None when
    there is no such run (or a row is unreadable)."""
    start: datetime | None = None
    last: datetime | None = None
    for ln in history:
        if not ln.strip():
            continue
        try:
            row = __import__("json").loads(ln)
            at = datetime.fromisoformat(str(row["at"]))
        except (ValueError, KeyError, TypeError):
            return None
        if not row.get("independent") or (last is not None and at - last > PROOF_MAX_AGE):
            start = at if row.get("independent") else None
        elif start is None:
            start = at
        last = at
    if last is None or now - last > PROOF_MAX_AGE:
        return None
    return start


def proof_holds(doc: Mapping[str, Any] | None, now: datetime) -> tuple[bool, str]:
    """The guard's per-cycle reading of RUN_AS.json (MF-B): stale or failing means the seat CLEAR
    is required again."""
    if not doc:
        return False, "RUN_AS.json missing"
    try:
        at = datetime.fromisoformat(str(doc["at"]))
    except (KeyError, ValueError):
        return False, "RUN_AS.json unreadable"
    if now - at > PROOF_MAX_AGE:
        return False, f"RUN_AS.json stale ({int((now - at).total_seconds() // 60)} min)"
    if not doc.get("independent"):
        why = [f"{k}={doc.get(k)}" for k in ("elevated_live_tree", "unreadable_tasks",
                                             "writable_by_quantrun", "terminal_checks_failed",
                                             "elevated_processes")
               if doc.get(k)]
        return False, "not independent: " + "; ".join(why)[:300]
    return True, "independent"


# ------------------------------------------------------------------ the CLI migrate.ps1 calls
def _same(a: str, b: str) -> bool:
    import os
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def kill_old(scripts: Sequence[str], keep_user: str = RUN_USER) -> list[int]:
    """After a moved task is stopped, end the processes its OLD principal left running (a stopped
    cmd.exe can leave its python child): python processes owned by anyone but quantrun one of
    whose arguments, resolved against the process's own working folder, IS one of the task's
    script paths (full paths, never a substring). Never a terminal64, never another script."""
    import os

    import psutil
    killed = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "username"]):
        try:
            if not str(p.info["name"] or "").lower().startswith("python"):
                continue
            owner = str(p.info["username"] or "").split("\\")[-1].lower()
            if owner == keep_user:
                continue
            cwd = p.cwd()
            args = [os.path.join(cwd, x) for x in (p.info["cmdline"] or [])[1:]
                    if x.lower().endswith((".py", ".cmd", ".ps1"))]
            if any(_same(x, s) for x in args for s in scripts if s):
                p.kill()
                killed.append(int(p.info["pid"]))
        except Exception:
            continue
    return killed


def main(argv: list[str] | None = None) -> int:
    """migrate.ps1's one entry: `plan <tasks.json> <state.json> <probes.json>` prints the next
    state and action as JSON; `proof <tasks.json> <writes.json> <terms.json> <out>` writes
    RUN_AS.json; `kill-old <marker>...` ends the old principal's leftovers."""
    import json
    import sys
    from pathlib import Path
    a = list(sys.argv[1:] if argv is None else argv)
    now = datetime.now(UTC)

    def load(p: str) -> Any:
        try:
            return json.loads(Path(p).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None
    if a[:1] == ["plan"]:
        tasks, state, probes = load(a[1]) or [], load(a[2]) or {}, load(a[3]) or {}
        nxt, act = step(state, now, probes=probes)
        print(json.dumps({"state": nxt, "action": act, "move": to_move(tasks),
                          "snapshot": snapshot(tasks, to_move(tasks))}))
        return 0
    if a[:1] == ["proof"]:
        try:
            import psutil
            rows = []
            for p in psutil.process_iter(["pid", "name", "cmdline", "username"]):
                try:
                    cwd = p.cwd()
                except Exception:
                    cwd = ""
                rows.append({"pid": p.info["pid"], "name": p.info["name"],
                             "cmdline": " ".join(p.info["cmdline"] or []),
                             "user": p.info["username"], "cwd": cwd})
            procs: list[str] | None = elevated_processes(rows)
        except Exception:
            procs = None
        doc = proof(load(a[1]) or [], load(a[2]) or {}, load(a[3]) or {}, now, procs)
        tmp = Path(a[4] + ".part")
        tmp.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
        tmp.replace(a[4])
        with Path(a[4]).with_name("RUN_AS_HISTORY.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": doc["at"], "independent": doc["independent"]}) + "\n")
        print(json.dumps(doc))
        return 0 if doc["independent"] else 1
    if a[:1] == ["watch"]:
        # watch <moved_at iso> <gateway_state.json>: heartbeat = the file's mtime; the market
        # opens Sunday 22:00 UTC after the move. Rejects are not read in r24 (heartbeat only).
        moved = datetime.fromisoformat(a[1]).replace(tzinfo=UTC)
        try:
            hb: datetime | None = datetime.fromtimestamp(Path(a[2]).stat().st_mtime, UTC)
        except OSError:
            hb = None
        days = (6 - moved.weekday()) % 7
        opened = (moved + timedelta(days=days)).replace(hour=22, minute=0, second=0,
                                                         microsecond=0)
        if opened < moved:
            opened += timedelta(days=7)
        print(watch_verdict(moved, now, market_open_since=opened, heartbeat_at=hb,
                            consecutive_rejects=0))
        return 0
    if a[:1] == ["kill-old"]:
        print(json.dumps({"killed": kill_old(a[1:])}))
        return 0
    print("usage: plan|proof|kill-old", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
