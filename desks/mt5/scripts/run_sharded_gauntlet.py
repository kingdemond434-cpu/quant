"""Launch the canonical judge through its existing fail-closed shard protocol.

The sealed judge owns every statistical decision.  This launcher only supplies the
parallel dispatcher that ``external_gauntlet.run_sharded`` deliberately exposes.
Each planned cell is assigned by the judge's own stable partition, returned once,
and merged by the judge before any authority artifact is written.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _path in (str(ROOT), str(DESK)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from libs.ops import proctree  # noqa: E402


def _shards() -> int:
    """Read the measured shard count, falling closed to the serial judge."""
    try:
        return max(1, int(os.environ.get("GAUNTLET_SHARDS", "1")))
    except (TypeError, ValueError):
        return 1


def _retry_attempts() -> int:
    """Retries after the parallel attempt; invalid values fall closed to two."""
    try:
        return max(0, int(os.environ.get("GAUNTLET_SHARD_RETRIES", "2")))
    except (TypeError, ValueError):
        return 2


#: Where each shard child records its own peak memory, per phase, so the next wave is sized from
#: what a shard MEASURED on this machine and never from a claim (CLAUDE.md: measure the box).
SHARD_PEAKS = DESK / "data" / "judge_shard_peaks.json"
#: The share of available memory a wave may plan to hold at its children's measured peaks. Half,
#: as `judging_throughput.HEADROOM_SHARE` and the sealed judge's own headroom share.
SHARD_HEADROOM_SHARE = 0.5
#: Peaks kept per phase; the wave is sized at the largest of them, never an average.
SHARD_PEAK_HISTORY = 30


def _shard_peak_mb(phase: str | None) -> float | None:
    """The largest recorded shard peak (MB) for this phase, or None when never measured."""
    try:
        doc = json.loads(SHARD_PEAKS.read_text("utf-8"))
        rows = [float(v) for v in (doc.get(str(phase)) or []) if float(v) > 0]
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    return max(rows) if rows else None


def _available_mb() -> float | None:
    try:
        import psutil
        return float(psutil.virtual_memory().available) / (1024.0 * 1024.0)
    except Exception:
        return None


def _parallelism(n: int, phase: str | None = None) -> int:
    """Bound the first wave so judge children do not exhaust committed memory.

    Two concurrent shards is the production-safe default measured after a 15-wide wave caused
    fourteen child failures.  Operators may raise the cap after measuring peak committed memory;
    malformed configuration falls closed to one child.

    THE CAP IS NOW MEASURED WHEN NOBODY SET IT (2026-10-13). Two shards of fifteen meant the rule
    phase -- loading every cached pair, both cost arms, CPCV, walk-forward -- ran on two cores of
    an 18-core box for most of every sweep: the "1-2 effective cores" the box reported. Each shard
    child now records its own peak (`SHARD_PEAKS`), and an unset cap becomes
    floor(available x SHARD_HEADROOM_SHARE / largest recorded peak for the phase), clamped to
    [1, n]. Nothing measured yet, or psutil absent: the historic 2, exactly as before. An explicit
    GAUNTLET_SHARD_CONCURRENCY still wins, so an operator cap is never overridden.
    """
    raw = os.environ.get("GAUNTLET_SHARD_CONCURRENCY")
    if raw is None:
        configured = 2
        peak, avail = _shard_peak_mb(phase), _available_mb()
        if peak and avail:
            configured = max(1, int((avail * SHARD_HEADROOM_SHARE) // peak))
    else:
        try:
            configured = int(raw)
        except (TypeError, ValueError):
            configured = 1
    return max(1, min(n, configured))


def _record_peaks(logs: Path, invocation: str, phase: str) -> None:
    """Fold this wave's per-child peak receipts into `SHARD_PEAKS` (bounded history per phase)."""
    peaks: list[float] = []
    for f in logs.glob(f"{invocation}-{phase}-*.peak.json"):
        try:
            peaks.append(float(json.loads(f.read_text("utf-8"))["peak_mb"]))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not peaks:
        return
    try:
        doc = json.loads(SHARD_PEAKS.read_text("utf-8"))
        if not isinstance(doc, dict):
            doc = {}
    except (OSError, ValueError):
        doc = {}
    rows = [*(doc.get(phase) or []), *peaks][-SHARD_PEAK_HISTORY:]
    doc[phase] = [round(v, 1) for v in rows]
    doc["updated_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        SHARD_PEAKS.parent.mkdir(parents=True, exist_ok=True)
        tmp = SHARD_PEAKS.with_name(f"{SHARD_PEAKS.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, SHARD_PEAKS)
    except OSError:
        pass  # a missed receipt costs one wave at the old cap, never a verdict


# ----------------------------------------------------------------- the --once watchdog's state
#: A SWEEP THAT NEVER ENDS, SEEN FROM INSIDE IT (2026-10-20). Measured from the resident's own
#: published heartbeats: on the five sweeps of 10-15..10-17 the single-process merge-and-publish
#: took 4,340-6,108 s. The sweep that entered it on 10-18 01:03Z was still there when its resident
#: stopped beating sixteen hours later, and pid 7324 entered it on 10-20 01:44Z and was still in it
#: fourteen hours later, at 7-16 GB, while JUDGE_RESIDENT.json read SWEEPING with a fresh
#: heartbeat. The resident's only ceiling was derived from `longest_sweep_s` (61,110.9 s, one
#: 17 h sweep, times three) and so sat at its 48 h cap: a sweep could stall for two days and every
#: artifact the desk publishes would call it healthy.
#:
#: So the --once child now watches itself, and its thresholds are PER PHASE and PER SHARD, sized
#: from what each phase measured -- never one sum that a single slow sweep inflates for good:
#:   * every shard child's tree is sampled while it runs (`_watched_run`);
#:   * every phase has a threshold, the run has one, and the shards have one -- all AMBER;
#:   * a heartbeat with the progress counts is written at least every minute while the run holds
#:     the certification lane;
#:   * on a no-progress breach: the stall artifact names the shard / phase and the last progress,
#:     every descendant is killed (frozen first, so a respawn cannot orphan one, and any survivor
#:     named), the merge's authority files are restored if a kill tore them, the run's own job
#:     locks are released, and the process exits STALL_RC so the next trigger starts fresh.
#: Nothing is ever marked judged by any of this: the sealed protocol deletes every `shard_*.pkl`
#: when the next plan is written and fails the merge closed on a missing or stale one, so an
#: unfinished shard's cells are simply planned again.
#:
#: SLOW IS NOT STUCK -- THE PREMISE ABOVE WAS WRONG (audit HOLD of 2832cebd1, 2026-10-20). pid 7324
#: FINISHED rc 0 at 10-20 15:57:45Z after a 64,711 s sweep whose merge took 51,198 s; the judge
#: was slow, not hung. The first cut of this watchdog seeded the merge deadline at 6,108 s x 3 =
#: 18,324 s and would have killed that healthy sweep nine hours before it published. So:
#:   * the phase, run and shard ceilings are SLOW THRESHOLDS: past one, an amber SLOW record is
#:     written (once per phase / shard / run) and the sweep KEEPS GOING;
#:   * the ONLY kill rule is NO PROGRESS: the whole process tree (or one shard's tree) burned under
#:     NO_PROGRESS_CORES for NO_PROGRESS_S, measured per process with psutil. Progress that cannot
#:     be measured never kills -- it is UNMEASURED, and the thresholds still write SLOW;
#:   * every kill, and every sweep found dead, is a missed-growth line on GAUNTLET_STALL.json
#:     (`missed_growth`), carried into MISSED_GROWTH.json by `research/missed_growth.py`.
HEARTBEAT = DESK / "reports" / "GAUNTLET_HEARTBEAT.json"
STALL = DESK / "reports" / "GAUNTLET_STALL.json"
#: Measured phase / shard / sweep wall seconds of SUCCESSFUL sweeps (bounded history).
PHASE_TIMES = DESK / "data" / "judge_phase_times.json"
#: THE SEED, the floor under this box's own history (`max(history, seed)`, never `or`): the
#: largest wall each phase took in the resident's published history on live (JUDGE_RESIDENT.json,
#: 677c8e58b). Merge: 4,340..6,108 s on 10-15..10-17, then 51,198 s for pid 7324 (10-20 01:44:27Z
#: -> 15:57:45Z). Sweep: 64,711.4 s (`longest_sweep_s`), the same pid.
MEASURED_PHASE_S: dict[str, float] = {
    "plan": 10705.9, "build_shards": 42781.5, "collect_and_cut": 1235.2,
    "rule_shards": 819.3, "merge_and_publish": 51198.0}
#: The longest successful sweep the resident has measured (JUDGE_RESIDENT.json, pid 7324).
MEASURED_SWEEP_S = 64711.4
PHASE_DEADLINE_MULT = 3.0
PHASE_DEADLINE_FLOOR_S = 3600.0
SHARD_TIMEOUT_MULT = 3.0
SHARD_TIMEOUT_FLOOR_S = 1800.0
RUN_DEADLINE_MULT = 2.0
RUN_DEADLINE_FLOOR_S = 4 * 3600.0
#: The tree burned under this many cores in every heartbeat interval for this long: stalled.
NO_PROGRESS_S = 1800.0
NO_PROGRESS_CORES = 0.02
#: ...AND moved under this many bytes of real I/O per second (psutil io_counters, read + write,
#: where the platform exposes them). Heartbeat-sized writes are a few KB a beat, far under it.
NO_PROGRESS_IO_BPS = 65536.0
NO_PROGRESS_CAP_S = 4 * 3600.0
#: A RUNNING heartbeat older than this is a wedged watchdog: the resident and the next run act.
HEARTBEAT_STALE_S = 600.0
WATCHDOG_BEAT_S = 30.0
PHASE_TIME_HISTORY = 30
STALL_HISTORY = 20
#: The resident already counts this code as a hung sweep (and widens its window on a repeat).
STALL_RC = 124
#: The job locks a sweep holds (`external_gauntlet.run_sharded`), released when it is killed.
SWEEP_LOCKS = ("certification_lane", "external_gauntlet")
#: A command line holding any of these may own a sweep lock, so a lock whose pid now names one is
#: NEVER reclaimed: `certifier_launcher.py` takes `certification_lane` too, and the hourly
#: cycle's `external_gauntlet` leg takes both. Reclaiming from one of them would make two writers.
CERTIFIER_MARKERS = ("run_sharded_gauntlet", "external_gauntlet", "certifier_launcher",
                     "qquant_gates", "hourly_cycle")
#: A reused pid is one whose process was born this long AFTER the lock was stamped. Wide, so a
#: wall clock stepped back (NTP, a VM resume) can never make a lock's own writer look reused; the
#: certifier cmdline check above is the guard that does not depend on the clock at all.
REUSED_PID_MARGIN_S = 300.0
#: How often a shard child's tree is sampled while it runs.
SHARD_POLL_S = 5.0
#: The most `_kill_tree` spends re-enumerating a respawning tree before naming the survivors.
KILL_WALL_S = 60.0
#: A takeover never kills on the heartbeat alone: it measures the prior sweep's tree for this
#: long first, and kills only if that live sample is idle too.
TAKEOVER_SAMPLE_S = 60.0
#: The sealed merge's two authority files, copied aside when the merge starts; a kill mid-write
#: restores them if they no longer parse. (`reports/` is gitignored, so the copy never ships.)
MERGE_OUTPUTS = (DESK / "reports" / "universal_gates_external.json",
                 DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
MERGE_SNAPSHOT = DESK / "reports" / ".judge_merge_snapshot"
MISSED_GROWTH_HISTORY = 50
#: What the sealed judge's plan resume did this sweep (written by `external_gauntlet._resume_plan`
#: and `_run_shards` beside the plan, in the judge's SHARD_DIR, as PLAN_RESUME_NAME; stamped with
#: the sweep's pid): the cells it set aside and the wall it saved.
PLAN_RESUME = DESK / "reports" / "gauntlet_cache" / "shards" / "plan_resume.json"

#: Shard progress for the heartbeat, written by `dispatch` and read by the watchdog thread.
_PROGRESS: dict[str, Any] = {}
_PROGRESS_LOCK = threading.Lock()
#: Set by the watchdog before it kills the tree, so `dispatch` starts no new shard meanwhile.
_ABORT = threading.Event()


class ShardStalled(RuntimeError):
    """A shard child's tree made no measured progress for its whole window and was killed."""

    def __init__(self, phase: str, k: int, idle_s: float, kill: dict[str, Any] | None = None,
                 why: str = "no_progress") -> None:
        super().__init__(phase, k, idle_s, why)
        self.phase, self.k, self.idle_s, self.kill, self.why = phase, k, idle_s, kill or {}, why

    def __str__(self) -> str:                 # read at use: `dispatch` names the shard after
        return (f"{self.phase} shard {self.k} made no measured progress for {self.idle_s:.0f}s "
                f"({self.why}); killed with its process tree")


class _TreeProgress:
    """When a process tree last made progress, from per-process CPU deltas.

    PER PROCESS, so a child that exits (taking its CPU total with it) never reads as a negative
    or as progress, and a new process counts everything it has burned. `measured` stays False
    until one sample has arrived: unmeasured progress is never a reason to kill.
    """

    def __init__(self, now: float, cores: float | None = None,
                 max_gap_s: float | None = None) -> None:
        self.started = now
        self.last_progress = now
        self.cores = NO_PROGRESS_CORES if cores is None else cores
        #: An interval longer than this (a VM pause, a suspended host, a starved sampler) is
        #: never judged: it becomes a fresh baseline, so one long gap cannot read as idleness.
        self.max_gap_s = max_gap_s
        self.measured = False
        self.gaps = 0
        self._cpu: dict[int, float] = {}
        self._io: dict[int, float] = {}
        self._last_t: float | None = None

    def update(self, sample: dict[str, Any] | None, now: float) -> bool | None:
        """True / False = progressing or not over the interval; None = not judged (no sample,
        or a gap longer than `max_gap_s`, which restarts the idle clock from `now`)."""
        if sample is None:
            return None
        cpu = sample.get("cpu") or {}
        io = sample.get("io") or {}
        dt = now - (self._last_t if self._last_t is not None else self.started)
        if self.max_gap_s is not None and dt > self.max_gap_s:
            self.gaps += 1
            self.measured = True
            self.last_progress = now
            self._cpu, self._io, self._last_t = dict(cpu), dict(io), now
            return None
        self.measured = True
        delta = sum(max(0.0, v - self._cpu.get(p, 0.0)) for p, v in cpu.items())
        io_delta = sum(max(0.0, v - self._io.get(p, 0.0)) for p, v in io.items())
        # PROGRESS IS CPU OR I/O (audit of 7cf2ece90): a process blocked on a disk it is
        # streaming through burns little CPU and is still working. Heartbeat-sized writes stay
        # under NO_PROGRESS_IO_BPS, so the watchdog's own beat never reads as work.
        progressing = (dt <= 0 or delta / dt >= self.cores
                       or (bool(io) and io_delta / dt >= NO_PROGRESS_IO_BPS))
        if progressing:
            self.last_progress = now
        self._cpu, self._io, self._last_t = dict(cpu), dict(io), now
        return progressing

    def idle_s(self, now: float) -> float:
        return max(0.0, now - self.last_progress)


def _env_seconds(name: str) -> float | None:
    """A positive number of seconds from the environment, or None (derive instead)."""
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None       # 0 / negative cannot switch a ceiling off: derive it


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write_json_atomic(path: Path, doc: dict[str, Any]) -> None:
    """Write-then-rename that also works on Windows when the destination is read-only.

    `os.replace` onto a read-only file is legal on POSIX and raises WinError 5 on Windows
    (CLAUDE.md, the frontier port). The read-only bit is cleared and the rename retried, and as a
    last resort the file is written in place. A report is never worth an exception.
    """
    import stat

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError:
        return
    try:
        os.replace(tmp, path)
        return
    except PermissionError:
        with contextlib.suppress(OSError):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        with contextlib.suppress(OSError):
            os.replace(tmp, path)
            return
    except OSError:
        pass
    with contextlib.suppress(OSError):
        path.write_text(tmp.read_text("utf-8"), encoding="utf-8")
    with contextlib.suppress(OSError):
        tmp.unlink()


def consecutive_stalls() -> int:
    try:
        return max(0, int(_read_json(STALL).get("consecutive") or 0))
    except (TypeError, ValueError):
        return 0


def _widen(seconds: float, consecutive: int, cap: float | None = None) -> float:
    """A SLOW SWEEP MUST STILL FINISH (audit of #350): each consecutive stall doubles a ceiling,
    up to the cap, so a deterministic long phase widens its own window instead of dying at the
    same mark forever. Every one of those kills is still a named, RED stall."""
    top = RESIDENT_HANG_CAP_S if cap is None else cap
    return float(min(top, seconds * (2.0 ** max(0, min(int(consecutive), 16)))))


def _history_max(rows: object) -> float | None:
    vals: list[float] = []
    for v in rows if isinstance(rows, list) else []:
        with contextlib.suppress(TypeError, ValueError):
            if float(v) > 0:
                vals.append(float(v))
    return max(vals) if vals else None


def _at_least_seed(history: float | None, seed: float) -> float:
    """`max(history, seed)`. `history or seed` dropped the seed after ONE sample (audit of
    2832cebd1): a single fast merge would have pulled the threshold under the 51,198 s merge the
    box measured. The seed is the floor; this box's own history can only raise it."""
    return max(float(history or 0.0), float(seed))


def phase_deadline_s(phase: str | None, consecutive: int | None = None,
                     times: dict[str, Any] | None = None) -> float | None:
    """A phase's SLOW threshold: 3x its longest measured wall (max of this box's history and the
    seed), never under an hour. Past it the sweep is SLOW (amber) and KEEPS GOING; it is never a
    kill. GAUNTLET_PHASE_DEADLINE_S overrides every phase; the closing `done` has none.
    """
    if not phase or phase == "done":
        return None
    c = consecutive_stalls() if consecutive is None else consecutive
    forced = _env_seconds("GAUNTLET_PHASE_DEADLINE_S")
    if forced is not None:
        return _widen(forced, c)
    doc = times if times is not None else _read_json(PHASE_TIMES)
    seed = MEASURED_PHASE_S.get(phase) or max(MEASURED_PHASE_S.values())
    longest = _at_least_seed(_history_max((doc.get("phases") or {}).get(phase)), seed)
    return _widen(max(PHASE_DEADLINE_FLOOR_S, PHASE_DEADLINE_MULT * longest), c)


def shard_timeout_s(phase: str, consecutive: int | None = None,
                    times: dict[str, Any] | None = None) -> float:
    """One shard child's SLOW threshold (never a kill): 3x the longest shard this box measured
    for the phase, never under 30 minutes and never under the longest whole WAVE measured for the
    phase (history or seed, whichever is larger) -- a shard has never needed longer than its
    entire wave, so a wave's wall is the floor, not the fallback."""
    c = consecutive_stalls() if consecutive is None else consecutive
    forced = _env_seconds("GAUNTLET_SHARD_TIMEOUT_S")
    if forced is not None:
        return _widen(forced, c)
    doc = times if times is not None else _read_json(PHASE_TIMES)
    seed = MEASURED_PHASE_S.get(f"{phase}_shards") or max(MEASURED_PHASE_S.values())
    wave = _at_least_seed(_history_max((doc.get("phases") or {}).get(f"{phase}_shards")), seed)
    shard = _history_max((doc.get("shards") or {}).get(phase))
    base = max(SHARD_TIMEOUT_FLOOR_S, wave, SHARD_TIMEOUT_MULT * (shard or 0.0))
    return _widen(base, c)


def run_deadline_s(consecutive: int | None = None, times: dict[str, Any] | None = None) -> float:
    """The whole --once run's SLOW threshold: twice the longest successful sweep (max of history
    and the 64,711 s seed), never under 4 h. Amber past it, never a kill."""
    c = consecutive_stalls() if consecutive is None else consecutive
    forced = _env_seconds("GAUNTLET_RUN_DEADLINE_S")
    if forced is not None:
        return _widen(forced, c)
    doc = times if times is not None else _read_json(PHASE_TIMES)
    longest = _at_least_seed(_history_max(doc.get("sweeps")), MEASURED_SWEEP_S)
    return _widen(max(RUN_DEADLINE_FLOOR_S, RUN_DEADLINE_MULT * longest), c)


def no_progress_s(consecutive: int | None = None) -> float:
    c = consecutive_stalls() if consecutive is None else consecutive
    forced = _env_seconds("GAUNTLET_NO_PROGRESS_S")
    return _widen(forced if forced is not None else NO_PROGRESS_S, c, cap=NO_PROGRESS_CAP_S)


def _record_phase_times(phases: dict[str, Any] | None = None, sweep_s: float | None = None,
                        shard_walls: dict[str, list[float]] | None = None) -> None:
    """Fold a SUCCESSFUL sweep's phase walls (or a wave's shard walls) into PHASE_TIMES."""
    doc = _read_json(PHASE_TIMES)
    ph = doc.get("phases") if isinstance(doc.get("phases"), dict) else {}
    sh = doc.get("shards") if isinstance(doc.get("shards"), dict) else {}
    assert isinstance(ph, dict) and isinstance(sh, dict)
    for name, secs in (phases or {}).items():
        with contextlib.suppress(TypeError, ValueError):
            ph[name] = [*(ph.get(name) or []), round(float(secs), 1)][-PHASE_TIME_HISTORY:]
    for name, walls in (shard_walls or {}).items():
        if walls:
            sh[name] = [*(sh.get(name) or []), *(round(float(w), 1) for w in walls)
                        ][-PHASE_TIME_HISTORY:]
    sweeps = list(doc.get("sweeps") or [])
    if sweep_s is not None:
        sweeps = [*sweeps, round(float(sweep_s), 1)][-PHASE_TIME_HISTORY:]
    _write_json_atomic(PHASE_TIMES, {"phases": ph, "shards": sh, "sweeps": sweeps,
                                     "updated_utc": datetime.now(UTC).isoformat(
                                         timespec="seconds")})


def _progress_set(**kw: Any) -> None:
    with _PROGRESS_LOCK:
        _PROGRESS.update(kw)


def _progress_bump(key: str, by: int = 1) -> None:
    with _PROGRESS_LOCK:
        _PROGRESS[key] = int(_PROGRESS.get(key) or 0) + by


def _progress_snapshot() -> dict[str, Any]:
    with _PROGRESS_LOCK:
        return dict(_PROGRESS)


def _own_elapsed_s() -> float | None:
    t0 = _PHASE_DOC.get("_t0")
    return round(time.time() - t0, 1) if isinstance(t0, float) else None


def _missed_growth_line(reason: str, lost_s: float | None, why: str) -> dict[str, Any]:
    """One missed-growth line in `forward_slot_ranker`'s shape. The rail register is sealed
    (`libs/portfolio/rails.py`), so the line is PUBLISHED on this organ's own artifact and carried
    by `research/missed_growth.py`, never appended to data/missed_growth.jsonl. The wall a kill
    threw away is measured; what it cost in E[log W] is not, so the value is UNMEASURED."""
    now = datetime.now(UTC)
    return {"day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
            "rail": "gauntlet_watchdog", "kind": "opportunity_cost", "value": None,
            "verdict": "UNMEASURED", "units": "judge wall-seconds discarded",
            "reason": reason, "lost_s": lost_s,
            "why": (f"{why}. Every unfinished shard is re-planned by the next sweep, so this "
                    "wall bought no verdict; its E[log W] price is not measured")}


#: THE STALL FILE IS ONE RECORD WITH SEVERAL WRITERS (audit of 7cf2ece90): the shard threads and
#: the watchdog thread in a sweep, and the resident -- a different process. Each write is atomic,
#: but read-modify-write was not: a SLOW that read before a STALL landed wrote back over it, and
#: lost the red, the widening count and the missed-growth line (4 threads, 100 stalls: 36 kept).
#: So every writer holds this lock (threads) AND an exclusive lock file (processes).
_STALL_LOCK = threading.RLock()
STALL_LOCK_WAIT_S = 60.0


_LOCK_LOCAL = threading.local()


def _os_trylock(fd: int) -> bool:
    """One non-blocking attempt at an exclusive OS lock on `fd`. The OS drops it when the holder
    dies, so a dead writer can never leave the file locked and nothing has to break it."""
    if sys.platform == "win32":
        import msvcrt

        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined,unused-ignore]
            return True
        except OSError:
            return False
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, PermissionError):
        return False


def _os_unlock(fd: int) -> None:
    with contextlib.suppress(OSError):
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined,unused-ignore]
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def _stall_guard() -> Any:
    """Thread lock + an OS file lock (flock / msvcrt.locking) around one stall-file
    read-modify-write.

    v3 used an O_EXCL file and broke it when it looked stale; the audit of be522dd44 showed a
    failed unlink spun forever holding the thread lock, and two waiters could both break one
    stale lock. An OS lock needs no breaking: the kernel releases it when its holder dies. Every
    failure -- the file cannot be opened (Windows delete-pending, an ACL), the lock stays held --
    is retried with a sleep until STALL_LOCK_WAIT_S, then the write goes ahead UNLOCKED and says
    so in the record (`lock`), because a report must never hang the sweep.
    """
    with _STALL_LOCK:
        if getattr(_LOCK_LOCAL, "depth", 0):          # re-entered on this thread: already held
            _LOCK_LOCAL.depth += 1
            try:
                yield
            finally:
                _LOCK_LOCAL.depth -= 1
            return
        lock = STALL.with_name(f"{STALL.name}.lock")
        end = time.monotonic() + STALL_LOCK_WAIT_S
        fd: int | None = None
        held = False
        why = ""
        while True:
            try:
                if fd is None:
                    with contextlib.suppress(OSError):
                        lock.parent.mkdir(parents=True, exist_ok=True)
                    fd = os.open(str(lock), os.O_RDWR | os.O_CREAT, 0o666)
                if _os_trylock(fd):
                    held = True
                    break
                why = "held by another writer"
            except OSError as exc:            # PermissionError, delete-pending, ...: retry
                why = f"{type(exc).__name__}: {exc}"[:160]
                if fd is not None:
                    with contextlib.suppress(OSError):
                        os.close(fd)
                    fd = None
            if time.monotonic() >= end:       # ALWAYS checked, whatever failed above
                break
            time.sleep(0.01)                  # ...and never a spin
        _LOCK_LOCAL.note = ("LOCKED" if held else
                            f"UNLOCKED after {STALL_LOCK_WAIT_S:.0f}s: {why or 'unknown'}")
        _LOCK_LOCAL.depth = 1
        try:
            yield
        finally:
            _LOCK_LOCAL.depth = 0
            if fd is not None:
                if held:
                    _os_unlock(fd)
                with contextlib.suppress(OSError):
                    os.close(fd)


