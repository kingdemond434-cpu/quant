"""THE REGION DEPARTMENT RUNNER -- one region's twenty-step loop, hourly, as one leg.

WHAT THIS IS. `libs/research/region_mandate.py` is the principal's Japan mandate with the nouns
taken out: the vocabularies, the registers, the frontier, saturation, the ROI and the wall. This
is the ORGAN that runs it. Point it at a region package and it executes sections 38's twenty
steps in order, inside a wall-clock budget, and leaves one artifact that says what each step did
-- including the steps that did nothing, and why.

    python region_department.py --region japan --budget-s 1800 [--once] [--dry-run]

A REGION IS A PACKAGE, NOT A BRANCH OF THIS FILE. `desks/mt5/research/<region>/mandate.py`
exposes MANDATE (a `region_mandate.Mandate`), `miners.py` exposes MINERS -- `{name: callable(ctx)
-> dict}`. Japan first, macro second, then China, Korea, India, Australia, Europe, the UK, North
America, LatAm, the Middle East and Africa; section 46 requires each region to discover its own
mechanics, so nothing region-specific may ever be written here. If the package is absent this
exits 2 and NAMES what is missing -- a runner that treated an absent region as an empty one would
report a green pass for a department that does not exist.

BUDGETS ARE PAID BY MEASURED YIELD, WITH TWO FLOORS. Each miner's share comes from its
`generator_yield` row under a Jeffreys prior ((independent_survivors + 0.5) / (generated + 1)),
so a miner that has produced nothing is not assumed useless and a miner with one lucky survivor
is not crowned. Then two floors, in this order: every miner keeps at least MINER_FLOOR of the
pool, and the miners with NO success ever collectively keep at least COLD_SHARE of it (section
28: cold exploration is PROTECTED -- no survivor, no popular strategy, no English analogue, no
previous success is exactly the ground a yield-maximising allocator defunds first, and it is the
only ground where an unshared edge can still be).

THE ONE THING THIS DOES NOT DO IS DONATE. The compiler (step 12) already donates what it
compiles, through `proposer_common.donate`, and the docket reads the registry. Donating again
here would put the same cell on the docket twice and charge the program's shared multiple-testing
budget twice for one question. The department's bid is a CLAIM: step 16 marks the top-ranked
complete candidates `claimed` for the gauntlet, which is the exchange's own currency.

AND IT HAS NO CAPITAL AUTHORITY (section 42). It writes no sleeve, no fraction, no promotion and
no threshold. Its output terminates at a gauntlet-ready candidate, `region_mandate.validate`
refuses a mandate that claims otherwise, and `assert_boundaries` refuses a policy knob that so
much as names point-in-time, trial accounting, multiple testing, a sealed holdout, a gauntlet
threshold, forward evidence, a cost assumption or provenance.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import region_mandate as RM  # noqa: E402

#: Where a region package lives. Module-level so a test can plant one in tmp_path.
PACKAGE_ROOT: Path = BASE / "research"
#: A region whose natural package name would shadow an existing package (desks/mt5/macro is
#: the macro allocator) lives under another directory; the region id stays what the mandate says.
REGION_PACKAGES: dict[str, str] = {"macro": "macro_region"}
REPORTS = BASE / "reports"
DATA = BASE / "data"
REGIONS = DATA / "regions"
SLEEVES = DATA / "sleeves.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
SHADOW = REPORTS / "shadow" / "shadow_state.json"
RESEARCH_DEBT_JSON = REPORTS / "RESEARCH_DEBT.json"
#: Run exactly as `hourly_cycle._producer` runs it: resolved against both roots, a subprocess with
#: a timeout, its exit code and tail captured, an absent script reported MISSING rather than run.
COMPILER = "research/discovery_compiler.py"

BUDGET_S = 1800.0
#: How the pass's seconds are split. The miners and the compiler are the work; the other
#: seventeen steps are bookkeeping and measurement and must not be able to eat the pass.
MINER_SHARE = 0.50
COMPILER_SHARE = 0.25
#: Per-miner floors of the miner pool (section 27: exploration AND exploitation, permanently).
MINER_FLOOR = 0.05
COLD_SHARE = 0.10
#: A step may never be given less than this, or "time-boxed" becomes "not run".
STEP_FLOOR_S = 2.0
#: How many ranked candidates the department bids for per pass.
CLAIM_K = 24
#: How hard an empty cell outranks a crowded one when the queue is ranked (section 35).
ORTHO_BONUS = 1.0
#: Rows read per pass from the registry; a pass that hits this says so.
MAX_ROWS = 20_000

OK, SKIPPED, UNMEASURED, FAILED = "ok", "skipped", "UNMEASURED", "failed"

#: Which loop step each kind of specialist miner runs under (sections 26 and 38).
MINER_STEP: dict[str, str] = {
    "scout": "ingest_sources", "data": "ingest_datasets", "calendar": "update_policy_event_state",
    "mechanism": "discover_mechanisms", "transfer": "exploit_mechanisms",
    "failure": "mine_failures", "residual": "mine_residuals",
}

#: Chart -> the frontier's horizon vocabulary. A chart nobody can place leaves the horizon
#: UNKNOWN, which makes the row unplaceable, which is counted -- never guessed.
CHART_HORIZON: dict[str, str] = {"M1": "intraday", "M5": "intraday", "M15": "intraday",
                                 "M30": "intraday", "H1": "intraday", "H4": "overnight",
                                 "D1": "multi_day", "W1": "multi_day"}

RULE_47 = ("a region department has ZERO capital authority: its output terminates at a "
           "GAUNTLET_READY_CANDIDATE, it never assumes saturation, it never stops exploring "
           "cold ground, and it is never finished -- the loop runs again next hour")


class RegionMissing(RuntimeError):
    """The region package is not on this box, and the runner says exactly what is absent."""


# --------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only destination is legal
    on POSIX and raises WinError 5 here -- the way a VPS-tested fix once broke the trading box."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(body, encoding="utf-8")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- the region package
def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RegionMissing(f"{path} cannot be loaded as a module")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


MinerFn = Callable[["Ctx"], Mapping[str, Any]]


def load_region(region: str) -> tuple[RM.Mandate, dict[str, MinerFn]]:
    """The region's mandate and miners, or RegionMissing naming the first thing that is absent."""
    pkg = Path(PACKAGE_ROOT) / REGION_PACKAGES.get(region, region)
    if not pkg.is_dir():
        raise RegionMissing(f"no region package at {pkg}: a region is a directory holding "
                            f"mandate.py (exposing MANDATE) and miners.py (exposing MINERS)")
    mandate_py, miners_py = pkg / "mandate.py", pkg / "miners.py"
    if not mandate_py.exists():
        raise RegionMissing(f"{mandate_py} is absent; it must expose MANDATE")
    if not miners_py.exists():
        raise RegionMissing(f"{miners_py} is absent; it must expose MINERS")
    mandate_mod = _load_module(mandate_py, f"region_{region}_mandate")
    miners_mod = _load_module(miners_py, f"region_{region}_miners")
    mandate = getattr(mandate_mod, "MANDATE", None)
    if not isinstance(mandate, RM.Mandate):
        raise RegionMissing(f"{mandate_py} exposes no MANDATE of type region_mandate.Mandate")
    miners = getattr(miners_mod, "MINERS", None)
    if not isinstance(miners, Mapping):
        raise RegionMissing(f"{miners_py} exposes no MINERS mapping of name -> callable(ctx)")
    out: dict[str, MinerFn] = {}
    for name, fn in miners.items():
        if callable(fn):
            out[str(name)] = fn
    return mandate, out


