"""Launch the canonical judge through its fail-closed shard protocol, sized by MEASURED memory.

The sealed judge owns every statistical decision. This launcher supplies the dispatcher that
``external_gauntlet.run_sharded`` exposes: it runs each planned shard as a child process, and it
decides HOW MANY run at once and HOW MANY shards the plan is cut into. It changes no gate, verdict,
docket, merge rule or trial charge.

THE RESTART LOOP THIS FILE ENDS (measured on the trading box 2026-10-06). Every MT5-Gauntlet
attempt pre-warmed for ~7,800-8,000 s, then launched 15 shards over 584,979 cells ALL AT ONCE
(``ThreadPoolExecutor(max_workers=n)``). Each child imported the judge with the WHOLE sweep's
``GAUNTLET_MEMORY_BUDGET_MB`` (the env the throughput organ writes for the parent), so fifteen
processes each believed they owned the sweep's budget. Every one also unpickled the whole plan.
Logs show ArrayMemoryError and only 10 of 15 shard outputs. Publication failed closed, so 0
verdicts were committed, and the next attempt repeated the work. Certificates stayed at 847.

WHAT CHANGES, AND WHY EACH IS A MEASUREMENT RATHER THAN A GUESS:

1. ADMISSION BY MEASURED FREE MEMORY. A shard starts only when psutil says the box has room for
   its PREDICTED peak plus the live terminal's reserve; otherwise it waits for a running shard
   to finish. At least one shard always runs, so this can delay a shard but never stop the
   judge. The prediction comes from the peaks this launcher MEASURED on earlier shards (Windows'
   own ``peak_wset``, else sampled RSS of the child's whole tree), persisted in
   ``data/judging_shard_memory.json`` and refined on every run.
2. EACH CHILD GETS ITS OWN MEMORY BUDGET, NOT THE SWEEP'S. ``GAUNTLET_MEMORY_BUDGET_MB`` for a
   child is its share of the measured room. The sealed build loop then DEFERS fresh cells at that
   cap instead of growing until numpy cannot allocate. BLAS/OpenMP pools are pinned to one
   thread per child, because N children times one pool each, every pool as wide as the box, is
   oversubscription rather than throughput.
3. THE SHARD COUNT IS DERIVED FROM CELLS x MEASURED MB PER CELL, separately from concurrency.
   More, smaller shards bound each child's peak. Concurrency bounds the sum. While the judge has
   an unfinished epoch (``shards/epoch.json``, sealed patch ``judge_streaming_resume``), the
   count is held at the epoch's own, so finished shards stay valid.
4. ONLY UNFINISHED SHARDS RUN. With the patched judge the dispatcher receives ``ks``, the
   shards still pending, so a resumed epoch never reruns a finished shard. With the unpatched
   judge, all shards run, exactly as before.

A missing psutil, an unreadable model or an unwritable file changes nothing: the dispatcher falls
back to the measured worker count with no admission wait, never to a stop.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _path in (str(ROOT), str(DESK)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

try:
    import psutil
except ImportError:  # pragma: no cover - the box has psutil; a host without it runs unmeasured
    psutil = None  # type: ignore[assignment]

#: The persisted per-shard memory model. Box state (under data/), written by this launcher only.
MODEL_FILE = DESK / "data" / "judging_shard_memory.json"
SHARD_DIR = DESK / "reports" / "gauntlet_cache" / "shards"

#: What the live terminal, the gateway and the merging parent keep however many shards run.
RESERVE_MB = float(os.environ.get("GAUNTLET_SHARD_RESERVE_MB", "6144"))
#: The share of measured free memory the shards may take together.
FREE_SHARE = float(os.environ.get("GAUNTLET_SHARD_FREE_SHARE", "0.8"))
#: Before any shard has been measured: the first wave assumes this peak per shard. It is
#: replaced by the first measurement in the same run (see `Admission.predict`).
DEFAULT_SHARD_PEAK_MB = 4096.0
#: Python + numpy + pandas + the judge's imports, before any plan or cell is loaded.
IMPORT_MB = 350.0
#: An unpickled plan takes several times its file size in memory (dicts of small objects).
PICKLE_EXPANSION = 4.0
#: Headroom over the measured per-cell figure when the next run's shard count is derived.
MODEL_MARGIN = 1.25
#: Runs kept in the model file (each is a few hundred bytes).
KEEP_RUNS = 30
SAMPLE_S = 2.0
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
               "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


# --------------------------------------------------------------------------------- env knobs
def _env_int(name: str, default: int, floor: int) -> int:
    try:
        return max(floor, int(float(os.environ.get(name, str(default)))))
    except (TypeError, ValueError):
        return default


def _shards() -> int:
    """The measured shard count the throughput organ published, falling closed to serial."""
    return _env_int("GAUNTLET_SHARDS", 1, 1)


def _retry_attempts() -> int:
    """Retries after the admitted wave; invalid values fall closed to two."""
    return _env_int("GAUNTLET_SHARD_RETRIES", 2, 0)


def _max_concurrency() -> int:
    """The CPU ceiling on simultaneous shards: the measured worker count, else the shard count."""
    raw = os.environ.get("GAUNTLET_SHARD_CONCURRENCY") or os.environ.get("GAUNTLET_WORKERS")
    try:
        return max(1, int(float(raw))) if raw else max(1, (os.cpu_count() or 1) - 1)
    except (TypeError, ValueError):
        return 1


# ------------------------------------------------------------------------------- measurement
def free_mb() -> float | None:
    """Available physical memory in MB, or None where psutil cannot say."""
    if psutil is None:
        return None
    try:
        return float(psutil.virtual_memory().available) / 1048576.0
    except Exception:
        return None


def total_mb() -> float | None:
    if psutil is None:
        return None
    try:
        return float(psutil.virtual_memory().total) / 1048576.0
    except Exception:
        return None


def tree_peak_mb(pid: int, prior: float = 0.0) -> float:
    """The larger of `prior` and the process tree's current resident size (or Windows' own peak
    working set, which records the high-water mark exactly even between samples)."""
    if psutil is None:
        return prior
    try:
        proc = psutil.Process(pid)
        procs = [proc, *proc.children(recursive=True)]
    except Exception:
        return prior
    total = 0.0
    for p in procs:
        try:
            mi = p.memory_info()
            total += float(getattr(mi, "peak_wset", 0) or mi.rss) / 1048576.0
        except Exception:
            continue
    return max(prior, total)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def load_model(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or MODEL_FILE, {})
    return doc if isinstance(doc, dict) else {}


def plan_base_mb(shard_dir: Path, k: int) -> float:
    """What a shard holds before its first cell: imports plus the plan it unpickles. A patched
    judge hands each shard a spec-free header and its own slice; an unpatched one, the whole
    plan."""
    size = 0.0
    for f in (shard_dir / "plan.pkl", shard_dir / f"plan_{k}.pkl"):
        with contextlib.suppress(OSError):
            size += f.stat().st_size / 1048576.0
    return IMPORT_MB + PICKLE_EXPANSION * size


def shard_cells(shard_dir: Path, k: int, planned: int | None, n: int) -> int | None:
    """Cells in shard k: its slice's length when the judge wrote slices, else planned / n."""
    f = shard_dir / f"plan_{k}.pkl"
    if f.exists():
        try:
            import pickle
            with open(f, "rb") as fh:
                return len(pickle.load(fh))  # noqa: S301 - the judge's own file
        except Exception:
            pass
    return math.ceil(planned / n) if planned and n else None


