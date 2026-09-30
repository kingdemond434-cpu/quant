"""The MT5-Gauntlet launcher: the sealed judge's sweep, sharded N ways when the judge supports it.

WHY. One sweep holds the exclusive `certification_lane` and, after the pre-warm pool has built
the cold cells, rules the whole docket on ONE core: loading every cached series pair, CPCV,
walk-forward, the swap price, cell after cell. The trading box has 18 cores. `external_gauntlet`
(sealed) grows a sharded sweep in `sealed_patches/external_gauntlet_sharded_sweep.patch`:
`run_sharded(n, dispatch)` plans the docket once, hands the plan to `dispatch`, verifies that
every planned cell came back from exactly one shard, and then computes every program-level
number -- the trial census, the deflated-Sharpe charge, PBO, SPA -- ONCE, on the union matrix,
before writing anything. This file is the unsealed half: it decides N, runs the shards as
subprocesses, and records what happened.

IT NEVER CHANGES A VERDICT AND IT NEVER BLOCKS THE JUDGE.
  * The sealed file without the patch has no `SHARD_PROTOCOL`: this launcher then runs
    `external_gauntlet._cli_main()` exactly as `RunGauntlet.cmd` always did (feature-detected,
    not version-guessed).
  * N resolves to 1 (small box, or `GAUNTLET_SHARDS=1`), or the call is a reproduction
    (`--only`): the same unsharded `_cli_main()`.
  * A sharded sweep that fails (a shard died, the merge refused) publishes nothing -- the
    sealed merge fails closed -- and this launcher then runs the unsharded sweep in the same slot,
    so a broken shard costs latency, never the hour's verdicts.

    python scripts/external_gauntlet_sharded.py              # the MT5-Gauntlet entry point
    python scripts/external_gauntlet_sharded.py --shards 6   # force N
    python scripts/external_gauntlet_sharded.py --plan       # print the decision, run nothing
    python scripts/external_gauntlet_sharded.py --worker DIR K   # one shard (the launcher's)

THE NAME CARRIES `external_gauntlet` ON PURPOSE. `judging_throughput._is_judge` and
`stall_watch.ps1` find the judge by that substring in a process's command line; a launcher (or a
shard) named anything else would read as foreign load to the first and be invisible to the second.

ARTIFACT: `desks/mt5/reports/SHARDED_SWEEP.json` -- mode (sharded / unsharded), why, N, the
per-shard environment, wall-clock, return code, and the sealed merge's own `sharding` block
(per-shard seconds and cells). Read by `research/judging_burndown.py` into JUDGING_BURNDOWN.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DESK = HERE.parent
REPORT = DESK / "reports" / "SHARDED_SWEEP.json"

#: Memory one shard is budgeted, in MB. The sealed sweep's measured working set is ~1,620 MB for
#: the WHOLE docket (see external_gauntlet.DECLARED_NEED_MB's notes); a shard holds 1/N of the
#: series plus its own imports, so this is headroom, not a measurement. Override to tune.
PER_SHARD_MB = float(os.environ.get("GAUNTLET_PER_SHARD_MB", "1600"))
#: Share of free physical memory the shards together may be budgeted.
SHARD_MEMORY_SHARE = float(os.environ.get("GAUNTLET_SHARD_MEMORY_SHARE", "0.5"))
#: Ceiling on N. The merge (census, PBO, SPA, the writes) stays serial by design, so past a
#: handful of shards the per-cell phase is no longer what the sweep's length is made of.
MAX_SHARDS = int(os.environ.get("GAUNTLET_SHARDS_MAX", "8"))
#: A shard that has not finished this long after the build budget is killed (the merge then
#: refuses and the unsharded sweep runs).
SHARD_TIMEOUT_EXTRA_S = float(os.environ.get("GAUNTLET_SHARD_TIMEOUT_EXTRA_S", "1800"))


def _import_judge() -> Any:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import external_gauntlet as eg
    return eg


def supports_sharding(eg: Any) -> bool:
    """Feature detection: the patched judge exposes the protocol and its three entry points."""
    return (int(getattr(eg, "SHARD_PROTOCOL", 0) or 0) >= 1
            and all(callable(getattr(eg, f, None))
                    for f in ("run_sharded", "shard_worker", "shard_of")))


def _free_mb() -> float | None:
    try:
        import psutil
        return float(psutil.virtual_memory().available) / 1048576.0
    except Exception:
        return None


def decide(eg: Any, requested: int | None = None) -> dict[str, Any]:
    """How many shards, and each one's pool and memory budget. Measured, never assumed."""
    total_workers = int(getattr(eg, "WORKERS", 1) or 1)
    free = _free_mb()
    env_n = os.environ.get("GAUNTLET_SHARDS")
    if requested is not None:
        n, basis = int(requested), "requested on the command line"
    elif env_n:
        n, basis = int(float(env_n)), "GAUNTLET_SHARDS"
    else:
        by_cores = max(1, total_workers // 2)
        by_mem = (int(SHARD_MEMORY_SHARE * free // PER_SHARD_MB) if free is not None else 1)
        n = max(1, min(by_cores, by_mem, MAX_SHARDS))
        basis = (f"auto: min(workers {total_workers}//2={by_cores}, "
                 f"{SHARD_MEMORY_SHARE:.0%} of {free if free is None else round(free)} MB free "
                 f"/ {PER_SHARD_MB:.0f} MB = {by_mem}, cap {MAX_SHARDS})")
    n = max(1, n)
    per_workers = max(1, total_workers // n)
    return {"n_shards": n, "basis": basis, "free_mb": None if free is None else round(free),
            "workers_total": total_workers, "workers_per_shard": per_workers,
            "per_shard_budget_mb": int(PER_SHARD_MB),
            "need_mb": int(float(getattr(eg, "MEMORY_BUDGET_MB", 1200)) + n * PER_SHARD_MB)}


def _shard_env(decision: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    env["GAUNTLET_WORKERS"] = str(decision["workers_per_shard"])
    env["GAUNTLET_MEMORY_BUDGET_MB"] = str(decision["per_shard_budget_mb"])
    env["PYTHONUNBUFFERED"] = "1"
    return env


def make_dispatch(decision: dict[str, Any], timeout_s: float):
    """`dispatch(shard_dir, n)`: one subprocess per shard, all at once; raise if any fails."""
    env = _shard_env(decision)

    def dispatch(shard_dir: Path, n: int) -> None:
        procs = []
        for k in range(n):
            log = open(Path(shard_dir) / f"shard_{k}.log", "w", encoding="utf-8")  # noqa: SIM115
            p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker",
                                  str(shard_dir), str(k)], stdout=log,
                                 stderr=subprocess.STDOUT, env=env, cwd=str(DESK))
            procs.append((k, p, log))
        deadline = time.time() + timeout_s
        failed: list[str] = []
        for k, p, log in procs:
            try:
                rc = p.wait(timeout=max(1.0, deadline - time.time()))
            except subprocess.TimeoutExpired:
                p.kill()
                rc = -9
            log.close()
            if rc != 0:
                failed.append(f"shard {k} rc={rc}")
        for k, _p, _log in procs:
            try:
                tail = (Path(shard_dir) / f"shard_{k}.log").read_text(
                    "utf-8", errors="replace").splitlines()[-3:]
                for line in tail:
                    print(f"  [shard {k}] {line}")
            except OSError:
                pass
        if failed:
            raise RuntimeError("; ".join(failed))

    return dispatch


def _write_report(doc: dict[str, Any]) -> None:
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(f".json.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, REPORT)
    except OSError as exc:
        print(f"SHARDED_SWEEP.json not written ({exc})")


def _merge_block(eg: Any) -> Any:
    """The sealed merge's own `sharding` block from the report it just wrote, or None."""
    try:
        doc = json.loads((eg.REPORTS / "universal_gates_external.json").read_text("utf-8"))
        return doc.get("sharding")
    except Exception:
        return None


def _unsharded(eg: Any, argv: list[str]) -> int:
    sys.argv = [str(Path(eg.__file__)), *argv]
    return int(eg._cli_main() or 0)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--worker"]:
        eg = _import_judge()
        eg.shard_worker(Path(argv[1]), int(argv[2]))
        return 0
    requested: int | None = None
    if "--shards" in argv:
        i = argv.index("--shards")
        requested = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    plan_only = "--plan" in argv
    argv = [a for a in argv if a != "--plan"]

    eg = _import_judge()
    started = datetime.now(tz=UTC)
    doc: dict[str, Any] = {"at": started.isoformat(timespec="seconds"),
                           "sealed_protocol": int(getattr(eg, "SHARD_PROTOCOL", 0) or 0)}
    why = None
    decision: dict[str, Any] | None = None
    if not supports_sharding(eg):
        why = "sealed judge has no SHARD_PROTOCOL (patch not applied): unsharded sweep"
    elif any(a.startswith("--only") for a in argv):
        why = "reproduction (--only) is never sharded"
    else:
        decision = decide(eg, requested)
        doc["decision"] = decision
        if decision["n_shards"] <= 1:
            why = f"N=1 ({decision['basis']}): unsharded sweep"
    if plan_only:
        doc.update(mode="plan", why=why or "sharded")
        print(json.dumps(doc, indent=1, default=str))
        return 0

    t0 = time.time()
    if why is None and decision is not None:
        timeout = float(getattr(eg, "FRESH_BUILD_BUDGET_SEC", 2700)) + SHARD_TIMEOUT_EXTRA_S
        try:
            rc = eg.run_sharded(decision["n_shards"], make_dispatch(decision, timeout),
                                need_mb=decision["need_mb"])
            doc.update(mode="sharded", rc=rc, wall_seconds=round(time.time() - t0, 1),
                       merge=_merge_block(eg),
                       why=("sharded sweep ran" if rc == 0 else
                            "DEFERRED: the certification lane was not granted"))
            _write_report(doc)
            return 0
        except Exception as exc:
            doc["sharded_failure"] = f"{type(exc).__name__}: {exc}"[:500]
            doc["sharded_wall_seconds"] = round(time.time() - t0, 1)
            why = ("sharded sweep FAILED CLOSED (nothing published); running the unsharded "
                   "sweep in the same slot")
            print(f"SHARDED SWEEP FAILED: {doc['sharded_failure']} -- {why}")
    t1 = time.time()
    doc.update(mode="unsharded", why=why)
    _write_report({**doc, "status": "RUNNING"})
    rc = _unsharded(eg, argv)
    doc.update(rc=rc, wall_seconds=round(time.time() - t1, 1))
    _write_report(doc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
