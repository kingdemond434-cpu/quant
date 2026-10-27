"""BLAS THREAD DIFFERENTIAL -- does single-threaded BLAS leave every judge output byte-identical?

THE QUESTION

Pinning `OPENBLAS_NUM_THREADS` / `MKL_NUM_THREADS` / `OMP_NUM_THREADS` to 1 in the judge's
workers would end BLAS oversubscription (eighteen workers x eighteen BLAS threads on an
eighteen-core box). But a LAPACK/BLAS routine may sum in a different order at a different
thread count, and the judge's correlation census (`mt5desk.canonical`: the Gram/GEMM path and
`numpy.linalg.eigvalsh` at canonical.py:229) feeds `trial_census`, the `dsr_inputs` rho, the
rounded-up DSR trial charge and the DSR bar -- sealed outputs. This harness MEASURES whether the
thread count moves any of them, so the switch (`research/blas_threads.py`) can be licensed by
evidence or refused by it.

WHAT IT DOES

  1. PREPARE (one subprocess): reads a recorded sweep's input set from disk -- the shard plan
     the last sharded sweep left (`reports/gauntlet_cache/shards/plan.pkl`, the default), a sweep
     report (`reports/universal_gates_external.json`), a JSON cell list, or a prepared cells
     pickle -- picks a bounded, deterministic sample (sha256 rank of the cell identity; default
     500), and loads each sampled cell's series pair from the judge's own content-addressed cache
     through the judge's own build loop with the fresh-build budget already spent, so NOTHING is
     built and nothing is written. The frozen cells go to a scratch pickle.
  2. JUDGE, THREE TIMES (fresh subprocesses, because BLAS reads its thread count once, at load):
     arm `default` with the three variables UNSET, arm `single` with all three = 1, and a second
     `control` default arm (on by default; `--no-control` skips it, and a proof without it never
     licenses the switch) that measures the judge's own run-to-run noise. Each arm runs the
     SEALED `external_gauntlet.run_gauntlet` on the identical frozen cells, and rebuilds a
     family-STRATIFIED sample of the recorded plan -- builds that reach `causal_residual`
     (lstsq/solve), the other orthogonal families (eigh/lstsq), then the rest -- through the
     pre-warm worker's own function (`_warm_one`, cache I/O diverted), so the build path the
     pre-warm pool and MT5-CacheWarm share is covered too. A build that produced no series is
     LOST coverage, counted per stratum, never silently skipped.
  3. COMPARE, BYTE FOR BYTE: every verdict row (canonical JSON), the whole sweep result except
     its timestamp, `trial_census`, the `dsr_inputs` rho, the rounded-up per-family DSR trial
     charge (`dsr_inputs.effective_trials`), the campaign charge `n_trials`, the DSR bar (the
     constitution's `dsr_threshold` and every cell's `sr0`), and the rebuilt series.
  4. LOCALISE: inside each arm a pure-numpy probe re-runs the census's own steps on the exact
     matrix the judge handed the census -- the correlation matrix, `eigvalsh`, the Gram the
     finite path uses, both participation ratios -- and records their digests and float.hex, so
     a difference can be pinned to the step that produced it.
  5. REPORT: `reports/BLAS_DIFFERENTIAL.json`, verdict IDENTICAL / DIFFERS (every difference
     listed) / UNMEASURED (with the reason), wall and CPU time per cell for each arm, the
     evidence floor and whether it clears, and the identity (release, cores, numpy, Python, BLAS
     build, CPU model) the proof is bound to. An eigvalsh spectrum that moves with the thread
     count is a difference, not mere localisation. The report carries a run id; one row of
     `data/blas_differential_runs.jsonl` binds it, and where the box holds the release-signing
     key the digest is HMAC'd under it (`research/blas_threads.py` explains why).

CLOCK: hourly leg `blas_differential` (`--if-lapsed`): it measures only when the proof is absent,
from another release/identity, within a day of lapsing, no longer the latest run, or UNMEASURED
for six hours -- so its cost is one JSON read on most hours and a bounded run after an adoption.
CONSUMER: `research/judging_throughput.py` (through `research/blas_threads.py`), which applies the
switch to the judge's environment and publishes its state in JUDGING_THROUGHPUT.json every hour,
and `scripts/warm_gauntlet_cache.py`, which takes the same decision for MT5-CacheWarm.

WHAT IT NEVER DOES

  * It writes nothing but the report, one run-log row and its own scratch directory (a fresh
    temp directory, deleted afterwards). Every child installs a write guard (a
    `sys.addaudithook`) that REFUSES any write, rename, delete, mkdir, utime or writable sqlite
    open under the repository outside the scratch directory, and any subprocess at all, and the
    refused attempts are listed in the report. `cache_save` is diverted; no ledger, verdict
    file, cursor or cache entry is touched.
  * It changes no trial count, gate, bar or CPU priority, and edits no sealed file. The judge is
    imported and called, never modified.
  * Inputs that live outside the BLAS question are FROZEN across arms (recorded by the first arm,
    replayed by the others, keyed by their exact arguments): the constitution read, the lifetime
    trial ledger read and the live cost read. A live box appends to those between arms, and a
    difference caused by a ledger append is not a BLAS difference. A call whose arguments differ
    between arms misses the replay and runs live, so a BLAS-induced argument change still shows.

THE PROOF IS ONLY AS GOOD AS ITS EVIDENCE THAT THE ARMS DIFFERED. IDENTICAL requires the two
arms to have measurably run different BLAS thread counts (threadpoolctl, else process thread
counts); a box where both ran one thread proves nothing and reports UNMEASURED.

Box command (Desk health): see the bundle README. Windows-safe: psutil for CPU time, no
`os.replace` onto a read-only file, no POSIX-only calls.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import math
import os
import pickle
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import blas_threads  # noqa: E402  (stdlib only; never imports numpy)

REPORT = DESK / "reports" / "BLAS_DIFFERENTIAL.json"
DEFAULT_PLAN = DESK / "reports" / "gauntlet_cache" / "shards" / "plan.pkl"
DEFAULT_SWEEP = DESK / "reports" / "universal_gates_external.json"
DEFAULT_META = DESK / "data" / "universe" / "universe.json"

SCHEMA = blas_threads.SCHEMA
THREAD_VARS = blas_threads.THREAD_VARS
IDENTICAL, DIFFERS, UNMEASURED = (blas_threads.IDENTICAL, blas_threads.DIFFERS,
                                  blas_threads.UNMEASURED)
#: A prepared input: frozen cell objects exactly as the judge's build loop returns them.
CELLS_KIND = "blas_differential_cells/v1"
DEFAULT_SAMPLE = 500
DEFAULT_REBUILD = 25
DEFAULT_ARM_TIMEOUT_S = 4 * 3600.0
#: The sweep-result keys that are wall-clock facts, not judge outputs.
VOLATILE_RESULT_KEYS = frozenset({"swept_at"})
#: Read-side calls frozen across arms: (module, attribute) -> how its arguments are keyed.
FROZEN_CALLS = (("scripts.external_gauntlet", "constitution_thresholds"),
                ("scripts.external_gauntlet", "lifetime_trial_report"),
                ("research.cost_to_edge", "verdict"))
#: Fixed `judged_at` for the derived dsr_inputs rows, so the derivation itself is deterministic.
_FIXED_JUDGED_AT = "2000-01-01T00:00:00+00:00"


# ============================================================================ small utilities
def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _cpu_seconds() -> float:
    """This process's user+system CPU seconds (psutil; os.times when psutil is absent)."""
    try:
        import psutil
        t = psutil.Process().cpu_times()
        return float(t.user + t.system)
    except Exception:
        t2 = os.times()
        return float(t2.user + t2.system)