# --------------------------------------------------------------------------- the miner context
@dataclass
class Ctx:
    """What a region miner is handed: the registry connection, the mandate, its own budget, and
    the one door it records through -- which stamps the region tag so every row it writes can be
    found again by `region_mandate.is_region_row`."""

    region: str
    mandate: RM.Mandate
    conn: sqlite3.Connection
    budget_s: float
    deadline: float
    dry_run: bool = False
    miner: str = ""
    recorded: list[str] = field(default_factory=list)

    @property
    def tag(self) -> str:
        return RM.tag(self.mandate)

    def remaining_s(self) -> float:
        """Seconds left in this miner's box. A miner is expected to honour it; the runner
        MEASURES the overrun either way, because a callable cannot be interrupted from outside."""
        return max(0.0, self.deadline - time.monotonic())

    def record_discovery(self, *, mechanism: str, source_id: str = "",
                         source_type: str = "claim", **fields: Any) -> tuple[str, bool]:
        """Record one discovery, stamped for this region. Returns (discovery_id, created)."""
        tag = self.tag
        sid = str(source_id or self.miner or "unattributed")
        if not sid.lower().startswith(tag):
            sid = f"{tag}{sid}"
        # A MINER MAY NAME ITS OWN GENERATOR, and four Japan miners do ("japan:mine_gotobi").
        # This wrapper used to build the generator and then forward **fields, so any miner that
        # supplied one raised `got multiple values for keyword argument 'generator'` -- measured
        # 2026-09-17, where it silently cost four calendar miners every discovery they made,
        # every pass, while the department reported UNMEASURED TypeError and carried on. The
        # miner's own name wins; the region tag is still enforced on it.
        generator = str(fields.pop("generator", "") or "").strip() or (
            f"{tag}{self.miner or 'unnamed'}")
        if not generator.lower().startswith(tag):
            generator = f"{tag}{generator}"
        payload = dict(fields.pop("payload", None) or {})
        payload.setdefault("region", self.mandate.region)
        payload.setdefault("miner", self.miner)
        origin = str(fields.pop("origin", "EXTERNAL"))
        if self.dry_run:
            return "dry-run", False
        did, created = R.record_discovery(source_id=sid, source_type=source_type,
                                          mechanism=mechanism, origin=origin, generator=generator,
                                          payload=payload, conn=self.conn, **fields)
        self.recorded.append(did)
        return did, created