def _lock_stamp(prev: dict[str, Any]) -> dict[str, Any]:
    """The lock outcome of THIS write, and the running count of writes that went unlocked."""
    note = str(getattr(_LOCK_LOCAL, "note", "LOCKED"))
    n = int(prev.get("unlocked_writes") or 0) + (0 if note == "LOCKED" else 1)
    return {"lock": note, "unlocked_writes": n}


def _stall_locked(fn: Callable[..., Any]) -> Callable[..., Any]:
    import functools

    @functools.wraps(fn)
    def inner(*a: Any, **kw: Any) -> Any:
        with _stall_guard():
            return fn(*a, **kw)
    return inner


@_stall_locked
def record_stall(reason: str, *, detail: str = "", shard: dict[str, Any] | None = None,
                 pid: int | None = None, counts: bool = True,
                 last_heartbeat: dict[str, Any] | None = None,
                 lost_s: float | None = None, kill: dict[str, Any] | None = None,
                 restored: list[str] | None = None) -> dict[str, Any]:
    """Write GAUNTLET_STALL.json: STALLED, why, where, the last progress seen, and the
    missed-growth line for the wall the kill (or the death) threw away.

    `counts` False records an unfinished sweep whose cause is unknown (its pid vanished with no
    final record) without widening the next ceilings: only a breach that was measured does.
    `lost_s` defaults to this process's own elapsed sweep wall when `pid` is this process.
    """
    prev = _read_json(STALL)
    consecutive = int(prev.get("consecutive") or 0) + (1 if counts else 0)
    hb = last_heartbeat if last_heartbeat is not None else _read_json(HEARTBEAT)
    if lost_s is None and (pid is None or pid == os.getpid()):
        lost_s = _own_elapsed_s()
    if lost_s is None:
        started, beat = _ts(hb.get("started_utc")), _ts(hb.get("beat_utc"))
        if started is not None:
            lost_s = round(max(0.0, (beat or time.time()) - started), 1)
    row = {"status": "STALLED", "reason": reason, "detail": detail[:600],
           "stalled_utc": datetime.now(UTC).isoformat(timespec="seconds"),
           "pid": pid if pid is not None else os.getpid(),
           "phase": hb.get("phase") or _PHASE_DOC.get("phase"),
           "shard": shard,
           "last_progress": {k: hb.get(k) for k in (
               "beat_utc", "phase", "phase_elapsed_s", "shards", "tree", "last_progress_utc",
               "idle_s") if k in hb},
           "counts_toward_widening": counts, "lost_s": lost_s,
           "kill": kill, "restored_from_merge_snapshot": restored or []}
    history = [*(prev.get("history") or []), row][-STALL_HISTORY:]
    mg = [*(prev.get("missed_growth") or []),
          _missed_growth_line(reason, lost_s, f"sweep pid {row['pid']} {reason}: {detail[:200]}")
          ][-MISSED_GROWTH_HISTORY:]
    doc = {**row, **_lock_stamp(prev), "consecutive": consecutive, "history": history,
           "missed_growth": mg,
           "last_clear_utc": prev.get("last_clear_utc"),
           "next_run": ("starts fresh: the sealed protocol re-plans every unfinished shard's "
                        "cells; nothing from the stalled run was marked judged")}
    _write_json_atomic(STALL, doc)
    with contextlib.suppress(Exception):
        print(f"{datetime.now(UTC).isoformat()} GAUNTLET STALL: {reason} -- {detail}", flush=True)
    return doc