def _jsonable(o: Any) -> Any:
    """json.dumps default: numpy scalars/arrays, timestamps, paths, sets."""
    item = getattr(o, "item", None)
    if callable(item) and getattr(o, "ndim", None) == 0:
        return item()
    tolist = getattr(o, "tolist", None)
    if callable(tolist):
        return tolist()
    iso = getattr(o, "isoformat", None)
    if callable(iso):
        return iso()
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=repr)
    if isinstance(o, Path):
        return str(o)
    return repr(o)


def canon(x: Any) -> str:
    """The byte-level identity of a judge output: canonical JSON, floats by repr (exact)."""
    return json.dumps(x, sort_keys=True, default=_jsonable, allow_nan=True,
                      separators=(",", ":"))


def _strict(x: Any) -> Any:
    """A JSON-strict copy (non-finite floats as strings), for the published report."""
    if isinstance(x, float):
        return x if math.isfinite(x) else repr(x)
    if isinstance(x, Mapping):
        return {str(k): _strict(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_strict(v) for v in x]
    return x


def _sha256_file(path: Path) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def cell_key(spec: Mapping[str, Any]) -> str:
    """A stable identity for a spec or cell, independent of process and hash seed."""
    return json.dumps({"s": str(spec.get("sym")), "f": str(spec.get("family")),
                       "p": spec.get("params") or {}}, sort_keys=True, default=str)


def sample_order(items: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Distinct items ranked by sha256 of their identity: deterministic, spread across the plan,
    and independent of the order the recorded sweep happened to list them in."""
    seen: dict[str, Mapping[str, Any]] = {}
    for it in items:
        if isinstance(it, Mapping) and it.get("sym") and it.get("family"):
            seen.setdefault(cell_key(it), it)
    return [seen[k] for k in sorted(seen, key=lambda k: hashlib.sha256(k.encode()).hexdigest())]


# =================================================================================== write guard
_GUARD: dict[str, Any] = {"blocked": [], "installed": False}
_WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC)


def _norm(p: Any) -> str | None:
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    if not isinstance(p, (str, os.PathLike)):
        return None
    try:
        return os.path.normcase(os.path.abspath(os.fspath(p)))
    except (TypeError, ValueError):
        return None


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("\\/") + os.sep)


def install_write_guard(protected: Iterable[Path], allowed: Iterable[Path]) -> None:
    """Refuse every write/rename/delete/mkdir under `protected` outside `allowed`, process-wide.

    An audit hook cannot be removed, so this is called only in the harness's own children.
    Refused attempts are recorded in `_GUARD["blocked"]` and published with the arm's output.
    """
    prot = [r for r in (_norm(p) for p in protected) if r]
    allow = [r for r in (_norm(p) for p in allowed) if r]

    def refused(path: Any) -> str | None:
        n = _norm(path)
        if n is None or "__pycache__" in n:
            return None
        if any(_under(n, a) for a in allow):
            return None
        return n if any(_under(n, r) for r in prot) else None

    def hook(event: str, args: tuple) -> None:
        target = None
        if event == "open" and args:
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else 0
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and bool(flags & _WRITE_FLAGS))
            if writing:
                target = refused(args[0])
        elif event in ("os.rename", "os.replace", "os.link", "os.symlink") and len(args) > 1:
            target = refused(args[1]) or refused(args[0])
        elif event in ("os.remove", "os.unlink", "os.rmdir", "os.mkdir", "os.truncate",
                       "os.chmod", "os.utime", "shutil.rmtree", "shutil.move",
                       "shutil.copyfile") and args:
            target = refused(args[0]) or (refused(args[1]) if event in (
                "shutil.move", "shutil.copyfile") and len(args) > 1 else None)
        elif event == "sqlite3.connect" and args:
            # A database opened read-only (`file:...?mode=ro`) cannot write; anything else can.
            db = os.fsdecode(args[0]) if isinstance(args[0], bytes) else str(args[0])
            if "mode=ro" not in db:
                target = refused(db[5:].split("?", 1)[0] if db.startswith("file:") else db)
        elif event == "subprocess.Popen":
            # NO CHILD OF A CHILD. A subprocess runs outside this hook, so it could write what
            # the guard refuses; the harness's children need none, and any attempt is listed.
            target = f"<subprocess {os.fsdecode(args[0]) if args and args[0] else '?'}>"
        if target is not None:
            if len(_GUARD["blocked"]) < 200:
                _GUARD["blocked"].append({"event": event, "path": target})
            raise PermissionError(f"blas_thread_differential write guard refused {event} "
                                  f"{target}")

    sys.addaudithook(hook)
    _GUARD["installed"] = True


# ================================================================================ input loading
def load_input(path: Path, meta_path: Path | None = None) -> dict[str, Any]:
    """Read a recorded sweep's input set. Returns {kind, specs|cells, meta, provenance}."""
    path = Path(path)
    prov = {"path": str(path), "sha256": _sha256_file(path),
            "mtime_utc": (datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
                timespec="seconds") if path.exists() else None)}
    meta: Any = None
    if path.suffix.lower() == ".pkl":
        with open(path, "rb") as fh:
            obj = pickle.load(fh)  # noqa: S301 -- the judge's own plan, or this harness's
        if isinstance(obj, dict) and obj.get("kind") == CELLS_KIND:
            return {"kind": "cells", "cells": list(obj.get("cells") or []),
                    "meta": obj.get("meta") or {}, "rebuild_specs":
                    list(obj.get("rebuild_specs") or []), "provenance": prov}
        if isinstance(obj, dict) and isinstance(obj.get("specs"), list):
            prov.update(plan_protocol=obj.get("protocol"), plan_token=obj.get("token"),
                        plan_shards=obj.get("n"))
            specs, meta = list(obj["specs"]), obj.get("meta")
        else:
            raise ValueError(f"{path.name}: neither a shard plan nor a {CELLS_KIND} pickle")
    else:
        doc = json.loads(path.read_text("utf-8"))
        if isinstance(doc, list):
            specs = doc
        elif isinstance(doc, dict) and isinstance(doc.get("verdicts"), list):
            specs = [{"sym": v.get("sym"), "family": v.get("family"),
                      "params": v.get("params") or {}} for v in doc["verdicts"]
                     if isinstance(v, dict)]
            prov.update(swept_at=doc.get("swept_at"), hunt=doc.get("hunt"))
        elif isinstance(doc, dict) and isinstance(doc.get("specs") or doc.get("cells"), list):
            specs = list(doc.get("specs") or doc.get("cells"))
            meta = doc.get("meta")
        else:
            raise ValueError(f"{path.name}: no cell list, `specs`, `cells` or `verdicts` found")
    if not isinstance(meta, dict):
        mp = Path(meta_path or DEFAULT_META)
        meta = json.loads(mp.read_text("utf-8"))
        prov["meta_path"] = str(mp)
    specs = [s for s in specs if isinstance(s, dict)]
    prov["n_specs"] = len(specs)
    return {"kind": "specs", "specs": specs, "meta": meta, "rebuild_specs": [],
            "provenance": prov}


def default_input() -> Path | None:
    for p in (DEFAULT_PLAN, DEFAULT_SWEEP):
        if p.exists():
            return p
    return None


# ===================================================================================== prepare
def _prepare(job: dict[str, Any]) -> dict[str, Any]:
    """Child: freeze a bounded sample of cached cells into the scratch pickle."""
    scratch = Path(job["scratch"])
    loaded = load_input(Path(job["input"]), Path(job["meta"]) if job.get("meta") else None)
    n, n_rebuild = int(job["sample"]), int(job["rebuild"])
    meta = loaded["meta"]
    strata = family_strata()
    if loaded["kind"] == "cells":
        cells = list(sample_order(loaded["cells"]))[:n]
        rebuild, plan = stratified_rebuild(list(loaded["rebuild_specs"]), n_rebuild, strata)
        scanned, not_cached, blocked_n = len(cells), 0, 0
    else:
        from scripts import external_gauntlet as eg
        eg.cache_save = _refuse_cache_save           # belt and braces: the guard also refuses
        cells, deferred, blocked = [], [], []
        built_syms: set[str] = set()
        scanned = 0
        for sp in sample_order(loaded["specs"]):
            if len(cells) >= n:
                break
            scanned += 1
            s0, s0v = eg.stage0_new_summary(), {}
            # `_build_t0 = 0.0`: the fresh-build budget is already spent, so a spec with no cached
            # series is DEFERRED by the judge's own loop and nothing is ever built here.
            acc = eg._build_specs([sp], meta, 0.0, s0, s0v, built_syms, blocked,
                                  cell_objs=cells, deferred=deferred)
            cells, deferred = acc["cell_objs"], acc["deferred"]
        not_cached, blocked_n = len(deferred), len(blocked)
        # THE REBUILD IS DRAWN FROM THE WHOLE RECORDED PLAN, stratified by family module -- the
        # families whose builds call lstsq/solve (causal_residual), the orthogonal families
        # (eigh/lstsq), then the rest -- because a build's BLAS dependence is a property of its
        # family, and the first N cells of a hash order can all be one family.
        rebuild, plan = stratified_rebuild(loaded["specs"], n_rebuild, strata)
    out = scratch / "cells.pkl"
    with open(out, "wb") as fh:
        pickle.dump({"kind": CELLS_KIND, "meta": meta, "cells": cells,
                     "rebuild_specs": rebuild}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return {"provenance": loaded["provenance"], "input_kind": loaded["kind"],
            "sampled_cells": len(cells), "scanned_specs": scanned,
            "skipped_not_cached": not_cached, "skipped_blocked": blocked_n,
            "rebuild_cells": len(rebuild), "rebuild_plan": plan, "cells_pickle": str(out),
            "cell_ids": [cell_key(c) for c in cells]}


#: The family strata the rebuild covers, in the order they are drawn from.
STRATA = ("causal_residual", "families_orthogonal", "families")


def family_strata() -> dict[str, str]:
    """family -> stratum: `causal_residual` for an orthogonal family whose build reaches
    `mt5desk.causal_residual` (directly or through a helper in the same module),
    `families_orthogonal` for the other orthogonal families; everything else is `families`."""
    try:
        import inspect

        from mt5desk import families_orthogonal as fo
    except Exception:
        return {}
    src: dict[str, str] = {}
    for name, obj in vars(fo).items():
        if inspect.isfunction(obj) and getattr(obj, "__module__", "") == fo.__name__:
            with contextlib.suppress(OSError, TypeError):
                src[name] = inspect.getsource(obj)
    reach = {n for n, t in src.items() if "causal_residual(" in t}
    for _ in range(6):                     # helpers of helpers, bounded
        grown = {n for n, t in src.items() if n not in reach and any(
            f"{h}(" in t for h in reach)}
        if not grown:
            break
        reach |= grown
    out: dict[str, str] = {}
    for fam, fn in getattr(fo, "ORTHOGONAL_FAMILIES", {}).items():
        out[str(fam)] = ("causal_residual" if getattr(fn, "__name__", "") in reach
                         else "families_orthogonal")
    return out


def stratified_rebuild(specs: Iterable[Mapping[str, Any]], n: int,
                       strata: Mapping[str, str]) -> tuple[list[dict], list[dict]]:
    """Up to `n` specs, round-robin over STRATA and, inside each, over families (hash order).

    Returns (specs, plan): the plan names each pick's family and stratum, plus one row per
    stratum present in the input, so the report can say which strata were asked for at all."""
    by: dict[str, dict[str, list[Mapping[str, Any]]]] = {s: {} for s in STRATA}
    for sp in sample_order(specs):
        fam = str(sp.get("family"))
        by[strata.get(fam, "families")].setdefault(fam, []).append(sp)
    picks: list[dict] = []
    plan: list[dict] = []
    queues = {s: [list(v) for _, v in sorted(by[s].items())] for s in STRATA}
    while len(picks) < max(0, int(n)) and any(any(q) for q in queues.values()):
        for s in STRATA:
            fams = queues[s]
            while fams and not fams[0]:
                fams.pop(0)
            if not fams or len(picks) >= n:
                continue
            sp = fams[0].pop(0)
            fams.append(fams.pop(0))           # next family of this stratum next time
            picks.append({k: sp.get(k) for k in ("sym", "family", "params", "mechanism_status",
                                                 "mechanism_note")})
            plan.append({"key": cell_key(sp), "family": str(sp.get("family")), "stratum": s})
    present = {s: sum(len(v) for v in by[s].values()) for s in STRATA}
    return picks, [*plan, *({"stratum_in_input": s, "specs": c} for s, c in present.items())]


def _refuse_cache_save(*_a: Any, **_k: Any) -> None:
    raise PermissionError("blas_thread_differential never writes the series cache")


# ======================================================================================== arms
def thread_info() -> dict[str, Any]:
    """The BLAS thread counts this process actually loaded (threadpoolctl), and its OS threads."""
    import numpy as np
    out: dict[str, Any] = {"env": {k: os.environ.get(k) for k in THREAD_VARS}}
    try:
        from threadpoolctl import threadpool_info
        out["threadpoolctl"] = [{**{k: d.get(k) for k in (
            "user_api", "internal_api", "num_threads", "version", "prefix", "architecture",
            "threading_layer")}, "lib": os.path.basename(str(d.get("filepath") or ""))}
            for d in threadpool_info()]
    except Exception as exc:
        out["threadpoolctl"] = None
        out["threadpoolctl_why"] = f"{type(exc).__name__}: {exc}"[:200]
    a = np.random.default_rng(0).standard_normal((768, 768))
    _ = a @ a                                          # wake the BLAS pool before counting
    try:
        import psutil
        out["os_threads"] = int(psutil.Process().num_threads())
    except Exception:
        out["os_threads"] = None
    return out


class Freezer:
    """Record (first arm) or replay (later arms) read-side calls, keyed by exact arguments."""

    def __init__(self, path: Path, record: bool) -> None:
        self.path, self.record = path, record
        self.store: dict[str, Any] = {}
        self.stats: dict[str, dict[str, int]] = {}
        if not record and path.exists():
            with open(path, "rb") as fh:
                self.store = pickle.load(fh)  # noqa: S301 -- written by the first arm

    def wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        st = self.stats.setdefault(name, {"recorded": 0, "replayed": 0, "missed": 0})

        def frozen(*args: Any, **kwargs: Any) -> Any:
            args = tuple(tuple(a) if (hasattr(a, "__next__") and hasattr(a, "__iter__"))
                         else a for a in args)
            try:
                key = hashlib.sha256(pickle.dumps((name, args, sorted(kwargs.items())),
                                                  protocol=4)).hexdigest()
            except Exception:
                key = None
            if key is not None and not self.record and key in self.store:
                st["replayed"] += 1
                return copy.deepcopy(self.store[key])
            value = fn(*args, **kwargs)
            if key is not None and self.record:
                with contextlib.suppress(Exception):
                    self.store[key] = copy.deepcopy(value)
                st["recorded"] += 1
            elif not self.record:
                st["missed"] += 1
            return value

        return frozen

    def save(self) -> None:
        if self.record:
            with open(self.path, "wb") as fh:
                pickle.dump(self.store, fh, protocol=pickle.HIGHEST_PROTOCOL)


def _series_digest(s: Any) -> str | None:
    """Digest of a daily series' values and dates, exactly."""
    if s is None:
        return None
    import numpy as np
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(s.to_numpy(float)).tobytes())
    h.update("|".join(map(str, s.index)).encode("utf-8"))
    return h.hexdigest()


def _hex(x: Any) -> str | None:
    try:
        return float(x).hex()
    except (TypeError, ValueError):
        return None


def _digest(a: Any) -> str:
    import numpy as np
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def _eig_rank(arrs: list[Any]) -> float | None:
    """canonical.effective_trials' eigvalsh branch (canonical.py:229), verbatim arithmetic."""
    import numpy as np
    from mt5desk import canonical
    c = canonical._corr_matrix(arrs)
    if c is None:
        return None
    ev = np.clip(np.linalg.eigvalsh(c), 0.0, None)
    den = float((ev ** 2).sum())
    if den <= 0:
        return None
    return max(2.0, min(float(ev.sum() ** 2 / den), float(len(arrs))))


def probe(cols: list[Any], scratch: Path, arm: str) -> dict[str, Any]:
    """Re-run the census's own numeric steps on the exact matrix the judge handed it.

    Two layers. `raw`: bit-level digests and float.hex of every intermediate (the correlation
    matrix, its eigvalsh spectrum, the Gram the finite path uses, both participation ratios) --
    LOCALISATION ONLY, because the judge rounds before it publishes. `reported`: what the judge
    WOULD publish from each census branch, rounded exactly as `deflation_pair` rounds it -- the
    branch it took (also compared directly in the sweep result) and the eigvalsh branch at
    canonical.py:229, which the judge takes only on a non-finite matrix. A difference in
    `reported` is a judge-output difference and makes the verdict DIFFERS.
    """
    import numpy as np
    from mt5desk import canonical
    arrs = [np.asarray(c, dtype=float) for c in cols]
    m = np.column_stack(arrs)
    n_raw = len(arrs)
    finite = bool(np.isfinite(m).all())
    raw: dict[str, Any] = {"shape": list(m.shape)}
    reported: dict[str, Any] = {"matrix_sha256": _digest(m), "finite": finite,
                                "census_path": "finite_gram" if finite else "eigvalsh"}
    t0 = time.perf_counter()
    corr = canonical._corr_matrix(arrs)
    if corr is not None:
        raw["corr_sha256"] = _digest(corr)
        ev = np.linalg.eigvalsh(corr)
        np.save(scratch / f"eigvals_{arm}.npy", ev)
        raw["eigvalsh_sha256"] = _digest(ev)
        raw["eigvals_file"] = f"eigvals_{arm}.npy"
    raw["eigvalsh_seconds"] = round(time.perf_counter() - t0, 4)
    # THE EIGVALSH BRANCH, carried through the null calibration and the judge's rounding.
    observed = _eig_rank(arrs)
    eig: dict[str, Any] = {"observed_hex": _hex(observed)}
    if observed is not None:
        rng = np.random.default_rng(canonical.NULL_CALIBRATION_SEED)
        nulls = [_eig_rank([rng.permutation(col) for col in arrs])
                 for _ in range(canonical.NULL_CALIBRATION_DRAWS)]
        if all(x is not None for x in nulls):
            floor = float(np.mean([float(x) for x in nulls if x is not None]))
            cal = max(2.0, min(float(n_raw), observed / floor * n_raw)) if floor > 0 else None
            eig.update(null_floor_hex=_hex(floor), calibrated_hex=_hex(cal))
            if cal is not None:
                reported["eigvalsh_path_n_effective"] = round(cal, 2)
                reported["eigvalsh_path_rho"] = round(cal, 2) / n_raw
    raw["eigvalsh_path"] = eig
    # THE FINITE BRANCH canonical.effective_trials takes on finite input (GEMM + sums).
    keep = m.std(axis=0) > 0
    if m.shape[0] >= canonical.MIN_SERIES and keep.sum() >= 2 and finite:
        z = m[:, keep]
        z = z - z.mean(axis=0)
        z /= np.sqrt(np.sum(z * z, axis=0))
        gram = z @ z.T if z.shape[0] < z.shape[1] else z.T @ z
        raw["gram_shape"] = list(gram.shape)
        raw["gram_sha256"] = _digest(gram)
        den = float(np.sum(gram * gram))
        raw["gram_participation_hex"] = _hex(np.trace(gram) ** 2 / den) if den > 0 else None
    et = canonical.effective_trials(arrs, include_clone_pairs=False)
    nc = canonical.null_calibrated_effective_trials(arrs, include_clone_pairs=False)
    raw.update(effective_trials_method=et.method, effective_trials_hex=_hex(et.n_effective),
               null_calibrated_method=nc.method, null_calibrated_hex=_hex(nc.n_effective))
    reported.update(taken_path_method=nc.method,
                    taken_path_n_effective=round(nc.n_effective, 2),
                    taken_path_rho=round(nc.n_effective, 2) / n_raw)
    return {"reported": reported, "raw": raw}


def derived_quantities(result: Mapping[str, Any]) -> dict[str, Any]:
    """The dsr_inputs quantities the sweep report feeds: rho and the rounded-up family charge."""
    out: dict[str, Any] = {"n_trials": result.get("n_trials"),
                           "trial_count_basis": result.get("trial_count_basis"),
                           "trial_census": result.get("trial_census"),
                           "dsr_bar": (result.get("constitution") or {}).get("dsr_threshold")
                           if isinstance(result.get("constitution"), Mapping) else None}
    try:
        from libs.research import dsr_inputs
        ratio = getattr(dsr_inputs, "_census_ratio", None)
        if callable(ratio):
            rho, method = ratio(result)
            out["rho"], out["rho_hex"], out["rho_method"] = rho, _hex(rho), method
        rows = dsr_inputs.trial_rows(result, sweep_id="blas_thread_differential",
                                     judged_at=_FIXED_JUDGED_AT)
        out["family_effective_trials"] = dsr_inputs.effective_trials(rows)
    except Exception as exc:
        out["dsr_inputs_error"] = f"{type(exc).__name__}: {exc}"[:200]
    out["cell_dsr"] = {
        str(v.get("cell")): {k: (v.get("stages") or {}).get("deflated_sharpe", {}).get(k)
                             for k in ("n_trials", "sr0", "dsr", "passed")}
        for v in result.get("verdicts") or [] if isinstance(v, Mapping) and not v.get("unmeasured")}
    return out


def _arm(job: dict[str, Any]) -> dict[str, Any]:
    """Child: judge the frozen cells once under this process's BLAS thread count."""
    import importlib

    scratch, arm = Path(job["scratch"]), str(job["arm"])
    info_before = thread_info()
    with open(job["cells_pickle"], "rb") as fh:
        doc = pickle.load(fh)  # noqa: S301 -- written by this harness's prepare step
    cells, meta = list(doc["cells"]), doc["meta"]
    rebuild_specs = list(doc.get("rebuild_specs") or [])

    from scripts import external_gauntlet as eg
    eg.cache_save = _refuse_cache_save
    freezer = Freezer(scratch / "frozen_calls.pkl", record=bool(job.get("record")))
    frozen = []
    for mod_name, attr in FROZEN_CALLS:
        try:
            mod = importlib.import_module(mod_name)
            setattr(mod, attr, freezer.wrap(f"{mod_name}.{attr}", getattr(mod, attr)))
            frozen.append(f"{mod_name}.{attr}")
        except Exception as exc:
            frozen.append(f"{mod_name}.{attr}: NOT FROZEN ({type(exc).__name__})")

    from mt5desk import canonical
    captured: dict[str, Any] = {}
    real_census = canonical.calibrated_census_report

    def capturing_census(series: Iterable[Any], *a: Any, **k: Any) -> dict:
        cols = list(series)
        captured["cols"], captured["calls"] = cols, captured.get("calls", 0) + 1
        out = real_census(cols, *a, **k)
        captured["returned"] = copy.deepcopy(out)
        return out

    canonical.calibrated_census_report = capturing_census

    log = open(scratch / f"arm_{arm}.log", "w", encoding="utf-8")  # noqa: SIM115
    old_out = sys.stdout
    sys.stdout = log
    try:
        w0, c0 = time.perf_counter(), _cpu_seconds()
        result = eg.run_gauntlet(cells, "blas_thread_differential", meta)
        wall, cpu = time.perf_counter() - w0, _cpu_seconds() - c0

        rebuilt: dict[str, Any] = {}
        rw0, rc0 = time.perf_counter(), _cpu_seconds()
        if rebuild_specs:
            saved: dict[str, Any] = {}
            eg.cache_load = lambda _key: None                       # force the fresh path
            eg.cache_save = lambda key, ds1, ds3: saved.__setitem__(key, (ds1, ds3))
            for sp in rebuild_specs:
                saved.clear()
                st = eg._warm_one(sp, meta)
                ck = st.get("ckey")
                pair = saved.get(ck) if ck else None
                rebuilt[cell_key(sp)] = {
                    "status": st.get("status"), "ckey": ck,
                    "ds1_sha256": _series_digest(pair[0]) if pair else None,
                    "ds3_sha256": _series_digest(pair[1]) if pair else None}
        r_wall, r_cpu = time.perf_counter() - rw0, _cpu_seconds() - rc0
    finally:
        sys.stdout = old_out
        log.close()
    freezer.save()
    pr = probe(captured["cols"], scratch, arm) if captured.get("cols") else None
    n = max(1, len(cells))
    nr = max(1, len(rebuild_specs))
    return {"arm": arm, "pid": os.getpid(), "threads": info_before, "threads_after": thread_info(),
            "n_cells": len(cells), "n_judged": result.get("n_judged"),
            "timing": {"judge_wall_s": round(wall, 4), "judge_cpu_s": round(cpu, 4),
                       "per_cell_wall_ms": round(1000 * wall / n, 3),
                       "per_cell_cpu_ms": round(1000 * cpu / n, 3),
                       "rebuild_cells": len(rebuild_specs),
                       "rebuild_wall_s": round(r_wall, 4), "rebuild_cpu_s": round(r_cpu, 4),
                       "rebuild_per_cell_wall_ms": round(1000 * r_wall / nr, 3)
                       if rebuild_specs else None,
                       "rebuild_per_cell_cpu_ms": round(1000 * r_cpu / nr, 3)
                       if rebuild_specs else None},
            "result": {k: v for k, v in result.items() if k not in VOLATILE_RESULT_KEYS},
            "census_calls": captured.get("calls", 0), "census_returned": captured.get("returned"),
            "derived": derived_quantities(result), "probe": pr, "rebuilt": rebuilt,
            "frozen": frozen, "frozen_stats": freezer.stats,
            "write_guard_blocked": list(_GUARD["blocked"])}


# ================================================================================== comparison
def diff_paths(a: Any, b: Any, path: str = "", out: list | None = None,
               limit: int = 100000) -> list[dict[str, Any]]:
    """Every leaf at which `a` and `b` differ byte-for-byte (canonical JSON), by path."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append({"path": f"{path}/{k}", "a": a.get(k, "<absent>"),
                            "b": b.get(k, "<absent>")})
            elif canon(a[k]) != canon(b[k]):
                diff_paths(a[k], b[k], f"{path}/{k}", out, limit)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            if canon(x) != canon(y):
                diff_paths(x, y, f"{path}[{i}]", out, limit)
        return out
    if canon(a) != canon(b):
        out.append({"path": path or "/", "a": a, "b": b})
    return out


def _verdict_map(arm_doc: Mapping[str, Any]) -> dict[str, Any]:
    rows = (arm_doc.get("result") or {}).get("verdicts") or []
    return {str(v.get("cell")): v for v in rows if isinstance(v, Mapping)}


def compare_arms(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every byte-level difference between two arms' judge outputs, sectioned."""
    diffs: list[dict[str, Any]] = []

    def add(section: str, rows: list[dict[str, Any]]) -> None:
        for r in rows:
            diffs.append({"section": section, "path": r["path"], "a": r["a"], "b": r["b"]})

    va, vb = _verdict_map(a), _verdict_map(b)
    order_a = [str(v.get("cell")) for v in (a.get("result") or {}).get("verdicts") or []]
    order_b = [str(v.get("cell")) for v in (b.get("result") or {}).get("verdicts") or []]
    if order_a != order_b:
        add("verdict_order", [{"path": "/verdicts[*].cell", "a": order_a, "b": order_b}])
    for cid in sorted(set(va) | set(vb)):
        if canon(va.get(cid)) != canon(vb.get(cid)):
            add("verdict", diff_paths(va.get(cid), vb.get(cid), f"/{cid}"))
    ra = {k: v for k, v in (a.get("result") or {}).items() if k != "verdicts"}
    rb = {k: v for k, v in (b.get("result") or {}).items() if k != "verdicts"}
    add("sweep_result", diff_paths(ra, rb))
    add("derived", diff_paths(a.get("derived"), b.get("derived")))
    add("census_returned", diff_paths(a.get("census_returned"), b.get("census_returned")))
    add("probe_reported", diff_paths((a.get("probe") or {}).get("reported"),
                                     (b.get("probe") or {}).get("reported")))
    rba, rbb = a.get("rebuilt") or {}, b.get("rebuilt") or {}
    for key in sorted(set(rba) | set(rbb)):
        x, y = rba.get(key) or {}, rbb.get(key) or {}
        if x.get("ckey") != y.get("ckey"):
            continue                          # input moved between arms: not comparable
        if canon(x) != canon(y):
            add("rebuild", diff_paths(x, y, f"/{key}"))
    return diffs


def localise(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Bit-level differences in the census intermediates: where a thread count changes bits."""
    pa = copy.deepcopy((a.get("probe") or {}).get("raw") or {})
    pb = copy.deepcopy((b.get("probe") or {}).get("raw") or {})
    for p in (pa, pb):
        p.pop("eigvalsh_seconds", None)
        p.pop("eigvals_file", None)
    return diff_paths(pa, pb)


def rebuild_input_moves(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[str]:
    """Rebuilt cells whose cache key (data-day, code identity) changed between arms."""
    rba, rbb = a.get("rebuilt") or {}, b.get("rebuilt") or {}
    return sorted(k for k in set(rba) & set(rbb)
                  if (rba[k] or {}).get("ckey") != (rbb[k] or {}).get("ckey"))


def thread_evidence(single: Mapping[str, Any], default: Mapping[str, Any]) -> dict[str, Any]:
    """Did the two arms measurably run different BLAS thread counts?"""
    def blas_threads_of(doc: Mapping[str, Any]) -> list[int] | None:
        tp = (doc.get("threads") or {}).get("threadpoolctl")
        if not isinstance(tp, list) or not tp:
            return None
        return [int(d.get("num_threads") or 0) for d in tp
                if d.get("user_api") in ("blas", "openmp")]

    s, d = blas_threads_of(single), blas_threads_of(default)
    if s and d:
        ok = max(s) == 1 and max(d) > 1
        return {"basis": "threadpoolctl", "single": s, "default": d, "differed": ok,
                "why": ("single arm loaded 1 BLAS thread, default arm loaded "
                        f"{max(d)}" if ok else
                        f"single arm {s} vs default arm {d}: the arms did not run single "
                        "versus multi-threaded BLAS")}
    so = (single.get("threads") or {}).get("os_threads")
    do = (default.get("threads") or {}).get("os_threads")
    if isinstance(so, int) and isinstance(do, int):
        ok = do > so
        return {"basis": "os_thread_count", "single": so, "default": do, "differed": ok,
                "why": (f"process threads after a BLAS call: single {so}, default {do}"
                        + ("" if ok else " -- no evidence the arms differed"))}
    return {"basis": None, "differed": False,
            "why": "neither threadpoolctl nor psutil could read the arms' thread counts"}


def decide_verdict(arms: Mapping[str, Mapping[str, Any] | None],
                   failures: Mapping[str, str]) -> dict[str, Any]:
    """IDENTICAL / DIFFERS / UNMEASURED from the arms' outputs. Absence is never IDENTICAL."""
    single, default, control = arms.get("single"), arms.get("default"), arms.get("control")
    if failures or single is None or default is None:
        return {"verdict": UNMEASURED, "why": "an arm did not complete: " + "; ".join(
            f"{k}: {v}" for k, v in failures.items()) if failures else "an arm is missing",
            "differences": [], "n_differences": 0}
    diffs = compare_arms(default, single)
    noise = compare_arms(default, control) if control is not None else None
    noise_keys = {(r["section"], r["path"]) for r in noise or []}
    for r in diffs:
        r["also_in_control"] = None if noise is None else (r["section"], r["path"]) in noise_keys
        r["default"], r["single"] = r.pop("a"), r.pop("b")
    ev = thread_evidence(single, default)
    out: dict[str, Any] = {"thread_evidence": ev, "differences": diffs,
                           "n_differences": len(diffs),
                           "control_differences": None if noise is None else len(noise),
                           "rebuild_inputs_moved": rebuild_input_moves(default, single),
                           "localisation": {
                               "note": ("bit-level differences in the census's intermediates. "
                                        "The judge rounds before it publishes, so these are "
                                        "localisation, not verdict; any that survive the "
                                        "rounding appear above as probe_reported or verdict "
                                        "differences"),
                               "single_vs_default": localise(default, single),
                               "control_vs_default": (None if control is None
                                                      else localise(default, control))}}
    # AN EIGVALSH SPECTRUM THAT MOVES WITH THE THREAD COUNT BLOCKS IDENTICAL (audit of
    # 5d4d0279f). It is the branch canonical.py:229 takes on a non-finite matrix; a sample that
    # happened to be finite cannot speak for the sweep that is not, so a moved bit there is
    # listed as a difference, not merely localised.
    noise_loc = {r["path"] for r in (out["localisation"]["control_vs_default"] or [])}
    for r in out["localisation"]["single_vs_default"]:
        if "eigvalsh" in r["path"]:
            diffs.append({"section": "localisation_eigvalsh", "path": r["path"],
                          "default": r["a"], "single": r["b"],
                          "also_in_control": None if control is None
                          else r["path"] in noise_loc})
    out["n_differences"] = len(diffs)
    runtime = blas_runtime(arms)
    out["blas_runtime"] = runtime
    judged = min(int(single.get("n_judged") or 0), int(default.get("n_judged") or 0))
    if diffs:
        sections = sorted({r["section"] for r in diffs})
        out.update(verdict=DIFFERS, why=(f"{len(diffs)} byte-level difference(s) between the "
                                         f"default and single-threaded arms in {sections}"))
    elif not ev["differed"]:
        out.update(verdict=UNMEASURED, why=f"no thread contrast: {ev['why']}")
    elif not runtime["consistent"]:
        out.update(verdict=UNMEASURED, why=f"BLAS runtime not bound: {runtime['why']}")
    elif judged < 2 or not default.get("census_calls"):
        out.update(verdict=UNMEASURED, why=(f"{judged} judged cell(s); the census needs two "
                                            "columns, so the comparison never reached it"))
    else:
        n_loc = len(out["localisation"]["single_vs_default"])
        out.update(verdict=IDENTICAL, why=(
            f"{judged} judged cell(s): every verdict, the sweep result, the trial census, rho, "
            "the DSR trial charge and bar, and the rounded census both branches would publish "
            f"are byte-identical; {ev['why']}; {n_loc} bit-level difference(s) in unpublished "
            "census intermediates (see localisation)"))
    return out


def blas_runtime(arms: Mapping[str, Mapping[str, Any] | None]) -> dict[str, Any]:
    """The BLAS each arm actually loaded (threadpoolctl): one library, one version, one kernel
    architecture across every arm, and that library one numpy's RECORD ships (the identity)."""
    seen: dict[str, Any] = {}
    for name, a in arms.items():
        tp = ((a or {}).get("threads") or {}).get("threadpoolctl")
        if not isinstance(tp, list):
            continue
        seen[name] = sorted({(str(d.get("internal_api")), str(d.get("version")),
                              str(d.get("architecture")), str(d.get("lib")))
                             for d in tp if d.get("user_api") == "blas"})
    if not seen:
        return {"consistent": False, "arms": {}, "why": "threadpoolctl unreadable in every arm"}
    distinct = {json.dumps(v) for v in seen.values()}
    if len(distinct) != 1 or not next(iter(seen.values())):
        return {"consistent": False, "arms": seen,
                "why": "the arms loaded different (or no) BLAS libraries"}
    build = blas_threads.blas_build()
    shipped = {str(r.get("name")) for r in build["libs"]}
    libs = {row[3] for row in next(iter(seen.values()))}
    if shipped and not libs <= shipped:
        return {"consistent": False, "arms": seen, "shipped": sorted(shipped),
                "why": f"loaded {sorted(libs)} is not a library numpy's RECORD ships"}
    return {"consistent": True, "arms": seen, "build_digest": build["digest"],
            "why": f"every arm loaded {sorted(libs)}"}


def rebuild_coverage(arms: Mapping[str, Mapping[str, Any] | None],
                     plan: list[Mapping[str, Any]]) -> dict[str, Any]:
    """What the pre-warm rebuild actually covered. A requested cell that built no series in
    every arm is LOST coverage, counted and named, never silently skipped."""
    picks = [r for r in plan if "key" in r]
    present = {str(r["stratum_in_input"]): int(r.get("specs") or 0) for r in plan
               if "stratum_in_input" in r}
    by: dict[str, dict[str, Any]] = {}
    lost: list[dict[str, Any]] = []
    rebuilt = 0
    for r in picks:
        row = by.setdefault(str(r["stratum"]), {"requested": 0, "rebuilt": 0, "lost": 0,
                                                "families": set()})
        row["requested"] += 1
        got = [((a or {}).get("rebuilt") or {}).get(r["key"]) or {} for a in arms.values()
               if a is not None]
        if got and all(g.get("ds1_sha256") for g in got):
            row["rebuilt"] += 1
            row["families"].add(r["family"])
            rebuilt += 1
        else:
            row["lost"] += 1
            lost.append({"family": r["family"], "stratum": r["stratum"],
                         "status": sorted({str(g.get("status")) for g in got})})
    for row in by.values():
        row["families"] = sorted(row["families"])
    return {"requested": len(picks), "rebuilt": rebuilt, "lost": len(lost),
            "lost_cells": lost[:100], "by_stratum": by, "strata_in_input": present,
            "strata_unrebuilt": sorted(s for s, row in by.items() if row["rebuilt"] == 0),
            "strata_absent_from_input": sorted(s for s in STRATA if not present.get(s))}


# ===================================================================================== driver
def _child_env(single: bool) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in THREAD_VARS}
    if single:
        env.update(dict.fromkeys(THREAD_VARS, "1"))
    env["PYTHONHASHSEED"] = "0"            # same set/dict iteration in every arm
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run_child(role: str, job: dict[str, Any], scratch: Path, *, single: bool,
               timeout_s: float) -> tuple[dict[str, Any] | None, str | None, float]:
    """Run one child (`prepare` or an arm) and return (output, failure, wall seconds)."""
    job_path = scratch / f"job_{role}.json"
    out_path = scratch / f"out_{role}.json"
    job = {**job, "out": str(out_path)}
    job_path.write_text(json.dumps(job), encoding="utf-8")
    t0 = time.perf_counter()
    try:
        cp = subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()),
                             "--_child", str(job_path)], cwd=str(DESK),
                            env=_child_env(single), capture_output=True, timeout=timeout_s,
                            check=False)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout_s:.0f}s", time.perf_counter() - t0
    wall = time.perf_counter() - t0
    (scratch / f"stderr_{role}.log").write_bytes(cp.stderr or b"")
    if cp.returncode != 0 or not out_path.exists():
        tail = (cp.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-3:]
        return None, f"exit {cp.returncode}: {' | '.join(tail)[:400]}", wall
    try:
        return json.loads(out_path.read_text("utf-8")), None, wall
    except ValueError as exc:
        return None, f"unreadable output ({exc})", wall


