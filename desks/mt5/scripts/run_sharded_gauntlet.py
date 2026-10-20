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
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any
from uuid import uuid4

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _path in (str(ROOT), str(DESK)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from libs.ops.proctree import run  # noqa: E402


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
#: So the --once child now watches itself, and its ceilings are PER PHASE and PER SHARD, sized
#: from what each phase measured -- never one sum that a single slow sweep inflates for good:
#:   * every shard child has a wall-clock timeout; one past it is killed with its tree, the wave
#:     stops handing out work, a named stall is written and the run exits non-zero;
#:   * every phase has a deadline, the run has one, and a whole tree that burns no CPU for
#:     `NO_PROGRESS_S` is stalled whatever its deadline says (a deadlock, a thrashing pager);
#:   * a heartbeat with the progress counts is written at least every minute while the run holds
#:     the certification lane;
#:   * on any breach: the stall artifact names the shard / phase and the last progress, every
#:     descendant is killed (frozen first, so a respawn cannot orphan one), the run's own job
#:     locks are released, and the process exits STALL_RC so the next trigger starts fresh.
#: Nothing is ever marked judged by any of this: the sealed protocol deletes every `shard_*.pkl`
#: when the next plan is written and fails the merge closed on a missing or stale one, so an
#: unfinished shard's cells are simply planned again.
HEARTBEAT = DESK / "reports" / "GAUNTLET_HEARTBEAT.json"
STALL = DESK / "reports" / "GAUNTLET_STALL.json"
#: Measured phase / shard / sweep wall seconds of SUCCESSFUL sweeps (bounded history).
PHASE_TIMES = DESK / "data" / "judge_phase_times.json"
#: THE SEED, until this box has recorded its own: the largest wall each phase took over the six
#: sweeps the resident published between 2026-10-15 and 2026-10-18 (JUDGE_RESIDENT.json history;
#: merge = the next sweep's `last_sweep_ended_utc` minus the merge phase start, 4,340..6,108 s).
MEASURED_PHASE_S: dict[str, float] = {
    "plan": 10705.9, "build_shards": 42781.5, "collect_and_cut": 1235.2,
    "rule_shards": 819.3, "merge_and_publish": 6108.0}
#: The longest successful sweep the resident has measured (JUDGE_RESIDENT.json, 2026-10-16).
MEASURED_SWEEP_S = 61110.9
PHASE_DEADLINE_MULT = 3.0
PHASE_DEADLINE_FLOOR_S = 3600.0
SHARD_TIMEOUT_MULT = 3.0
SHARD_TIMEOUT_FLOOR_S = 1800.0
RUN_DEADLINE_MULT = 2.0
RUN_DEADLINE_FLOOR_S = 4 * 3600.0
#: The tree burned under this many cores in every heartbeat interval for this long: stalled.
NO_PROGRESS_S = 1800.0
NO_PROGRESS_CORES = 0.02
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

#: Shard progress for the heartbeat, written by `dispatch` and read by the watchdog thread.
_PROGRESS: dict[str, Any] = {}
_PROGRESS_LOCK = threading.Lock()
#: Set by the watchdog before it kills the tree, so `dispatch` starts no new shard meanwhile.
_ABORT = threading.Event()


class ShardTimeout(RuntimeError):
    """A shard child ran past its wall-clock timeout and was killed with its tree."""

    def __init__(self, phase: str, k: int, timeout_s: float) -> None:
        super().__init__(f"{phase} shard {k} exceeded its {timeout_s:.0f}s wall-clock timeout")
        self.phase, self.k, self.timeout_s = phase, k, timeout_s


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


def phase_deadline_s(phase: str | None, consecutive: int | None = None,
                     times: dict[str, Any] | None = None) -> float | None:
    """The most one phase of a sweep may take: 3x its longest measured wall, never under an hour.

    GAUNTLET_PHASE_DEADLINE_S overrides every phase (an operator ceiling); the closing `done`
    has none.
    """
    if not phase or phase == "done":
        return None
    c = consecutive_stalls() if consecutive is None else consecutive
    forced = _env_seconds("GAUNTLET_PHASE_DEADLINE_S")
    if forced is not None:
        return _widen(forced, c)
    doc = times if times is not None else _read_json(PHASE_TIMES)
    longest = (_history_max((doc.get("phases") or {}).get(phase))
               or MEASURED_PHASE_S.get(phase) or max(MEASURED_PHASE_S.values()))
    return _widen(max(PHASE_DEADLINE_FLOOR_S, PHASE_DEADLINE_MULT * longest), c)


def shard_timeout_s(phase: str, consecutive: int | None = None,
                    times: dict[str, Any] | None = None) -> float:
    """One shard child's wall-clock timeout: 3x the longest shard this box measured for the phase,
    never under 30 minutes. Before any shard is measured: the longest whole WAVE measured for the
    phase -- a single shard has never needed longer than its entire wave."""
    c = consecutive_stalls() if consecutive is None else consecutive
    forced = _env_seconds("GAUNTLET_SHARD_TIMEOUT_S")
    if forced is not None:
        return _widen(forced, c)
    doc = times if times is not None else _read_json(PHASE_TIMES)
    longest = _history_max((doc.get("shards") or {}).get(phase))
    if longest is not None:
        base = max(SHARD_TIMEOUT_FLOOR_S, SHARD_TIMEOUT_MULT * longest)
    else:
        wave = (_history_max((doc.get("phases") or {}).get(f"{phase}_shards"))
                or MEASURED_PHASE_S.get(f"{phase}_shards") or max(MEASURED_PHASE_S.values()))
        base = max(SHARD_TIMEOUT_FLOOR_S, wave)
    return _widen(base, c)


def run_deadline_s(consecutive: int | None = None, times: dict[str, Any] | None = None) -> float:
    """The whole --once run's backstop: twice the longest successful sweep, never under 4 h."""
    c = consecutive_stalls() if consecutive is None else consecutive
    forced = _env_seconds("GAUNTLET_RUN_DEADLINE_S")
    if forced is not None:
        return _widen(forced, c)
    doc = times if times is not None else _read_json(PHASE_TIMES)
    longest = _history_max(doc.get("sweeps")) or MEASURED_SWEEP_S
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


def record_stall(reason: str, *, detail: str = "", shard: dict[str, Any] | None = None,
                 pid: int | None = None, counts: bool = True,
                 last_heartbeat: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write GAUNTLET_STALL.json: STALLED, why, where, and the last progress seen.

    `counts` False records an unfinished sweep whose cause is unknown (its pid vanished with no
    final record) without widening the next ceilings: only a breach that was measured does.
    """
    prev = _read_json(STALL)
    consecutive = int(prev.get("consecutive") or 0) + (1 if counts else 0)
    hb = last_heartbeat if last_heartbeat is not None else _read_json(HEARTBEAT)
    row = {"status": "STALLED", "reason": reason, "detail": detail[:600],
           "stalled_utc": datetime.now(UTC).isoformat(timespec="seconds"),
           "pid": pid if pid is not None else os.getpid(),
           "phase": hb.get("phase") or _PHASE_DOC.get("phase"),
           "shard": shard,
           "last_progress": {k: hb.get(k) for k in (
               "beat_utc", "phase", "phase_elapsed_s", "shards", "tree", "last_progress_utc",
               "idle_s") if k in hb},
           "counts_toward_widening": counts}
    history = [*(prev.get("history") or []), row][-STALL_HISTORY:]
    doc = {**row, "consecutive": consecutive, "history": history,
           "last_clear_utc": prev.get("last_clear_utc"),
           "next_run": ("starts fresh: the sealed protocol re-plans every unfinished shard's "
                        "cells; nothing from the stalled run was marked judged")}
    _write_json_atomic(STALL, doc)
    with contextlib.suppress(Exception):
        print(f"{datetime.now(UTC).isoformat()} GAUNTLET STALL: {reason} -- {detail}", flush=True)
    return doc


def _record_clear() -> None:
    """A sweep finished: the stall run is over (history kept), so the fence reads green again."""
    prev = _read_json(STALL)
    if not prev:
        return
    _write_json_atomic(STALL, {**{k: v for k, v in prev.items() if k != "status"},
                               "status": "CLEAR", "consecutive": 0,
                               "last_clear_utc": datetime.now(UTC).isoformat(
                                   timespec="seconds")})


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
    # EVERY SHARD HAS A WALL-CLOCK CEILING (2026-10-20). `timeout=None` here meant one shard that
    # never returned held the wave -- and with it the sweep, the certification lane and the
    # task's one instance -- forever. `proctree.run` kills the child's WHOLE tree on timeout.
    timeout_s = shard_timeout_s(phase)
    abort_wave = threading.Event()
    walls: list[float] = []
    walls_lock = threading.Lock()
    _progress_set(phase=phase, total=n, done=0, failed=0, running=0, timed_out=0, retrying=0,
                  shard_timeout_s=round(timeout_s, 1),
                  wave_started_utc=datetime.now(UTC).isoformat(timespec="seconds"))

    def one(k: int, attempt: int = 0) -> None:
        if _ABORT.is_set() or abort_wave.is_set():
            raise RuntimeError(f"{phase} shard {k} not started: the wave was aborted")
        receipt = logs / f"{invocation}-{phase}-{k}-attempt-{attempt}.log"
        with receipt.open("wb") as output:
            output.write(f"{datetime.now(UTC).isoformat()} {phase} shard={k} "
                         f"attempt={attempt} timeout_s={timeout_s:.0f}\n".encode())
            output.flush()
            t0 = time.monotonic()
            _progress_bump("running")
            try:
                child_env = {**os.environ, "GAUNTLET_PEAK_RECEIPT": str(
                    logs / f"{invocation}-{phase}-{k}-attempt-{attempt}.peak.json")}
                try:
                    run([sys.executable, "-u", "-c", code, str(shard_dir), str(k), phase],
                        cwd=DESK, env=child_env, timeout=timeout_s, capture_output=False,
                        stdout=output, stderr=output, check=True)
                except subprocess.TimeoutExpired as exc:
                    raise ShardTimeout(phase, k, timeout_s) from exc
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
                if isinstance(exc, ShardTimeout):
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
        except ShardTimeout as exc:
            # A HUNG SHARD ENDS THE WAVE: the rest would be merged with a hole and refused, so
            # nothing more is started; shards already running finish or meet their own ceiling.
            abort_wave.set()
            _progress_bump("timed_out")
            return k, exc
        except Exception as exc:  # child exit/OOM is evidence, then retried below
            _progress_bump("failed")
            return k, exc
        return k, None

    def stalled(exc: ShardTimeout, not_started: int = 0) -> ShardTimeout:
        record_stall("shard_timeout", detail=(
            f"{exc}; killed with its process tree"
            + (f"; {not_started} shard(s) of the wave were not started" if not_started else "")),
            shard={"phase": phase, "k": exc.k, "timeout_s": round(exc.timeout_s, 1),
                   "receipt_glob": str(logs / f"{invocation}-{phase}-{exc.k}-attempt-*.log")})
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

    timeouts = [exc for _k, exc in first if isinstance(exc, ShardTimeout)]
    if timeouts:
        skipped = sum(1 for _k, exc in first
                      if exc is not None and not isinstance(exc, ShardTimeout)
                      and "the wave was aborted" in str(exc))
        raise stalled(timeouts[0], skipped)
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
            except ShardTimeout as exc:
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
#: measured, whichever is larger, never under an hour -- and a child past it is killed WITH ITS
#: WHOLE TREE (`libs.ops.proctree.run`), recorded as a hung sweep, and the next one starts.
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


def _kill_sweep_tree(pid: int, *, rounds: int = 20) -> int:
    """Kill a sweep and every descendant (see `_kill_tree`)."""
    return _kill_tree(pid, rounds=rounds, include_root=True)


def _kill_descendants(pid: int, *, rounds: int = 20) -> int:
    """Kill every descendant of `pid` (the watchdog's own process), never `pid` itself."""
    return _kill_tree(pid, rounds=rounds, include_root=False)


def _kill_tree(pid: int, *, rounds: int = 20, include_root: bool = True) -> int:
    """Kill a sweep and EVERY descendant, including shards its dispatch respawns mid-kill.

    Audit of #350: snapshot-then-kill left orphans in 2 of 5 probes, because the root's retry
    loop and executor started new shards after the snapshot -- and on the box an orphan becomes
    the oldest external_gauntlet, which StallWatch keeps while it kills the NEXT sweep's shards.
    So the root is SUSPENDED first (it can start nothing), then descendants are re-enumerated,
    suspended and killed until a pass finds none, then the root dies. Returns processes killed.
    """
    try:
        import psutil
    except ImportError:                                        # pragma: no cover - box has it
        return 0
    try:
        root = psutil.Process(pid)
        if include_root:              # a process never freezes itself: its own kill would stop
            root.suspend()
    except psutil.Error:
        return 0
    killed = 0
    for _ in range(rounds):
        try:
            kids = root.children(recursive=True)
        except psutil.Error:
            break
        if not kids:
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
                kids = root.children(recursive=True)
            except psutil.Error:
                break
        kids = list(frozen.values())
        for k in kids:
            with contextlib.suppress(psutil.Error):
                k.kill()
                killed += 1
        psutil.wait_procs(kids, timeout=5)
    if include_root:
        with contextlib.suppress(psutil.Error):
            root.kill()
            killed += 1
            root.wait(timeout=10)
    return killed


def _child_breach(pid: int, now: float) -> str | None:
    """Why the resident must kill sweep `pid` now, read from ITS heartbeat, or None.

    The second line of defence: the child's own watchdog thread normally acts first. If that
    thread is wedged its heartbeat goes stale, and if it is alive but failed to act the run is
    past its own published deadline; either way the resident, a different process, acts.
    """
    hb = _read_json(HEARTBEAT)
    if hb.get("pid") != pid or hb.get("status") != "RUNNING":
        return None
    beat = _ts(hb.get("beat_utc"))
    if beat is not None and now - beat > HEARTBEAT_STALE_S:
        return f"its heartbeat is {now - beat:.0f}s old: the sweep's own watchdog is wedged"
    deadline = _ts(hb.get("run_deadline_utc"))
    if deadline is not None and now > deadline + HEARTBEAT_STALE_S:
        return f"it is past its own run deadline {hb.get('run_deadline_utc')} and still running"
    return None


def _one_sweep_child(hang_s: float | None = None, *, poll_s: float = 60.0,
                     clock: Callable[[], float] = time.monotonic,
                     wall: Callable[[], float] = time.time) -> int:
    """One sweep in a fresh process, at the priority the scheduler gives the judge today."""
    flags = 0
    if sys.platform == "win32":
        # BELOW_NORMAL is the Task Scheduler's default priority (7) for MT5-Gauntlet, so the
        # child keeps exactly the standing the judge has now: miners are never displaced by it.
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    child = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "--once"],
                             cwd=DESK, env=_sweep_env(), creationflags=flags)
    deadline = None if hang_s is None else clock() + float(hang_s)
    while True:
        wait_s = poll_s if deadline is None else max(0.0, min(poll_s, deadline - clock()))
        try:
            return int(child.wait(timeout=wait_s))
        except subprocess.TimeoutExpired:
            pass
        why = _child_breach(child.pid, wall())
        if why is None and deadline is not None and clock() >= deadline:
            why = f"the resident's {hang_s:.0f}s hang ceiling was reached"
        if why is None:
            continue
        hb = _read_json(HEARTBEAT)
        _kill_sweep_tree(child.pid)
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=30)
        record_stall("resident_kill", detail=f"sweep pid {child.pid}: {why}", pid=child.pid,
                     last_heartbeat=hb if hb.get("pid") == child.pid else {})
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
    rss = 0.0
    for p in procs:
        try:
            t = p.cpu_times()
            cpu[p.pid] = float(t.user) + float(t.system)
            rss += float(p.memory_info().rss)
        except Exception:
            continue
    return {"cpu": cpu, "rss_mb": round(rss / (1024.0 * 1024.0), 1), "procs": len(cpu)}


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