def _resume_delay_line(doc: dict[str, Any], sweep_s: float | None, *,
                       plan_kept: bool) -> dict[str, Any]:
    """THE RESUME'S TWO-SIDED LINE (audit HOLD of b94babf39). A resumed plan judges the docket
    it was made from: a cell added since waits for the next full plan (`_replan_changed`'s
    `cells_not_in_this_plan`), and a sweep killed again resumes again, up to the plan's maximum
    age. That delay is the rail's cost; the planning and build wall the resume did not spend
    again is what it bought. Both are measured in their own units; neither is priced in
    E[log W], so the verdict is UNMEASURED, never a clean zero."""
    def _num(key: str) -> float | None:
        v = doc.get(key)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    cells = int(_num("cells_not_in_this_plan") or 0)
    age, max_age = _num("plan_age_s"), _num("max_age_s")
    floor_s = round(float(sweep_s), 1) if sweep_s is not None else None
    ceil_s = (None if floor_s is None or age is None or max_age is None
              else round(max(0.0, max_age - age) + floor_s, 1)) if plan_kept else floor_s
    plan_saved, build_saved = _num("plan_seconds_saved"), _num("build_seconds_saved")
    saved = [x for x in (plan_saved, build_saved) if x is not None]
    now = datetime.now(UTC)
    return {"day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
            "rail": "gauntlet_plan_resume", "kind": "opportunity_cost", "value": None,
            "verdict": "UNMEASURED", "reason": "plan_resumed", "lost_s": None,
            "units": "docket cells x hours delayed (cost) / judge wall-seconds saved (benefit)",
            "cost": {"cells_delayed": cells,
                     "cells_changed_replanned": int(_num("cells_changed_replanned") or 0),
                     "cells_removed": int(_num("cells_removed") or 0),
                     # deferred by the killed sweep's budget and kept so by shard reuse
                     "cells_kept_deferred": int(_num("cells_kept_deferred") or 0),
                     "delay_s_floor": floor_s, "delay_s_ceiling": ceil_s,
                     "cell_hours_floor": (None if floor_s is None
                                          else round(cells * floor_s / 3600.0, 2)),
                     "cell_hours_ceiling": (None if ceil_s is None
                                            else round(cells * ceil_s / 3600.0, 2)),
                     "plan_kept_for_the_next_sweep": plan_kept,
                     "basis": ("floor: this sweep's own wall, which every delayed cell waited "
                               "out; ceiling: the plan's remaining resumable age plus that wall "
                               "when the plan is kept (a kill), else the wall alone -- the next "
                               "sweep's gap is not counted")},
            "benefit": {"plan_s_saved": plan_saved, "build_s_saved": build_saved,
                        "shards_reused": doc.get("shards_reused") or [],
                        "judge_s_saved": round(sum(saved), 1) if saved else None},
            "why": (f"the sweep resumed a plan {age if age is not None else '?'}s old: "
                    f"{cells} docket cell(s) not in it wait for the next full plan and "
                    f"{int(_num('cells_kept_deferred') or 0)} stay deferred in reused shards, "
                    "against "
                    f"{round(sum(saved), 1) if saved else 'UNMEASURED'} judge wall-seconds "
                    "not spent re-planning and re-building; the E[log W] price of either side "
                    "is not measured")}


@_stall_locked
def record_resume_delay(rc: int, *, sweep_t0: float | None = None,
                        path: Path | None = None) -> dict[str, Any] | None:
    """Publish the resume's two-sided missed-growth line on GAUNTLET_STALL.json, where
    `research/missed_growth.py` carries the watchdog's lines. Only for THIS sweep's resume:
    the sealed judge stamps its record with this process's pid and the time it resumed, so an
    older record (or none: the plan was made, not resumed) publishes nothing."""
    doc = _read_json(path or PLAN_RESUME)
    at = _ts(doc.get("at"))
    t0 = sweep_t0 if sweep_t0 is not None else _PHASE_DOC.get("_t0")
    if (not doc.get("resumed") or doc.get("pid") != os.getpid() or at is None
            or (isinstance(t0, float) and at < t0 - 2.0)):
        return None
    sweep_s = (time.time() - t0) if isinstance(t0, float) else None
    line = _resume_delay_line(doc, sweep_s, plan_kept=rc != 0)
    prev = _read_json(STALL)
    mg = [*(prev.get("missed_growth") or []), line][-MISSED_GROWTH_HISTORY:]
    _write_json_atomic(STALL, {**prev, **_lock_stamp(prev), "missed_growth": mg,
                               "plan_resume": line})
    with contextlib.suppress(Exception):
        print(f"{datetime.now(UTC).isoformat()} plan resume: {line['cost']['cells_delayed']} "
              f"cell(s) delayed, {line['benefit']['judge_s_saved']} judge s saved", flush=True)
    return line


@_stall_locked
def record_slow(reason: str, *, detail: str = "", shard: dict[str, Any] | None = None,
                pid: int | None = None,
                last_heartbeat: dict[str, Any] | None = None) -> dict[str, Any]:
    """A sweep past a SLOW threshold that is still making progress: amber, and it keeps going.

    Nothing is killed and nothing widens. The status reads SLOW unless an earlier stall is still
    unanswered (STALLED stays STALLED until a sweep finishes, so a red is never washed amber by
    the next sweep merely being slow).
    """
    prev = _read_json(STALL)
    hb = last_heartbeat if last_heartbeat is not None else _read_json(HEARTBEAT)
    row = {"kind": "SLOW", "reason": reason, "detail": detail[:600],
           "slow_utc": datetime.now(UTC).isoformat(timespec="seconds"),
           "pid": pid if pid is not None else os.getpid(),
           "phase": hb.get("phase") or _PHASE_DOC.get("phase"), "shard": shard,
           "progress": {k: hb.get(k) for k in ("beat_utc", "tree", "last_progress_utc", "idle_s")
                        if k in hb}}
    status = "STALLED" if prev.get("status") == "STALLED" else "SLOW"
    doc = {**prev, **_lock_stamp(prev), "status": status, "slow": row,
           "history": [*(prev.get("history") or []), row][-STALL_HISTORY:],
           "consecutive": int(prev.get("consecutive") or 0)}
    _write_json_atomic(STALL, doc)
    with contextlib.suppress(Exception):
        print(f"{datetime.now(UTC).isoformat()} GAUNTLET SLOW (still progressing, not killed): "
              f"{reason} -- {detail}", flush=True)
    return doc


@_stall_locked
def _record_clear() -> None:
    """A sweep finished: the stall run is over (history kept), so the fence reads green again."""
    prev = _read_json(STALL)
    if not prev:
        return
    _write_json_atomic(STALL, {**{k: v for k, v in prev.items() if k not in ("status", "slow")},
                               **_lock_stamp(prev), "status": "CLEAR", "consecutive": 0,
                               "last_clear_utc": datetime.now(UTC).isoformat(
                                   timespec="seconds")})


#: Files up to this size are checked with a full `json.load`; a larger one (the merge's ~625 MB
#: verdict report) by a structural check of its two ends, so a restore never parses 625 MB twice.
PARSE_FULL_MAX_BYTES = 32 * 1024 * 1024
_PARSE_CACHE: dict[tuple[str, int, int, int, int], bool] = {}


def _ends_close(path: Path, size: int) -> bool:
    """Does the file open with `{`/`[` and end with the matching bracket on a line of its own?
    `json.dumps(indent=...)` puts the outermost closer at column 0 and every inner one indented,
    so a file torn mid-write ends anywhere but there."""
    try:
        with path.open("rb") as fh:
            head = fh.read(64).lstrip()
            fh.seek(max(0, size - 64))
            tail = fh.read().rstrip()
    except OSError:
        return False
    if not head or head[:1] not in (b"{", b"["):
        return False
    closer = b"}" if head[:1] == b"{" else b"]"
    if head[1:2] not in (b"\n", b"\r"):
        # COMPACT JSON IS A WEAK CHECK, KEPT ON PURPOSE (audit of be522dd44): with no column-0
        # closer, 432 of 10,755 torn compact prefixes still end in the closer. No merge output is
        # compact today (external_gauntlet.py writes indent=2); a compact one would need a
        # full parse or a writer-side checksum to be judged properly.
        return tail.endswith(closer)
    return tail.endswith(b"\n" + closer)


def _parses(path: Path) -> bool:
    """Is `path` whole JSON? Cached by (size, mtime): the same bytes are never judged twice."""
    try:
        st = path.stat()
    except OSError:
        return False
    # inode and ctime too (audit of be522dd44): a rewrite with a forced `os.utime` keeps size and
    # mtime, but a replace changes the inode and any write moves ctime, which utime cannot set.
    key = (str(path), int(st.st_size), int(st.st_mtime_ns), int(st.st_ino), int(st.st_ctime_ns))
    hit = _PARSE_CACHE.get(key)
    if hit is not None:
        return hit
    if st.st_size > PARSE_FULL_MAX_BYTES:
        ok = _ends_close(path, int(st.st_size))
    else:
        try:
            with path.open("rb") as fh:
                json.load(fh)
            ok = True
        except (OSError, ValueError):
            ok = False
    if len(_PARSE_CACHE) > 64:
        _PARSE_CACHE.clear()
    _PARSE_CACHE[key] = ok
    return ok