def _child_main(job_path: str) -> int:
    job = json.loads(Path(job_path).read_text("utf-8"))
    scratch = Path(job["scratch"])
    sys.dont_write_bytecode = True
    install_write_guard([ROOT, *[Path(p) for p in job.get("protected", [])]], [scratch])
    fn = _prepare if job["role"] == "prepare" else _arm
    out = fn(job)
    out["write_guard_blocked"] = list(_GUARD["blocked"])
    Path(job["out"]).write_text(canon(out), encoding="utf-8")
    return 0


def _ratio(a: Any, b: Any) -> float | None:
    try:
        return round(float(a) / float(b), 4) if float(b) else None
    except (TypeError, ValueError):
        return None


def write_report(doc: dict[str, Any], out: Path, run_log: Path | None = None) -> Path:
    """Publish the report, then bind it to this run. Refuses (raises) rather than replace a
    read-only destination.

    THE BINDING (audit of 5d4d0279f: an unkeyed digest is tamper-evidence only, and a hand-built
    five-field report licensed the switch). The report carries this run's `run_id`; the run log
    gets one row naming that id and the report's digest, written only by this function after
    the report itself; and on a box that holds the release-signing key the digest is HMAC'd
    under it (`proof_hmac`). `blas_threads.proof_status` honours a report only when it is the
    latest row of the log and, where a key exists, its MAC verifies.
    """
    doc = _strict(doc)
    doc["content_sha256"] = blas_threads.content_sha256(doc)
    mac = blas_threads.proof_hmac(doc["content_sha256"])
    if mac:
        doc["proof_hmac"] = mac
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not (os.stat(out).st_mode & stat.S_IWRITE and os.access(out, os.W_OK)):
        raise PermissionError(f"{out} is read-only; refusing to replace it")
    tmp = out.with_name(f"{out.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=False, allow_nan=False), "utf-8")
    os.replace(tmp, out)
    log = Path(run_log or blas_threads.RUN_LOG)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"run_id": doc.get("run_id"), "content_sha256": doc["content_sha256"],
                             "verdict": doc.get("verdict"), "at": doc.get("generated_utc"),
                             "release_id": (doc.get("identity") or {}).get("release_id"),
                             "harness_version": doc.get("harness_version"),
                             "report": str(out), "keyed": bool(mac)}, sort_keys=True) + "\n")
    return out


