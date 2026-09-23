"""THE THREE PERMANENT MOAT SWARMS -- exploit, explore, resurrect, all three running at once.

THE PRINCIPAL, 2026-09-17 (ledger item M19): "generator-yield learning and worker reallocation:
Y_g = independent survivors / tests generated, delta n_eff,g, delta E[log W]_g per generator;
three permanent moat swarms (EXPLOIT deepens winners, EXPLORE mines unused data, RESURRECT
attacks the graveyard) with dedicated workers rebalanced by yield."

WHAT WAS THERE BEFORE. Eight internal exploitation engines, each a fine organ, each a leg of one
sequential hourly pass. A leg is a slot: it runs once an hour whatever it is worth, and the hour
decides how long it gets rather than the evidence. So the engine that has never produced an
independent survivor got the same seconds as the engine that produced nine, hour after hour, and
NOTHING IN THE DESK EVER MOVED A SECOND BETWEEN THEM. The `generator_yield` table has held the
number that should move them since the registry landed; no organ read it back.

THE THREE SWARMS, AND WHY EXACTLY THREE. They are the three ways a moat grows, and they fail
differently, which is the only reason to run them concurrently rather than in sequence:

    EXPLOIT     deepens what is ALREADY KNOWN TO WORK -- card_explosion (a live card's axes),
                alpha_recombination (pairs of survivors), forward_exploitation's WORKING half
                (what state makes a live clock pay) and descendants (children of the canon).
                Alone it rebuilds the leaderboard: three variants of one bet, n_eff flat.
    EXPLORE     mines the data and the relationships the desk OWNS AND HAS NEVER READ --
                unused_information (the archive nothing opens), shadow_discovery (the desk's own
                unexplained P&L), execution_alpha (the tape's own edge) and alpha_lineage (the
                abandoned branch). Alone it never compounds: every pass starts from nothing.
    RESURRECT   attacks what the desk ALREADY PAID FOR AND THREW AWAY -- graveyard_resurrection
                (a failure re-asked along the axis its fate names), forward_exploitation's
                FAILING half (a KILL is the most expensive measurement this desk makes and it
                was generating nothing) and discovery_compiler over BLOCKED/UNPROCESSED
                discoveries. Alone it has nothing new to work on.

Each swarm is a RESIDENT, not a leg: `python moat_swarms.py --swarm exploit` holds
`data/locks/moat_exploit.lock` and loops. Three residents, three locks, three sets of workers,
100% concurrency -- the keep-alive trigger that restarts a dead swarm is a no-op while one is
alive, exactly as `department_resident` does it, and the pass discipline is borrowed wholesale
from `hourly_cycle._producer`: a child under a hard timeout at BELOW_NORMAL priority, a
compute-ledger run opened and closed around every engine so `research_runs` sees it, a MISSING
script reported rather than run, and one engine's failure never taking the pass with it.

THE ALLOCATION RULE, WHICH IS THE POINT OF THE WHOLE FILE.

    share_g = FLOOR + (COLD if g has never been measured) + free x (Y_g + PRIOR) / sum(Y + PRIOR)

with Y_g = independent survivors / generated from `registry.generator_yields()`, FLOOR = 0.10 and
COLD = 0.05. A productive engine gets more seconds and a junk-producing one fewer, and NEITHER
EVER GETS ZERO. The floor is not timidity (GROWTH GOVERNANCE Rule 1): an engine starved to zero
can never produce the evidence that would un-starve it, so a zero share is a permanent retirement
dressed up as an allocation, and no measurement here says any of these eight is worth retiring.
The cold share is that same argument for a generator the table has never seen -- unmeasured is a
real answer (L1.28a) and must be allowed to become a measured one. What the floor COSTS the best
engine is published as `floor_cost_s`, so the rail is never free and never invisible.

delta_n_eff and delta_elogw are PUBLISHED PER GENERATOR and NOT fed into the weight: they are in
different units from a ratio and unmeasured for most generators today, and a weight that mixed
them would be a confident ordering of made-up numbers -- the failure `compute_ledger` names in
its own first paragraph. They are in the report so the pass that earns the right to use them can.

    python moat_swarms.py --swarm exploit                 # the resident, until stopped
    python moat_swarms.py --swarm explore --once          # one pass (tests, probes)
    python moat_swarms.py --swarm resurrect --dry-run     # the plan; run nothing, write nothing
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(REPO), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LOCKS = DESK / "data" / "locks"
LOGS = DESK / "logs"
OUT = DESK / "reports" / "MOAT_SWARMS.json"

#: Wall clock one pass hands out across its engines. Not a limit on the swarm -- the resident
#: restarts the moment a pass ends -- but the unit the yield rule divides.
PASS_BUDGET_S = float(os.environ.get("MOAT_PASS_BUDGET_S", "1800"))
#: Grace on top of an engine's own `--budget-s` before the child is stopped. An engine that
#: honours its budget never sees this; one that hangs on a terminal call does.
GRACE_S = float(os.environ.get("MOAT_GRACE_S", "120"))
#: What the discovery compiler gets at the tail of every pass, outside the yield allocation:
#: it is the JOIN, not a generator, and starving the join starves every generator at once.
COMPILER_BUDGET_S = float(os.environ.get("MOAT_COMPILER_BUDGET_S", "180"))
MIN_CYCLE_S = float(os.environ.get("MOAT_MIN_CYCLE_S", "600"))
PAUSE_S = float(os.environ.get("MOAT_PAUSE_S", "30"))
MIN_FREE_MB = float(os.environ.get("MOAT_MIN_FREE_MB", "4096"))
MAX_MEM_WAIT_S = float(os.environ.get("MOAT_MAX_MEM_WAIT_S", "1800"))
RECYCLE_PASSES = int(os.environ.get("MOAT_RECYCLE_PASSES", "48"))
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

#: The share every engine keeps however badly it has scored, and the extra an engine the yield
#: table has never seen gets so that unmeasured can become measured.
FLOOR_SHARE = 0.10
COLD_SHARE = 0.05
#: An unmeasured yield is this, never 1.0 and never 0.0 -- the registry's own candidate prior.
PRIOR = 0.5

RULE = ("three swarms run concurrently with dedicated workers; the moat learns which kind of "
        "mining works and moves seconds toward it, never below a floor")

#: swarm -> its engines, in the order a pass runs them. `yield_key` is the generator name the
#: engine writes into `generator_yield` (an engine that keys sub-generators `key:variant` is
#: matched by prefix); `focus` says which half of a two-sided engine this swarm is here for.
SWARMS: dict[str, dict[str, Any]] = {
    "exploit": {
        "what": "deepen what is already known to work",
        "engines": (
            {"engine": "card_explosion", "script": "research/moat_card_explosion.py",
             "yield_key": "card_explosion", "focus": "every axis of every live card"},
            {"engine": "alpha_recombination", "script": "research/alpha_recombination.py",
             "yield_key": "alpha_recombination", "focus": "pairs and triples of survivors"},
            {"engine": "forward_exploitation", "script": "research/forward_exploitation.py",
             "yield_key": "forward_exploitation",
             "focus": "the WORKING half: what state makes a live clock pay"},
            {"engine": "descendants", "script": "research/descendants.py",
             "yield_key": "descendants", "focus": "children of the canon"},
        ),
    },
    "explore": {
        "what": "mine the data and the relationships the desk owns and has never read",
        "engines": (
            {"engine": "unused_information", "script": "research/unused_information.py",
             "yield_key": "unused_information", "focus": "the archive nothing opens"},
            {"engine": "shadow_discovery", "script": "research/shadow_discovery.py",
             "yield_key": "shadow_discovery", "focus": "the desk's own unexplained P&L"},
            {"engine": "execution_alpha", "script": "research/execution_alpha_miner.py",
             "yield_key": "execution_alpha_miner", "focus": "the execution tape's own edge"},
            {"engine": "alpha_lineage", "script": "research/alpha_lineage_search.py",
             "yield_key": "lineage", "focus": "the branch that was abandoned, not refuted"},
        ),
    },
    "resurrect": {
        "what": "attack what the desk already paid for and threw away",
        "engines": (
            {"engine": "graveyard_resurrection", "script": "research/graveyard_resurrection.py",
             "yield_key": "graveyard_resurrection",
             "focus": "a failure re-asked along the axis its recorded fate names"},
            {"engine": "forward_exploitation", "script": "research/forward_exploitation.py",
             "yield_key": "forward_exploitation",
             "focus": "the FAILING half: what changed under a killed clock"},
        ),
    },
}

#: The manifest rows the session that owns the box task table copies verbatim. A resident needs
#: a KEEP-ALIVE, not a schedule: at startup so a reboot brings the swarm back, then every ten
#: minutes so a resident that died or recycled is replaced inside ten minutes. Starting one while
#: another holds the lock is a no-op that exits 0, which is what makes a keep-alive safe.
#: Literal task names, one per swarm: the box-task fence reads names as literals.
TASK_NAMES: dict[str, str] = {"exploit": "MT5-Moat-Exploit", "explore": "MT5-Moat-Explore",
                              "resurrect": "MT5-Moat-Resurrect"}
BOX_TASKS: tuple[dict[str, str], ...] = tuple(
    {"name": TASK_NAMES[s],
     "trigger": "at startup + every 10 minutes (keep-alive of a 24/7 resident)",
     "runs": "desks/mt5/research/moat_swarms.py",
     "arguments": f"--swarm {s}",
     "working_directory": "C:\\opt\\quant\\desks\\mt5",
     "run_as": "SYSTEM",
     "why": SWARMS[s]["what"]}
    for s in SWARMS)

try:                                            # the resident next door already measures memory
    from department_resident import free_phys_mb as _free_phys_mb
    _MEM_WHY = ""
except Exception as exc:                        # pragma: no cover - the sibling is always there
    _free_phys_mb = None                        # type: ignore[assignment]
    _MEM_WHY = f"department_resident unavailable: {type(exc).__name__}: {exc}"


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def free_phys_mb() -> float | None:
    """Free physical memory, or None where it cannot be read -- never a guess, never a zero."""
    return _free_phys_mb() if _free_phys_mb is not None else None


def log(swarm: str, msg: str) -> None:
    line = f"{now()} moat[{swarm}]: {msg}"
    print(line, flush=True)
    with contextlib.suppress(OSError):
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / "moat_swarms.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def claim_singleton(swarm: str):
    """Hold data/locks/moat_<swarm>.lock for this process's life; None when another holds it."""
    LOCKS.mkdir(parents=True, exist_ok=True)
    path = LOCKS / f"moat_{swarm}.lock"
    try:
        fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115 -- held for the process lifetime
    except OSError:
        return None
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    with contextlib.suppress(OSError):
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()} {now()}\n")
        fh.flush()
    return fh


