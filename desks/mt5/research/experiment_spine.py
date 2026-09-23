"""THE EXPERIMENT SPINE -- every research civilization becomes one experiment changing the next.

THE PRINCIPAL (RD-Agent closure, 2026-09-22): *make every one of your research civilizations
behave like one experiment directly changing the next.* Six mandated items meet on this clock:

    1   the canonical ExperimentSpec                  libs/research/experiment_spec.py
    11  world-miner -> experiment -> CampaignQueue    the CONVERSION SWEEP below
    16  the experiment memory graph                   libs/research/experiment_graph.py
    5   research credit assignment, end to end        the CREDIT LEDGER below
    4   priors updated by every completed experiment  libs/research/research_priors.py
    20  the funnel metric that settles it             RESEARCH_FUNNEL.json below

WHAT RUNS HERE, IN ORDER, AND WHY THAT ORDER. Conversion first, because an experiment that never
compiled cannot be graphed, credited or learned from. Graph refresh second, so the verdicts the
gauntlet recorded this hour are on the nodes. Credit third, because credit walks the graph.
Priors fourth, because a prior is updated by a COMPLETED experiment and completion is a verdict.
Funnel last, because it divides what the first four produced by what the hour cost.

THE CONVERSION IS THE EDGE (item 11, the principal's words: the desk's biggest). Sources this
sweep reads -- each one an organ that already runs, none of them rewritten here:

    registry discoveries        every miner, forest, deep-forest crawl and country pack
    registry candidates         the compiled cells that have no experiment node yet
    DISCOVERY_COMPILER.json     the discovery-to-cell compiler's mechanism rows
    miner_candidates.json       the seat/miner candidate compiler's hypotheses
    external_survivors.json     the merged docket (merge_hypotheses)
    TRANSMISSION_GRAPH.json     the transmission engine's edges
    GLOBAL_RESEARCH_OS.json     the global research OS / country packs' mine() output

EVERY ROW THAT CANNOT CONVERT GETS A NAMED BLOCKER. `CONVERSION_DEBT` in the artifact carries the
defect classes, counts and examples by source and generator; conversion debt to zero is a standing
law, and a row that vanishes silently is the failure this organ exists to end.

ENRICHMENT IS NAMED, NEVER INVENTED. Two fields the desk's own compilers do not write are DERIVED
before a row is called a defect, and the basis is stamped on the spec:
  * the data snapshot -- a row naming a symbol and a chart would be measured on this desk's own
    bar file for that pair, `data/universe/<SYM>_<CHART>.parquet`, whose mtime is the vintage;
  * the falsifier -- a family+symbol rule's standing falsifier IS the desk's procedure: the same
    exact rule re-judged on later bars no longer clears the ten gates.
Neither is a guess about the world. A row that still cannot compile after both is a real defect.

    python desks/mt5/research/experiment_spine.py --once [--budget-s 600] [--dry-run]

CONSUMERS: `desks/mt5/research/meta_controller.py` reads RESEARCH_PRIORS through
`libs.research.research_priors.prior_for` when it ranks proposals; the never-tried frontier in
EXPERIMENT_SPINE.json is read by the proposers through `libs.research.experiment_graph.never_tried`;
RESEARCH_FUNNEL.json is the funnel number the research dashboard and the Tier-1 acceptance
properties read; the registry's `research_credit` rows are the credit ledger `research_roi.py`
and the federation's source ROI join on.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry  # noqa: E402
from libs.research import experiment_graph as graph  # noqa: E402
from libs.research import research_priors as priors  # noqa: E402
from libs.research.experiment_spec import (  # noqa: E402
    CompileDefect,
    ExperimentSpec,
    compile_row,
    enqueue,
)

REPORTS = DESK / "reports"
OUT = REPORTS / "EXPERIMENT_SPINE.json"
FUNNEL_OUT = REPORTS / "RESEARCH_FUNNEL.json"
PRIOR_CURSOR = ROOT / "desks" / "mt5" / "data" / "research_priors" / "charged.json"

UNIVERSE = DESK / "data" / "universe"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
ALLOCATION = REPORTS / "pf_allocation.json"
RESEARCH_PNL = REPORTS / "RESEARCH_PNL.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
SLEEVES = DESK / "data" / "sleeves.json"
SHADOW = (REPORTS / "shadow" / "shadow_state.json",
          REPORTS / "shadow" / "qquant_shadow_state.json",
          REPORTS / "shadow" / "scalp_shadow_state.json")

UNMEASURED = "UNMEASURED"
WINDOW_DAYS = 30
BUDGET_S = 600.0

#: THE CONVERSION SWEEP NEVER GETS THE WHOLE BUDGET. Measured on the first full pass over this
#: desk's backlog: conversion alone wrote 5,074 experiment nodes in 180 s and the graph refresh,
#: the credit ledger, the prior update and the funnel all reported UNMEASURED because the budget
#: was gone. A pass that only ever runs its first stage is the truncated-job defect that cost
#: this desk eighty-four forward clocks -- so conversion is capped at this share and the four
#: stages that LEARN from it always run.
CONVERSION_SHARE = 0.55

#: And the graph refresh takes at most this share of what is LEFT, for the same reason: it walks
#: every node against its cell, so it grows with the graph and would otherwise swallow the credit
#: ledger, the prior update and the funnel as the desk's experiment count rises.
REFRESH_SHARE = 0.45

#: The artifact sources of the conversion sweep: (path, kind, the key holding the rows).
#: A `None` key means the document itself is a list. An ABSENT source is UNMEASURED BY NAME in
#: the report -- never a zero, and never silence (L1.28a).
ARTIFACT_SOURCES: tuple[tuple[Path, str, str | None, str], ...] = (
    (REPORTS / "DISCOVERY_COMPILER.json", "world_lead", "mechanisms", "discovery_compiler"),
    (DESK / "data" / "hypotheses" / "miner_candidates.json", "world_lead", "hypotheses",
     "miner_candidate_compiler"),
    (DESK / "data" / "hypotheses" / "external_survivors.json", "world_lead", "rows",
     "merge_hypotheses"),
    (REPORTS / "TRANSMISSION_GRAPH.json", "macro_idea", "edges", "transmission_engine"),
    (REPORTS / "GLOBAL_RESEARCH_OS.json", "country_mechanism", "mechanisms",
     "global_research_os"),
)

#: Bytes a conversion row costs while it is held in memory (a dict of ~20 short fields plus the
#: compiled spec). Used to DERIVE the pass cap from measured free memory, never a machine size.
BYTES_PER_ROW = 4096
FREE_MEMORY_SHARE = 0.10
MAX_ROWS_FLOOR = 2_000


def _free_bytes() -> int | None:
    """Free physical memory, measured on THIS box. None when it cannot be read -- never a zero.

    The trading box has 98 GB and this build box 8 GB; a cap sized off either number is sized for
    a machine the code may not be on (CLAUDE.md, the 96 GB lesson). Both readers are tried.
    """
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        kernel = getattr(ctypes, "windll", None)
        if kernel is not None and kernel.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(st)):
            return int(st.ullAvailPhys)
    except Exception:
        pass
    try:
        from libs.ops.host_resources import mem_available_mb
        mb = mem_available_mb()
        return None if mb is None else int(mb) * 1024 * 1024
    except Exception:
        return None


def max_rows_per_pass() -> int:
    free = _free_bytes()
    if free is None:
        return MAX_ROWS_FLOOR
    return max(MAX_ROWS_FLOOR, int(free * FREE_MEMORY_SHARE / BYTES_PER_ROW))


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    os.replace(tmp, path)
    return path


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


class Budget:
    """Wall-clock budget. Every stage checks it and the artifact says which stage ran out."""

    def __init__(self, seconds: float) -> None:
        self.seconds = float(seconds)
        self.t0 = time.monotonic()
        self.stopped_at: str | None = None

    def left(self) -> float:
        return self.seconds - (time.monotonic() - self.t0)

    def spent(self) -> float:
        return round(time.monotonic() - self.t0, 2)

    def ok(self, stage: str, reserve: float = 0.0) -> bool:
        if self.left() > reserve:
            return True
        if self.stopped_at is None:
            self.stopped_at = stage
        return False


# ----------------------------------------------------------------------------- enrichment
_BAR_CHARTS = ("H1", "M15", "M5", "H4", "D1", "M30", "M1")


def _bar_file(symbol: str, chart: str) -> Path | None:
    if not symbol:
        return None
    charts = [chart.upper()] if chart else list(_BAR_CHARTS)
    for ch in charts:
        p = UNIVERSE / f"{symbol}_{ch}.parquet"
        if p.exists():
            return p
    return None


def enrich(row: Mapping[str, Any]) -> dict[str, Any]:
    """Fill the two derivable fields the desk's own compilers do not write, and SAY SO.

    Returns a copy of the row. Nothing about the world is guessed: the data is the bar file this
    desk actually holds for the row's instrument, and the falsifier is the desk's own standing
    re-judgement procedure. Both carry a `*_basis` key so a reader can tell a derived field from
    a declared one, which is the difference between enrichment and invention.
    """
    out = dict(row)
    # THE SAME KEY UNION `from_claim` READS. A row that names its instrument under `instruments`
    # is not a row without an instrument: reading only `symbol` here made every country-pack
    # mechanism a NO_FALSIFIER defect while the compiler could see the instrument perfectly well.
    sym = ""
    for key in ("symbol", "instrument", "symbols", "instruments", "assets"):
        v = out.get(key)
        if isinstance(v, str) and v:
            sym = v
            break
        if isinstance(v, (list, tuple)) and v:
            sym = str(v[0])
            break
    chart = str(out.get("chart") or out.get("timeframe") or "")
    if not out.get("required_data") and not out.get("required_data_json"):
        bar = _bar_file(sym, chart)
        if bar is not None:
            out["required_data"] = [str(bar.relative_to(ROOT)).replace("\\", "/")]
            out["data_vintage"] = datetime.fromtimestamp(
                bar.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")
            out["required_data_basis"] = ("derived: the desk's own bar file for this instrument "
                                          "and chart; the vintage is that file's mtime")
    if not out.get("falsifier"):
        fam = str(out.get("family") or out.get("mechanism_family") or "")
        if fam and sym:
            out["falsifier"] = (f"the exact {fam} rule on {sym} re-judged on bars after the "
                                f"snapshot no longer clears the ten gates")
            out["falsifier_basis"] = "derived: the desk's standing re-judgement procedure"
    return out


# ------------------------------------------------------------------------ the conversion sweep
def _artifact_rows(doc: Any, key: str | None) -> list[Mapping[str, Any]]:
    if doc is None:
        return []
    if key is None:
        rows = doc
    elif isinstance(doc, Mapping):
        rows = doc.get(key)
        if rows is None:
            # The merged docket and several compilers write their rows under the document root
            # or under a differently-named list. Take the LONGEST list of mappings rather than
            # reporting zero for a file that plainly holds rows.
            best: list[Any] = []
            for v in doc.values():
                if isinstance(v, list) and len(v) > len(best) and v and isinstance(v[0], Mapping):
                    best = v
            rows = best
    else:
        rows = doc
    if isinstance(rows, Mapping):
        rows = list(rows.values())
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, Mapping)]


def convert(*, budget: Budget, cap: int, dry_run: bool,
            conn: sqlite3.Connection) -> dict[str, Any]:
    """source -> mechanism -> variables -> ExperimentSpec -> CampaignQueue, for every source."""
    per_source: dict[str, dict[str, Any]] = {}
    defects: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    unmeasured: list[dict[str, str]] = []
    converted = enqueued = created = 0
    seen_specs: set[str] = set()
    already = 0
    # EVERY PASS MUST MAKE PROGRESS. The sources are read in a stable order, so without this the
    # sweep would re-convert the same prefix every hour and never reach the tail -- truncated at
    # the same place forever, reported as scheduled. A spec already in the graph is skipped in
    # O(1) and counted, so the budget goes to rows the desk has never seen.
    try:
        known: set[str] = {str(r[0]) for r in conn.execute(
            "SELECT spec_hash FROM experiments WHERE spec_hash<>''")}
    except sqlite3.Error:
        known = set()

    def _take(rows: Iterable[Mapping[str, Any]], kind: str, source_name: str,
              generator: str) -> None:
        nonlocal converted, enqueued, created, already
        stat = per_source.setdefault(source_name, {"rows": 0, "converted": 0, "enqueued": 0,
                                                   "new_candidates": 0, "defects": 0})
        for i, raw in enumerate(rows):
            if i >= cap or not budget.ok(f"convert:{source_name}", reserve=5.0):
                stat["budget_stopped"] = True
                break
            stat["rows"] += 1
            spec = compile_row(enrich(raw), kind=kind, source=source_name, generator=generator)
            if isinstance(spec, CompileDefect):
                stat["defects"] += 1
                defects[spec.reason] = defects.get(spec.reason, 0) + 1
                if len(examples) < 40:
                    examples.append({**spec.to_dict(), "artifact": source_name})
                continue
            if not spec.experiment_id:
                spec = _with_id(spec)
            h = spec.spec_hash()
            if h in seen_specs:
                continue
            seen_specs.add(h)
            if h in known:
                already += 1
                stat["already_known"] = int(stat.get("already_known", 0)) + 1
                continue
            converted += 1
            stat["converted"] += 1
            if dry_run:
                continue
            cid, was_new = enqueue(spec, conn=conn)
            graph.upsert(spec, candidate_id=cid, conn=conn)
            enqueued += 1
            stat["enqueued"] += 1
            if was_new:
                created += 1
                stat["new_candidates"] += 1

    # 1. the registry's own discoveries -- every miner, forest and country pack
    try:
        disc = registry.discoveries(limit=min(cap, 5000), conn=conn)
    except sqlite3.Error as exc:
        disc = []
        unmeasured.append({"what": "registry discoveries", "why": f"{type(exc).__name__}: {exc}"})
    _take(disc, "", "registry:discoveries", "registry")

    # 2. compiled cells with no experiment node yet
    if budget.ok("convert:candidates", reserve=10.0):
        try:
            have = {str(r[0]) for r in conn.execute(
                "SELECT candidate_id FROM experiments WHERE candidate_id<>''")}
            cands = [r for r in registry.candidates(limit=min(cap, 5000), conn=conn)
                     if str(r.get("id")) not in have]
        except sqlite3.Error as exc:
            cands = []
            unmeasured.append({"what": "registry candidates",
                               "why": f"{type(exc).__name__}: {exc}"})
        _take(cands, "", "registry:candidates", "registry")

    # 3. the compilers' and miners' own artifacts
    for path, kind, key, generator in ARTIFACT_SOURCES:
        if not budget.ok(f"convert:{path.name}", reserve=5.0):
            break
        doc = _read_json(path)
        if doc is None:
            unmeasured.append({"what": f"artifact rows from {generator}",
                               "why": f"absent or unreadable: {path}"})
            per_source[path.name] = {"rows": 0, "converted": 0, "enqueued": 0,
                                     "new_candidates": 0, "defects": 0, "status": UNMEASURED}
            continue
        _take(_artifact_rows(doc, key), kind, path.name, generator)

    total_rows = sum(int(s["rows"]) for s in per_source.values())
    total_def = sum(int(s["defects"]) for s in per_source.values())
    return {
        "rows_read": total_rows, "converted": converted, "enqueued": enqueued,
        "already_in_graph": already,
        "new_candidates": created, "defects": total_def,
        "conversion_rate": None if total_rows == 0 else round(converted / total_rows, 6),
        "by_source": per_source,
        "conversion_debt": {
            "unconverted_rows": total_def,
            "by_reason": dict(sorted(defects.items(), key=lambda kv: -kv[1])),
            "examples": examples,
            "rule": ("conversion debt goes to ZERO: every row either compiles into an "
                     "ExperimentSpec or carries a named blocker here. A row that vanishes "
                     "silently is the defect this organ exists to end."),
        },
        "registry_debt": _registry_debt(conn),
        "unmeasured": unmeasured,
        "row_cap": cap,
    }


def _with_id(spec: ExperimentSpec) -> ExperimentSpec:
    from dataclasses import replace
    return replace(spec, experiment_id=f"exp_{spec.spec_hash()}")


def _registry_debt(conn: sqlite3.Connection) -> dict[str, Any]:
    try:
        return registry.conversion_debt(conn=conn)
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- forward and live
def _forward_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in SHADOW:
        d = _read_json(p)
        if not isinstance(d, dict):
            continue
        for key, r in d.items():
            if not isinstance(r, dict):
                continue
            e, n = r.get("exp_r"), r.get("n")
            if isinstance(e, (int, float)) and isinstance(n, (int, float)) and int(n) > 0:
                out.append({"clock": str(key), "lane": p.name, "exp_r": float(e), "n": int(n),
                            "realised_r": float(e) * int(n),
                            "symbol": str(key).split(".")[0],
                            "family": str(r.get("family") or ""),
                            "status": str(r.get("status") or "")})
    return out


def _live_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not LIVE_LEDGER.exists():
        return out
    try:
        text = LIVE_LEDGER.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        r = d.get("r_multiple")
        if isinstance(r, (int, float)):
            out.append({"sleeve": str(d.get("sleeve") or ""), "symbol": str(d.get("symbol") or ""),
                        "realised_r": float(r)})
    return out


def _delta_elogw() -> tuple[dict[str, float], str]:
    """Per-sleeve dE[log W]/day from the allocator's own gradient. Never re-derived here."""
    alloc = _read_json(ALLOCATION)
    if isinstance(alloc, dict) and isinstance(alloc.get("marginal_delta_elog"), dict):
        return ({str(k): _f(v) for k, v in alloc["marginal_delta_elog"].items()},
                "pf_allocation.marginal_delta_elog")
    pnl = _read_json(RESEARCH_PNL)
    if isinstance(pnl, dict) and isinstance(pnl.get("sources"), dict):
        return ({str(k): _f((v or {}).get("growth_per_day"))
                 for k, v in pnl["sources"].items() if isinstance(v, dict)},
                "RESEARCH_PNL.sources[*].growth_per_day")
    return {}, UNMEASURED


