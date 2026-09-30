"""WHAT MUST COME BACK AFTER A RESTART OF THE BOX THAT TRADES -- captured, then verified.

THE CHANGE THIS EXISTS FOR. `GetPerformanceInfo` reports `CommitPeak == CommitLimit ==
245.95 GB` exactly (96 GB RAM + a 150 GB system-managed page file on C:). At the commit ceiling
the first allocation to fail is a freshly spawned pool worker importing numpy, which breaks the
sealed judge's `ProcessPoolExecutor` and discards the whole pass: 77 `BrokenProcessPool`, 23
`OSError: handle is closed`, 17 `MemoryError` and 12 `ImportError: DLL load failed ... the paging
file is too small` -- 129 of 168 recorded pass deaths (77%). C: has 911 GB free, so the ceiling
is raisable, and raising it is the single biggest lever on certificate production.

WHY A RESTART IS REQUIRED, measured rather than assumed. The no-restart path is adding a page
file to ANOTHER volume. This box has one: `mountvol` lists C:\\ plus two volumes, one of which
reports the same 1.2 TB / 917.5 GB free as C: (it IS C:'s GUID) and the other is an unformatted
system partition. `PagingFiles` is `?:\\pagefile.sys` -- system-managed on the boot volume -- and
switching that to an explicit larger size takes effect at boot. So there is nothing to add live.

THE REASON THIS FILE EXISTS RATHER THAN A CHECKLIST IN A COMMIT MESSAGE. A reboot means
terminal64.exe, the gateway resident, every department resident and every scheduled task must
come back unaided, and if ONE does not, the desk goes quiet in a way no dashboard shows -- which
is the failure mode this desk keeps rediscovering. A hand-written list of "what should be
running" is a guess about a machine nobody re-read. So the inventory is MEASURED while the box is
healthy (`--capture`) and compared after (`--verify`), and anything that did not return is named.

    python scripts/check_after_reboot.py --capture   # BEFORE, while the box is healthy
    python scripts/check_after_reboot.py --verify    # AFTER, names whatever did not return

Exit code 1 from --verify means something did not come back. It never starts or stops anything:
naming the gap is this organ's whole job, and repairing the gateway is the gateway owner's.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPORTS = BASE / "reports"
BASELINE = REPORTS / "REBOOT_BASELINE.json"
VERDICT = REPORTS / "REBOOT_VERIFY.json"
#: The artifact the component registry reads as this organ's proof of running.
REPORT = VERDICT

#: Long-lived processes identified by a fragment of their command line. A resident that is
#: restarted by its own keep-alive trigger still has to APPEAR, so absence is reportable either
#: way; this list is only the seed, and `--capture` adds whatever else is actually running.
SEED_PROCESSES: frozenset[str] = frozenset({
    "terminal64.exe",
    "gateway_resident.py",
    "department_resident.py",
    "external_gauntlet.py",
})

#: How long a process must already have been alive to count as something that MUST come back.
#:
#: MEASURED THE FIRST TIME THIS RAN: the baseline captured `check_blueprint_coverage.py` and
#: `data_vitals.py` -- two hourly legs that happened to be mid-run -- and the verify forty seconds
#: later reported them as having failed to return, on a box that had not restarted. A verifier
#: that cries wolf on a healthy box is worse than none, because the one time it matters nobody
#: reads it. A leg that runs for a minute an hour is not an inventory item; a resident is.
MIN_AGE_S = 300.0

#: Task name prefixes the desk owns. Everything matching is captured; nothing is filtered by
#: hand, because a task nobody listed is exactly the one that will not come back.
TASK_PREFIXES: tuple[str, ...] = ("MT5-", "E8-", "quant")


def commit_info() -> dict:
    """Commit charge and limit -- the number the restart exists to raise."""
    if sys.platform != "win32":
        return {"status": "UNMEASURED", "why": "GetPerformanceInfo is a Windows counter"}

    class _PI(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong)] + [
            (n, ctypes.c_size_t) for n in
            ("CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable",
             "SystemCache", "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize")
        ] + [("HandleCount", ctypes.c_ulong), ("ProcessCount", ctypes.c_ulong),
             ("ThreadCount", ctypes.c_ulong)]

    try:
        pi = _PI()
        pi.cb = ctypes.sizeof(_PI)
        if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb):
            return {"status": "UNMEASURED", "why": "GetPerformanceInfo returned false"}
        g = float(pi.PageSize) / 1024 ** 3
        return {"status": "MEASURED",
                "commit_limit_gb": round(pi.CommitLimit * g, 2),
                "commit_total_gb": round(pi.CommitTotal * g, 2),
                "commit_peak_gb": round(pi.CommitPeak * g, 2),
                "peak_touched_ceiling": bool(pi.CommitPeak >= pi.CommitLimit)}
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def running_processes() -> dict[str, dict]:
    """Every desk-relevant process now alive, keyed by the fragment that identifies it."""
    out: dict[str, dict] = {}
    try:
        import psutil
    except ImportError:
        return {"__status__": {"status": "UNMEASURED", "why": "psutil not importable"}}
    seen: dict[str, int] = {}
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            info = proc.info
            name = (info["name"] or "")
            cmd = " ".join(info["cmdline"] or [])
        except Exception:
            continue
        key = None
        if name.lower() == "terminal64.exe":
            key = "terminal64.exe"
        else:
            m = re.search(r"([A-Za-z0-9_]+\.py)", cmd)
            if m and "opt\\quant" in cmd.replace("/", "\\"):
                key = m.group(1)
        if not key:
            continue
        age = time.time() - float(info["create_time"] or 0)
        if age < MIN_AGE_S and key not in SEED_PROCESSES:
            continue
        seen[key] = seen.get(key, 0) + 1
        prev = out.get(key)
        if prev is None or info["create_time"] < prev["started_epoch"]:
            out[key] = {"pid": int(info["pid"]), "started_epoch": float(info["create_time"]),
                        "started_at": datetime.fromtimestamp(info["create_time"],
                                                             UTC).isoformat(timespec="seconds")}
    for key, n in seen.items():
        out[key]["instances"] = n
    return out


def scheduled_tasks() -> dict[str, dict]:
    """The desk's scheduled tasks with their state -- from schtasks, which needs no CIM.

    CIM IS NOT USED ANYWHERE IN THIS FILE. `Get-CimInstance` has hung on this box and `wmic` is
    absent; a verification organ that can hang is not a verification organ.
    """
    try:
        raw = subprocess.run(["schtasks", "/query", "/fo", "LIST", "/v"],
                             capture_output=True, text=True, timeout=600).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return {"__status__": {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}}
    out: dict[str, dict] = {}
    for block in re.split(r"\r?\n\r?\n", raw):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip()] = v.strip()
        name = fields.get("TaskName", "")
        short = name.lstrip("\\")
        if not short or not short.startswith(TASK_PREFIXES):
            continue
        out[short] = {"status": fields.get("Status", ""),
                      "last_run": fields.get("Last Run Time", ""),
                      "last_result": fields.get("Last Result", ""),
                      "next_run": fields.get("Next Run Time", "")}
    return out


def snapshot() -> dict:
    return {"at": datetime.now(UTC).isoformat(timespec="seconds"),
            "boot_epoch": _boot_epoch(),
            "commit": commit_info(),
            "processes": running_processes(),
            "tasks": scheduled_tasks()}


def _boot_epoch() -> float | None:
    try:
        import psutil
        return float(psutil.boot_time())
    except Exception:
        return None


def compare(base: dict, now: dict) -> dict:
    """What did NOT come back. Absence is the finding; a new arrival is noted, never a failure."""
    missing_p = sorted(k for k in (base.get("processes") or {})
                       if not str(k).startswith("__") and k not in (now.get("processes") or {}))
    b_tasks, n_tasks = base.get("tasks") or {}, now.get("tasks") or {}
    missing_t = sorted(k for k in b_tasks if not str(k).startswith("__") and k not in n_tasks)
    # A task that exists but is Disabled came back in name only, which is not coming back.
    disabled = sorted(k for k, v in n_tasks.items()
                      if not str(k).startswith("__")
                      and str(v.get("status", "")).lower().startswith("disabled")
                      and not str((b_tasks.get(k) or {}).get("status", "")).lower()
                      .startswith("disabled"))
    b_lim = ((base.get("commit") or {}).get("commit_limit_gb"))
    n_lim = ((now.get("commit") or {}).get("commit_limit_gb"))
    rebooted = None
    if base.get("boot_epoch") and now.get("boot_epoch"):
        rebooted = now["boot_epoch"] > base["boot_epoch"] + 1
    ok = not missing_p and not missing_t and not disabled
    return {
        "at": now["at"],
        "rebooted_since_capture": rebooted,
        "commit_limit_before_gb": b_lim,
        "commit_limit_after_gb": n_lim,
        "commit_limit_rose": (None if b_lim is None or n_lim is None else n_lim > b_lim + 0.5),
        "processes_missing": missing_p,
        "tasks_missing": missing_t,
        "tasks_newly_disabled": disabled,
        "processes_returned": sorted(k for k in (base.get("processes") or {})
                                     if not str(k).startswith("__")
                                     and k in (now.get("processes") or {})),
        "verdict": "EVERYTHING RETURNED" if ok else "SOMETHING DID NOT RETURN",
        "ok": ok,
    }


def _atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--capture", action="store_true",
                    help="record the healthy inventory BEFORE the restart")
    ap.add_argument("--verify", action="store_true",
                    help="compare the live box against that inventory AFTER the restart")
    a = ap.parse_args(argv)
    if a.capture == a.verify:
        ap.error("choose exactly one of --capture / --verify")

    if a.capture:
        snap = snapshot()
        _atomic(BASELINE, snap)
        print(f"captured {len(snap['processes'])} process kind(s) and {len(snap['tasks'])} "
              f"task(s); commit limit "
              f"{(snap['commit'] or {}).get('commit_limit_gb')}GB -> {BASELINE}")
        return 0

    try:
        base = json.loads(BASELINE.read_text("utf-8"))
    except (OSError, ValueError):
        print(f"REFUSING to verify: no readable baseline at {BASELINE}. Run --capture on a "
              f"healthy box first; verifying against nothing is not a verification.")
        return 2
    out = compare(base, snapshot())
    _atomic(VERDICT, out)
    print(f"{out['verdict']}  (rebooted_since_capture={out['rebooted_since_capture']}, "
          f"commit limit {out['commit_limit_before_gb']}GB -> {out['commit_limit_after_gb']}GB, "
          f"rose={out['commit_limit_rose']})")
    for label, rows in (("PROCESS DID NOT RETURN", out["processes_missing"]),
                        ("TASK DID NOT RETURN", out["tasks_missing"]),
                        ("TASK CAME BACK DISABLED", out["tasks_newly_disabled"])):
        for r in rows:
            print(f"  {label}: {r}")
    print(f"-> {VERDICT}")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
