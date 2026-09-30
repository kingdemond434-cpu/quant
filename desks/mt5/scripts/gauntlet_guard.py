"""THE JUDGE'S ENVIRONMENT, MEASURED -- and it changes nothing the judge does.

`scripts/external_gauntlet.py` is SEALED. This organ never touches it, never starts it and never
stops it. It measures the three things that decided whether a pass reached its epilogue, and
publishes them as `reports/GAUNTLET_PASSES.json` so "the judge finishes now" is a reading rather
than an impression.

WHAT KILLED PASSES, measured 2026-09-24 over the whole 844 MB of MT5-Gauntlet.log: 212 passes
reached pre-warm, 163 reached `Saved to`, and only 117 reached the survivor write. Of 168
recorded tracebacks:

    77  concurrent.futures.process.BrokenProcessPool  (a pool worker died at spawn)
    23  OSError: handle is closed                      (the same pool, tearing down)
    19  pyarrow ArrowInvalid: magic bytes / 0 bytes    (a universe frame read mid-rewrite)
    17  MemoryError
    12  ImportError: DLL load failed ... the paging file is too small

The first two, the fourth and the fifth are ONE fault: `CommitPeak == CommitLimit` exactly
(245.95 GB = 96 GB RAM + 150 GB page file). At the ceiling any allocation fails, and the
allocation that fails first is a freshly spawned pool worker importing numpy -- which breaks the
pool and takes the whole sweep with it. The third is a separate fault and is now fixed at the
writer (`mt5desk.universe_registry.publish_frame`).

So this organ measures, every pass: commit headroom and whether the ceiling was touched, the
integrity of every frame the judge will read, and how close the live pass is to its window.

THE THREE NUMBERS THAT MATTER, and why each is here rather than inferred:
  * `margin_s`    -- window seconds left when the pass ended. A pass that finishes with four
                     seconds to spare is lucky, not fixed, and only a distribution shows which.
  * `commit_peak_gb_during_pass` -- the box's closest approach to the ceiling while this pass
                     ran. This is "how close the judge came to being killed", in the units that
                     actually kill it.
  * `torn_frames` -- universe frames that were unreadable at check time. Must stay 0.

WHAT A STOPPED PASS COSTS, and the honest limit of what can be fixed from outside. The judge's
per-cell BUILD is durable: `cache_save` writes each cell's series pair through a temp file and
`os.replace`, so a killed pass keeps every cell it built and the next pass loads them. The
judge's VERDICTS are not: `_save_build_cursor`, `_save_seen_cells`, `_append_gate_ledger`,
`universal_gates_external.json` and `UNIVERSAL_SURVIVORS.json` are all written in one tail after
`run_gauntlet` returns. Making a verdict durable per cell means writing inside `run_gauntlet`,
which is inside the sealed file. THIS ORGAN DOES NOT DO THAT AND MUST NOT. What it does instead
is measure the tail's width (`judged_cells` against `survivors_written`) so the cost of a stop is
a published number, and remove the causes of the stop at the writer and the box.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPORTS = BASE / "reports"
UNIVERSE = BASE / "data" / "universe"
LOG = BASE / "logs" / "MT5-Gauntlet.log"
OUT = REPORTS / "GAUNTLET_PASSES.json"

#: MT5-Gauntlet's `Stop Task If Runs X Hours and X Mins`, in seconds. The fallback is the value
#: read off the box on 2026-09-24; `judging_throughput` owns the task and may lengthen it, so the
#: live task is asked first and this is only what an unreadable task falls back to.
WINDOW_S_FALLBACK = 4 * 3600

#: How many passes the report keeps. A distribution needs more than the last one.
KEEP_PASSES = 60

#: The judge's own script name, as it appears in the command line of its process.
JUDGE = "external_gauntlet.py"


# --------------------------------------------------------------------------- commit
class _PerfInfo(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong)] + [
        (n, ctypes.c_size_t)
        for n in ("CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal",
                  "PhysicalAvailable", "SystemCache", "KernelTotal", "KernelPaged",
                  "KernelNonpaged", "PageSize")
    ] + [("HandleCount", ctypes.c_ulong), ("ProcessCount", ctypes.c_ulong),
         ("ThreadCount", ctypes.c_ulong)]


def commit_info() -> dict:
    """Commit charge, limit and all-time peak in GB -- the units the judge dies in.

    UNMEASURED where the call is unavailable (this is a Windows counter), never a zero: a zero
    here would read as "infinite headroom", which is the opposite of the truth it replaced.
    """
    if sys.platform != "win32":
        return {"status": "UNMEASURED", "why": "GetPerformanceInfo is a Windows counter"}
    try:
        pi = _PerfInfo()
        pi.cb = ctypes.sizeof(_PerfInfo)
        if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb):
            return {"status": "UNMEASURED", "why": "GetPerformanceInfo returned false"}
        g = float(pi.PageSize) / 1024 ** 3
        total, limit, peak = pi.CommitTotal * g, pi.CommitLimit * g, pi.CommitPeak * g
        return {
            "status": "MEASURED",
            "commit_total_gb": round(total, 2),
            "commit_limit_gb": round(limit, 2),
            "commit_peak_gb": round(peak, 2),
            "headroom_gb": round(limit - total, 2),
            "peak_headroom_gb": round(limit - peak, 2),
            # The exact equality is the diagnosis, not a near-miss: at the ceiling a spawning
            # worker's DLL load fails and the pool breaks.
            "peak_touched_ceiling": bool(pi.CommitPeak >= pi.CommitLimit),
            "processes": int(pi.ProcessCount),
            "threads": int(pi.ThreadCount),
        }
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- inputs
def frame_integrity(root: Path | None = None) -> dict:
    """Every universe frame the judge may read, checked for the torn-read signature.

    A parquet file begins and ends with the four bytes `PAR1`. A frame caught mid-rewrite has
    neither, and the sealed `_bars_for` raises on it and kills the sweep. Eight bytes per file
    over ~1,700 files is a few milliseconds and it is the difference between a named bad frame
    and a dead pass with a pyarrow traceback.
    """
    root = root or UNIVERSE
    torn: list[str] = []
    checked = 0
    if not root.is_dir():
        return {"status": "UNMEASURED", "why": f"{root} is not a directory"}
    for path in sorted(root.glob("*.parquet")):
        checked += 1
        try:
            size = path.stat().st_size
            if size < 12:
                torn.append(f"{path.name}:{size}B")
                continue
            with path.open("rb") as fh:
                head = fh.read(4)
                fh.seek(-4, os.SEEK_END)
                tail = fh.read(4)
            if head != b"PAR1" or tail != b"PAR1":
                torn.append(path.name)
        except OSError as exc:
            torn.append(f"{path.name}:{type(exc).__name__}")
    return {"status": "MEASURED", "checked": checked, "torn": torn, "n_torn": len(torn)}


# --------------------------------------------------------------------------- live pass
def window_s() -> int:
    """MT5-Gauntlet's execution time limit in seconds, from the task itself where it can be read."""
    try:
        import re
        import subprocess
        xml = subprocess.run(["schtasks", "/query", "/tn", "MT5-Gauntlet", "/xml"],
                             capture_output=True, text=True, timeout=120).stdout
        m = re.search(r"<ExecutionTimeLimit>PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", xml)
        if m:
            h, mi, s = (int(x or 0) for x in m.groups())
            got = h * 3600 + mi * 60 + s
            if got > 0:
                return got
    except Exception:
        pass
    return WINDOW_S_FALLBACK


