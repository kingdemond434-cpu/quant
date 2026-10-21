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
    is the last verdict (the same row stamp `judging_throughput._verdict_counts` reads), and
    when the ledger is absent the `last_verdict_at` that JUDGING_THROUGHPUT.json publishes;
  * `desks/mt5/reports/JUDGE_RESIDENT.json` -- status, heartbeat, resident pid, and the sweep
    child's pid and current phase.

THE INCIDENTS, each its own persisted key. EVERY THRESHOLD IS MEASURED, from the git history of
JUDGING_THROUGHPUT.json (242 snapshots, 2026-10-07..10-20) and JUDGE_RESIDENT.json (492
snapshots, 2026-10-14..10-21), and the evidence is beside each constant below:

  no_verdict      no new verdict for NO_VERDICT_H hours. The backstop. The judge appends only
                  when a terminal verdict CHANGES, and only near the end of a sweep, so healthy
                  gaps are long: the healthy gaps since the 10-14 hang fix were 5.6, 6.7, 6.8,
                  14.5, 15.3 and 31.3 h (two healthy sweeps ended inside the 31.3 h one without
                  changing a verdict).
  resident_dead   the resident's heartbeat (re-stamped every 30 s) is older than
                  HEARTBEAT_STALE_MIN, or its pid is not alive on this box. The fast signal.
  sweep_dead      the resident says SWEEPING and the sweep child's pid is not alive.
  phase_overrun   the current sweep phase has run past its own measured limit (PHASE_LIMIT_H).
                  This is what catches a stall the heartbeat cannot see: the heartbeat thread
                  kept beating through the 33 h stall of 10-12.

DEDUPE, the desk's convention (state_publication.page_flow, check_judge_coverage): one page when
an incident OPENS, a reminder every REPAGE_H = 6 h while it stands, one RESOLVED notice when it
clears. A send that raised, or that an armed pager delivered to no channel, leaves the incident
unpaged so the next run retries; NOT ARMED is recorded by send_all and counts as sent. An input
that cannot be read is UNMEASURED for its incidents: it neither opens nor clears them.

ON THE BOX ONLY. JUDGE_RESIDENT.json is published to origin, so every checkout holds a copy whose
heartbeat is hours old and whose pids mean nothing here. Off the trading host (libs.ops.
host_identity, `may_be_trading`) this measures and prints, and never pages or writes state.
Pid liveness uses psutil only -- on Windows `os.kill(pid, 0)` TERMINATES the process -- and an
absent psutil makes the pid checks UNMEASURED.

Clock: MT5-BoxHeartbeat (every 5 minutes; box_heartbeat.main invokes this as a bounded
subprocess). Artifact: `desks/mt5/reports/JUDGE_STALL.json`. State (box-local, gitignored):
`desks/mt5/logs/judge_stall_page.json`.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
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
OUT = BASE / "reports" / "JUDGE_STALL.json"
PAGE_STATE_REL = "desks/mt5/logs/judge_stall_page.json"
UNMEASURED = "UNMEASURED"

#: Hours with no new verdict before `no_verdict` opens. MEASURED: the gaps between consecutive
#: distinct `last_verdict_at` values in JUDGING_THROUGHPUT.json's history were 5.55, 6.72, 6.80,
#: 12.30, 12.51, 14.48, 15.26, 15.89, 17.87, 22.65, 31.33, 46.70, 46.70 and 67.33 h. The 46.7 h
#: (10-12, the 33 h hang) and 67.33 h (10-18, the resident died) gaps are incidents. The largest
#: healthy gap is 31.33 h (10-14 17:59Z -> 10-16 01:18Z: sweeps ended 22:59Z and 08:35Z without
#: changing a verdict). With n this small the p99 IS the maximum, so N sits above it with margin.
#: This is the backstop; the resident and phase incidents are the fast signals.
NO_VERDICT_H = 36.0
#: Minutes before the resident's heartbeat is stale. MEASURED: it is re-stamped every 30 s
#: (run_sharded_gauntlet.RESIDENT_HEARTBEAT_S). Its age at publication over 491 healthy
#: snapshots was median 0.3, p90 0.5, p99 1.5 and max 2.2 min; the one incident read 134.7 min
#: (10-18 19:20Z, the resident dead).
HEARTBEAT_STALE_MIN = 10.0
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
PHASE_LIMIT_H: dict[str, float] = {"plan": 4.5, "build_shards": 18.0, "collect_and_cut": 1.0,
                                   "rule_shards": 1.0, "merge_and_publish": 3.0}
#: The desk's reminder convention (state_publication.REPAGE_H, run_alerts._DEDUPE_S).
REPAGE_H = 6.0
INCIDENTS = ("no_verdict", "resident_dead", "sweep_dead", "phase_overrun")
#: Bytes read from the ledger's end. Rows are a few hundred bytes; the newest stamp is in here.
TAIL_BYTES = 256 * 1024
#: Statuses in which the resident has stopped ON PURPOSE and its heartbeat is expected to stop.
OPERATOR_STOPPED = ("STOPPED", "DONE")