def per_cell_mb(model: dict[str, Any]) -> float | None:
    """The measured MB per planned cell above a shard's base, p90 over recent successful shards."""
    vals = sorted(float(s["per_cell_mb"]) for r in (model.get("runs") or [])[-10:]
                  for s in (r.get("shards") or [])
                  if isinstance(s, dict) and s.get("ok") and isinstance(s.get("per_cell_mb"),
                                                                        (int, float)))
    if not vals:
        return None
    return vals[min(len(vals) - 1, int(0.9 * len(vals)))]


def derive_shards(model: dict[str, Any], planned: int | None, concurrency: int,
                  floor: int, box_free_mb: float | None,
                  epoch: dict[str, Any] | None = None) -> tuple[int, str]:
    """The shard count for THIS run, and why. One-way above the published floor.

    An unfinished epoch keeps its own count (changing it would discard every finished shard).
    Otherwise: enough shards that one shard's predicted peak (base + cells x MB/cell x margin)
    fits the per-shard room, `concurrency` shards at a time.
    """
    if epoch and isinstance(epoch.get("n"), int) and epoch["n"] >= 1:
        return int(epoch["n"]), f"held at the unfinished epoch's {epoch['n']} (resume)"
    pc = per_cell_mb(model)
    base = float(model.get("base_mb") or IMPORT_MB)
    if not planned or pc is None or box_free_mb is None:
        return floor, "no measured MB/cell or plan size yet: the published shard count"
    room = max(512.0, (FREE_SHARE * box_free_mb - RESERVE_MB) / max(1, concurrency) - base)
    need = math.ceil(planned * pc * MODEL_MARGIN / room)
    cap = max(floor, 8 * (os.cpu_count() or 1))
    n = max(floor, min(cap, need))
    return n, (f"{planned} planned x {pc:.3f} MB/cell x {MODEL_MARGIN} over {room:.0f} MB per "
               f"shard at {concurrency} concurrent -> {need} (floor {floor}, cap {cap})")