# --------------------------------------------------------------------------- yields and shares
def generator_yields() -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    """`registry.generator_yields()` keyed by generator, plus what could not be read.

    A generator that keys sub-generators (`graveyard_resurrection:cost`, `lineage:abandoned`)
    is folded into its stem here: the swarm allocates to an ENGINE, and the engine owns every
    sub-generator it writes. Counts add; delta_n_eff and delta_elogw add, because both are
    already differences and the engine's contribution is the sum of its parts'.
    """
    try:
        from libs.moat import registry as reg
        rows = reg.generator_yields()
    except Exception as exc:
        return {}, [{"what": "generator_yield", "why": f"{type(exc).__name__}: {exc}"}]
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("generator") or "")
        if not key:
            continue
        out[key] = {"generated": int(row.get("generated") or 0),
                    "independent_survivors": int(row.get("independent_survivors") or 0),
                    "survivors": int(row.get("survivors") or 0),
                    "judged": int(row.get("judged") or 0),
                    "compute_s": float(row.get("compute_s") or 0.0),
                    "delta_n_eff": float(row.get("delta_n_eff") or 0.0),
                    "delta_elogw": float(row.get("delta_elogw") or 0.0),
                    "yield": row.get("yield")}
    return out, []


def yield_of(key: str, table: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """One engine's folded yield row: its own key plus every `key:variant` it writes."""
    parts = [v for k, v in table.items() if k == key or k.startswith(f"{key}:")]
    gen = sum(int(p["generated"]) for p in parts)
    ind = sum(int(p["independent_survivors"]) for p in parts)
    row = {"generator": key, "rows_folded": len(parts), "generated": gen,
           "independent_survivors": ind,
           "survivors": sum(int(p["survivors"]) for p in parts),
           "judged": sum(int(p["judged"]) for p in parts),
           "compute_s": round(sum(float(p["compute_s"]) for p in parts), 2),
           "delta_n_eff": round(sum(float(p["delta_n_eff"]) for p in parts), 6),
           "delta_elogw": round(sum(float(p["delta_elogw"]) for p in parts), 6)}
    # UNMEASURED IS NOT ZERO. A generator that has generated nothing has no ratio, and scoring it
    # as 0.0 would be a verdict the evidence does not carry (L1.28a).
    row["yield"] = None if gen == 0 else round(ind / gen, 6)
    return row


def allocate(engines: list[dict[str, Any]], table: dict[str, dict[str, Any]], budget_s: float,
             *, floor: float = FLOOR_SHARE, cold: float = COLD_SHARE,
             prior: float = PRIOR) -> tuple[list[dict[str, Any]], str, float]:
    """Split `budget_s` across the swarm's engines by measured yield, with a floor and a cold
    share. Returns (rows, rule_text, floor_cost_s).

    `floor_cost_s` is the MISSED-GROWTH LEDGER LINE the growth governance demands of every rail
    here: the seconds the best-yielding engine gave up so that every sibling kept its floor. A
    rail whose cost is not published is a rail nobody can argue with.
    """
    n = len(engines)
    if n == 0:
        return [], "no engine in this swarm", 0.0
    rows = [{**e, **{"yields": yield_of(str(e["yield_key"]), table)}} for e in engines]
    measured = np.array([r["yields"]["yield"] is not None for r in rows], dtype=bool)
    y = np.array([float(r["yields"]["yield"] or 0.0) for r in rows], dtype=float)
    w = y + float(prior)
    n_cold = int((~measured).sum())
    base = floor * n + cold * n_cold
    free = max(0.0, 1.0 - base)
    if base > 1.0 or not np.isfinite(w).all() or w.sum() <= 0.0:
        # More engines than the floor can seat, or a yield table that says nothing: EVEN is the
        # honest split, and the report says so rather than pretending a ranking existed.
        share = np.full(n, 1.0 / n, dtype=float)
        rule = (f"{n} engine(s) cannot all keep a {floor:.0%} floor plus the cold share, or no "
                f"weight is finite: the budget is split EVENLY and no yield was used")
    else:
        share = floor + cold * (~measured).astype(float) + free * (w / w.sum())
        rule = (f"share_g = {floor:.0%} floor + {cold:.0%} when g is unmeasured + "
                f"{free:.0%} x (Y_g + {prior}) / sum(Y + {prior}); Y_g = independent survivors / "
                f"generated from the registry's generator_yield table. Never zero: an engine "
                f"starved to zero can never earn its way back, which is a retirement, not an "
                f"allocation")
    seconds = _largest_remainder(share, float(budget_s))
    top = int(np.argmax(w)) if w.size else 0
    floor_cost = round(max(0.0, float(budget_s) * float(w[top] / w.sum() - share[top])), 1) \
        if w.sum() > 0 else 0.0
    for r, s, sh, m in zip(rows, seconds, share, measured, strict=True):
        r["budget_s"] = float(s)
        r["share"] = round(float(sh), 4)
        r["basis"] = "measured" if bool(m) else "cold"
    return rows, rule, floor_cost


def _largest_remainder(share: np.ndarray, budget_s: float) -> list[float]:
    """Whole seconds that sum to the budget: floors first, then the largest remainders."""
    exact = np.asarray(share, dtype=float) * float(budget_s)
    base = np.floor(exact).astype(np.int64)
    left = round(float(budget_s)) - int(base.sum())
    if left > 0:
        for i in np.argsort(-(exact - base))[:left]:
            base[int(i)] += 1
    return [float(max(1, int(v))) for v in base]


# --------------------------------------------------------------------------- running one engine
def resolve(script: str) -> Path | None:
    """The engine's file under the desk or the repo; None when it is under neither.

    ABSENCE IS NEVER A PASS (L1.28a). An engine this tree does not carry is reported MISSING with
    both roots named -- never run, never silently counted as a clean zero.
    """
    for root in (DESK, REPO):
        target = root / script
        if target.exists():
            return target
    return None


def _spawn(cmd: list[str], cwd: Path, timeout_s: float) -> dict[str, Any]:
    """THE ONE PLACE A CHILD IS STARTED, so a test can stand in for the box.

    BELOW_NORMAL on Windows, exactly as `department_resident` runs its pass: the gateway resident
    and the terminal always win the CPU, because a mining pass that starves the book has cost
    more than it can ever find.
    """
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = BELOW_NORMAL_PRIORITY_CLASS
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd),
                           timeout=timeout_s, check=False, **kwargs)
        return {"rc": r.returncode, "seconds": round(time.monotonic() - t0, 1),
                "status": "ok" if r.returncode == 0 else "exit",
                "tail": (r.stdout or r.stderr or "")[-300:]}
    except subprocess.TimeoutExpired:
        return {"rc": None, "seconds": round(time.monotonic() - t0, 1), "status": "timeout",
                "tail": f"stopped at {timeout_s:.0f}s; its partial work is whatever it wrote"}
    except OSError as exc:
        return {"rc": None, "seconds": round(time.monotonic() - t0, 1),
                "status": f"failed_to_start: {type(exc).__name__}", "tail": str(exc)[:300]}