def live_pass() -> dict:
    """The judge process right now: age, memory, workers, and seconds left in its window."""
    try:
        import psutil
    except ImportError:
        return {"status": "UNMEASURED", "why": "psutil not importable"}
    win = window_s()
    now = time.time()
    judge = None
    workers = 0
    for proc in psutil.process_iter(["pid", "ppid", "name", "cmdline", "create_time",
                                     "memory_info"]):
        try:
            cmd = " ".join(proc.info["cmdline"] or [])
        except Exception:
            continue
        if JUDGE in cmd and "--only" not in cmd:
            judge = proc
    if judge is None:
        return {"status": "NO_PASS_RUNNING", "window_s": win}
    try:
        info = judge.info
        for proc in psutil.process_iter(["ppid"]):
            try:
                if proc.info["ppid"] == info["pid"]:
                    workers += 1
            except Exception:
                continue
        mem = info["memory_info"]
        age = now - info["create_time"]
        return {
            "status": "RUNNING",
            "pid": int(info["pid"]),
            "started_at": datetime.fromtimestamp(info["create_time"], UTC).isoformat(),
            "age_s": round(age),
            "window_s": win,
            "margin_s": round(win - age),
            "margin_frac": round(max(0.0, win - age) / win, 3) if win else None,
            "rss_mb": round((mem.rss if mem else 0) / 1024 ** 2),
            "private_mb": round(getattr(mem, "private", 0) / 1024 ** 2) if mem else None,
            "workers": workers,
        }
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- pass ledger
#: The judge's own phase prints, in the order one pass emits them. The list is the grammar the
#: reader below parses; a marker the judge stops printing simply stops appearing, which shows up
#: as a phase that never closes rather than as a wrong number.
MARKERS: tuple[tuple[str, str], ...] = (
    ("PRE-WARM:", "prewarm"),
    ("Cell cache:", "cache"),
    ("BUILD BUDGET reached", "build_budget"),
    ("  seen-cells: +", "seen"),
    ("Saved to ", "saved_report"),
    ("Updated UNIVERSAL_SURVIVORS.json", "survivors"),
    ("SURVIVORS_LEDGER.json:", "ledger"),
    ("Traceback (most recent call last)", "traceback"),
    ("No candidates advanced", "no_candidates"),
)