_AT = re.compile(r'"at"\s*:\s*"([^"]+)"')

Sender = Callable[[str, str], Any]


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
                "why": f"{UNMEASURED}: no past-dated `at` stamp in the last {TAIL_BYTES} bytes"}
    doc = _read_json(throughput)
    rate = doc.get("rate") if isinstance(doc, dict) else None
    verdicts = rate.get("verdicts") if isinstance(rate, dict) else None
    at = _stamp(verdicts.get("last_verdict_at")) if isinstance(verdicts, dict) else None
    if at is not None and at <= now:
        return {"at": at.isoformat(timespec="seconds"),
                "source": f"{throughput.name} rate.verdicts.last_verdict_at"}
    return {"at": None, "source": None,
            "why": f"{UNMEASURED}: {ledger.name} absent and {throughput.name} names no verdict"}


def _pid_alive(pid: object) -> bool | None:
    """True/False from psutil; None when psutil or the pid is unusable. Never os.kill."""
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
        return bool(psutil.pid_exists(n))
    except Exception:
        return None


def measure(now: datetime | None = None, *, ledger: Path = LEDGER,
            throughput: Path = THROUGHPUT, resident: Path = RESIDENT,
            pid_alive: Callable[[object], bool | None] = _pid_alive) -> dict[str, Any]:
    """Each incident: True (open), False (clear) or None (UNMEASURED), with its reading."""
    at = now or datetime.now(tz=UTC)
    out: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "incidents": {},
                           "thresholds": {"no_verdict_h": NO_VERDICT_H,
                                          "heartbeat_stale_min": HEARTBEAT_STALE_MIN,
                                          "phase_limit_h": PHASE_LIMIT_H}}
    inc: dict[str, dict[str, Any]] = out["incidents"]

    lv = last_verdict(at, ledger=ledger, throughput=throughput)
    out["last_verdict"] = lv
    lv_at = _stamp(lv.get("at"))
    if lv_at is None:
        inc["no_verdict"] = {"open": None, "why": lv.get("why")}
    else:
        h = (at - lv_at).total_seconds() / 3600.0
        inc["no_verdict"] = {"open": h > NO_VERDICT_H, "hours": round(h, 2),
                             "why": (f"no new verdict for {h:.1f}h (last {lv['at']}, "
                                     f"{lv['source']}); limit {NO_VERDICT_H:g}h")}

    doc = _read_json(resident)
    if not isinstance(doc, dict):
        why = f"{UNMEASURED}: {resident.name} absent or unreadable"
        for k in ("resident_dead", "sweep_dead", "phase_overrun"):
            inc[k] = {"open": None, "why": why}
        return out
    status = str(doc.get("status") or "")
    out["resident"] = {"status": status, "pid": doc.get("pid"),
                       "heartbeat_utc": doc.get("heartbeat_utc")}
    hb = _stamp(doc.get("heartbeat_utc"))
    if status in OPERATOR_STOPPED:
        inc["resident_dead"] = {"open": False,
                                "why": f"resident {status} on purpose: {doc.get('why')}"}
    elif hb is None:
        inc["resident_dead"] = {"open": None, "why": f"{UNMEASURED}: no heartbeat stamp"}
    else:
        age_min = max(0.0, (at - hb).total_seconds() / 60.0)
        alive = pid_alive(doc.get("pid"))
        stale = age_min > HEARTBEAT_STALE_MIN
        inc["resident_dead"] = {
            "open": stale or alive is False, "heartbeat_age_min": round(age_min, 1),
            "pid_alive": alive,
            "why": (f"resident {status} pid {doc.get('pid')}: heartbeat {age_min:.1f} min old "
                    f"(limit {HEARTBEAT_STALE_MIN:g}), pid "
                    + {True: "alive", False: "NOT ALIVE", None: "UNMEASURED"}[alive])}

    phase = doc.get("sweep_phase") if isinstance(doc.get("sweep_phase"), dict) else {}
    if status != "SWEEPING" or not phase:
        why = f"resident {status or UNMEASURED}: no sweep in flight"
        inc["sweep_dead"] = {"open": False if status else None, "why": why}
        inc["phase_overrun"] = {"open": False if status else None, "why": why}
        return out
    child = pid_alive(phase.get("pid"))
    inc["sweep_dead"] = {"open": None if child is None else not child, "pid": phase.get("pid"),
                         "why": (f"sweep child pid {phase.get('pid')} "
                                 + {True: "alive", False: "NOT ALIVE",
                                    None: "UNMEASURED"}[child])}
    name = str(phase.get("phase") or "")
    started = _stamp(phase.get("phase_started_utc"))
    limit = PHASE_LIMIT_H.get(name)
    if started is None or limit is None:
        inc["phase_overrun"] = {"open": None, "phase": name or None,
                                "why": f"{UNMEASURED}: phase {name or '?'} has no measured "
                                       f"limit or no start stamp"}
    else:
        h = max(0.0, (at - started).total_seconds() / 3600.0)
        inc["phase_overrun"] = {"open": h > limit, "phase": name, "hours": round(h, 2),
                                "why": (f"sweep phase {name} has run {h:.1f}h since "
                                        f"{phase.get('phase_started_utc')} (limit {limit:g}h)")}
    return out


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