#: An UNMEASURED proof (an arm timed out, too few cached cells) is retried after this long, not
#: every hour: the leg's cost stays bounded when the cause is structural.
RETRY_UNMEASURED_S = 6 * 3600


def lapsed(report: Path | None = None, *, now: datetime | None = None) -> tuple[bool, str]:
    """Must the hourly leg measure again? (lapsed, why).

    A report that is CURRENT for this process -- this schema and harness, this release, cores,
    numpy, Python, BLAS build and CPU, younger than the proof's age limit, still the latest run
    -- is a measurement, whatever it says: a DIFFERS on this release is not re-run every hour.
    An UNMEASURED is retried after RETRY_UNMEASURED_S.
    """
    path = Path(report or REPORT)
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return True, f"{path.name} absent or unreadable"
    if not isinstance(doc, dict):
        return True, f"{path.name} is not a mapping"
    if doc.get("schema") != SCHEMA or doc.get("harness_version") != blas_threads.HARNESS_VERSION:
        return True, (f"{path.name} is {doc.get('schema')}/{doc.get('harness_version')}, this "
                      f"harness writes {SCHEMA}/{blas_threads.HARNESS_VERSION}")
    proved, here = doc.get("identity") or {}, blas_threads.identity()
    moved = [k for k in blas_threads.IDENTITY_KEYS if proved.get(k) != here.get(k)]
    if moved:
        return True, f"identity moved since the last run: {moved}"
    run = blas_threads._last_run()
    if not run or run.get("run_id") != doc.get("run_id"):
        return True, "the report is not the latest harness run"
    at = blas_threads._parse(doc.get("generated_utc"))
    age = ((now or datetime.now(UTC)) - at).total_seconds() if at else float("inf")
    if age > blas_threads.MAX_PROOF_AGE_S - 86400:
        return True, f"{age / 86400:.1f} days old; re-measured a day before the proof lapses"
    if doc.get("verdict") == UNMEASURED and age > RETRY_UNMEASURED_S:
        return True, f"UNMEASURED {age / 3600:.1f} h ago; retried every {RETRY_UNMEASURED_S}s"
    return False, f"current: {doc.get('verdict')} on release {here['release_id']}, {age:.0f}s old"


