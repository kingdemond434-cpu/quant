"""THE SANDBOX RUNNER -- the federation's execution layer (LAWS 5h/5m), hourly.

Each hour, inside its budget, this leg picks the highest-ROI RUNNABLE systems -- upstream
research engines through their adapters (`libs/research/adapters/`) and the desk's own rebuilt
cells (`research/sandboxes/`) -- and runs them over ONE read-only ResearchBundle built from the
desk's own point-in-time bars (`data/universe/*.parquet`, closed bars only, never a network).
Adapters execute in their per-system sandbox (`libs.research.sandbox`: scrubbed environment,
work directory outside the desk tree, hard timeout, inputs copied never mounted); cells are desk
code and run in-process under the same bundle and the same exit.

THE EXIT IS ONE SHAPE. Every run leaves an ExternalResearchPacket; the runner converts it:
candidates -> `libs.moat.registry.enqueue_candidate` with provenance (system, version, licence,
disposition, run, commit) and a trial family; representations, mechanisms, datasets and research
methods -> `record_discovery` rows the compiler and the deepening worker read; the packet's
`trials_charged` -> effective trials through `libs.research.trial_ledger.census` and the
lifetime ledger `data/sandbox_trials.jsonl`. A verdict-shaped field raises at the packet
boundary and the run is recorded REJECTED_WITH_EVIDENCE.

WHAT NEVER CRASHES THE HOUR. A library that is not importable is recorded UNMEASURED with an
INSTALL TASK row (the pinned requirement, the venv command); an unread licence is read through
`licence_reader` when fetching is allowed and otherwise recorded as a LICENCE TASK; a system
whose disposition is REBUILT and has no cell is a REBUILT TASK; a packet that carries only text
(no candidate, representation, mechanism or dataset) is TEXT_ONLY, which is never a resting
state -- it gets a REBUILT task row on the same pass. Allocation is `external_federation.
allocation`: ROI-proportional with a floor, so no frontier is switched off for one bad week.

ARTIFACT `reports/SANDBOX_RUNNER.json`: systems tried (status, disposition, licence, version,
seconds, counts), packets, candidates enqueued, the UNMEASURED list with its tasks, ROI per
system, and the allocation. CONSUMERS: `research/federation_ops.py` (reads `<sandbox>/
sandbox.json`, `out/*.json` and the processed packet archive for its twins and dashboard), the
registry queue (`external_gauntlet` claims the candidates), and `research/dislocation_lab.py`
(the conformal cell's calibration file).
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import adapters as A  # noqa: E402
from libs.research import external_federation as fed  # noqa: E402
from libs.research import licence_reader as LR  # noqa: E402
from libs.research import sandbox as SB  # noqa: E402
from libs.research import sandbox_rotation as ROT  # noqa: E402
from libs.research import trial_ledger as T  # noqa: E402
from libs.research.external_federation import ExternalResearchPacket  # noqa: E402
from research import sandboxes as CELLS  # noqa: E402

UNMEASURED = "UNMEASURED"
GENERATOR = "sandbox_runner"
REPORT = DESK / "reports" / "SANDBOX_RUNNER.json"
STATE = DESK / "data" / "sandbox_runner_state.json"
TRIALS = DESK / "data" / "sandbox_trials.jsonl"
FED_STATE = DESK / "data" / "external_federation.json"
PROCESSED = DESK / "data" / "external_packets" / "processed"
UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE_REGISTRY = UNIVERSE_DIR / "universe.json"
#: The bundle's core: the book's instruments first, then a rotation through the hypothesis lane.
CORE_SYMBOLS: tuple[str, ...] = ("XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "US500", "XAGUSD",
                                 "AUDUSD", "USDCAD")
ROTATION_EXTRA = 2
MAX_LICENCE_READS = 3
MAX_DISCOVERIES_PER_PACKET = 40
FLOOR_S = 30
MIN_BARS_FOR_SYSTEM = 300
LAW = ("LAWS 5h: run research code aggressively in sandboxes; never give it live authority. An "
       "external engine is a researcher, never a validator, never a capital authority.")
CONSUMERS = ("research/federation_ops.py (sandbox.json, out/*.json, the processed packet "
             "archive)", "libs/moat/registry.py research_candidates -> external_gauntlet",
             "research/dislocation_lab.py (reports/SANDBOX_CONFORMAL.json)")


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _safe(name: str) -> str:
    """A run id as a file name: the cell prefix's colon is illegal on NTFS."""
    return "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in name)


def free_phys_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped]
        return float(psutil.virtual_memory().available) / (1024 * 1024)
    except Exception:
        return None


def bars_cap(free_mb: float | None) -> int:
    """How many H1 bars per symbol the bundle carries, DERIVED from measured free memory (two
    bars per free MB, floored at 600 and capped at 4000); an unreadable counter gives the floor.
    Never sized off a machine's nominal RAM."""
    if free_mb is None:
        return 600
    return int(min(4000, max(600, free_mb * 2)))