def _page(reading: dict[str, Any], *, root: Path, now: datetime, sender: Sender | None,
          repage_h: float) -> dict[str, Any]:
    path = root / PAGE_STATE_REL
    prev = _read_json(path)
    prev = prev if isinstance(prev, dict) else {}
    raw = prev.get("open")
    open_prev: dict[str, dict[str, Any]] = {
        k: v for k, v in (raw.items() if isinstance(raw, dict) else ())
        if k in INCIDENTS and isinstance(v, dict)}
    inc = reading.get("incidents") or {}
    stamp = now.isoformat(timespec="seconds")
    is_open = {k for k in INCIDENTS if (inc.get(k) or {}).get("open") is True}
    # UNMEASURED neither opens nor clears: an incident we cannot read stays as it was.
    unmeasured = {k for k in INCIDENTS if (inc.get(k) or {}).get("open") is None}
    standing = is_open | (unmeasured & set(open_prev))
    opened = [k for k in INCIDENTS if k in is_open and k not in open_prev]
    resolved = [k for k in INCIDENTS if k in open_prev and k not in standing]
    due: list[str] = []
    for k in INCIDENTS:
        if k not in is_open or k not in open_prev:
            continue
        last = None
        with contextlib.suppress(TypeError, ValueError):
            last = datetime.fromisoformat(str(open_prev[k].get("paged_at")))
        if last is None or last > now or (now - last).total_seconds() / 3600 >= repage_h:
            due.append(k)
    state_open: dict[str, dict[str, Any]] = {}
    for k in standing:
        row = dict(open_prev.get(k) or {})
        row.setdefault("opened_at", stamp)
        row["incident"] = f"judge_stall:{k}@{row['opened_at']}"
        if k in is_open:
            row["why"] = str((inc.get(k) or {}).get("why"))[:300]
        state_open[k] = row
    out: dict[str, Any] = {"sent": False, "open": sorted(is_open), "opened": opened,
                           "reminded": due, "resolved": resolved}
    to_page = opened + due
    if to_page or resolved:
        title = ("JUDGE STALLED: " + ", ".join(sorted(is_open)) if to_page
                 else "JUDGE STALL RESOLVED: " + ", ".join(resolved))
        lines = [f"{'OPEN' if k in opened else 'STILL'} {k}: {inc[k].get('why')}"
                 for k in to_page]
        lines += [f"RESOLVED {k} (opened {open_prev[k].get('opened_at')}): "
                  f"{(inc.get(k) or {}).get('why')}" for k in resolved]
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
        failed = bool(err) or (bool(armed) and not delivered)
        out.update({"sent": not failed, "title": title, "armed": armed, "delivered": delivered})
        if err:
            out["error"] = str(err)[:200]
        for k in to_page:
            if failed:
                state_open[k]["last_error"] = out.get("error") or "no armed channel delivered"
                state_open[k]["last_error_at"] = stamp
            else:
                state_open[k]["paged_at"] = stamp
                state_open[k].pop("last_error", None)
                state_open[k].pop("last_error_at", None)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"at": stamp, "open": state_open, "last": {
            k: out.get(k) for k in ("sent", "title", "armed", "delivered", "error", "opened",
                                    "reminded", "resolved")}}, indent=1, default=str), "utf-8")
    except OSError as exc:
        out["state_write_error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def _on_box() -> bool:
    try:
        from libs.ops import host_identity
        return bool(host_identity.identify().may_be_trading)
    except Exception:
        return False


def run(*, dry_run: bool = False, out: Path = OUT, root: Path | None = None,
        now: datetime | None = None, sender: Sender | None = None,
        on_box: bool | None = None, **paths: Any) -> dict[str, Any]:
    doc = measure(now, **paths)
    box = _on_box() if on_box is None else on_box
    doc["host"] = "trading box" if box else "off box (measured, never paged)"
    if dry_run or not box:
        doc["page"] = {"sent": False, "reason": "dry run" if dry_run else "off box"}
        return doc
    doc["page"] = page(doc, root=root, now=now, sender=sender)
    with contextlib.suppress(OSError):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    print(json.dumps({"open": sorted(k for k, v in doc["incidents"].items() if v.get("open")),
                      "unmeasured": sorted(k for k, v in doc["incidents"].items()
                                           if v.get("open") is None),
                      "last_verdict": doc["last_verdict"].get("at"),
                      "host": doc["host"],
                      "page": {k: doc["page"].get(k) for k in ("sent", "title", "error",
                                                                 "reason")}}))
    return 0


__all__ = ["HEARTBEAT_STALE_MIN", "INCIDENTS", "NO_VERDICT_H", "PAGE_STATE_REL", "PHASE_LIMIT_H",
           "REPAGE_H", "last_verdict", "main", "measure", "page", "run"]


if __name__ == "__main__":
    raise SystemExit(main())