def _clean_merge_tmp() -> list[str]:
    """Remove the partial copies a kill can leave (a snapshot or a restore cut mid-copy): up to
    ~625 MB each, never read by a restore, and otherwise kept until the next finished sweep."""
    gone: list[str] = []
    pats = [(MERGE_SNAPSHOT, "*.tmp"),
            *((dst.parent, f"{dst.name}.restore.*.tmp") for dst in MERGE_OUTPUTS)]
    for folder, pat in pats:
        with contextlib.suppress(OSError):
            for f in folder.glob(pat):
                with contextlib.suppress(OSError):
                    f.unlink()
                    gone.append(f.name)
    return gone


def snapshot_merge_outputs() -> dict[str, Any]:
    """Copy the sealed merge's two authority files aside as the merge starts.

    A kill can land while the sealed writer is mid-file; the copy is what `restore_merge_outputs`
    puts back if the file no longer parses. Skipped (and said so) when the disk cannot hold it.
    """
    import shutil

    out: dict[str, Any] = {"pid": os.getpid(), "at": datetime.now(UTC).isoformat(
        timespec="seconds"), "files": {}}
    with contextlib.suppress(OSError):
        MERGE_SNAPSHOT.mkdir(parents=True, exist_ok=True)
    _clean_merge_tmp()
    for src in MERGE_OUTPUTS:
        if not src.exists() or not _parses(src):
            out["files"][src.name] = "absent or unparseable at merge start: nothing to keep"
            continue
        try:
            size = src.stat().st_size
            if shutil.disk_usage(MERGE_SNAPSHOT).free < 2 * size:
                out["files"][src.name] = f"SKIPPED: under 2x {size} bytes free"
                continue
            tmp = MERGE_SNAPSHOT / f"{src.name}.{os.getpid()}.tmp"
            shutil.copyfile(src, tmp)
            os.replace(tmp, MERGE_SNAPSHOT / src.name)
            out["files"][src.name] = size
        except OSError as exc:
            out["files"][src.name] = f"SKIPPED: {type(exc).__name__}"
    _write_json_atomic(MERGE_SNAPSHOT / "manifest.json", out)
    return out


#: Why the last `restore_merge_outputs` left a torn output torn (name -> reason), for the record.
_RESTORE_REFUSED: dict[str, str] = {}


def _snapshot_vouches(manifest: dict[str, Any], name: str, copy: Path, *,
                      pid: int | None, since: float | None) -> str | None:
    """None when the snapshot's manifest vouches for `copy`; otherwise why it does not.

    A copy is put back only when the manifest written by the SAME snapshot call recorded it as
    copied, at the size it has now (audit of b94babf39): a snapshot that was SKIPPED (disk) or
    that found the file torn says so in the manifest, and a copy left behind by an older
    snapshot -- a suppressed partial rmtree, a skip -- is never restored as if it were current.
    When the caller names the sweep it is recovering, the manifest must be that sweep's (`pid`)
    and taken no earlier than it started (`since`)."""
    if not manifest:
        return "no readable manifest: the copy cannot be shown to be this snapshot's"
    if pid is not None and manifest.get("pid") != pid:
        return f"snapshot taken by pid {manifest.get('pid')}, not the recovered sweep {pid}"
    at = _ts(manifest.get("at"))
    if since is not None and (at is None or at < since - 2.0):
        return (f"snapshot at {manifest.get('at')} predates the recovered sweep's start "
                f"{_iso(since)}")
    want = (manifest.get("files") or {}).get(name)
    if not isinstance(want, int) or isinstance(want, bool):
        return f"the manifest did not copy it: {want!r}"
    try:
        size = copy.stat().st_size
    except OSError:
        return "the copy is unreadable"
    if size != want:
        return f"the copy is {size} bytes, the manifest copied {want}"
    return None


def restore_merge_outputs(*, pid: int | None = None, since: float | None = None) -> list[str]:
    """After a kill: put back every merge output that no longer parses, from the snapshot, and
    remove any partial copy the kill left behind.

    Only a copy the snapshot's manifest vouches for is put back (`_snapshot_vouches`); `pid` and
    `since` name the sweep being recovered when the caller knows it. A refusal is kept in
    `_RESTORE_REFUSED` and the torn file stays torn -- which also keeps the snapshot
    (`_drop_merge_snapshot` removes it only when every output parses)."""
    restored: list[str] = []
    _RESTORE_REFUSED.clear()
    _clean_merge_tmp()
    manifest = _read_json(MERGE_SNAPSHOT / "manifest.json")
    for dst in MERGE_OUTPUTS:
        copy = MERGE_SNAPSHOT / dst.name
        if not copy.exists() or (dst.exists() and _parses(dst)) or not _parses(copy):
            continue
        why = _snapshot_vouches(manifest, dst.name, copy, pid=pid, since=since)
        if why is not None:
            _RESTORE_REFUSED[dst.name] = why
            continue
        try:
            import shutil

            tmp = dst.with_name(f"{dst.name}.restore.{os.getpid()}.tmp")
            shutil.copyfile(copy, tmp)
            try:
                os.replace(tmp, dst)
            except PermissionError:          # Windows: a read-only destination (WinError 5)
                import stat

                os.chmod(dst, stat.S_IWRITE | stat.S_IREAD)
                os.replace(tmp, dst)
            restored.append(dst.name)
        except OSError:
            continue
    _clean_merge_tmp()
    return restored


def _drop_merge_snapshot() -> bool:
    """Remove the merge snapshot ON POSITIVE EVIDENCE ONLY (watchdog v4.1).

    The snapshot is the one copy a restore can use, so it is removed only when every output it
    holds a copy of is READ BACK now and parses -- the copy is then provably never needed
    (`restore_merge_outputs` skips a parsing destination). An output that is absent, or no
    longer parses, keeps the snapshot for the next restore: an absence never removes it.
    Declared in `libs/ops/reference_freshness.DESTRUCTIVE_PATHS` as `positive`.
    """
    import shutil

    for dst in MERGE_OUTPUTS:
        if (MERGE_SNAPSHOT / dst.name).exists() and not (dst.exists() and _parses(dst)):
            return False
    with contextlib.suppress(OSError):
        shutil.rmtree(MERGE_SNAPSHOT)
    return not MERGE_SNAPSHOT.exists()


def _watched_run(argv: list[str], *, cwd: Path | str | None = None,
                 env: dict[str, str] | None = None, stdout: Any = None, stderr: Any = None,
                 check: bool = False, capture_output: bool = False,
                 slow_s: float | None = None, idle_s: float | None = None,
                 on_slow: Callable[[float, _TreeProgress], Any] | None = None,
                 poll_s: float | None = None,
                 sampler: Callable[[int], dict[str, Any] | None] | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 ) -> subprocess.CompletedProcess[Any]:
    """Run one shard child, watching its WHOLE TREE; kill it only when it stops progressing.

    Past `slow_s` it calls `on_slow` once and keeps waiting: a slow shard is never killed. When
    the tree's measured CPU stays under NO_PROGRESS_CORES for `idle_s`, or the sweep's watchdog
    aborts, the tree is killed and ShardStalled raised. Unmeasured progress (no psutil) never
    kills. A non-zero exit raises CalledProcessError when `check` is set, as `subprocess.run`.
    Windows child CPU is booked to `proctree`'s counter exactly as `proctree.run` books it.
    """
    if capture_output:
        raise ValueError("_watched_run streams to files; a PIPE it polls could fill and deadlock")
    sample = sampler or _sample_tree
    every = SHARD_POLL_S if poll_s is None else max(0.01, float(poll_s))
    proc = subprocess.Popen(list(argv), cwd=cwd, env=env, stdout=stdout, stderr=stderr)
    t0 = clock()
    tracker = _TreeProgress(t0, max_gap_s=3.0 * every)
    slow_sent = False
    try:
        while True:
            try:
                rc = proc.wait(timeout=every)
                break
            except subprocess.TimeoutExpired:
                pass
            now = clock()
            tracker.update(sample(proc.pid), now)
            why = None
            if _ABORT.is_set():
                why = "aborted"
            elif idle_s and tracker.measured and tracker.idle_s(now) > idle_s:
                why = "no_progress"
            if why is not None:
                kill = _kill_sweep_tree(proc.pid)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=30)
                raise ShardStalled("?", -1, tracker.idle_s(now), kill=_kill_report(kill),
                                   why=why)
            if slow_s and not slow_sent and now - t0 > slow_s:
                slow_sent = True
                if on_slow is not None:
                    with contextlib.suppress(Exception):     # a report never stops a shard
                        on_slow(now - t0, tracker)
    finally:
        if proc.poll() is not None:
            proctree._CHILD_CPU_S[0] += proctree._windows_process_cpu(proc)
    done: subprocess.CompletedProcess[Any] = subprocess.CompletedProcess(list(argv), rc)
    if check:
        done.check_returncode()
    return done


#: The shard runner `dispatch` calls (the tests substitute it).
run = _watched_run


def dispatch(shard_dir: Path, n: int, phase: str) -> None:
    """Run every judge-owned shard, retrying only failed children at low concurrency.

    Publication remains fail closed: a shard that still fails after the bounded retries raises,
    so the sealed judge cannot merge a partial result.  The retries are deliberately serial.
    A measured production failure mode had ten of fifteen memory-heavy shards finish, five die,
    and the next scheduled invocation discard all ten successful artifacts before repeating the
    two-hour pre-warm.  Retaining the successful outputs and rerunning only the failed children
    after the parallel wave has released its memory converts that restart loop into progress
    without changing a gate, verdict, docket, or merge rule.
    """
    code = (
        "import sys;"
        f"sys.path[:0]=[{str(ROOT)!r},{str(DESK)!r}];"
        "from scripts.run_sharded_gauntlet import record_own_peak;"
        "import atexit,os;"
        "atexit.register(record_own_peak,os.environ.get('GAUNTLET_PEAK_RECEIPT',''));"
        "from scripts.external_gauntlet import shard_worker;"
        "shard_worker(sys.argv[1],int(sys.argv[2]),sys.argv[3])"
    )

    # Python's reassignment of sys.stderr does not redirect a child's OS stderr handle.
    # Keep errors outside the judge's disposable shard directory, without buffering them
    # in the parent's memory. Every retry gets its own receipt.
    logs = shard_dir.parent / f"{shard_dir.name}-logs"
    logs.mkdir(parents=True, exist_ok=True)
    invocation = uuid4().hex
    # EVERY SHARD IS WATCHED, AND ONLY AN IDLE ONE IS KILLED (2026-10-20, re-cut after the audit
    # HOLD of 2832cebd1). `timeout=None` meant a shard that never returned held the wave -- and
    # with it the sweep, the lane and the task's one instance -- forever; a wall-clock timeout
    # instead would kill a shard that is merely slow. So the shard's tree is sampled: past its
    # SLOW threshold it is recorded amber and left running; only a tree that burns under
    # NO_PROGRESS_CORES for the whole no-progress window is killed (`_watched_run`).
    timeout_s = shard_timeout_s(phase)
    idle_s = no_progress_s()
    abort_wave = threading.Event()
    walls: list[float] = []
    walls_lock = threading.Lock()
    _progress_set(phase=phase, total=n, done=0, failed=0, running=0, stalled=0, slow=0,
                  retrying=0, shard_slow_s=round(timeout_s, 1), shard_idle_kill_s=round(idle_s, 1),
                  wave_started_utc=datetime.now(UTC).isoformat(timespec="seconds"))

    def one(k: int, attempt: int = 0) -> None:
        if _ABORT.is_set() or abort_wave.is_set():
            raise RuntimeError(f"{phase} shard {k} not started: the wave was aborted")
        receipt = logs / f"{invocation}-{phase}-{k}-attempt-{attempt}.log"

        def slow(elapsed: float, tracker: _TreeProgress) -> None:
            _progress_bump("slow")
            record_slow("shard_slow", detail=(
                f"{phase} shard {k} has run {elapsed:.0f}s, past its {timeout_s:.0f}s SLOW "
                f"threshold, and is still progressing (last progress "
                f"{tracker.idle_s(time.monotonic()):.0f}s ago): left running"),
                shard={"phase": phase, "k": k, "slow_s": round(timeout_s, 1),
                       "receipt": str(receipt)})

        with receipt.open("wb") as output:
            output.write(f"{datetime.now(UTC).isoformat()} {phase} shard={k} "
                         f"attempt={attempt} slow_s={timeout_s:.0f} "
                         f"idle_kill_s={idle_s:.0f}\n".encode())
            output.flush()
            t0 = time.monotonic()
            _progress_bump("running")
            try:
                child_env = {**os.environ, "GAUNTLET_PEAK_RECEIPT": str(
                    logs / f"{invocation}-{phase}-{k}-attempt-{attempt}.peak.json")}
                try:
                    run([sys.executable, "-u", "-c", code, str(shard_dir), str(k), phase],
                        cwd=DESK, env=child_env, capture_output=False,
                        stdout=output, stderr=output, check=True,
                        slow_s=timeout_s, idle_s=idle_s, on_slow=slow)
                except ShardStalled as exc:
                    exc.phase, exc.k = phase, k
                    raise
            except Exception as exc:
                # A native child can fail without writing a traceback (termination, allocation
                # failure). Persist its exit evidence immediately, before the remaining wave
                # finishes; a start-only receipt must never be mistaken for a still-running job.
                try:
                    output.seek(0, os.SEEK_END)
                    output.write(f"{datetime.now(UTC).isoformat()} CHILD_FAILED "
                                 f"type={type(exc).__name__} "
                                 f"returncode={getattr(exc, 'returncode', None)}\n".encode())
                    output.flush()
                except OSError:
                    pass  # the original child failure still propagates below
                if isinstance(exc, ShardStalled):
                    raise
                raise RuntimeError(f"{phase} shard {k} failed; child log={receipt}") from exc
            finally:
                _progress_bump("running", -1)
            output.seek(0, os.SEEK_END)
            output.write(f"{datetime.now(UTC).isoformat()} CHILD_EXIT_OK\n".encode())
            output.flush()
        with walls_lock:
            walls.append(time.monotonic() - t0)
        _progress_bump("done")

    def attempted(k: int) -> tuple[int, Exception | None]:
        try:
            one(k)
        except ShardStalled as exc:
            # AN IDLE SHARD ENDS THE WAVE: the rest would be merged with a hole and refused, so
            # nothing more is started; shards already running finish or meet their own window.
            abort_wave.set()
            _progress_bump("stalled")
            return k, exc
        except Exception as exc:  # child exit/OOM is evidence, then retried below
            _progress_bump("failed")
            return k, exc
        return k, None

    def stalled(exc: ShardStalled, not_started: int = 0) -> ShardStalled:
        record_stall(f"shard_{exc.why}", detail=(
            f"{exc}"
            + (f"; {not_started} shard(s) of the wave were not started" if not_started else "")),
            shard={"phase": phase, "k": exc.k, "idle_s": round(exc.idle_s, 1),
                   "slow_s": round(timeout_s, 1),
                   "receipt_glob": str(logs / f"{invocation}-{phase}-{exc.k}-attempt-*.log")},
            kill=exc.kill)
        return exc

    width = _parallelism(n, phase)
    print(f"SHARD WAVE: {phase} x{n} at concurrency {width} (recorded peak "
          f"{_shard_peak_mb(phase)} MB, available {_available_mb()} MB)", flush=True)
    with ThreadPoolExecutor(max_workers=width, thread_name_prefix=f"judge-{phase}") as pool:
        # Consume every result even when one child fails, so successful shard artifacts survive.
        first = list(pool.map(attempted, range(n)))
    _record_peaks(logs, invocation, phase)
    if walls:
        _record_phase_times(shard_walls={phase: walls})

    idle = [exc for _k, exc in first if isinstance(exc, ShardStalled)]
    if idle:
        skipped = sum(1 for _k, exc in first
                      if exc is not None and not isinstance(exc, ShardStalled)
                      and "the wave was aborted" in str(exc))
        raise stalled(idle[0], skipped)
    if _ABORT.is_set():
        raise RuntimeError(f"{phase} wave aborted by the sweep watchdog")
    failed = [(k, exc) for k, exc in first if exc is not None]
    if failed:
        print(f"SHARD RECOVERY: {len(failed)}/{n} {phase} shard(s) failed in parallel; "
              "retrying only those shards serially after peer memory was released", flush=True)
    for k, first_exc in failed:
        assert first_exc is not None
        last_exc = first_exc
        for attempt in range(1, _retry_attempts() + 1):
            _progress_bump("retrying")
            try:
                one(k, attempt)
                print(f"SHARD RECOVERY: {phase} shard {k} recovered on retry {attempt}",
                      flush=True)
                break
            except ShardStalled as exc:
                raise stalled(exc) from last_exc
            except Exception as exc:
                last_exc = exc
                print(f"SHARD RECOVERY: {phase} shard {k} retry {attempt} failed: "
                      f"{type(exc).__name__}: {exc}", flush=True)
        else:
            attempts = _retry_attempts() + 1
            raise RuntimeError(
                f"{phase} shard {k} failed after {attempts} attempt(s); refusing partial merge"
            ) from last_exc