def run(*, input_path: Path | None, out: Path, sample: int = DEFAULT_SAMPLE,
        rebuild: int = DEFAULT_REBUILD, control: bool = True, meta: Path | None = None,
        scratch: Path | None = None, keep_scratch: bool = False,
        arm_timeout_s: float = DEFAULT_ARM_TIMEOUT_S,
        run_log: Path | None = None) -> dict[str, Any]:
    """Prepare, judge in each arm, compare, publish. Returns the published report."""
    started = _now_iso()
    own_scratch = scratch is None
    scratch = Path(tempfile.mkdtemp(prefix=f"blas_diff_{os.getpid()}_")) if own_scratch \
        else Path(scratch)
    for forbidden in (DESK / "data", DESK / "reports"):
        if _under(_norm(scratch) or "", _norm(forbidden) or "\0"):
            raise ValueError(f"scratch {scratch} is inside {forbidden}; use a temp directory")
    scratch.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "schema": SCHEMA, "harness_version": blas_threads.HARNESS_VERSION,
        "run_id": uuid.uuid4().hex, "generated_utc": started,
        "identity": blas_threads.identity(),
        "blas_build": blas_threads.blas_build(),
        "evidence_floor": {"min_sample": blas_threads.MIN_SAMPLE,
                           "min_rebuilt": blas_threads.MIN_REBUILT,
                           "required_arms": list(blas_threads.REQUIRED_ARMS)},
        "release": _release_summary(), "host": platform.node(),
        "platform": platform.platform(), "executable": sys.executable,
        "thread_vars": list(THREAD_VARS),
        "params": {"sample": sample, "rebuild": rebuild, "control": control,
                   "arm_timeout_s": arm_timeout_s},
        "frozen_calls": [f"{m}.{a}" for m, a in FROZEN_CALLS],
        "scratch": str(scratch) if keep_scratch else "removed after the run",
        "writes": ("this report and one row of the run log; scratch in a temp directory, "
                   "removed afterwards; every child refuses writes, sqlite opens, utime and "
                   "subprocesses under the repository (audit-hook guard)"),
    }
    try:
        if input_path is None or not Path(input_path).exists():
            doc.update(verdict=UNMEASURED, why=(f"no recorded sweep input on disk "
                                                f"({input_path or DEFAULT_PLAN})"),
                       differences=[], n_differences=0)
            return _finish(doc, out, run_log)
        base = {"scratch": str(scratch), "input": str(input_path), "sample": int(sample),
                "rebuild": int(rebuild), "meta": str(meta) if meta else None}
        prep, fail, prep_wall = _run_child("prepare", {**base, "role": "prepare"}, scratch,
                                           single=False, timeout_s=arm_timeout_s)
        if prep is None:
            doc.update(verdict=UNMEASURED, why=f"prepare failed: {fail}", differences=[],
                       n_differences=0)
            return _finish(doc, out, run_log)
        doc["input"] = {k: v for k, v in prep.items() if k not in ("cell_ids", "cells_pickle")}
        doc["input"]["prepare_wall_s"] = round(prep_wall, 3)
        doc["input"]["cell_ids_sha256"] = hashlib.sha256(
            canon(prep.get("cell_ids")).encode()).hexdigest()
        if int(prep.get("sampled_cells") or 0) < 2:
            doc.update(verdict=UNMEASURED, why=(f"only {prep.get('sampled_cells')} cached cell(s)"
                                                " found in the recorded sweep; the census needs "
                                                "two"), differences=[], n_differences=0)
            return _finish(doc, out, run_log)
        plan = [("default", False, True), ("single", True, False)]
        if control:
            plan.append(("control", False, False))
        arms: dict[str, dict[str, Any] | None] = {}
        failures: dict[str, str] = {}
        timing: dict[str, Any] = {}
        for name, single, record in plan:
            got, fail, wall = _run_child(
                name, {**base, "role": "arm", "arm": name, "record": record,
                       "cells_pickle": prep["cells_pickle"]}, scratch, single=single,
                timeout_s=arm_timeout_s)
            arms[name] = got
            if got is None:
                failures[name] = str(fail)
                continue
            timing[name] = {**got["timing"], "process_wall_s": round(wall, 3)}
        decided = decide_verdict(arms, failures)
        doc.update(decided)
        doc["rebuild_coverage"] = rebuild_coverage(arms, list(prep.get("rebuild_plan") or []))
        short = blas_threads.evidence_floor(doc)
        doc["evidence_floor"]["shortfalls"] = short
        doc["evidence_floor"]["clears"] = not short
        doc["timing"] = timing
        if "default" in timing and "single" in timing:
            doc["timing"]["single_over_default"] = {
                "judge_wall": _ratio(timing["single"]["judge_wall_s"],
                                     timing["default"]["judge_wall_s"]),
                "judge_cpu": _ratio(timing["single"]["judge_cpu_s"],
                                    timing["default"]["judge_cpu_s"])}
        doc["arms"] = {name: _arm_summary(a) for name, a in arms.items() if a is not None}
        doc["probe"] = {name: a.get("probe") for name, a in arms.items() if a is not None}
        doc["eigvals_max_abs_diff"] = _eig_diff(scratch, arms)
        doc["key_quantities"] = {name: {k: v for k, v in (a.get("derived") or {}).items()
                                        if k != "cell_dsr"}
                                 for name, a in arms.items() if a is not None}
        blocked = {name: a.get("write_guard_blocked") for name, a in arms.items()
                   if a is not None and a.get("write_guard_blocked")}
        if prep.get("write_guard_blocked"):
            blocked["prepare"] = prep["write_guard_blocked"]
        doc["write_guard_blocked"] = blocked
        return _finish(doc, out, run_log)
    finally:
        if own_scratch and not keep_scratch:
            shutil.rmtree(scratch, ignore_errors=True)


