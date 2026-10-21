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

    def one(k: int, attempt: int = 0) -> None:
        receipt = logs / f"{invocation}-{phase}-{k}-attempt-{attempt}.log"
        started = time.monotonic()
        _shard_progress("start", phase, attempt=attempt)
        try:
            _one(k, attempt, receipt)
        except BaseException:
            _shard_progress("failed", phase, elapsed_s=time.monotonic() - started)
            raise
        _shard_progress("ok", phase, elapsed_s=time.monotonic() - started)

    def _one(k: int, attempt: int, receipt: Path) -> None:
        with receipt.open("wb") as output:
            output.write(f"{datetime.now(UTC).isoformat()} {phase} shard={k} "
                         f"attempt={attempt}\n".encode())
            output.flush()
            try:
                child_env = {**os.environ, "GAUNTLET_PEAK_RECEIPT": str(
                    logs / f"{invocation}-{phase}-{k}-attempt-{attempt}.peak.json")}
                run([sys.executable, "-u", "-c", code, str(shard_dir), str(k), phase],
                    cwd=DESK, env=child_env, timeout=None, capture_output=False,
                    stdout=output, stderr=output, check=True)
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
                raise RuntimeError(f"{phase} shard {k} failed; child log={receipt}") from exc
            output.seek(0, os.SEEK_END)
            output.write(f"{datetime.now(UTC).isoformat()} CHILD_EXIT_OK\n".encode())
            output.flush()

    def attempted(k: int) -> tuple[int, Exception | None]:
        try:
            one(k)
        except Exception as exc:  # child exit/OOM is evidence, then retried below
            return k, exc
        return k, None

    width = _parallelism(n, phase)
    _shard_progress("begin", phase, total=n)
    print(f"SHARD WAVE: {phase} x{n} at concurrency {width} (recorded peak "
          f"{_shard_peak_mb(phase)} MB, available {_available_mb()} MB)", flush=True)
    with ThreadPoolExecutor(max_workers=width, thread_name_prefix=f"judge-{phase}") as pool:
        # Consume every result even when one child fails, so successful shard artifacts survive.
        first = list(pool.map(attempted, range(n)))
    _record_peaks(logs, invocation, phase)

    failed = [(k, exc) for k, exc in first if exc is not None]
    if failed:
        print(f"SHARD RECOVERY: {len(failed)}/{n} {phase} shard(s) failed in parallel; "
              "retrying only those shards serially after peer memory was released", flush=True)
    for k, first_exc in failed:
        assert first_exc is not None
        last_exc = first_exc
        for attempt in range(1, _retry_attempts() + 1):
            try:
                one(k, attempt)
                print(f"SHARD RECOVERY: {phase} shard {k} recovered on retry {attempt}",
                      flush=True)
                break
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
#:
#: SCHEMA OF JUDGE_SWEEP_PHASE.json (also published as JUDGE_RESIDENT.json["sweep_phase"]).
#: The pager v4 contract reads ONLY `pid`, `sweep_started_utc`, `phase`, `phase_started_utc`;
#: those four names and meanings are fixed. Top-level `phase` is the LAUNCHER's phase name, one
#: of plan, build_shards, collect_and_cut, rule_shards, merge_and_publish, done; `phases` maps
#: each closed phase to the seconds it took. While a shard wave runs, `shards` is present:
#:   shards.phase      the JUDGE's protocol phase name, "build" or "rule". It is NOT the
#:                     top-level name: top-level `phase` == shards.phase + "_shards" while that
#:                     wave runs (build -> build_shards, rule -> rule_shards). The judge's name is
#:                     kept because it is what the sealed judge passes to dispatch.
#:   total             shards in the wave (each shard index counted once).
#:   started           child ATTEMPTS started, retries included -- not shards; can exceed total.
#:   done_ok           child attempts that exited ok. A shard succeeds at most once, so this is
#:                     also the count of shards done, <= total.
#:   failed            child ATTEMPTS that failed, a shard counted once per failed attempt -- not
#:                     shards; failed=4 beside done_ok=5 of total=6 is legal (retries succeeded).
#:   retries           attempts with attempt index > 0.
#:   running           attempts started and not yet exited.
#:   last_finish_epoch/last_finish_utc   the last attempt EXIT, ok or failed.
#:   longest_shard_s   the longest SUCCESSFUL attempt in the wave; None until one succeeds. A
#:                     failed attempt never sets it: a shard that OOMs in 3 s says nothing about
#:                     how long a healthy shard takes.
#:   seconds_since_last_finish   re-derived against the clock on every read.
#:   stalled_hint      REPORT-ONLY (III.16 declared): no organ acts on it yet; the pager does not
#:                     read `shards`. It is true only when done_ok > 0, running > 0 and the gap
#:                     since the last finish exceeds longest_shard_s. Never true from absence.
#:   stalled_hint_authority   always "report_only" until a consumer is wired; a consumer must
#:                     change this string in the same commit that starts acting on the hint.
SWEEP_PHASE = DESK / "reports" / "JUDGE_SWEEP_PHASE.json"
STALLED_HINT_AUTHORITY = "report_only"
_PHASE_DOC: dict[str, Any] = {}
#: Guards `_PHASE_DOC` and its file: dispatch stamps shard progress from concurrent children.
_PHASE_LOCK = threading.Lock()
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


