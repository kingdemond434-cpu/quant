#!/usr/bin/env python3
"""Standing sweep: kill desk-box research processes that outlived their supervisor.

WHY A CLOCK AND NOT ONLY A TRIGGER. Two reapers already exist and both are conditional:
`ops/run_external_pipeline.sh` reaps when a remote stage times out, and `scripts/auto_fixers.py`
reaps before it relaunches. Neither fires if the pipeline itself is killed, if a process is
orphaned by a route that goes through neither, or if the orphan predates the fix that would have
reaped it. MEASURED 2026-09-03: a 6.0 GB `external_gauntlet.py` from before the memory fix was
still resident hours later, the desk box had 215 MB free, `edge_search` (needs ~2000 MB) could
not start, and edge_search_results.json went 21.6 hours stale while orthogonal_candidates.json
went 9.3. One unswept process starved both legs of the search.

`timeout ... ssh` kills the SSH CLIENT, never the remote process, so this class recurs by
construction on every stage that overruns. A standing sweep is the only thing that bounds it.

WHAT IT WILL NEVER TOUCH. Only the named research scripts are eligible, and the match is on the
command line. The MT5 gateway, the forward engine, the moat recorder and the dashboard are not on
the list and cannot be caught by it -- a blanket python kill on this box would take the process
that holds live positions.

AGE IS THE ONLY OTHER TEST, and it is generous: every eligible job is bounded by a 25-minute
remote-stage timeout, so anything past the threshold below has already been declared dead by
whatever started it.

    python3 scripts/reap_desk_orphans.py [--minutes 60] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "contabo-mt5"
OUT = ROOT / "data" / "desk_orphan_reaper.json"

#: Research scripts that are bounded by a supervisor and may therefore be orphaned. NOTHING that
#: holds live positions or accrues forward evidence appears here, and nothing may be added to
#: this list without the same argument.
ELIGIBLE = ("external_gauntlet.py", "edge_search.py", "orthogonal_sweep.py")

#: Minutes past which an eligible process is an orphan rather than a long run. The remote-stage
#: timeout is 25 minutes, so 60 leaves more than double the headroom before anything is touched.
DEFAULT_MINUTES = 60

#: Job name -> script, for the lock lookup below. `exclusive_job(name)` writes
#: desks/mt5/data/.job_locks/<name>.json holding the pid that legitimately owns the job.
_LOCK_NAMES = {"external_gauntlet.py": "external_gauntlet",
               "edge_search.py": "edge_search",
               "orthogonal_sweep.py": "orthogonal_sweep"}

#: NO QUOTES OF ITS OWN, ON PURPOSE. This has to survive python -> ssh -> cmd.exe -> the remote
#: interpreter, and the first version used nested PowerShell quoting that cmd.exe ate: the command
#: returned nothing, `lock_holders()` read {} and the duplicate rule below could never fire --
#: a silent zero that looked exactly like "no locks held". Path segments and separators are built
#: from chr() so the payload contains no quote character at all and nothing can eat it.
_PS_LOCKS = (
    'py -3 -c "import os;'
    'p=os.path.join(chr(67)+chr(58),os.sep,'
    'chr(111)+chr(112)+chr(116),'                        # opt
    'chr(113)+chr(117)+chr(97)+chr(110)+chr(116),'       # quant
    'chr(100)+chr(101)+chr(115)+chr(107)+chr(115),'      # desks
    'chr(109)+chr(116)+chr(53),'                         # mt5
    'chr(100)+chr(97)+chr(116)+chr(97),'                 # data
    'chr(46)+chr(106)+chr(111)+chr(98)+chr(95)+chr(108)+chr(111)+chr(99)+chr(107)+chr(115));'
    'print(chr(10).join(f.rsplit(chr(46),1)[0]+chr(61)+open(os.path.join(p,f)).read() '
    'for f in os.listdir(p))) if os.path.isdir(p) else None"'
)


def lock_holders() -> dict[str, int]:
    """job name -> pid that holds its lock, for every lock currently on the box.

    A MISSING ANSWER IS NOT AN EMPTY ONE. If the locks cannot be read this returns {}, and the
    duplicate rule below simply does not fire -- it never guesses that a job is unlocked, because
    "no lock" and "could not read the lock" would then kill the legitimate holder.
    """
    out: dict[str, int] = {}
    rc, body_text = _ssh(_PS_LOCKS)
    if rc != 0:
        return out
    for line in body_text.splitlines():
        if "=" not in line:
            continue
        name, _, body = line.partition("=")
        try:
            pid = int(json.loads(body)["pid"])
        except (ValueError, KeyError, TypeError):
            continue
        out[name.strip()] = pid
    return out


#: ISO-8601 IS ASKED FOR EXPLICITLY. Win32_Process returns CreationDate as .NET
#: `/Date(1788008440823)/`, which no ISO parser reads -- the first version of this survey silently
#: failed to parse every row and reported the box as unsurveyable.
_PS = (
    "powershell -NoProfile -Command \""
    "Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | "
    "Select-Object ProcessId,WorkingSetSize,CommandLine,"
    "@{n='Started';e={$_.CreationDate.ToUniversalTime().ToString('o')}} "
    "| ConvertTo-Json -Compress\""
)


def _ssh(cmd: str, timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", REMOTE, cmd],
                           capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def survey() -> list[dict]:
    """Every python process on the desk box, or an empty list with the reason logged."""
    rc, out = _ssh(_PS)
    if rc != 0 or not out.strip():
        return []
    # Slice from whichever of [ or { comes FIRST. Looking for "{" in a list response starts the
    # slice inside the first element and produces invalid JSON.
    starts = [i for i in (out.find("["), out.find("{")) if i >= 0]
    if not starts:
        return []
    try:
        doc = json.loads(out[min(starts):])
    except ValueError:
        return []
    return [doc] if isinstance(doc, dict) else [d for d in doc if isinstance(d, dict)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = survey()
    now = datetime.now(tz=UTC)
    report: dict = {"checked_utc": now.isoformat(timespec="seconds"),
                    "threshold_minutes": args.minutes, "surveyed": len(rows),
                    "eligible_scripts": list(ELIGIBLE), "reaped": [], "spared": []}
    if not rows:
        # UNMEASURED, NOT CLEAN. A survey that failed is not a box with no orphans.
        report["error"] = "could not survey the desk box; nothing reaped"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
        print("desk orphan reaper: SURVEY FAILED -- nothing reaped (UNMEASURED, not clean)")
        return 2

    holders = lock_holders()
    report["lock_holders"] = dict(holders)
    for r in rows:
        cmd = str(r.get("CommandLine") or "")
        script = next((e for e in ELIGIBLE if e in cmd), None)
        if not script:
            continue
        raw = str(r.get("Started") or "")
        try:
            started = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            age_min = (now - started).total_seconds() / 60.0
        except ValueError:
            # An unreadable start time is not licence to kill: leave it and say so.
            report["spared"].append({"pid": r.get("ProcessId"), "script": script,
                                     "why": f"unreadable start time {raw!r}"})
            continue
        mb = round(float(r.get("WorkingSetSize") or 0) / 1048576.0)
        entry = {"pid": r.get("ProcessId"), "script": script,
                 "age_min": round(age_min, 1), "mb": mb}
        # A DUPLICATE IS A DUPLICATE AT ANY AGE. Age answers "was this abandoned"; it cannot
        # answer "should this be running at all", and that is the question that was costing the
        # desk its search. MEASURED 2026-09-03: TWO external_gauntlet.py processes ran at once
        # under two different invocations, holding 3.3GB between them on an 8GB box that also
        # runs the live terminal. Only one held the lock. Physical memory available fell to
        # 1,085MB, edge_search needs 2,000MB to be admitted, so it waited its twelve minutes and
        # stood down -- every hour, while both gauntlets thrashed. This reaper surveyed both,
        # found them inside the 60-minute window, and spared them: correct by its own rule and
        # useless against the actual defect.
        #
        # The lock settles it without guessing. exclusive_job names the pid that legitimately
        # owns the job; anyone else running that script slipped past admission and is a second
        # writer, which is the exact condition the lock exists to prevent. Killing the LOCK
        # HOLDER is never right, so it is spared explicitly rather than by accident.
        holder = holders.get(_LOCK_NAMES.get(script, ""))
        if holder is not None and int(r.get("ProcessId") or 0) != holder:
            if not args.dry_run:
                _ssh(f"powershell -NoProfile -Command \"Stop-Process -Id "
                     f"{r.get('ProcessId')} -Force\"")
            report["reaped"].append({**entry, "why": f"duplicate: {script} lock is held by "
                                                     f"pid {holder}, not this one"})
            continue
        if age_min < args.minutes:
            report["spared"].append({**entry, "why": "still inside its supervisor's window"})
            continue
        if not args.dry_run:
            _ssh(f"powershell -NoProfile -Command \"Stop-Process -Id {r.get('ProcessId')} -Force\"")
        report["reaped"].append(entry)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if report["reaped"]:
        freed = sum(x["mb"] for x in report["reaped"])
        print(f"desk orphan reaper: reaped {len(report['reaped'])} process(es), ~{freed} MB"
              + (" (dry run)" if args.dry_run else ""))
        for x in report["reaped"]:
            print(f"   pid {x['pid']} {x['script']} {x['age_min']:.0f}min {x['mb']}MB")
    else:
        print(f"desk orphan reaper: nothing older than {args.minutes}min "
              f"({len(report['spared'])} eligible process(es) still inside their window)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