# --------------------------------------------------------------------------- budgets
def miner_budgets(mandate: RM.Mandate, pool_s: float,
                  yields: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Seconds per miner, by MEASURED downstream yield, under two floors.

    Jeffreys rather than a raw ratio: (independent_survivors + 0.5) / (generated + 1). A miner
    with 0/0 reads 0.5 and a miner with 1/1 reads 0.75, so neither absence nor a single lucky
    survivor decides the allocation. The floor keeps every declared miner alive; the cold share
    keeps the miners that have never succeeded ALIVE AS A CLASS, which is the only protection
    that survives an allocator doing its job.
    """
    by_gen = {str(r.get("generator") or "").lower(): r for r in yields}
    tag = RM.tag(mandate)
    names = [mi.name for mi in mandate.miners]
    out: dict[str, dict[str, Any]] = {}
    if not names:
        return out
    fixed = [mi.name for mi in mandate.miners if not mi.steerable]
    steer = [n for n in names if n not in fixed]
    fixed_share = min(1.0, len(fixed) / float(len(names)))
    share_left = max(0.0, 1.0 - fixed_share)

    prior: dict[str, float] = {}
    cold: list[str] = []
    for name in names:
        row = by_gen.get(f"{tag}{name}".lower(), {})
        gen = _f(row.get("generated"))
        indep = _f(row.get("independent_survivors"))
        prior[name] = (indep + 0.5) / (gen + 1.0)
        if indep <= 0:
            cold.append(name)

    weight: dict[str, float] = {n: fixed_share / len(fixed) for n in fixed} if fixed else {}
    if steer:
        floor = min(MINER_FLOOR, share_left / len(steer))
        free = max(0.0, share_left - floor * len(steer))
        total = sum(prior[n] for n in steer)
        for n in steer:
            frac = (prior[n] / total) if total > 0 else (1.0 / len(steer))
            weight[n] = floor + free * frac
    cold_steer = [n for n in cold if n in weight]
    warm = [n for n in weight if n not in cold_steer]
    have = sum(weight[n] for n in cold_steer)
    want = COLD_SHARE * sum(weight.values())
    if cold_steer and have < want:
        # THE COLD FLOOR WINS OVER THE PER-MINER FLOOR, and it has to: a warm miner pushed below
        # MINER_FLOOR still ran last pass and can be funded next one, while cold ground defunded
        # to zero is never measured again and therefore never stops looking worthless.
        for n in cold_steer:
            weight[n] = (weight[n] * want / have) if have > 0 else want / len(cold_steer)
        rest = max(0.0, sum(weight.values()) - want)
        warm_have = sum(weight[n] for n in warm)
        for n in warm:
            weight[n] = (rest * weight[n] / warm_have) if warm_have > 0 else (
                rest / len(warm) if warm else 0.0)
    total_w = sum(weight.values()) or 1.0
    for mi in mandate.miners:
        w = weight.get(mi.name, 0.0) / total_w
        out[mi.name] = {
            "weight": round(w, 6), "budget_s": round(max(0.0, pool_s * w), 3),
            "prior": round(prior[mi.name], 6), "cold": mi.name in cold,
            "steerable": bool(mi.steerable), "kind": mi.kind,
            "why": (f"jeffreys prior {prior[mi.name]:.3f} on its generator_yield row"
                    + ("; COLD (no independent survivor ever) and protected by the "
                       f"{COLD_SHARE:.0%} cold share" if mi.name in cold else "")
                    + ("" if mi.steerable else "; fixed cost, not steerable")),
        }
    return out


# --------------------------------------------------------------------------- desk evidence
def _axes_from(mandate: RM.Mandate, symbol: str, mechanism: str, session: str, chart: str,
               regime: str) -> dict[str, str] | None:
    """A desk row placed on the region's eight-axis map, or None when the mandate does not
    DETERMINE the missing axes.

    A sleeve records a symbol, a family, a session and a chart. It records no economic actor and
    no constraint, and those are two of the eight axes. Filling them by picking an actor that
    could plausibly apply would put the desk's own book on coordinates nobody measured, so the
    row is placed only when exactly one of the mandate's actors names that instrument and that
    actor names exactly one constraint and one information axis. Everything else is counted as
    unplaceable, which is a finding about the mandate rather than a gap in the map.
    """
    sym = str(symbol or "").upper()
    if sym not in {s.upper() for s in mandate.instruments}:
        return None
    actors = [a for a in mandate.actors if sym in {i.upper() for i in a.instruments}]
    if len(actors) != 1 or len(actors[0].constraints) != 1 or len(actors[0].information) != 1:
        return None
    horizon = CHART_HORIZON.get(str(chart or "").upper(), "")
    ses = str(session or "").lower()
    if ses in ("", "none", "all_day"):
        ses = "all"
    if ses == "asia":
        ses = "tokyo"
    reg = str(regime or "").lower() or "unconditional"
    if ses not in RM.SESSIONS or horizon not in RM.HORIZONS:
        return None
    if reg not in RM.REGIMES:
        reg = "unconditional"
    a = actors[0]
    return {"asset": sym, "actor": a.name, "constraint": a.constraints[0], "mechanism": mechanism,
            "information": a.information[0], "session": ses, "horizon": horizon, "regime": reg}


def desk_evidence(mandate: RM.Mandate) -> tuple[dict[str, list[dict[str, str]]], dict[str, int]]:
    """LIVE / FORWARD / SURVIVED cells from the desk's own artifacts, plus what could not be
    placed. Read tolerantly: an absent artifact is an absence, never a zero."""
    out: dict[str, list[dict[str, str]]] = {"LIVE": [], "FORWARD": [], "SURVIVED": []}
    note = {"sleeves": 0, "survivors": 0, "forward": 0, "unplaceable": 0, "absent": 0}

    def place(state: str, counter: str, axes: dict[str, str] | None) -> None:
        note[counter] += 1
        if axes is None:
            note["unplaceable"] += 1
        else:
            out[state].append(axes)

    doc = _read_json(SLEEVES)
    if doc is None:
        note["absent"] += 1
    rows = (doc.get("sleeves") if isinstance(doc, dict) else doc) or []
    for s in (rows.values() if isinstance(rows, dict) else rows):
        if not isinstance(s, dict):
            continue
        if str(s.get("status") or "").upper() not in ("LIVE", "STANDBY"):
            continue
        place("LIVE", "sleeves",
              _axes_from(mandate, str(s.get("symbol") or ""), str(s.get("family") or ""),
                         str(s.get("session") or ""), str(s.get("timeframe") or ""), ""))

    doc = _read_json(SURVIVORS)
    if doc is None:
        note["absent"] += 1
    surv = (doc.get("survivors") if isinstance(doc, dict) else doc) or {}
    for row in (surv.values() if isinstance(surv, dict) else surv):
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
        place("SURVIVED", "survivors",
              _axes_from(mandate, str(row.get("sym") or ""), str(spec.get("family") or ""),
                         str(spec.get("session") or ""), str(spec.get("chart") or ""), ""))

    doc = _read_json(SHADOW)
    if doc is None:
        note["absent"] += 1
    for key, row in (doc or {}).items() if isinstance(doc, dict) else []:
        if not isinstance(row, dict):
            continue
        bits = str(key).split()
        place("FORWARD", "forward",
              _axes_from(mandate, bits[0] if bits else "", bits[1] if len(bits) > 1 else "",
                         bits[3] if len(bits) > 3 else "", str(row.get("timeframe") or ""),
                         bits[4] if len(bits) > 4 else ""))
    return out, note


# --------------------------------------------------------------------------- the compiler leg
def _producer(name: str, script: str, *args: str, budget_s: float = 240.0) -> dict[str, Any]:
    """One producer as a subprocess, bounded, reported -- the shape `hourly_cycle._producer` uses.

    The script is resolved against BOTH roots and a miss is REPORTED rather than run: python
    given a nonexistent file exits 2 with a one-line error, which would read as an ordinary
    failing leg. ABSENCE IS NEVER A PASS (L1.28a)."""
    for root in (BASE, REPO):
        target = root / script
        if target.exists():
            break
    else:
        return {"exit_code": None, "status": "MISSING",
                "why": f"{script} exists under neither {BASE} nor {REPO}", "at": _now()}
    try:
        r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target), *args],
                           capture_output=True, text=True, cwd=str(root),
                           timeout=max(1.0, budget_s), check=False)
        return {"exit_code": r.returncode, "tail": (r.stdout or r.stderr or "")[-300:],
                "budget_s": budget_s, "at": _now()}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "timeout_s": budget_s,
                "note": f"{name} exceeded its step budget and was stopped; its partial work is "
                        f"whatever it had already written", "at": _now()}
    except OSError as exc:
        return {"exit_code": None, "error": f"{type(exc).__name__}: {exc}", "at": _now()}


# --------------------------------------------------------------------------- the pass
@dataclass
class Pass:
    """One execution of the twenty steps. Everything a step learns lands here, so a later step
    reads a measurement rather than re-deriving it (and the two can never disagree)."""

    region: str
    mandate: RM.Mandate
    miners: dict[str, MinerFn]
    conn: sqlite3.Connection
    budget_s: float
    dry_run: bool
    started: float
    n: int = 1
    steps: list[dict[str, Any]] = field(default_factory=list)
    miner_rows: list[dict[str, Any]] = field(default_factory=list)
    budgets: dict[str, dict[str, Any]] = field(default_factory=dict)
    registers: dict[str, Any] = field(default_factory=dict)
    frontier: dict[str, Any] = field(default_factory=dict)
    ranked: list[dict[str, Any]] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    verdicts: list[dict[str, Any]] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    cursor: dict[str, Any] = field(default_factory=dict)
    documents: int = 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def left(self) -> float:
        return max(0.0, self.budget_s - self.elapsed())


def _step(p: Pass, name: str, budget_s: float,
          fn: Callable[[float], Mapping[str, Any]]) -> dict[str, Any]:
    """Run one loop step inside its box and RECORD IT, whatever happened.

    Four outcomes and no fifth: ok, skipped (the pass budget was spent first), UNMEASURED (the
    step ran and the thing it measures is not on this box), failed (with the exception). A step
    that quietly produced no row is the one failure mode this harness exists to make impossible."""
    idx = len(p.steps) + 1
    row: dict[str, Any] = {"n": idx, "step": name, "budget_s": round(budget_s, 2)}
    if p.left() <= 0:
        row.update({"outcome": SKIPPED, "seconds": 0.0,
                    "why": f"the pass budget of {p.budget_s:.0f}s was spent before step {idx}"})
        p.steps.append(row)
        return row
    t0 = time.monotonic()
    try:
        result = fn(max(STEP_FLOOR_S, min(budget_s, p.left())))
        row.update(dict(result))
        row.setdefault("outcome", OK)
    except Exception as exc:          # one step may never take the pass with it
        row.update({"outcome": FAILED, "why": f"{type(exc).__name__}: {str(exc)[:300]}"})
    row["seconds"] = round(time.monotonic() - t0, 3)
    if row["outcome"] in (UNMEASURED, FAILED):
        p.unmeasured.append(f"{name}: {row.get('why') or row['outcome']}")
    p.steps.append(row)
    return row


def _run_miners(p: Pass, kind: str, budget_s: float) -> dict[str, Any]:
    """Every miner of one kind, each inside its own measured share of the pool."""
    specs = [mi for mi in p.mandate.miners if mi.kind == kind]
    if not specs:
        return {"outcome": UNMEASURED, "miners": 0,
                "why": f"the mandate declares no {kind} miner; that axis is unmined, not empty"}
    ran = 0
    discoveries = 0
    for mi in specs:
        fn = p.miners.get(mi.name)
        share = _f((p.budgets.get(mi.name) or {}).get("budget_s"), 0.0)
        box = max(STEP_FLOOR_S, min(share, p.left()))
        rec: dict[str, Any] = {"name": mi.name, "kind": mi.kind, "budget_s": round(box, 3),
                               "discoveries": 0, "documents": 0, "seconds": 0.0,
                               "why": str((p.budgets.get(mi.name) or {}).get("why") or "")}
        if fn is None:
            rec.update({"outcome": FAILED,
                        "why": "declared in the mandate and absent from MINERS"})
            p.miner_rows.append(rec)
            p.unmeasured.append(f"miner {mi.name}: declared and not implemented")
            continue
        if p.left() <= 0:
            rec.update({"outcome": SKIPPED, "why": "the pass budget was spent first"})
            p.miner_rows.append(rec)
            continue
        ctx = Ctx(region=p.region, mandate=p.mandate, conn=p.conn, budget_s=box,
                  deadline=time.monotonic() + box, dry_run=p.dry_run, miner=mi.name)
        t0 = time.monotonic()
        try:
            result = fn(ctx)
            out = dict(result) if isinstance(result, Mapping) else {}
            rec["result"] = {k: v for k, v in out.items() if k not in ("outcome", "why")}
            rec["documents"] = int(_f(out.get("documents")))
            rec["outcome"] = str(out.get("outcome") or OK)
            if out.get("why"):
                rec["why"] = str(out["why"])
            ran += 1
        except Exception as exc:      # one miner may never take the step with it
            rec.update({"outcome": FAILED, "why": f"{type(exc).__name__}: {str(exc)[:200]}"})
            p.unmeasured.append(f"miner {mi.name}: {type(exc).__name__}")
        rec["seconds"] = round(time.monotonic() - t0, 3)
        rec["discoveries"] = len(ctx.recorded)
        rec["overran_s"] = round(max(0.0, rec["seconds"] - box), 3)
        discoveries += rec["discoveries"]
        p.documents += rec["documents"]
        p.miner_rows.append(rec)
    return {"outcome": OK if ran else UNMEASURED, "miners": len(specs), "ran": ran,
            "discoveries": discoveries,
            "why": "" if ran else f"no {kind} miner produced a pass"}


# --------------------------------------------------------------------------- the twenty steps
def run_pass(region: str, mandate: RM.Mandate, miners: dict[str, MinerFn], *,
             budget_s: float = BUDGET_S, dry_run: bool = False,
             conn: sqlite3.Connection | None = None, n: int = 1) -> dict[str, Any]:
    """Sections 38's twenty steps, in order, inside `budget_s`. Returns the report."""
    c = conn or R.connect()
    close = conn is None
    p = Pass(region=region, mandate=mandate, miners=miners, conn=c, budget_s=float(budget_s),
             dry_run=dry_run, started=time.monotonic(), n=n)
    p.cursor = _read_cursor(region)
    try:
        pool = p.budget_s * MINER_SHARE
        p.budgets = miner_budgets(mandate, pool, R.generator_yields(conn=c))
        book = max(STEP_FLOOR_S,
                   p.budget_s * (1.0 - MINER_SHARE - COMPILER_SHARE) / 12.0)

        _step(p, "ingest_sources", pool, lambda b: _run_miners(p, "scout", b))
        _step(p, "update_source_graph", book, lambda b: _update_source_graph(p, b))
        _step(p, "ingest_datasets", pool, lambda b: _ingest_datasets(p, b))
        _step(p, "update_policy_event_state", pool, lambda b: _run_miners(p, "calendar", b))
        _step(p, "discover_mechanisms", pool, lambda b: _run_miners(p, "mechanism", b))
        _step(p, "update_frontier", book, lambda b: _update_frontier(p, b))
        _step(p, "exploit_mechanisms", pool, lambda b: _run_miners(p, "transfer", b))
        _step(p, "mine_failures", pool, lambda b: _run_miners(p, "failure", b))
        _step(p, "mine_residuals", pool, lambda b: _run_miners(p, "residual", b))
        _step(p, "inspect_conversion_debt", book, lambda b: _conversion_debt(p, b))
        _step(p, "inspect_research_debt", book, lambda b: _research_debt(p, b))
        _step(p, "compile_cells", p.budget_s * COMPILER_SHARE, lambda b: _compile_cells(p, b))
        _step(p, "dedupe", book, lambda b: _dedupe(p, b))
        _step(p, "score_orthogonality", book, lambda b: _score_orthogonality(p, b))
        _step(p, "rank_queue", book, lambda b: _rank_queue(p, b))
        _step(p, "submit_to_gauntlet", book, lambda b: _submit(p, b))
        _step(p, "ingest_verdicts", book, lambda b: _ingest_verdicts(p, b))
        _step(p, "update_priors", book, lambda b: _update_priors(p, b))
        _step(p, "create_descendants", book, lambda b: _create_descendants(p, b))
        report = _report(p)
        _step(p, "simplify", book, lambda b: _simplify(p, b, report))
        report["steps"] = p.steps
        report["seconds"] = round(p.elapsed(), 3)
        if not dry_run:
            _write_atomic(REPORTS / f"REGION_{region.upper()}.json", report)
            _append_loop(region, report)
            _write_cursor(region, p, report)
            with contextlib.suppress(Exception):
                R.worker_heartbeat(f"region:{region}", kind="region_department",
                                   department=f"region:{region}", beat=_now(),
                                   generator=RM.tag(mandate), campaigns_done_inc=1, conn=c)
        return report
    finally:
        if close:
            c.close()


def _update_source_graph(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 2. Every source that produced a region discovery gets a row and a lead counted, so
    section 36's ROI has a denominator before it has a numerator."""
    rows = [r for r in R.discoveries(limit=MAX_ROWS, conn=p.conn)
            if RM.is_region_row(p.mandate, r)]
    sources: dict[str, int] = {}
    for r in rows:
        sid = str(r.get("source_id") or "")
        if sid:
            sources[sid] = sources.get(sid, 0) + 1
    if p.dry_run:
        return {"outcome": OK, "sources": len(sources), "why": "dry run: nothing written"}
    known = {str(r["source_id"]) for r in p.conn.execute("SELECT source_id FROM sources")}
    created = 0
    for sid, n in sources.items():
        if sid in known:
            continue
        p.conn.execute("INSERT OR IGNORE INTO sources(source_id, kind, language, country, "
                       "first_seen, last_crawled, status, meta_json) VALUES(?,?,?,?,?,?,?,?)",
                       (sid, "region", (p.mandate.native_languages or ("",))[0], p.region,
                        _now(), _now(), "active",
                        json.dumps({"region": p.mandate.region, "leads": n})))
        created += 1
    p.conn.commit()
    return {"outcome": OK, "sources": len(sources), "created": created}


def _ingest_datasets(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 3. The data miners run, and the mandate's own catalogue (section 20) is written into
    research memory -- including every entry whose six PIT stamps cannot be reconstructed, which
    is the field the catalogue exists for."""
    res = dict(_run_miners(p, "data", budget_s))
    not_pit = [d.name for d in p.mandate.datasets if not d.pit_feasible]
    res["datasets"] = len(p.mandate.datasets)
    res["not_pit_feasible"] = not_pit
    if p.dry_run or not p.mandate.datasets:
        return res
    tag = RM.tag(p.mandate)
    for d in p.mandate.datasets:
        R.remember("region_dataset", f"{d.name}: {d.source}", kind="dataset",
                   memory_key=f"{tag}dataset:{d.name}",
                   result="success" if d.pit_feasible else "pending",
                   failure_cause=None if d.pit_feasible else RM.PIT_UNSAFE,
                   payload={"region": p.mandate.region, "name": d.name, "source": d.source,
                            "coverage": d.coverage, "frequency": d.frequency,
                            "publication_lag_days": d.publication_lag_days,
                            "revisions": d.revisions, "licence": d.licence,
                            "history_from": d.history_from, "pit_feasible": d.pit_feasible,
                            "assets": list(d.assets), "mechanism_families":
                                list(d.mechanism_families), "how_to_fetch": d.how_to_fetch},
                   conn=p.conn)
    res["outcome"] = OK
    return res


def _update_frontier(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 6. The eight-axis map, with the desk's own book placed on it where the mandate
    determines the coordinates and COUNTED where it does not."""
    evidence, note = desk_evidence(p.mandate)
    p.frontier = RM.frontier(p.mandate, conn=p.conn, evidence=evidence)
    if note["unplaceable"]:
        p.unmeasured.append(
            f"frontier: {note['unplaceable']} desk row(s) could not be placed -- no sleeve, "
            f"certificate or clock records an economic actor or a constraint")
    un = p.frontier.get("unmeasured") or {}
    if un.get("truncated"):
        p.unmeasured.append(f"frontier: {un.get('truncated_why')}")
    return {"outcome": OK, "n_cells": p.frontier["n_cells"],
            "n_populated": p.frontier["n_populated"], "by_state": p.frontier["by_state"],
            "truncated": bool(un.get("truncated")), "evidence": note}


def _conversion_debt(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 10. Section 24's nine registers; the ninth is the one that must reach zero."""
    p.registers = RM.conversion_registers(p.mandate, conn=p.conn)
    prefix = p.region.upper()
    debt = int(p.registers.get(f"{prefix}_UNEXPLAINED_DEBT") or 0)
    return {"outcome": OK, "registers": {k: v for k, v in p.registers.items()
                                         if k.startswith(prefix)},
            "unexplained_debt": debt,
            "why": "" if debt == 0 else f"{debt} child cell(s) left a closure with no disposition"}


def _research_debt(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 11. What a mechanism tested on one coordinate still owes on every other. Read from
    the organ that OWNS it; absent is UNMEASURED, never zero."""
    doc = _read_json(RESEARCH_DEBT_JSON)
    if not isinstance(doc, dict):
        return {"outcome": UNMEASURED,
                "why": f"{RESEARCH_DEBT_JSON} is absent or unreadable; the research-debt organ "
                       f"owns that number and this pass will not invent one"}
    mechs = {RM.norm(m) for m in p.frontier.get("mechanism_vocabulary", [])}
    rows = doc.get("mechanisms") if isinstance(doc.get("mechanisms"), list) else []
    mine = [r for r in rows if isinstance(r, Mapping)
            and RM.norm(r.get("mechanism_id")) in mechs]
    return {"outcome": OK, "at": doc.get("at"), "total_debt": doc.get("total_debt"),
            "region_mechanisms_with_debt": len(mine),
            "region_debt_cells": sum(int(_f(r.get("debt_cells"))) for r in mine),
            "never_tested": len(doc.get("untested_mechanisms") or [])}


def _compile_cells(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 12. The universal discovery-to-cell compiler, as a bounded subprocess.

    IT IS NOT RE-IMPLEMENTED HERE. One compiler means one closure, one gate vocabulary and one
    conversion-debt ledger for every department; a region that compiled its own cells would have
    its own silent drops to find."""
    args = ["--budget-s", str(int(max(1.0, budget_s)))]
    if p.dry_run:
        args.append("--dry-run")
    res = _producer("discovery_compiler", COMPILER, *args, budget_s=budget_s)
    ok = res.get("exit_code") == 0
    said = (res.get("status") or res.get("error") or res.get("note")
            or f"exit {res.get('exit_code')}")
    return {"outcome": OK if ok else FAILED, "compiler": res,
            "why": "" if ok else f"discovery_compiler: {said}"}


def _parent_payload(row: Mapping[str, Any], conn: Any,
                    cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The payload of the discovery this candidate came from, or {}.

    THE REQUIREMENTS LIVE THERE AND NOWHERE ELSE. `discoveries` has no column for counterparty,
    exact entry, exact exit, expected costs, capacity, negative control or falsifier, so every
    region miner writes them into its payload -- and the candidate the compiler builds from that
    discovery carries none of them. Measured 2026-09-17 on the Japan department: 539 of 539
    candidates ranked, 539 held upstream, all ten fields missing on every one. The miners were
    doing the work; the fields were being dropped in transit.
    """
    if conn is None:
        return {}
    did = str(row.get("discovery_id") or "")
    if not did:
        for edge in R.provenance_of("cell", str(row.get("id") or ""), depth=3, conn=conn):
            if str(edge.get("parent_kind")) == "discovery":
                did = str(edge.get("parent_id") or "")
                break
    if not did:
        return {}
    if did in cache:
        return cache[did]
    payload: dict[str, Any] = {}
    try:
        got = conn.execute("SELECT payload_json FROM discoveries WHERE discovery_id=?",
                           (did,)).fetchone()
        raw = got["payload_json"] if got is not None else ""
        parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:                       # a payload nobody can read is not a crash
        payload = {}
    cache[did] = payload
    return payload


def _candidate_view(row: Mapping[str, Any], conn: Any = None,
                    cache: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """A candidate row plus the fields the registry has no COLUMN for.

    Three of section 33's twenty-five -- original_language, counterparty, negative_control --
    have no column in `research_candidates`, so a miner carries them inside params/lineage. Read
    literally, every candidate on the box would be permanently incomplete and the department
    would claim nothing, forever, while reporting that it enforced the requirement. The merge is
    one-way and never overwrites a real column."""
    view = dict(row)
    for key in ("params_json", "lineage_json", "required_data_json"):
        doc = row.get(key)
        parsed = json.loads(doc) if isinstance(doc, str) and doc.strip() else doc
        if not isinstance(parsed, dict):
            continue
        for k, v in parsed.items():
            if view.get(k) in (None, "", [], {}):
                view[k] = v
    payload = _parent_payload(row, conn, cache if cache is not None else {})
    for source in (payload.get("requirements"), payload):
        if not isinstance(source, Mapping):
            continue
        for k, v in source.items():
            if view.get(k) in (None, "", [], {}) and v not in (None, "", [], {}):
                view[k] = v
    return view


def _own_discovery_ids(p: Pass) -> set[str]:
    """Discovery ids this region's miners recorded, by generator/source prefix or declared
    region in the payload. A candidate the compiler built from one of them is the region's own
    even though the candidate row itself carries no region tag."""
    t = RM.tag(p.mandate)
    like = f"{t}%"
    region_tok = f'"region": "{p.mandate.region}"'
    try:
        rows = p.conn.execute(
            "SELECT discovery_id FROM discoveries WHERE generator LIKE ? OR source_id LIKE ? "
            "OR payload_json LIKE ?", (like, like, f"%{region_tok}%")).fetchall()
    except Exception:
        return set()
    return {str(r["discovery_id"] if hasattr(r, "keys") else r[0]) for r in rows}


def _queued(p: Pass) -> list[dict[str, Any]]:
    """The region's OWN queued candidates: rows that carry the region's prefix or declared
    region, plus rows the compiler built from the region's discoveries. Never every candidate
    on an instrument the mandate names (see `region_mandate.OWN_CRITERIA`)."""
    own_discoveries = _own_discovery_ids(p)
    out: list[dict[str, Any]] = []
    for r in R.candidates(status="queued", limit=MAX_ROWS, conn=p.conn):
        if RM.is_own_row(p.mandate, r) or str(r.get("discovery_id") or "") in own_discoveries:
            out.append(r)
    return out


def _dedupe(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 13. Sameness across six notions (section 34) -- and three of them are UNMEASURED here
    and say so. The registry's content hash catches the structural twin, the grid cell catches
    the mechanism twin, the discovery id catches the ancestry twin. Semantic, factor and return
    dedupe need an embedding, a factor model and a return series this step does not have."""
    rows = _queued(p)
    by_hash: dict[str, int] = {}
    by_cell: dict[str, int] = {}
    by_parent: dict[str, int] = {}
    for r in rows:
        by_hash[str(r.get("content_hash") or "")] = by_hash.get(
            str(r.get("content_hash") or ""), 0) + 1
        by_cell[str(r.get("grid_cell") or "")] = by_cell.get(str(r.get("grid_cell") or ""), 0) + 1
        pid = str(r.get("discovery_id") or "")
        if pid:
            by_parent[pid] = by_parent.get(pid, 0) + 1
    repeats = sum(max(0, int(r.get("search_count") or 1) - 1) for r in rows)
    return {"outcome": OK, "queued": len(rows),
            "structural_twins": sum(v - 1 for v in by_hash.values() if v > 1),
            "mechanism_twins": sum(v - 1 for v in by_cell.values() if v > 1),
            "ancestry_siblings": sum(v - 1 for v in by_parent.values() if v > 1),
            "search_count_repeats": repeats,
            "unmeasured_axes": ["semantic", "factor", "return"],
            "why": "semantic, factor and return dedupe need an embedding, a factor model and a "
                   "return series; they are named UNMEASURED rather than reported clean"}


def _score_orthogonality(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 14. Section 35: orthogonality is REWARDED, so a cell with no sibling is worth up to
    twice one with many. The multiplier is 1 + ORTHO_BONUS/(1 + siblings in the same cell)."""
    rows = _queued(p)
    coverage = R.grid_coverage(conn=p.conn)
    sibs: dict[str, int] = {}
    for r in rows:
        key = RM.cell_key(RM.axes_of_candidate(r))
        sibs[key] = sibs.get(key, 0) + 1
    payload_cache: dict[str, dict[str, Any]] = {}
    scored: list[dict[str, Any]] = []
    for r in rows:
        cell = str(r.get("grid_cell") or "")
        empty = int(coverage.get(cell, 0)) <= 1
        base = R.score_candidate(r, empty)
        key = RM.cell_key(RM.axes_of_candidate(r))
        n_sibs = int(sibs.get(key, 1))
        ortho = 1.0 + ORTHO_BONUS / float(n_sibs)
        scored.append({"id": str(r.get("id")), "symbol": r.get("symbol"),
                       "family": r.get("family"), "mechanism": r.get("mechanism"),
                       "cell": key, "grid_cell": cell, "base_score": round(base, 8),
                       "siblings": n_sibs, "orthogonality": round(ortho, 6),
                       "score": round(base * ortho, 8), "cell_empty": empty,
                       "missing": RM.candidate_complete(
                           _candidate_view(r, p.conn, payload_cache)), "row": r})
    p.ranked = scored
    return {"outcome": OK, "scored": len(scored),
            "alone_in_cell": sum(1 for s in scored if s["siblings"] == 1),
            "most_crowded_cell": max((s["siblings"] for s in scored), default=0)}


def _rank_queue(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 15. Highest value first; complete candidates only are eligible (section 33)."""
    p.ranked.sort(key=lambda s: (-float(s["score"]), str(s["id"])))
    eligible = [s for s in p.ranked if not s["missing"]]
    held: dict[str, int] = {}
    for s in p.ranked:
        for fieldname in s["missing"]:
            held[fieldname] = held.get(fieldname, 0) + 1
    return {"outcome": OK, "ranked": len(p.ranked), "eligible": len(eligible),
            "held_upstream": len(p.ranked) - len(eligible),
            "missing_by_field": dict(sorted(held.items(), key=lambda kv: -kv[1])[:12]),
            "top": [{k: s[k] for k in ("id", "symbol", "mechanism", "score", "orthogonality")}
                    for s in p.ranked[:5]],
            "why": ("an incomplete candidate stays upstream (section 33): the missing field is "
                    "the work, not a weaker candidate")}


def _submit(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 16. The department's BID. It claims, it does not donate: the compiler already donated
    what it compiled, and donating again would charge the program's shared multiple-testing
    budget twice for one question."""
    eligible = [s for s in p.ranked if not s["missing"]]
    top = eligible[:CLAIM_K]
    if p.dry_run:
        return {"outcome": OK, "claimed": 0, "would_claim": [s["id"] for s in top],
                "why": "dry run: nothing claimed"}
    claimed: list[str] = []
    for s in top:
        if R.mark_candidate(str(s["id"]), "claimed", claimed_by=f"region:{p.region}",
                            claimed_at=_now(), department=f"region:{p.region}", conn=p.conn):
            claimed.append(str(s["id"]))
    p.claims = claimed
    return {"outcome": OK if claimed else UNMEASURED, "claimed": len(claimed),
            "candidates": claimed[:20], "eligible": len(eligible),
            "why": "" if claimed else "no complete region candidate was queued this pass"}


def _ingest_verdicts(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 17. Every region candidate the gauntlet judged since the last pass."""
    since = str(p.cursor.get("last_judged_at") or "")
    rows = [r for r in R.candidates(limit=MAX_ROWS, conn=p.conn)
            if RM.is_region_row(p.mandate, r) and str(r.get("judged_at") or "")
            and str(r.get("judged_at")) > since]
    p.verdicts = rows
    survived = sum(1 for r in rows if int(r.get("survived") or 0) == 1)
    classes: dict[str, int] = {}
    for r in rows:
        fc = str(r.get("failure_class") or "")
        if fc:
            classes[fc] = classes.get(fc, 0) + 1
    return {"outcome": OK if rows else UNMEASURED, "verdicts": len(rows), "survived": survived,
            "deaths": len(rows) - survived, "failure_classes": classes, "since": since or None,
            "why": "" if rows else "no region candidate has been judged since the last pass"}


def _miner_generator(rec: Mapping[str, Any], tag: str) -> str:
    """THE one key a miner is credited under, derived in ONE place.

    A miner stamps its own generator on every discovery and candidate it writes (the region's
    `_envelope`/`_record` pair). That stamp is what the registry will be joined on, so it is the
    identity -- and the class name in the mandate is only how the pass FINDS the function. Typing
    the key a second time here is what let one organ wear two identities and read barren under
    one of them. The class-name form remains the fallback for a miner that publishes no stamp,
    and it is a fallback, never a second convention.
    """
    result = rec.get("result")
    if isinstance(result, Mapping):
        stamped = str(result.get("generator") or "").strip()
        if stamped.lower().startswith(tag.lower()):
            return stamped
    return f"{tag}{rec['name']}"


def _update_priors(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 18. Pay the miners and the sources by what the gauntlet actually said.

    A miner is paid in INDEPENDENT survivors, never in candidates (section 36/37): the cheapest
    way to top a candidate-count leaderboard is to donate the same rule fifty times, and the
    registry already collapses that to one candidate with search_count 50."""
    if p.dry_run:
        return {"outcome": OK, "generators": 0, "sources": 0, "why": "dry run: nothing written"}
    tag = RM.tag(p.mandate)
    gen_inc: dict[str, dict[str, float]] = {}
    for rec in p.miner_rows:
        # ONE ORGAN, ONE KEY, AND IT IS DERIVED (principal 2026-09-23). This used to be
        # `f"{tag}{rec['name']}"` -- the miner's CLASS name -- while every discovery and candidate
        # the same miner writes carries the SHORT name it stamps itself (`japan:data_scout`, not
        # `japan:JapanDataScout`). Two identities for one organ: `generator_yield` showed twelve
        # Japan miners with compute and no cells while the lineage held their 135 gotobi and 20
        # data_scout discoveries under the other name, so the yield fence read them as barren.
        # The miner's OWN stamp is the single source: it is what the registry will be joined on.
        g = _miner_generator(rec, tag)
        gen_inc.setdefault(g, {}).update({"compute_s": _f(rec.get("seconds"))})
        gen_inc[g]["generated"] = gen_inc[g].get("generated", 0.0) + _f(rec.get("discoveries"))
    for r in p.verdicts:
        g = str(r.get("generator") or "")
        if not g.lower().startswith(tag):
            continue
        d = gen_inc.setdefault(g, {})
        d["judged"] = d.get("judged", 0.0) + 1.0
        if int(r.get("survived") or 0) == 1:
            d["survivors"] = d.get("survivors", 0.0) + 1.0
            indep = _f(r.get("expected_return_independence"), R.PRIOR)
            d["independent_survivors"] = d.get("independent_survivors", 0.0) + (
                1.0 if indep >= 0.5 else 0.0)
    for g, inc in gen_inc.items():
        R.generator_yield_update(g, conn=p.conn, **inc)

    src_inc: dict[str, dict[str, float]] = {}
    for r in p.verdicts:
        sid = str(r.get("source_id") or "")
        if not sid.lower().startswith(tag):
            continue
        d = src_inc.setdefault(sid, {})
        d["judged"] = d.get("judged", 0.0) + 1.0
        if int(r.get("survived") or 0) == 1:
            d["survivors"] = d.get("survivors", 0.0) + 1.0
            d["independent_survivors"] = d.get("independent_survivors", 0.0) + 1.0
    written = 0
    if src_inc:
        try:
            from research import source_frontier as SF
            bump = SF.bump_source_yield
        except Exception:                                                     # pragma: no cover
            bump = _bump_source_yield
        for sid, inc in src_inc.items():
            bump(sid, conn=p.conn, **inc)
            written += 1
    return {"outcome": OK, "generators": len(gen_inc), "sources": written}


def _bump_source_yield(source_id: str, conn: Any = None, **inc: float) -> None:
    """The additive source-yield writer, inline, for a box where the desk module will not import.
    Same columns and the same additive contract as `source_frontier.bump_source_yield`."""
    fields = ("leads", "claims", "mechanisms", "candidates", "donated", "judged", "survivors",
              "independent_survivors", "compute_s")
    c = conn or R.connect()
    try:
        row = c.execute("SELECT * FROM source_yield WHERE source_id=?", (source_id,)).fetchone()
        cur = dict(row) if row is not None else {}
        vals = {k: _f(cur.get(k)) + _f(inc.get(k)) for k in fields}
        c.execute("INSERT OR REPLACE INTO source_yield(source_id, leads, claims, mechanisms, "
                  "candidates, donated, judged, survivors, independent_survivors, compute_s, "
                  "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (source_id, int(vals["leads"]), int(vals["claims"]), int(vals["mechanisms"]),
                   int(vals["candidates"]), int(vals["donated"]), int(vals["judged"]),
                   int(vals["survivors"]), int(vals["independent_survivors"]),
                   vals["compute_s"], _now()))
        c.commit()
    finally:
        if conn is None:
            c.close()


def _create_descendants(p: Pass, budget_s: float) -> dict[str, Any]:
    """Step 19. Section 29: a failure is EXPLOITED, not filed -- but only where the death
    JUSTIFIES a descendant. A cost-killed cell earns an execution variant; a cell with no effect
    anywhere earns nothing, and manufacturing a child for it is search waste wearing a lineage."""
    made: list[str] = []
    skipped: dict[str, int] = {}
    for r in p.verdicts:
        if int(r.get("survived") or 0) == 1:
            continue
        cls = str(r.get("failure_class") or "").upper()
        op = RM.FAILURE_DESCENDANT.get(cls)
        if op is None:
            key = cls or "UNCLASSIFIED"
            skipped[key] = skipped.get(key, 0) + 1
            continue
        if p.dry_run:
            made.append(f"dry-run:{r.get('id')}")
            continue
        parent = str(r.get("discovery_id") or "")
        # THE CHILD MUST BE A DIFFERENT OBJECT FROM ITS PARENT, or the registry's content hash
        # (source, mechanism, assets, rule) collapses it back onto the discovery the parent came
        # from and the descendant is silently never made. The rule carries the operator and the
        # parent's id: distinct per parent, and IDENTICAL across passes, so re-running this step
        # on the same verdict creates nothing twice.
        rule = (f"{op} of [{r.get('exact_rules') or r.get('mechanism') or ''}] "
                f"(parent candidate {r.get('id')})")
        did, created = R.record_discovery(
            source_id=str(r.get("source_id") or f"{RM.tag(p.mandate)}descendants"),
            source_type="descendant", mechanism=str(r.get("mechanism") or ""),
            exact_rule=rule,
            origin="MOAT", generator=f"{RM.tag(p.mandate)}descendants",
            parent_discovery_ids=[parent] if parent else [],
            actor=r.get("economic_actor"), constraint=r.get("constraint_text"),
            information=r.get("information"), assets=[str(r.get("symbol") or "")],
            economic_rationale=(f"{cls} on {r.get('symbol')}: the {op} transformation is the one "
                                f"this death justifies"),
            falsifier=str(r.get("falsifier") or ""),
            payload={"region": p.mandate.region, "operator": op, "failure_class": cls,
                     "parent_candidate": r.get("id")},
            conn=p.conn)
        if created:
            made.append(did)
    return {"outcome": OK if made else UNMEASURED, "descendants": len(made),
            "no_justified_descendant": skipped,
            "why": "" if made else "no judged region failure justified a descendant this pass"}


def _simplify(p: Pass, budget_s: float, report: Mapping[str, Any]) -> dict[str, Any]:
    """Step 20. Section 40: anti-complexity. What the region is carrying that it is not using --
    miners that produced nothing this pass and mechanisms with no candidate behind them."""
    idle = [r["name"] for r in p.miner_rows if int(r.get("discoveries") or 0) == 0]
    vocab = list(p.frontier.get("mechanism_vocabulary") or [])
    live = {RM.norm(s.get("mechanism")) for s in p.ranked}
    unused = [m for m in vocab if m not in live]
    return {"outcome": OK, "idle_miners": idle, "mechanisms_without_a_candidate": unused,
            "report_fields": len(report),
            "why": ("carrying a miner that produced nothing is a cost; carrying it while "
                    "reporting it as coverage is a lie, so both are named here")}


# --------------------------------------------------------------------------- the artifact
def _report(p: Pass) -> dict[str, Any]:
    """The pass's artifact, section 39's self-improvement block included."""
    m = p.mandate
    prefix = p.region.upper()
    registers = p.registers or RM.conversion_registers(m, conn=p.conn)
    front = p.frontier or RM.frontier(m, conn=p.conn)
    sat = RM.saturation(m, conn=p.conn)
    roi_src = RM.roi_by_source(m, conn=p.conn)
    rroi = RM.research_roi(m, conn=p.conn)
    dash = RM.dashboard(m, conn=p.conn, extra={"pass": p.n})
    debt_now = int(registers.get(f"{prefix}_UNEXPLAINED_DEBT") or 0)
    debt_was = p.cursor.get("unexplained_debt")
    survived = sum(1 for r in p.verdicts if int(r.get("survived") or 0) == 1)
    mechanisms = {RM.norm(r.get("mechanism")) for r in p.ranked}
    mechanisms.discard("unknown")
    return {
        "at": _now(), "region": p.region, "pass": p.n, "budget_s": p.budget_s,
        "steps": p.steps, "registers": registers,
        "frontier": {"by_state": front.get("by_state"), "n_cells": front.get("n_cells"),
                     "populated_share": front.get("populated_share"),
                     "truncated": bool((front.get("unmeasured") or {}).get("truncated")),
                     "evidence_outside_the_grid":
                         (front.get("unmeasured") or {}).get("evidence_outside_the_grid"),
                     "top_holes": RM.top_holes(front, 20)},
        "saturation": sat, "dashboard": dash, "roi_by_source": roi_src, "research_roi": rroi,
        "miners": [{k: r.get(k) for k in ("name", "kind", "budget_s", "seconds", "discoveries",
                                          "documents", "outcome", "overran_s", "why")}
                   for r in p.miner_rows],
        "self_improvement": {
            "compute_s": round(p.elapsed(), 3), "documents": p.documents,
            "novel_mechanisms": len(mechanisms),
            "valid_cells": registers.get(f"{prefix}_VALID_CELLS"),
            "duplicates": dash.get("duplicates"), "admissions": len(p.claims),
            "deaths": len(p.verdicts) - survived, "survivors": survived,
            "delta_n_eff": None, "research_roi": rroi.get("research_roi"),
            "unexplained_debt": debt_now,
            "debt_reduced": (None if debt_was is None else int(debt_was) - debt_now),
            "unmeasured": ["delta_n_eff: the portfolio's effective-bet counter is owned by the "
                           "allocator, not by a research department"],
        },
        "unmeasured": sorted(set(p.unmeasured)),
        "capital_authority": bool(m.capital_authority),
        "terminal_output": RM.TERMINAL_OUTPUT,
        "rule": RULE_47,
    }


def _append_loop(region: str, report: Mapping[str, Any]) -> Path:
    path = REGIONS / region / "loop.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    steps = report.get("steps") or []
    row = {"at": report.get("at"), "region": region, "pass": report.get("pass"),
           "seconds": report.get("seconds"),
           "ok": sum(1 for s in steps if s.get("outcome") == OK),
           "skipped": sum(1 for s in steps if s.get("outcome") == SKIPPED),
           "unmeasured": sum(1 for s in steps if s.get("outcome") == UNMEASURED),
           "failed": sum(1 for s in steps if s.get("outcome") == FAILED),
           "discoveries": sum(int(m.get("discoveries") or 0)
                              for m in (report.get("miners") or [])),
           "claims": (report.get("self_improvement") or {}).get("admissions"),
           "unexplained_debt": (report.get("self_improvement") or {}).get("unexplained_debt")}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
    return path


def _cursor_path(region: str) -> Path:
    return REGIONS / region / "cursor.json"


def _read_cursor(region: str) -> dict[str, Any]:
    doc = _read_json(_cursor_path(region))
    return doc if isinstance(doc, dict) else {}


def _write_cursor(region: str, p: Pass, report: Mapping[str, Any]) -> None:
    judged = [str(r.get("judged_at") or "") for r in p.verdicts]
    last = max(judged) if judged else str(p.cursor.get("last_judged_at") or "")
    _write_atomic(_cursor_path(region),
                  {"at": _now(), "pass": p.n + 1, "last_judged_at": last,
                   "unexplained_debt": (report.get("self_improvement") or {}
                                        ).get("unexplained_debt")})


# --------------------------------------------------------------------------- the CLI
def summary_lines(report: Mapping[str, Any]) -> list[str]:
    si = report.get("self_improvement") or {}
    out = [f"region {report.get('region')} pass {report.get('pass')} in "
           f"{report.get('seconds')}s: {si.get('documents')} document(s), "
           f"{si.get('novel_mechanisms')} mechanism(s), {si.get('valid_cells')} valid cell(s), "
           f"{si.get('admissions')} claim(s), debt {si.get('unexplained_debt')}"]
    for s in report.get("steps") or []:
        mark = {OK: " ", SKIPPED: "-", UNMEASURED: "?", FAILED: "!"}.get(str(s.get("outcome")), "?")
        out.append(f" {mark} {s.get('n'):>2} {s.get('step')!s:<26} "
                   f"{s.get('outcome'):<10} {s.get('seconds')}s "
                   f"{str(s.get('why') or '')[:70]}")
    for u in report.get("unmeasured") or []:
        out.append(f"  UNMEASURED {u}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--region", required=True, help="the region package under research/")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no artifact, no registry row, no claim")
    a = ap.parse_args(argv)
    region = str(a.region).strip().lower()
    try:
        mandate, miners = load_region(region)
    except RegionMissing as exc:
        print(f"region {region}: {exc}", file=sys.stderr)
        return 2
    problems = RM.validate(mandate)
    if problems:
        print(f"region {region}: the mandate does not validate ({len(problems)} problem(s)):",
              file=sys.stderr)
        for pr in problems[:20]:
            print(f"  {pr}", file=sys.stderr)
        return 1
    n = int(_read_cursor(region).get("pass") or 1)
    while True:
        report = run_pass(region, mandate, miners, budget_s=float(a.budget_s),
                          dry_run=bool(a.dry_run), n=n)
        for line in summary_lines(report):
            print(line)
        print("dry run -- nothing written" if a.dry_run
              else f"-> {REPORTS / f'REGION_{region.upper()}.json'}")
        if a.once:
            return 0
        n += 1


if __name__ == "__main__":
    raise SystemExit(main())