def _reclaim_reused_locks() -> list[str]:
    """A sweep lock whose pid now names a process STARTED AFTER the lock was written is a dead
    owner's lock and a reused pid. `job_lock` reads such an owner as ALIVE and never reclaims it,
    which would refuse every sweep forever; it is removed here, and only here."""
    import socket

    root = _lock_root()
    out: list[str] = []
    if root is None:
        return out
    for name in SWEEP_LOCKS:
        path = root / f"{name}.json"
        doc = _read_json(path)
        pid, written = doc.get("pid"), _ts(doc.get("started_at"))
        if (not isinstance(pid, int) or written is None
                or str(doc.get("host") or "") != socket.gethostname()):
            continue
        born = _create_time(pid)
        if born is not None and born > written + 5.0:
            with contextlib.suppress(OSError):
                path.unlink()
                out.append(name)
    return out


def _alive_as(pid: int, create_time: object) -> bool:
    """`pid` is alive AND is the same process that wrote the heartbeat (not a reused pid)."""
    born = _create_time(pid)
    if born is None:
        return False
    try:
        return abs(born - float(str(create_time))) < 2.0
    except (TypeError, ValueError):
        return True                    # the writer could not stamp it: liveness alone


def take_over_stale(now: float | None = None) -> dict[str, Any] | None:
    """THE PRIOR SWEEP, IF IT IS DEAD OR STUCK. Called by every --once before it plans.

    A RUNNING heartbeat whose pid is gone is an unfinished sweep nobody recorded (an OOM kill, a
    reboot, a hand kill): it is recorded as one. A RUNNING heartbeat whose pid is alive but which
    has not beaten in HEARTBEAT_STALE_S, or which is past its run deadline, belongs to a sweep
    whose watchdog could not act: its whole tree is killed so its locks fall to `job_lock`'s
    dead-owner rule, and the stall is recorded. Anything else is left alone.
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
        record_stall("died_unrecorded", detail=(
            f"sweep pid {pid} is gone and left a RUNNING heartbeat "
            f"{'' if age is None else f'{age:.0f}s old '}in phase {hb.get('phase')}: it was "
            "killed from outside (OOM, reboot, hand kill) before it could record why"),
            pid=pid, counts=False, last_heartbeat=hb)
        _write_json_atomic(HEARTBEAT, {**hb, "status": "DEAD",
                                       "noticed_utc": _iso(t), "noticed_by": os.getpid()})
        return {"action": "recorded_dead", "pid": pid}
    deadline = _ts(hb.get("run_deadline_utc"))
    stale = age is not None and age > HEARTBEAT_STALE_S
    past = deadline is not None and t > deadline + HEARTBEAT_STALE_S
    if not (stale or past):
        return None
    why = (f"heartbeat {age:.0f}s old (> {HEARTBEAT_STALE_S:.0f}s): its watchdog is wedged"
           if stale else f"past its run deadline {hb.get('run_deadline_utc')} and still running")
    killed = _kill_sweep_tree(pid)
    record_stall("takeover", detail=f"sweep pid {pid} {why}; killed {killed} process(es)",
                 pid=pid, last_heartbeat=hb)
    _write_json_atomic(HEARTBEAT, {**hb, "status": "KILLED_BY_TAKEOVER",
                                   "noticed_utc": _iso(t), "noticed_by": os.getpid()})
    return {"action": "killed", "pid": pid, "killed": killed, "why": why}


class SweepWatchdog:
    """The --once run's own watchdog thread: heartbeat, deadlines, no-progress, and the kill.

    Injected `clock`, `sampler`, `lane` and `exit_fn` exist for the tests; production uses wall
    time, psutil, the certification lane's lock file and `os._exit` (the main thread may be deep
    inside the sealed merge, where nothing else can stop it).
    """

    def __init__(self, *, beat_s: float | None = None, clock: Callable[[], float] = time.time,
                 sampler: Callable[[int], dict[str, Any] | None] | None = None,
                 lane: Callable[[], bool] | None = None,
                 exit_fn: Callable[[int], Any] = os._exit) -> None:
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
        self.last_progress = self.started
        self.progress_measured = False
        self._cpu: dict[int, float] = {}
        self._last_t: float | None = None
        self.beats = 0
        self.wrote = False
        self.breached: dict[str, Any] | None = None
        self.stop = threading.Event()
        self._thread: threading.Thread | None = None

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
                "run_s": round(self.run_s, 1), "run_deadline_utc": _iso(self.started + self.run_s),
                "phase_s": None if phase_dl is None else round(phase_dl, 1),
                "phase_deadline_utc": (_iso(since + phase_dl) if isinstance(since, float)
                                       and phase_dl is not None else None),
                "no_progress_s": round(self.idle_s, 1), "consecutive_stalls": self.consecutive},
            "run_deadline_utc": _iso(self.started + self.run_s),
            "shards": _progress_snapshot(),
            "tree": (None if sample is None else {k: sample[k] for k in ("procs", "rss_mb")}
                     | {"cpu_s": round(sum(sample["cpu"].values()), 1)}),
            "progress": "MEASURED" if sample is not None else "UNMEASURED (no psutil)",
            "last_progress_utc": _iso(self.last_progress),
            "idle_s": round(now - self.last_progress, 1),
        }

    def tick(self) -> dict[str, Any]:
        now = self.clock()
        self.beats += 1
        sample = self.sampler(os.getpid())
        if sample is not None:
            self.progress_measured = True
            cpu = sample["cpu"]
            # PER PROCESS, so a shard that exits (taking its CPU total with it) never reads as a
            # negative or as progress; a new process counts all it has burned.
            delta = sum(max(0.0, v - self._cpu.get(p, 0.0)) for p, v in cpu.items())
            dt = now - (self._last_t if self._last_t is not None else self.started)
            if dt <= 0 or delta / dt >= NO_PROGRESS_CORES:
                self.last_progress = now
            self._cpu, self._last_t = dict(cpu), now
        phase = _PHASE_DOC.get("phase")
        since = _PHASE_DOC.get("_t")
        phase_el = now - since if isinstance(since, float) else None
        phase_dl = phase_deadline_s(phase, self.consecutive, self.times)
        reason: tuple[str, str] | None = None
        if now - self.started > self.run_s:
            reason = ("run_deadline", f"the run passed its {self.run_s:.0f}s deadline "
                                      f"in phase {phase}")
        elif phase_dl is not None and phase_el is not None and phase_el > phase_dl:
            reason = (f"phase_deadline:{phase}", f"phase {phase} ran {phase_el:.0f}s, past its "
                                                 f"{phase_dl:.0f}s deadline (3x its longest "
                                                 "measured wall, widened per consecutive stall)")
        elif self.progress_measured and now - self.last_progress > self.idle_s:
            reason = ("no_progress", f"the whole process tree burned < {NO_PROGRESS_CORES} core "
                                     f"for {now - self.last_progress:.0f}s in phase {phase} "
                                     "(deadlocked, or paging instead of computing)")
        doc = self._doc(now, "RUNNING", sample, phase, phase_el, phase_dl)
        if self.wrote or self.lane():
            self.wrote = True
            _write_json_atomic(HEARTBEAT, doc)
        if reason is not None:
            self.breach(reason[0], reason[1], doc)
        return doc

    def breach(self, reason: str, detail: str, doc: dict[str, Any]) -> None:
        _ABORT.set()
        prog = _progress_snapshot()
        shard = ({k: prog.get(k) for k in ("phase", "total", "done", "running", "failed",
                                           "timed_out", "shard_timeout_s")}
                 if str(doc.get("phase") or "").endswith("_shards") else None)
        record_stall(reason, detail=detail, shard=shard, last_heartbeat=doc)
        killed = _kill_descendants(os.getpid())
        released = _release_own_locks()
        self.breached = {"reason": reason, "detail": detail, "killed": killed,
                         "locks_released": released}
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


def _sweep_succeeded() -> None:
    """Record the measured walls of a FINISHED sweep and end any run of stalls."""
    phases = {k: v for k, v in (_PHASE_DOC.get("phases") or {}).items()}
    t0 = _PHASE_DOC.get("_t0")
    _record_phase_times(phases=phases,
                        sweep_s=(time.time() - t0) if isinstance(t0, float) else None)
    _record_clear()


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
        sys.stdout = sys.stderr = log
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

            if getattr(judge, "SHARD_PROTOCOL", None) != 2:
                raise RuntimeError(
                    "canonical judge does not expose the required fail-closed shard protocol v2"
                )
            def _timed_dispatch(shard_dir: Path, n: int, phase: str) -> None:
                _phase(f"{phase}_shards")
                dispatch(shard_dir, n, phase)
                # after `build`: collect + cut; after `rule`: the single-process merge + publish
                _phase("collect_and_cut" if phase == "build" else "merge_and_publish")

            try:
                rc = int(judge.run_sharded(_shards(), _timed_dispatch))
            except ShardTimeout as exc:
                print(f"{datetime.now(UTC).isoformat()} sweep stopped: {exc}", flush=True)
                return STALL_RC
            _phase("done")
            if rc == 0:
                _sweep_succeeded()
            return rc
        finally:
            sys.stdout, sys.stderr = old_out, old_err


if __name__ == "__main__":
    raise SystemExit(main())