def _write_atomic(path: Path, doc: dict[str, Any]) -> None:
    """Write `doc` to `path` through a per-pid/thread tmp and os.replace. A report only: an
    OSError is swallowed. The tmp is unlinked in `finally`, so a failed replace (on NTFS the
    destination held open by a reader, or read-only) never leaves one behind -- and with a
    per-thread name, leftovers would otherwise multiply."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # a report; judging never stops for it
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def _flush_phase_doc() -> None:
    """Atomically publish `_PHASE_DOC` to SWEEP_PHASE. Caller holds `_PHASE_LOCK`."""
    _write_atomic(SWEEP_PHASE, {k: v for k, v in _PHASE_DOC.items() if k != "_t"})


def _phase(name: str) -> None:
    """Close the current sweep phase and open `name`, stamped to SWEEP_PHASE."""
    now = time.time()
    with _PHASE_LOCK:
        doc = _PHASE_DOC
        if not doc:
            doc.update(pid=os.getpid(), sweep_started_utc=datetime.now(UTC).isoformat(
                timespec="seconds"), phases={})
        prev, since = doc.get("phase"), doc.get("_t")
        if prev and isinstance(since, float):
            doc["phases"][prev] = round(doc["phases"].get(prev, 0.0) + now - since, 1)
        # shard progress describes the CURRENT phase only; a new phase starts without it
        doc.pop("shards", None)
        doc.update(phase=name, phase_started_utc=datetime.now(UTC).isoformat(
            timespec="seconds"), _t=now)
        _flush_phase_doc()


def _shard_live(shards: dict[str, Any], now: float) -> dict[str, Any]:
    """Refresh the time-derived fields of a shard-progress block against `now`.

    `stalled_hint` is a REPORT-ONLY HINT, never a verdict: it is true only when at least one
    shard has SUCCEEDED, at least one is still running, and the gap since the last finish
    exceeds the longest successful shard time measured so far in this phase. Nothing succeeded
    yet is UNMEASURED -- the hint stays false, because a hang is never inferred from absence,
    and a fast failure (an early OOM) is not a measure of how long a healthy shard runs.
    """
    out = dict(shards)
    last = out.get("last_finish_epoch")
    longest = out.get("longest_shard_s")
    since = round(max(0.0, now - float(last)), 1) if isinstance(last, (int, float)) else None
    out["seconds_since_last_finish"] = since
    out["stalled_hint"] = bool(
        since is not None and isinstance(longest, (int, float))
        and int(out.get("done_ok") or 0) > 0
        and int(out.get("running") or 0) > 0 and since > float(longest))
    out["stalled_hint_authority"] = STALLED_HINT_AUTHORITY
    return out


def _shard_progress(event: str, phase: str, *, total: int | None = None,
                    attempt: int = 0, elapsed_s: float | None = None) -> None:
    """Fold one dispatch event into the current phase's shard progress and publish it.

    `event` is "begin" (a wave of `total` shards is about to start), "start" (a child attempt
    started), "ok" or "failed" (a child attempt exited after `elapsed_s`). Children run
    concurrently, so every update and write happens under `_PHASE_LOCK`. A report only:
    nothing here can raise into dispatch.
    """
    try:
        now = time.time()
        with _PHASE_LOCK:
            sh = _PHASE_DOC.get("shards")
            if event == "begin" or not isinstance(sh, dict) or sh.get("phase") != phase:
                sh = {"phase": phase, "total": int(total or 0), "started": 0, "done_ok": 0,
                      "failed": 0, "retries": 0, "running": 0, "last_finish_epoch": None,
                      "last_finish_utc": None, "longest_shard_s": None}
            if event == "start":
                sh["started"] += 1
                sh["running"] += 1
                if attempt > 0:
                    sh["retries"] += 1
            elif event in ("ok", "failed"):
                sh["done_ok" if event == "ok" else "failed"] += 1
                sh["running"] = max(0, sh["running"] - 1)
                sh["last_finish_epoch"] = now
                sh["last_finish_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
                # successful attempts only: a 3 s crash must not set the yardstick (audit)
                if event == "ok" and elapsed_s is not None:
                    sh["longest_shard_s"] = round(max(float(sh["longest_shard_s"] or 0.0),
                                                      float(elapsed_s)), 1)
            _PHASE_DOC["shards"] = _shard_live(sh, now)
            _flush_phase_doc()
    except Exception:
        pass  # shard progress is a report; dispatch never stops for it


def _sweep_phase() -> dict[str, Any] | None:
    try:
        doc = json.loads(SWEEP_PHASE.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    if isinstance(doc.get("shards"), dict):
        # re-derived on every read so the resident's heartbeat carries a LIVE gap, not the
        # gap as it stood at the last child event
        doc["shards"] = _shard_live(doc["shards"], time.time())
    return doc


def _write_state(doc: dict[str, Any]) -> None:
    doc = {**doc, "heartbeat_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    if doc.get("status") == "SWEEPING":
        doc["sweep_phase"] = _sweep_phase()
    _write_atomic(RESIDENT_STATE, doc)  # the heartbeat is a report; judging never stops for it


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
    with contextlib.suppress(psutil.Error):
        root.kill()
        killed += 1
        root.wait(timeout=10)
    return killed


def _one_sweep_child(hang_s: float | None = None) -> int:
    """One sweep in a fresh process, at the priority the scheduler gives the judge today."""
    import subprocess

    flags = 0
    if sys.platform == "win32":
        # BELOW_NORMAL is the Task Scheduler's default priority (7) for MT5-Gauntlet, so the
        # child keeps exactly the standing the judge has now: miners are never displaced by it.
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    child = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "--once"],
                             cwd=DESK, env=_sweep_env(), creationflags=flags)
    try:
        return int(child.wait(timeout=hang_s))
    except subprocess.TimeoutExpired:
        _kill_sweep_tree(child.pid)
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=30)
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if _resident_enabled(argv):
        return resident(limit_s=_task_limit_s())
    return _sweep_once()


def _sweep_once() -> int:
    from research.judging_throughput import apply_env

    apply_env()
    _phase("plan")
    log_path = DESK / "logs" / "MT5-Gauntlet.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = log
        try:
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

            rc = int(judge.run_sharded(_shards(), _timed_dispatch))
            _phase("done")
            return rc
        finally:
            sys.stdout, sys.stderr = old_out, old_err


if __name__ == "__main__":
    raise SystemExit(main())
