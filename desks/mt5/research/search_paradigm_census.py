"""W6 -- ONE INTAKE, FOURTEEN SEARCHES, AND THE TWO THAT WERE ON NO CLOCK.

THE LEDGER ITEM (Tier-1 W6): *diverse search algorithms feeding one intake -- AlphaSchema
semantic, AlphaPROBE DAG evolution, trajectory evolution, budget-aware controllers
(IMPROVE/COMBINE/PIVOT/STOP), program evolution, MCTS, quality-diversity, MAPLE multi-output
correlation penalty, symbolic regression, Bayesian optimisation, causal discovery, residual
mining, literature-to-code, counterexample agents.*

THE MEASURED GAP, 2026-09-22: nine of the paradigms exist as organs and run on their own legs.
`libs/research/search_controller.py` and `libs/research/search_populations.py` -- the budget-aware
controller and the nine populations -- are imported by `paradigm_router` for a handful of draws
per lead and are otherwise ON NO CLOCK OF THEIR OWN. A library nothing schedules is a library
that runs when some other organ happens to want four trees, which is not a search. And nothing
anywhere measured PARADIGM-LEVEL REDUNDANCY: fourteen searches can all be proposing the same
cells, and a desk that counts fourteen names and calls it diversity is counting names.

SO THIS LEG DOES TWO JOBS AND NOTHING ELSE.

  1. IT IS THE CONTROLLER'S CLOCK. Every pass builds the desk's ACTIVE LINES OF WORK from the
     registry itself -- one line per family carrying queued or claimed candidates, with its
     attempts, its successes, its pending trials and its saturation read off the rows -- and asks
     `search_controller.choose_action` for a decision on each, inside the leg's budget. The
     library speaks six actions; the item's vocabulary has four, so the mapping is DECLARED here
     and published with every decision rather than implied:

         EXPLOIT, MUTATE   -> IMPROVE    (work the line that is already paying)
         CROSSOVER         -> COMBINE    (two fertile lineages, one child)
         EXPLORE, ACQUIRE  -> PIVOT      (fresh ground, or the data the desk does not have)
         FALSIFY           -> STOP       (spend this line's budget trying to END it --
                                          `counterexample_agent` is where that budget goes)

     A line that is saturated and has never succeeded gets STOP from THIS organ's own rule,
     before the controller is asked, because "no branch has ever returned" is not a reason to
     keep drawing from it. STOP IS A RECOMMENDATION AND NOTHING ELSE. No status changes, no
     candidate is withdrawn, no gate is added: the ten gates and the promoter remain the only
     judges, and the desk never reduces its aggressiveness on a report's say-so.

  2. IT IS THE POPULATIONS' CLOCK. One generation of `search_populations.run` on real bars, with
     whatever it draws donated through the ordinary intake (`proposer_common.donate`, family
     `formula`, exactly as `expression_factory` donates an expression) -- never to a store beside
     the registry. If the bars, the grammar or the library are not there this pass, the row reads
     UNMEASURED with the reason, which is a verdict and not a zero (L1.28a).

  3. IT PUBLISHES THE REDUNDANCY NOBODY MEASURED. For every paradigm: the organ that implements
     it, the legs that can run it, whether any of those legs RAN in the last 24h (read from the
     compute ledger and the event bus, not from a docstring), how many candidates it put into the
     intake, and -- the number the item is actually missing -- the PAIRWISE OVERLAP: the share of
     each paradigm's (symbol, family, params) cells that another paradigm proposed in the same
     window. Two searches on one cell is one hypothesis and two multiplicity charges.

         effective_paradigms = n x |union of cells| / sum of each paradigm's cell count

     -- n when nothing overlaps and 1 when every paradigm proposes the same cells. The desk's
     breadth number, the inverse-Herfindahl 1 / sum(share^2) over proposal shares, is published
     beside it as `effective_paradigms_by_volume` and is NOT the headline: it measures
     concentration, so two paradigms doing one paradigm's work twice still read 2.0 on it.
     Fourteen names whose work is one paradigm's work read as one, which is the point.

     A paradigm whose legs did not run is NOT_SCHEDULED with its organ named. That row is the
     whole output for the wiring hunter: it is the difference between "the desk owns fourteen
     searches" and "the desk RAN fourteen searches".

    python desks/mt5/research/search_paradigm_census.py --once --budget-s 600
    python desks/mt5/research/search_paradigm_census.py --dry-run     # writes nothing
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "SEARCH_PARADIGMS.json"
INTEL_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")

SOURCE = "search_paradigm_census"
#: The window every "did it run" and "what did it propose" question is asked over.
WINDOW_H = 24
BUDGET_S = 600.0
#: Distinct grid cells a family needs before this organ calls its ground saturated. A declared
#: scale, published with the number, so nobody reads the saturation as a measurement of the
#: ground rather than of the desk's coverage of it.
SATURATION_CELLS = 400.0
#: A line with no success after this many judged attempts, on saturated ground, is STOPped by
#: this organ's own rule before the controller is asked.
STOP_MIN_ATTEMPTS = 8
STOP_SATURATION = 0.9
#: Trees one population draws per pass. Small: the paradigms' own legs do the volume, and a
#: census that out-drew them would be a fifteenth search nobody asked for.
DRAWS_PER_POPULATION = 6
#: Rows read from the registry when the machine's free memory cannot be measured. Derived from
#: measured free memory when it can be -- NEVER sized off a claim about the box (CLAUDE.md).
ROWS_FLOOR = 20_000
ROW_BYTES = 2_048

RULE = ("one intake, many searches: a paradigm that never ran is NOT_SCHEDULED, and two "
        "paradigms on one cell are one hypothesis carrying two multiplicity charges")

#: The library's six actions -> the item's four-verb vocabulary. Declared, not implied.
DECISION_OF: dict[str, str] = {
    "EXPLOIT": "IMPROVE", "MUTATE": "IMPROVE", "CROSSOVER": "COMBINE",
    "EXPLORE": "PIVOT", "ACQUIRE": "PIVOT", "FALSIFY": "STOP",
}
DECISIONS = ("IMPROVE", "COMBINE", "PIVOT", "STOP")

#: paradigm -> the organ that implements it, the legs that can run it, and the intake sources
#: whose donations are ITS donations. `legs` are read against the compute ledger and the event
#: bus; `sources` against the registry's `generator`/`source_id` and the intelligence roots.
PARADIGMS: tuple[dict[str, Any], ...] = (
    {"paradigm": "alphaschema_semantic",
     "organ": "libs/research/alpha_schema.py via desks/mt5/research/axis_registry.py",
     "legs": ("axis_registry", "axis_proposer"),
     "sources": ("axis_registry", "axis_proposer", "alpha_schema")},
    {"paradigm": "alphaprobe_dag_evolution",
     "organ": "libs/research/lineage_dag.py via desks/mt5/research/alpha_lineage_search.py",
     "legs": ("alpha_lineage",),
     "sources": ("alpha_lineage", "alpha_lineage_search", "lineage_dag")},
    {"paradigm": "trajectory_evolution",
     "organ": "desks/mt5/research/trajectory_evolution.py",
     "legs": ("trajectory_evolution",),
     "sources": ("trajectory_evolution",)},
    {"paradigm": "budget_aware_controller",
     "organ": "libs/research/search_controller.py",
     "legs": ("search_paradigm_census",),
     "sources": (SOURCE,)},
    {"paradigm": "program_evolution",
     "organ": "desks/mt5/research/program_alpha_lane.py",
     "legs": ("program_alpha_lane",),
     "sources": ("program_alpha_lane", "program_synthesis")},
    {"paradigm": "mcts",
     "organ": "libs/research/mcts.py via desks/mt5/research/research_tree.py",
     "legs": ("paradigm_router", "frontier_implementer"),
     "sources": ("paradigm_router", "research_tree", "mcts")},
    {"paradigm": "quality_diversity",
     "organ": "desks/mt5/research/qd_frontier.py",
     "legs": ("qd_frontier",),
     "sources": ("qd_frontier", "map_elites")},
    {"paradigm": "maple_multi_output_penalty",
     "organ": "libs/research/alpha_fitness.py via desks/mt5/research/orthogonality.py",
     "legs": ("orthogonality",),
     "sources": ("orthogonality", "alpha_fitness")},
    {"paradigm": "symbolic_regression",
     "organ": "libs/research/search_populations.py:symreg",
     # `alpha_evolution` IS a leg of this paradigm: `search_populations.symreg` runs inside it
     # (Tier-1 Q18). It was absent, so the paradigm factor could never reach the one hourly leg
     # that actually runs the population, and the leg read `belongs to no paradigm`.
     "legs": ("search", SOURCE, "alpha_evolution"),
     "sources": ("search_populations", SOURCE, "symreg")},
    {"paradigm": "bayesian_optimisation",
     "organ": "libs/research/search_populations.py:bayesian",
     "legs": ("search", SOURCE, "alpha_evolution"),
     "sources": ("search_populations", SOURCE, "bayesian")},
    {"paradigm": "gflownet_flow_matching",
     "organ": "libs/research/generators.py:GFlowNet via libs/research/search_populations.py",
     "legs": ("alpha_evolution",),
     "sources": ("alpha_evolution", "gflownet")},
    {"paradigm": "causal_discovery",
     "organ": "desks/mt5/research/causal_discovery.py",
     "legs": ("causal_graph", "causal_lab", "event_graph_lab"),
     "sources": ("causal_discovery", "causal_lab", "causal_graph", "event_graph_lab")},
    {"paradigm": "residual_mining",
     "organ": "desks/mt5/research/residual_queue.py",
     "legs": ("residual_queue", "residual_hunt", "residual_factors"),
     "sources": ("residual_queue", "residual_hunt", "factor_residual", "residual")},
    {"paradigm": "literature_to_code",
     "organ": "desks/mt5/research/deep_forest_miner.py",
     "legs": ("deep_forest", "compile_candidates"),
     "sources": ("deep_forest", "deep_forest_miner", "claims_derived")},
    {"paradigm": "counterexample_agent",
     "organ": "desks/mt5/research/counterexample_agent.py",
     "legs": ("counterexample_agent",),
     "sources": ("counterexample_agent",)},
)


# --------------------------------------------------------------------------------- plumbing
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _cut(window_h: float) -> datetime:
    return datetime.now(tz=UTC) - timedelta(hours=float(window_h))


def _stamp(value: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _row(name: str, present: bool, why: str) -> dict[str, Any]:
    return {"name": name, "status": "present" if present else "absent", "why": why}


def _write(path: Path, doc: Any) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:                                             # pragma: no cover
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def rows_cap() -> tuple[int, str]:
    """Registry rows this pass may hold, DERIVED from measured free memory, floored.

    Never sized off a claim about the box: the trading box and the build box differ by 90 GB and
    a floor sized for the wrong one either thrashes the machine that trades or refuses to run.
    """
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except Exception:
        return ROWS_FLOOR, "psutil absent; the historic floor stands"
    try:
        avail = int(psutil.virtual_memory().available)
    except Exception:                                                   # pragma: no cover
        return ROWS_FLOOR, "free memory unreadable; the historic floor stands"
    cap = max(ROWS_FLOOR, int(0.10 * avail / ROW_BYTES))
    return cap, f"10% of {avail // (1024 * 1024)} MB free at {ROW_BYTES} B/row, floor {ROWS_FLOOR}"


def cell_key(symbol: Any, family: Any, params: Any) -> str:
    """The (symbol, family, params) cell two paradigms either share or do not."""
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {"raw": params}
    if not isinstance(params, dict):
        params = {}
    body = json.dumps({k: params[k] for k in sorted(params)}, sort_keys=True, default=str)
    return f"{str(symbol).strip().upper()}|{str(family).strip().lower()}|{body}"


# ------------------------------------------------------------------------- did the leg run
def leg_runs(window_h: float = WINDOW_H, ledger: Path | None = None,
             events: Path | None = None) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Runs per leg in the window, from the compute ledger AND the event bus.

    BOTH, because they fail differently: the ledger carries every costed run with its wall clock
    and is written by `_costed`; the bus carries LEG_DONE/LEG_FAILED and survives a ledger that
    was rotated. A leg seen by either RAN.
    """
    out: dict[str, dict[str, Any]] = {}
    inputs: list[dict[str, Any]] = []
    cut = _cut(window_h)

    try:
        from libs.ops import compute_ledger as cl
        raw = cl.rows(window_days=max(1, math.ceil(window_h / 24.0)),
                      path=ledger if ledger is not None else None)
        inputs.append(_row("compute_ledger", bool(raw),
                           f"{len(raw)} costed run(s) inside {window_h:g}h"
                           if raw else "no costed run in the window"))
        for r in raw:
            at = _stamp(r.get("at"))
            if at is None or at < cut:
                continue
            a = out.setdefault(str(r.get("run") or "?"),
                               {"runs": 0, "last_at": "", "failures": 0, "seen_in": set()})
            a["runs"] += 1
            a["seen_in"].add("compute_ledger")
            a["last_at"] = max(str(a["last_at"]), at.isoformat(timespec="seconds"))
            if str(r.get("outcome") or "ok") != "ok":
                a["failures"] += 1
    except Exception as exc:
        inputs.append(_row("compute_ledger", False, f"{type(exc).__name__}: {exc}"))

    try:
        from libs.ops import events as ev
        raw2 = ev.since(cut, kinds=("LEG_DONE", "LEG_FAILED"),
                        path=events if events is not None else None)
        inputs.append(_row("events", bool(raw2),
                           f"{len(raw2)} leg event(s) inside {window_h:g}h"
                           if raw2 else "no leg event in the window"))
        for r in raw2:
            leg = str(r.get("leg") or "")
            if not leg:
                continue
            a = out.setdefault(leg, {"runs": 0, "last_at": "", "failures": 0, "seen_in": set()})
            a["seen_in"].add("events")
            if "compute_ledger" not in a["seen_in"]:
                a["runs"] += 1
            a["last_at"] = max(str(a["last_at"]), str(r.get("at") or ""))
            if str(r.get("kind")) == "LEG_FAILED":
                a["failures"] += 1
    except Exception as exc:
        inputs.append(_row("events", False, f"{type(exc).__name__}: {exc}"))

    for a in out.values():
        a["seen_in"] = sorted(a["seen_in"])
    return out, inputs


