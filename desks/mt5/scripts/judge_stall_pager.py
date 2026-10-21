#!/usr/bin/env python3
"""THE JUDGE STALL PAGER: a stalled judge pages within minutes, not at the next fence rotation.

    python desks/mt5/scripts/judge_stall_pager.py            # rides MT5-BoxHeartbeat (5 min)
    python desks/mt5/scripts/judge_stall_pager.py --dry-run  # measure and print, page nothing

WHY (2026-10-21). A stalled judge only reached a human through records: the coverage fence in
the MT5-LawGate rotation, which reaches any one fence every few hours at best, and
JUDGE_RESIDENT.json, which no organ read at all. The measured cases were long: 10-12 06:59Z, 33h
with no verdict while the resident's heartbeat kept beating; 10-18 ~19:20Z, the resident died
mid merge_and_publish and nothing judged for ~45h; 10-20 01:44Z, a merge_and_publish that took
14.2h against a healthy 1.2-1.7h. This pager reads the judge's own outputs every five minutes
and pages each incident once, through `libs.ops.alert_channels.send_all`.

WHAT IT READS, and nothing else (it never touches the judge, its priority or its timing):
  * the tail of `desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl` -- the newest `at` stamp
    is the last verdict (the row stamp `judging_throughput._verdict_counts` reads), and when the
    ledger is absent the `last_verdict_at` that JUDGING_THROUGHPUT.json publishes;
  * `desks/mt5/reports/JUDGE_RESIDENT.json` -- status, heartbeat, resident pid and start, the
    last sweep's end, length and exit code, and the sweep child's pid, start and phase;
  * `desks/mt5/reports/universal_gates_external.json` -- the judge's own result for the sweep
    it last completed (`swept_at`, `n_cells`), for the zero-judged-sweep incident only.

THE INCIDENTS, each its own persisted key. EVERY THRESHOLD IS MEASURED, from the git history of
JUDGING_THROUGHPUT.json (242 snapshots, 2026-10-07..10-20) and JUDGE_RESIDENT.json (492
snapshots, 2026-10-14..10-21), and the evidence is beside each constant below:

  no_verdict         no new verdict for NO_VERDICT_H. The backstop only: the ledger appends when a
                     verdict CHANGES, so healthy gaps are long and a sweep that judges and changes
                     nothing is invisible to it -- the incidents below are the real signals.
  resident_dead      heartbeat older than HEARTBEAT_STALE_MIN (or past FUTURE_SKEW_S in the
                     future), or the resident's pid is not alive -- where a pid whose process was
                     created after the resident's own `started_utc` is a REUSED pid, so dead.
  sweep_dead         SWEEPING, and the sweep child's pid is not alive (same reuse rule, against the
                     child's `sweep_started_utc`).
  phase_overrun      the current sweep phase has run past its measured limit (PHASE_LIMIT_H); a
                     phase this file has no measurement for gets UNKNOWN_PHASE_LIMIT_H and is named
                     as unknown in the page. It catches what the heartbeat cannot: the heartbeat
                     thread kept beating through the 33h stall of 10-12.
  sweep_overdue      too long since `last_sweep_ended_utc`: past SWEEP_OVERDUE_H while SWEEPING, or
                     past IDLE_OVERDUE_H in any other live status -- which is how a resident stuck
                     in LANE_HELD or BACKOFF reads, since neither ever reaches phase_overrun.
  zero_judged_sweep  the last sweep completed rc 0 and the judge's own result for it judged 0 cells.
  inputs_unmeasured  a core input (the verdict source, JUDGE_RESIDENT.json, or the phase of a
                     SWEEPING resident) has been unreadable, torn or empty for UNMEASURED_PAGE_MIN.
                     UNMEASURED is a verdict here, and a verdict that persists pages.
  host_unreadable    libs.ops.host_identity raised. The pager fails TOWARD paging: it treats the
                     host as the box, writes its artifact and pages this incident with the rest.

DEDUPE, the desk's convention (state_publication.page_flow, check_judge_coverage): one page when
an incident OPENS, a reminder every REPAGE_H = 6h while it stands, one RESOLVED notice when it
clears. A per-incident reading that cannot be made neither opens nor clears it. The state is
written BEFORE send_all with an in-flight marker, so a run killed mid-send (the 60 s bound) does
not re-page every five minutes: an unconfirmed send is retried after INFLIGHT_RETRY_MIN. A send
that raised, or that an armed pager delivered to no channel, is retried on the next run -- a
RESOLVED notice included. NOT ARMED is recorded by send_all and counts as sent.

ON THE BOX ONLY. JUDGE_RESIDENT.json is published to origin, so every checkout holds a copy whose
heartbeat is hours old and whose pids mean nothing here. Off the trading host (libs.ops.
host_identity, `may_be_trading`) this measures and prints, and never pages or writes state. Pid
liveness uses psutil only -- on Windows `os.kill(pid, 0)` TERMINATES the process -- and an absent
psutil makes the pid checks UNMEASURED.

Clock: MT5-BoxHeartbeat (every 5 minutes; box_heartbeat.main invokes this as a bounded
subprocess and records its exit code in BOX_HEARTBEAT.json, where a failing exit fails the next
heartbeat). Exit 1 means the pager itself failed (a send error or an unwritable state).
Artifact: `desks/mt5/reports/JUDGE_STALL.json` (published by sync_shadow_to_git.ps1). State
(box-local, gitignored): `desks/mt5/logs/judge_stall_page.json`.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
THROUGHPUT = BASE / "reports" / "JUDGING_THROUGHPUT.json"
RESIDENT = BASE / "reports" / "JUDGE_RESIDENT.json"
SWEEP_RESULT = BASE / "reports" / "universal_gates_external.json"
OUT = BASE / "reports" / "JUDGE_STALL.json"
PAGE_STATE_REL = "desks/mt5/logs/judge_stall_page.json"
UNMEASURED = "UNMEASURED"

#: Hours with no new verdict before `no_verdict` opens. MEASURED: the gaps between consecutive
#: distinct `last_verdict_at` values in JUDGING_THROUGHPUT.json's history were 5.55, 6.72, 6.80,
#: 12.30, 12.51, 14.48, 15.26, 15.89, 17.87, 22.65, 31.33, 46.70, 46.70 and 67.33 h. The 46.7 h
#: (10-12, the 33 h hang) and 67.33 h (10-18, the resident died) gaps are incidents. The largest
#: healthy gap is 31.33 h (10-14 17:59Z -> 10-16 01:18Z: sweeps ended 22:59Z and 08:35Z without
#: changing a verdict). With n this small the p99 IS the maximum, so N sits above it with margin.
NO_VERDICT_H = 36.0
#: Minutes before the resident's heartbeat is stale. MEASURED: it is re-stamped every 30 s
#: (run_sharded_gauntlet.RESIDENT_HEARTBEAT_S). Its age at publication over 491 healthy
#: snapshots was median 0.3, p90 0.5, p99 1.5 and max 2.2 min; the one incident read 134.7 min
#: (10-18 19:20Z, the resident dead).
HEARTBEAT_STALE_MIN = 10.0
#: How far ahead of this clock a stamp may sit and still be read: the repo's existing tolerance
#: (libs/research/dsr_inputs.FUTURE_SKEW_S, global_research_acceptance.MAX_FUTURE_SKEW_S).
FUTURE_SKEW_S = 300
#: A process created more than this long after the stamp that names its pid is not that process.
PID_START_SKEW_S = 300
#: Hours a sweep phase may run before `phase_overrun` opens. MEASURED from the healthy sweeps'
#: phase records, 2026-10-14..10-20 (sweep_phase.phases; merge_and_publish from its start to
#: the sweep's end):
#:   plan               9,303 .. 10,706 s (max 2.97 h)  -> 4.5 h  (1.5x the max)
#:   build_shards       3,545 .. 42,782 s (max 11.9 h)  -> 18 h   (1.5x)
#:   collect_and_cut      443 ..  1,235 s               -> 1 h    (floor)
#:   rule_shards           93 ..    819 s               -> 1 h    (floor)
#:   merge_and_publish  4,340 ..  6,108 s (max 1.70 h)  -> 3 h    (1.5x, rounded up)
#: The 10-20 merge_and_publish of 51,198 s (14.2 h, the 64,711 s sweep) is NOT in the healthy
#: set: it held every verdict for 14 h, and it is exactly what this incident is for.
#: `prewarm` and `plan_handoff` are the phases judge_plan_phase adds: prewarm runs against its
#: 8,640 s budget plus ~1,100 s of slack, so 1.5x (8,640 + 1,100) s = 4.06 h; plan_handoff is a
#: handoff with no measured history yet, so the 1 h floor.
PHASE_LIMIT_H: dict[str, float] = {"plan": 4.5, "build_shards": 18.0, "collect_and_cut": 1.0,
                                   "rule_shards": 1.0, "merge_and_publish": 3.0,
                                   "prewarm": round(1.5 * (8_640 + 1_100) / 3600.0, 2),
                                   "plan_handoff": 1.0}
#: A phase with no measurement gets the most generous known limit, and is named unknown.
UNKNOWN_PHASE_LIMIT_H = max(PHASE_LIMIT_H.values())
#: SWEEP OVERDUE. MEASURED: healthy completed sweeps (last_sweep_s, rc 0) ran 36 .. 61,111 s
#: (17,283 / 20,221 / 24,352 / 24,745 / 34,564 / 52,043 / 54,327 / 61,111; the 64,711 s sweep is
#: the 14.2 h-merge incident above). The resident starts the next sweep at once: end -> next
#: start measured 0 .. 31 s, and its longest designed pause is the 300 s backoff cap
#: (run_sharded_gauntlet.RESIDENT_BACKOFF_S). So while SWEEPING, 1.5 x (61,111 + 300) s = 25.6 h
#: since the last end; in any other live status (RUNNING, BACKOFF, LANE_HELD, RESPAWN, EXITED)
#: the healthy gap is at most the 300 s pause, floored at one hour.
HEALTHY_SWEEP_MAX_S = 61_111
INTER_SWEEP_MAX_S = 300
SWEEP_OVERDUE_H = round(1.5 * (HEALTHY_SWEEP_MAX_S + INTER_SWEEP_MAX_S) / 3600.0, 2)
IDLE_OVERDUE_H = 1.0
#: Minutes a core input may stay UNMEASURED before `inputs_unmeasured` opens.
UNMEASURED_PAGE_MIN = 30.0
#: Minutes before an unconfirmed (in-flight) send is retried: a run killed mid-send must not
#: re-page every five minutes, and must not lose the page either.
INFLIGHT_RETRY_MIN = 30.0
#: The desk's reminder convention (state_publication.REPAGE_H, run_alerts._DEDUPE_S).
REPAGE_H = 6.0
INCIDENTS = ("no_verdict", "resident_dead", "sweep_dead", "phase_overrun", "sweep_overdue",
             "zero_judged_sweep", "inputs_unmeasured", "host_unreadable")
#: Bytes read from the ledger's end. Rows are a few hundred bytes; the newest stamp is in here.
TAIL_BYTES = 256 * 1024
#: Statuses in which the resident has stopped ON PURPOSE and its heartbeat is expected to stop.
OPERATOR_STOPPED = ("STOPPED", "DONE")

_AT = re.compile(r'"at"\s*:\s*"([^"]+)"')

Sender = Callable[[str, str], Any]
PidAlive = Callable[[object, datetime | None], bool | None]


def _stamp(txt: object) -> datetime | None:
    s = str(txt or "").strip()
    if not s:
        return None
    try:
        at = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at.astimezone(UTC) if at.tzinfo else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _says(alive: bool | None) -> str:
    return {True: "alive", False: "NOT ALIVE", None: "UNMEASURED"}[alive]


def last_verdict(now: datetime, *, ledger: Path = LEDGER,
                 throughput: Path = THROUGHPUT) -> dict[str, Any]:
    """The newest verdict stamp, from the ledger tail; the published figure when it is absent."""
    try:
        with ledger.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        tail = None
    if tail is not None:
        stamps = [s for s in (_stamp(m.group(1)) for m in _AT.finditer(tail))
                  if s is not None and s <= now]
        if stamps:
            return {"at": max(stamps).isoformat(timespec="seconds"), "source": ledger.name}
        return {"at": None, "source": ledger.name,
                "why": f"{UNMEASURED}: {ledger.name} is empty or holds no past-dated `at` stamp "
                       f"in its last {TAIL_BYTES} bytes"}
    doc = _read_json(throughput)
    rate = doc.get("rate") if isinstance(doc, dict) else None
    verdicts = rate.get("verdicts") if isinstance(rate, dict) else None
    at = _stamp(verdicts.get("last_verdict_at")) if isinstance(verdicts, dict) else None
    if at is not None and at <= now:
        return {"at": at.isoformat(timespec="seconds"),
                "source": f"{throughput.name} rate.verdicts.last_verdict_at"}
    return {"at": None, "source": None,
            "why": f"{UNMEASURED}: {ledger.name} absent and {throughput.name} names no verdict"}


def _pid_alive(pid: object, started: datetime | None) -> bool | None:
    """Is `pid` the process that `started` names? psutil only -- never os.kill.

    True: it exists and was created no later than `started` + PID_START_SKEW_S. False: it does
    not exist, or it was created AFTER that (the pid was reused by another process). None: psutil
    is absent, the pid or `started` is unusable, or the create time cannot be read."""
    try:
        n = int(pid)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        if not psutil.pid_exists(n):
            return False
        if started is None:
            return None
        created = float(psutil.Process(n).create_time())
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None
    return created <= started.timestamp() + PID_START_SKEW_S


def _heartbeat(doc: dict[str, Any], at: datetime, status: str,
               pid_alive: PidAlive) -> dict[str, Any]:
    if status in OPERATOR_STOPPED:
        return {"open": False, "why": f"resident {status} on purpose: {doc.get('why')}"}
    hb = _stamp(doc.get("heartbeat_utc"))
    if hb is None:
        return {"open": None, "why": f"{UNMEASURED}: no heartbeat stamp"}
    raw_min = (at - hb).total_seconds() / 60.0
    alive = pid_alive(doc.get("pid"), _stamp(doc.get("started_utc")))
    if raw_min < -FUTURE_SKEW_S / 60.0:
        return {"open": True, "heartbeat_age_min": round(raw_min, 1), "pid_alive": alive,
                "why": (f"resident heartbeat {doc.get('heartbeat_utc')} is {-raw_min:.1f} min in "
                        f"the future, past the {FUTURE_SKEW_S}s skew: it proves nothing")}
    age_min = max(0.0, raw_min)
    return {"open": age_min > HEARTBEAT_STALE_MIN or alive is False,
            "heartbeat_age_min": round(age_min, 1), "pid_alive": alive,
            "why": (f"resident {status} pid {doc.get('pid')}: heartbeat {age_min:.1f} min old "
                    f"(limit {HEARTBEAT_STALE_MIN:g}), pid {_says(alive)}")}


def _overdue(doc: dict[str, Any], at: datetime, status: str) -> dict[str, Any]:
    if status in OPERATOR_STOPPED:
        return {"open": False, "why": f"resident {status} on purpose"}
    since = _stamp(doc.get("last_sweep_ended_utc")) or _stamp(doc.get("started_utc"))
    if since is None:
        return {"open": None, "why": f"{UNMEASURED}: no last_sweep_ended_utc or started_utc"}
    h = max(0.0, (at - since).total_seconds() / 3600.0)
    limit = SWEEP_OVERDUE_H if status == "SWEEPING" else IDLE_OVERDUE_H
    return {"open": h > limit, "hours": round(h, 2), "limit_h": limit,
            "why": (f"{h:.1f}h since the last sweep ended ({doc.get('last_sweep_ended_utc')}), "
                    f"status {status or '?'}; limit {limit:g}h")}


def _zero_judged(doc: dict[str, Any], sweep_result: Path) -> dict[str, Any]:
    end = _stamp(doc.get("last_sweep_ended_utc"))
    if end is None:
        return {"open": None, "why": f"{UNMEASURED}: no completed sweep recorded"}
    if doc.get("last_rc") not in (0, "0"):
        return {"open": False, "why": f"last sweep rc {doc.get('last_rc')}: not a completed sweep"}
    res = _read_json(sweep_result)
    swept = _stamp(res.get("swept_at")) if isinstance(res, dict) else None
    try:
        length = float(doc.get("last_sweep_s") or 0.0)
    except (TypeError, ValueError):
        length = 0.0
    lo = end - timedelta(seconds=length + PID_START_SKEW_S)
    hi = end + timedelta(seconds=PID_START_SKEW_S)
    if not isinstance(res, dict) or swept is None or not lo <= swept <= hi:
        return {"open": None, "why": (f"{UNMEASURED}: {sweep_result.name} carries no result "
                                      f"stamped inside the last sweep "
                                      f"({lo.isoformat(timespec='seconds')} .. "
                                      f"{end.isoformat(timespec='seconds')})")}
    n = res.get("n_cells")
    if n is None and isinstance(res.get("verdicts"), list):
        n = len(res["verdicts"])
    try:
        cells = int(n)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {"open": None, "why": f"{UNMEASURED}: {sweep_result.name} names no cell count"}
    return {"open": cells == 0, "cells": cells,
            "why": f"the sweep that ended {doc.get('last_sweep_ended_utc')} judged {cells} cell(s)"}


def measure(now: datetime | None = None, *, ledger: Path = LEDGER,
            throughput: Path = THROUGHPUT, resident: Path = RESIDENT,
            sweep_result: Path = SWEEP_RESULT,
            pid_alive: PidAlive = _pid_alive) -> dict[str, Any]:
    """Each incident: True (open), False (clear) or None (UNMEASURED), with its reading."""
    at = now or datetime.now(tz=UTC)
    out: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "incidents": {},
                           "unmeasured_inputs": [],
                           "thresholds": {"no_verdict_h": NO_VERDICT_H,
                                          "heartbeat_stale_min": HEARTBEAT_STALE_MIN,
                                          "phase_limit_h": PHASE_LIMIT_H,
                                          "unknown_phase_limit_h": UNKNOWN_PHASE_LIMIT_H,
                                          "sweep_overdue_h": SWEEP_OVERDUE_H,
                                          "idle_overdue_h": IDLE_OVERDUE_H,
                                          "unmeasured_page_min": UNMEASURED_PAGE_MIN}}
    inc: dict[str, dict[str, Any]] = out["incidents"]
    gaps: list[str] = out["unmeasured_inputs"]

    lv = last_verdict(at, ledger=ledger, throughput=throughput)
    out["last_verdict"] = lv
    lv_at = _stamp(lv.get("at"))
    if lv_at is None:
        inc["no_verdict"] = {"open": None, "why": lv.get("why")}
        gaps.append(f"verdict source: {lv.get('why')}")
    else:
        h = (at - lv_at).total_seconds() / 3600.0
        inc["no_verdict"] = {"open": h > NO_VERDICT_H, "hours": round(h, 2),
                             "why": (f"no new verdict for {h:.1f}h (last {lv['at']}, "
                                     f"{lv['source']}); limit {NO_VERDICT_H:g}h")}

    doc = _read_json(resident)
    if not isinstance(doc, dict) or not doc:
        why = f"{UNMEASURED}: {resident.name} absent, torn or empty"
        for k in ("resident_dead", "sweep_dead", "phase_overrun", "sweep_overdue",
                  "zero_judged_sweep"):
            inc[k] = {"open": None, "why": why}
        gaps.append(why)
        return out
    status = str(doc.get("status") or "")
    out["resident"] = {"status": status, "pid": doc.get("pid"),
                       "heartbeat_utc": doc.get("heartbeat_utc"),
                       "last_sweep_ended_utc": doc.get("last_sweep_ended_utc"),
                       "last_rc": doc.get("last_rc")}
    inc["resident_dead"] = _heartbeat(doc, at, status, pid_alive)
    inc["sweep_overdue"] = _overdue(doc, at, status)
    inc["zero_judged_sweep"] = _zero_judged(doc, sweep_result)

    phase = doc.get("sweep_phase") if isinstance(doc.get("sweep_phase"), dict) else None
    if status != "SWEEPING":
        why = f"resident {status or UNMEASURED}: no sweep in flight"
        inc["sweep_dead"] = {"open": False if status else None, "why": why}
        inc["phase_overrun"] = {"open": False if status else None, "why": why}
        return out
    if not phase:
        # SWEEPING WITH NO PHASE IS NOT CLEAN: the resident says a sweep runs and nothing names it.
        why = f"{UNMEASURED}: resident SWEEPING but JUDGE_RESIDENT.json carries no sweep_phase"
        inc["sweep_dead"] = {"open": None, "why": why}
        inc["phase_overrun"] = {"open": None, "why": why}
        gaps.append(why)
        return out
    child = pid_alive(phase.get("pid"), _stamp(phase.get("sweep_started_utc")))
    inc["sweep_dead"] = {"open": None if child is None else not child, "pid": phase.get("pid"),
                         "why": f"sweep child pid {phase.get('pid')} {_says(child)}"}
    name = str(phase.get("phase") or "")
    started = _stamp(phase.get("phase_started_utc"))
    if started is None or not name:
        why = f"{UNMEASURED}: sweep phase {name or '?'} carries no name or no start stamp"
        inc["phase_overrun"] = {"open": None, "phase": name or None, "why": why}
        gaps.append(why)
        return out
    known = name in PHASE_LIMIT_H
    limit = PHASE_LIMIT_H.get(name, UNKNOWN_PHASE_LIMIT_H)
    h = max(0.0, (at - started).total_seconds() / 3600.0)
    inc["phase_overrun"] = {
        "open": h > limit, "phase": name, "hours": round(h, 2), "known_phase": known,
        "why": (f"sweep phase {name}{'' if known else ' (UNKNOWN to this pager)'} has run "
                f"{h:.1f}h since {phase.get('phase_started_utc')} (limit {limit:g}h"
                + ("" if known else ", the default for an unmeasured phase") + ")")}
    return out


def _write_atomic(path: Path, text: str) -> None:
    """tmp + os.replace, so a reader (or a killed run) never sees a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, "utf-8")
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def _default_sender(root: Path) -> Sender:
    def send(title: str, body: str) -> Any:
        from libs.ops import alert_channels
        # Anchored on the repo root; nothing here reads, prints or records a credential.
        return alert_channels.send_all(
            title, body, config=root / "data/secrets/alert_channels.json",
            ledger=root / "data/alert_delivery.jsonl")
    return send