def record_own_peak(path: str) -> None:
    """atexit hook in a shard child: write this process's peak memory (MB) to `path`."""
    if not path:
        return
    peak: float | None = None
    try:
        import psutil
        mi = psutil.Process().memory_info()
        peak = float(getattr(mi, "peak_wset", 0) or getattr(mi, "rss", 0)) / (1024.0 * 1024.0)
    except Exception:
        try:
            import resource
            peak = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
        except Exception:
            peak = None
    if not peak:
        return
    with contextlib.suppress(OSError):
        Path(path).write_text(json.dumps({"peak_mb": round(peak, 1)}), encoding="utf-8")


# ------------------------------------------------------------------------- the resident judge
#: THE JUDGE NEVER WAITS FOR A CLOCK (principal, 2026-10-10: "judging must be 24 7 uninterrupted,
#: 0 cadences, no 5 min cadences"). Every trigger used to be ONE sweep: it published, exited, and
#: the box idled until the next repetition fired -- 5 or 10 minutes when `judging_throughput`'s
#: cadence apply worked, an hour when it timed out (it FAILED on 2026-10-13). The resident judge
#: starts the next sweep the moment the last one ends, each in a fresh child process (fresh
#: memory, and the release's code identity). The scheduled trigger becomes a RESPAWNER: with
#: `MultipleInstances IgnoreNew` it does nothing while the resident runs, and restarts it within
#: one interval if it ever dies.
#:
#: It stops for exactly three things, each recorded in `JUDGE_RESIDENT.json`:
#:   * `RESIDENT_STOP` exists (an operator stop; delete it to resume);
#:   * the task's own ExecutionTimeLimit would kill the next sweep -- it does not start one it
#:     cannot finish, and exits so the trigger starts a fresh resident (PT0S = no limit);
#:   * it is not the canonical certifier (the lane is held) -- it waits and retries.
#: A failed sweep is retried after a short, growing pause (`RESIDENT_BACKOFF_S`), never abandoned.
RESIDENT_STATE = DESK / "reports" / "JUDGE_RESIDENT.json"
RESIDENT_STOP = DESK / "data" / "RESIDENT_STOP"
RESIDENT_BACKOFF_S = (15, 30, 60, 120, 300)
#: Seconds kept clear of the task's time limit, and the shortest sweep assumed before one is
#: measured, when deciding whether another sweep fits inside it.
RESIDENT_LIMIT_MARGIN_S = 300.0
RESIDENT_MIN_SWEEP_S = 600.0
#: Exit code a sweep returns when another certifier owns the lane (`run_sharded`).
LANE_HELD_RC = 75
#: The heartbeat is re-stamped this often while a sweep runs, so a resident killed mid-sweep
#: reads as an old heartbeat (check_judge_coverage marks it DEAD past 5 minutes), never as a
#: SWEEPING that lasts forever.
RESIDENT_HEARTBEAT_S = 30.0
#: A SWEEP THAT NEVER ENDS IS THE ONE FAILURE THE RESPAWNER CANNOT SEE (2026-10-13). The task runs
#: with `MultipleInstances IgnoreNew` and no time limit (`task_time_limit_s` 0), so one hung sweep
#: keeps its instance alive and every trigger after it is refused (0x800710E0): from 10-12 06:59Z
#: the box held ~1 busy judge core, wrote no verdict for 33 hours, and Task Scheduler refused each
#: MT5-Gauntlet start. The heartbeat thread kept beating through it. So each sweep child now has a
#: ceiling derived from what it is allowed to spend -- twice the build budget the throughput
#: organ sets (`GAUNTLET_FRESH_BUDGET_SEC`) or three times the longest sweep this resident has
#: measured, whichever is larger, never under an hour. SINCE THE AUDIT HOLD OF 2832cebd1 THAT
#: CEILING IS A SLOW THRESHOLD: a child past it that is still burning CPU is recorded amber and
#: left to finish; only one the resident MEASURES idle is killed with its whole tree.
RESIDENT_HANG_RC = 124
#: WHICH PART OF A SWEEP THE TIME WENT TO, named from outside the sealed judge (2026-10-13). The
#: 33-hour stall held ~1 busy core -- CPU-bound in one process, not a deadlock -- and nothing on
#: origin could say whether that was planning, a shard wave, or the single-process merge and
#: publish after the last wave. The launcher sees every boundary the protocol exposes: the judge
#: plans until it dispatches `build`, collects and cuts between `build` and `rule`, and merges
#: and publishes after `rule` returns. Each sweep child stamps the phase it is in and the seconds
#: each finished phase took; the resident folds that into JUDGE_RESIDENT.json (published) on
#: every heartbeat and names the phase a hung sweep was killed in.
SWEEP_PHASE = DESK / "reports" / "JUDGE_SWEEP_PHASE.json"
_PHASE_DOC: dict[str, Any] = {}
RESIDENT_HANG_BUDGET_MULT = 2.0
RESIDENT_HANG_SWEEP_MULT = 3.0
RESIDENT_HANG_FLOOR_S = 3600.0
#: A SWEEP THAT IS SLOW, NOT STUCK, MUST STILL FINISH (audit of #350). Each consecutive kill
#: doubles the ceiling, up to this cap, and the count survives a resident restart (it is read
#: back from JUDGE_RESIDENT.json), so a deterministic long merge widens its own window instead of
#: being killed at the same mark forever. Two or more in a row fail the coverage fence.
RESIDENT_HANG_CAP_S = 48 * 3600.0
#: The sealed judge's own default build budget, used when the sweep's env names none.
SEALED_FRESH_BUDGET_S = 2700.0


def _resident_enabled(argv: list[str]) -> bool:
    if "--once" in argv:
        return False
    if "--resident" in argv:
        return True
    return os.environ.get("GAUNTLET_RESIDENT", "1").strip().lower() not in ("0", "false", "no")


def _task_limit_s() -> float | None:
    """The scheduled task's ExecutionTimeLimit in seconds; 0 = unlimited; None = unreadable."""
    try:
        from research.judging_throughput import OUT, task_time_limit_s
    except Exception:
        return None
    limit = task_time_limit_s()
    if limit is not None:
        return float(limit)
    try:
        prev = (json.loads(Path(OUT).read_text("utf-8")).get("decision") or {}).get(
            "task_time_limit_s")
        return float(prev) if isinstance(prev, (int, float)) else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _fits(elapsed: float, limit: float | None, last_sweep_s: float | None) -> bool:
    """Another sweep fits before the task's limit. Unlimited (0) and unreadable (None) fit:
    an unreadable limit is UNMEASURED and the sweep is resumable, so it is never a reason to
    stop judging."""
    if not limit:
        return True
    need = max(float(last_sweep_s or 0.0), RESIDENT_MIN_SWEEP_S) + RESIDENT_LIMIT_MARGIN_S
    return elapsed + need <= limit


def _phase(name: str) -> None:
    """Close the current sweep phase and open `name`, stamped to SWEEP_PHASE."""
    now = time.time()
    doc = _PHASE_DOC
    if not doc:
        doc.update(pid=os.getpid(), sweep_started_utc=datetime.now(UTC).isoformat(
            timespec="seconds"), phases={}, _t0=now)
    prev, since = doc.get("phase"), doc.get("_t")
    if prev and isinstance(since, float):
        doc["phases"][prev] = round(doc["phases"].get(prev, 0.0) + now - since, 1)
    doc.update(phase=name, phase_started_utc=datetime.now(UTC).isoformat(timespec="seconds"),
               _t=now)
    try:
        SWEEP_PHASE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SWEEP_PHASE.with_name(f"{SWEEP_PHASE.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({k: v for k, v in doc.items() if not k.startswith("_")},
                                  indent=1),
                       encoding="utf-8")
        os.replace(tmp, SWEEP_PHASE)
    except OSError:
        pass  # a phase stamp is a report; judging never stops for it