# ------------------------------------------------------------------------------ credit ledger
#: The ancestor kinds credit is kept for. `experiment` is included so a coevolution builder can
#: ask what one experiment's descendants earned without re-walking the DAG.
CREDIT_KINDS: tuple[str, ...] = ("source", "discovery", "experiment", "miner", "transformation",
                                 "mechanism")


def credit_ledger(*, budget: Budget, conn: sqlite3.Connection,
                  dry_run: bool) -> dict[str, Any]:
    """source or search method -> hypothesis -> cell -> survivor -> forward -> live dE[log W].

    One ledger keyed by ANCESTRY. A cell's realised value is walked backwards through the
    registry's provenance DAG and added to every ancestor it passes, plus the four ATTRIBUTE
    ancestors the experiment node carries (its method, model, representation and family), because
    "which operator creates alpha" is a question about an attribute, not about a node.
    """
    forward = _forward_rows()
    live = _live_rows()
    elog, elog_basis = _delta_elogw()
    nodes = graph.experiments(limit=20000, conn=conn)
    by_cell: dict[str, dict[str, Any]] = {}
    for n in nodes:
        cid = str(n.get("candidate_id") or "")
        if cid:
            by_cell[cid] = n

    # forward evidence joins to a cell by symbol+family; live by sleeve symbol. Both are labelled
    # on every row so nobody reads forward R as live money.
    fwd_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in forward:
        fwd_by_key.setdefault((r["symbol"], r["family"]), []).append(r)
    live_by_sym: dict[str, float] = {}
    live_n: dict[str, int] = {}
    for r in live:
        live_by_sym[r["symbol"]] = live_by_sym.get(r["symbol"], 0.0) + r["realised_r"]
        live_n[r["symbol"]] = live_n.get(r["symbol"], 0) + 1

    ledger: dict[tuple[str, str], dict[str, Any]] = {}
    survivor_records: dict[tuple[str, str], list[dict[str, Any]]] = {}

    charged: set[tuple[str, str]] = set()

    def _bump(kind: str, node_id: str, **add: float) -> None:
        # ONE EXPERIMENT CREDITS AN ANCESTOR ONCE. A source reaches a cell by several paths at
        # once (as the experiment's own `source_id`, through source -> discovery -> cell, and
        # through source -> experiment -> cell), and crediting each path separately multiplies
        # the same forward R by the number of edges the DAG happens to carry -- measured x3 on
        # the first pass. `charged` is reset per experiment by the caller.
        if not node_id or (kind, node_id) in charged:
            return
        charged.add((kind, node_id))
        row = ledger.setdefault((kind, node_id), {
            "experiments": 0.0, "candidates": 0.0, "judged": 0.0, "survivors": 0.0,
            "forward_r": 0.0, "forward_n": 0.0, "live_delta_elogw": 0.0, "compute_s": 0.0})
        for k, v in add.items():
            row[k] = row.get(k, 0.0) + float(v)

    walked = 0
    for n in nodes:
        if not budget.ok("credit", reserve=5.0):
            break
        charged.clear()
        verdict = str(n.get("verdict") or "UNJUDGED")
        cid = str(n.get("candidate_id") or "")
        symbols = json.loads(str(n.get("symbols_json") or "[]") or "[]")
        sym = str(symbols[0]) if symbols else ""
        fam = str(n.get("family") or "")
        fr = sum(x["realised_r"] for x in fwd_by_key.get((sym, fam), []))
        fn = sum(x["n"] for x in fwd_by_key.get((sym, fam), []))
        de = _f(elog.get(sym)) if sym in elog else 0.0
        if sym in live_by_sym and live_n.get(sym, 0) > 0:
            de += 0.0  # live R is realised money, not a growth rate; kept separate by design
        vals = {"experiments": 1.0, "candidates": 1.0 if cid else 0.0,
                "judged": 1.0 if verdict != "UNJUDGED" else 0.0,
                "survivors": 1.0 if verdict == "SURVIVED" else 0.0,
                "forward_r": fr, "forward_n": float(fn), "live_delta_elogw": de,
                "compute_s": _f(n.get("compute_s"))}
        # the ATTRIBUTE ancestors, straight off the node
        for kind, key in (("transformation", str(n.get("method") or "")),
                          ("source", str(n.get("source_id") or "")),
                          ("miner", str(n.get("generator") or "")),
                          ("mechanism", str(n.get("mechanism_id") or "")),
                          ("experiment", str(n.get("experiment_id") or "")),
                          ("discovery", str(n.get("discovery_id") or ""))):
            was_new = (kind, key) not in charged
            _bump(kind, key, **vals)
            if vals["survivors"] and was_new:
                survivor_records.setdefault((kind, key), []).append(
                    {"id": n.get("experiment_id"), "family": fam, "symbol": sym,
                     "model": n.get("model"), "representation": n.get("representation"),
                     "chart": n.get("chart"), "regime": n.get("regime"),
                     "horizon": n.get("horizon")})
        # the DAG ancestors of the cell (the delayed credit walk)
        if cid:
            try:
                edges = registry.provenance_of("cell", cid, depth=6, conn=conn)
            except sqlite3.Error:
                edges = []
            walked += 1
            for e in edges:
                k, i = str(e.get("from_kind")), str(e.get("from_id"))
                if k in CREDIT_KINDS:
                    was_new = (k, i) not in charged
                    _bump(k, i, **vals)
                    if vals["survivors"] and was_new:
                        survivor_records.setdefault((k, i), []).append(
                            {"id": n.get("experiment_id"), "family": fam, "symbol": sym,
                             "model": n.get("model"),
                             "representation": n.get("representation")})

    # independence: the effective breadth of each ancestor's survivors, never the raw count
    n_eff = _effective_counts(survivor_records)
    rows_written = 0
    if not dry_run:
        for (kind, node_id), row in ledger.items():
            eff = n_eff.get((kind, node_id), 0.0)
            credit = row["forward_r"] + row["live_delta_elogw"] * 1000.0
            try:
                conn.execute(
                    "INSERT INTO research_credit(ancestor_kind, ancestor_id, experiments,"
                    " candidates, judged, survivors, independent_survivors, forward_r, forward_n,"
                    " live_delta_elogw, compute_s, credit, basis, updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(ancestor_kind, ancestor_id) DO UPDATE SET"
                    " experiments=excluded.experiments, candidates=excluded.candidates,"
                    " judged=excluded.judged, survivors=excluded.survivors,"
                    " independent_survivors=excluded.independent_survivors,"
                    " forward_r=excluded.forward_r, forward_n=excluded.forward_n,"
                    " live_delta_elogw=excluded.live_delta_elogw, compute_s=excluded.compute_s,"
                    " credit=excluded.credit, basis=excluded.basis, updated_at=excluded.updated_at",
                    (kind, node_id, int(row["experiments"]), int(row["candidates"]),
                     int(row["judged"]), int(row["survivors"]), eff, row["forward_r"],
                     int(row["forward_n"]), row["live_delta_elogw"], row["compute_s"], credit,
                     f"forward R (shadow lanes) + dE[log W] ({elog_basis})", _now()))
                rows_written += 1
            except sqlite3.Error:
                break
        conn.commit()

    top = sorted(
        ({"ancestor_kind": k, "ancestor_id": i,
          "independent_survivors": round(n_eff.get((k, i), 0.0), 3),
          **{kk: round(vv, 6) for kk, vv in v.items()}}
         for (k, i), v in ledger.items()),
        key=lambda r: (-float(r["forward_r"]), -float(r["survivors"])))[:40]
    return {"ancestors": len(ledger), "rows_written": rows_written, "cells_walked": walked,
            "forward_clocks": len(forward), "live_deals": len(live),
            "delta_elogw_basis": elog_basis,
            "credit_basis": ("forward R is realised R on the shadow lanes; live dE[log W] is the "
                             "allocator's own gradient. They are NOT summed into one number "
                             "without saying so -- `credit` weights dE[log W] at 1000 R-units "
                             "per unit growth and names it here."),
            "top": top}