def classify(line: str) -> str | None:
    """Which phase marker this log line is, or None. Pure -- the whole reader is tested on it."""
    for prefix, name in MARKERS:
        if line.startswith(prefix):
            return name
    return None


def read_new_events(cursor: int) -> tuple[list[dict], int]:
    """Phase markers appended to the judge's log since `cursor`, and the new cursor.

    NEVER READS THE WHOLE LOG. It is 844 MB and grows by ~16 MB per pass; a reader that started
    at byte zero every ten minutes would cost more than the thing it measures. A cursor past the
    end of the file (the log was rotated) restarts from the end, which loses the passes in
    between -- recorded as `rotated`, because a silent reset is how a counter starts lying.
    """
    if not LOG.exists():
        return [], 0
    size = LOG.stat().st_size
    if cursor > size:
        return [{"phase": "rotated", "text": f"log shrank {cursor} -> {size}"}], size
    if cursor <= 0:
        cursor = max(0, size - 2_000_000)
    events: list[dict] = []
    with LOG.open("rb") as fh:
        fh.seek(cursor)
        if cursor:
            fh.readline()          # never start mid-line
        for raw in fh:
            line = raw.decode("utf-8", "replace").rstrip()
            phase = classify(line)
            if phase:
                events.append({"phase": phase, "text": line[:220]})
        return events, fh.tell()