def _sweep_phase() -> dict[str, Any] | None:
    try:
        doc = json.loads(SWEEP_PHASE.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _write_state(doc: dict[str, Any]) -> None:
    doc = {**doc, "heartbeat_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    if doc.get("status") == "SWEEPING":
        doc["sweep_phase"] = _sweep_phase()
    try:
        RESIDENT_STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = RESIDENT_STATE.with_name(
            f"{RESIDENT_STATE.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, RESIDENT_STATE)
    except OSError:
        pass  # the heartbeat is a report; judging never stops for it


def _published_env() -> dict[str, str]:
    """judging_throughput's measured env as it stands now ({} when unreadable or refused)."""
    try:
        from research.judging_throughput import apply_env
    except Exception:
        return {}
    probe: dict[str, str] = {}
    try:
        apply_env(env=probe)
    except Exception:
        return {}
    return probe


#: The measured env as the resident found it at launch, and the process env at that moment.
_LAUNCH: dict[str, dict[str, str]] = {}


def _sweep_env() -> dict[str, str]:
    """The env for the next sweep: the launch env with judging_throughput's LATEST numbers.

    The launcher exported the measured env once, but a resident outlives many hourly
    re-measurements. A key that came from that file is refreshed from it every sweep; a key an
    operator exported by hand (it differed from the file at launch) still outranks the organ.
    """
    if not _LAUNCH:
        _LAUNCH["file"] = _published_env()
        _LAUNCH["proc"] = {k: os.environ[k] for k in _LAUNCH["file"] if k in os.environ}
    env = os.environ.copy()
    for k, v in _published_env().items():
        launched = _LAUNCH["proc"].get(k)
        if launched is None or launched == _LAUNCH["file"].get(k):
            env[k] = v
    return env


def _hang_limit_s(longest_sweep_s: float | None, consecutive_hangs: int = 0,
                  env: dict[str, str] | None = None) -> float:
    """The most one sweep child may run before it is killed as hung (see RESIDENT_HANG_RC).

    The budget is the one the CHILD runs with (`_sweep_env`), never the resident's own env.
    """
    raw = (env if env is not None else os.environ).get("GAUNTLET_FRESH_BUDGET_SEC")
    try:
        budget = float(raw) if raw is not None else SEALED_FRESH_BUDGET_S
    except (TypeError, ValueError):
        budget = SEALED_FRESH_BUDGET_S
    base = max(RESIDENT_HANG_FLOOR_S, RESIDENT_HANG_BUDGET_MULT * max(budget, 0.0),
               RESIDENT_HANG_SWEEP_MULT * float(longest_sweep_s or 0.0))
    return min(RESIDENT_HANG_CAP_S, base * (2.0 ** max(0, int(consecutive_hangs))))


def _kill_report(res: object) -> dict[str, Any]:
    """A kill helper's result as a dict (a test double may return a bare count or nothing)."""
    if isinstance(res, dict):
        return res
    return {"killed": int(res) if isinstance(res, int) else 0, "orphans": []}


def _kill_sweep_tree(pid: int, *, wall_s: float | None = None) -> dict[str, Any]:
    """Kill a sweep and every descendant (see `_kill_tree`)."""
    return _kill_tree(pid, wall_s=wall_s, include_root=True)


def _kill_descendants(pid: int, *, wall_s: float | None = None) -> dict[str, Any]:
    """Kill every descendant of `pid` (the watchdog's own process), never `pid` itself."""
    return _kill_tree(pid, wall_s=wall_s, include_root=False)


def _kill_tree(pid: int, *, wall_s: float | None = None,
               include_root: bool = True) -> dict[str, Any]:
    """Kill a sweep and EVERY descendant, including shards its dispatch respawns mid-kill.

    Audit of #350: snapshot-then-kill left orphans in 2 of 5 probes, because the root's retry
    loop and executor started new shards after the snapshot -- and on the box an orphan becomes
    the oldest external_gauntlet, which StallWatch keeps while it kills the NEXT sweep's shards.
    So the root is SUSPENDED first (it can start nothing), then descendants are re-enumerated,
    suspended and killed until a pass finds none, then the root dies.

    IT LOOPS UNTIL THE TREE IS EMPTY, NOT FOR A FIXED COUNT (audit of 2832cebd1: twenty rounds
    could give up on a tree still respawning), bounded only by `wall_s` (KILL_WALL_S). Anything
    seen that is still alive at the end is named in `orphans`, which every caller writes into
    the stall artifact. Returns {"killed", "orphans", "wall_s"}.
    """
    out: dict[str, Any] = {"killed": 0, "orphans": [], "wall_s": 0.0}
    try:
        import psutil
    except ImportError:                                        # pragma: no cover - box has it
        out["note"] = "psutil absent: nothing was killed"
        return out
    try:
        root = psutil.Process(pid)
        if include_root:              # a process never freezes itself: its own kill would stop
            root.suspend()
    except psutil.Error:
        return out
    t0 = time.monotonic()
    budget = KILL_WALL_S if wall_s is None else max(0.0, float(wall_s))
    seen: dict[int, Any] = {}
    killed = 0
    def live_kids() -> list[Any]:
        # A killed child of a suspended (or not-yet-reaping) parent is a ZOMBIE: dead, holding
        # nothing, and still listed. It is never "the tree is not empty yet".
        out_kids = []
        for k in root.children(recursive=True):
            with contextlib.suppress(psutil.Error):
                if k.status() != psutil.STATUS_ZOMBIE:
                    out_kids.append(k)
        return out_kids

    while True:
        try:
            kids = live_kids()
        except psutil.Error:
            break
        if not kids or time.monotonic() - t0 > budget:
            break
        # FREEZE THE WHOLE TREE BEFORE ANY KILL: a grandchild started between enumeration and
        # suspension would be re-parented away (and orphaned) the moment its parent died, so
        # enumerate-and-suspend repeats until a pass finds nobody new.
        frozen: dict[int, Any] = {}
        while True:
            fresh = [k for k in kids if k.pid not in frozen]
            if not fresh:
                break
            for k in fresh:
                with contextlib.suppress(psutil.Error):
                    k.suspend()
                frozen[k.pid] = k
            try:
                kids = live_kids()
            except psutil.Error:
                break
        kids = list(frozen.values())
        seen.update(frozen)
        for k in kids:
            with contextlib.suppress(psutil.Error):
                k.kill()
                killed += 1
        psutil.wait_procs(kids, timeout=max(0.1, min(5.0, budget - (time.monotonic() - t0))))
    if include_root:
        with contextlib.suppress(psutil.Error):
            root.kill()
            killed += 1
            root.wait(timeout=10)
    orphans: set[int] = set()
    for p in seen.values():
        with contextlib.suppress(psutil.Error):
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                orphans.add(p.pid)
    with contextlib.suppress(psutil.Error):
        orphans.update(k.pid for k in live_kids())
    out.update(killed=killed, orphans=sorted(orphans), wall_s=round(time.monotonic() - t0, 2))
    return out


def _child_slow(pid: int, now: float) -> tuple[str, str] | None:
    """(tag, why) when sweep `pid` reads SLOW from ITS heartbeat (a quiet beat, or past its run
    threshold), else None. A NOTE, never a kill: only the resident's measured idleness kills."""
    hb = _read_json(HEARTBEAT)
    if hb.get("pid") != pid or hb.get("status") != "RUNNING":
        return None
    beat = _ts(hb.get("beat_utc"))
    if beat is not None and now - beat > HEARTBEAT_STALE_S:
        return ("quiet_heartbeat",
                f"its heartbeat is {now - beat:.0f}s old: the sweep's own watchdog is quiet")
    deadline = _ts(hb.get("run_deadline_utc"))
    if deadline is not None and now > deadline + HEARTBEAT_STALE_S:
        return ("past_run_threshold",
                f"it is past its own run threshold {hb.get('run_deadline_utc')}")
    return None


def _one_sweep_child(hang_s: float | None = None, *, poll_s: float = 60.0,
                     clock: Callable[[], float] = time.monotonic,
                     wall: Callable[[], float] = time.time,
                     sampler: Callable[[int], dict[str, Any] | None] | None = None) -> int:
    """One sweep in a fresh process, at the priority the scheduler gives the judge today.

    THE RESIDENT KILLS ONLY AN IDLE SWEEP (audit HOLD of 2832cebd1). `hang_s` is a SLOW
    threshold: past it, and on a quiet child heartbeat, an amber record is written and the sweep
    runs on. The kill is the resident's OWN measurement of the child's tree: under
    NO_PROGRESS_CORES for the child's no-progress window plus HEARTBEAT_STALE_S (so the child's
    watchdog, which acts at the window, always goes first). Without psutil nothing is measured,
    so nothing is killed -- the thresholds still write SLOW.
    """
    flags = 0
    if sys.platform == "win32":
        # BELOW_NORMAL is the Task Scheduler's default priority (7) for MT5-Gauntlet, so the
        # child keeps exactly the standing the judge has now: miners are never displaced by it.
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    child = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "--once"],
                             cwd=DESK, env=_sweep_env(), creationflags=flags)
    sample = sampler or _sample_tree
    t0 = clock()
    tracker = _TreeProgress(t0, max_gap_s=(3.0 * poll_s) if poll_s > 0 else None)
    idle_kill_s = no_progress_s() + HEARTBEAT_STALE_S
    noted: set[str] = set()
    while True:
        try:
            return int(child.wait(timeout=poll_s))
        except subprocess.TimeoutExpired:
            pass
        now = clock()
        tracker.update(sample(child.pid), now)
        if tracker.measured and tracker.idle_s(now) > idle_kill_s:
            break
        slow = _child_slow(child.pid, wall())
        if slow is None and hang_s is not None and now - t0 >= float(hang_s):
            slow = ("resident_threshold",
                    f"the resident's {hang_s:.0f}s SLOW threshold was reached")
        if slow is not None and slow[0] not in noted:
            noted.add(slow[0])
            record_slow("resident_slow", detail=(
                f"sweep pid {child.pid}: {slow[1]}; its tree is "
                + (f"progressing (last {tracker.idle_s(now):.0f}s ago)" if tracker.measured
                   else "UNMEASURED (no psutil)") + ": left running"), pid=child.pid)
    why = (f"its whole tree burned < {NO_PROGRESS_CORES} core for {tracker.idle_s(now):.0f}s "
           f"(> {idle_kill_s:.0f}s), measured by the resident")
    hb = _read_json(HEARTBEAT)
    kill = _kill_report(_kill_sweep_tree(child.pid))
    with contextlib.suppress(subprocess.TimeoutExpired):
        child.wait(timeout=30)
    restored = restore_merge_outputs(
        pid=child.pid, since=_ts(hb.get("started_utc")) if hb.get("pid") == child.pid else None)
    record_stall("resident_kill", detail=f"sweep pid {child.pid}: {why}", pid=child.pid,
                 last_heartbeat=hb if hb.get("pid") == child.pid else {},
                 lost_s=round(now - t0, 1), kill=kill, restored=restored)
    if hb.get("pid") == child.pid and hb.get("status") == "RUNNING":
        # Recorded here, so the next sweep's takeover does not re-report it as unrecorded.
        _write_json_atomic(HEARTBEAT, {**hb, "status": "KILLED_BY_RESIDENT", "why": why})
    return RESIDENT_HANG_RC


def _heartbeat(state: dict[str, Any], stop: threading.Event, every_s: float) -> None:
    """Re-stamp the heartbeat while the main thread waits on a sweep."""
    while not stop.wait(every_s):
        if stop.is_set():                         # never land a beat after the final record
            return
        with contextlib.suppress(RuntimeError):   # the dict changed while it was copied
            _write_state(dict(state))


def resident(*, sweep=None, sleep=time.sleep, clock=time.monotonic,
             limit_s: float | None = None, max_sweeps: int | None = None,
             heartbeat_s: float = RESIDENT_HEARTBEAT_S) -> int:
    """Run sweeps back to back until stopped; return the last sweep's exit code."""
    started, last_rc = clock(), 0
    state: dict[str, Any] = {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat(
        timespec="seconds"), "task_limit_s": limit_s, "sweeps": 0, "failures": 0,
        "lane_held": 0, "hung_kills": 0, "busy_seconds": 0.0, "status": "RUNNING"}
    # WHAT A RESTART MUST NOT FORGET (audit of #350): the longest measured sweep and the run of
    # consecutive hung kills, read back from the last record, so the ceiling keeps widening.
    prev = _read_state()
    state["longest_sweep_s"] = prev.get("longest_sweep_s")
    state["consecutive_hangs"] = int(prev.get("consecutive_hangs") or 0)
    state["hung_kills"] = int(prev.get("hung_kills") or 0)
    if sweep is None:
        def sweep() -> int:
            hang = _hang_limit_s(state.get("longest_sweep_s"),
                                 int(state.get("consecutive_hangs") or 0), _sweep_env())
            state["hang_limit_s"] = round(hang, 1)
            return _one_sweep_child(hang)
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat, args=(state, stop, heartbeat_s), daemon=True)
    beat.start()
    try:
        last_rc = _resident_loop(state, sweep, sleep, clock, started, limit_s, max_sweeps)
    finally:
        stop.set()
        beat.join(timeout=5)
        if state.get("status") in ("RUNNING", "SWEEPING", "BACKOFF"):
            # Anything that ends the loop without naming why (an exception, an interrupt) still
            # leaves an EXITED record rather than a SWEEPING one.
            state["status"], state["why"] = "EXITED", "the resident loop ended unexpectedly"
        state["uptime_s"] = round(clock() - started, 1)
        _write_state(state)
    return last_rc