def page(reading: dict[str, Any], *, root: Path | None = None, now: datetime | None = None,
         sender: Sender | None = None, repage_h: float = REPAGE_H) -> dict[str, Any]:
    """Page opened incidents, reminders and resolutions, deduplicated. Never raises."""
    try:
        return _page(reading, root=root or ROOT, now=now or datetime.now(tz=UTC),
                     sender=sender, repage_h=repage_h)
    except Exception as exc:
        return {"sent": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


def _ts(row: dict[str, Any], key: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(row.get(key)))
    except (TypeError, ValueError):
        return None


def _landing(row: dict[str, Any], now: datetime) -> bool:
    """A send marked in flight less than INFLIGHT_RETRY_MIN ago may still be landing."""
    t = _ts(row, "inflight_at")
    return t is not None and t <= now and (now - t).total_seconds() / 60.0 < INFLIGHT_RETRY_MIN


def _page(reading: dict[str, Any], *, root: Path, now: datetime, sender: Sender | None,
          repage_h: float) -> dict[str, Any]:
    path = root / PAGE_STATE_REL
    prev = _read_json(path)
    prev = prev if isinstance(prev, dict) else {}
    raw = prev.get("open")
    open_prev: dict[str, dict[str, Any]] = {
        k: dict(v) for k, v in (raw.items() if isinstance(raw, dict) else ())
        if k in INCIDENTS and isinstance(v, dict)}
    raw_res = prev.get("resolving")
    resolving: dict[str, dict[str, Any]] = {
        k: dict(v) for k, v in (raw_res.items() if isinstance(raw_res, dict) else ())
        if k in INCIDENTS and isinstance(v, dict)}
    stamp = now.isoformat(timespec="seconds")
    inc: dict[str, dict[str, Any]] = {k: dict(v) for k, v in
                                      (reading.get("incidents") or {}).items()}

    # UNMEASURED IS A VERDICT THAT PAGES ONCE IT PERSISTS (audit of e759c01f6, must-fix 1).
    gaps = [str(g) for g in reading.get("unmeasured_inputs") or ()]
    since: datetime | None = None
    if gaps:
        since = _ts(prev, "unmeasured_since")
        if since is None or since > now:
            since = now
        mins = (now - since).total_seconds() / 60.0
        inc["inputs_unmeasured"] = {
            "open": mins >= UNMEASURED_PAGE_MIN, "minutes": round(mins, 1),
            "why": (f"UNMEASURED for {mins:.0f} min (limit {UNMEASURED_PAGE_MIN:g}): "
                    + "; ".join(gaps))[:400]}
    else:
        inc["inputs_unmeasured"] = {"open": False, "why": "every core input was read"}

    is_open = {k for k in INCIDENTS if (inc.get(k) or {}).get("open") is True}
    # A per-incident UNMEASURED reading neither opens nor clears that incident.
    unmeasured = {k for k in INCIDENTS if (inc.get(k) or {}).get("open") is None}
    standing = is_open | (unmeasured & set(open_prev))
    opened = [k for k in INCIDENTS if k in is_open and k not in open_prev]
    for k in standing:                       # a recurrence cancels an undelivered resolve
        resolving.pop(k, None)
    for k in INCIDENTS:
        if k in open_prev and k not in standing:
            resolving[k] = {"opened_at": open_prev[k].get("opened_at"), "resolved_at": stamp}
    due: list[str] = []
    for k in INCIDENTS:
        if k not in is_open or k not in open_prev:
            continue
        row = open_prev[k]
        if _landing(row, now):
            continue                         # a send may still be landing: do not re-page
        last = _ts(row, "paged_at")
        if row.get("inflight_at") or last is None or last > now or \
                (now - last).total_seconds() / 3600 >= repage_h:
            due.append(k)
    to_resolve = [k for k in INCIDENTS if k in resolving and not _landing(resolving[k], now)]
    state_open: dict[str, dict[str, Any]] = {}
    for k in standing:
        row = dict(open_prev.get(k) or {})
        row.setdefault("opened_at", stamp)
        row["incident"] = f"judge_stall:{k}@{row['opened_at']}"
        if k in is_open:
            row["why"] = str((inc.get(k) or {}).get("why"))[:300]
        state_open[k] = row
    out: dict[str, Any] = {"sent": False, "open": sorted(is_open), "opened": opened,
                           "reminded": due, "resolved": to_resolve}
    to_page = opened + due

    def _save() -> None:
        try:
            _write_atomic(path, json.dumps({
                "at": stamp,
                "unmeasured_since": None if since is None else since.isoformat(
                    timespec="seconds"),
                "open": state_open, "resolving": resolving, "last": {
                    k: out.get(k) for k in ("sent", "title", "armed", "delivered", "error",
                                            "opened", "reminded", "resolved")}},
                indent=1, default=str))
        except OSError as exc:
            out["state_write_error"] = f"{type(exc).__name__}: {exc}"[:200]

    if not (to_page or to_resolve):
        _save()
        return out
    # IN FLIGHT BEFORE THE SEND: a kill inside send_all leaves this marker, not silence.
    for k in to_page:
        state_open[k]["inflight_at"] = stamp
    for k in to_resolve:
        resolving[k]["inflight_at"] = stamp
    _save()
    title = ("JUDGE STALLED: " + ", ".join(sorted(is_open)) if to_page
             else "JUDGE STALL RESOLVED: " + ", ".join(to_resolve))
    lines = [f"{'OPEN' if k in opened else 'STILL'} {k}: {inc[k].get('why')}" for k in to_page]
    lines += [f"RESOLVED {k} (opened {resolving[k].get('opened_at')}): "
              f"{(inc.get(k) or {}).get('why')}" for k in to_resolve]
    if reading.get("host_note"):
        lines.append(str(reading["host_note"]))
    lv = reading.get("last_verdict") or {}
    lines.append(f"last verdict {lv.get('at')} ({lv.get('source')}); measured "
                 f"{reading.get('at')} by judge_stall_pager.py")
    err: object = None
    try:
        res = (sender or _default_sender(root))(title, "\n".join(lines)[:3500])
        res = res if isinstance(res, dict) else {}
        err = res.get("error")
    except Exception as exc:
        res, err = {}, f"{type(exc).__name__}: {exc}"
    armed, delivered = res.get("armed"), res.get("delivered")
    # A send that raised, or an armed pager that delivered to no channel, is retried on the next
    # run (its in-flight marker is cleared, so it is due at once). NOT ARMED counts as sent.
    failed = bool(err) or (bool(armed) and not delivered)
    out.update({"sent": not failed, "title": title, "armed": armed, "delivered": delivered})
    if err:
        out["error"] = str(err)[:200]
    for k in to_page:
        state_open[k].pop("inflight_at", None)
        if failed:
            state_open[k]["last_error"] = out.get("error") or "no armed channel delivered"
            state_open[k]["last_error_at"] = stamp
            state_open[k].pop("paged_at", None)
        else:
            state_open[k]["paged_at"] = stamp
            state_open[k].pop("last_error", None)
            state_open[k].pop("last_error_at", None)
    for k in to_resolve:
        if failed:
            resolving[k].pop("inflight_at", None)
            resolving[k]["last_error"] = out.get("error") or "no armed channel delivered"
        else:
            resolving.pop(k, None)
    _save()
    return out


def _on_box() -> bool | None:
    """True/False from host_identity; None when it raised (fail toward paging)."""
    try:
        from libs.ops import host_identity
        return bool(host_identity.identify().may_be_trading)
    except Exception:
        return None


_DETECT = "detect"


def run(*, dry_run: bool = False, out: Path = OUT, root: Path | None = None,
        now: datetime | None = None, sender: Sender | None = None,
        on_box: bool | str | None = _DETECT, **paths: Any) -> dict[str, Any]:
    doc = measure(now, **paths)
    box = _on_box() if on_box == _DETECT else on_box
    if box is None:
        # HOST IDENTITY UNREADABLE: fail toward paging. A box that cannot name itself must not go
        # silent everywhere; the cost of the alternative is one page from a machine with no
        # armed channel, which send_all records as NOT ARMED.
        doc["host"] = "UNKNOWN (host_identity raised): treated as the box"
        doc["host_note"] = "host identity unreadable: this page may come from a non-box checkout"
        doc["incidents"]["host_unreadable"] = {"open": True,
                                               "why": "libs.ops.host_identity raised"}
    else:
        doc["host"] = "trading box" if box else "off box (measured, never paged)"
        doc["incidents"]["host_unreadable"] = {"open": False, "why": "host identity read"}
    if dry_run or box is False:
        doc["page"] = {"sent": False, "reason": "dry run" if dry_run else "off box"}
        return doc
    doc["page"] = page(doc, root=root, now=now, sender=sender)
    try:
        _write_atomic(out, json.dumps(doc, indent=1, default=str))
    except OSError as exc:
        doc["page"]["state_write_error"] = f"artifact: {type(exc).__name__}: {exc}"[:200]
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    page_doc = doc.get("page") or {}
    print(json.dumps({"open": sorted(k for k, v in doc["incidents"].items() if v.get("open")),
                      "unmeasured": sorted(k for k, v in doc["incidents"].items()
                                           if v.get("open") is None),
                      "last_verdict": doc["last_verdict"].get("at"),
                      "host": doc["host"],
                      "page": {k: page_doc.get(k) for k in ("sent", "title", "error",
                                                            "state_write_error", "reason")}}))
    return 1 if page_doc.get("error") or page_doc.get("state_write_error") else 0


__all__ = ["FUTURE_SKEW_S", "HEARTBEAT_STALE_MIN", "IDLE_OVERDUE_H", "INCIDENTS",
           "NO_VERDICT_H", "PAGE_STATE_REL", "PHASE_LIMIT_H", "REPAGE_H", "SWEEP_OVERDUE_H",
           "UNKNOWN_PHASE_LIMIT_H", "UNMEASURED_PAGE_MIN", "last_verdict", "main", "measure",
           "page", "run"]


if __name__ == "__main__":
    raise SystemExit(main())
