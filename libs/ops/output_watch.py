"""THE OUTPUT WATCH: every producer, lab, factory and leg on the box must keep producing, or the
box restarts what is safe and pages -- with no Claude in the path (zuck 2026-11-25 21:41Z).

WHY. The math lab produced nothing from 11-24 19:49Z: its three legs hit their 720 s caps on
every pass and moved 0 artifacts, the task itself read "Running" (0x800710E0 is an IgnoreNew
skip), process_health called it UNCONTRACTED, and nothing paged for three days. A task's state and
exit code say nothing about OUTPUT; this judges output.

WHAT IT READS (read only):
  * desks/mt5/data/compute_ledger.jsonl (the last LEDGER_TAIL bytes): one row per finished run
    {at, run, kind, outcome}. For every run name seen in the last 7 days: when it last finished
    at all, and when it last finished OK.
  * desks/mt5/reports/process_health.json: every scheduled task's verdict and state.

WHAT IT FLAGS:
    FAILING_24H   ran inside its allowed gap, but no OK finish in it (timeouts, crashes: the
                  math lab). The allowed gap is max(24h, twice the run's own median gap).
    SILENT_24H    ran at least twice in the last 7 days, nothing at all inside its allowed gap
    TASK_<V>      a task process_health reads NOT_SCHEDULED, FAILING, STALE or NO_ARTIFACT
    UNWATCHED     a task with no artifact contract (counted, named; a gap to close, not a pass)

WHAT IT DOES: starts (schtasks /Run, never End) a non-money task that reads STALE or FAILING and
is not Running, at most once per 2h each; pages through the principal page when the set of
flagged names changes and every 6h while any stays flagged. Writes
desks/mt5/reports/OUTPUT_WATCH.json. The money path is paged, never touched.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

SCHEMA = "output_watch/1"
LEDGER_REL = "desks/mt5/data/compute_ledger.jsonl"
HEALTH_REL = "desks/mt5/reports/process_health.json"
REPORT_REL = "desks/mt5/reports/OUTPUT_WATCH.json"
STATE_REL = "desks/mt5/data/OUTPUT_WATCH_STATE.json"
LEDGER_TAIL = 32 * 1024 * 1024
SEEN_WINDOW = timedelta(days=7)
SILENCE = timedelta(hours=24)
RESTART_EVERY = timedelta(hours=2)
REPAGE_EVERY = timedelta(hours=6)
OK = frozenset({"ok", "success", "done", "completed", "pass", "passed"})
BAD_TASK = ("NOT_SCHEDULED", "FAILING", "STALE", "NO_ARTIFACT")
RESTARTABLE = ("STALE", "FAILING")
MONEY = re.compile(r"(?i)gateway|allocator|terminal|shadow|promot|ftmo|e8|fusion|sleeve|fill|"
                   r"exec|adopt|account|deadman")


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def ledger_rows(path: Path, tail: int = LEDGER_TAIL) -> list[dict[str, Any]]:
    try:
        with path.open("rb") as h:
            size = h.seek(0, 2)
            h.seek(max(0, size - tail))
            text = h.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for ln in text.splitlines()[1 if tail and len(text) >= tail else 0:]:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def runs(rows: Iterable[Mapping[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Per run name seen in the last 7 days: last finish, last OK finish, the flag. Pure.

    A run's allowed gap is max(24h, twice its own median gap), so a daily or twice-daily leg is
    judged on its own clock; a run seen only once is never called silent (no clock to judge)."""
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        t = _ts(r.get("at") or r.get("finished_at"))
        name = str(r.get("run") or "")
        if t is None or not name or t < now - SEEN_WINDOW or t > now + timedelta(hours=1):
            continue
        e = seen.setdefault(name, {"run": name, "kind": r.get("kind"), "times": [],
                                   "last_ok": None, "last_outcome": None, "last": None})
        e["times"].append(t)
        if e["last"] is None or t > e["last"]:
            e["last"], e["last_outcome"] = t, str(r.get("outcome"))
        if str(r.get("outcome") or "").lower() in OK and (e["last_ok"] is None
                                                          or t > e["last_ok"]):
            e["last_ok"] = t
    out = []
    for e in seen.values():
        ts = sorted(set(e.pop("times")))
        gaps = sorted(b - a for a, b in pairwise(ts))
        cadence = gaps[len(gaps) // 2] if gaps else None
        allowed = max(SILENCE, 2 * cadence) if cadence else SILENCE
        flag = None
        if cadence is not None and now - e["last"] > allowed:
            flag = "SILENT_24H"
        elif now - e["last"] <= allowed and (e["last_ok"] is None
                                             or now - e["last_ok"] > allowed):
            flag = "FAILING_24H"
        out.append({**e, "last": e["last"].isoformat(), "runs_7d": len(ts),
                    "cadence_h": round(cadence.total_seconds() / 3600, 2) if cadence else None,
                    "last_ok": e["last_ok"].isoformat() if e["last_ok"] else None, "flag": flag})
    return sorted(out, key=lambda e: (e["flag"] is None, e["run"]))


def tasks(health: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """(flagged tasks, unwatched task names) from process_health. Pure."""
    bad, unwatched = [], []
    for p in health.get("processes") or []:
        if not isinstance(p, dict):
            continue
        n, v = str(p.get("name") or ""), str(p.get("verdict") or "")
        if v == "UNCONTRACTED":
            unwatched.append(n)
        elif v in BAD_TASK and not (v == "DISABLED" or p.get("expected_disabled")):
            bad.append({"task": n, "verdict": v, "state": p.get("state"),
                        "why": str(p.get("why") or "")[:200], "money_path": bool(MONEY.search(n))})
    return bad, sorted(unwatched)


def restarts(bad: Iterable[Mapping[str, Any]], state: Mapping[str, Any],
             now: datetime) -> list[str]:
    """Non-money STALE/FAILING tasks not Running and not started in the last 2h. Pure."""
    raw = state.get("started")
    started: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out = []
    for b in bad:
        if b["money_path"] or b["verdict"] not in RESTARTABLE or b.get("state") == "Running":
            continue
        t = _ts(started.get(b["task"]))
        if t is None or now - t >= RESTART_EVERY:
            out.append(str(b["task"]))
    return out


def task_start(name: str) -> bool:
    try:
        p = subprocess.run(["schtasks.exe", "/Run", "/TN", name], capture_output=True,
                           text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def run_once(root: Path, *, now: datetime | None = None,
             start: Callable[[str], bool] = task_start,
             page: Callable[[str], None] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    legs = runs(ledger_rows(root / LEDGER_REL), now)
    health = _read(root / HEALTH_REL)
    bad, unwatched = tasks(health)
    st_path = root / STATE_REL
    state = _read(st_path)
    todo = restarts(bad, state, now)
    done = {t: start(t) for t in todo}
    if done:
        raw = state.get("started")
        prev: dict[str, Any] = raw if isinstance(raw, dict) else {}
        state["started"] = {**prev, **{t: now.isoformat() for t in done}}
    flagged = [e for e in legs if e["flag"]]
    names = sorted({f"{e['flag']}:{e['run']}" for e in flagged}
                   | {f"TASK_{b['verdict']}:{b['task']}" for b in bad})
    health_at = _ts(health.get("at"))
    doc = {"schema": SCHEMA, "at": now.isoformat(), "legs_seen": len(legs),
           "flagged": names, "legs": flagged,
           "legs_flagged_n": len(flagged), "tasks_flagged": bad, "unwatched": unwatched,
           "unwatched_n": len(unwatched), "started": done,
           "process_health_age_h": round((now - health_at).total_seconds() / 3600, 2)
           if health_at else None}
    if health_at is None or now - health_at > timedelta(hours=2):
        names.append("PROCESS_HEALTH_STALE")
        doc["flagged"] = names
    key = "|".join(names)
    paged_at = _ts(state.get("paged_at"))
    if names and page is not None and (key != state.get("paged_key") or paged_at is None
                                       or now - paged_at > REPAGE_EVERY):
        top = "; ".join(names[:8]) + (f" (+{len(names) - 8} more)" if len(names) > 8 else "")
        page(f"OUTPUT WATCH: {len(names)} producer/lab/task(s) not producing: {top}. "
             f"Restarted: {sorted(done) or 'none'}. Unwatched (no output contract): "
             f"{len(unwatched)}. Detail: desks/mt5/reports/OUTPUT_WATCH.json")
        state["paged_key"], state["paged_at"] = key, now.isoformat()
    elif not names:
        state.pop("paged_key", None)
    for p, d in ((root / REPORT_REL, doc), (st_path, state)):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, indent=1, sort_keys=True, default=str), encoding="utf-8")
            tmp.replace(p)
        except OSError:
            pass
    return doc