def fold(events: list[dict], passes: list[dict], seen_at: str) -> list[dict]:
    """Fold new markers into the pass list. A pass CLOSES on `ledger` (complete) or on the next
    `prewarm` / a `traceback` (died). An open pass stays open and is reported as open."""
    out = list(passes)
    for ev in events:
        phase, text = ev["phase"], ev["text"]
        cur = out[-1] if out and out[-1].get("outcome") == "OPEN" else None
        if phase == "prewarm":
            if cur is not None:
                cur["outcome"] = "DIED_BEFORE_EPILOGUE"
                cur["closed_at"] = seen_at
            out.append({"opened_at": seen_at, "outcome": "OPEN", "phases": [],
                        "prewarm": text[:200]})
            cur = out[-1]
        if cur is None:
            continue
        cur["phases"].append(phase)
        if phase == "seen":
            cur["seen_line"] = text[:160]
        elif phase == "survivors":
            cur["survivors_line"] = text[:160]
        elif phase == "traceback":
            cur["outcome"] = "DIED_BEFORE_EPILOGUE"
            cur["closed_at"] = seen_at
        elif phase == "ledger":
            cur["outcome"] = "REACHED_EPILOGUE"
            cur["closed_at"] = seen_at
            cur["ledger_line"] = text[:160]
    return out[-KEEP_PASSES:]


def _atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    del argv
    now = datetime.now(UTC).isoformat(timespec="seconds")
    prior: dict = {}
    if OUT.exists():
        try:
            prior = json.loads(OUT.read_text("utf-8"))
        except (OSError, ValueError):
            prior = {}

    events, cursor = read_new_events(int(prior.get("log_cursor") or 0))
    passes = fold(events, list(prior.get("passes") or []), now)
    commit = commit_info()
    frames = frame_integrity()
    live = live_pass()

    # The closest approach to the ceiling while the CURRENT pass has been running: the guard sees
    # the box every ten minutes, so this is a floor on the true peak, never an upper bound.
    watch = dict(prior.get("live_watch") or {})
    if live.get("status") == "RUNNING":
        if watch.get("pid") != live.get("pid"):
            watch = {"pid": live.get("pid"), "started_at": live.get("started_at"),
                     "min_headroom_gb": commit.get("headroom_gb"),
                     "max_rss_mb": live.get("rss_mb"), "observations": 0}
        watch["observations"] = int(watch.get("observations") or 0) + 1
        for key, val, better in (("min_headroom_gb", commit.get("headroom_gb"), min),
                                 ("max_rss_mb", live.get("rss_mb"), max)):
            if val is not None:
                watch[key] = val if watch.get(key) is None else better(watch[key], val)
        watch["last_margin_s"] = live.get("margin_s")

    closed = [p for p in passes if p.get("outcome") != "OPEN"]
    reached = [p for p in closed if p["outcome"] == "REACHED_EPILOGUE"]
    doc = {
        "generated_at": now,
        "note": ("Measured environment around the SEALED judge. This organ starts nothing, "
                 "stops nothing and writes no certificate."),
        "log_cursor": cursor,
        "commit": commit,
        "frame_integrity": frames,
        "live_pass": live,
        "live_watch": watch,
        "passes_recorded": len(passes),
        "passes_closed": len(closed),
        "passes_reached_epilogue": len(reached),
        "reach_rate": round(len(reached) / len(closed), 3) if closed else None,
        # THE STOP COST, published rather than assumed. The judge's cell BUILD is durable per cell
        # (content-addressed cache, temp + os.replace); its VERDICTS become durable only in the
        # tail after run_gauntlet returns. So this is the count a stop discards.
        "stop_cost": {
            "durable_per_cell": "cell series cache (external_gauntlet.cache_save)",
            "lost_on_stop": ("every gate verdict of the running pass: build cursor, seen-cells, "
                             "gate ledger rows, universal_gates_external.json and any survivor"),
            "why_not_fixed_here": ("per-cell verdict durability requires writing inside "
                                   "run_gauntlet, which is in the SEALED file. Not attempted."),
        },
        "passes": passes,
    }
    _atomic(OUT, doc)
    print(f"gauntlet_guard: {len(reached)}/{len(closed)} closed passes reached the epilogue; "
          f"commit headroom {commit.get('headroom_gb')}GB "
          f"(peak touched ceiling: {commit.get('peak_touched_ceiling')}); "
          f"torn frames {frames.get('n_torn')}; live {live.get('status')} "
          f"margin {live.get('margin_s')}s -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