# --------------------------------------------------------------------------------- admission
class Admission:
    """Starts a shard only when measured free memory covers its predicted peak plus the reserve.

    One shard always runs, so admission can delay the judge and never stop it. The prediction is
    the larger of the persisted model and every peak measured in this run so far, so the first
    shard's real figure governs the rest of the wave.
    """

    def __init__(self, model: dict[str, Any], measure: Callable[[], float | None] = free_mb):
        self.model = model
        self.measure = measure
        self.cond = threading.Condition()
        self.running = 0
        self.seen_peaks: list[float] = []

    def predict(self, base: float, cells: int | None) -> float:
        pc = per_cell_mb(self.model)
        guess = (base + cells * pc * MODEL_MARGIN) if (pc is not None and cells) else None
        observed = max(self.seen_peaks) if self.seen_peaks else None
        cands = [x for x in (guess, observed) if x is not None]
        return max(cands) if cands else DEFAULT_SHARD_PEAK_MB

    def acquire(self, need_mb: float, poll_s: float = 5.0) -> None:
        with self.cond:
            while True:
                if self.running == 0:
                    break
                free = self.measure()
                if free is None or free - RESERVE_MB >= need_mb:
                    break
                self.cond.wait(timeout=poll_s)
            self.running += 1

    def release(self, peak_mb: float | None) -> None:
        with self.cond:
            self.running -= 1
            if peak_mb:
                self.seen_peaks.append(float(peak_mb))
            self.cond.notify_all()


# ---------------------------------------------------------------------------------- children
def child_env(budget_mb: float | None) -> dict[str, str]:
    env = os.environ.copy()
    # ONE shard, ONE worker: a child that sized its own pool from the box would multiply it N x.
    env["GAUNTLET_WORKERS"] = "1"
    env["LOKY_MAX_CPU_COUNT"] = "1"
    for var in THREAD_VARS:
        env[var] = "1"
    if budget_mb is not None:
        # The CHILD's budget, not the sweep's: the sealed build loop defers fresh cells at it.
        env["GAUNTLET_MEMORY_BUDGET_MB"] = str(int(max(1200.0, budget_mb)))
    return env


def run_child(argv: list[str], env: dict[str, str]) -> tuple[int, float]:
    """Run one shard to completion, sampling its tree's memory. Returns (rc, peak MB)."""
    peak = 0.0
    with subprocess.Popen(argv, cwd=DESK, env=env) as proc:
        while True:
            try:
                rc = proc.wait(timeout=SAMPLE_S)
                break
            except subprocess.TimeoutExpired:
                peak = tree_peak_mb(proc.pid, peak)
    return int(rc), round(peak, 1)


_CODE = (
    "import sys;"
    f"sys.path[:0]=[{str(ROOT)!r},{str(DESK)!r}];"
    "from scripts.external_gauntlet import shard_worker;"
    "shard_worker(sys.argv[1],int(sys.argv[2]),sys.argv[3])"
)

