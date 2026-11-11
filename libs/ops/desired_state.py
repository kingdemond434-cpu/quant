"""Box-local switches flipped by the adopter, not by a person typing "yes" (adopter v4, v6).

THE GAP (2026-10-28 06:43Z, zuck: "remove even telling or typing ... I want it to auto do it").
The adopter lands audited CODE on its own, but the desk's box-local switches -- the gitignored
files a lane reads each pass, such as desks/mt5/data/GOLD_OCO_MODE.json (which lanes trade gold,
and which of them in full OCO) -- were still flipped by a box session that asked zuck to type a
word first. The switch is as much a live change as the code, so it takes the same road:

    1. The wanted content is COMMITTED under desks/mt5/data/box_state_desired/<NAME>. That path is
       governed state, so `adopt_guard.pre` will not adopt it without an auditor CLEAR row for
       its blob, and it is checked again here against the CLEAR rows HEAD carries.
    2. Only names in DESIRED are ever written, each to desks/mt5/data/<NAME>, and only after its
       own check passes. A name nobody wrote a check for is reported and never applied.
    3. EACH COMMITTED VERSION IS APPLIED ONCE (v4 audit MF4): the journal keys it by blob, so a
       person's later box-local edit (dropping a lane during an incident) is never written over
       by the same committed version an hour later. A new committed version is a new decision.
       The journal row goes down BEFORE the switch is written; a journal that cannot be written
       stops the apply.
    4. Never near a gold window: the same broker-clock blackout and start margin as an adoption.
    5. NO NEW-RISK HOLD (v4 audit MF3, Rule 1): a gold switch matters only inside a gold window,
       and the apply runs hours away from one, so holding every lane bought nothing.
    6. PROVISIONAL UNTIL A GOLD WINDOW HAS RUN ON IT (v4 audit MF2). Outside the windows no lane
       run exercises the new mode, so "the lanes ran fine for seven minutes" proved nothing. The
       switch stays provisional, with its backup armed, and `verify` -- every adopter run, the
       gold windows included, since it only ever puts the old switch back -- restores it when
         - a lane task the switch touches, that was healthy before it, FINISHED a run since with
           a nonzero result (a running task is not a failure: v4 audit MF1), or
         - a lane the switch ADDED stops publishing its gold state: gold_oco then freezes gold on
           EVERY lane, so putting the old switch back is what un-freezes E8 and Fusion.
       It is confirmed only after the first gold window that followed it has ended with every
       touched lane's latest finished run, started after that window opened, exiting 0.
       Lanes already failing before the switch are reported and never judged (v4 audit MF3).

GOLD_OCO_MODE.json's check (gold_oco.py, "SWITCHING THE MODE"): lanes are known lanes, modes name
listed lanes and say "oco" or "fallback", and every lane the change ADDS must already publish a
readable gold state carrying the current protocol (within a day). gold_oco places NO gold on any
lane while a listed lane is silent, so declaring a lane that is not running would freeze gold
everywhere -- that is refused here rather than discovered at the next window. The lanes it
touches are the task that runs each lane in the old or new file (policy `gold_lane_tasks`:
E8-Gold, MT5-Gateway for Fusion, MT5-FTMO-Follower).

Never sends anything, never edits a committed file; the only writes are the box-local switch, its
backup under data/box_state_backups/ (gitignored), the provisional record and the journal.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.ops import adopt_guard as ag

DESIRED_DIR = "desks/mt5/data/box_state_desired"
LIVE_DIR = "desks/mt5/data"
BACKUP_DIR = "desks/mt5/data/box_state_backups"
PROVISIONAL_REL = "desks/mt5/data/box_state_backups/PROVISIONAL.json"
JOURNAL_REL = "desks/mt5/reports/BOX_STATE_APPLIED.jsonl"
#: A lane the change adds must be publishing NOW: gold_oco freezes gold on every lane once a
#: declared lane's state is older than its own 600 s bound (adopter v6 audit).
ADDED_LANE_MAX_AGE_S = 600.0
#: gold_oco's own staleness bound: a declared lane older than this freezes gold on every lane.
LIVE_LANE_MAX_AGE_S = 600.0
#: Journal results after which a committed version is never applied again.
FINAL = frozenset(
    {"APPLYING", "APPLIED", "RESTORED", "CONFIRMED", "KEPT_UNCONFIRMED", "SUPERSEDED"}
)
#: A provisional switch still without in-window evidence after this many TRADING gold windows
#: (one trading day: asia, london_am, afternoon) pages once and is kept, its restore disarmed.
#: Counted in windows, not hours, so a weekend never runs it out (v10 audit MF1).
UNCONFIRMED_WINDOWS = 3

LaneReader = Callable[..., "tuple[dict[str, Any] | None, str]"]
TaskInfo = Callable[[str], "dict[str, Any] | None"]


#: The desk this code ships with: switches are checked by the executors' own code, whichever repo
#: root the journal and backups live under.
_CODE_ROOT = Path(__file__).resolve().parents[2]


def _gold_oco(root: Path) -> Any:
    for p in (str(_CODE_ROOT), str(_CODE_ROOT / "desks" / "mt5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mt5desk import gold_oco

    return gold_oco


def _passed_in_window(
    root: Path, task: str, start: datetime, now: datetime, release: object
) -> bool:
    """A task that is always mid-run when verify looks (MT5-Gateway starts a pass every minute,
    so its LastTaskResult reads 267009) still proves a finished pass: the load stamp each pass
    writes after it saved its state (run_gateway_loop, `runner`). Read inside the window only."""
    try:
        doc = json.loads((root / ag.GATEWAY_LOADED_REL).read_text(encoding="utf-8"))
        passed = datetime.fromisoformat(str(doc.get("last_pass_at")))
    except (OSError, ValueError, TypeError):
        return False
    if passed.tzinfo is None:
        passed = passed.replace(tzinfo=UTC)
    # ...by a pass of the release the switch was applied under (v10 audit should-fix)
    return (
        doc.get("runner") == task
        and bool(release)
        and doc.get("release_sha") == release
        and start <= passed <= now
    )


def _sealed(root: Path) -> str | None:
    try:
        return ag.sealed_code_sha(root, "HEAD") or None
    except ag.GuardError:
        return None


def _protocol(root: Path) -> int:
    return int(_gold_oco(root).PROTOCOL)


def _default_lane_reader(root: Path) -> LaneReader:
    go = _gold_oco(root)
    return lambda lane, max_age_s=ADDED_LANE_MAX_AGE_S: go.read_lane(lane, max_age_s=max_age_s)


def check_gold_oco(
    root: Path, new: dict[str, Any], old: dict[str, Any] | None, read_lane: LaneReader
) -> str | None:
    """None when `new` is a mode file gold_oco reads as written and every lane it adds runs."""
    known = ("e8", "fusion", "ftmo")
    lanes = new.get("lanes")
    if not isinstance(lanes, list) or not lanes or any(x not in known for x in lanes):
        return f"lanes must be a non-empty list of {known}: {lanes!r}"
    if "e8" not in lanes:
        return "lanes must hold e8, the leader"
    modes = new.get("modes", {})
    if not isinstance(modes, dict):
        return "modes must be an object"
    for lane, mode in modes.items():
        if lane not in lanes:
            return f"modes names {lane}, which is not in lanes"
        if mode not in ("oco", "fallback"):
            return f"mode for {lane} must be oco or fallback, not {mode!r}"
    unknown = set(new) - {"lanes", "modes", "note"}
    if unknown:
        return f"unknown keys {sorted(unknown)}"
    before = (
        old.get("lanes") if isinstance(old, dict) and isinstance(old.get("lanes"), list) else []
    )
    if not before:
        before = ["e8", "fusion"]  # gold_oco.DEFAULT_LANES: what an absent file means
    proto = _protocol(root)
    for lane in lanes:
        if lane in before:
            continue
        doc, why = read_lane(lane)
        if doc is None:
            return f"adding {lane}: it does not publish a gold state ({why}); gold would freeze"
        if doc.get("protocol") != proto:
            return f"adding {lane}: its state carries protocol {doc.get('protocol')}, not {proto}"
    return None


def _gold_lanes(doc: dict[str, Any] | None) -> list[str]:
    lanes = doc.get("lanes") if isinstance(doc, dict) else None
    return [str(x) for x in lanes] if isinstance(lanes, list) and lanes else ["e8", "fusion"]


def touches_gold_oco(
    pol: dict[str, Any], new: dict[str, Any], old: dict[str, Any] | None
) -> tuple[list[str], list[str]]:
    """(lane tasks the switch touches, gold lanes it adds)."""
    tasks = pol["gold_lane_tasks"]
    lanes = sorted(set(_gold_lanes(new)) | set(_gold_lanes(old)))
    added = [x for x in _gold_lanes(new) if x not in _gold_lanes(old)]
    return sorted({n for x in lanes for n in tasks.get(x, [])}), added


def check_cancel_pending(
    root: Path, new: dict[str, Any], old: dict[str, Any] | None, read_lane: LaneReader
) -> str | None:
    """None when every executor reads the request file as written (mt5desk.cancel_pending)."""
    _gold_oco(root)  # puts the desk on the path
    from mt5desk import cancel_pending

    why = cancel_pending.problem(new)
    return None if why is None else str(why)


def touches_cancel_pending(
    pol: dict[str, Any], new: dict[str, Any], old: dict[str, Any] | None
) -> tuple[list[str], list[str]]:
    """The lane tasks a request names; it adds no gold lane."""
    tasks = pol["gold_lane_tasks"]
    lanes = {str(r.get("lane")) for r in (new.get("requests") or []) if isinstance(r, dict)}
    return sorted({n for x in lanes for n in tasks.get(x, [])}), []


#: The only switches this module writes: (check, what it touches).
DESIRED: dict[str, tuple[Callable[..., str | None], Callable[..., tuple[list[str], list[str]]]]] = {
    "GOLD_OCO_MODE.json": (check_gold_oco, touches_gold_oco),
    # cancel requests only withdraw resting orders, so they are not held for the gold windows
    "CANCEL_PENDING.json": (check_cancel_pending, touches_cancel_pending),
}
#: Switches that only ever reduce exposure: applied whenever the run reaches them, windows too.
ANY_TIME = frozenset({"CANCEL_PENDING.json"})


def _load(raw: bytes | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    doc = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError("not a JSON object")
    return doc


def _journal_rows(root: Path) -> list[dict[str, Any]]:
    try:
        lines = (root / JOURNAL_REL).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _journal(root: Path, row: dict[str, Any]) -> None:
    """RAISES OSError: the journal is what keeps a version from being applied twice."""
    f = root / JOURNAL_REL
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now(UTC).isoformat(), **row}, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _results(root: Path, blob: str) -> set[str]:
    return {str(r.get("result")) for r in _journal_rows(root) if r.get("blob") == blob}


def _write_atomic(f: Path, data: bytes) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".adopt_tmp")
    tmp.write_bytes(data)
    os.replace(tmp, f)


def load_provisional(root: Path) -> list[dict[str, Any]]:
    """Fail closed: a garbled record could be the one armed restore."""
    f = root / PROVISIONAL_REL
    if not f.exists():
        return []
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ag.GuardError(f"{PROVISIONAL_REL} unreadable ({type(exc).__name__})") from exc
    if not isinstance(doc, list):
        raise ag.GuardError(f"{PROVISIONAL_REL} is not a list")
    return doc


def _save_provisional(root: Path, rows: list[dict[str, Any]]) -> None:
    _write_atomic(root / PROVISIONAL_REL, json.dumps(rows, indent=1, sort_keys=True).encode())


def next_window(
    after: datetime, pol: dict[str, Any], offset_h: Callable[[datetime], int]
) -> tuple[datetime, datetime]:
    """(start, end) in UTC of the first gold window (policy blackouts, broker clock) that STARTS
    after `after` on a TRADING day. The broker's day runs Monday to Friday (New York + 7 h: the
    week opens Sunday 17:00 New York = Monday 00:00 broker), so a broker Saturday or Sunday
    window is a closed market: every lane exits clean there and proves nothing (v10 audit MF1).
    Exchange holidays are not known here; a window on one rolls on like any other."""
    best: tuple[datetime, datetime] | None = None
    broker_day = (after.astimezone(UTC) + timedelta(hours=offset_h(after))).date()
    for d in range(5):
        day = broker_day + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        # the broker's offset is read for EACH day (v11 audit: across a DST change one offset
        # for the whole look-ahead put Monday's window an hour early)
        noon = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
        off = offset_h(noon)
        for w in pol.get("blackouts_broker") or []:
            s_min, e_min = ag._minute(w["from"]), ag._minute(w["to"])
            start = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(
                minutes=s_min, hours=-off
            )
            end = start + timedelta(minutes=(e_min - s_min) % 1440 or 1440)
            if start > after and (best is None or start < best[0]):
                best = (start, end)
    if best is None:
        raise ag.GuardError("no gold window in the policy")
    return best


def plan(root: Path, commit: str = "HEAD") -> tuple[list[dict[str, Any]], list[str]]:
    """(changes to make, reasons others are not made). A change is a committed desired version
    that differs from the box's live copy and was never applied before."""
    commit = ag._rev(root, commit)
    tree = ag._tree(root, commit)
    names = sorted(p[len(DESIRED_DIR) + 1 :] for p in tree if p.startswith(DESIRED_DIR + "/"))
    todo: list[dict[str, Any]] = []
    skipped: list[str] = []
    clears: list[ag.Clear] | None = None
    for name in names:
        rel = f"{DESIRED_DIR}/{name}"
        if name not in DESIRED:
            skipped.append(f"{name}: no check is written for it; never applied")
            continue
        live = root / LIVE_DIR / name
        try:
            want = _load(ag._show(root, commit, rel))
            have = _load(live.read_bytes()) if live.exists() else None
        except (OSError, ValueError) as exc:
            skipped.append(f"{name}: unreadable ({type(exc).__name__}: {exc})")
            continue
        if want == have:
            continue
        results = _results(root, tree[rel])
        # a version whose attempt never finished (a write that failed, or a run killed between
        # the APPLYING row and the write) is tried again: the live copy still differs from it
        if results & (FINAL - {"APPLYING"}):
            skipped.append(
                f"{name}: this committed version was applied once already; the box's "
                "own later edit stands"
            )
            continue
        if clears is None:
            clears = ag.committed_clears(root, commit)
        if ag.uncovered(root, [rel], commit, clears):
            skipped.append(f"{name}: its committed content has no auditor CLEAR")
            continue
        todo.append({"name": name, "rel": rel, "blob": tree[rel], "want": want, "have": have})
    return todo, skipped