def _arm_summary(a: Mapping[str, Any]) -> dict[str, Any]:
    return {"threads": a.get("threads"), "n_cells": a.get("n_cells"),
            "n_judged": a.get("n_judged"), "census_calls": a.get("census_calls"),
            "frozen": a.get("frozen"), "frozen_stats": a.get("frozen_stats"),
            "verdicts_sha256": hashlib.sha256(canon(
                (a.get("result") or {}).get("verdicts")).encode()).hexdigest(),
            "result_sha256": hashlib.sha256(canon(a.get("result")).encode()).hexdigest()}


def _eig_diff(scratch: Path, arms: Mapping[str, Any]) -> dict[str, Any] | None:
    """Largest absolute eigenvalue difference of each arm against `default`, for localisation."""
    try:
        import numpy as np
    except ImportError:
        return None
    base = scratch / "eigvals_default.npy"
    if not base.exists():
        return None
    ref = np.load(base)
    out: dict[str, Any] = {}
    for name in arms:
        f = scratch / f"eigvals_{name}.npy"
        if name == "default" or not f.exists():
            continue
        other = np.load(f)
        out[name] = (float(np.max(np.abs(other - ref))) if other.shape == ref.shape
                     else f"shape {other.shape} != {ref.shape}")
    return out


def _release_summary() -> dict[str, Any]:
    try:
        d = json.loads(blas_threads.RELEASE.read_text("utf-8"))
        return {k: d.get(k) for k in ("release_id", "live_sha", "code_sha", "sealed_at")}
    except (OSError, ValueError, AttributeError):
        return {"release_id": "unreleased"}