#: Facts about the current run, filled in by `main` and by the dispatcher, persisted per phase.
RUN: dict[str, Any] = {}


def _persist(model_path: Path | None = None) -> None:
    path = model_path or MODEL_FILE
    model = load_model(path)
    runs = [r for r in (model.get("runs") or []) if r.get("run_id") != RUN.get("run_id")]
    runs.append(dict(RUN))
    model["runs"] = runs[-KEEP_RUNS:]
    model["per_cell_mb"] = per_cell_mb(model)
    bases = [float(s["base_mb"]) for s in RUN.get("shards") or [] if s.get("base_mb")]
    if bases:
        model["base_mb"] = round(max(bases), 1)
    model["at"] = datetime.now(UTC).isoformat(timespec="seconds")
    model["why"] = ("written by scripts/run_sharded_gauntlet.py: measured per-shard peak RSS, "
                    "MB per planned cell above the shard's base, and the admission decisions; "
                    "read back by the same launcher to size the next run's shards and "
                    "concurrency, and by research/judging_throughput.py")
    _write_json(path, model)


def dispatch(shard_dir: Path, n: int, phase: str, ks: list[int] | None = None, *,
             runner: Callable[[list[str], dict[str, str]], tuple[int, float]] | None = None,
             admission: Admission | None = None) -> None:
    """Run `phase` on shards `ks` (default all), admitted by measured memory, retrying failures.

    Publication remains fail-closed: a shard that still fails after the bounded serial retries
    raises, so the sealed judge cannot merge a partial result. Successful shard outputs are
    kept, and with the patched judge they are kept ACROSS invocations as well.
    """
    run_ = runner or run_child
    todo = list(range(n)) if ks is None else sorted(int(k) for k in ks)
    model = load_model()
    adm = admission or Admission(model)
    cap = max(1, min(_max_concurrency(), len(todo) or 1))
    box_free = free_mb()
    budget = ((FREE_SHARE * box_free - RESERVE_MB) / cap) if box_free is not None else None
    records: list[dict[str, Any]] = RUN.setdefault("shards", [])
    planned = RUN.get("planned_cells")
    RUN.setdefault("dispatch", []).append(
        {"phase": phase, "ks": todo, "n": n, "max_concurrency": cap,
         "free_mb_at_start": round(box_free, 1) if box_free is not None else None,
         "child_budget_mb": round(budget, 1) if budget is not None else None})

    def one(k: int, serial: bool = False) -> Exception | None:
        base = plan_base_mb(Path(shard_dir), k)
        cells = shard_cells(Path(shard_dir), k, planned, n)
        need = adm.predict(base, cells)
        if not serial:
            adm.acquire(need)
        t0 = time.time()
        peak: float | None = None
        err: Exception | None = None
        try:
            # A serial retry runs alone, so it may take the whole measured room.
            room = free_mb() if serial else None
            env = child_env((room - RESERVE_MB) if room is not None else budget)
            rc, peak = run_([sys.executable, "-u", "-c", _CODE, str(shard_dir), str(k), phase],
                            env)
            if rc != 0:
                err = subprocess.CalledProcessError(rc, f"shard {k} {phase}")
        except Exception as exc:  # child launch failure is evidence, then retried below
            err = exc
        finally:
            if not serial:
                adm.release(peak)
        rec = {"k": k, "phase": phase, "ok": err is None, "serial_retry": serial,
               "seconds": round(time.time() - t0, 1), "peak_mb": peak,
               "predicted_mb": round(need, 1), "base_mb": round(base, 1), "cells": cells,
               "error": None if err is None else f"{type(err).__name__}: {err}"[:300]}
        if err is None and peak and cells:
            rec["per_cell_mb"] = round(max(0.0, peak - base) / cells, 5)
        records.append(rec)
        return err

    threads: list[threading.Thread] = []
    results: dict[int, Exception | None] = {}

    def worker(k: int) -> None:
        results[k] = one(k)

    # Shards are started in order; each start waits for its admission, so at most `cap` run
    # and never more than measured memory admits.
    gate = threading.Semaphore(cap)
    for k in todo:
        gate.acquire()

        def _w(k: int = k) -> None:
            try:
                worker(k)
            finally:
                gate.release()

        t = threading.Thread(target=_w, name=f"judge-{phase}-{k}", daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    with contextlib.suppress(Exception):
        _persist()

    failed = [k for k in todo if results.get(k) is not None]
    if failed:
        print(f"SHARD RECOVERY: {len(failed)}/{len(todo)} {phase} shard(s) failed; retrying "
              "only those shards serially after peer memory was released", flush=True)
    for k in failed:
        last_exc = results[k]
        for attempt in range(1, _retry_attempts() + 1):
            exc = one(k, serial=True)
            if exc is None:
                print(f"SHARD RECOVERY: {phase} shard {k} recovered on retry {attempt}",
                      flush=True)
                break
            last_exc = exc
            print(f"SHARD RECOVERY: {phase} shard {k} retry {attempt} failed: "
                  f"{type(exc).__name__}: {exc}", flush=True)
        else:
            with contextlib.suppress(Exception):
                _persist()
            raise RuntimeError(f"{phase} shard {k} failed after {_retry_attempts() + 1} "
                               "attempt(s); refusing partial merge") from last_exc
    with contextlib.suppress(Exception):
        _persist()


class _PlanTap:
    """Stdout tee that reads the judge's own `SHARDED SWEEP: N planned cell(s)` line, so the
    launcher learns the plan size without unpickling the plan."""

    PAT = re.compile(r"SHARDED SWEEP: (\d+) planned cell")

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def write(self, s: str) -> int:
        m = self.PAT.search(s)
        if m:
            RUN["planned_cells"] = int(m.group(1))
        return int(self.inner.write(s) or 0)

    def flush(self) -> None:
        self.inner.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def unfinished_epoch(shard_dir: Path | None = None) -> dict[str, Any] | None:
    doc = _read_json((shard_dir or SHARD_DIR) / "epoch.json", None)
    return doc if isinstance(doc, dict) and isinstance(doc.get("n"), int) else None


def decide(model: dict[str, Any] | None = None) -> dict[str, Any]:
    """This run's shard count, concurrency ceiling and (optionally) streaming bound."""
    model = load_model() if model is None else model
    conc = _max_concurrency()
    last_planned = next((r.get("planned_cells") for r in reversed(model.get("runs") or [])
                         if isinstance(r.get("planned_cells"), int)), None)
    n, why = derive_shards(model, last_planned, conc, _shards(), free_mb(),
                           unfinished_epoch())
    return {"n_shards": n, "shards_why": why, "max_concurrency": conc,
            "planned_cells_last_run": last_planned, "per_cell_mb": per_cell_mb(model)}


def main() -> int:
    from research.judging_throughput import apply_env

    apply_env()
    log_path = DESK / "logs" / "MT5-Gauntlet.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    decision = decide()
    RUN.clear()
    RUN.update(run_id=f"{os.getpid()}-{int(time.time())}",
               at=datetime.now(UTC).isoformat(timespec="seconds"), **decision)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = _PlanTap(log)  # type: ignore[assignment]
        sys.stderr = log
        try:
            print(f"{datetime.now(UTC).isoformat()} canonical sharded judge "
                  f"runtime={sys.executable} shards={decision['n_shards']} "
                  f"({decision['shards_why']}) max_concurrency={decision['max_concurrency']}",
                  flush=True)
            from scripts import external_gauntlet as judge

            if getattr(judge, "SHARD_PROTOCOL", None) != 2:
                raise RuntimeError(
                    "canonical judge does not expose the required fail-closed shard protocol v2"
                )
            t0 = time.time()
            try:
                rc = int(judge.run_sharded(int(decision["n_shards"]), dispatch))
                RUN["outcome"] = "PUBLISHED" if rc == 0 else f"rc={rc}"
                return rc
            except BaseException as exc:
                RUN["outcome"] = f"FAILED: {type(exc).__name__}: {str(exc)[:200]}"
                raise
            finally:
                RUN["wall_seconds"] = round(time.time() - t0, 1)
                with contextlib.suppress(Exception):
                    _persist()
        finally:
            sys.stdout, sys.stderr = old_out, old_err


if __name__ == "__main__":
    raise SystemExit(main())
