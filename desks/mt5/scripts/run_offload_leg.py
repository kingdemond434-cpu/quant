"""Run one hourly-cycle leg on its OWN scheduled task, so the serial pass stops starving it.

WHY THIS EXISTS (measured on the trading box 2026-11-04). `hourly_cycle.main()` is one serial
line of ~325 costed legs. The eleven ALWAYS_RUN legs alone cost 2,947 s against the rotation's
2,640 s budget (0.80 x the MT5-HourlyCore limit), so every one of the 151 rotating legs is
deferred and 16-18 of them have never run. Two of the casualties are on the promotion path:

  * `pf_allocator --mode heavy` writes the admission scan. It was 124 h old against a 3.5 h
    cadence and a 26 h consumer expiry, because its leg sits in the rotated "forward" department.
    Max-growth's 131 candidates waited on it.
  * `forward_enrolment` gives every fresh certificate its clock. Rotated out, "immediately"
    meant "whenever the rotation next reaches the validate department".

`record_tape` is ALWAYS_RUN (a tick not recorded is gone) and is the third leg that gets its own
clock: on its own task it runs every hour whatever the pass in front of it costs, and the pass
gets its seconds back.

THE SAME CODE THE CYCLE RUNS, NOT A COPY. Each leg calls exactly what `hourly_cycle` calls, with
the same arguments: `hourly_cycle.record_tape()` in-process, and the two producer scripts as
budgeted children under the tree-killing runner. The heavy allocator pass is stamped with
`hourly_cycle._stamp_heavy_pass`, so the cycle's own `_allocator_mode_for_the_hour` sees the
scan this task measured and does not schedule a second heavy pass for it.

STANDBY UNTIL THE CYCLE LETS GO (the overlap rule). `record_tape` and `forward_enrolment` have
no cross-process lock of their own: `tape.write_day` merges and rewrites a day file, and two
writers doing that at once can lose the slower one's rows. So while a leg is still run by the
cycle (not in `hourly_cycle.OWN_CLOCK_LEGS`), this runner does NOT run it. It writes a STANDBY
receipt and exits 0. That still proves the task fires, finds its interpreter and imports the
cycle, which is what the OWN_CLOCK_LEGS flip waits for. The flip, in its own later change, is
what moves the work. `pf_allocator` needs no such wait: every one of its clocks takes the one
`exclusive_job("pf_allocator")` lock (research/pf_allocator.py main), so a heavy pass here and
a pass anywhere else serialise. A held lock makes the allocator stand down by name.

A RECEIPT PER LEG, NEVER A SHARED FILE. Three tasks write at different minutes but can overlap,
so each writes `reports/offload/<leg>.json` alone: status RAN / STANDBY / FAILED / TIMEOUT,
exit code, seconds, and why. Absence of the file means the task never ran, which is UNMEASURED,
not healthy (L1.28a).

    python scripts/run_offload_leg.py forward_enrolment
    python scripts/run_offload_leg.py record_tape
    python scripts/run_offload_leg.py pf_allocator_heavy

Exit code: the leg's own exit code (0 on STANDBY), so the scheduler's Last Result is the alarm.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RECEIPTS = BASE / "reports" / "offload"

#: leg -> (the producer script and its arguments, exactly as hourly_cycle passes them, and the
#: child's timeout in seconds). `record_tape` is in-process, as in the cycle, so it has no script.
PRODUCERS: dict[str, tuple[tuple[str, ...], float]] = {
    "forward_enrolment": (("research/forward_enrolment.py", "--once", "--budget-s", "300"), 540.0),
    "pf_allocator_heavy": (("research/pf_allocator.py", "--mode", "heavy"), 2400.0),
}
#: Legs that must wait for the cycle to stop running them (no cross-process lock of their own).
NEEDS_HANDOVER: frozenset[str] = frozenset({"record_tape", "forward_enrolment"})
LEGS: tuple[str, ...] = ("forward_enrolment", "record_tape", "pf_allocator_heavy")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_receipt(leg: str, doc: dict[str, Any], out_dir: Path | None = None) -> Path:
    """Write this leg's receipt atomically (tmp + replace) and return its path."""
    out_dir = out_dir or RECEIPTS
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{leg}.json"
    tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def _cycle() -> Any:
    from research import hourly_cycle  # type: ignore[import-not-found]
    return hourly_cycle


def _run_producer(leg: str, runner: Callable[..., Any] | None = None) -> dict[str, Any]:
    args, timeout = PRODUCERS[leg]
    cmd = [sys.executable, "-u", "-W", "ignore", str(BASE / args[0]), *args[1:]]
    if runner is None:
        try:
            from libs.ops import proctree
            runner = proctree.run
        except Exception:
            runner = subprocess.run
    try:
        proc = runner(cmd, timeout=timeout, cwd=str(BASE))
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "exit_code": None,
                "why": f"{args[0]} ran past {timeout:.0f}s; its process tree was killed"}
    rc = int(proc.returncode)
    return {"status": "RAN" if rc == 0 else "FAILED", "exit_code": rc}


def run_leg(leg: str, cycle: Any = None, runner: Callable[..., Any] | None = None,
            out_dir: Path | None = None) -> dict[str, Any]:
    """Run `leg` once (or stand by), write its receipt, and return the receipt."""
    if leg not in LEGS:
        raise SystemExit(f"unknown leg {leg!r}; expected one of {', '.join(LEGS)}")
    started = datetime.now(UTC)
    t0 = time.monotonic()
    doc: dict[str, Any] = {"leg": leg, "started_utc": started.isoformat(timespec="seconds"),
                           "task_pid": os.getpid()}
    try:
        hc = cycle if cycle is not None else _cycle()
        if leg in NEEDS_HANDOVER and leg not in hc.OWN_CLOCK_LEGS:
            doc.update(status="STANDBY", exit_code=0,
                       why=(f"{leg} still runs inside the hourly cycle (not in OWN_CLOCK_LEGS); "
                            "running it here too could race the cycle's writer, so this task "
                            "only proves it fires until the OWN_CLOCK_LEGS change moves the work"))
        elif leg == "record_tape":
            res = hc.record_tape()
            rc = int(res.get("exit_code") if res.get("exit_code") is not None else 1)
            doc.update(status="RAN" if rc == 0 else "FAILED", exit_code=rc, result=res)
        else:
            doc.update(_run_producer(leg, runner))
            if leg == "pf_allocator_heavy":
                stamped = hc._stamp_heavy_pass({"exit_code": doc.get("exit_code")},
                                               started=started)
                doc["heavy_pass_stamped"] = bool(stamped)
    except Exception as exc:
        doc.update(status="FAILED", exit_code=1, why=f"{type(exc).__name__}: {exc}")
    doc["seconds"] = round(time.monotonic() - t0, 1)
    doc["finished_utc"] = _now()
    write_receipt(leg, doc, out_dir)
    print(f"offload {leg}: {doc['status']} exit={doc.get('exit_code')} "
          f"in {doc['seconds']}s", flush=True)
    return doc


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(f"usage: run_offload_leg.py {{{'|'.join(LEGS)}}}", file=sys.stderr)
        return 2
    doc = run_leg(argv[0])
    rc = doc.get("exit_code")
    return int(rc) if isinstance(rc, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
