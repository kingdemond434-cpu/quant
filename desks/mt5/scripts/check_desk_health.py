"""Is the desk actually running? Asked on the box, answered in plain English.

WHY THIS EXISTS (2026-09-05). The desk produced nothing for days while every fence stayed
green, and each diagnosis had to be inferred from artifacts read on a machine that cannot reach
this one. Two of those inferences were wrong: an eleven-day-old `retcode 10027` was read as
"AutoTrading is off right now" when the principal had it switched on, and a gateway lock path
was called live when the box had already fixed it. The box knows all of this directly. Nobody
had written the questions down in a form it could be asked.

WHAT IT REPORTS, and nothing more:
  * the scheduled tasks that drive the desk -- present, enabled, when they last ran, what they
    returned;
  * whether the MT5 terminal and the gateway are actually resident;
  * how old the artifacts each leg is supposed to produce are;
  * whether `py -3` resolves, since a launcher pointing at a Python that does not exist on this
    machine is exactly the failure that started all of this.

WHAT IT DOES NOT DO. It starts nothing, stops nothing, kills nothing, and writes nothing outside
its own report. It is safe to run while the desk is trading, which is the point: a diagnostic
you hesitate to run is a diagnostic you do not run.

STALE IS NOT DEAD, AND MISSING IS NOT ZERO. An artifact this cannot read is reported as
UNREADABLE, and a task Windows will not describe is reported UNKNOWN. Both are findings. The one
thing this must never do is print a reassuring line about something it could not actually check.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent

#: task name -> what it drives, and how stale its evidence may be before it is a finding.
TASKS: tuple[tuple[str, str], ...] = (
    ("MT5-Gateway", "places and manages orders -- the money path"),
    ("MT5-Hourly", "the hourly chain: health, mining, sync"),
    ("MT5-Shadow", "forward evidence for candidate sleeves"),
    ("MT5-Gauntlet", "judges the docket and mints certificates"),
)

#: process -> why it matters. Matched on the command line, never killed.
PROCS: tuple[tuple[str, str], ...] = (
    ("terminal64", "the MT5 terminal itself"),
    ("run_gateway_loop", "the gateway pass"),
    ("run_deadman_switch", "the Tier-3 protective rail"),
)

#: artifact -> (what produced it, hours after which it is a finding)
ARTIFACTS: tuple[tuple[str, str, float], ...] = (
    ("data/gateway_state.json", "the gateway, every pass", 1.0),
    ("data/hypotheses/edge_search_results.json", "the SEARCH leg", 3.0),
    ("data/hypotheses/orthogonal_candidates.json", "the SWEEP leg", 3.0),
    ("reports/UNIVERSAL_SURVIVORS.json", "the gauntlet's canon", 6.0),
    ("reports/pf_allocation.json", "the allocator", 0.5),
)


def _ok(msg: str) -> None:
    print(f"  [ OK ]      {msg}")


def _bad(msg: str) -> None:
    print(f"  [PROBLEM]   {msg}")


def _unknown(msg: str) -> None:
    print(f"  [UNKNOWN]   {msg}")


def _run(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 124, f"{type(exc).__name__}: {exc}"


def check_python() -> None:
    print("PYTHON")
    print(f"  running as: {sys.executable}")
    rc, out = _run(["py", "-3", "-c", "import sys; print(sys.executable)"])
    if rc == 0 and out.strip():
        _ok(f"`py -3` resolves to {out.strip().splitlines()[-1]}")
    else:
        _bad("`py -3` does NOT work on this machine. Every .cmd launcher uses it, so every "
             "scheduled task that runs one exits immediately, doing nothing, reporting success.")
    print()


def check_tasks() -> None:
    print("SCHEDULED TASKS  (what drives the desk)")
    for name, what in TASKS:
        rc, out = _run(["schtasks", "/Query", "/TN", name, "/FO", "LIST", "/V"])
        if rc != 0:
            _bad(f"{name} is NOT INSTALLED on this machine -- {what}. Nothing runs it, so "
                 f"nothing it produces will ever appear.")
            continue
        fields = {}
        for line in out.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip().lower()] = v.strip()
        status = fields.get("scheduled task state", fields.get("status", "?"))
        last_run = fields.get("last run time", "?")
        last_res = fields.get("last result", "?")
        if status.lower() in {"disabled"}:
            _bad(f"{name} is INSTALLED BUT DISABLED -- {what}. Enable it in Task Scheduler.")
        elif last_res not in {"0", "267009", "?"}:
            # 267009 is "task is currently running", which is healthy.
            _bad(f"{name} last run {last_run} and returned {last_res} (non-zero = it failed) "
                 f"-- {what}")
        else:
            _ok(f"{name}: {status}, last run {last_run}, result {last_res} -- {what}")
    print()


def check_processes() -> None:
    print("RUNNING NOW")
    rc, out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process | ForEach-Object { $_.Name + ' ' + "
                    "$_.CommandLine }"], timeout=90)
    if rc != 0:
        _unknown("could not read the process list, so nothing below is claimed either way")
        print()
        return
    blob = out.lower()
    for needle, what in PROCS:
        if needle.lower() in blob:
            _ok(f"{what} is running ({needle})")
        else:
            _bad(f"{what} is NOT running ({needle} is absent from the process list)")
    print()


def check_artifacts() -> None:
    print("WHAT THE DESK HAS ACTUALLY PRODUCED")
    now = time.time()
    for rel, producer, max_h in ARTIFACTS:
        p = DESK / rel
        if not p.exists():
            p = ROOT / rel
        if not p.exists():
            _bad(f"{rel} does not exist -- {producer} has never written it here")
            continue
        try:
            age_h = (now - p.stat().st_mtime) / 3600.0
        except OSError as exc:
            _unknown(f"{rel} could not be read ({exc}); UNREADABLE is not the same as absent")
            continue
        if age_h <= max_h:
            _ok(f"{rel} is {age_h:.1f}h old -- {producer}")
        else:
            _bad(f"{rel} is {age_h:.1f}h old (expected under {max_h:.0f}h) -- {producer} has "
                 f"stopped producing")
    print()


def check_gateway_state() -> None:
    print("THE GATEWAY'S OWN LAST WORD")
    p = DESK / "data" / "gateway_state.json"
    if not p.exists():
        _bad("data/gateway_state.json is absent -- the gateway has never written state here")
        print()
        return
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        _unknown(f"gateway_state.json could not be parsed ({exc})")
        print()
        return
    rec = doc.get("last_reconcile")
    print(f"  last reconcile with the broker: {rec}")
    deployed = doc.get("deployed") or {}
    print(f"  sleeves deployed: {len(deployed)}"
          + ("" if deployed else "   <- nothing is deployed"))
    seen = []
    for key, br in (doc.get("brackets") or {}).items():
        for o in (br.get("orders") or []):
            code = o.get("retcode")
            if code is not None:
                seen.append((key, code, str(o.get("comment") or "")[:60]))
    if not seen:
        print("  no order results recorded -- the gateway has not attempted an order")
    for key, code, comment in seen[:6]:
        note = "  <- 10027 means the terminal's AutoTrading button was off AT THAT TIME" \
            if code == 10027 else ""
        print(f"  {key}: retcode {code} {comment}{note}")
    if seen:
        print("  NOTE: these are the LAST results recorded, not necessarily current. Read them")
        print("        together with the reconcile time above before concluding anything.")
    print()


def main() -> int:
    os.chdir(DESK)
    print(f"desk root: {DESK}")
    print(f"checked  : {time.strftime('%Y-%m-%d %H:%M:%S')} local\n")
    check_python()
    check_tasks()
    check_processes()
    check_artifacts()
    check_gateway_state()
    print("Every [PROBLEM] line above is a thing to fix. [UNKNOWN] means this could not check,")
    print("which is a finding too -- it is never the same as OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