def _finish(doc: dict[str, Any], out: Path, run_log: Path | None = None) -> dict[str, Any]:
    doc["finished_utc"] = _now_iso()
    write_report(doc, out, run_log)
    return json.loads(out.read_text("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path, default=None,
                    help="recorded sweep input: shard plan.pkl (default), sweep report JSON, "
                         "cell-list JSON, or a prepared cells pickle")
    ap.add_argument("--meta", type=Path, default=None,
                    help="universe.json when the input carries no meta")
    ap.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    ap.add_argument("--rebuild", type=int, default=DEFAULT_REBUILD,
                    help="cells also rebuilt through the pre-warm worker (0 disables)")
    ap.add_argument("--no-control", dest="control", action="store_false",
                    help="skip the second default-thread (noise) arm; a proof without it never "
                         "licenses the switch")
    ap.add_argument("--if-lapsed", action="store_true",
                    help="the hourly leg: measure only when the proof is missing or lapsed")
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--scratch", type=Path, default=None)
    ap.add_argument("--keep-scratch", action="store_true")
    ap.add_argument("--arm-timeout-s", type=float, default=DEFAULT_ARM_TIMEOUT_S)
    ap.add_argument("--_child", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a._child:
        return _child_main(a._child)
    if a.if_lapsed:
        need, why = lapsed(a.out)
        if not need:
            print(f"BLAS_DIFFERENTIAL: not re-measured -- {why}")
            return 0
        print(f"BLAS_DIFFERENTIAL: re-measuring -- {why}")
    try:
        rep = run(input_path=a.input or default_input(), out=a.out, sample=a.sample,
                  rebuild=a.rebuild, control=a.control, meta=a.meta, scratch=a.scratch,
                  keep_scratch=a.keep_scratch, arm_timeout_s=a.arm_timeout_s)
    except Exception as exc:
        print(f"blas_thread_differential: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    print(f"BLAS_DIFFERENTIAL: {rep.get('verdict')} -- {rep.get('why')}")
    for name, t in (rep.get("timing") or {}).items():
        if isinstance(t, dict) and "per_cell_wall_ms" in t:
            print(f"  {name}: {t['per_cell_wall_ms']} ms wall / {t['per_cell_cpu_ms']} ms CPU "
                  f"per cell")
    print(f"  report: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
