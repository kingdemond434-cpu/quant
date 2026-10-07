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
   to finish. The FIRST shard is held to the same rule: no child is ever launched into memory
   the box does not have (an 8 GB box with 1 GB free waits, then re-cuts the shard smaller, then
   names it BLOCKED -- see 5). The prediction comes from the peaks this launcher MEASURED on
   earlier shards (Windows'
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
5. OUT OF MEMORY ALONE IS RE-CUT, NOT REPEATED. A shard that dies of memory with nothing beside
   it (or cannot be admitted alone) would fail the same way for the epoch's whole 24 h life at
   the same shard count. It is recorded in ``reports/BLOCKED_SHARD_OOM.json`` and its cells are
   re-cut into parts sized from measured free memory, each ruled by the sealed ``shard_worker``
   and joined into the one shard file the merge reads (``split_shard``). A single cell that
   still dies alone is DEFERRED, the sealed build loop's own over-budget rule.

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
#: ...but never more than this share of the MEASURED total: 6 GB is right on the 96 GB trading
#: box and is three quarters of an 8 GB one, where it would admit nothing ever (see reserve_mb).
RESERVE_SHARE = 0.25
#: With no measured MB/cell yet, a planned cell is assumed to take this much above the base
#: (2026-10-06: ~9 GB peaks over ~39,000-cell shards measured ~0.23 MB/cell; this is 2x that).
DEFAULT_CELL_MB = 0.5
#: How long a shard with NOTHING running beside it waits for memory to appear before its cells
#: are re-cut smaller (or, when even one cell cannot fit, the shard is named BLOCKED).
ADMIT_WAIT_S = float(os.environ.get("GAUNTLET_ADMIT_WAIT_S", "600"))
#: The named record of every shard that ran out of memory ALONE, or could not be admitted alone.
BLOCKED_FILE = DESK / "reports" / "BLOCKED_SHARD_OOM.json"
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


def reserve_mb(total: float | None = None) -> float:
    """The memory no shard may take: RESERVE_MB, capped at RESERVE_SHARE of the measured total."""
    t = total_mb() if total is None else total
    return RESERVE_MB if t is None else min(RESERVE_MB, RESERVE_SHARE * float(t))


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
    """The measured MB per planned cell above a shard's base, p90 over recent shards (ok or not)."""
    # Failed shards count (audit D1): a shard that died of memory at its peak measured that peak.
    vals = sorted(float(s["per_cell_mb"]) for r in (model.get("runs") or [])[-10:]
                  for s in (r.get("shards") or [])
                  if isinstance(s, dict) and isinstance(s.get("per_cell_mb"), (int, float)))
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
    """Starts a shard only when measured memory covers it AND every running shard's growth.

    AUDIT D1 (2026-10-06). Comparing one shard's need with CURRENT free memory admits a whole wave
    at once: a shard that has just started has not grown yet, so free memory still looks full --
    measured, 15 shards launched within 0.3 s against 60 GB free with ~9 GB peaks, which is the
    original ArrayMemoryError. The rule now is

        free - RESERVE - sum over running shards of max(0, predicted_peak - current_rss) >= need

    so the memory a running shard is still going to take is charged before it takes it. With NO
    measured model (no MB/cell on file and no shard finished this run) exactly ONE shard runs
    until its peak is sampled, then admission widens on that measurement. Failed shards' peaks
    feed the prediction too. The first shard is admitted only when measured free memory covers
    it (an unmeasurable host still runs one); a shard that cannot be admitted alone within
    ADMIT_WAIT_S is re-cut by the dispatcher. `limit` is lowered after a memory failure (D3)
    and never raised within a run.
    """

    def __init__(self, model: dict[str, Any], measure: Callable[[], float | None] | None = None,
                 reserve: float | None = None):
        self.model = model
        # Resolved at call time, so the module's `free_mb` is the one measured.
        self.measure: Callable[[], float | None] = measure or (lambda: free_mb())
        self.reserve = reserve_mb() if reserve is None else float(reserve)
        self.cond = threading.Condition()
        self.running = 0
        self.seen_peaks: list[float] = []
        self.seen_pc: list[float] = []
        self.live: dict[int, dict[str, float]] = {}
        self.limit: int | None = None

    def measured(self) -> bool:
        return per_cell_mb(self.model) is not None or bool(self.seen_peaks)

    def cell_mb(self) -> float | None:
        """MB per planned cell: the model's, or the largest measured in this run."""
        vals = [v for v in (per_cell_mb(self.model), *self.seen_pc) if v is not None]
        return max(vals) if vals else None

    def predict(self, base: float, cells: int | None) -> float:
        pc = self.cell_mb()
        if cells:
            # Unmeasured: the conservative default per cell, so a SMALLER part predicts smaller
            # and a re-cut shard can fit where the whole one could not (8 GB cold start).
            return base + cells * (pc if pc is not None else DEFAULT_CELL_MB) * MODEL_MARGIN
        observed = max(self.seen_peaks) if self.seen_peaks else None
        return observed if observed is not None else DEFAULT_SHARD_PEAK_MB

    def room(self) -> float | None:
        """Measured free memory less the reserve and every running shard's predicted growth."""
        free = self.measure()
        return None if free is None else free - self.reserve - self.outstanding()

    def fits(self, need_mb: float) -> bool:
        room = self.room()
        # Unmeasurable host: the unchanged fallback (one shard at a time, see `admits`).
        return True if room is None else room >= need_mb

    def outstanding(self) -> float:
        """Memory the running shards are predicted to take beyond what they hold now."""
        return sum(max(0.0, v["predicted"] - v["rss"]) for v in self.live.values())

    def admits(self, need_mb: float) -> bool:
        if self.running == 0:
            # NEVER INTO AN OOM (2026-10-06, 8 GB cold start): even the first shard starts only
            # when measured free memory covers it. Unmeasurable: one shard runs, as before.
            return self.fits(need_mb)
        if self.limit is not None and self.running >= self.limit:
            return False
        if not self.measured():
            return False                       # one shard first; widen on its measured peak
        if self.measure() is None:
            return False                       # unmeasurable: never widen past one shard
        return self.fits(need_mb)

    def acquire(self, need_mb: float, poll_s: float = 5.0, key: int | None = None,
                wait_s: float | None = None) -> bool:
        """Wait for room. A shard waits as long as others run (they release memory); with
        NOTHING running it waits at most `wait_s` (ADMIT_WAIT_S) and returns False -- the caller
        re-cuts it smaller or names it BLOCKED, and no child is launched into memory that is not
        there."""
        limit_s = ADMIT_WAIT_S if wait_s is None else float(wait_s)
        t_end = time.monotonic() + limit_s
        with self.cond:
            while not self.admits(need_mb):
                if self.running == 0 and time.monotonic() >= t_end:
                    return False
                self.cond.wait(timeout=poll_s)
            self.running += 1
            self.live[key if key is not None else -len(self.live) - 1] = {
                "predicted": float(need_mb), "rss": 0.0}
            return True

    def sample(self, key: int, rss_mb: float) -> None:
        with self.cond:
            if key in self.live:
                self.live[key]["rss"] = max(self.live[key]["rss"], float(rss_mb))

    def shrink(self) -> None:
        """After a memory failure: at most half of what was running, never below one."""
        with self.cond:
            cur = self.limit if self.limit is not None else max(1, self.running)
            self.limit = max(1, min(cur, max(1, self.running)) // 2)

    def release(self, peak_mb: float | None, key: int | None = None,
                base: float | None = None, cells: int | None = None) -> None:
        with self.cond:
            self.running = max(0, self.running - 1)
            if key is not None:
                self.live.pop(key, None)
            elif self.live:
                self.live.pop(next(iter(self.live)))
            if peak_mb:
                self.seen_peaks.append(float(peak_mb))
                if cells:
                    self.seen_pc.append(max(0.0, float(peak_mb) - float(base or 0.0)) / cells)
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
        # No fixed floor (it was 1200 MB whatever the box had free): admission has already
        # checked that measured free memory covers this child's predicted need, and the budget
        # it exports is that measured room -- never a figure the box does not have.
        env["GAUNTLET_MEMORY_BUDGET_MB"] = str(max(1, int(budget_mb)))
    return env


#: What a child's stderr says when the shard died of memory (numpy's `_ArrayMemoryError` is a
#: MemoryError subclass and prints as `numpy.core._exceptions._ArrayMemoryError`).
OOM_MARKERS = ("MemoryError", "Unable to allocate")


def run_child(argv: list[str], env: dict[str, str],
              on_sample: Callable[[float], None] | None = None
              ) -> tuple[int, float, dict[str, Any]]:
    """Run one shard to completion, sampling its tree's memory.

    Returns (rc, peak MB, info). `on_sample` receives each sample (admission charges a running
    shard's growth against it). The child's stderr is captured to a temp file and then copied to
    ours (the task log), so a death by memory is recognised by name: `info["oom"]`."""
    import tempfile
    peak = 0.0
    with tempfile.TemporaryFile() as err:
        with subprocess.Popen(argv, cwd=DESK, env=env, stderr=err) as proc:
            while True:
                try:
                    rc = proc.wait(timeout=SAMPLE_S)
                    break
                except subprocess.TimeoutExpired:
                    peak = tree_peak_mb(proc.pid, peak)
                    if on_sample is not None:
                        with contextlib.suppress(Exception):
                            on_sample(peak)
        err.seek(0)
        text = err.read().decode("utf-8", "replace")
    if text:
        with contextlib.suppress(Exception):
            sys.stderr.write(text)
    oom = int(rc) != 0 and any(m in text for m in OOM_MARKERS)
    return int(rc), round(peak, 1), {"oom": oom, "stderr_tail": text[-400:] if rc else ""}


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



# ------------------------------------------------------------------- out of memory, alone (M3)
class ShardNoRoom(MemoryError):
    """Measured free memory does not cover a shard even with nothing else running."""


class ShardBlocked(RuntimeError):
    """A shard that cannot be ruled at any cut this box has memory for: fail closed, named."""


def _judge() -> Any:
    """The sealed judge module, for its OWN shard-file helpers (format owned by the seal)."""
    import importlib
    return sys.modules.get("scripts.external_gauntlet") or importlib.import_module(
        "scripts.external_gauntlet")


def record_blocked(entry: dict[str, Any], path: Path | None = None) -> None:
    """BLOCKED_SHARD_OOM.json: the latest named event and the last 50. Never raises."""
    path = path or BLOCKED_FILE
    doc = _read_json(path, {})
    doc = doc if isinstance(doc, dict) else {}
    entry = {"at": datetime.now(UTC).isoformat(timespec="seconds"),
             "run_id": RUN.get("run_id"), **entry}
    hist = [h for h in (doc.get("history") or []) if isinstance(h, dict)][-49:]
    hist.append(entry)
    doc.update(latest=entry, history=hist, count=int(doc.get("count") or 0) + 1,
               why=("written by scripts/run_sharded_gauntlet.py when a shard runs out of memory "
                    "ALONE or cannot be admitted alone. Before 2026-10-06 that shard was retried "
                    "at the same cut for the epoch's whole life (24 h) and nothing published; it "
                    "is now re-cut into parts that fit, and a cell that still cannot be built "
                    "alone is DEFERRED exactly as the sealed memory budget defers one."))
    _write_json(path, doc)
    RUN.setdefault("blocked", []).append(entry)


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    size = max(1, int(size))
    return [items[i:i + size] for i in range(0, len(items), size)]


def split_shard(shard_dir: Path, k: int, phase: str, adm: Admission, *,
                runner: Callable[[list[str], dict[str, str]], tuple[Any, ...]] | None = None,
                judge: Any = None, cause: str = "oom") -> dict[str, Any]:
    """RE-CUT shard k's cells into parts that fit and rule them one part at a time, alone.

    Each part is a sub-plan in `shard_dir/split_<k>_<phase>_<j>/` that the SEALED
    `shard_worker` rules exactly as it rules a shard (same plan header, same token, a slice of
    the same cells); the parts' outputs are joined, in plan order, into `shard_<k>.pkl` and its
    done marker, so `_shard_collect` reads one shard as it always has. Part size comes from
    measured free memory and the measured MB/cell. A part that still dies of memory is halved;
    a SINGLE cell that dies alone is DEFERRED (`passed: None`, re-queued, no trial charged) --
    the sealed build loop's own over-budget rule -- in phase `build`. In phase `rule` (one
    series a cell) a single cell that cannot be ruled is BLOCKED and the merge fails closed.
    """
    J = judge or _judge()
    run_ = runner or run_child
    shard_dir = Path(shard_dir)
    plan_k, out_k = shard_dir / f"plan_{k}.pkl", shard_dir / f"shard_{k}.pkl"
    header = J._unpickle(shard_dir / "plan.pkl")
    base = plan_base_mb(shard_dir, k)
    if phase == "build":
        if header.get("specs") is not None or not plan_k.exists():
            raise ShardBlocked(f"shard {k}: the plan has no per-shard slice to re-cut "
                               "(unpatched judge)")
        items: list[Any] = list(J._unpickle(plan_k))
        built: dict[str, Any] | None = None
    else:
        built = J._unpickle(out_k)
        if built.get("phase") != "build":
            raise ShardBlocked(f"shard {k}: no build output to re-cut for phase {phase}")
        items = list(built["rows"])
    pc = adm.cell_mb() or DEFAULT_CELL_MB
    room = adm.room()
    if room is not None:
        fit = int((room - base) // (pc * MODEL_MARGIN)) if room > base else 0
        if fit < 1:
            raise ShardBlocked(f"shard {k} {phase}: {room:.0f} MB free over the reserve cannot "
                               f"hold one cell ({base:.0f} MB base + {pc:.3f} MB/cell)")
        size = min(fit, max(1, (len(items) + 1) // 2))
    else:
        size = max(1, (len(items) + 1) // 2)
    queue = _chunks(items, size)
    rows: list[dict[str, Any]] = []
    syms: set[str] = set()
    dates: set[Any] = set()
    secs = 0.0
    peak_all = 0.0
    ruled = 0
    stage_cache: dict[str, Any] = {}
    deferred: list[Any] = []
    parts_run = 0
    j = 0
    while queue:
        part = queue.pop(0)
        sub = shard_dir / f"split_{k}_{phase}_{j}"
        j += 1
        import shutil
        shutil.rmtree(sub, ignore_errors=True)
        sub.mkdir(parents=True)
        shutil.copyfile(shard_dir / "plan.pkl", sub / "plan.pkl")
        if phase == "build":
            J._pickle_atomic(sub / f"plan_{k}.pkl", part)
        else:
            shutil.copyfile(shard_dir / "cut.pkl", sub / "cut.pkl")
            J._pickle_atomic(sub / f"shard_{k}.pkl", {**(built or {}), "rows": part})
        need = adm.predict(base, len(part))
        key = -(10_000 + j)
        if not adm.acquire(need, key=key):
            shutil.rmtree(sub, ignore_errors=True)
            raise ShardBlocked(f"shard {k} {phase}: a {len(part)}-cell part needing "
                               f"{need:.0f} MB was not admitted within {ADMIT_WAIT_S:.0f} s")
        peak: float | None = None
        oom = False
        try:
            room_now = adm.measure()
            budget = (room_now - adm.reserve) if room_now is not None else None
            argv = [sys.executable, "-u", "-c", _CODE, str(sub), str(k), phase]
            out = run_(argv, child_env(max(need, budget) if budget is not None else None))
            rc, peak = int(out[0]), out[1]
            info = out[2] if len(out) > 2 and isinstance(out[2], dict) else {}
            oom = bool(info.get("oom"))
        finally:
            adm.release(peak, key=key, base=base, cells=len(part))
        parts_run += 1
        if rc != 0:
            shutil.rmtree(sub, ignore_errors=True)
            if not oom:
                raise ShardBlocked(f"shard {k} {phase}: part of {len(part)} cell(s) failed "
                                   f"(rc={rc}), not of memory")
            if len(part) > 1:
                queue[:0] = _chunks(part, (len(part) + 1) // 2)
                continue
            if phase != "build":
                raise ShardBlocked(f"shard {k} rule: one cell cannot be ruled alone")
            i, sp = part[0]
            deferred.append(J._spec_ident(sp) if hasattr(J, "_spec_ident") else i)
            rows.append({"idx": i, "kind": "deferred", "obj": sp,
                         "stage0": (J.stage0_new_summary(), {}), "cache_hits": 0,
                         "built_fresh": 0, "mem_deferred": 1})
            continue
        got = J._unpickle(sub / f"shard_{k}.pkl")
        shutil.rmtree(sub, ignore_errors=True)
        rows.extend(got["rows"])
        syms |= set(got.get("built_syms") or ())
        dates.update(got.get("dates") or ())
        secs += float(got.get("seconds" if phase == "rule" else "build_seconds") or 0.0)
        peak_all = max(peak_all, float(got.get("peak_rss_mb" if phase == "rule"
                                               else "build_peak_rss_mb") or 0.0))
        ruled += int(got.get("cells_ruled") or 0)
        for kk, vv in (got.get("stage_cache") or {}).items():
            stage_cache[kk] = stage_cache.get(kk, 0) + vv
    rows.sort(key=lambda r: int(r["idx"]))
    if phase == "build":
        merged = {"protocol": header["protocol"], "token": header["token"], "k": int(k),
                  "n": int(header["n"]), "pid": os.getpid(), "phase": "build", "rows": rows,
                  "built_syms": sorted(syms), "dates": list(dates),
                  "build_seconds": round(secs, 3), "build_peak_rss_mb": round(peak_all, 1)}
        J._pickle_atomic(out_k, merged)
        J._mark_done(shard_dir, k, header["token"], "build")
    else:
        cut = J._unpickle(shard_dir / "cut.pkl")["cut"]
        merged = {**(built or {}), "rows": rows, "phase": "rule", "cut": cut,
                  "cells_ruled": ruled, "seconds": round(secs, 3),
                  "peak_rss_mb": round(peak_all, 1), "stage_cache": stage_cache}
        J._pickle_atomic(out_k, merged)
        J._mark_done(shard_dir, k, header["token"], "rule", cut)
    return {"k": int(k), "phase": phase, "cause": cause, "cells": len(items),
            "part_size": size, "parts_run": parts_run, "deferred_cells": deferred}


def dispatch(shard_dir: Path, n: int, phase: str, ks: list[int] | None = None, *,
             runner: Callable[[list[str], dict[str, str]], tuple[Any, ...]] | None = None,
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
    box_free = adm.measure()
    budget = ((FREE_SHARE * box_free - adm.reserve) / cap) if box_free is not None else None
    records: list[dict[str, Any]] = RUN.setdefault("shards", [])
    planned = RUN.get("planned_cells")
    RUN.setdefault("dispatch", []).append(
        {"phase": phase, "ks": todo, "n": n, "max_concurrency": cap,
         "free_mb_at_start": round(box_free, 1) if box_free is not None else None,
         "child_budget_mb": round(budget, 1) if budget is not None else None,
         "reserve_mb": round(adm.reserve, 1)})

    def one(k: int, serial: bool = False) -> Exception | None:
        """One shard attempt. EVERYTHING is inside the try (audit D5): a prediction, admission
        or bookkeeping fault is this shard's failure, never a thread that dies silently and
        reads as success."""
        t0 = time.time()
        peak: float | None = None
        err: Exception | None = None
        need = 0.0
        base = 0.0
        cells: int | None = None
        oom = False
        admitted = False
        try:
            base = plan_base_mb(Path(shard_dir), k)
            cells = shard_cells(Path(shard_dir), k, planned, n)
            need = adm.predict(base, cells)
            # Every attempt, first wave or serial retry, is admitted on MEASURED free memory:
            # no child is launched into memory the box does not have (8 GB cold start).
            if not adm.acquire(need, key=k):
                raise ShardNoRoom(f"shard {k} {phase}: {need:.0f} MB predicted, not admitted "
                                  f"within {ADMIT_WAIT_S:.0f} s with nothing else running")
            admitted = True
            # A serial retry runs alone, so it may take the whole measured room.
            room = adm.measure() if serial else None
            child = (room - adm.reserve) if room is not None else budget
            env = child_env(max(need, child) if child is not None else None)
            argv = [sys.executable, "-u", "-c", _CODE, str(shard_dir), str(k), phase]
            if run_ is run_child:
                out = run_child(argv, env, on_sample=lambda mb: adm.sample(k, mb))
            else:
                out = run_(argv, env)
            rc, peak = int(out[0]), out[1]
            info = out[2] if len(out) > 2 and isinstance(out[2], dict) else {}
            oom = bool(info.get("oom"))
            if rc != 0:
                err = (MemoryError(f"shard {k} {phase} died of memory (rc={rc})") if oom
                       else subprocess.CalledProcessError(rc, f"shard {k} {phase}"))
        except ShardNoRoom as exc:       # never launched: no memory death, nothing to shrink
            err = exc
        except MemoryError as exc:       # the parent itself ran out: still this shard's failure
            err, oom = exc, True
        except Exception as exc:         # launch / bookkeeping failure is evidence, retried below
            err = exc
        finally:
            if admitted:
                adm.release(peak, key=k, base=base, cells=cells)
        if oom:
            # AUDIT D3: a memory death lowers this run's concurrency and its peak feeds the model.
            adm.shrink()
        rec = {"k": k, "phase": phase, "ok": err is None, "serial_retry": serial,
               "seconds": round(time.time() - t0, 1), "peak_mb": peak, "oom": oom,
               "predicted_mb": round(need, 1), "base_mb": round(base, 1), "cells": cells,
               "error": None if err is None else f"{type(err).__name__}: {err}"[:300]}
        if peak and cells:
            # Failed shards' peaks count too (D1): a shard that died at 9 GB measured 9 GB.
            rec["per_cell_mb"] = round(max(0.0, float(peak) - base) / cells, 5)
        records.append(rec)
        return err

    threads: list[threading.Thread] = []
    results: dict[int, Exception | None] = {}
    _MISSING = RuntimeError("shard thread ended without a result")

    def worker(k: int) -> None:
        try:
            results[k] = one(k)
        except BaseException as exc:     # recorded as this shard's failure
            results[k] = exc if isinstance(exc, Exception) else RuntimeError(repr(exc))

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

    # A MISSING RESULT IS A FAILURE (audit D5): only an explicit None is success.
    failed = [k for k in todo if k not in results or results[k] is not None]

    def _recut(shard_dir: Path, k: int, phase: str, adm: Admission, run_: Any,
               exc: BaseException) -> bool:
        cause = "not_admitted" if isinstance(exc, ShardNoRoom) else "oom_alone"
        last = next((r for r in reversed(records) if r.get("k") == k), {})
        entry = {"k": k, "phase": phase, "n": n, "cause": cause, "error": str(exc)[:300],
                 "cells": last.get("cells"), "peak_mb": last.get("peak_mb"),
                 "predicted_mb": last.get("predicted_mb"), "free_mb": adm.measure(),
                 "reserve_mb": round(adm.reserve, 1)}
        try:
            got = split_shard(shard_dir, k, phase, adm,
                              runner=None if run_ is run_child else run_, cause=cause)
        except Exception as split_exc:
            record_blocked({**entry, "action": "BLOCKED",
                            "why": f"{type(split_exc).__name__}: {split_exc}"[:300]})
            print(f"BLOCKED_SHARD_OOM: {phase} shard {k}: {split_exc}", flush=True)
            return False
        record_blocked({**entry, "action": "SPLIT", **got})
        print(f"BLOCKED_SHARD_OOM: {phase} shard {k} re-cut into {got['parts_run']} part(s) of "
              f"<= {got['part_size']} cell(s); {len(got['deferred_cells'])} cell(s) deferred",
              flush=True)
        return True
    if failed:
        print(f"SHARD RECOVERY: {len(failed)}/{len(todo)} {phase} shard(s) failed; retrying "
              "only those shards serially (alone) after peer memory was released", flush=True)
    for k in failed:
        last_exc = results.get(k) or _MISSING
        for attempt in range(1, _retry_attempts() + 1):
            exc = one(k, serial=True)
            if exc is None:
                print(f"SHARD RECOVERY: {phase} shard {k} recovered on retry {attempt}",
                      flush=True)
                break
            last_exc = exc
            print(f"SHARD RECOVERY: {phase} shard {k} retry {attempt} failed: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            if isinstance(exc, MemoryError):
                # OUT OF MEMORY ALONE (audit M3). The same cut would fail the same way on every
                # attempt for the epoch's whole life; it is named and RE-CUT instead.
                if _recut(shard_dir, k, phase, adm, run_, exc):
                    break
                raise RuntimeError(f"{phase} shard {k} BLOCKED_SHARD_OOM: no cut this box has "
                                   "memory for; refusing partial merge") from exc
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


def forward_args(judge: Any, argv: list[str]) -> int:
    """RunGauntlet.cmd passes `%*` here. The sealed judge's own CLI owns those flags (today
    `--only` / `--report-to`, the single-cell reproduction path, which writes no authority file
    and must not be sharded), so they go to `judge._cli_main()` VERBATIM under the judge's own
    argv[0]. An unknown flag therefore fails loudly in the judge's argparse instead of being
    dropped and running a full certifying sweep the caller did not ask for."""
    saved = sys.argv
    sys.argv = [str(DESK / "scripts" / "external_gauntlet.py"), *argv]
    try:
        return int(judge._cli_main() or 0)
    finally:
        sys.argv = saved


def main(argv: list[str] | None = None) -> int:
    from research.judging_throughput import apply_env

    args = list(sys.argv[1:] if argv is None else argv)
    apply_env()
    if args:
        from scripts import external_gauntlet as judge
        print(f"{datetime.now(UTC).isoformat()} run_sharded_gauntlet: forwarding {args!r} "
              "to the judge's own CLI (unsharded)", flush=True)
        return forward_args(judge, args)
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