def _read_state() -> dict[str, Any]:
    try:
        doc = json.loads(RESIDENT_STATE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _resident_loop(state: dict[str, Any], sweep: Callable[[], int],
                   sleep: Callable[[float], Any], clock: Callable[[], float], started: float,
                   limit_s: float | None, max_sweeps: int | None) -> int:
    failures, n, last_rc = 0, 0, 0
    last_sweep_s: float | None = None
    while True:
        if RESIDENT_STOP.exists():
            state["status"], state["why"] = "STOPPED", f"{RESIDENT_STOP.name} present"
            break
        if not _fits(clock() - started, limit_s, last_sweep_s):
            state["status"] = "RESPAWN"
            state["why"] = ("the next sweep would not finish inside the task's ExecutionTimeLimit;"
                            " exiting so the trigger starts a fresh resident")
            break
        if max_sweeps is not None and n >= max_sweeps:
            state["status"], state["why"] = "DONE", f"max_sweeps={max_sweeps}"
            break
        t0 = clock()
        state.update(status="SWEEPING", sweep_started_utc=datetime.now(UTC).isoformat(
            timespec="seconds"))
        _write_state(state)
        try:
            last_rc = int(sweep())
        except Exception as exc:  # a launcher-level crash is a failed sweep, retried below
            last_rc, state["last_error"] = 1, f"{type(exc).__name__}: {exc}"[:300]
        dt = clock() - t0
        n += 1
        state["sweeps"], state["busy_seconds"] = n, round(state["busy_seconds"] + dt, 1)
        state.update(last_rc=last_rc, last_sweep_s=round(dt, 1), uptime_s=round(
            clock() - started, 1), last_sweep_ended_utc=datetime.now(UTC).isoformat(
            timespec="seconds"))
        if last_rc == 0:
            failures, last_sweep_s = 0, dt
            state["consecutive_hangs"] = 0
            state["longest_sweep_s"] = round(max(dt, float(state.get("longest_sweep_s") or 0.0)),
                                             1)
            state["status"] = "RUNNING"
            _write_state(state)
            continue                       # ZERO CADENCE: the next sweep starts now
        if last_rc == LANE_HELD_RC:
            state["lane_held"] += 1
            pause = RESIDENT_BACKOFF_S[0]
        else:
            failures += 1
            state["failures"] += 1
            if last_rc == RESIDENT_HANG_RC:
                state["hung_kills"] = int(state.get("hung_kills") or 0) + 1
                state["consecutive_hangs"] = int(state.get("consecutive_hangs") or 0) + 1
                state["last_hung_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
                state["killed_in_phase"] = _sweep_phase()
            pause = RESIDENT_BACKOFF_S[min(failures, len(RESIDENT_BACKOFF_S)) - 1]
        state.update(status="BACKOFF", backoff_s=pause)
        _write_state(state)
        sleep(pause)
    return last_rc


# --------------------------------------------------------------------- the --once watchdog
def _ts(raw: object) -> float | None:
    """Epoch seconds of an ISO timestamp, or None."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, UTC).isoformat(timespec="seconds")


def _create_time(pid: int) -> float | None:
    try:
        import psutil
        return float(psutil.Process(pid).create_time())
    except Exception:
        return None


def _sample_tree(pid: int) -> dict[str, Any] | None:
    """CPU seconds per process, total RSS and the process count of `pid` and its descendants.
    None when psutil is absent: progress is then UNMEASURED and only the deadlines apply."""
    try:
        import psutil
        root = psutil.Process(pid)
        procs = [root, *root.children(recursive=True)]
    except Exception:
        return None
    cpu: dict[int, float] = {}
    io: dict[int, float] = {}
    rss = 0.0
    io_ok = True
    for p in procs:
        try:
            t = p.cpu_times()
            cpu[p.pid] = float(t.user) + float(t.system)
        except psutil.AccessDenied:
            # ONE UNREADABLE PROCESS MAKES THE WHOLE TREE UNMEASURED (audit of be522dd44): an
            # idle readable parent over a denied busy grandchild read as measured idle and was
            # killed. A tree is idle only when every process in it was seen to be idle.
            return None
        except psutil.Error:
            continue                    # exited between enumeration and the read: not in it
        except Exception:
            return None
        with contextlib.suppress(Exception):
            rss += float(p.memory_info().rss)
        try:
            c = p.io_counters()
            io[p.pid] = float(getattr(c, "read_bytes", 0)) + float(getattr(c, "write_bytes", 0))
        except psutil.AccessDenied:
            return None                 # denied I/O is as unmeasured as denied CPU
        except Exception:
            io_ok = False               # not exposed here (or it exited): CPU only
    if not cpu:
        # NOTHING COULD BE READ (AccessDenied on every process, audit of 7cf2ece90): that is
        # UNMEASURED, never "measured idle" -- an empty CPU map once killed a child busy at one
        # full core.
        return None
    out: dict[str, Any] = {"cpu": cpu, "rss_mb": round(rss / (1024.0 * 1024.0), 1),
                           "procs": len(cpu)}
    if io_ok and io and len(io) == len(cpu):   # I/O only when every process gave it
        out["io"] = io
    return out


def _lock_root() -> Path | None:
    try:
        from research.job_lock import LOCK_ROOT
    except Exception:
        return None
    return Path(LOCK_ROOT)


def _holds_lane() -> bool:
    """This process owns the certification lane (the sealed judge's lock)."""
    import socket

    root = _lock_root()
    if root is None:
        return False
    doc = _read_json(root / "certification_lane.json")
    return doc.get("pid") == os.getpid() and str(doc.get("host") or "") == socket.gethostname()


def _release_own_locks() -> list[str]:
    """Remove the sweep locks THIS process holds. `os._exit` skips the `finally` that would."""
    import socket

    root = _lock_root()
    out: list[str] = []
    if root is None:
        return out
    for name in SWEEP_LOCKS:
        path = root / f"{name}.json"
        doc = _read_json(path)
        if doc.get("pid") == os.getpid() and str(doc.get("host") or "") == socket.gethostname():
            with contextlib.suppress(OSError):
                path.unlink()
                out.append(name)
    return out


def _cmdline(pid: int) -> str | None:
    """The process's command line, or None when it cannot be read (never a guess)."""
    try:
        import psutil
        return " ".join(psutil.Process(pid).cmdline())
    except Exception:
        return None


def _is_certifier(cmdline: str | None) -> bool:
    """Could this command line own a sweep lock? Unreadable counts as YES: never reclaim blind.
    The resident launcher (`run_sharded_gauntlet` without `--once`) takes no lock, so it is not
    one; its `--once` children are."""
    if cmdline is None:
        return True
    if "run_sharded_gauntlet" in cmdline and "--once" not in cmdline:
        rest = cmdline.replace("run_sharded_gauntlet", "")
        return any(m in rest for m in CERTIFIER_MARKERS)
    return any(m in cmdline for m in CERTIFIER_MARKERS)


def _reclaim_reused_locks() -> list[str]:
    """A sweep lock whose pid now names a process that is NOT a certifier and that was STARTED
    WELL AFTER the lock was written is a dead owner's lock and a reused pid. `job_lock` reads such
    an owner as ALIVE and never reclaims it, which would refuse every sweep forever; it is
    removed here, and only here.

    TWO WRITERS ARE IMPOSSIBLE BY CONSTRUCTION (audit of 2832cebd1): `certification_lane` is
    also taken by `certifier_launcher.py` and by the hourly `external_gauntlet` leg, so a lock
    whose pid now runs ANY certifier (or whose command line cannot be read) is never touched,
    whatever the clocks say. The create-time test only adds to that, with a REUSED_PID_MARGIN_S
    wide enough that a wall clock stepped back cannot make a live writer look reused.
    """
    import socket

    root = _lock_root()
    out: list[str] = []
    if root is None:
        return out
    for name in SWEEP_LOCKS:
        path = root / f"{name}.json"
        doc = _read_json(path)
        pid, written = doc.get("pid"), _ts(doc.get("started_at"))
        if (not isinstance(pid, int) or written is None or pid == os.getpid()
                or str(doc.get("host") or "") != socket.gethostname()):
            continue
        born = _create_time(pid)
        if born is None or born <= written + REUSED_PID_MARGIN_S:
            continue
        if _is_certifier(_cmdline(pid)):
            continue
        with contextlib.suppress(OSError):
            path.unlink()
            out.append(name)
    return out


def _alive_as(pid: int, create_time: object) -> bool:
    """`pid` is alive AND is the same process that wrote the heartbeat (not a reused pid).

    An unparseable or missing stamp is NOT the same process (audit of 2832cebd1): identity
    cannot be shown, so the pid is treated as gone -- which only ever RECORDS a death, because
    nothing is killed on the dead path."""
    born = _create_time(pid)
    if born is None:
        return False
    try:
        return abs(born - float(str(create_time))) < 2.0
    except (TypeError, ValueError):
        return False


def _tree_cpu_s(sample: dict[str, Any] | None) -> float | None:
    return None if sample is None else float(sum((sample.get("cpu") or {}).values()))


def take_over_stale(now: float | None = None, *, sample_s: float | None = None,
                    sleep: Callable[[float], Any] = time.sleep,
                    sampler: Callable[[int], dict[str, Any] | None] | None = None,
                    ) -> dict[str, Any] | None:
    """THE PRIOR SWEEP, IF IT IS DEAD OR GENUINELY IDLE. Called by every --once before it plans.

    A RUNNING heartbeat whose pid is gone (or cannot be shown to be the same process) is an
    unfinished sweep nobody recorded (an OOM kill, a reboot, a hand kill): it is RECORDED, with
    its missed-growth line, and nothing is killed.

    A live prior sweep is KILLED ONLY ON MEASURED IDLENESS, never on a deadline or a quiet
    heartbeat alone (audit HOLD of 2832cebd1). All four must hold:
      * its heartbeat is at least the no-progress window old;
      * the tree's CPU since that last beat is under NO_PROGRESS_CORES per second elapsed;
      * a live TAKEOVER_SAMPLE_S sample of the tree is idle too;
      * the pid's command line is a `run_sharded_gauntlet.py --once` AND its create_time matches
        the heartbeat's stamp, both checked here in code, immediately before the kill.
    Anything short of that is recorded SLOW and left running.
    """
    hb = _read_json(HEARTBEAT)
    if hb.get("status") != "RUNNING":
        return None
    try:
        pid = int(hb.get("pid") or 0)
    except (TypeError, ValueError):
        return None
    if pid <= 0 or pid == os.getpid():
        return None
    t = time.time() if now is None else now
    beat = _ts(hb.get("beat_utc"))
    age = None if beat is None else t - beat
    if not _alive_as(pid, hb.get("create_time")):
        # THE DEAD SWEEP MAY HAVE DIED MID-WRITE (audit HOLD of b94babf39): the sealed writer is
        # not atomic, so an OOM kill or a reboot inside the merge leaves a torn authority file.
        # Nobody else will repair it -- the next sweep can return 0 without writing it (an empty
        # docket, a firewall HALT) -- so it is put back here, from that sweep's own snapshot.
        restored = restore_merge_outputs(pid=pid, since=_ts(hb.get("started_utc")))
        record_stall("died_unrecorded", detail=(
            f"sweep pid {pid} is gone (or no longer provably the process that wrote the "
            f"heartbeat) and left a RUNNING heartbeat "
            f"{'' if age is None else f'{age:.0f}s old '}in phase {hb.get('phase')}: it was "
            "killed from outside (OOM, reboot, hand kill) before it could record why"
            + (f"; restored {restored}" if restored else "")
            + (f"; NOT restored {dict(_RESTORE_REFUSED)}" if _RESTORE_REFUSED else "")),
            pid=pid, counts=False, last_heartbeat=hb, restored=restored)
        _write_json_atomic(HEARTBEAT, {**hb, "status": "DEAD",
                                       "noticed_utc": _iso(t), "noticed_by": os.getpid()})
        return {"action": "recorded_dead", "pid": pid, "restored": restored}
    # A FRESH BEAT IS ITS OWN WATCHDOG'S BUSINESS, however far past a threshold the sweep is:
    # that watchdog is measuring the tree every beat and kills it the moment it goes idle.
    if age is None or age <= HEARTBEAT_STALE_S:
        return None
    sample = sampler or _sample_tree
    window = no_progress_s()
    reasons: list[str] = []
    then_cpu = (hb.get("tree") or {}).get("cpu_s") if isinstance(hb.get("tree"), dict) else None
    first = sample(pid)
    now_cpu = _tree_cpu_s(first)
    idle_since_beat = False
    if age < window:
        reasons.append(f"heartbeat {age:.0f}s old, under the {window:.0f}s no-progress window")
    elif not isinstance(then_cpu, (int, float)) or now_cpu is None:
        reasons.append("CPU since the last beat is UNMEASURED")
    elif now_cpu < float(then_cpu):
        reasons.append("the tree's CPU total fell since the last beat (processes exited): "
                       "activity, not idleness")
    elif (now_cpu - float(then_cpu)) / age >= NO_PROGRESS_CORES:
        reasons.append(f"the tree burned {now_cpu - float(then_cpu):.0f} cpu-s since its last "
                       f"beat {age:.0f}s ago: it is progressing")
    else:
        idle_since_beat = True
    live_idle = False
    if idle_since_beat:
        span = TAKEOVER_SAMPLE_S if sample_s is None else max(0.0, float(sample_s))
        tracker = _TreeProgress(0.0)
        tracker.update(first, 0.0)
        tracker.last_progress = -1.0           # the first sample is a baseline, not progress
        sleep(span)
        progressing = tracker.update(sample(pid), max(span, 1e-6))
        if progressing is None:
            reasons.append("the live sample is UNMEASURED")
        elif progressing:
            reasons.append(f"a live {span:.0f}s sample shows the tree burning CPU")
        else:
            live_idle = True
    cmd = _cmdline(pid)
    same = _alive_as(pid, hb.get("create_time"))
    if live_idle and not (cmd and "run_sharded_gauntlet" in cmd and "--once" in cmd and same):
        reasons.append(f"identity not proven at kill time (cmdline {cmd!r}, create_time "
                       f"{'matches' if same else 'does not match'})")
        live_idle = False
    quiet = f"heartbeat {age:.0f}s old"
    if not live_idle:
        record_slow("takeover_left_running", detail=(
            f"prior sweep pid {pid}: {quiet}, but NOT killed: {'; '.join(reasons)}"),
            pid=pid, last_heartbeat=hb)
        return {"action": "left_running", "pid": pid, "why": reasons}
    why = (f"{quiet}; its tree burned < {NO_PROGRESS_CORES} core since that beat and over a live "
           f"sample; cmdline and create_time verified")
    kill = _kill_report(_kill_sweep_tree(pid))
    restored = restore_merge_outputs(pid=pid, since=_ts(hb.get("started_utc")))
    record_stall("takeover", detail=(f"sweep pid {pid} {why}; killed {kill.get('killed')} "
                                     f"process(es), orphans {kill.get('orphans')}"),
                 pid=pid, last_heartbeat=hb, kill=kill, restored=restored)
    _write_json_atomic(HEARTBEAT, {**hb, "status": "KILLED_BY_TAKEOVER",
                                   "noticed_utc": _iso(t), "noticed_by": os.getpid()})
    return {"action": "killed", "pid": pid, "killed": kill.get("killed"), "why": why}


class SweepWatchdog:
    """The --once run's own watchdog thread: heartbeat, SLOW thresholds, no-progress, the kill.

    The phase and run thresholds write an amber SLOW record once each and never stop the sweep;
    the one kill is NO PROGRESS, measured per process over the whole tree (`_TreeProgress`).
    Injected `clock`, `sampler`, `lane` and `exit_fn` exist for the tests; production uses wall
    time, psutil, the certification lane's lock file and `os._exit` (the main thread may be deep
    inside the sealed merge, where nothing else can stop it).
    """

    def __init__(self, *, beat_s: float | None = None, clock: Callable[[], float] = time.time,
                 sampler: Callable[[int], dict[str, Any] | None] | None = None,
                 lane: Callable[[], bool] | None = None,
                 exit_fn: Callable[[int], Any] = os._exit,
                 mono: Callable[[], float] | None = None) -> None:
        raw = beat_s if beat_s is not None else (_env_seconds("GAUNTLET_HEARTBEAT_S")
                                                 or WATCHDOG_BEAT_S)
        self.beat_s = max(0.01, min(60.0, float(raw)))      # at least once a minute, always
        self.clock = clock
        self.sampler = sampler or _sample_tree
        self.lane = lane or _holds_lane
        self.exit_fn = exit_fn
        self.started = clock()
        self.consecutive = consecutive_stalls()
        self.times = _read_json(PHASE_TIMES)
        self.run_s = run_deadline_s(self.consecutive, self.times)
        self.idle_s = no_progress_s(self.consecutive)
        self.create_time = _create_time(os.getpid())
        # PROGRESS INTERVALS ARE MONOTONIC (audit of 7cf2ece90): a wall-clock step forward of half
        # an hour (NTP, a VM resume) was one interval and read a busy tree as idle. `clock` stays
        # the wall time the published stamps need; a test that injects one clock gets it for both.
        self.mono = mono or (time.monotonic if clock is time.time else clock)
        self.progress = _TreeProgress(self.mono(), max_gap_s=3.0 * self.beat_s)
        self._idle = 0.0
        self.slow: list[str] = []
        self.beats = 0
        self.wrote = False
        self.breached: dict[str, Any] | None = None
        self.stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def last_progress(self) -> float:
        return self.progress.last_progress

    @property
    def progress_measured(self) -> bool:
        return self.progress.measured

    def start(self) -> SweepWatchdog:
        self._thread = threading.Thread(target=self._loop, name="sweep-watchdog", daemon=True)
        self._thread.start()
        return self

    def _loop(self) -> None:
        while not self.stop.wait(self.beat_s):
            try:
                self.tick()
            except Exception as exc:     # a broken beat goes stale, and the resident acts on it
                with contextlib.suppress(Exception):
                    print(f"sweep watchdog: beat failed: {type(exc).__name__}: {exc}", flush=True)

    def _doc(self, now: float, status: str, sample: dict[str, Any] | None,
             phase: str | None, phase_el: float | None, phase_dl: float | None) -> dict[str, Any]:
        since = _PHASE_DOC.get("_t")
        return {
            "pid": os.getpid(), "create_time": self.create_time, "status": status,
            "started_utc": _iso(self.started), "beat_utc": _iso(now), "beats": self.beats,
            "beat_every_s": self.beat_s, "phase": phase,
            "phase_started_utc": _iso(since) if isinstance(since, float) else None,
            "phase_elapsed_s": None if phase_el is None else round(phase_el, 1),
            "phases_done": dict(_PHASE_DOC.get("phases") or {}),
            "deadlines": {
                "kind": "SLOW thresholds (amber, never a kill); only no_progress_s kills",
                "run_s": round(self.run_s, 1), "run_deadline_utc": _iso(self.started + self.run_s),
                "phase_s": None if phase_dl is None else round(phase_dl, 1),
                "phase_deadline_utc": (_iso(since + phase_dl) if isinstance(since, float)
                                       and phase_dl is not None else None),
                "no_progress_s": round(self.idle_s, 1), "consecutive_stalls": self.consecutive},
            "run_deadline_utc": _iso(self.started + self.run_s),
            "slow": list(self.slow),
            "shards": _progress_snapshot(),
            "tree": (None if sample is None else {k: sample[k] for k in ("procs", "rss_mb")}
                     | {"cpu_s": round(sum(sample["cpu"].values()), 1)}),
            "progress": "MEASURED" if self.progress.measured else "UNMEASURED (no psutil)",
            "last_progress_utc": _iso(now - self._idle),
            "idle_s": round(self._idle, 1),
            "progress_gaps": self.progress.gaps,
        }

    def tick(self) -> dict[str, Any]:
        now = self.clock()
        self.beats += 1
        sample = self.sampler(os.getpid())
        m = self.mono()
        self.progress.update(sample, m)
        self._idle = self.progress.idle_s(m)
        phase = _PHASE_DOC.get("phase")
        since = _PHASE_DOC.get("_t")
        phase_el = now - since if isinstance(since, float) else None
        phase_dl = phase_deadline_s(phase, self.consecutive, self.times)
        slow: list[tuple[str, str]] = []
        if now - self.started > self.run_s and "run_deadline" not in self.slow:
            slow.append(("run_deadline", f"the run passed its {self.run_s:.0f}s SLOW threshold "
                                         f"in phase {phase}"))
        key = f"phase_deadline:{phase}"
        if (phase_dl is not None and phase_el is not None and phase_el > phase_dl
                and key not in self.slow):
            slow.append((key, f"phase {phase} ran {phase_el:.0f}s, past its {phase_dl:.0f}s "
                              "SLOW threshold (3x the longest measured wall)"))
        reason: tuple[str, str] | None = None
        if self.progress.measured and self._idle > self.idle_s:
            reason = ("no_progress", f"the whole process tree burned < {NO_PROGRESS_CORES} core "
                                     f"for {self._idle:.0f}s in phase {phase} "
                                     "(deadlocked, or paging instead of computing)")
        self.slow.extend(k for k, _ in slow)
        doc = self._doc(now, "RUNNING", sample, phase, phase_el, phase_dl)
        if self.wrote or self.lane():
            self.wrote = True
            _write_json_atomic(HEARTBEAT, doc)
            for k, detail in slow:
                # PROGRESSING PAST A THRESHOLD IS AMBER, NOT RED, and the sweep keeps going.
                record_slow(k, detail=f"{detail}; the tree is "
                            + (f"progressing (last {self._idle:.0f}s ago)"
                               if self.progress.measured else "UNMEASURED")
                            + ": left running", last_heartbeat=doc)
        if reason is not None:
            self.breach(reason[0], reason[1], doc)
        return doc

    def breach(self, reason: str, detail: str, doc: dict[str, Any]) -> None:
        _ABORT.set()
        prog = _progress_snapshot()
        shard = ({k: prog.get(k) for k in ("phase", "total", "done", "running", "failed",
                                           "stalled", "slow", "shard_idle_kill_s")}
                 if str(doc.get("phase") or "").endswith("_shards") else None)
        kill = _kill_report(_kill_descendants(os.getpid()))
        restored = restore_merge_outputs(pid=os.getpid())
        released = _release_own_locks()
        record_stall(reason, detail=detail, shard=shard, last_heartbeat=doc,
                     lost_s=round(self.clock() - self.started, 1), kill=kill, restored=restored)
        self.breached = {"reason": reason, "detail": detail, "killed": kill.get("killed"),
                         "orphans": kill.get("orphans"), "locks_released": released,
                         "restored_from_merge_snapshot": restored}
        if self.wrote:
            _write_json_atomic(HEARTBEAT, {**doc, "status": "STALLED", **self.breached})
        for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
            with contextlib.suppress(Exception):
                if stream is not None:
                    stream.flush()
        self.exit_fn(STALL_RC)

    def finish(self, rc: int) -> None:
        self.stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)
        if self.wrote and self.breached is None:
            status = {0: "DONE", LANE_HELD_RC: "LANE_HELD", STALL_RC: "STALLED"}.get(rc, "FAILED")
            now = self.clock()
            _write_json_atomic(HEARTBEAT, {**self._doc(now, status, None, _PHASE_DOC.get("phase"),
                                                       None, None), "rc": rc})


def _sweep_succeeded() -> list[str]:
    """Record the measured walls of a FINISHED sweep and end any run of stalls.

    THE SNAPSHOT IS USED BEFORE IT IS DROPPED (audit HOLD of b94babf39). A sweep can return 0
    without writing the authority files (an empty docket, a firewall HALT), so an output a
    killed sweep tore may still be torn here. It is repaired from the snapshot first, and the
    snapshot is dropped only when every output then parses. Returns what was restored."""
    phases = dict(_PHASE_DOC.get("phases") or {})
    t0 = _PHASE_DOC.get("_t0")
    _record_phase_times(phases=phases,
                        sweep_s=(time.time() - t0) if isinstance(t0, float) else None)
    restored: list[str] = []
    with contextlib.suppress(Exception):
        restored = restore_merge_outputs()
    if restored or _RESTORE_REFUSED:
        with contextlib.suppress(Exception):
            print(f"{datetime.now(UTC).isoformat()} finished sweep: merge outputs restored "
                  f"{restored}, not restored {dict(_RESTORE_REFUSED)}", flush=True)
    _record_clear()
    _drop_merge_snapshot()
    return restored


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if _resident_enabled(argv):
        return resident(limit_s=_task_limit_s())
    return _sweep_once()


def _sweep_once() -> int:
    # THE WATCHDOG STARTS FIRST, before anything that could block: it is the only thing in this
    # process that can end a run the sealed judge never returns from.
    dog = SweepWatchdog().start()
    rc = 1
    try:
        from research.judging_throughput import apply_env

        apply_env()
        _phase("plan")
        rc = _sweep_logged()
        return rc
    finally:
        dog.finish(rc)


def _sweep_logged() -> int:
    log_path = DESK / "logs" / "MT5-Gauntlet.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        old_out, old_err = sys.stdout, sys.stderr
        # WHERE THE PLAN IS (judge_plan_progress): the judge's own log lines name its step, and
        # the sealed image's progress hook, where it has one, its counts. Reports only.
        from scripts.judge_plan_progress import PlanTracker
        plan = PlanTracker(_PHASE_DOC, SWEEP_PHASE, on_phase=_phase)
        plan.step("lane_and_docket")
        sys.stdout = sys.stderr = plan.tee(log)
        try:
            # THE PRIOR SWEEP FIRST: a dead one is recorded, a stuck one is killed, and a lock
            # held by a reused pid is cleared -- so this run can never wait behind a corpse.
            try:
                took, reclaimed = take_over_stale(), _reclaim_reused_locks()
            except Exception as exc:     # the takeover is a rail, never a reason not to judge
                took, reclaimed = {"error": f"{type(exc).__name__}: {exc}"}, []
            if took or reclaimed:
                print(f"{datetime.now(UTC).isoformat()} prior sweep: {took} "
                      f"reclaimed locks={reclaimed}", flush=True)
            print(
                f"{datetime.now(UTC).isoformat()} canonical sharded judge "
                f"runtime={sys.executable} shards={_shards()} "
                f"shard_concurrency={_parallelism(_shards())}",
                flush=True,
            )
            from scripts import external_gauntlet as judge
            plan.attach(judge)

            if getattr(judge, "SHARD_PROTOCOL", None) != 2:
                raise RuntimeError(
                    "canonical judge does not expose the required fail-closed shard protocol v2"
                )
            def _timed_dispatch(shard_dir: Path, n: int, phase: str) -> None:
                _phase(f"{phase}_shards")
                dispatch(shard_dir, n, phase)
                # after `build`: collect + cut; after `rule`: the single-process merge + publish
                if phase == "build":
                    _phase("collect_and_cut")
                else:
                    _phase("merge_and_publish")
                    # A kill mid-write must never leave the authority files unparseable.
                    with contextlib.suppress(Exception):
                        snapshot_merge_outputs()

            try:
                rc = int(judge.run_sharded(_shards(), _timed_dispatch))
            except ShardStalled as exc:
                print(f"{datetime.now(UTC).isoformat()} sweep stopped: {exc}", flush=True)
                return STALL_RC
            _phase("done")
            with contextlib.suppress(Exception):   # bookkeeping: never a reason to fail a sweep
                record_resume_delay(rc)
            if rc == 0:
                _sweep_succeeded()
            return rc
        finally:
            sys.stdout, sys.stderr = old_out, old_err


if __name__ == "__main__":
    raise SystemExit(main())