# ------------------------------------------------------------------------------- the bundle

def lane_ok(symbol: str, registry: dict[str, Any]) -> bool:
    """HYPOTHESIS lane only: the two-lane order routes by asset class; equities never enter."""
    try:
        from research import universe_policy as UP
        return bool(UP.may_hypothesise(symbol))
    except Exception:
        row = registry.get(symbol) or {}
        klass = str(row.get("asset_class") or "").lower()
        return bool(klass) and "equit" not in klass


def _frame_from_parquet(symbol: str, path: Path, n_bars: int, cutoff: datetime
                        ) -> A.BarFrame | None:
    try:
        import pandas as pd
        df = pd.read_parquet(path, columns=["open", "high", "low", "close", "tick_volume"])
    except Exception:
        return None
    if df.empty:
        return None
    with contextlib.suppress(TypeError):
        df = df[df.index < cutoff]
    df = df.tail(n_bars)
    if df.empty:
        return None
    times = tuple(t.isoformat() for t in df.index.to_pydatetime())
    return A.BarFrame(symbol, "H1", times, tuple(float(x) for x in df["open"]),
                      tuple(float(x) for x in df["high"]), tuple(float(x) for x in df["low"]),
                      tuple(float(x) for x in df["close"]),
                      tuple(float(x) for x in df["tick_volume"]))


def build_bundle(*, universe_dir: Path = UNIVERSE_DIR, registry_path: Path = UNIVERSE_REGISTRY,
                 n_bars: int = 2000, seed: int = 0, budget_s: int = 300,
                 symbols: list[str] | None = None) -> A.ResearchBundle:
    """The read-only bundle: closed H1 bars for the book's core plus a rotation, the cost
    surface from the universe registry, the desk's question and the compute budget."""
    registry = _read(registry_path, {}) or {}
    available = {p.stem[:-3] for p in universe_dir.glob("*_H1.parquet")}
    if symbols:
        chosen = [s for s in symbols if s in available]
    else:
        chosen = [s for s in CORE_SYMBOLS if s in available and lane_ok(s, registry)]
        pool = sorted(s for s in available if s not in chosen and lane_ok(s, registry))
        if pool:
            start = seed % len(pool)
            chosen += [pool[(start + i) % len(pool)] for i in range(min(ROTATION_EXTRA,
                                                                        len(pool)))]
    cutoff = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    bars: dict[str, A.BarFrame] = {}
    for s in chosen:
        f = _frame_from_parquet(s, universe_dir / f"{s}_H1.parquet", n_bars, cutoff)
        if f is not None and len(f) >= MIN_BARS_FOR_SYSTEM:
            bars[f.key] = f
    costs: dict[str, A.CostRow] = {}
    for frame in bars.values():
        row = registry.get(frame.symbol) or {}
        costs[frame.symbol] = A.CostRow(frame.symbol, float(row.get("tick_size") or 0.0),
                                    float(row.get("contract_size") or 0.0),
                                    float(row.get("median_spread_pts")
                                          or row.get("spread_pts_at_collection")
                                          or float("nan")))
    universe = tuple(f.symbol for f in bars.values())
    watermark = max((f.time[-1] for f in bars.values()), default="")
    return A.ResearchBundle(
        bundle_id=f"desk-{watermark[:13].replace(':', '') or 'empty'}-{seed}", built_at=now(),
        question="what price-only structure in these instruments is a hypothesis the ten gates "
                 "have not yet judged", compute_budget_s=int(budget_s), seed=int(seed),
        horizons=("4h", "24h"), universe=universe, bars=bars, costs=costs,
        provenance={"source": "desks/mt5/data/universe/*_H1.parquet (closed bars only, cutoff "
                              f"{cutoff.isoformat()})", "n_bars_cap": n_bars,
                    "lane": "HYPOTHESIS (universe_policy); equities never enter",
                    "network": "none: the bundle is the only input a run receives"})


# ------------------------------------------------------------------------------- the roster

