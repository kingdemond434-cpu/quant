"""Run the MT5 evidence-pipeline self-heal and publish its measured result.

This is deliberately separate from :mod:`desk_self_heal`: the audit module is kept incapable of
process launch or file mutation by an AST fence.  This thin actuator may only re-run the existing
producer task named by that audit.  It cannot promote, size, arm, edit a gate, or place an order.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import desk_self_heal as heal

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
REPORT = DESK / "reports" / "DESK_SELF_HEAL.json"
#: THE BOUND (principal 2026-11-19: restart stalled lanes "within bounds"). A task this actuator
#: re-runs is re-run at most once per RERUN_MIN_GAP_S and RERUN_MAX_PER_DAY times a day; past
#: that the fault is reported as unrepaired, because a re-run that has not cured it four times
#: is a code defect, and hammering the scheduler hides it.
RERUN_LEDGER = DESK / "data" / "self_heal_reruns.json"
RERUN_MIN_GAP_S = 2 * 3600
RERUN_MAX_PER_DAY = 4


def rerun_allowed(ledger: dict[str, Any], task: str, now: datetime) -> tuple[bool, str]:
    stamps = []
    for x in ledger.get(task) or []:
        try:
            t = datetime.fromisoformat(str(x))
        except ValueError:
            continue
        stamps.append(t if t.tzinfo else t.replace(tzinfo=UTC))
    day = [t for t in stamps if (now - t).total_seconds() < 86400]
    if len(day) >= RERUN_MAX_PER_DAY:
        return False, f"{task} re-run {len(day)}x in 24h (cap {RERUN_MAX_PER_DAY})"
    if day and (now - max(day)).total_seconds() < RERUN_MIN_GAP_S:
        return False, f"{task} re-run at {max(day).isoformat(timespec='seconds')}, inside the gap"
    return True, "due"


def _load_ledger(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(ledger, indent=1) + "\n", "utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


#: END+RUN (Audit 11-20 conditions): a research task whose lane is HUNG (output older than
#: HUNG_FACTOR x its limit) while the scheduler still reads it Running is ended with
#: `schtasks /End` on that task only -- never a pid or image kill -- and then run again. Same
#: bounds as a re-run; every End is logged under END_KEY in the ledger. A live task can never be
#: ended: research_task() refuses anything executor-, follower-, gateway-, release- or
#: account-shaped, and only built-in research tasks or research prefixes qualify.
END_KEY = "_ends"
END_SETTLE_S = 15


def _task_running(name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/Query", "/TN", name, "/FO", "CSV", "/NH"],
                              capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and '"Running"' in proc.stdout


def _end_task(name: str) -> bool:
    if not (heal.research_task(name) or heal.board_rerunnable(name)) or os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode == 0:
        import time
        time.sleep(END_SETTLE_S)
    return proc.returncode == 0


#: THE HOLDER AN END LEAVES BEHIND (Audit ruling 2026-11-25 12:17Z). `schtasks /End` ends the
#: process the scheduler started. A task whose action is `cmd /c ... python x.py` can leave the
#: python grandchild ALIVE and still holding its job lock -- box 11-24..25: MT5-MergeDocket's
#: merge_hypotheses.py (pid 16808) sat 17.5 h at 0.01 core with the lock, so every next run was
#: refused and the End+Run cured nothing. After an End, the lock's holder is terminated, with its
#: tree, ONLY when every proof holds:
#:   * the task is a research/ops lane (`_may_end`) and is NOT live-shaped (heal._LIVE_TASK);
#:   * the task names its lock here (no lock, nothing to reap);
#:   * BEFORE the End, the holder was alive, its create_time matched the lock row's (Windows
#:     reuses pids), and its parent's command line carried the task's own registered action;
#:   * AFTER the End, the same holder (same pid, same create_time) is still alive.
#: Any proof missing: nothing is killed and the guardian alerts Claude. Every reap is logged under
#: REAP_KEY and emitted as a PLUMBING_DEFECT (Claude's feed, never a phone).
TASK_LOCKS: dict[str, str] = {"MT5-MergeDocket": "merge_hypotheses"}
LOCK_DIR = Path("desks") / "mt5" / "data" / ".job_locks"
REAP_KEY = "_reaps"
REAP_WAIT_S = 10.0


def _norm(text: str) -> str:
    return " ".join(str(text).replace('"', " ").lower().split())


def _task_action(name: str) -> str | None:
    """The task's registered Command + Arguments, read off the scheduler; None off Windows."""
    if os.name != "nt":
        return None
    try:
        proc = subprocess.run(["schtasks", "/Query", "/TN", name, "/XML"], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    import re as _re
    cmd = _re.search(r"<Command>(.*?)</Command>", proc.stdout, _re.S)
    args = _re.search(r"<Arguments>(.*?)</Arguments>", proc.stdout, _re.S)
    if not cmd:
        return None
    import html as _html
    return _html.unescape(cmd.group(1) + " " + (args.group(1) if args else ""))


def _proc_info(pid: int) -> dict[str, Any] | None:
    try:
        import psutil
        p = psutil.Process(int(pid))
        info: dict[str, Any] = {"pid": int(pid), "create_time": float(p.create_time())}
        try:
            parent = p.parent()
            info["ppid"] = parent.pid if parent else None
            info["parent_cmdline"] = " ".join(parent.cmdline()) if parent else ""
        except Exception:
            info["ppid"], info["parent_cmdline"] = None, ""
        return info
    except Exception:
        return None


def _kill_tree(pid: int, create_time: float) -> bool:
    try:
        import psutil
        p = psutil.Process(int(pid))
        if abs(float(p.create_time()) - float(create_time)) > 2.0:
            return False
        procs = [*p.children(recursive=True), p]
        import contextlib
        for q in procs:
            with contextlib.suppress(psutil.NoSuchProcess):
                q.terminate()
        _, alive = psutil.wait_procs(procs, timeout=REAP_WAIT_S)
        for q in alive:
            with contextlib.suppress(psutil.NoSuchProcess):
                q.kill()
        return not psutil.pid_exists(int(pid)) or not p.is_running()
    except Exception:
        return False


def holder_before_end(root: Path, task: str, *, proc_info: Any = None,
                      task_action: Any = None) -> dict[str, Any]:
    """The proofs taken BEFORE the End. `ok` True only when the holder may be reaped after it."""
    lock = TASK_LOCKS.get(task)
    out: dict[str, Any] = {"task": task, "lock": lock, "ok": False}
    if not lock or heal._LIVE_TASK.search(task) or not _may_end(task):
        out["why"] = "no lock declared for this task" if not lock else "not a research/ops lane"
        return out
    try:
        row = json.loads((root / LOCK_DIR / f"{lock}.json").read_text("utf-8"))
    except (OSError, ValueError):
        out["why"] = "lock absent or unreadable: nothing holds it"
        return out
    pid, want = row.get("pid"), row.get("create_time")
    if not isinstance(pid, int) or not isinstance(want, (int, float)):
        out.update(why="lock row has no pid/create_time to prove the holder by", alert=True)
        return out
    info = (proc_info or _proc_info)(pid)
    if info is None:
        out["why"] = f"holder pid {pid} is not alive"
        return out
    if abs(float(info["create_time"]) - float(want)) > 2.0:
        out.update(why=f"pid {pid} was reused: it is not the lock's holder", alert=True)
        return out
    action = (task_action or _task_action)(task)
    if not action or _norm(action) not in _norm(info.get("parent_cmdline") or ""):
        out.update(why=f"holder pid {pid}'s parent is not {task}'s own action", alert=True)
        return out
    out.update(ok=True, pid=pid, create_time=float(want), ppid=info.get("ppid"),
               why="holder proven: same create_time, parent runs the task's action")
    return out


def reap_after_end(snap: dict[str, Any], *, proc_info: Any = None,
                   kill_tree: Any = None) -> dict[str, Any]:
    """After the End: terminate the proven holder's tree if (and only if) it survived."""
    row = {k: snap.get(k) for k in ("task", "lock", "pid", "create_time")}
    if not snap.get("ok"):
        return {**row, "reaped": False, "alert": bool(snap.get("alert")), "why": snap.get("why")}
    info = (proc_info or _proc_info)(int(snap["pid"]))
    if info is None:
        return {**row, "reaped": False, "alert": False, "why": "the End took the holder too"}
    if abs(float(info["create_time"]) - float(snap["create_time"])) > 2.0:
        return {**row, "reaped": False, "alert": True,
                "why": "pid reused between the proofs and the reap: nothing killed"}
    ok = bool((kill_tree or _kill_tree)(int(snap["pid"]), float(snap["create_time"])))
    return {**row, "reaped": ok, "alert": True,
            "why": "holder survived the End; its tree was terminated" if ok
            else "holder survived the End and could NOT be terminated"}


def _run_task(name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/Run", "/TN", name], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


#: A money-path organ still failing is paged again after this long (Audit should-fix: page on
#: change, not every pass; a day keeps a standing fault from going silent).
MONEYPATH_REPAGE_H = 24.0
#: A board task re-run this many times in 24h and still faulted is PAGED (principal 2026-11-25:
#: "End+Run, alert Claude if still bad after 2 tries"). The re-run bounds above still apply.
BOARD_GIVE_UP_RUNS = 2


def _may_end(task: str) -> bool:
    return heal.research_task(task) or heal.board_rerunnable(task)


def _runs_24h(ledger: dict[str, Any], task: str, now: datetime) -> int:
    n = 0
    for x in ledger.get(task) or []:
        try:
            t = datetime.fromisoformat(str(x))
        except ValueError:
            continue
        t = t if t.tzinfo else t.replace(tzinfo=UTC)
        n += (now - t).total_seconds() < 86400
    return n

def run(*, root: Path = ROOT, apply: bool = False,
        out: Path = REPORT, ledger_path: Path = RERUN_LEDGER,
        run_task: Any = None, now: datetime | None = None,
        task_running: Any = None, end_task: Any = None,
        measure_headroom: bool = True, run_pass: bool = True,
        before_end: Any = None, after_end: Any = None) -> dict[str, Any]:
    t_now = now or datetime.now(tz=UTC)
    # HEADROOM FIRST (principal 2026-11-25 02:49Z): measure + reclaim (disk only, evidence
    # compressed never deleted) so the invariants below read this pass's numbers. Never raises.
    headroom_err = None
    if measure_headroom:
        try:
            import box_headroom
            box_headroom.run(root, t_now, apply=apply)
        except Exception as exc:
            headroom_err = f"{type(exc).__name__}: {exc}"
    findings = heal.audit(root, t_now)
    ledger = _load_ledger(ledger_path)
    bounded: list[dict[str, str]] = []
    launch = run_task or _run_task
    is_running = task_running or _task_running
    end = end_task or _end_task
    ran_this_pass: set[str] = set()
    hung = {f.task for f in findings
            if not f.ok and f.hung and f.task and _may_end(f.task)}
    ended: list[dict[str, Any]] = []
    reaps: list[dict[str, Any]] = []

    def _bounded_run(task: str) -> bool:
        # Two faults owned by one task (cadence and judge stall both -> MT5-Gauntlet) are one run.
        if task in ran_this_pass:
            return True
        ok, why = rerun_allowed(ledger, task, t_now)
        if not ok:
            bounded.append({"task": task, "why": why})
            return False
        ran_this_pass.add(task)
        ledger[task] = [*[str(x) for x in (ledger.get(task) or [])][-10:],
                        t_now.isoformat(timespec="seconds")]
        if task in hung and _may_end(task) and is_running(task):
            snap = (before_end or (lambda t: holder_before_end(root, t)))(task)
            ok_end = bool(end(task))
            row = {"task": task, "at": t_now.isoformat(timespec="seconds"), "ended": ok_end}
            ended.append(row)
            ledger[END_KEY] = [*(ledger.get(END_KEY) or [])[-50:], row]
            if not ok_end:
                return False
            if snap.get("lock"):
                reap = {"at": t_now.isoformat(timespec="seconds"),
                        **(after_end or reap_after_end)(snap)}
                reaps.append(reap)
                ledger[REAP_KEY] = [*(ledger.get(REAP_KEY) or [])[-50:], reap]
        return bool(launch(task))

    remedies, escalations = heal.plan(findings, run_task=_bounded_run if apply else None)
    outcomes: list[tuple[str, bool]] = []
    if apply:
        for remedy in remedies:
            outcomes.append((remedy.action, bool(remedy.apply())))
        _save_ledger(ledger_path, ledger)
    doc = {
        "at": t_now.isoformat(timespec="seconds"),
        "status": "OK" if all(f.ok for f in findings) else "DEGRADED",
        "applied": apply,
        "findings": [{"check": f.check, "ok": f.ok, "detail": f.detail,
                      "fixable": f.fixable} for f in findings],
        "repairs": [{"action": action, "ok": ok} for action, ok in outcomes],
        "unrepaired": [{"check": f.check, "detail": f.detail} for f in escalations],
        "bounded": bounded,
        "ended": ended,
        "reaped": reaps,
        "bounds": {"min_gap_s": RERUN_MIN_GAP_S, "max_per_day": RERUN_MAX_PER_DAY},
        "boundary": ("research evidence producers may be re-run; promotion, capital, gates, "
                     "deadman state and orders are outside this actuator"),
    }
    # MONEYPATH_CRASH ALERTS (principal 2026-11-24 18:14Z): each failing money-path organ lands
    # on the event log as a PLUMBING_DEFECT with its root cause, the surface the alert relay to
    # Claude reads. Only on an applied pass, so a dry run never pages; the writer never raises.
    # THE BOARD PAGES TOO (2026-11-25): a board fault no re-run can cure (alert-only verdicts,
    # STALE_OUTPUT on a task we may not touch) pages at once; a re-runnable one pages once it
    # has had BOARD_GIVE_UP_RUNS re-runs in 24h and is still faulted.
    def _board_due(f: Any) -> bool:
        if f.ok or not f.check.startswith("board "):
            return False
        return (not f.fixable or not f.task
                or _runs_24h(ledger, f.task, t_now) >= BOARD_GIVE_UP_RUNS)
    alerts = [f for f in findings if not f.ok
              and (f.check.startswith(("moneypath ", "invariant ")) or _board_due(f))]
    _, census = heal.check_process_board(root, t_now)
    doc["board"] = census
    if headroom_err:
        doc["headroom_error"] = headroom_err
    doc["invariants"] = [{"invariant": f.check.split(" ", 1)[1], "holds": f.ok,
                          "detail": f.detail} for f in findings
                         if f.check.startswith("invariant ")]
    doc["moneypath_alerts"] = [{"organ": f.check, "detail": f.detail} for f in alerts]
    # PAGE ON CHANGE (Audit should-fix on 45d647ac7): an organ pages when it newly fails and again
    # every MONEYPATH_REPAGE_H while it stays failed -- never once per 15-minute pass. The
    # memory is the organs paged and when, beside the event log.
    seen_p = root / "desks" / "mt5" / "data" / "moneypath_alerts_paged.json"
    try:
        seen = json.loads(seen_p.read_text("utf-8"))
        seen = seen if isinstance(seen, dict) else {}
    except (OSError, ValueError):
        seen = {}
    due = []
    for f in alerts:
        try:
            last = datetime.fromisoformat(str(seen.get(f.check)))
        except ValueError:
            last = None
        if last is None or (t_now - last).total_seconds() >= MONEYPATH_REPAGE_H * 3600:
            due.append(f)
    doc["moneypath_paged"] = [f.check for f in due]
    if apply:
        paged = {f.check: seen[f.check] for f in alerts if f.check in seen}
        paged |= {f.check: t_now.isoformat() for f in due}
        try:
            seen_p.parent.mkdir(parents=True, exist_ok=True)
            seen_p.write_text(json.dumps(paged, indent=1), "utf-8")
        except OSError as exc:
            doc["moneypath_paged_error"] = f"{type(exc).__name__}: {exc}"
    if apply and due:
        try:
            import sys as _sys
            if str(root) not in _sys.path:
                _sys.path.insert(0, str(root))
            from libs.ops import events as _ev
            for f in due:
                defect = ("MONEYPATH_CRASH" if f.check.startswith("moneypath ")
                          and "board " not in f.check
                          else "INVARIANT_" + f.check.split(" ", 1)[1]
                          if f.check.startswith("invariant ")
                          else "BOARD_" + f.detail.split(":", 1)[0].strip())
                _ev.emit("PLUMBING_DEFECT", root / "desks" / "mt5" / "data" / "events.jsonl",
                     organ=f.check, defect=defect,
                         detail=f.detail[:600], producer="desk_self_heal", priority=2)
        except Exception as exc:  # the report still names every alert
            doc["moneypath_alert_error"] = f"{type(exc).__name__}: {exc}"
    # EVERY REAP, AND EVERY HOLDER THAT COULD NOT BE PROVEN, IS CLAUDE'S TO KNOW (Audit 11-25).
    loud = [r for r in reaps if r.get("alert")]
    if apply and loud:
        try:
            import sys as _sys
            if str(root) not in _sys.path:
                _sys.path.insert(0, str(root))
            from libs.ops import events as _ev
            for r in loud:
                _ev.emit("PLUMBING_DEFECT", root / "desks" / "mt5" / "data" / "events.jsonl",
                         organ=f"lock {r.get('lock')}",
                         defect="LOCK_HOLDER_REAPED" if r.get("reaped") else "LOCK_HOLDER_UNPROVEN",
                         detail=f"{r.get('task')}: pid {r.get('pid')}: {r.get('why')}"[:600],
                         producer="desk_self_heal", priority=2)
        except Exception as exc:
            doc["reap_alert_error"] = f"{type(exc).__name__}: {exc}"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, out)
    # THE HOURLY PASS ON THE BOX (principal 2026-11-25 03:11Z), last: it reads this report.
    # Read-only; on the real report path only, so a test's report never feeds the box pass.
    if run_pass and out == REPORT:
        try:
            import box_pass
            box_pass.run(root, t_now)
        except Exception as exc:
            doc["pass_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    doc = run(root=args.root, apply=args.apply, out=args.out)
    print(f"desk self-heal: {doc['status']}; repairs={len(doc['repairs'])}; "
          f"unrepaired={len(doc['unrepaired'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