def apply(
    root: Path,
    *,
    commit: str = "HEAD",
    now: datetime | None = None,
    offset_h: Callable[[datetime], int] = ag.broker_offset_h,
    read_lane: LaneReader | None = None,
    task_info: TaskInfo = ag._task_info,
    any_time_only: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Make the box's switches what HEAD says, once per committed version, provisionally.
    0 applied, refused or nothing to do; 10 waiting (a gold window is near, the adopter's hold
    stands, or the same switch is still provisional); 2 error."""
    pol = ag.load_policy(root)
    when = now or datetime.now(UTC)
    todo, skipped = plan(root, commit)
    if not todo:
        return ag.GO, {"decision": "NOTHING_TO_APPLY", "skipped": skipped}
    if any_time_only:
        todo = [t for t in todo if t["name"] in ANY_TIME]
        if not todo:
            return ag.GO, {"decision": "NOTHING_TO_APPLY", "skipped": skipped}
    why = ag.blackout(when, pol, margin_min=int(pol["start_margin_min"]), offset_h=offset_h)
    if why:
        # withdrawing resting orders is never held for a window; everything else waits
        if not any(t["name"] in ANY_TIME for t in todo):
            return ag.HOLD, {
                "decision": "HOLD_BLACKOUT",
                "reason": why,
                "skipped": skipped,
                "waiting": [t["name"] for t in todo],
            }
        skipped += [
            f"{t['name']}: waits for the window to pass" for t in todo if t["name"] not in ANY_TIME
        ]
        todo = [t for t in todo if t["name"] in ANY_TIME]
    if ag.own_hold_since(root) is not None:
        if not any(t["name"] in ANY_TIME for t in todo):
            return ag.HOLD, {
                "decision": "HOLD_RELEASE_HELD",
                "skipped": skipped,
                "reason": "the adopter's own new-risk hold stands (an unhealthy "
                "release); switches wait for a healthy one",
            }
        skipped += [
            f"{t['name']}: waits for a healthy release" for t in todo if t["name"] not in ANY_TIME
        ]
        todo = [t for t in todo if t["name"] in ANY_TIME]
    # a request that only withdraws orders never reads the provisional record, so a garbled
    # record (which fails closed for the switches it guards) cannot block a cancel (v7 audit)
    if any(t["name"] not in ANY_TIME for t in todo):
        pending = {str(r.get("name")): r for r in load_provisional(root)}
    else:
        pending = {}
    reader = read_lane or _default_lane_reader(root)
    applied: list[str] = []
    for t in todo:
        # A NEWER CLEARED VERSION SUPERSEDES A PROVISIONAL ONE (adopter v8 audit MF5): it does
        # not wait behind it. Its restore goes back to the state before the first of them.
        older = pending.get(t["name"]) if t["name"] not in ANY_TIME else None
        check, touches = DESIRED[t["name"]]
        problem = check(root, t["want"], t["have"], reader)
        if problem:
            skipped.append(f"{t['name']}: {problem}")
            if "REFUSED" not in _results(root, t["blob"]):  # one page per refused version
                ag.page(root, f"box-state change {t['name']} refused by its check: {problem}")
            _journal(
                root, {"name": t["name"], "blob": t["blob"], "result": "REFUSED", "why": problem}
            )
            continue
        # what the switch touches is measured against the state its restore goes back to: for
        # a superseding version that is the state before BOTH (v10 audit MF2), so a lane the
        # older version added is still an added lane, busy-checked before any restore
        base_have = t["have"]
        if older is not None:
            try:
                base_have = (
                    _load(Path(older["backup"]).read_bytes()) if older.get("backup") else None
                )
            except (OSError, ValueError) as exc:
                skipped.append(f"{t['name']}: the older version's backup is unreadable ({exc})")
                continue
        tasks, added = touches(pol, t["want"], base_have)
        # lanes already failing are reported, never judged against the switch
        before = {n: ag.task_verdict(task_info(n), datetime.fromtimestamp(0, UTC)) for n in tasks}
        live = root / LIVE_DIR / t["name"]
        stamp = when.strftime("%Y%m%dT%H%M%SZ")
        backup = root / BACKUP_DIR / f"{t['name']}.{stamp}" if live.exists() else None
        if older is not None:
            backup = Path(older["backup"]) if older.get("backup") else None
        start, end = next_window(when, pol, offset_h)
        entry = {
            "name": t["name"],
            "blob": t["blob"],
            "applied_at": when.isoformat(),
            "backup": str(backup) if backup else None,
            "tasks": tasks,
            "judged": [n for n, v in before.items() if v in ("OK", "RUNNING")],
            "lanes_before": before,
            "added_gold_lanes": added,
            "release": _sealed(root),
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
        }
        # IN THIS ORDER: the journal row that makes the version applied-once, the backup, the
        # armed restore, and only then the switch. Any of the first three failing writes nothing.
        _journal(
            root,
            {
                "name": t["name"],
                "blob": t["blob"],
                "result": "APPLYING",
                "backup": entry["backup"],
                "lanes_before": before,
            },
        )
        if backup is not None and older is None:
            _write_atomic(backup, live.read_bytes())
        # a switch that only withdraws resting orders has nothing to watch a window for
        provisional = t["name"] not in ANY_TIME
        # a run killed after it armed this version's restore left a row, and a superseded
        # version leaves one: this row replaces both
        rows = (
            [
                x
                for x in load_provisional(root)
                if x.get("blob") != t["blob"] and x.get("name") != t["name"]
            ]
            if provisional
            else []
        )
        if provisional:
            _save_provisional(root, [*rows, entry])
        try:
            _write_atomic(live, json.dumps(t["want"], indent=1, sort_keys=True).encode())
        except OSError as exc:
            if provisional:
                _save_provisional(root, rows)
            _journal(
                root,
                {"name": t["name"], "blob": t["blob"], "result": "WRITE_FAILED", "why": str(exc)},
            )
            skipped.append(f"{t['name']}: the switch could not be written ({exc})")
            continue
        _journal(root, {"name": t["name"], "blob": t["blob"], "result": "APPLIED"})
        if older is not None and older.get("blob") != t["blob"]:
            _journal(
                root,
                {"name": t["name"], "blob": older["blob"], "result": "SUPERSEDED", "by": t["blob"]},
            )
        applied.append(t["name"])
    decision = "APPLIED_PROVISIONAL" if applied else "REFUSED"
    return ag.GO, {"decision": decision, "applied": applied, "skipped": skipped}


def verify(
    root: Path,
    *,
    now: datetime | None = None,
    read_lane: LaneReader | None = None,
    task_info: TaskInfo = ag._task_info,
    offset_h: Callable[[datetime], int] = ag.broker_offset_h,
) -> tuple[int, dict[str, Any]]:
    """Restore a provisional switch the lanes failed on, confirm one a gold window ran on.
    0 nothing failed; 11 something was restored; 12 a restore failed (paged)."""
    when = now or datetime.now(UTC)
    rows = load_provisional(root)
    if not rows:
        return ag.GO, {"decision": "NOTHING_PROVISIONAL"}
    reader = read_lane or _default_lane_reader(root)
    keep: list[dict[str, Any]] = []
    restored: list[str] = []
    confirmed: list[str] = []
    code = ag.GO
    for r in rows:
        since = datetime.fromisoformat(r["applied_at"])
        _, seen = ag.lane_problems(root, since, task_info, names=r["tasks"])
        fails = [
            f"lane task {n} {v} since the switch"
            for n, v in seen.items()
            if n in r["judged"] and v.startswith("FAILED")
        ]
        for lane in r["added_gold_lanes"]:
            doc, why = reader(lane, max_age_s=LIVE_LANE_MAX_AGE_S)
            if doc is None:
                fails.append(
                    f"added gold lane {lane} went silent ({why}): gold is frozen on every lane"
                )
        # NEVER UNDECLARE A LANE THAT HOLDS GOLD (adopter v6 audit MF2): gold_oco locks only the
        # declared lanes, so dropping one with a position or resting entry would let E8 and Fusion
        # trade blind to it. The switch then stays (the fail-closed side) and a person is paged.
        busy = []
        for lane in r["added_gold_lanes"] if fails else []:
            last, lwhy = reader(lane, max_age_s=1e12)
            if last is None or last.get("positions") or last.get("orders"):
                busy.append(f"{lane} ({'holds gold' if last is not None else lwhy})")
        if fails and busy:
            if not r.get("paged_busy"):
                ag.page(
                    root,
                    f"box-state change {r['name']} failed ({fails[0]}) but is NOT put "
                    f"back: lane {', '.join(busy)}; it stays as it is until a person acts",
                )
                r["paged_busy"] = True
            keep.append(r)
            code = max(code, ag.UNHEALTHY)
            continue
        if fails:
            try:
                live = root / LIVE_DIR / r["name"]
                if r.get("backup"):
                    _write_atomic(live, Path(r["backup"]).read_bytes())
                else:
                    live.unlink(missing_ok=True)
                _journal(
                    root,
                    {"name": r["name"], "blob": r["blob"], "result": "RESTORED", "why": fails[0]},
                )
            except OSError as exc:
                ag.page(root, f"box-state RESTORE FAILED for {r['name']} after '{fails[0]}': {exc}")
                keep.append(r)
                code = ag.ROLLBACK_FAILED
                continue
            ag.page(root, f"box-state change {r['name']} put back by itself: {fails[0]}")
            restored.append(r["name"])
            code = max(code, ag.UNHEALTHY)
            continue
        # CONFIRMED ONLY ON EVIDENCE (adopter v6 audit MF1; UNMEASURED is never clean): every
        # touched lane must be seen with a successful run inside a gold window, by a verify that
        # ran inside it. A window that passes without that rolls to the next one; a day without
        # it pages once and the switch stays provisional, its restore armed.
        start = datetime.fromisoformat(r["window_start"])
        ended = datetime.fromisoformat(r["window_end"])
        seen_ok = set(r.get("seen_ok") or [])
        if start <= when < ended:
            for n in r["tasks"]:
                v = ag.task_verdict(task_info(n), start)
                if v == "OK" or (
                    v == "RUNNING" and _passed_in_window(root, n, start, when, r.get("release"))
                ):
                    seen_ok.add(n)
            r["seen_ok"] = sorted(seen_ok)
        done = bool(r["tasks"]) and when >= ended and set(r["tasks"]) <= seen_ok
        if when >= ended and not done:
            nxt = next_window(when, ag.load_policy(root), offset_h)
            r["window_start"], r["window_end"] = nxt[0].isoformat(), nxt[1].isoformat()
            r["windows_unconfirmed"] = int(r.get("windows_unconfirmed") or 0) + 1
        if (
            not done
            and int(r.get("windows_unconfirmed") or 0) >= UNCONFIRMED_WINDOWS
            and not r.get("paged_unconfirmed")
        ):
            missing = sorted(set(r["tasks"]) - seen_ok) or ["no lane task is measured"]
            ag.page(
                root,
                f"box-state change {r['name']} still unconfirmed after a trading day's gold "
                f"windows; no in-window success seen for {', '.join(missing)}; it is kept and its "
                "automatic restore is now off",
            )
            r["paged_unconfirmed"] = True
            # ...and its restore is DISARMED (adopter v8 audit MF5): a switch that ran a day
            # without failing is not rolled back by a lane's unrelated failure days later.
            try:
                _journal(
                    root,
                    {
                        "name": r["name"],
                        "blob": r["blob"],
                        "result": "KEPT_UNCONFIRMED",
                        "missing": missing,
                    },
                )
            except OSError:
                keep.append(r)
                continue
            continue
        if done:
            try:
                _journal(root, {"name": r["name"], "blob": r["blob"], "result": "CONFIRMED"})
            except OSError:
                keep.append(r)
                continue
            confirmed.append(r["name"])
        else:
            keep.append(r)
    _save_provisional(root, keep)
    return code, {
        "decision": "VERIFIED",
        "restored": restored,
        "confirmed": confirmed,
        "provisional": [r["name"] for r in keep],
    }