def fed_rows(state: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (state or {}).get("systems") if isinstance(state, dict) else None
    return {str(k): dict(v) for k, v in (rows or {}).items() if isinstance(v, dict)}


def adapter_systems() -> list[str]:
    """Every adapter module in the package, whether or not its upstream imports here."""
    pkg = Path(A.__file__).parent
    return sorted(p.stem for p in pkg.glob("*.py") if p.stem != "__init__" and p.stem in A.SPECS)


def _system(sid: str, row: dict[str, Any]) -> fed.ExternalSystem:
    base = fed.SEED_BY_ID.get(sid)
    if base is None:
        spec = A.SPECS.get(sid)
        base = fed.ExternalSystem(sid, sid, f"public:{sid}", "adapter-only system", "DIRECT",
                                  (A.FAMILY_OF.get(sid, "data_tooling"),), ("representation",),
                                  notes=spec.note if spec else "")
    licence = str(row.get("licence") or base.licence or "UNVERIFIED")
    return dataclasses.replace(base, licence=licence)


@dataclasses.dataclass
class Plan:
    system_id: str
    kind: str                      # adapter | cell | own
    status: str                    # RUNNABLE | UNMEASURED | REFUSED | REBUILT_ROUTE | WRAPPED_API
    disposition: str
    licence: str
    version: str
    requirement: str
    why: str = ""
    task: dict[str, Any] | None = None
    module: Any = None
    system: fed.ExternalSystem | None = None

    def record(self) -> dict[str, Any]:
        return {"system_id": self.system_id, "kind": self.kind, "status": self.status,
                "disposition": self.disposition, "licence": self.licence,
                "version": self.version, "requirement": self.requirement, "why": self.why,
                "task": self.task}


def plan_adapter(sid: str, row: dict[str, Any], *, root: Path, allow_fetch: bool,
                 licence_reads: list[dict[str, Any]], deadline_left: float,
                 shared: dict[str, str] | None = None) -> Plan:
    spec = A.SPECS[sid]
    shared = SB.shared_modules(root) if shared is None else shared
    system = _system(sid, row)
    version = spec.version or UNMEASURED
    try:
        module = __import__(f"libs.research.adapters.{sid}", fromlist=["run"])
    except Exception as exc:
        return Plan(sid, "adapter", "UNMEASURED", "UNDISPOSED", system.licence, version,
                    spec.requirement, f"adapter import failed: {type(exc).__name__}: {exc}"[:200],
                    {"kind": "fix_adapter", "system": sid})
    if bool(getattr(module, "RUNS_WITHOUT_LIBRARY", False)):
        return Plan(sid, "own", "RUNNABLE", "REBUILT", "desk (own code)", A.commit_of(sid),
                    "", "REBUILT method in desk code; runs in-process", module=module,
                    system=system)
    disposition = str(row.get("disposition") or "")
    if disposition not in fed.RUNNING_DISPOSITIONS:
        disposition = system.integration if system.integration in fed.RUNNING_DISPOSITIONS \
            else "WRAPPED"
    if disposition == "REBUILT":
        return Plan(sid, "adapter", "REBUILT_ROUTE", disposition, system.licence, version,
                    spec.requirement, "rostered REBUILT: upstream code never runs here",
                    {"kind": "rebuilt", "system": sid, "what": f"reproduce {sid}'s mechanism as "
                                                                "a cell under research/"
                                                                "sandboxes/",
                     "covered_by": [c for c in CELLS.CELLS if sid in tuple(getattr(
                         CELLS.load_cell(c), "UPSTREAM", ()))]},
                    module=module, system=system)
    box = SB.Sandbox(sid, root / sid)
    venv = SB.venv_python(box)
    #: Three ways the upstream can be reachable, cheapest first: importable in THIS process, the
    #: shared venv the provisioner filled (`sandbox_provision.py`), or a per-system venv.
    in_shared = sid in shared
    available = (A.library(spec.module) is not None) if spec.module else False
    if not available and not in_shared and not venv.exists():
        cmd = (f"python desks/mt5/research/sandbox_provision.py --once --only {sid}"
               if spec.version
               else f"pin {sid}'s commit/wheel first (no wheel resolved on this interpreter)")
        return Plan(sid, "adapter", "UNMEASURED", disposition, system.licence, version,
                    spec.requirement, f"{spec.module or sid} is not importable here and no "
                                      f"sandbox venv exists", {"kind": "install", "system": sid,
                                                                "requirement": spec.requirement,
                                                                "weight": spec.weight,
                                                                "how": cmd},
                    module=module, system=system)
    why = SB.refuse_reason(system, disposition)
    if why and "licence has not been read" in why and allow_fetch \
            and len(licence_reads) < MAX_LICENCE_READS and deadline_left > 60:
        reading = LR.read(system, root=root)
        LR.apply(row, reading)
        disp2, dwhy = LR.dispose(system, reading)
        licence_reads.append({"system": sid, **reading.record(), "disposition": disp2,
                              "why": dwhy})
        if reading.read:
            row["disposition"], row["why"] = disp2, dwhy
            system = dataclasses.replace(system, licence=reading.licence)
            disposition = disp2 if disp2 in fed.RUNNING_DISPOSITIONS else disposition
            why = SB.refuse_reason(system, disposition)
    if why:
        kind = "licence" if "licence" in why else "host"
        return Plan(sid, "adapter", "REFUSED", disposition, system.licence, version,
                    spec.requirement, why, {"kind": kind, "system": sid,
                                            "how": ("licence_reader.read at the pin (allowed when "
                                                    "the pass may fetch)" if kind == "licence"
                                                    else "pin the repository on an allowlisted "
                                                         "host")},
                    module=module, system=system)
    return Plan(sid, "adapter", "RUNNABLE", disposition, system.licence, version,
                spec.requirement, "library importable" if available else f"venv {venv}",
                module=module, system=system)


def plan_cells() -> list[Plan]:
    out = []
    for name in CELLS.CELLS:
        try:
            module = CELLS.load_cell(name)
        except Exception as exc:
            out.append(Plan(CELLS.system_id(name), "cell", "UNMEASURED", "REBUILT",
                            "desk (own code)", A.commit_of(A.CELL_PREFIX + name), "",
                            f"cell import failed: {type(exc).__name__}: {exc}"[:200],
                            {"kind": "fix_cell", "cell": name}))
            continue
        d = CELLS.describe(module)
        out.append(Plan(d["name"], "cell", "RUNNABLE", "REBUILT", d["licence"],
                        A.commit_of(d["name"]), "", f"fallback: {d['fallback']}; upstream "
                                                    f"available: {d['upstream_available']}",
                        module=module))
    return out


# ------------------------------------------------------------------------------- running

def stage_adapter(box: SB.Sandbox, sid: str, bundle: A.ResearchBundle) -> tuple[Path, list[str]]:
    """Copy the adapter package (import-light by contract) and the bundle into the work dir."""
    pkg = Path(A.__file__).parent
    files = {"libs/__init__.py": ROOT / "libs" / "__init__.py",
             "libs/research/__init__.py": ROOT / "libs" / "research" / "__init__.py",
             "libs/research/external_federation.py": ROOT / "libs" / "research"
             / "external_federation.py",
             "libs/research/adapters/__init__.py": pkg / "__init__.py",
             f"libs/research/adapters/{sid}.py": pkg / f"{sid}.py"}
    staged = SB.stage(box, files)
    manifest = A.write_bundle(bundle, box.work / "bundle")
    return manifest, staged


def run_adapter(plan: Plan, bundle: A.ResearchBundle, *, root: Path, timeout_s: int,
                dry_run: bool) -> tuple[ExternalResearchPacket, dict[str, Any]]:
    sid = plan.system_id
    assert plan.system is not None
    box = SB.provision(plan.system, plan.disposition, root=root, dry_run=dry_run)
    meta: dict[str, Any] = {"sandbox": box.record(), "seconds": 0.0}
    if not box.provisioned:
        return A.unmeasured(sid, bundle, f"not provisioned: {box.why}"), meta
    manifest, staged = stage_adapter(box, sid, bundle)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    out = box.out / f"{sid}-{stamp}.json"
    venv = SB.venv_python(box)
    shared = SB.shared_python(root)
    #: The system's own venv wins; then the shared one the provisioner fills; the desk's
    #: interpreter is the last resort (it is the right answer only for a pure-stdlib adapter).
    python = str(venv) if venv.exists() else (str(shared) if shared.exists()
                                              else sys.executable)
    argv = [python, "-m", f"libs.research.adapters.{sid}", "--bundle", str(manifest),
            "--out", str(out)]
    res = SB.run(box, argv, timeout_s=max(10, timeout_s))
    meta.update({"seconds": res.seconds, "returncode": res.returncode, "run": res.why,
                 "stdout_tail": list(res.stdout_tail[-5:]), "staged": staged,
                 "python": python, "out": str(out)})
    if out.exists():
        try:
            pkt = SB.packet(box, out)
        except (TypeError, ValueError) as exc:
            meta["rejected"] = str(exc)[:300]
            return A.unmeasured(sid, bundle, f"REJECTED_WITH_EVIDENCE: {exc}"[:300]), meta
    else:
        pkt = A.unmeasured(sid, bundle, f"no packet written: {res.why}; "
                                       + " | ".join(res.stdout_tail[-2:])[:300])
    with contextlib.suppress(OSError):
        _write(box.root / "sandbox.json", {**box.record(), "last_run": {
            "at": now(), "run_id": pkt.run_id, "seconds": res.seconds, "ok": res.ok,
            "why": res.why, "counts": pkt.counts()}})
    return pkt, meta


def run_in_process(plan: Plan, bundle: A.ResearchBundle, *, root: Path, ctx: CELLS.CellContext
                   ) -> tuple[ExternalResearchPacket, dict[str, Any]]:
    """Cells and REBUILT-in-desk-code adapters: in-process, guarded, packet written where
    federation_ops reads it."""
    t0 = time.monotonic()
    sid = plan.system_id
    if plan.kind == "cell":
        pkt = CELLS.run_cell(sid[len(A.CELL_PREFIX):], bundle, ctx)
    else:
        try:
            pkt = plan.module.run(bundle)
        except Exception as exc:
            pkt = A.unmeasured(sid, bundle, f"adapter raised: {type(exc).__name__}: {exc}"[:300])
    seconds = round(time.monotonic() - t0, 1)
    folder = root / sid.replace(":", "_")
    meta: dict[str, Any] = {"seconds": seconds, "in_process": True, "folder": str(folder)}
    if not ctx.dry_run:
        with contextlib.suppress(OSError):
            (folder / "out").mkdir(parents=True, exist_ok=True)
            _write(folder / "out" / f"{_safe(pkt.run_id)}.json", A.to_dict(pkt))
            _write(folder / "sandbox.json", {"system_id": sid, "commit": pkt.commit,
                                             "licence": plan.licence, "provisioned": True,
                                             "in_process": True, "why": plan.why,
                                             "last_run": {"at": now(), "run_id": pkt.run_id,
                                                          "seconds": seconds,
                                                          "counts": pkt.counts()}})
    return pkt, meta


# ------------------------------------------------------------------------------- ingestion

#: Research-method rows that are ROUTES or NOTES rather than measurements. A packet made only of
#: these is TEXT_ONLY: the system said something and measured nothing, which is never a resting
#: state (LAWS 5h) -- it gets a REBUILT task on the same pass.
ROUTE_KINDS: frozenset[str] = frozenset({"REBUILT_ROUTE", "WRAPPED_ROUTE", "api_surface",
                                         "calibration_feed", "note", "text"})


def is_text_only(pkt: ExternalResearchPacket) -> bool:
    substantive = bool(pkt.candidates or pkt.representations or pkt.mechanisms or pkt.datasets)
    if substantive:
        return False
    rows = [r for r in pkt.research_methods if str(r.get("kind")) != UNMEASURED]
    return bool(rows) and all(str(r.get("kind")) in ROUTE_KINDS for r in rows)


def ingest(pkt: ExternalResearchPacket, plan: Plan, *, compute_s: float, conn: Any,
           apply: bool) -> dict[str, Any]:
    out: dict[str, Any] = {"candidates": 0, "created": 0, "existing": 0, "unregistered": 0,
                           "discoveries": 0, "trials": []}
    prov = {"system": plan.system_id, "version": plan.version, "licence": plan.licence,
            "disposition": plan.disposition, "run_id": pkt.run_id, "commit": pkt.commit,
            "trials_charged": pkt.trials_charged, "authority": "researcher only; the gauntlet "
                                                                "judges"}
    n_c = max(1, len(pkt.candidates))
    for row in pkt.candidates:
        family = str(row.get("family") or "")
        symbols = [str(s) for s in (row.get("symbols") or [])]
        if family not in A.FAMILIES or not symbols:
            out["unregistered"] += 1
            continue
        ev_raw = row.get("evidence")
        ev: dict[str, Any] = dict(ev_raw) if isinstance(ev_raw, dict) else {}
        p_raw = ev.get("parameters")
        params: dict[str, Any] = dict(p_raw) if isinstance(p_raw, dict) else {}
        text = str(row.get("text") or "")
        horizon = str(row.get("horizon") or "")
        for sym in symbols:
            out["candidates"] += 1
            trial = T.Trial(f"{pkt.run_id}:{family}:{sym}", family,
                            {"symbol": sym, "horizon": horizon, "mechanism": plan.system_id,
                             "method": plan.system_id}, dict(params),
                            max(1, pkt.trials_charged // n_c))
            out["trials"].append(trial)
            if not apply:
                continue
            try:
                _cid, created = R.enqueue_candidate(
                    family=family, symbol=sym, params=dict(params), origin="EXTERNAL",
                    mechanism=text[:240], generator=f"sandbox:{plan.system_id}",
                    source_id=f"sandbox:{plan.system_id}", horizon=horizon,
                    information="external_engine", exact_rules=text,
                    causal_rationale=text[:400], lineage={**prov, "evidence": ev},
                    trial_family=f"ext:{plan.system_id}:{family}",
                    research_cost=float(compute_s), department="intel",
                    transformation="sandbox_packet", conn=conn)
            except Exception as exc:
                out.setdefault("errors", []).append(f"{sym}/{family}: {type(exc).__name__}: "
                                                    f"{exc}"[:160])
                continue
            out["created" if created else "existing"] += 1
    n_disc = 0
    for group in ("representations", "mechanisms", "datasets", "research_methods"):
        for row in getattr(pkt, group):
            if str(row.get("kind")) == UNMEASURED or n_disc >= MAX_DISCOVERIES_PER_PACKET:
                continue
            n_disc += 1
            if not apply:
                continue
            syms = row.get("symbols") or ([row["symbol"]] if row.get("symbol") else [])
            with contextlib.suppress(Exception):
                R.record_discovery(source_id=f"sandbox:{plan.system_id}",
                                   source_type="external_system",
                                   mechanism=f"{group}:{row.get('kind')}", origin="EXTERNAL",
                                   generator=GENERATOR, assets=list(syms), information=group,
                                   payload={**row, "provenance": prov}, conn=conn)
    out["discoveries"] = n_disc
    return out


def charge_trials(trials: list[Any], *, apply: bool) -> dict[str, Any]:
    if not trials:
        return {"n_raw": 0, "n_effective": 0.0}
    census = T.census(trials)
    doc = census.to_dict()
    if apply:
        try:
            TRIALS.parent.mkdir(parents=True, exist_ok=True)
            with TRIALS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": now(), "n_raw": census.n_raw,
                                     "n_effective": round(census.n_effective, 3),
                                     "families": sorted(census.families)},
                                    separators=(",", ":")) + "\n")
        except OSError as exc:
            doc["ledger_error"] = f"{type(exc).__name__}: {exc}"
    return doc


