"""THE DESK'S EVOLUTIONARY RECORD, READ AS A RECORD (principal 2026-09-17).

WHAT IS ALREADY WRITTEN DOWN AND NEVER READ BACK. `hypothesis_graph.jsonl` holds every
hypothesis this desk has ever minted with the PARENT it was mutated from, the source that minted
it and the fate it met. `gate_verdict_ledger.jsonl` holds the gate each one died at.
`shadow_state.json` holds what happened forward. `alpha_events` holds every card's creation,
status change and retirement. Four records of one process -- hypothesis -> mutation -> backtest
verdict -> conditional variant -> forward result -- and nothing on this tree joins them, so the
desk has a complete genealogy it cannot read and asks the same questions of new strangers'
mechanisms every hour.

WHAT A GENEALOGY ANSWERS THAT A DOCKET CANNOT. A docket says how many cells were tested. A
FOREST says which MOVES were ever made. Those are different questions and only the second one
finds unexplored ground: 35,199 rows can carry one mutation repeated 35,199 times, and that is
what "exhausted" has meant here before (L1.51 -- exhaustion needs PER-AXIS evidence). So this
organ classifies every parent -> child EDGE into the transformation that produced it, and then
reports the transformations that have NO edge anywhere under a mechanism. An axis with no edge
is not a failure; it is a question nobody asked.

THE SIX FINDINGS, and each is a mistake the desk can be shown to have made:

  1. MUTATIONS NEVER TRIED. Per family, which of the nine transformation axes has no child edge
     anywhere. The named example is the best-evidenced node of that family -- the cell the
     untried move should be applied to first.
  2. BRANCHES ABANDONED TOO EARLY. A node whose posterior upper bound sits ABOVE its family's
     median with no descendants for more than `--abandon-days`. The bound is Wilson's on the
     node's own subtree survival -- a numpy-only stand-in for the Beta posterior's upper tail --
     and it is an UPPER bound on purpose: abandoning a branch is a decision about what the
     evidence still ALLOWS, not about its point estimate.
  3. PARAMETER NEIGHBOURHOODS NEVER EXPLORED. Per family, the grid values the family DECLARES
     (`FAMILY_REGISTRY[...]["param_grid"]`) against the values any node actually carried. A
     family with no declared grid is UNMEASURED and says so; it is not reported as explored.
  4. MECHANISMS TESTED ON ONE ASSET ONLY. A mechanism is a property of a constraint some
     participant operates under, not of a ticker; a family with three tested cells all on one
     instrument has never been asked whether it transfers.
  5. MECHANISMS TESTED IN ONE SESSION ONLY. The same argument on the clock: the participants
     differ by session and so does the constraint.
  6. APPARENTLY DIFFERENT STRATEGIES SHARING AN ANCESTOR. Two families descending from one root
     are not independent bets, and the allocator sizes them as if they were.

THIS ORGAN DONATES NOTHING. Every finding is written to the canonical registry as a DISCOVERY in
state UNPROCESSED whose payload names the parent cell and the untried move; the discovery
compiler is what turns it into cells. Two reasons, and the second is the real one: a finding
about the SEARCH is not a hypothesis about a market, and a miner that both finds and compiles its
own findings is a miner whose conversion debt nobody can audit. `record_discovery` hashes
(source, mechanism, assets, rule), so a second run on an unchanged forest records nothing new --
the idempotence is the registry's, not a flag here.

    python desks/mt5/research/alpha_lineage_search.py [--dry-run] [--budget-s 240]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from libs.research import set_aside as sa  # noqa: E402
from research import axis_registry as ar  # noqa: E402

GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
OUT = DESK / "reports" / "ALPHA_LINEAGE.json"

SEAT = "lineage"
ORIGIN = "MOAT"

#: The transformation vocabulary an EDGE is classified into. These are the moves the desk can
#: actually make; an edge that fits none of them is `parameter_neighbourhood`, and an edge that
#: changes nothing is `none` and is counted rather than dropped.
MUTATION_AXES: tuple[str, ...] = ("inverse", "transfer", "horizon", "session", "regime",
                                  "residual", "interaction", "execution",
                                  "parameter_neighbourhood")

HOLD_KEYS = ("ttl_bars", "hold_bars", "max_hold", "horizon")
DIRECTION_KEYS = ("side", "side_mode", "side_bias", "mode", "direction")
REGIME_KEYS = ("vol_filter", "require_quiet", "state", "vol_state", "market_state", "regime",
               "band", "crisis_only")
EXECUTION_KEYS = ("wait_bars", "cooldown_bars", "signal_at", "spread_gate", "entry_z", "exit_z")
RESIDUAL_FAMILIES = frozenset({"cross_asset_residual", "pca_residual", "relative_value",
                               "correlation_regime", "style_premia"})
INTERACTION_FAMILIES = frozenset({"ensemble", "joint_genome", "formula", "cross_sectional"})

#: A family with fewer tested cells than this is not a claim about the search: "tested on one
#: asset only" needs enough cells for the singleness to mean something.
MIN_FAMILY_NODES = 3
#: Days with no descendant before a node counts as ABANDONED rather than merely recent.
ABANDON_DAYS = 14
#: Wilson's z. 1.96 is the 97.5% one-sided bound.
WILSON_Z = 1.96
#: Rows read per source. The box holding the live terminal has 8 GB and a dozen resident python
#: processes; a source larger than this is reported TRUNCATED rather than silently halved.
MAX_GRAPH_ROWS = 200_000
MAX_LEDGER_ROWS = 400_000
MAX_FINDINGS = 40
BUDGET_S = 240.0
#: The name this organ files its named refusals under (libs/research/set_aside.py).
ORGAN = "alpha_lineage_search"

#: The six findings, in the order the report carries them.
FINDINGS: tuple[str, ...] = ("untried_mutations", "abandoned_branches",
                            "unexplored_neighbourhoods", "single_asset_mechanisms",
                            "single_session_mechanisms", "shared_ancestors")

CERTIFIED = "CERTIFIED"
FAILED = "FAILED"

RULE = ("the desk's own record is the cheapest unexplored ground it owns: every parent -> child "
        "edge is classified into the transformation that produced it, and a transformation with "
        "no edge under a mechanism is a question nobody asked, not a question already answered")


# ------------------------------------------------------------------ tolerant reading
def _read_jsonl(path: Path, max_rows: int, note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every readable object in `path`, at most `max_rows`. Never raises; says what it skipped."""
    if not path.exists():
        note.append({"what": f"{path.name} absent", "n": 0,
                     "why": f"{path} does not exist on this box; UNMEASURED, not empty"})
        return []
    rows: list[dict[str, Any]] = []
    bad = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if len(rows) >= max_rows:
                    note.append({"what": f"{path.name} truncated", "n": max_rows,
                                 "why": f"read the first {max_rows} rows; the rest is UNMEASURED "
                                        f"on a box with 8 GB"})
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError as exc:
        note.append({"what": f"{path.name} unreadable", "n": 0, "why": f"{exc}"})
    if bad:
        note.append({"what": f"{path.name} unparseable rows", "n": bad,
                     "why": "a row that is not JSON is counted, never guessed at"})
    return rows