# ------------------------------------------------------------- what reached the one intake
#: Generators that are the INTAKE rather than a search. A candidate carrying one of these is
#: attributed to the DISCOVERY it was compiled from, because the compiler is the door every
#: paradigm walks through -- reading it as a paradigm would make the intake itself the largest
#: "search" on the desk and hide every real one behind it.
_COMPILERS = ("discovery_compiler", "miner_candidate_compiler", "seat", "registry",
              "intelligence")


def _source_of(row: dict[str, Any]) -> str:
    """Who proposed this row. The discovery's generator wins over the compiler that queued it."""
    for key in ("disc_generator", "generator", "source_id", "origin"):
        raw = str(row.get(key) or "").strip()
        if not raw:
            continue
        head = raw.split(":", 1)[0].strip().lower()
        if head in _COMPILERS:
            # `discovery_compiler:residual` still names the transformation that made the cell,
            # and residual IS a paradigm on the item's list -- so the tail is tried before the
            # row is given up on, and only then does it fall through to the next column.
            tail = raw.split(":", 1)[1].split(":", 1)[0].strip().lower() if ":" in raw else ""
            if tail and tail not in _COMPILERS:
                return tail
            continue
        return head
    return ""


def registry_proposals(window_h: float, cap: int,
                       conn: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Candidates created inside the window, with the source that put each one there."""
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return [], _row("registry", False, f"{type(exc).__name__}: {exc}")
    own = conn is None
    try:
        c = conn if conn is not None else reg.connect()
    except Exception as exc:                                            # pragma: no cover
        return [], _row("registry", False, f"{type(exc).__name__}: {exc}")
    since = _cut(window_h).isoformat(timespec="seconds")
    joined = (
        "SELECT rc.symbol, rc.family, rc.params_json, rc.generator, rc.source_id, rc.origin, "
        "rc.created_at, d.generator AS disc_generator FROM research_candidates rc "
        "LEFT JOIN discoveries d ON d.discovery_id = rc.discovery_id "
        "WHERE rc.created_at >= ? ORDER BY rc.created_at DESC LIMIT ?")
    plain = ("SELECT symbol, family, params_json, generator, source_id, origin, created_at "
             "FROM research_candidates WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?")
    try:
        try:
            rows = [dict(r) for r in c.execute(joined, (since, int(cap))).fetchall()]
        except Exception:
            # No discoveries table on this tree (a test's bare registry): the compiler's own
            # generator is then all there is, and the attribution says so by falling through.
            rows = [dict(r) for r in c.execute(plain, (since, int(cap))).fetchall()]
    except Exception as exc:
        return [], _row("registry", False, f"{type(exc).__name__}: {exc}")
    finally:
        if own:
            with contextlib.suppress(Exception):
                c.close()
    out = [{"source": _source_of(r), "symbol": r.get("symbol"), "family": r.get("family"),
            "params": r.get("params_json"), "at": r.get("created_at"), "via": "registry"}
           for r in rows]
    return out, _row("registry", True,
                     f"{len(out)} candidate row(s) created inside {window_h:g}h (cap {cap})")


def intake_proposals(window_h: float, cap: int, roots: tuple[Path, ...] | None = None
                     ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Donations in the intelligence roots inside the window, attributed by their directory.

    The registry is the record and this is the contract the compilers glob; a donation that has
    not reached the registry yet is still a proposal that was made, and counting only one of the
    two would under-report whichever paradigm donated most recently.
    """
    # RESOLVED AT CALL TIME, never bound as a default: a default argument freezes the module
    # constant at import, so a caller that repoints the roots (a test, a second tree) would be
    # silently reading the desk's real intake instead.
    roots = INTEL_ROOTS if roots is None else roots
    cut = _cut(window_h).timestamp()
    out: list[dict[str, Any]] = []
    seen_roots = 0
    for root in roots:
        if not root.exists():
            continue
        seen_roots += 1
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            for f in sorted(d.glob("discoveries_*.json")):
                try:
                    if f.stat().st_mtime < cut:
                        continue
                    doc = json.loads(f.read_text("utf-8-sig"))
                except (OSError, ValueError):
                    continue
                rows = doc.get("discoveries") if isinstance(doc, dict) else doc
                for r in (rows or [])[:cap]:
                    if not isinstance(r, dict):
                        continue
                    out.append({"source": str(r.get("source") or d.name),
                                "symbol": r.get("symbol"), "family": r.get("family"),
                                "params": r.get("params"), "at": doc.get("generated_at")
                                if isinstance(doc, dict) else "", "via": "intake"})
                if len(out) >= cap:
                    return out[:cap], _row("intelligence", True,
                                           f"{len(out)} donated row(s), capped at {cap}")
    if not seen_roots:
        return [], _row("intelligence", False, "no intelligence root on this tree")
    return out, _row("intelligence", True,
                     f"{len(out)} donated row(s) inside {window_h:g}h across {seen_roots} root(s)")


def attribute(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Proposal rows -> {paradigm: {"cells": set, "proposals": n}}, plus what nothing claimed."""
    index: dict[str, str] = {}
    for spec in PARADIGMS:
        for s in spec["sources"]:
            index[str(s).lower()] = str(spec["paradigm"])
    by: dict[str, dict[str, Any]] = {str(s["paradigm"]): {"cells": set(), "proposals": 0}
                                     for s in PARADIGMS}
    unattributed: dict[str, int] = {}
    for r in rows:
        src = str(r.get("source") or "").strip().lower()
        name = index.get(src) or index.get(src.split(":", 1)[0])
        if name is None:
            unattributed[src or "?"] = unattributed.get(src or "?", 0) + 1
            continue
        by[name]["proposals"] += 1
        by[name]["cells"].add(cell_key(r.get("symbol"), r.get("family"), r.get("params")))
    return by, unattributed


def redundancy(by: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Pairwise overlap, the duplicated share per paradigm, and the effective paradigm count.

    `share_of_a` is DIRECTED on purpose: a small paradigm wholly inside a large one is fully
    duplicated while the large one barely notices, and a symmetric Jaccard alone would hide
    exactly the case worth acting on.
    """
    live = {k: v for k, v in by.items() if v["proposals"] > 0}
    total = sum(v["proposals"] for v in live.values())
    pairs: list[dict[str, Any]] = []
    names = sorted(live)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ca, cb = live[a]["cells"], live[b]["cells"]
            shared = ca & cb
            if not shared:
                continue
            union = len(ca | cb)
            pairs.append({"a": a, "b": b, "shared_cells": len(shared),
                          "share_of_a": round(len(shared) / len(ca), 4) if ca else None,
                          "share_of_b": round(len(shared) / len(cb), 4) if cb else None,
                          "jaccard": round(len(shared) / union, 4) if union else None})
    pairs.sort(key=lambda r: -int(r["shared_cells"]))

    dup: dict[str, Any] = {}
    for a in names:
        others: set[str] = set()
        for b in names:
            if b != a:
                others |= live[b]["cells"]
        ca = live[a]["cells"]
        dup[a] = round(len(ca & others) / len(ca), 4) if ca else None

    all_cells: dict[str, int] = {}
    for v in live.values():
        for cell in v["cells"]:
            all_cells[cell] = all_cells.get(cell, 0) + 1
    multi = sum(1 for n in all_cells.values() if n > 1)

    hhi = sum((v["proposals"] / total) ** 2 for v in live.values()) if total else 0.0
    # TWO EFFECTIVE COUNTS, BECAUSE ONE OF THEM CANNOT SEE THE THING THIS ORGAN EXISTS TO SEE.
    # The inverse-Herfindahl over proposal shares is the desk's breadth number and is published
    # unchanged -- but it measures CONCENTRATION, not redundancy: two paradigms proposing the
    # identical ten cells still hold half the volume each, so it reads 2.0 for a search that is
    # doing one paradigm's work twice. The headline `effective_paradigms` is therefore the
    # COVERAGE count -- how many paradigms' worth of DISTINCT ground the desk actually reached:
    #
    #     effective_paradigms = n x |union of all cells| / sum_i |cells_i|
    #
    # which is n when nothing overlaps and 1 when every paradigm proposes the same cells.
    covered = sum(len(v["cells"]) for v in live.values())
    eff = (len(live) * len(all_cells) / covered) if covered else None
    return {
        "paradigms_with_proposals": len(live), "total_proposals": total,
        "distinct_cells": len(all_cells), "cells_proposed_by_two_or_more": multi,
        "cells_proposed_total": covered,
        "duplicated_cell_share": round(multi / len(all_cells), 4) if all_cells else None,
        "duplicated_share_by_paradigm": dup,
        "hhi": round(hhi, 6) if total else None,
        "effective_paradigms": round(eff, 3) if eff is not None else None,
        "effective_paradigms_by_volume": round(1.0 / hhi, 3) if hhi > 0 else None,
        "pairwise": pairs[:60],
        "rule": ("effective_paradigms = n x |union of cells| / sum of each paradigm's cell "
                 "count -- n when nothing overlaps, 1 when every paradigm proposes the same "
                 "cells; effective_paradigms_by_volume = 1 / sum(share^2) over proposal shares, "
                 "the same inverse-Herfindahl the desk uses for breadth, which measures "
                 "concentration and CANNOT see duplication; overlap is the share of a "
                 "paradigm's cells another paradigm also proposed"),
    }


# ------------------------------------------------------------------- the controller's clock
def lines_of_work(cap: int, conn: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The desk's ACTIVE lines of work, read off the registry: one per family with live rows."""
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return [], _row("lines_of_work", False, f"{type(exc).__name__}: {exc}")
    own = conn is None
    try:
        c = conn if conn is not None else reg.connect()
    except Exception as exc:                                            # pragma: no cover
        return [], _row("lines_of_work", False, f"{type(exc).__name__}: {exc}")
    try:
        cur = c.execute(
            "SELECT family, COUNT(*) AS n, "
            " SUM(CASE WHEN status IN ('queued','claimed','donated') THEN 1 ELSE 0 END) AS pending,"
            " SUM(CASE WHEN COALESCE(survived,0) > 0 THEN 1 ELSE 0 END) AS successes, "
            " SUM(CASE WHEN judged_at IS NOT NULL AND judged_at != '' THEN 1 ELSE 0 END) AS judged,"
            " COUNT(DISTINCT grid_cell) AS cells "
            "FROM research_candidates WHERE family IS NOT NULL AND family != '' "
            "GROUP BY family ORDER BY n DESC LIMIT ?", (int(min(cap, 400)),))
        raw = [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        return [], _row("lines_of_work", False, f"{type(exc).__name__}: {exc}")
    finally:
        if own:
            with contextlib.suppress(Exception):
                c.close()
    out: list[dict[str, Any]] = []
    for r in raw:
        pending = int(r.get("pending") or 0)
        if pending <= 0:
            continue                       # not an ACTIVE line: nothing of it is in flight
        judged = int(r.get("judged") or 0)
        out.append({"line": str(r["family"]), "rows": int(r.get("n") or 0),
                    "attempts": judged, "successes": int(r.get("successes") or 0),
                    "pending": pending,
                    "saturation": round(min(1.0, float(r.get("cells") or 0) / SATURATION_CELLS),
                                        4)})
    return out, _row("lines_of_work", bool(out),
                     f"{len(out)} family line(s) with pending rows" if out
                     else "no family carries a queued or claimed candidate")


def controller_pass(lines: list[dict[str, Any]], *, budget: int,
                    seed: int = 0) -> dict[str, Any]:
    """Run the REAL budget-aware controller on the REAL lines. Recommendations only."""
    try:
        from libs.research import search_controller as sc
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}",
                "decisions": [], "counts": {}}
    if not lines:
        return {"status": "UNMEASURED",
                "why": "no active line of work: the registry carries no queued or claimed "
                       "candidate, so there is nothing to decide about",
                "decisions": [], "counts": {}}

    branches = [sc.Branch(key=str(ln["line"]), attempts=int(ln["attempts"]),
                          successes=int(ln["successes"]), pending=int(ln["pending"]),
                          population=("REFINE" if int(ln["successes"]) > 0 else "EXPLORE"),
                          saturation=float(ln["saturation"])) for ln in lines]
    by_key = {b.key: b for b in branches}
    decisions: list[dict[str, Any]] = []
    counts = dict.fromkeys(DECISIONS, 0)
    for ln in lines:
        b = by_key[str(ln["line"])]
        if (b.saturation >= STOP_SATURATION and b.successes == 0
                and b.attempts >= STOP_MIN_ATTEMPTS):
            native, why = "FALSIFY", (
                f"{b.attempts} judged attempt(s) and no success on ground this organ reads as "
                f"{b.saturation:.2f} saturated: STOP is this census's own rule, applied before "
                f"the controller is asked. It withdraws nothing -- the gauntlet and the promoter "
                f"remain the only judges")
        else:
            native, why = sc.choose_action(branches, seed=(seed + abs(hash(b.key))) % (2**31))
            # `choose_action` ranks the whole set; the line under decision only OWNS the verdict
            # when it is the branch the controller named. Otherwise it is being told to work the
            # winner, which for this line reads as PIVOT: its own budget is better spent
            # elsewhere.
            if native in ("EXPLOIT", "MUTATE") and b.key not in why:
                native, why = "EXPLORE", (
                    f"the controller's best branch is not {b.key}; this line's own budget is "
                    f"better spent on fresh ground than on refining a branch it does not own "
                    f"({why})")
        decision = DECISION_OF.get(native, "PIVOT")
        counts[decision] += 1
        decisions.append({"line": b.key, "native_action": native, "decision": decision,
                          "why": why, "attempts": b.attempts, "successes": b.successes,
                          "pending": b.pending, "saturation": b.saturation,
                          "reward": round(b.reward(), 6),
                          "ucb": (None if math.isinf(sc.ucb(b, sum(x.attempts for x in branches)))
                                  else round(sc.ucb(b, sum(x.attempts for x in branches)), 6))})
    try:
        split = sc.split_budget(branches, int(budget), seed=seed)
    except Exception as exc:                                            # pragma: no cover
        split = {}
        counts["budget_error"] = f"{type(exc).__name__}: {exc}"         # type: ignore[assignment]
    return {"status": "MEASURED", "why": f"{len(decisions)} active line(s) decided",
            "decisions": decisions, "counts": counts,
            "budget_trials": int(budget),
            "budget_split": dict(sorted(split.items(), key=lambda kv: -kv[1])[:40]),
            "mapping": DECISION_OF,
            "stop_rule": (f"saturation >= {STOP_SATURATION} and 0 successes after "
                          f">= {STOP_MIN_ATTEMPTS} judged attempts"),
            "authority": ("recommendations only: no status changes, no candidate withdrawn, no "
                          "cap or veto added -- the ten gates and the promoter remain the only "
                          "judges")}


# ------------------------------------------------------------------ the populations' clock
def _frames(symbol: str) -> tuple[dict[str, Any], Any, str]:
    """(frames, forward return, why) for a symbol, or ({}, None, why) when the bars are absent."""
    try:
        from research import proposer_common as pc
    except Exception as exc:
        return {}, None, f"{type(exc).__name__}: {exc}"
    d = pc.bars(symbol)
    if d is None or len(d) < 500:
        return {}, None, f"{symbol}: fewer than 500 H1 bars on this tree"
    frames = {c: d[c].astype(float) for c in ("open", "high", "low", "close") if c in d.columns}
    if "tick_volume" in d.columns:
        frames["volume"] = d["tick_volume"].astype(float)
    elif "volume" in d.columns:
        frames["volume"] = d["volume"].astype(float)
    ret = d["close"].astype(float).pct_change().shift(-1)
    return frames, ret, f"{symbol}: {len(d)} H1 bars"


def populations_pass(*, symbol: str, budget_s: float, draws: int = DRAWS_PER_POPULATION,
                     dry_run: bool = False, seed: int = 0) -> dict[str, Any]:
    """One generation of every population, donated through the ordinary intake."""
    try:
        import numpy as np

        from libs.research import alpha_grammar as ag
        from libs.research import search_populations as sp
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}", "yields": []}

    frames, ret, why = _frames(symbol)
    try:
        ctx = sp.SearchContext(rng=np.random.default_rng(seed), frames=frames, ret=ret,
                               symbol=symbol,
                               notes=dict.fromkeys(sp.POPULATIONS,
                                                   f"drawn by {SOURCE} on {why}"))
        res = sp.run(ctx, n_per_population=int(draws), budget_s=float(budget_s))
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}", "yields": [],
                "bars": why}

    proposals = list(getattr(res, "proposals", []) or [])
    out: dict[str, Any] = {
        "status": "MEASURED" if proposals else "UNMEASURED",
        "why": (f"{len(proposals)} well-formed tree(s) from "
                f"{len(getattr(res, 'yields', {}) or {})} population(s)") if proposals
               else f"no population drew a well-formed tree this pass ({why})",
        "bars": why, "symbol": symbol,
        "yields": res.yield_rows() if hasattr(res, "yield_rows") else [],
        "failures": list(getattr(res, "failures", []) or [])[:20],
        "donated": 0, "donation": {},
    }
    if not proposals or dry_run:
        out["donation"] = {"skipped": "dry run" if dry_run else "nothing to donate"}
        return out

    try:
        from research import proposer_common as pc
        from research.universe_policy import may_hypothesise
    except Exception as exc:                                            # pragma: no cover
        out["donation"] = {"error": f"{type(exc).__name__}: {exc}"}
        return out
    if not may_hypothesise(symbol):
        out["donation"] = {"refused_wrong_lane": len(proposals),
                           "why": f"{symbol} is not in the hypothesis-discovery lane"}
        return out

    cands: list[dict[str, Any]] = []
    for expr, pop in proposals:
        try:
            rendered = ag.to_str(expr)
        except Exception:                                               # pragma: no cover
            continue
        cands.append(pc.candidate(
            SOURCE, symbol, "formula",
            {"expr": rendered, "population": str(pop)},
            f"search population {pop} over the desk's own grammar",
            f"{pop}: {rendered[:90]}",
            {"population": str(pop), "drawn_by": SOURCE, "bars": why}))
    try:
        path = pc.donate(SOURCE, cands, tests_run=len(proposals))
        counts = pc.donation_counts()
    except Exception as exc:
        out["donation"] = {"error": f"{type(exc).__name__}: {exc}"}
        return out
    out["donated"] = int(counts.get("donated") or 0)
    out["donation"] = {**counts, "path": str(path) if path else None}
    return out