def _effective_counts(survivor_records: Mapping[tuple[str, str], list[dict[str, Any]]]
                      ) -> dict[tuple[str, str], float]:
    """Effective breadth of each ancestor's survivors -- independence measured, not counted."""
    try:
        from libs.research.trial_ledger import effective_count_of_records
    except ImportError:
        return {k: float(len(v)) for k, v in survivor_records.items()}
    out: dict[tuple[str, str], float] = {}
    for key, recs in survivor_records.items():
        try:
            out[key] = float(effective_count_of_records(recs))
        except (ValueError, TypeError, ZeroDivisionError):
            out[key] = float(len(recs))
    return out


# -------------------------------------------------------------------------------- the priors
def _charged() -> dict[str, str]:
    doc = _read_json(PRIOR_CURSOR)
    return {str(k): str(v) for k, v in doc.items()} if isinstance(doc, dict) else {}


def update_priors(*, budget: Budget, conn: sqlite3.Connection,
                  dry_run: bool) -> dict[str, Any]:
    """Every COMPLETED experiment moves its posteriors -- once, and once only.

    The cursor records the verdict each experiment was last charged at, so an hourly re-run
    charges nothing and a CHANGED verdict (a survivor that later decayed) charges again. Double
    counting a verdict would make a family look twice as good for having been read twice.
    """
    charged = _charged()
    state = priors.load()
    moved = 0
    by_class: dict[str, int] = {}
    for n in graph.experiments(limit=20000, conn=conn):
        if not budget.ok("priors", reserve=3.0):
            break
        eid = str(n.get("experiment_id") or "")
        verdict = str(n.get("verdict") or "UNJUDGED")
        if not eid or verdict == "UNJUDGED" or charged.get(eid) == verdict:
            continue
        fails = json.loads(str(n.get("failed_assumptions_json") or "[]") or "[]")
        reason = " ".join(str(f) for f in fails) if isinstance(fails, list) else ""
        res = priors.record_outcome(
            verdict, family=str(n.get("family") or "") or None,
            operator=str(n.get("method") or "") or None,
            source=str(n.get("source_id") or "") or None,
            model=str(n.get("model") or "") or None,
            representation=str(n.get("representation") or "") or None,
            kind=str(n.get("kind") or "") or None,
            experiment_id=eid, rejection_reason=reason,
            state=state, persist=False)
        by_class[str(res["outcome_class"])] = by_class.get(str(res["outcome_class"]), 0) + 1
        charged[eid] = verdict
        moved += 1
    if not dry_run and moved:
        priors.save(state)
        _atomic_write(PRIOR_CURSOR, charged)
    snap = priors.snapshot(state=state, top=15)
    return {"experiments_charged": moved, "by_outcome_class": by_class,
            "cursor_size": len(charged), "snapshot": snap,
            "consumers": ["desks/mt5/research/meta_controller.py",
                          "libs.research.research_priors.prior_for (search organs)"]}