def run_engine(swarm: str, row: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """One engine as a costed child. Never raises: a swarm of four must not lose three."""
    out = {"engine": str(row["engine"]), "script": str(row["script"]),
           "focus": str(row.get("focus") or ""), "budget_s": float(row.get("budget_s") or 0.0),
           "share": row.get("share"), "basis": row.get("basis"),
           "yields": row.get("yields") or {}, "seconds": 0.0, "rc": None, "status": "UNKNOWN"}
    target = resolve(str(row["script"]))
    if target is None:
        out["status"] = "MISSING"
        out["why"] = f"{row['script']} exists under neither {DESK} nor {REPO}"
        return out
    if dry_run:
        out["status"] = "PLANNED"
        out["why"] = "--dry-run: the plan only; no child started, nothing written"
        return out
    root = DESK if target.is_relative_to(DESK) else REPO
    budget = max(15.0, float(row.get("budget_s") or 0.0))
    cmd = [sys.executable, "-u", "-W", "ignore", str(target), "--budget-s", str(int(budget))]
    with _costed(f"moat_{swarm}:{out['engine']}", swarm=swarm, engine=out["engine"]) as run:
        res = _spawn(cmd, root, budget + GRACE_S)
        out.update({"rc": res["rc"], "seconds": res["seconds"], "status": res["status"],
                    "tail": res.get("tail", "")})
        run["outcome"] = ("ok" if res["status"] == "ok"
                          else (f"exit_code={res['rc']}" if res["status"] == "exit"
                                else str(res["status"]).upper()))
        run["outputs"] = [target]
    return out


class _costed:
    """`open_run` / `close_run` around one engine, so `research_runs` sees every child.

    NEVER FAILS THE ENGINE, for the same reason `hourly_cycle._costed` does not: a ledger that
    can take down the work it measures would be removed within a week, correctly. An absent
    `libs` means the engine runs uncosted, which is the state it was in before -- and it is
    PRINTED, because a denominator that fails silently is a scaling law nobody can draw.
    """

    def __init__(self, name: str, **meta: Any) -> None:
        self.name, self.meta, self.run, self.close = name, meta, None, None
        self.result: dict[str, Any] = {}

    def __enter__(self) -> dict[str, Any]:
        try:
            from libs.ops.compute_ledger import close_run, open_run
            self.run, self.close = open_run(self.name, kind="moat_swarm", **self.meta), close_run
        except Exception as exc:
            print(f"{self.name} compute ledger UNAVAILABLE: {type(exc).__name__}: {exc}",
                  flush=True)
        return self.result

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self.close is not None and self.run is not None:
            outcome = (f"{exc_type.__name__}: {exc}"[:200] if exc_type is not None
                       else str(self.result.get("outcome") or "ok"))
            with contextlib.suppress(Exception):
                self.close(self.run, outcome=outcome, outputs=self.result.get("outputs") or [])
        return False


# --------------------------------------------------------------------------- one pass
def run_pass(swarm: str, pass_no: int, *, budget_s: float = PASS_BUDGET_S,
             dry_run: bool = False) -> dict[str, Any]:
    """One swarm pass: read the yields, split the budget, run the engines, then the compiler."""
    t0 = time.monotonic()
    spec = SWARMS[swarm]
    table, unmeasured = generator_yields()
    if _MEM_WHY:
        unmeasured.append({"what": "memory guard", "why": _MEM_WHY})
    rows, rule, floor_cost = allocate(list(spec["engines"]), table, budget_s)
    engines = [run_engine(swarm, r, dry_run=dry_run) for r in rows]
    doc: dict[str, Any] = {
        "pass": int(pass_no), "at": now(), "what": str(spec["what"]),
        "engines": engines,
        "yields": {str(r["engine"]): r["yields"] for r in rows},
        "allocation_rule": rule, "pass_budget_s": float(budget_s),
        "floor_cost_s": floor_cost,
        "floor_cost_note": ("seconds the best-yielding engine gave up so every sibling kept its "
                            "floor -- the missed-growth ledger line for this rail"),
        "n_generators_measured": sum(1 for r in rows if r["basis"] == "measured"),
        "seconds": round(time.monotonic() - t0, 1),
    }
    doc["compiler"] = run_compiler(swarm, dry_run=dry_run)
    doc["seconds"] = round(time.monotonic() - t0, 1)
    if not dry_run:
        _pay_compute(engines)
    doc["unmeasured"] = unmeasured
    return doc


def run_compiler(swarm: str, *, dry_run: bool = False) -> dict[str, Any]:
    """`discovery_compiler` at the tail of every pass: what the engines found becomes cells.

    OUTSIDE THE YIELD ALLOCATION ON PURPOSE. The compiler is the JOIN, not a generator -- it owns
    no yield of its own and starving it starves every generator at once, because a discovery
    nobody compiles is a discovery nobody can be paid for. It runs LAST so the pass's own
    donations are in the registry when it reads.
    """
    row = {"engine": "discovery_compiler", "script": "research/discovery_compiler.py",
           "focus": ("BLOCKED and UNPROCESSED discoveries: no finding dies of neglect"
                     if swarm == "resurrect" else "this pass's own donations become cells"),
           "budget_s": COMPILER_BUDGET_S, "share": None, "basis": "join",
           "yields": {"generator": "discovery_compiler", "yield": None,
                      "why": "the compiler is the join, not a generator: it has no yield of its "
                             "own and is never allocated by one"}}
    return run_engine(swarm, row, dry_run=dry_run)


def _pay_compute(engines: list[dict[str, Any]]) -> None:
    """Every engine's seconds go back into `generator_yield.compute_s`.

    THE DENOMINATOR CLOSES HERE. Y_g on its own says which engine converts; compute_s says what
    the conversion cost, and the pass that spends the seconds is the only organ that knows. An
    engine that never ran is never charged.
    """
    try:
        from libs.moat import registry as reg
    except Exception:
        return
    for e in engines:
        key = str((e.get("yields") or {}).get("generator") or "")
        if not key or e["status"] in ("MISSING", "PLANNED") or float(e["seconds"]) <= 0.0:
            continue
        with contextlib.suppress(Exception):
            reg.generator_yield_update(key, compute_s=float(e["seconds"]))


def heartbeat(swarm: str, pass_no: int, *, status: str = "running", done_inc: int = 0) -> None:
    """The swarm is a WORKER of the canonical registry, one row per swarm, beating every pass."""
    with contextlib.suppress(Exception):
        from libs.moat import registry as reg
        reg.worker_heartbeat(f"moat:{swarm}", kind="moat_swarm", department=f"moat_{swarm}",
                             beat=str(MIN_CYCLE_S), status=status, pid=os.getpid(),
                             current_campaign=f"pass {pass_no}", generator=swarm,
                             campaigns_done_inc=done_inc)


def workers() -> list[dict[str, Any]]:
    """Every live moat-swarm worker the registry knows -- the proof the three run CONCURRENTLY."""
    try:
        from libs.moat import registry as reg
        rows = reg.workers_alive()
    except Exception:
        return []
    return [{"worker_id": str(r.get("worker_id")), "status": str(r.get("status")),
             "pid": r.get("pid"), "host": str(r.get("host") or ""),
             "current_campaign": str(r.get("current_campaign") or ""),
             "campaigns_done": int(r.get("campaigns_done") or 0), "age_s": r.get("age_s")}
            for r in rows if str(r.get("kind") or "") == "moat_swarm"]


def wait_for_memory(swarm: str, *, min_free_mb: float = MIN_FREE_MB,
                    max_wait_s: float = MAX_MEM_WAIT_S) -> float | None:
    """Do not start a pass while the box is tight. UNMEASURABLE free memory starts the pass:
    refusing on an unreadable counter would idle the swarm forever on a box that cannot answer."""
    waited = 0.0
    while waited < max_wait_s:
        free = free_phys_mb()
        if free is None or free >= min_free_mb:
            return free
        if waited == 0.0:
            log(swarm, f"waiting: free memory {free:.0f}MB below {min_free_mb:.0f}MB")
        time.sleep(30)
        waited += 30.0
    return free_phys_mb()


# --------------------------------------------------------------------------- the report
def _write(path: Path, doc: dict[str, Any]) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def publish(swarm: str, doc: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    """Merge this swarm's pass into the shared report and write it whole.

    THREE RESIDENTS SHARE ONE FILE, which is the price of one readable artifact for three
    concurrent workers. Each owns exactly its own key under `swarms`, so a merge can only ever
    lose the LAST pass of a sibling that wrote in the same instant -- never a sibling's presence,
    and never a pass's own work, which is already in the registry and the compute ledger.
    """
    dst = path or OUT
    prior: dict[str, Any] = {}
    try:
        prior = json.loads(dst.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        prior = {}
    swarms = dict(prior.get("swarms") or {}) if isinstance(prior.get("swarms"), dict) else {}
    swarms[swarm] = doc
    report = {
        "at": now(),
        "swarms": swarms,
        "workers": workers(),
        "unmeasured": list(doc.get("unmeasured") or []),
        "swarms_idle": [s for s in SWARMS if s not in swarms],
        "box_tasks": [dict(t) for t in BOX_TASKS],
        "rule": RULE,
    }
    _write(dst, report)
    return report


def summary(swarm: str, doc: dict[str, Any]) -> list[str]:
    """Six lines: what ran, on what evidence, for how long, and what could not be measured."""
    eng = doc["engines"]
    lines = [f"MOAT SWARM {swarm.upper()} pass {doc['pass']} {doc['at']}  "
             f"budget={doc['pass_budget_s']:.0f}s spent={doc['seconds']}s  "
             f"measured generators {doc['n_generators_measured']}/{len(eng)}",
             f"  {doc['what']}"]
    for e in eng:
        y = e.get("yields") or {}
        yv = "UNMEASURED" if y.get("yield") is None else f"Y={y['yield']:.4f}"
        lines.append(f"  {e['status']:<8} {e['engine']:<24} budget={e['budget_s']:>6.0f}s "
                     f"ran={e['seconds']:>6.1f}s rc={e['rc']} {yv} ({e.get('basis')})")
    c = doc.get("compiler") or {}
    lines.append(f"  {c.get('status', 'UNKNOWN'):<8} {'discovery_compiler':<24} "
                 f"budget={c.get('budget_s', 0):>6.0f}s ran={c.get('seconds', 0):>6.1f}s")
    lines.append(f"  floor cost {doc['floor_cost_s']}s  |  {doc['allocation_rule'][:120]}")
    for u in (doc.get("unmeasured") or [])[:3]:
        lines.append(f"  UNMEASURED {u['what']}: {str(u['why'])[:88]}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--swarm", required=True, choices=sorted(SWARMS),
                    help="which permanent swarm this resident is")
    ap.add_argument("--once", action="store_true", help="one pass, then exit (tests, probes)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan; start no child, write nothing, charge nothing")
    ap.add_argument("--budget-s", type=float, default=PASS_BUDGET_S,
                    help=f"wall clock one pass hands out (default {PASS_BUDGET_S:.0f})")
    a = ap.parse_args(argv)
    swarm = str(a.swarm).strip().lower()
    handle = None if a.dry_run else claim_singleton(swarm)
    if handle is None and not a.dry_run:
        print(f"moat[{swarm}]: another swarm resident holds the slot; exiting", flush=True)
        return 0
    if not a.dry_run:
        log(swarm, f"swarm started pid {os.getpid()}; pass budget {a.budget_s:.0f}s, "
                   f"min cycle {MIN_CYCLE_S:.0f}s, recycle after {RECYCLE_PASSES} passes")
    passes = 0
    if not a.dry_run:
        heartbeat(swarm, 0)
    try:
        while True:
            passes += 1
            if not a.dry_run:
                wait_for_memory(swarm)
                heartbeat(swarm, passes)
            started = time.monotonic()
            doc = run_pass(swarm, passes, budget_s=float(a.budget_s), dry_run=a.dry_run)
            for line in summary(swarm, doc):
                print(line, flush=True)
            if a.dry_run:
                print("  --dry-run: nothing started, nothing written, nothing charged", flush=True)
                return 0
            publish(swarm, doc)
            log(swarm, f"pass {passes}: {len(doc['engines'])} engine(s) in {doc['seconds']}s "
                       f"-> {OUT}")
            heartbeat(swarm, passes, done_inc=1)
            if a.once:
                return 0
            if passes >= RECYCLE_PASSES:
                log(swarm, "recycling: the keep-alive trigger restarts a fresh swarm")
                return 0
            time.sleep(max(PAUSE_S, MIN_CYCLE_S - (time.monotonic() - started)))
    finally:
        if handle is not None:
            heartbeat(swarm, passes, status="stopped")
            with contextlib.suppress(OSError):
                handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
