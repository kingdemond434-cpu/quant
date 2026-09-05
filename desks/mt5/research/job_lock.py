"""Cross-controller, cross-shell single-instance locks for heavy MT5 research writers."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCK_ROOT = BASE / "data" / ".job_locks"
STALE_SECONDS = 45 * 60

#: How long a job that does not fit will WAIT for a neighbour to exit before standing down.
#: Bounded well under the hourly trigger so a waiting job can never overlap its own next run.
ADMIT_PATIENCE_SECONDS = 12 * 60
ADMIT_RECHECK_SECONDS = 45

#: How many past runs of a job are kept when correcting its declared need. Enough to outlast one
#: unusually small docket, short enough that a job which genuinely got lighter is believed within
#: a few hours rather than being held to a peak it no longer reaches.
PEAK_HISTORY = 8


def peak_rss_mb() -> int | None:
    """This process's HIGH-WATER RSS, or None where the platform will not say.

    The high-water mark, not the current reading: a job that touched 4.9GB and released it still
    needed 4.9GB, and admitting the next one on the trough is how the box gets starved.
    """
    try:
        for line in Path("/proc/self/status").read_text("utf-8").splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        import resource
        # ru_maxrss is KB on Linux, bytes on macOS. Both are the high-water mark.
        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(kb // 1024) if kb > 1 << 20 else int(kb) // 1024 or None
    except Exception:
        return None


def _peaks_path(name: str) -> Path:
    return LOCK_ROOT / f"{name}.peaks.json"


def observed_peaks(name: str) -> list[int]:
    """What this job has actually used on its last runs, newest last."""
    try:
        rows = json.loads(_peaks_path(name).read_text("utf-8"))
        return [int(v) for v in rows if isinstance(v, (int, float)) and v > 0][-PEAK_HISTORY:]
    except (OSError, ValueError, TypeError):
        return []


def record_peak(name: str, mb: int) -> None:
    """Append one run's high-water RSS. Best effort: a ledger that cannot be written must never
    cost the run that was trying to write it."""
    try:
        LOCK_ROOT.mkdir(parents=True, exist_ok=True)
        rows = [*observed_peaks(name), int(mb)]
        _peaks_path(name).write_text(json.dumps(rows[-PEAK_HISTORY:]), encoding="utf-8")
    except (OSError, ValueError, TypeError):
        pass


def measured_need_mb(name: str, declared: int) -> tuple[int, str]:
    """The memory this job should be ADMITTED on: its declared figure, corrected upward by what
    it has actually used.

    WHY (measured 2026-09-05). `external_gauntlet` declared 1200MB -- a figure taken from a
    1926MB peak in August and never revisited -- and was found holding 4882MB on an 8GB box, ten
    minutes into a legitimate run. Admission passed on 1200MB of headroom and the process then
    grew to four times its declaration, leaving 280MB free, so `edge_search` (2000MB) and
    `orthogonal_sweep` (1250MB) could not start and their artifacts went 28 and 23 hours stale.
    The guard was not wrong; the number it was given was, and nothing measured that.

    The module's own rule was already written down beside the constant -- "tighten it from
    observed successful runs, never from another guess" -- and had no mechanism. This is the
    mechanism. It only ever raises: a declaration is a FLOOR, so a job cannot talk its way into
    a box that cannot hold it, and a job that has grown is held to what it grew to.

    CORRECTED 2026-09-05, same day, after the first version took the MAXIMUM and locked the
    gauntlet out of the box for a day. See the block below for why the statistic is p75.
    """
    peaks = observed_peaks(name)
    if not peaks:
        return declared, f"declared {declared}MB (no run measured yet)"

    # A HIGH QUANTILE, NOT THE MAXIMUM, AND THE CHANGE IS WHY THE GAUNTLET CAME BACK.
    #
    # `max()` made this ratchet one-way in the wrong direction. `external_gauntlet` touched
    # 4882MB once -- one pathological run on an unusually large docket -- and was thereafter
    # admitted on 4882MB. On an 8GB box that also runs the live MT5 terminal, that much free
    # memory essentially never exists, so the job stood down every single hour, waited its twelve
    # minutes, stood down again, and exited non-zero. Measured 2026-09-05 from the live desk
    # state: "FAILING MT5-Gauntlet: last result 1 twice in a row", no new certificates for a day,
    # and the same for MT5-QQuantGatesCertify. The guard built to stop one job starving the box
    # had starved that job out of the box permanently, and reported it as a crash.
    #
    # A single spike must not be able to do that. The 75th percentile of the recent window keeps
    # the property the ratchet was for -- a job that CONSISTENTLY grows is held to what it grew
    # to -- while a one-off ages out. Measured on this tree the same sweep peaks at 1619MB and
    # 1615MB, which is its real working set.
    #
    # p75 RATHER THAN THE MEDIAN, and the difference is the whole safety argument. A median
    # dismisses any minority, so a job that spikes one run in three -- which is not an outlier,
    # it is a bimodal job -- would be admitted on its small mode and thrash the box on its large
    # one. p75 only discards a spike once there is enough record to call it a spike: one heavy
    # run out of three still sets the bar, one out of eight does not.
    #
    # THE SAFETY PROPERTY IS UNCHANGED IN THE DIRECTION THAT MATTERS. `declared` is still a hard
    # FLOOR, so nothing can talk its way into a box that cannot hold it. And admission is only
    # the first of two layers: `external_gauntlet.MEMORY_BUDGET_MB` defers cells when the run
    # exceeds its budget mid-flight, so a job that DOES grow past the admitted figure throttles
    # itself rather than thrashing. Admitting on the worst case of BOTH layers was belt, braces
    # and a lock on the door -- and the lock was the one that jammed.
    #
    # THE OUTLIER IS REPORTED, NEVER HIDDEN. A max far above the admitted figure is the signal
    # somebody should see -- it means this job has a tail -- so it is named in the reason string.
    ordered = sorted(peaks)
    typical = ordered[min(len(ordered) - 1, int(0.75 * len(ordered)))]
    worst = ordered[-1]
    tail = f"; worst was {worst}MB" if worst > typical else ""
    if typical <= declared:
        return declared, (f"declared {declared}MB (p75 of {len(peaks)} runs: {typical}MB"
                          f"{tail})")
    return typical, (f"declared {declared}MB but the p75 of {len(peaks)} measured runs was "
                     f"{typical}MB -- admitting on what it typically uses{tail}")


def _owner_state(path: Path) -> str:
    """"DEAD", "ALIVE" or "UNKNOWN" for the process named in the lock.

    TRI-STATE ON PURPOSE. This used to answer only "is it dead", and the caller could therefore
    use liveness to ADD staleness but never to VETO it -- so a lock older than STALE_SECONDS was
    reclaimed even when its owner was demonstrably alive and working. With sweeps that legitimately
    run 60-90 minutes against a 45 minute timer, that is not an edge case: it GUARANTEES a
    duplicate. Measured 2026-08-28 -- two external_gauntlet processes at once (66 and 22 minutes),
    both sweeping, on an 8GB box that also runs the live terminal, saturating it so completely
    that ssh could not complete.

    A living owner is proof the job is not abandoned, which is the only thing the age rule was
    ever trying to guess at. Age remains the backstop for the cases liveness genuinely cannot
    answer: a lock written by another host, or an unreadable one.
    The original lesson still holds and is why liveness exists at all: a time-only rule makes
    live work wait on a corpse -- a killed ssh leaves an orphaned writer, or the box reboots
    mid-run, and the next 45 minutes of hourly attempts are refused by a lock nobody holds
    (measured 2026-08-27). Both directions are now covered: a corpse never blocks, and a living
    owner is never robbed.
    """
    try:
        row = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return "UNKNOWN"                  # unreadable: fall back to the age rule, never guess
    if str(row.get("host") or "") != socket.gethostname():
        return "UNKNOWN"                  # another machine's lock is not ours to judge
    pid = row.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return "UNKNOWN"
    try:
        os.kill(pid, 0)                   # signal 0: existence check, never delivers a signal
    except ProcessLookupError:
        return "DEAD"
    except PermissionError:
        return "ALIVE"                    # running under another user is still running
    except OSError as exc:
        # WINDOWS NEVER RAISES ProcessLookupError HERE, so on the box this whole function could
        # only ever return False and the liveness path -- the entire reason it exists -- was dead
        # code. MEASURED on the desk box (win32) 2026-08-27: `os.kill(<nonexistent pid>, 0)`
        # raises plain `OSError` with `winerror=87` (ERROR_INVALID_PARAMETER), errno 22, and a
        # LIVE pid raises nothing. So on Windows the age rule was the only recovery there has
        # ever been, and the docstring's promise -- that live work never waits 45 minutes on a
        # corpse -- was true on Linux and false where the searcher actually runs.
        # Narrow on purpose: only the documented not-a-process signature counts as dead. Any
        # other OSError is still UNKNOWN and falls back to the age rule, because reclaiming a
        # lock from a process that is merely unreachable would let two writers run at once, which
        # is worse than waiting.
        if sys.platform == "win32" and getattr(exc, "winerror", None) == 87:
            return "DEAD"
        return "UNKNOWN"
    return "ALIVE"


def free_mb() -> int | None:
    """The BINDING memory headroom -- min(available physical, available COMMIT) -- or None.

    COMMIT, NOT JUST PHYSICAL. This returned available physical memory only, and on this box that
    is the wrong number: measured 2026-08-29, the desk had 2,705MB of physical RAM free and
    234MB of virtual memory, because the page file was full at 12,756MB. Every guard built on
    this function therefore read "healthy" while the machine could not satisfy an allocation --
    the sweep died on `MemoryError` importing pandas, before a single line of its own code ran.
    Windows fails an allocation when COMMIT is exhausted regardless of how much RAM is free, so
    the commit limit is what admission must respect.

    The culprit was this desk's own cache warmer: three Pool workers, each a full re-import under
    Windows spawn, holding 12.9GB of commit between them with working sets of 8-23MB. Entirely
    paged out, doing nothing, and invisible to a physical-memory check.

    UNMEASURED is a real answer (L1.28a): if this cannot be determined, admission must not invent
    a number, and the caller admits the job rather than blocking work on ignorance.
    """
    if sys.platform == "win32":
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        try:
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return None
        except (AttributeError, OSError):
            return None
        # ullAvailPageFile is the process-visible COMMIT headroom; ullAvailPhys is RAM. The
        # smaller of the two is what an allocation actually has to fit inside.
        avail_phys = int(st.ullAvailPhys // (1024 * 1024))
        avail_commit = int(st.ullAvailPageFile // (1024 * 1024))
        return min(avail_phys, avail_commit)
    # Linux has no separate commit ceiling in the Windows sense; MemAvailable already accounts
    # for reclaimable memory, and swap is counted by the OOM killer rather than by admission.
    try:
        for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


@contextmanager
def exclusive_job(name: str, need_mb: int = 0) -> Iterator[bool]:
    """Yield True to one writer, False to duplicates OR when the box cannot fit this job.

    THE MEMORY PRECONDITION (2026-08-28). This desk box has 8GB and runs the LIVE MT5 terminal
    beside the miners. A per-name lock stops a job racing itself; it has nothing to say about
    edge_search and external_gauntlet colliding, and colliding is what they did -- measured that
    night at 0.3GB free, with the sweep alive 87 minutes at a trickle of CPU having produced
    nothing. A thrashing process still breathes, so every liveness check passed while the box
    made no progress at all. The same collision shows up three times as `oom-kill` in the unit
    death log, so this is a recurring class, not an incident.

    Starting a job that does not fit is strictly worse than not starting it: it destroys its own
    run, degrades every neighbour, and endangers the terminal that holds live positions. Standing
    down is cheap -- the trigger is hourly and the per-cell cache makes the next attempt resume
    rather than restart -- so refusal costs a delay while admission costs the hour AND the box.

    The refusal is LOUD and names the number, because a silent stand-down is indistinguishable
    from the crash it prevents, and this desk has been burned by exactly that ambiguity.
    """
    if need_mb > 0:
        need_mb, need_why = measured_need_mb(name, need_mb)
        if need_mb > 0:
            print(f"{name}: {need_why}")
        # MEDIAN OF THREE, NOT ONE SAMPLE. Free memory on this box is a sawtooth: the searcher
        # builds primitives for a symbol, peaks, emits, releases. Measured 2026-08-28, a single
        # reading said 55MB while readings seconds either side said 1,605MB -- and the backfill
        # stood down on the trough for a box that had ample room. One sample of a sawtooth is a
        # coin flip, and a job whose start depends on a coin flip is not scheduled, it is
        # gambled. Three readings across ~20 seconds outlast the trough; a genuinely starved box
        # reads low in all of them.
        def _median_free() -> int | None:
            readings = []
            for i in range(3):
                if i:
                    time.sleep(10)
                r = free_mb()
                if r is not None:
                    readings.append(r)
            return sorted(readings)[len(readings) // 2] if readings else None

        # WAIT FOR THE NEIGHBOUR, DO NOT ABANDON THE HOUR (2026-09-01). The refusal above was
        # right that a job which does not fit must not start; it was wrong to treat "not now" as
        # "not this hour". These jobs are not competing with a permanent condition, they are
        # competing with EACH OTHER: edge_search (~2000MB), orthogonal_sweep (~1250MB) and
        # external_gauntlet (~1200MB) cannot coexist on an 8GB box that also runs the live
        # terminal, but any ONE of them fits with room to spare. Measured 2026-08-31: 162
        # stand-downs in a day -- edge_search 67, external_gauntlet 62, orthogonal_sweep 33 --
        # while free memory sat at 2389MB minutes later, because whoever lost the race gave up
        # the whole trigger instead of waiting a few minutes for the winner to exit.
        #
        # So the loser now waits. Nothing about the safety property changes: a job still never
        # starts unless it fits, measured by the same median-of-three that outlasts the
        # sawtooth. What changes is that "does not fit right now" costs minutes instead of an
        # hour, which is the difference between a gauntlet that runs hourly and one that runs
        # whenever it happens to win a coin flip.
        avail = _median_free()
        if avail is not None and avail < need_mb:
            deadline = time.monotonic() + ADMIT_PATIENCE_SECONDS
            print(f"{name}: waiting for room -- needs ~{need_mb}MB, box has {avail}MB; "
                  f"holding up to {ADMIT_PATIENCE_SECONDS // 60}min for a neighbour to exit "
                  f"rather than giving up this trigger.")
            while time.monotonic() < deadline:
                time.sleep(ADMIT_RECHECK_SECONDS)
                avail = _median_free()
                if avail is None or avail >= need_mb:
                    print(f"{name}: room found ({avail}MB) -- starting.")
                    break
            else:
                avail = _median_free()
        if avail is not None and avail < need_mb:
            print(f"{name}: STOOD DOWN -- needs ~{need_mb}MB, box has {avail}MB available "
                  f"after waiting {ADMIT_PATIENCE_SECONDS // 60}min. "
                  f"Not started (a job that does not fit thrashes the box and the live "
                  f"terminal); the next scheduled trigger retries and the cache makes it resume.")
            yield False
            return
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    path = LOCK_ROOT / f"{name}.json"
    token = uuid.uuid4().hex
    payload = json.dumps({
        "token": token, "pid": os.getpid(), "host": socket.gethostname(),
        "started_at": datetime.now(UTC).isoformat(),
    })
    owned = False
    for _attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stale = datetime.now(UTC).timestamp() - path.stat().st_mtime > STALE_SECONDS
            except OSError:
                stale = False
            state = _owner_state(path)
            if state == "DEAD":
                print(f"{name}: reclaiming lock from dead owner (pid gone) -- {path}")
                stale = True
            elif state == "ALIVE" and stale:
                # LIVENESS VETOES AGE. The holder is running; the lock is not abandoned, it is
                # merely old. Reclaiming here is what produced two concurrent sweeps.
                print(f"{name}: lock is older than {STALE_SECONDS // 60}min but its owner is "
                      f"ALIVE -- not reclaiming; a long job is not an abandoned one")
                stale = False
            if stale:
                with suppress(OSError):
                    path.unlink()
                continue
            print(f"{name}: REFUSED duplicate writer; active lock {path}")
            yield False
            return
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            owned = True
            break
    if not owned:
        print(f"{name}: REFUSED writer; stale lock could not be recovered")
        yield False
        return
    try:
        yield True
    finally:
        # WHAT IT ACTUALLY USED, recorded before anything else, so the next admission is made on
        # measurement instead of on a comment. A job that overran its declaration says so.
        _hwm = peak_rss_mb()
        if _hwm:
            record_peak(name, _hwm)
            if need_mb and _hwm > need_mb:
                print(f"{name}: PEAK {_hwm}MB exceeded the {need_mb}MB it was admitted on -- "
                      f"the next run is admitted on {_hwm}MB")
        # Never delete a successor's lock after a stale-owner race.
        try:
            current = json.loads(path.read_text("utf-8"))
            if current.get("token") == token:
                path.unlink()
        except (OSError, ValueError, AttributeError):
            pass