# --------------------------------------------------------------------------- the funnel metric
def _compute_hours(window_days: int) -> tuple[float | None, str]:
    try:
        from libs.ops.compute_ledger import cost_by_run
        agg = cost_by_run(window_days)
    except Exception as exc:
        return None, f"{UNMEASURED}: compute ledger unreadable ({type(exc).__name__}: {exc})"
    if not agg:
        return None, f"{UNMEASURED}: the compute ledger has no rows in the window"
    return round(sum(float(a.get("hours") or 0.0) for a in agg.values()), 4), \
        "libs.ops.compute_ledger.cost_by_run"


def funnel(*, conn: sqlite3.Connection, window_days: int = WINDOW_DAYS,
           credit: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """THE ONLY FUNNEL METRIC THAT SETTLES IT (item 20).

    Independent forward-valid discoveries per (compute + data + time), and the dE[log W]
    attributable to research. The INDEPENDENCE TERM IS MEASURED -- `trial_ledger`'s effective
    breadth over the forward-valid experiments' own descriptors -- because a raw count of
    survivors is exactly the number a desk maximises by producing the same idea forty times.

    THE THREE RATES ARE THE MEASUREMENT and the composite is an INDEX. Compute hours, distinct
    data snapshots and wall days are different units; their geometric mean is a dimensionless
    index that moves in the right direction and is never to be read as a physical quantity. Each
    rate is published beside it so nobody has to.
    """
    since = datetime.now(tz=UTC) - timedelta(days=window_days)
    rows = graph.experiments(limit=20000, conn=conn)
    recent = [r for r in rows if str(r.get("created_at") or "") >= since.isoformat()[:19]]
    forward_valid = [r for r in rows
                     if str(r.get("verdict")) == "SURVIVED"
                     or str(r.get("status") or "").upper() in ("FORWARD", "LIVE")
                     or _f(r.get("forward_r")) != 0.0]
    recs = [{"id": r.get("experiment_id"), "family": r.get("family"),
             "symbol": (json.loads(str(r.get("symbols_json") or "[]") or "[]") or [""])[0],
             "model": r.get("model"), "representation": r.get("representation"),
             "chart": r.get("chart"), "regime": r.get("regime"), "session": r.get("session"),
             "horizon": r.get("horizon"), "target": r.get("target"),
             "params": json.loads(str(r.get("spec_json") or "{}") or "{}").get("model_params")
             or {}}
            for r in forward_valid]
    try:
        from libs.research.trial_ledger import effective_count_of_records
        n_eff = float(effective_count_of_records(recs)) if recs else 0.0
        eff_basis = "libs.research.trial_ledger.effective_count_of_records (participation ratio)"
    except Exception as exc:
        n_eff = float(len(recs))
        eff_basis = f"{UNMEASURED}: trial ledger unavailable ({type(exc).__name__}); raw count"

    hours, hours_basis = _compute_hours(window_days)
    snapshots = {str(r.get("snapshot_hash") or "") for r in rows if r.get("snapshot_hash")}
    datasets: set[str] = set()
    for r in rows:
        spec = json.loads(str(r.get("spec_json") or "{}") or "{}")
        for d in ((spec.get("data_snapshot") or {}).get("datasets") or []):
            datasets.add(str(d))
    data_units = len(datasets)
    days = float(window_days)

    def _rate(num: float, den: float | None) -> float | None:
        return None if den in (None, 0) or den is None or den <= 0 else round(num / den, 8)

    per_hour = _rate(n_eff, hours)
    per_data = _rate(n_eff, float(data_units) if data_units else None)
    per_day = _rate(n_eff, days)
    composite = None
    if per_hour and per_data and per_day:
        composite = round((per_hour * per_data * per_day) ** (1.0 / 3.0), 10)

    de = 0.0
    de_basis = UNMEASURED
    if isinstance(credit, Mapping):
        de = sum(_f(r.get("live_delta_elogw")) for r in (credit.get("top") or [])
                 if str(r.get("ancestor_kind")) == "experiment")
        de_basis = str(credit.get("delta_elogw_basis") or UNMEASURED)

    status = "OK"
    why = ""
    if not rows:
        status, why = UNMEASURED, "the experiment graph holds no nodes yet"
    elif hours is None:
        status, why = "PARTIAL", hours_basis
    elif not forward_valid:
        status, why = "PARTIAL", ("no experiment has forward evidence yet: the numerator is a "
                                  "real zero, the rates are therefore zero and not undefined")

    return {
        "at": _now(), "window_days": window_days, "status": status, "why": why,
        "numerator": {
            "forward_valid_discoveries": len(forward_valid),
            "independent_forward_valid": round(n_eff, 4),
            "independence_basis": eff_basis,
            "why": ("a raw survivor count is the number a desk maximises by producing the same "
                    "idea forty times; effective breadth is the number that cannot be gamed "
                    "that way"),
        },
        "denominator": {
            "compute_hours": hours, "compute_basis": hours_basis,
            "data_units": data_units, "data_basis": "distinct datasets named by experiment "
                                                    "data snapshots",
            "data_snapshots": len(snapshots),
            "time_days": days,
        },
        "rates": {"per_compute_hour": per_hour, "per_data_unit": per_data, "per_day": per_day,
                  "composite_index": composite,
                  "composite_basis": ("geometric mean of the three rates -- a dimensionless "
                                      "index, never a physical quantity; the three rates above "
                                      "are the measurement")},
        "delta_elogw_attributable_to_research": round(de, 10),
        "delta_elogw_basis": de_basis,
        "graph": {"experiments": len(rows), "created_in_window": len(recent)},
    }


# ---------------------------------------------------------------------------------- the pass
def run(*, budget_s: float = BUDGET_S, dry_run: bool = False,
        window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    b = Budget(budget_s)
    cb = Budget(budget_s * CONVERSION_SHARE)
    cap = max_rows_per_pass()
    conn = registry.connect()
    try:
        conversion = convert(budget=cb, cap=cap, dry_run=dry_run, conn=conn)
        if cb.stopped_at and b.stopped_at is None:
            b.stopped_at = f"{cb.stopped_at} (conversion share {CONVERSION_SHARE})"
        refreshed = graph.refresh(
            conn=conn, budget_s=max(5.0, b.left() * REFRESH_SHARE),
        ) if b.ok("graph_refresh", reserve=10.0) else {
            "status": UNMEASURED, "why": "budget spent before the graph refresh"}
        census = graph.census(conn=conn)
        frontier: list[dict[str, Any]] = []
        for m in graph.surviving_mechanisms(limit=10, conn=conn):
            if not b.ok("frontier", reserve=5.0):
                break
            q = graph.never_tried(mechanism=str(m["mechanism_id"]),
                                  axes=("model", "chart", "regime"), limit=25, conn=conn)
            frontier.append({"mechanism": m["mechanism_id"], "survivors": m["survivors"],
                             "n_untried": q["n_untried"], "coverage": q["coverage"],
                             "untried": q["untried"][:10]})
        credit = credit_ledger(budget=b, conn=conn, dry_run=dry_run) if b.ok(
            "credit", reserve=10.0) else {"status": UNMEASURED,
                                          "why": "budget spent before the credit ledger"}
        prior_out = update_priors(budget=b, conn=conn, dry_run=dry_run) if b.ok(
            "priors", reserve=5.0) else {"status": UNMEASURED,
                                         "why": "budget spent before the prior update"}
        fun = funnel(conn=conn, window_days=window_days, credit=credit)
    finally:
        conn.close()

    doc = {
        "at": _now(), "dry_run": dry_run, "budget_s": budget_s, "elapsed_s": b.spent(),
        "budget_stopped_at": b.stopped_at, "row_cap": cap,
        "conversion": conversion,
        "graph": {"refresh": refreshed, "census": census, "never_tried_frontier": frontier},
        "credit": credit,
        "priors": prior_out,
        "funnel": fun,
        "consumers": {
            "priors": "desks/mt5/research/meta_controller.py (proposal ranking); any search "
                      "organ drawing families or operators via research_priors.rank/thompson",
            "never_tried": "the proposers, through libs.research.experiment_graph.never_tried",
            "credit": "libs/moat/registry research_credit rows; desks/mt5/research/"
                      "research_roi.py and the federation's source ROI join on them",
            "funnel": "desks/mt5/reports/RESEARCH_FUNNEL.json -- the research dashboard and the "
                      "Tier-1 acceptance properties",
        },
        "mandate": ("RD-Agent closure items 1, 4, 5, 11, 16, 20 (principal 2026-09-22): one "
                    "canonical experiment object, priors updated by every completed experiment, "
                    "credit measured end to end, world-miner conversion, the experiment memory "
                    "graph, and the funnel metric that settles it."),
    }
    if not dry_run:
        _atomic_write(OUT, doc)
        _atomic_write(FUNNEL_OUT, fun)
        with contextlib.suppress(Exception):
            from libs.ops.events import emit
            emit("LEG_DONE", leg="experiment_spine", outcome="ok",
                 converted=conversion.get("converted"),
                 defects=conversion.get("defects"),
                 experiments=census.get("nodes"),
                 independent_forward_valid=fun["numerator"]["independent_forward_valid"])
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run, window_days=a.window_days)
    c, f = doc["conversion"], doc["funnel"]
    print(f"experiment_spine: rows={c['rows_read']} converted={c['converted']} "
          f"enqueued={c['enqueued']} defects={c['defects']} "
          f"experiments={doc['graph']['census'].get('nodes')} "
          f"n_eff_forward_valid={f['numerator']['independent_forward_valid']} "
          f"elapsed={doc['elapsed_s']}s", flush=True)
    for reason, n in (c["conversion_debt"]["by_reason"] or {}).items():
        print(f"  conversion debt {reason}: {n}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