# ------------------------------------------------------------------------------- the pass

def run_pass(*, budget_s: float = 900.0, dry_run: bool = False, allow_fetch: bool = True,
             allow_network: bool = False, root: Path | None = None,
             symbols: list[str] | None = None, max_systems: int | None = None,
             fed_state_path: Path = FED_STATE, state_path: Path = STATE,
             report_path: Path = REPORT, processed: Path = PROCESSED,
             universe_dir: Path = UNIVERSE_DIR, registry_path: Path = UNIVERSE_REGISTRY,
             only: list[str] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = A.Deadline(max(10.0, budget_s * 0.9))
    root = root or SB.SANDBOX_ROOT
    state = _read(state_path, {}) or {}
    state.setdefault("systems", {})
    fed_state = _read(fed_state_path, {}) or {}
    rows = fed_rows(fed_state)
    free_mb = free_phys_mb()
    seed = int(datetime.now(tz=UTC).strftime("%Y%m%d%H"))
    bundle = build_bundle(universe_dir=universe_dir, registry_path=registry_path,
                          n_bars=bars_cap(free_mb), seed=seed, budget_s=int(budget_s),
                          symbols=symbols)
    licence_reads: list[dict[str, Any]] = []
    plans: list[Plan] = []
    for sid in adapter_systems():
        if only and sid not in only:
            continue
        row = rows.setdefault(sid, {})
        plans.append(plan_adapter(sid, row, root=root, allow_fetch=allow_fetch and not dry_run,
                                  licence_reads=licence_reads, deadline_left=deadline.left()))
    plans.extend(p for p in plan_cells() if not only or p.system_id in only
                 or p.system_id[len(A.CELL_PREFIX):] in only)
    runnable = [p for p in plans if p.status == "RUNNABLE"]
    #: ROTATION (libs/research/sandbox_rotation.py). Pure ROI order is a ratchet -- the systems
    #: that produced get the hour, so the ones that never got an hour never produce. The plan
    #: gives the most OVERDUE runnable systems a floor share first (every one runs inside the
    #: 24h window) and spends the rest ROI-proportionally REWEIGHTED by measured marginal
    #: breadth, so orthogonal cells buy more of the hour than a crowded corner does.
    rotation = ROT.plan([p.system_id for p in runnable], state["systems"],
                        budget_s=max(1.0, deadline.left()), floor_s=FLOOR_S) if runnable else {}
    alloc = {str(k): int(v) for k, v in (rotation.get("shares") or {}).items()}
    _rot_rank = {sid: i for i, sid in enumerate(rotation.get("order") or [])}
    order = sorted(runnable, key=lambda p: (_rot_rank.get(p.system_id, 10 ** 6), p.system_id))
    # THE PROPOSER SEAT, OPTIONAL: which sandboxed SYSTEM is worth this pass's seconds first.
    # An ORDER over the systems the federation already holds and the allocator already funded --
    # the seat may reorder what runs, never add a system, never change an allocation and never
    # judge a packet. Every cell still runs in the same sandbox under the same licence reads,
    # and a name the model invents is discarded. No panel, no call, order unchanged.
    seat_hint: dict[str, Any] = {"verdict": "UNMEASURED"}
    try:
        from libs.research import proposer_seat as _ps
        _ids = [p.system_id for p in order]
        _reply = _ps.ask("sandbox_runner", "order", options=_ids,
                         task=("Order these external research systems by which is most likely to "
                               "produce a NEW testable candidate against hourly FX, metals and "
                               "index bars this pass. Return the full list, best first."))
        seat_hint = _reply.to_row()
        if _reply.measured and _reply.ordered != _ids:
            _rank = {n: i for i, n in enumerate(_reply.ordered)}
            order = sorted(order, key=lambda p: _rank.get(p.system_id, 10 ** 6))
    except Exception as _exc:                             # pragma: no cover - optional seat
        seat_hint = {"verdict": "UNMEASURED", "why": f"{type(_exc).__name__}: {_exc}"}
    #: The seat may reorder the EXPLOIT lane; the SCOUT lane is ordered by age alone and is
    #: pinned back to the front afterwards. A model's opinion may not starve a frontier -- that
    #: is exactly the ratchet the rotation exists to break (L1.32).
    _scouts = {str(s) for s in (rotation.get("scouts") or [])}
    if _scouts:
        order = ([p for p in order if p.system_id in _scouts]
                 + [p for p in order if p.system_id not in _scouts])
    if max_systems:
        order = order[:max_systems]
    conn = None if dry_run else R.connect()
    tried: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    all_trials: list[Any] = []
    totals = {"candidates": 0, "created": 0, "existing": 0, "unregistered": 0, "discoveries": 0}
    text_only: list[str] = []
    skipped_budget: list[str] = []
    try:
        for plan in order:
            if deadline.expired() or not bundle.bars:
                skipped_budget.append(plan.system_id)
                continue
            share = int(min(alloc.get(plan.system_id, FLOOR_S), deadline.left()))
            run_bundle = dataclasses.replace(bundle, compute_budget_s=max(10, share))
            ctx = CELLS.CellContext(DESK, budget_s=max(10, share), seed=seed,
                                    network_allowed=allow_network, dry_run=dry_run,
                                    reference_engines=not dry_run)
            if plan.kind == "adapter":
                pkt, meta = run_adapter(plan, run_bundle, root=root, timeout_s=share,
                                        dry_run=dry_run)
            else:
                pkt, meta = run_in_process(plan, run_bundle, root=root, ctx=ctx)
            seconds = float(meta.get("seconds") or 0.0)
            ing = ingest(pkt, plan, compute_s=seconds, conn=conn, apply=not dry_run)
            all_trials.extend(ing.pop("trials"))
            for k in totals:
                totals[k] += int(ing.get(k) or 0)
            unmeasured = A.is_unmeasured(pkt)
            status = ("UNMEASURED" if unmeasured else "TEXT_ONLY" if is_text_only(pkt)
                      else "PRODUCED")
            if status == "TEXT_ONLY":
                text_only.append(plan.system_id)
                plan.task = {"kind": "rebuilt", "system": plan.system_id,
                             "what": "the packet carried text only: rebuild the mechanism as a "
                                     "cell that yields candidates or representations"}
            #: A MEASURED research method is a donation like any other and was worth ZERO here
            #: until 2026-09-23: `cell:rl_execution_challenger` donated a learned execution
            #: policy and three QUBO schedules every pass, scored information_gain 0.0, and so
            #: read ROI 0.0 and sank to the bottom of every allocation it was in. Route/note rows
            #: (`ROUTE_KINDS`) still count nothing -- those are the TEXT_ONLY case.
            _methods = sum(1 for r in pkt.research_methods
                           if str(r.get("kind")) not in ROUTE_KINDS
                           and str(r.get("kind")) != UNMEASURED)
            gain = (len(pkt.candidates) + 0.5 * (len(pkt.representations) + len(pkt.mechanisms)
                                                 + _methods)
                    + len(pkt.datasets))
            s_row = state["systems"].setdefault(plan.system_id, {})
            s_row.update({"runs": int(s_row.get("runs") or 0) + 1,
                          "compute_spent": float(s_row.get("compute_spent") or 0.0) + seconds,
                          "information_gain": float(s_row.get("information_gain") or 0.0) + gain,
                          "candidates": int(s_row.get("candidates") or 0) + len(pkt.candidates),
                          "last_run_id": pkt.run_id, "last_status": status, "last_at": now()})
            s_row["roi"] = fed.roi({**s_row, "live_delta_elog": None})
            #: THE CELLS THIS SYSTEM REACHES, kept so breadth can be MEASURED rather than
            #: asserted: one (family|symbol|horizon) key per candidate that entered the queue,
            #: de-duplicated, capped. `sandbox_rotation.breadth` turns these rows into the
            #: effective rank of the federation and each system's marginal contribution to it.
            _cells = {ROT.cell_key(c.get("family"), sym, c.get("horizon"))
                      for c in pkt.candidates for sym in (c.get("symbols") or [])}
            s_row["cells"] = sorted(set(s_row.get("cells") or []) | _cells)[:ROT.MAX_CELLS]
            record = {**plan.record(), "run_status": status, "seconds": seconds,
                      "counts": pkt.counts(), "ingested": ing, "budget_share_s": share,
                      "meta": {k: v for k, v in meta.items() if k != "sandbox"},
                      "why_unmeasured": (next((str(r.get("why")) for r in pkt.research_methods
                                               if str(r.get("kind")) == UNMEASURED), "")
                                         if unmeasured else "")}
            tried.append(record)
            packets.append({"run_id": pkt.run_id, "system_id": pkt.system_id,
                            "commit": pkt.commit, "counts": pkt.counts(), "status": status})
            if not dry_run:
                with contextlib.suppress(OSError):
                    _write(processed / f"{_safe(pkt.run_id)}.json",
                           {**A.to_dict(pkt), "compute_s": seconds, "scheduled_by":
                            "hourly_cycle:sandbox_runner", "at": now(), "variant": "integrated"})
    finally:
        if conn is not None:
            conn.close()
    for plan in plans:
        if plan.status != "RUNNABLE":
            tried.append({**plan.record(), "run_status": plan.status, "seconds": 0.0,
                          "counts": {}, "ingested": {}, "budget_share_s": 0})
    census = charge_trials(all_trials, apply=not dry_run)
    unmeasured_list = [{"system_id": r["system_id"], "why": r.get("why_unmeasured") or r["why"],
                        "task": r.get("task")} for r in tried
                       if r["run_status"] in ("UNMEASURED", "REFUSED", "REBUILT_ROUTE",
                                              "WRAPPED_API")]
    doc = {
        "at": now(), "seconds": round(time.monotonic() - t0, 1), "budget_s": budget_s,
        "dry_run": dry_run, "law": LAW, "generator": GENERATOR,
        "bundle": {"bundle_id": bundle.bundle_id, "universe": list(bundle.universe),
                   "n_frames": len(bundle.bars), "watermark": bundle.watermark(),
                   "digest": bundle.digest(), "n_bars_cap": bars_cap(free_mb),
                   "free_phys_mb": free_mb, "provenance": dict(bundle.provenance)},
        "allocation_s": alloc, "proposer_seat": seat_hint,
        "rotation": rotation,
        "systems_tried": tried, "packets": packets,
        "candidates": totals, "effective_trials": census,
        "text_only": text_only, "skipped_budget": skipped_budget,
        "unmeasured": unmeasured_list,
        "install_tasks": [r["task"] for r in tried if (r.get("task") or {}).get("kind")
                          == "install"],
        "licence_tasks": [r["task"] for r in tried if (r.get("task") or {}).get("kind")
                          in ("licence", "host")],
        "rebuilt_tasks": [r["task"] for r in tried if (r.get("task") or {}).get("kind")
                          == "rebuilt"],
        "licence_reads": licence_reads,
        "roi": {sid: {"roi": s.get("roi"), "runs": s.get("runs"),
                      "compute_spent": s.get("compute_spent"),
                      "information_gain": s.get("information_gain"),
                      "candidates": s.get("candidates"), "last_status": s.get("last_status")}
                for sid, s in sorted(state["systems"].items())},
        "counts": {"plans": len(plans), "runnable": len(runnable), "ran": len(packets),
                   "produced": sum(1 for p in packets if p["status"] == "PRODUCED"),
                   "unmeasured": len(unmeasured_list)},
        "sandbox": SB.status(root), "consumers": list(CONSUMERS),
        "rule": ("highest-ROI runnable systems inside the budget; every packet becomes registry "
                 "candidates with provenance and charged trials; a missing library is UNMEASURED "
                 "with an install task; TEXT_ONLY is never a resting state"),
    }
    if not dry_run:
        state["at"] = doc["at"]
        state["last_bundle"] = doc["bundle"]
        _write(state_path, state)
        if licence_reads and isinstance(fed_state, dict):
            fed_state["systems"] = {**fed_rows(fed_state), **rows}
            fed_state.setdefault("at", doc["at"])
            with contextlib.suppress(OSError):
                _write(fed_state_path, fed_state)
        _write(report_path, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true", help="never read a licence over the "
                                                           "network this pass")
    ap.add_argument("--allow-network", action="store_true",
                    help="let cells that declare public hosts (EDGAR) fetch this pass")
    ap.add_argument("--root", default=None, help="sandbox root (default QUANT_SANDBOX_ROOT)")
    ap.add_argument("--symbols", default="", help="comma-separated bundle symbols")
    ap.add_argument("--only", default="", help="comma-separated system ids / cells to run")
    ap.add_argument("--max-systems", type=int, default=None)
    a = ap.parse_args(argv)
    doc = run_pass(budget_s=a.budget_s, dry_run=a.dry_run, allow_fetch=not a.no_fetch,
                   allow_network=a.allow_network, root=Path(a.root) if a.root else None,
                   symbols=[s for s in a.symbols.split(",") if s] or None,
                   only=[s for s in a.only.split(",") if s] or None, max_systems=a.max_systems)
    c = doc["counts"]
    print(f"sandbox runner: {c['ran']} ran / {c['runnable']} runnable / {c['plans']} planned | "
          f"produced {c['produced']} | candidates {doc['candidates']} | unmeasured "
          f"{c['unmeasured']} | text_only {len(doc['text_only'])} | "
          f"{doc['seconds']}s of {doc['budget_s']}s | bundle {doc['bundle']['universe']}")
    return 0


if __name__ == "__main__":
    _ = (shutil, timedelta)
    raise SystemExit(main())