def _read_json(path: Path, note: list[dict[str, Any]]) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        note.append({"what": f"{path.name} unavailable", "n": 0, "why": f"{exc}"})
        return None


def _when(value: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _age_days(value: Any, now: datetime) -> float | None:
    d = _when(value)
    return None if d is None else max(0.0, (now - d).total_seconds() / 86400.0)


def wilson_upper(k: int, n: int, z: float = WILSON_Z) -> float | None:
    """The upper end of what the evidence still ALLOWS for this node's survival rate.

    Wilson's interval rather than a Beta quantile because the desk ships numpy and pandas and
    nothing else, and because Wilson is the interval that behaves at k=0 and k=n -- exactly the
    two cases a lineage is full of. `None` for n=0: an untested node has no bound, and inventing
    1.0 for it would make every unborn cell look like an abandoned winner.
    """
    if n <= 0:
        return None
    p = float(k) / float(n)
    den = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / den
    half = z * float(np.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))) / den
    return float(min(1.0, centre + half))


# ------------------------------------------------------------------ the forest
def node_spec(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("params")
    params: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    return {"symbol": str(row.get("symbol") or "").upper(),
            "family": str(row.get("family") or ""), "params": dict(params),
            "chart": ar.normalise_chart(params.get("timeframe")),
            "session": ar.normalise_session(params.get("session"))}


def classify_edge(parent: dict[str, Any], child: dict[str, Any]) -> str:
    """Which of the nine transformations turned `parent` into `child`, read off the two specs."""
    pf, cf = parent["family"], child["family"]
    if pf != cf:
        if cf in INTERACTION_FAMILIES:
            return "interaction"
        if cf in RESIDUAL_FAMILIES and pf not in RESIDUAL_FAMILIES:
            return "residual"
        return "transfer"
    if parent["symbol"] != child["symbol"] or parent["chart"] != child["chart"]:
        return "transfer"
    if parent["session"] != child["session"]:
        return "session"
    pp, cp = parent["params"], child["params"]
    changed = {k for k in set(pp) | set(cp) if pp.get(k) != cp.get(k)}
    if not changed:
        return "none"
    if changed & set(DIRECTION_KEYS):
        return "inverse"
    if changed & set(HOLD_KEYS):
        return "horizon"
    if changed & set(REGIME_KEYS):
        return "regime"
    if changed & set(EXECUTION_KEYS):
        return "execution"
    return "parameter_neighbourhood"


def build_forest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """nodes, children, roots and depth. A parent this record does not hold is a VIRTUAL root --
    the miner's own seed string -- and it is kept, because the strategies sharing it are the
    finding."""
    nodes: dict[str, dict[str, Any]] = {}
    for r in rows:
        nid = str(r.get("id") or "")
        if not nid:
            continue
        nodes[nid] = {"id": nid, "parent": str(r.get("parent") or ""),
                      "fate": str(r.get("fate") or "").upper(),
                      "source": str(r.get("source") or ""), "at": r.get("at"),
                      "spec": node_spec(r)}
    children: dict[str, list[str]] = defaultdict(list)
    roots: dict[str, list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        p = n["parent"]
        if p and p in nodes:
            children[p].append(nid)
        else:
            n["virtual_parent"] = p
    depth: dict[str, int] = {}
    for nid in nodes:
        seen: set[str] = set()
        cur, d = nid, 0
        while nodes[cur]["parent"] in nodes and cur not in seen:
            seen.add(cur)
            cur = nodes[cur]["parent"]
            d += 1
        depth[nid] = d
        # THE ROOT IS THE VIRTUAL PARENT WHEN THERE IS ONE. `cur` is the highest node this record
        # holds; the string above it -- the miner's own seed, a fund name, a claim -- is not a
        # node and it is still the ancestor. Grouping on `cur` instead made every unresolved
        # node its own root, which cannot produce a shared-ancestor finding at all: measured on
        # this tree, 0 of 35,199 parent references resolve to a node id, so the sixth finding
        # was structurally unreachable.
        above = nodes[cur]["parent"]
        nodes[nid]["root"] = above if above and above not in nodes else cur
        roots[nodes[nid]["root"]].append(nid)
    resolved = sum(1 for n in nodes.values() if n["parent"] in nodes)
    refs = sum(1 for n in nodes.values() if n["parent"])
    for nid, n in nodes.items():
        n["depth"] = depth[nid]
        n["children"] = children.get(nid, [])
    return {"nodes": nodes, "children": dict(children), "roots": dict(roots),
            "depth_max": max(depth.values()) if depth else 0,
            "n_parent_refs": refs, "n_parent_resolved": resolved}


def subtree_evidence(forest: dict[str, Any], nid: str) -> tuple[int, int]:
    """(survivors, terminal verdicts) in {node} U subtree. A BORN node is not a verdict."""
    nodes, children = forest["nodes"], forest["children"]
    k = n = 0
    stack, seen = [nid], set()
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in nodes:
            continue
        seen.add(cur)
        fate = nodes[cur]["fate"]
        if fate == CERTIFIED:
            k += 1
            n += 1
        elif fate == FAILED:
            n += 1
        stack.extend(children.get(cur, []))
    return k, n


# ------------------------------------------------------------------ the six findings
def untried_mutations(forest: dict[str, Any], edges: dict[str, dict[str, int]]
                      ) -> list[dict[str, Any]]:
    """Per family, the transformation axes with NO child edge anywhere under the mechanism."""
    nodes = forest["nodes"]
    by_family: dict[str, list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        by_family[n["spec"]["family"]].append(nid)
    out = []
    for family, ids in sorted(by_family.items()):
        if not family or len(ids) < MIN_FAMILY_NODES:
            continue
        made = edges.get(family, {})
        missing = [a for a in MUTATION_AXES if not made.get(a)]
        if not missing:
            continue
        best = sorted(ids, key=lambda i: (nodes[i]["fate"] != CERTIFIED,
                                          -len(nodes[i]["children"]), i))[0]
        out.append({"family": family, "mechanism": ar.classify_family(family)[0],
                    "n_nodes": len(ids), "untried": missing,
                    "tried": {a: made[a] for a in MUTATION_AXES if made.get(a)},
                    "example_cell": best, "example_spec": nodes[best]["spec"],
                    "why": f"{len(ids)} cells of {family} and not one edge on "
                           f"{', '.join(missing)}: the mechanism was sampled, not searched"})
    out.sort(key=lambda r: (-len(r["untried"]), -int(r["n_nodes"])))
    # MAX_FINDINGS IS A BATCH BUDGET, NOT A SCREEN (LAWS 7: only the four immutable evaluator
    # files may refuse a cell). The budget stays; what changes is that the remainder is NAMED --
    # organ, stage, count set aside, the ordering key that chose the survivors -- in
    # reports/SET_ASIDE_LEDGER.json, so "this finding is empty" can never be confused with "this
    # finding was truncated at 40 of 900".
    return sa.take(out, MAX_FINDINGS, organ=ORGAN, stage="untried_mutations",
                   ordering="-len(untried), -n_nodes")


def abandoned_branches(forest: dict[str, Any], now: datetime, abandon_days: float
                       ) -> list[dict[str, Any]]:
    """A node the evidence still allows, with no descendants and no activity for N days.

    THE MEDIAN IS A FAMILY BASELINE, so a family too small to have one is skipped -- the same
    `MIN_FAMILY_NODES` bar the other findings use. A median over two nodes is whichever of them
    the parent happens to be: measured on the fixture forest it made a FAILED leaf "promising"
    because its own parent's larger subtree dragged the median below it, which is an artefact of
    the denominator and not a branch anybody abandoned.
    """
    nodes = forest["nodes"]
    bound: dict[str, float] = {}
    for nid in nodes:
        k, n = subtree_evidence(forest, nid)
        u = wilson_upper(k, n)
        if u is not None:
            bound[nid] = u
    by_family: dict[str, list[float]] = defaultdict(list)
    for nid, u in bound.items():
        by_family[nodes[nid]["spec"]["family"]].append(u)
    median = {f: float(np.median(v)) for f, v in by_family.items() if v}
    out = []
    for nid, n in nodes.items():
        if n["children"] or nid not in bound:
            continue
        fam = n["spec"]["family"]
        med = median.get(fam)
        age = _age_days(n["at"], now)
        if med is None or len(by_family[fam]) < MIN_FAMILY_NODES:
            continue
        if age is None or age < abandon_days or bound[nid] <= med:
            continue
        out.append({"cell": nid, "family": fam, "symbol": n["spec"]["symbol"],
                    "fate": n["fate"], "posterior_upper": round(bound[nid], 4),
                    "family_median": round(med, 4), "age_days": round(age, 1),
                    "spec": n["spec"],
                    "why": f"the evidence still allows {bound[nid]:.2f} against a {fam} median of "
                           f"{med:.2f}, and nothing has descended from it in {age:.0f} days"})
    out.sort(key=lambda r: (-float(r["posterior_upper"]), -float(r["age_days"])))
    return sa.take(out, MAX_FINDINGS, organ=ORGAN, stage="abandoned_branches",
                   ordering="-posterior_upper, -age_days")


def declared_grids() -> dict[str, dict[str, list[Any]]]:
    """family -> the parameter grid the family DECLARES. Empty when nothing is importable."""
    try:
        from mt5desk import families as fam_mod
    except Exception:
        return {}
    out: dict[str, dict[str, list[Any]]] = {}
    for name, entry in (getattr(fam_mod, "FAMILY_REGISTRY", {}) or {}).items():
        grid = entry.get("param_grid") if isinstance(entry, dict) else None
        if isinstance(grid, dict) and grid:
            out[str(name)] = {str(k): list(v) for k, v in grid.items()
                              if isinstance(v, (list, tuple))}
    return out


def unexplored_neighbourhoods(forest: dict[str, Any], note: list[dict[str, Any]]
                              ) -> list[dict[str, Any]]:
    """Per family and knob: the declared grid values no node ever carried."""
    grids = declared_grids()
    if not grids:
        note.append({"what": "no declared parameter grids", "n": 0,
                     "why": "mt5desk.families is not importable here, so the declared bounds are "
                            "UNMEASURED and no neighbourhood can be called explored"})
        return []
    tested: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    counts: dict[str, int] = defaultdict(int)
    for n in forest["nodes"].values():
        fam = n["spec"]["family"]
        counts[fam] += 1
        for k, v in n["spec"]["params"].items():
            tested[fam][str(k)].add(json.dumps(v, sort_keys=True, default=str))
    out: list[dict[str, Any]] = []
    for family, grid in sorted(grids.items()):
        if counts.get(family, 0) < 1:
            continue
        gaps: list[dict[str, Any]] = []
        for knob, values in sorted(grid.items()):
            seen = tested[family].get(knob, set())
            untried = [v for v in values
                       if json.dumps(v, sort_keys=True, default=str) not in seen]
            if untried:
                gaps.append({"knob": knob, "untried": untried, "n_tested_values": len(seen)})
        if gaps:
            out.append({"family": family, "mechanism": ar.classify_family(family)[0],
                        "n_nodes": counts.get(family, 0), "gaps": gaps,
                        "why": f"{family} declares a grid the docket never reached on "
                               f"{', '.join(str(g['knob']) for g in gaps)}: the family's own "
                               f"bounds name the cells, and they were never built"})
    out.sort(key=lambda r: -sum(len(g["untried"]) for g in r["gaps"]))
    return sa.take(out, MAX_FINDINGS, organ=ORGAN, stage="unexplored_neighbourhoods",
                   ordering="-sum(len(gap.untried))")


def _single_axis(forest: dict[str, Any], key: str) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    ids: dict[str, list[str]] = defaultdict(list)
    out: list[dict[str, Any]] = []
    for nid, n in forest["nodes"].items():
        fam = n["spec"]["family"]
        if not fam:
            continue
        by_family[fam][str(n["spec"][key])] += 1
        ids[fam].append(nid)
    for family, seen in sorted(by_family.items()):
        n_nodes = sum(seen.values())
        if n_nodes < MIN_FAMILY_NODES or len(seen) != 1:
            continue
        only = next(iter(seen))
        out.append({"family": family, "mechanism": ar.classify_family(family)[0],
                    "n_nodes": n_nodes, key: only, "example_cell": sorted(ids[family])[0],
                    "why": f"{n_nodes} cells of {family} and every one at {key}={only!r}: the "
                           f"mechanism has never been asked whether it transfers"})
    out.sort(key=lambda r: -int(r["n_nodes"]))
    return sa.take(out, MAX_FINDINGS, organ=ORGAN, stage=f"single_axis:{key}",
                   ordering="-n_nodes")


def single_asset_mechanisms(forest: dict[str, Any]) -> list[dict[str, Any]]:
    return _single_axis(forest, "symbol")


def single_session_mechanisms(forest: dict[str, Any]) -> list[dict[str, Any]]:
    return _single_axis(forest, "session")


def shared_ancestors(forest: dict[str, Any]) -> list[dict[str, Any]]:
    """One root, two or more families: bets the allocator sizes as independent and are not."""
    nodes = forest["nodes"]
    out = []
    for root, ids in sorted(forest["roots"].items()):
        fams: dict[str, int] = defaultdict(int)
        for nid in ids:
            fam = nodes[nid]["spec"]["family"]
            if fam:
                fams[fam] += 1
        if len(fams) < 2:
            continue
        out.append({"root": root, "n_descendants": len(ids),
                    "families": dict(sorted(fams.items(), key=lambda kv: -kv[1])),
                    "example_cells": sorted(ids)[:4],
                    "why": f"{len(fams)} families descend from one ancestor; they look "
                           f"independent to the allocator and share a parameterisation"})
    out.sort(key=lambda r: (-len(r["families"]), -int(r["n_descendants"])))
    return sa.take(out, MAX_FINDINGS, organ=ORGAN, stage="shared_ancestors",
                   ordering="-len(families), -n_descendants")


# ------------------------------------------------------------------ the registry write
def _record(kind: str, key: str, mechanism: str, assets: list[str], move: dict[str, Any],
            rationale: str, payload: dict[str, Any], conn: Any) -> bool:
    did, created = reg.record_discovery(
        source_id=f"{SEAT}:{kind}:{key}", source_type=SEAT, mechanism=mechanism, origin=ORIGIN,
        generator=f"{SEAT}:{kind}", assets=assets,
        exact_rule=json.dumps(move, sort_keys=True, default=str),
        economic_rationale=rationale[:300], novelty=1.0,
        falsifier="the move is made and the child's verdict is no better than its parent's",
        payload={**payload, "finding": kind, "untried_move": move}, conn=conn)
    if created and payload.get("parent_cell"):
        with contextlib.suppress(Exception):
            reg.link("cell", str(payload["parent_cell"]), "discovery", did, f"{SEAT}:{kind}",
                     conn=conn)
    return bool(created)


def record_findings(report: dict[str, Any], conn: Any) -> tuple[int, int]:
    """Every finding becomes ONE discovery in state UNPROCESSED. Idempotent by construction: the
    registry hashes (source, mechanism, assets, rule), so a rerun on an unchanged forest creates
    nothing. Returns (created, existing)."""
    created = existing = 0

    def tally(ok: bool) -> None:
        nonlocal created, existing
        if ok:
            created += 1
        else:
            existing += 1

    for r in report["untried_mutations"]:
        for axis in r["untried"]:
            tally(_record("untried_mutation", f"{r['family']}:{axis}", r["mechanism"],
                          [str(r["example_spec"]["symbol"])],
                          {"axis": axis, "apply_to": r["example_cell"], "spec": r["example_spec"]},
                          r["why"], {"parent_cell": r["example_cell"], "family": r["family"],
                                     "axis": axis, "n_nodes": r["n_nodes"]}, conn))
    for r in report["abandoned_branches"]:
        tally(_record("abandoned_branch", str(r["cell"]),
                      ar.classify_family(r["family"])[0], [str(r["symbol"])],
                      {"axis": "any", "apply_to": r["cell"], "spec": r["spec"]}, r["why"],
                      {"parent_cell": r["cell"], "family": r["family"],
                       "posterior_upper": r["posterior_upper"],
                       "family_median": r["family_median"], "age_days": r["age_days"]}, conn))
    for r in report["unexplored_neighbourhoods"]:
        for g in r["gaps"]:
            tally(_record("unexplored_neighbourhood", f"{r['family']}:{g['knob']}", r["mechanism"],
                          [], {"axis": "parameter_neighbourhood", "family": r["family"],
                               "knob": g["knob"], "values": g["untried"]},
                          r["why"], {"parent_cell": "", "family": r["family"],
                                     "knob": g["knob"], "untried": g["untried"]}, conn))
    for kind, key in (("single_asset_mechanism", "symbol"),
                      ("single_session_mechanism", "session")):
        for r in report[kind + "s"]:
            tally(_record(kind, str(r["family"]), r["mechanism"],
                          [str(r.get("symbol") or "")] if key == "symbol" else [],
                          {"axis": "transfer" if key == "symbol" else "session",
                           "apply_to": r["example_cell"], "only": r[key]},
                          r["why"], {"parent_cell": r["example_cell"], "family": r["family"],
                                     key: r[key], "n_nodes": r["n_nodes"]}, conn))
    for r in report["shared_ancestors"]:
        tally(_record("shared_ancestor", str(r["root"])[:120], ar.UNKNOWN, [],
                      {"axis": "interaction", "root": r["root"],
                       "families": sorted(r["families"])}, r["why"],
                      {"parent_cell": r["example_cells"][0] if r["example_cells"] else "",
                       "root": r["root"], "families": r["families"]}, conn))
    return created, existing


# ------------------------------------------------------------------ build
def build(*, budget_s: float = BUDGET_S, abandon_days: float = ABANDON_DAYS,
          dry_run: bool = False) -> dict[str, Any]:
    """The report. Never raises on a missing input; an absent source is UNMEASURED, not zero."""
    t0 = time.monotonic()
    now = datetime.now(tz=UTC)
    at = now.isoformat(timespec="seconds")
    note: list[dict[str, Any]] = []
    rows = _read_jsonl(GRAPH, MAX_GRAPH_ROWS, note)
    forest = build_forest(rows)
    nodes = forest["nodes"]
    if forest["n_parent_refs"] and not forest["n_parent_resolved"]:
        note.append({"what": "no parent reference resolves to a node", "n":
                     forest["n_parent_refs"],
                     "why": "every row names a parent and not one of them is the id of another "
                            "row in this record, so the forest is one generation deep and the "
                            "mutation axes are UNMEASURED rather than untried; the writer that "
                            "appends the graph is recording the SEED it was given, not the cell "
                            "it mutated"})
        note.append({"what": "untried_mutations not searched", "n": 0,
                     "why": "with no resolvable edge anywhere, EVERY axis would read as untried "
                            "under every mechanism -- which measures the record's writer, not "
                            "the search. UNMEASURED beats a finding that is true of the file "
                            "and false of the desk"})

    verdicts = _read_jsonl(GATE_LEDGER, MAX_LEDGER_ROWS, note)
    gates: dict[str, int] = defaultdict(int)
    for v in verdicts:
        gates[str(v.get("terminal_gate") or "unknown")] += 1
    forward = _read_json(SHADOW, note)
    fwd_families: set[str] = set()
    if isinstance(forward, dict):
        for key in forward:
            fam = ar.parse_shadow_key(str(key)).get("family")
            if fam:
                fwd_families.add(str(fam))

    conn = None
    try:
        conn = reg.connect()
    except Exception as exc:
        note.append({"what": "registry unavailable", "n": 0, "why": f"{type(exc).__name__}: {exc}"})
    card_events = 0
    if conn is not None:
        try:
            card_events = len(reg.events(limit=5000, conn=conn))
        except Exception:
            card_events = 0

    edges: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    edge_totals: dict[str, int] = defaultdict(int)
    for n in nodes.values():
        p = n["parent"]
        if p not in nodes:
            continue
        axis = classify_edge(nodes[p]["spec"], n["spec"])
        family = nodes[p]["spec"]["family"] or n["spec"]["family"]
        edges[family][axis] += 1
        edge_totals[axis] += 1

    report: dict[str, Any] = {
        "at": at, "n_nodes": len(nodes), "n_roots": len(forest["roots"]),
        "depth_max": int(forest["depth_max"]),
        "n_parent_refs": int(forest["n_parent_refs"]),
        "n_parent_resolved": int(forest["n_parent_resolved"]),
        "n_edges": int(sum(edge_totals.values())), "edges_by_axis": dict(sorted(
            edge_totals.items())),
        "terminal_gates": dict(sorted(gates.items(), key=lambda kv: -kv[1])[:12]),
        "forward_families": sorted(fwd_families), "card_events": card_events,
    }
    edges_ok = bool(forest["n_parent_resolved"]) or not forest["n_parent_refs"]
    stages: tuple[tuple[str, Callable[[], list[dict[str, Any]]]], ...] = (
        ("untried_mutations", lambda: untried_mutations(forest, edges) if edges_ok else []),
        ("abandoned_branches", lambda: abandoned_branches(forest, now, abandon_days)),
        ("unexplored_neighbourhoods", lambda: unexplored_neighbourhoods(forest, note)),
        ("single_asset_mechanisms", lambda: single_asset_mechanisms(forest)),
        ("single_session_mechanisms", lambda: single_session_mechanisms(forest)),
        ("shared_ancestors", lambda: shared_ancestors(forest)))
    for name, fn in stages:
        if time.monotonic() - t0 > budget_s:
            report[name] = []
            note.append({"what": f"{name} not searched", "n": 0,
                         "why": f"the {budget_s:g}s budget ran out before this finding; "
                                "UNMEASURED, not zero"})
            continue
        report[name] = fn()

    created = existing = 0
    if conn is not None and not dry_run:
        try:
            created, existing = record_findings(report, conn)
            reg.generator_yield_update(SEAT, generated=created, conn=conn)
            reg.remember("moat", f"alpha lineage {at}: {len(nodes)} nodes, {created} new "
                                 f"discoveries, {existing} already known", kind="generator_run",
                         memory_key=f"{SEAT}:last_run",
                         metrics={"n_nodes": len(nodes), "created": created,
                                  "existing": existing},
                         payload={k: len(report.get(k) or []) for k in FINDINGS},
                         conn=conn)
        except Exception as exc:
            note.append({"what": "discoveries not recorded", "n": 0,
                         "why": f"{type(exc).__name__}: {exc}"})
    if conn is not None:
        conn.close()
    report["discoveries_recorded"] = created
    report["discoveries_existing"] = existing
    report["abandon_days"] = abandon_days
    report["budget_s"] = budget_s
    report["seconds"] = round(time.monotonic() - t0, 2)
    report["unmeasured"] = note
    report["rule"] = RULE
    return report


def _write(path: Path, doc: dict[str, Any]) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print; write no report and record no discovery")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--abandon-days", type=float, default=ABANDON_DAYS,
                    help=f"days with no descendant before a node is abandoned "
                         f"(default {ABANDON_DAYS:g})")
    a = ap.parse_args(argv)
    rep = build(budget_s=a.budget_s, abandon_days=a.abandon_days, dry_run=a.dry_run)
    print(f"ALPHA LINEAGE {rep['at']}  nodes={rep['n_nodes']} roots={rep['n_roots']} "
          f"depth_max={rep['depth_max']} edges={rep['n_edges']} "
          f"discoveries={rep['discoveries_recorded']}(+{rep['discoveries_existing']} known) "
          f"{rep['seconds']}s")
    print("  edges by axis  " + "  ".join(f"{k}={v}" for k, v in rep["edges_by_axis"].items()))
    for name in FINDINGS:
        rows = rep.get(name) or []
        head = rows[0]["why"][:80] if rows else "none found"
        print(f"  {name:<28} {len(rows):<4} {head}")
    for u in rep["unmeasured"][:5]:
        print(f"  UNMEASURED {u['what']}: {str(u['why'])[:88]}")
    if a.dry_run:
        print("  --dry-run: nothing written, no discovery recorded")
        return 0
    _write(OUT, rep)
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