# ------------------------------------------------------------------------------- the report
def paradigm_rows(runs: dict[str, dict[str, Any]], by: dict[str, dict[str, Any]],
                  dup: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in PARADIGMS:
        name = str(spec["paradigm"])
        legs = [str(x) for x in spec["legs"]]
        seen = {leg: runs[leg] for leg in legs if leg in runs}
        ran = bool(seen)
        n_runs = sum(int(v["runs"]) for v in seen.values())
        last = max((str(v["last_at"]) for v in seen.values()), default="")
        share = by.get(name) or {"cells": set(), "proposals": 0}
        if not ran:
            status = "NOT_SCHEDULED"
            why = (f"no leg of {name} appears in the compute ledger or the event bus inside the "
                   f"window; its organ is {spec['organ']} and the legs that would run it are "
                   f"{legs}")
        elif share["proposals"] == 0:
            status = "RAN_PROPOSED_NOTHING"
            why = (f"{n_runs} run(s) of {sorted(seen)} in the window and no candidate in the "
                   f"intake attributable to it -- a run is not a proposal")
        else:
            status = "RAN"
            why = f"{n_runs} run(s) of {sorted(seen)}; {share['proposals']} proposal(s)"
        out.append({"paradigm": name, "organ": spec["organ"], "legs": legs,
                    "scheduled": ran, "ran_24h": ran, "runs": n_runs,
                    "last_run_at": last or None,
                    "failures": sum(int(v["failures"]) for v in seen.values()),
                    "proposals": int(share["proposals"]), "distinct_cells": len(share["cells"]),
                    "duplicated_share": dup.get(name), "status": status, "why": why})
    return out


def build(*, window_h: float = WINDOW_H, budget_s: float = BUDGET_S,
          symbol: str = "XAUUSD", draws: int = DRAWS_PER_POPULATION,
          dry_run: bool = False, seed: int = 0, ledger: Path | None = None,
          events: Path | None = None,
          roots: tuple[Path, ...] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    cap, cap_why = rows_cap()
    inputs: list[dict[str, Any]] = [_row("rows_cap", True, cap_why)]

    runs, run_inputs = leg_runs(window_h, ledger=ledger, events=events)
    inputs.extend(run_inputs)

    reg_rows, reg_in = registry_proposals(window_h, cap)
    inputs.append(reg_in)
    intake_rows, intake_in = intake_proposals(window_h, cap, roots=roots)
    inputs.append(intake_in)

    by, unattributed = attribute(reg_rows + intake_rows)
    red = redundancy(by)
    dup = red.get("duplicated_share_by_paradigm") or {}

    lines, lines_in = lines_of_work(cap)
    inputs.append(lines_in)
    controller = controller_pass(lines, budget=max(10, len(lines) * 8), seed=seed)

    left = max(5.0, float(budget_s) - (time.monotonic() - started) - 5.0)
    populations = populations_pass(symbol=symbol, budget_s=min(left, float(budget_s) * 0.5),
                                   draws=draws, dry_run=dry_run, seed=seed)

    rows = paradigm_rows(runs, by, dup)
    report: dict[str, Any] = {
        "at": _now(), "source": SOURCE, "rule": RULE, "window_hours": window_h,
        "budget_s": budget_s, "dry_run": bool(dry_run), "seed": seed,
        "inputs": inputs,
        "controller": controller,
        "populations": populations,
        "paradigms": rows,
        "redundancy": red,
        "unattributed_sources": dict(sorted(unattributed.items(), key=lambda kv: -kv[1])[:25]),
        "counts": {
            "paradigms": len(rows),
            "ran_24h": sum(1 for r in rows if r["ran_24h"]),
            "not_scheduled": sum(1 for r in rows if r["status"] == "NOT_SCHEDULED"),
            "ran_proposed_nothing": sum(1 for r in rows
                                        if r["status"] == "RAN_PROPOSED_NOTHING"),
            "decisions": controller.get("counts") or {},
            "donated": int(populations.get("donated") or 0),
            "proposals_seen": len(reg_rows) + len(intake_rows),
        },
        "elapsed_s": round(time.monotonic() - started, 2),
    }
    report["summary"] = summary(report)
    return report


def summary(report: dict[str, Any]) -> list[str]:
    c = report["counts"]
    red = report["redundancy"]
    out = [f"{c['ran_24h']}/{c['paradigms']} paradigms ran inside "
           f"{report['window_hours']:g}h; {c['not_scheduled']} NOT_SCHEDULED",
           f"effective paradigms {red['effective_paradigms']} "
           f"(by volume {red['effective_paradigms_by_volume']}) over "
           f"{red['total_proposals']} proposal(s) in {red['distinct_cells']} distinct cell(s); "
           f"{red['cells_proposed_by_two_or_more']} cell(s) proposed by two or more"]
    ctrl = report["controller"]
    if ctrl.get("status") == "MEASURED":
        out.append("controller: " + ", ".join(f"{k}={v}" for k, v in
                                              (ctrl.get("counts") or {}).items()))
    else:
        out.append(f"controller UNMEASURED: {ctrl.get('why')}")
    pops = report["populations"]
    out.append(f"populations {pops.get('status')}: {pops.get('why')}; "
               f"donated {pops.get('donated')}")
    for r in report["paradigms"]:
        if r["status"] == "NOT_SCHEDULED":
            out.append(f"  NOT_SCHEDULED {r['paradigm']} -> {r['organ']}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the search-paradigm census and the controller's "
                                             "clock")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--window-h", type=float, default=WINDOW_H)
    ap.add_argument("--symbol", default="XAUUSD", help="bars the populations draw over")
    ap.add_argument("--draws", type=int, default=DRAWS_PER_POPULATION)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write nothing, donate nothing")
    ap.add_argument("--out", default=str(REPORT))
    a = ap.parse_args(argv)

    report = build(window_h=a.window_h, budget_s=a.budget_s, symbol=a.symbol, draws=a.draws,
                   dry_run=bool(a.dry_run), seed=int(a.seed))
    for line in report["summary"]:
        print(line)
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    _write(Path(a.out), report)
    print(f"  -> {a.out}")
    try:
        from libs.ops import events as ev
        ev.emit("LEG_DONE", leg=SOURCE, outcome="ok",
                paradigms=report["counts"]["paradigms"],
                not_scheduled=report["counts"]["not_scheduled"],
                effective=report["redundancy"]["effective_paradigms"])
    except Exception:
        pass
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
