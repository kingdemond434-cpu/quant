"""D2 -- EVOLVE THE WHOLE RESEARCH RUN, at the step that actually failed, across runs.

THE PRINCIPAL, 2026-09-16 (QuantaAlpha, D2): evolve TRAJECTORIES over whole research runs, not
final formulas.

WHY IT DID NOT EXIST ALREADY. `trajectory.py` knows how to mutate the step a failure indicts;
`lineage_dag.py` knows how to assign credit, sample fertile ancestors and penalise a rut. Both are
LIBRARIES -- handed a trajectory, they act on it -- and NOTHING ON THIS TREE EVER HANDED THEM ONE.
The verdict ledger holds 3,361 judgements and the graph 23,511 judged cells, while the next
generation is minted by sweeps that have read neither: a search with a memory it does not consult.

A RESEARCH GENOME is a judged cell reassembled as the PATH that produced it -- where the idea came
from, who pays, the causal claim, what it reads, how the feature is built, when it fires, how risk
is transformed, how it exits, what would falsify it, what the gates said, and the field everything
hangs off: WHICH STEP KILLED IT.

  MUTATE at `trajectory.mutation_target(terminal_gate)` and nowhere else. `stress_costs` moves the
      HORIZON (hold it longer, so the round trip is amortised) and leaves the mechanism alone;
      `deflated_sharpe` tightens the CONDITION; `economic_prior` replaces the MECHANISM, because
      lineage_dag reads a mechanism failure as LEAVE THE BRANCH, not re-parameterise inside it.

  CROSSOVER of two DIFFERENT trajectories that failed at DIFFERENT steps, so each parent's failure
      exonerates the segment the other needs -- and only when CAUSAL COMPATIBILITY passes.
      `mechanism_ontology` is the authority wherever it holds a contract for the left mechanism:
      that contract must admit the right genome's observable, transform and horizon. Where it holds
      none, the pair must at least read the same information source. And a session-window mechanism
      never crosses with a continuous one -- the window IS the claim. A CERTIFIED genome donates
      (nothing indicted its segments) and never receives.

  FACTOR MEMORY across runs (`data/trajectory_memory.json`): children are recorded against their
      parents and every later run joins them back to the gate ledger by cell id, so
      `parent_weights` sees real fertility and a re-mined subtree yields to one nobody has touched.

TWO JUDGEMENTS ABOUT ONE DEATH, AND THEY DIFFER. `FAILURE_STEP` says which step to CHANGE;
`lineage_dag` says whether the branch's posterior MOVES. A `deflated_sharpe` death is a POWER
failure by this desk's own gate spec -- about the width of the test, not about the mechanism -- so
the condition is mutated AND the branch keeps its fertility.

NOTHING HERE PROMOTES ANYTHING: every child re-enters at the intake, walks the same ten gates, and
inherits zero credibility from a parent that certified.

    python desks/mt5/research/trajectory_evolution.py [--dry-run] [--max-children 30]
                                                      [--budget-s 240] [--seed N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import lineage_dag as ld  # noqa: E402
from libs.research import mechanism_ontology as onto  # noqa: E402
from libs.research import trajectory as tj  # noqa: E402
from libs.research.hypothesis_graph import GATE_ORDER  # noqa: E402

SOURCE = "trajectory_evolution"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SHADOW = DESK / "reports" / "shadow"
AXIS_REPORT = DESK / "reports" / "AXIS_REGISTRY.json"
MEMORY = DESK / "data" / "trajectory_memory.json"
OUT = DESK / "reports" / "TRAJECTORY_EVOLUTION.json"

#: One run's ceiling on children and the wall clock it may not pass. Caps, never targets.
MAX_CHILDREN, BUDGET_S = 30, 240
#: Genomes HELD. Every judged cell is CENSUSED; these bound only what stays in memory, because the
#: graph is 18 MB of JSON and the box holding the live terminal has 8 GB. An unattributed genome
#: seeds nothing, so a sample is enough to hold -- the COUNT of them is never sampled.
KEEP_ATTRIBUTED, KEEP_UNATTRIBUTED = 20_000, 1_000
#: Seeds drawn per run, the pool `retrieve_seeds` narrows before the weighted draw, and how
#: many certified genomes are offered as crossover DONORS.
N_SEEDS, SEED_POOL, SURVIVOR_DONORS = 24, 96, 8
UNKNOWN = "UNKNOWN"
#: A verdict whose gate nothing maps. NOT "mechanism": `mutation_target` defaults an unknown class
#: to the mechanism step, which is right for a caller that must act and wrong for a census that
#: must not invent a cause. An unmapped verdict is UNMEASURED and reported (L1.28a).
UNATTRIBUTED = "UNATTRIBUTED"
#: Gates this ledger writes that `FAILURE_STEP` does not name, read the way it reads their
#: siblings: `swap_cost` is charged over the holding period exactly as `stress_costs` is.
EXTRA_STEP: dict[str, str] = {"swap_cost": "horizon", "observations": "evidence",
                              "symbol_eligibility": "evidence"}
#: One gate `FAILURE_STEP` DOES name per step, so an EXTRA_STEP gate reaches `trajectory.mutate`
#: through a class it recognises instead of falling to that function's unknown-class default and
#: mutating the MECHANISM of a cell killed by its holding cost.
STEP_GATE: dict[str, str] = {s: g for g, s in reversed(list(tj.FAILURE_STEP.items()))}
#: Terminal gate -> the failure class `lineage_dag` reasons about. DERIVED, not invented: the
#: validity/power split is `gate_classification`'s (the desk's own gate spec) and the names are
#: `artifacts.FAILURE_CLASSES`. The test pins the two together, so a gate reclassified in the spec
#: cannot silently keep the wrong posterior here.
GATE_FAILURE_CLASS: dict[str, str] = {
    "economic_prior": "invalid_mechanism",      # validity: no cause this desk can measure
    "in_sample_screen": "insufficient_power",   # power: it did not separate AT THIS n
    "deflated_sharpe": "insufficient_power",    # power: not beyond the width of the search
    "pbo": "pbo",                               # validity: the split that worked was the fitted one
    "reality_check_spa": "multiplicity",        # validity: beaten by the best of the other trials
    "cpcv": "unstable_parameters",              # power: unstable across purged folds
    "walk_forward": "regime_instability",       # power: worked, then the world moved
    "stress_costs": "cost_failure",             # validity: the edge is inside the round trip
    "swap_cost": "cost_failure",
    "lockbox": "no_effect",                     # validity: not there in untouched data
    "expected_value": "insufficient_power",     # power: positive, not yet worth the exposure
    "untradeable": "execution_failure",
    "measurement": "invalid_mechanism",
}
#: Parameter names that express each trajectory STEP. A mutation may touch only its own step's
#: keys -- that is what makes it surgical rather than a re-roll wearing a credit assignment.
STEP_KEYS: dict[str, tuple[str, ...]] = {
    "horizon": ("ttl_bars", "hold_bars", "max_hold", "ttl", "horizon", "wait_bars"),
    "condition": ("entry_z", "z_in", "widen_z", "ratio_in", "mom_thresh", "extreme_pct",
                  "entry_p_leave", "min_age", "adx_min"),
    "measurement": ("lookback", "beta_win", "norm", "window", "lookback_weeks", "refit_days",
                    "fast", "slow", "lead_bars", "atr_n"),
}
#: Probabilities: a multiplicative bump runs them past 1, so they move additively and clip.
PCT_KEYS = frozenset({"extreme_pct", "entry_p_leave"})
RISK_KEYS = ("rr", "stop_atr", "sl_atr", "tp_atr", "atr_n", "risk_frac")
EXIT_KEYS = ("ttl_bars", "hold_bars", "max_hold", "ttl", "trail_atr", "wait_bars", "horizon")
TIMING_KEYS = ("session", "timeframe", "clock", "active_month", "entry_hour", "side_bias")
#: The only params that survive a family swap: a `peer_symbol` grafted into a family that takes no
#: peer builds a cell that tests the fallback and fails for a reason that says nothing.
CARRIER_KEYS = ("timeframe", "session")
#: Mechanisms whose economics ARE a session window.
SESSION_MECHANISMS = frozenset({"session_handover", "session_information_handoff",
                                "hedging_demand_close_flow", "fx_fixing_flow"})
#: Desk mechanism -> the `mechanism_ontology` contract that is the SAME economic claim. Three, not
#: thirty: the ontology's core list is crypto-venue shaped and this desk trades MT5, so an alias is
#: written only where the claim coincides. The rest have no contract and fall to the
#: information-source rule, the weaker admission, which says so on the row.
ONTOLOGY_ALIAS: dict[str, str] = {"execution_microstructure": "ORDER_FLOW_IMBALANCE",
                                  "cross_market_lead": "CROSS_VENUE_PRICE_DISCOVERY",
                                  "forced_liquidation": "FORCED_LIQUIDATION"}
#: Desk information source -> the observable the ontology speaks. The last three have none ON
#: PURPOSE: no registered contract licenses them, so no contract may admit them.
INFO_OBSERVABLE: dict[str, str] = {
    "price_only": "return", "cross_asset": "cross_venue_spread", "carry": "basis",
    "positioning": "open_interest", "microstructure": "order_flow_imbalance",
    "macro": "macro_surprise", "event": "event_release", "seasonality": "calendar_position"}
HORIZON_ONTOLOGY = {"intrabar": "MINUTES", "sub_4h": "HOURLY", "sub_1d": "DAILY",
                    "multi_day": "MULTI_DAY"}
RULE = ("the whole trajectory evolves at the step that failed; segments cross only under causal "
        "compatibility")


@dataclass
class Genome:
    """One judged research RUN, whole: where it came from, what it claimed, and what killed it."""

    cell: str
    node_id: str
    symbol: str
    family: str
    params: dict[str, Any]
    source_ground: str
    economic_actor: str
    causal_hypothesis: str
    information_axes: dict[str, str]
    feature_construction: dict[str, Any]
    timing_logic: dict[str, Any]
    risk_transform: dict[str, Any]
    exit_logic: dict[str, Any]
    falsifier: str
    validation_history: dict[str, Any]
    failure_stage: str
    terminal_gate: str = ""
    passed: bool = False
    born_at: str = ""
    observable: str = UNKNOWN
    transform: str = "LEVEL"
    horizon: str = ""
    concepts: tuple[str, ...] = field(default_factory=tuple)

    @property
    def info_source(self) -> str:
        return self.information_axes.get("information_source", UNKNOWN)

    @property
    def session(self) -> str:
        return str(self.timing_logic.get("session") or "all")


def _tok(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())


def _salt(*parts: Any) -> int:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2s(raw, digest_size=4).digest(), "big")


def _cell_id(symbol: Any, family: Any, params: dict[str, Any]) -> str:
    from research.frontier_identity import cell_id
    return cell_id({"sym": symbol, "family": family, "params": params})


def failure_stage_of(terminal_gate: Any, passed: bool) -> str:
    """Which STEP this verdict indicts. PASSED and UNATTRIBUTED are answers, not gaps."""
    gate = _tok(terminal_gate)
    if passed or gate == "passed":
        return "PASSED"
    return tj.mutation_target(gate) if gate in tj.FAILURE_STEP else EXTRA_STEP.get(
        gate, UNATTRIBUTED)


def _transform_of(family: str, params: dict[str, Any]) -> str:
    """The ontology transform this cell's feature construction actually applies."""
    keys = {str(k).lower() for k in params}
    fam = _tok(family).replace("_", " ")
    if any(k.endswith("_z") or k in ("entry_z", "norm", "zscore") for k in keys):
        return "ZSCORE"
    if keys & {"extreme_pct", "entry_p_leave", "band", "percentile"}:
        return "PERCENTILE"
    if "residual" in fam or "pca" in fam:
        return "RESIDUAL"
    if "cross sectional" in fam or "style premia" in fam:
        return "CROSS_SECTIONAL_RANK"
    return "DIVERGENCE" if ("correlation" in fam or "lead lag" in fam) else "LEVEL"


def _falsifier(mechanism: str, gate: str, passed: bool) -> str:
    """The ontology's falsifier where a contract exists, the failing gate where one does not."""
    m = onto.CORE_MECHANISMS.get(ONTOLOGY_ALIAS.get(mechanism, ""))
    if m is not None and m.falsifiers:
        return m.falsifiers[0]
    if passed:
        return f"the forward clock does not reproduce what {mechanism or 'the mechanism'} claimed"
    return (f"already falsified at {gate or 'an unrecorded gate'}; the child must clear that gate "
            f"before anything else is claimed")


# --------------------------------------------------------------------------- reading
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Stream a JSONL file. A bad line is skipped, an absent file yields nothing -- never raises."""
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                row = json.loads(line) if line.strip() else None
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def verdict_index() -> dict[str, dict[str, Any]]:
    """cell id -> its LAST verdict. The ledger is append-only; the last row is the present one."""
    return {str(r["cell"]): r for r in _jsonl(VERDICTS) if r.get("cell")}


def forward_index() -> dict[tuple[str, str], dict[str, Any]]:
    """(SYMBOL, family) -> forward n and exp_r, from shadow_state or the ledgers behind it."""
    from research.axis_registry import parse_shadow_key

    rows: dict[tuple[str, str], list[tuple[float, float]]] = {}
    state = _read_json(SHADOW / "shadow_state.json")
    for key, row in (state.items() if isinstance(state, dict) else ()):
        # THE LIVE FILE IS NOT ONLY CLOCKS: it carries scalar housekeeping keys beside them, so a
        # value that is not a dict is skipped rather than read as a sleeve.
        n, exp = ((row.get("n"), row.get("exp_r")) if isinstance(row, dict) else (None, None))
        if isinstance(n, (int, float)) and isinstance(exp, (int, float)) and n > 0:
            p = parse_shadow_key(str(key))
            rows.setdefault((str(p.get("symbol") or "").upper(),
                             str(p.get("family") or "session_range_breakout")),
                            []).append((float(n), float(exp)))
    for path in (sorted(SHADOW.glob("ledger_*.json")) if not rows else ()):
        parts, trades = path.stem.split("_"), _read_json(path)
        r = np.asarray([t["r_multiple"] for t in trades or [] if isinstance(t, dict)
                        and isinstance(t.get("r_multiple"), (int, float))], dtype=float)
        if len(parts) >= 3 and r.size:
            rows.setdefault((parts[1].upper(), "_".join(parts[2:-1])),
                            []).append((float(r.size), float(np.mean(r))))
    out = {}
    for key, seen in rows.items():
        arr = np.asarray(seen, dtype=float)
        out[key] = {"forward_n": int(arr[:, 0].sum()),
                    "forward_exp_r": round(float(np.average(arr[:, 1], weights=arr[:, 0])), 6)}
    return out


def genome_of(row: dict[str, Any], verdict: dict[str, Any] | None,
              forward: dict[tuple[str, str], dict[str, Any]]) -> Genome | None:
    """Assemble one genome from a graph row and the verdict that judged its cell."""
    from research.axis_registry import axis_cell

    symbol, family = str(row.get("symbol") or ""), str(row.get("family") or "")
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    if not symbol or not family:
        return None
    axes = axis_cell(symbol, family, params)
    gate = str((verdict or {}).get("terminal_gate") or "")
    passed = bool((verdict or {}).get("passed")) or row.get("fate") == "CERTIFIED"
    mech, fwd = axes["mechanism"], forward.get((symbol.upper(), family), {})
    reached = GATE_ORDER.index(_tok(gate)) if _tok(gate) in GATE_ORDER else 0
    return Genome(
        cell=_cell_id(symbol, family, params), node_id=str(row.get("id") or ""), symbol=symbol,
        family=family, params=dict(params), source_ground=str(row.get("source") or UNKNOWN),
        economic_actor=axes["economic_actor"], causal_hypothesis=mech,
        information_axes={k: axes[k] for k in ("information_source", "asset_class", "chart",
                                               "session", "horizon", "regime", "execution_style")},
        feature_construction={"family": family, "param_keys": sorted(params)},
        timing_logic={"session": axes["session"], "chart": axes["chart"],
                      "selector": {k: params[k] for k in TIMING_KEYS if k in params}},
        risk_transform={k: params[k] for k in RISK_KEYS if k in params},
        exit_logic={k: params[k] for k in EXIT_KEYS if k in params},
        falsifier=_falsifier(mech, gate, passed),
        validation_history={"terminal_gate": gate or UNKNOWN, "passed": passed,
                            "gates_passed": list(GATE_ORDER[:reached]), "n_gates_passed": reached,
                            "forward_n": fwd.get("forward_n"),
                            "forward_exp_r": fwd.get("forward_exp_r"),
                            "judged_at": str((verdict or {}).get("at") or "")},
        failure_stage=failure_stage_of(gate, passed), terminal_gate=gate or UNKNOWN, passed=passed,
        born_at=str(row.get("born_at") or row.get("at") or ""),
        observable=INFO_OBSERVABLE.get(axes["information_source"], UNKNOWN),
        transform=_transform_of(family, params),
        horizon=HORIZON_ONTOLOGY.get(axes["horizon"], ""),
        concepts=(mech, axes["information_source"], axes["horizon"], axes["execution_style"]))


def assemble(deadline: float | None = None
             ) -> tuple[list[Genome], dict[str, Any], list[dict], Counter[str]]:
    """(genomes, inputs, unmeasured, census). One genome per JUDGED cell; the graph is STREAMED.

    THE CENSUS IS UNCAPPED AND THE RETENTION IS NOT. Every judged cell is counted by its failure
    stage whether or not the genome is held, so the report's `by_failure_stage` is the desk's real
    graveyard rather than the first N rows of a file.
    """
    verdicts, forward = verdict_index(), forward_index()
    genomes: list[Genome] = []
    census: Counter[str] = Counter()
    seen: set[str] = set()
    rows = dropped = kept_un = 0
    for rows, row in enumerate(_jsonl(GRAPH), start=1):
        if deadline and not rows % 2000 and time.monotonic() > deadline:
            break
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        cell = _cell_id(row.get("symbol"), row.get("family"), params)
        if cell in seen:
            continue
        verdict = verdicts.get(cell)
        # A ROW STILL MARKED `BORN` MAY ALREADY BE JUDGED. The ledger is written hourly and the
        # graph is not, so the recent verdicts land against rows whose fate was never rewritten.
        # Skipping on the fate alone lost every cell judged since the graph's last append.
        if verdict is None and row.get("fate") == "BORN" and not row.get("gates"):
            continue
        g = genome_of(row, verdict, forward)
        if g is None:
            continue
        seen.add(cell)
        census[g.failure_stage] += 1
        if g.failure_stage == UNATTRIBUTED:
            kept_un += 1
            if kept_un > KEEP_UNATTRIBUTED:
                dropped, kept_un = dropped + 1, kept_un - 1
                continue
        elif len(genomes) - kept_un >= KEEP_ATTRIBUTED:
            dropped += 1
            continue
        genomes.append(g)
    axis = _read_json(AXIS_REPORT)
    inputs = {"hypothesis_graph": f"{rows} row(s)" if rows else f"unreadable or absent: {GRAPH}",
              "gate_verdict_ledger": (f"{len(verdicts)} cell(s)" if verdicts
                                      else f"unreadable or absent: {VERDICTS}"),
              "forward": f"{len(forward)} clock(s)" if forward else "no forward series",
              "axis_registry": (f"{axis.get('n_cells')} cell(s) at {axis.get('at')}"
                                if isinstance(axis, dict) else "absent; axes read from the module")}
    unmeasured = []
    if not genomes:
        unmeasured.append({"what": "research genomes", "why": (
            "no judged cell could be assembled from the graph and the verdict ledger; nothing was "
            "evolved, and that is a reading rather than a zero")})
    if census[UNATTRIBUTED]:
        unmeasured.append({"what": f"{census[UNATTRIBUTED]} genome(s) with no attributable failure",
                           "why": ("the terminal gate is absent or outside FAILURE_STEP: no step "
                                   "is indicted, and a guess would blame one never reached")})
    if dropped:
        unmeasured.append({"what": f"{dropped} genome(s) counted but not held",
                           "why": f"the census is whole; retention is {KEEP_ATTRIBUTED} attributed"
                                  f" and {KEEP_UNATTRIBUTED} unattributed on an 8 GB box"})
    return genomes, inputs, unmeasured, census


# --------------------------------------------------------------------------- factor memory
def load_memory() -> dict[str, Any]:
    doc = _read_json(MEMORY)
    return doc if isinstance(doc, dict) and isinstance(doc.get("genomes"), dict) else {
        "version": 1, "runs": 0, "genomes": {}}


def refresh_memory(memory: dict[str, Any], verdicts: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Join every recorded child back to the gate ledger. THIS is what closes the loop."""
    counts: Counter[str] = Counter()
    for row in (memory.get("genomes") or {}).values():
        for child in row.setdefault("children", []):
            verdict = verdicts.get(str(child.get("cell") or ""))
            if verdict is not None:
                child["outcome"] = "CERTIFIED" if verdict.get("passed") else "FAILED"
                child["terminal_gate"] = str(verdict.get("terminal_gate") or "")
            counts[child.setdefault("outcome", "UNMEASURED")] += 1
        kids = row["children"]
        row["proposed"] = len(kids)
        row["cashed"] = sum(1 for c in kids if c.get("outcome") == "CERTIFIED")
        row["recent_children"] = sum(1 for c in kids if c.get("outcome") == "UNMEASURED")
    return dict(counts)


def parent_rows(memory: dict[str, Any], genomes: list[Genome],
                ruts: dict[tuple[str, ...], dict[str, Any]]) -> list[dict[str, Any]]:
    """Weighting rows for `trajectory.parent_weights`, with the conceptual rut folded in.

    THE RUT ENTERS THROUGH NOVELTY: a genome inside one has its `recent_children` raised by the
    ruts it belongs to, so ONE definition of the weight discounts it as it discounts a mined line.
    """
    rows = []
    for g in genomes:
        mem = (memory.get("genomes") or {}).get(g.cell) or {}
        hits = sum(1 for t in ruts if set(t) <= set(g.concepts))
        rows.append({"cell": g.cell, "proposed": int(mem.get("proposed") or 0),
                     "cashed": int(mem.get("cashed") or 0), "rut_hits": hits,
                     "recent_children": int(mem.get("recent_children") or 0) + hits})
    return rows


def record_children(memory: dict[str, Any], children: list[dict[str, Any]], at: str) -> None:
    """Write each child against every parent that contributed a segment."""
    book = memory.setdefault("genomes", {})
    for child in children:
        lineage = child.get("lineage") or {}
        for parent in lineage.get("parents") or []:
            row = book.setdefault(str(parent), {"children": [], "proposed": 0, "cashed": 0,
                                                "recent_children": 0, "first_seen": at})
            kids = row.setdefault("children", [])
            if any(str(k.get("cell")) == str(child.get("cell")) for k in kids):
                continue
            kids.append({"cell": child.get("cell"), "op": lineage.get("operation"),
                         "step": lineage.get("step_mutated"), "at": at, "outcome": "UNMEASURED"})
            row.update(symbol=child.get("symbol"), family=child.get("family"), last_seen=at,
                       proposed=len(kids),
                       recent_children=sum(1 for k in kids
                                           if k.get("outcome") == "UNMEASURED"))


# --------------------------------------------------------------------------- the operators
def registered_families() -> frozenset[str]:
    """Every family this tree can actually call, read the way `breadth_sweep` reads it."""
    try:
        from research.axis_registry import registered_families as _rf
        return _rf()
    except Exception:
        return frozenset()


def refuse_reason(symbol: str, family: str, families: frozenset[str]) -> str:
    """Why this child may not be built: an unregistered or banned family, or the wrong lane."""
    try:
        from research.family_policy import family_banned
        from research.universe_policy import may_hypothesise
    except Exception:                                              # pragma: no cover - install
        return ""
    if families and family not in families:
        return "unregistered_family"
    if family_banned(family):
        return "banned_family"
    return "" if may_hypothesise(symbol) else "wrong_lane"


def compatible(a: Genome, b: Genome) -> tuple[bool, str, str]:
    """May B's segment be spliced into A's trajectory? (ok, reason_code, why)."""
    if a.causal_hypothesis in (UNKNOWN, "") or b.causal_hypothesis in (UNKNOWN, ""):
        return False, "mechanism_unknown", (
            "one side names no mechanism, so nothing says what the other's segment would join")
    if a.causal_hypothesis == b.causal_hypothesis:
        return False, "same_mechanism", (
            "two lineages of one mechanism recombine into a third variant of it -- the parameter "
            "sweep failure wearing an evolutionary costume")
    windows = [g.causal_hypothesis in SESSION_MECHANISMS or g.session != "all" for g in (a, b)]
    if windows[0] != windows[1]:
        return False, "session_window_vs_continuous", (
            "a session-window mechanism never crosses with a continuous one: the window IS the "
            "economic claim, and a continuous segment spliced into it fires for no reason")
    contract = onto.CORE_MECHANISMS.get(ONTOLOGY_ALIAS.get(a.causal_hypothesis, ""))
    if contract is not None:
        ok, why = onto.compatible(contract, observable=b.observable, transform=b.transform,
                                  horizon=b.horizon or (contract.valid_horizons or ("",))[0])
        return ok, ("ontology_admits" if ok else "ontology_refuses"), why
    if a.info_source == b.info_source and a.info_source != UNKNOWN:
        return True, "same_information_source", (
            f"no registered contract covers {a.causal_hypothesis}; both trajectories read "
            f"{a.info_source}, the weaker admission, recorded as such")
    return False, "no_common_information_source", (
        f"{a.causal_hypothesis} has no ontology contract and reads {a.info_source} while "
        f"{b.causal_hypothesis} reads {b.info_source}; nothing licenses the splice")


def _bump(value: Any, factor: float, key: str) -> Any:
    """Move one number the way the failure argues. None when it is not a number, or cannot move."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if key in PCT_KEYS:
        moved: Any = min(0.99, round(float(value) + 0.03, 4))
    elif isinstance(value, int):
        moved = max(1, round(value * factor))
    else:
        moved = round(float(value) * factor, 6)
    return moved if moved != value else None


def mutate_params(g: Genome, step: str) -> tuple[dict[str, Any] | None, str]:
    """(child params, why) for a within-family mutation at `step`. None when nothing can move."""
    params = dict(g.params)
    factor = {"horizon": 2.0, "condition": 1.25, "measurement": 1.5}.get(step, 1.25)
    for key in (*STEP_KEYS.get(step, ()), *(("rr", "tp_atr") if step == "horizon" else ())):
        moved = _bump(params.get(key), factor if key in STEP_KEYS.get(step, ()) else 1.5, key)
        if moved is not None:
            params[key] = moved
            return params, f"{step}: {key} {g.params[key]} -> {moved}"
    if step == "condition" and "session" not in params and g.information_axes["chart"] != "D1":
        params["session"] = window = ("asia", "london", "ny")[_salt(g.cell) % 3]
        return params, f"condition: unconditional -> fires only in {window}"
    return None, (f"no parameter on this cell expresses its {step}, and moving one that does not "
                  f"would change something the failure never indicted")


def other_family(g: Genome, families: frozenset[str], prefer: frozenset[str]) -> str | None:
    """A registered family implementing ANOTHER mechanism on the same information source --
    `lineage_dag.mutate_target`'s reading of a mechanism failure. Deterministic in the genome's
    own id, so a generation replays exactly."""
    from research.axis_registry import FAMILY_TABLE, family_for

    mechs = sorted({m for m, _i, _s in FAMILY_TABLE.values()} - {g.causal_hypothesis, UNKNOWN})
    start = _salt(g.cell, "mechanism") % len(mechs) if mechs else 0
    for k in range(len(mechs)):
        fam = family_for(mechs[(start + k) % len(mechs)], g.info_source, families, prefer,
                         salt=g.cell)
        if fam and fam != g.family:
            return fam
    return None


def sibling_symbol(g: Genome) -> str | None:
    """Another hypothesis-lane instrument in the same asset class -- the market-transfer child."""
    from research.axis_registry import instruments_by_class

    pool = [s for s in instruments_by_class().get(g.information_axes["asset_class"], [])
            if s.upper() != g.symbol.upper()]
    return pool[_salt(g.cell, "symbol") % len(pool)] if pool else None


def trajectory_of(g: Genome) -> tj.Trajectory:
    """The genome as a `libs.research.trajectory.Trajectory` -- what the operators act on."""
    return tj.Trajectory(
        generator=SOURCE, failure_class=_tok(g.terminal_gate),
        failed_step=g.failure_stage if g.failure_stage in tj.STEPS else "",
        steps={"evidence": {"symbol": g.symbol, "cell": g.cell,
                            "n": g.validation_history.get("forward_n")},
               "mechanism": g.causal_hypothesis, "measurement": g.info_source,
               "condition": g.feature_construction,
               "horizon": g.exit_logic or g.information_axes["horizon"],
               "implementation": g.risk_transform or None,
               "experiment": g.validation_history.get("terminal_gate")})


def _child(parents: list[Genome], op: str, step: str, symbol: str, family: str,
           params: dict[str, Any], why: str, refusals: Counter[str],
           known: set[str]) -> dict[str, Any] | None:
    """One donated row, or None with the refusal counted. Executability is checked HERE."""
    refusal = refuse_reason(symbol, family, registered_families())
    if refusal:
        refusals[refusal] += 1
        return None
    cell = _cell_id(symbol, family, params)
    if cell in known or any(cell == p.cell for p in parents):
        refusals["already_tried"] += 1
        return None
    from research.proposer_common import candidate

    head = parents[0]
    row = candidate(
        source=f"{SOURCE}:{op}", symbol=symbol, family=family, params=params,
        mechanism=head.causal_hypothesis, title=f"{op} at {step}: {symbol}.{family}",
        evidence={"why": why, "parents": [p.cell for p in parents],
                  "parent_gates": [p.terminal_gate for p in parents],
                  "parent_failure_stages": [p.failure_stage for p in parents],
                  "falsifier": head.falsifier, "economic_actor": head.economic_actor,
                  "information_axes": head.information_axes,
                  "starts_at": "IDEA -- a child inherits no credibility and walks all ten gates"})
    row["cell"] = cell
    row["lineage"] = {"parents": [p.cell for p in parents], "step_mutated": step, "operation": op}
    known.add(cell)
    return row


def mutate_child(g: Genome, refusals: Counter[str], known: set[str],
                 prefer: frozenset[str] = frozenset()) -> dict[str, Any] | None:
    """Mutate the step this genome's own death indicts, and nothing downstream of it."""
    step = g.failure_stage
    if step in ("PASSED", UNATTRIBUTED, "", "implementation", "experiment"):
        refusals["no_mutable_step"] += 1
        return None
    symbol, family, params, why = g.symbol, g.family, dict(g.params), ""
    if step == "mechanism":
        fam = other_family(g, registered_families(), prefer)
        if not fam:
            refusals["no_other_mechanism"] += 1
            return None
        family, params = fam, {k: g.params[k] for k in CARRIER_KEYS if k in g.params}
        why = (f"mechanism: {g.causal_hypothesis} was indicted at {g.terminal_gate}; the branch is "
               f"left for {fam} at its own defaults on the same information source")
    elif step == "evidence":
        sib = sibling_symbol(g)
        if not sib:
            refusals["no_sibling_instrument"] += 1
            return None
        symbol, why = sib, (f"evidence: {g.symbol} was never ownable here, so the same path is "
                            f"tried on its sibling {sib}")
    else:
        params, why = mutate_params(g, step)
        if params is None:
            refusals["no_parameter_expresses_the_step"] += 1
            return None
    gate = _tok(g.terminal_gate)
    klass = gate if gate in tj.FAILURE_STEP else STEP_GATE.get(step, "")
    child = tj.mutate(trajectory_of(g), klass,
                      {"symbol": symbol, "family": family, "params": params}, op=SOURCE)
    if child is None:
        refusals["refused_by_trajectory"] += 1
        return None
    row = _child([g], "mutate", step, symbol, family, params, why, refusals, known)
    if row is not None:
        row["lineage"].update(fingerprint=child.fingerprint(), mutation_op=child.mutation_op)
    return row


def crossover_child(a: Genome, b: Genome, refusals: Counter[str],
                    known: set[str]) -> dict[str, Any] | None:
    """Splice B's un-indicted segment into A, at the step A died of. Compatibility first."""
    step = a.failure_stage
    # THE DONOR MAY BE A SURVIVOR: a genome that passed has no failing step, which is the strongest
    # exoneration of the segment taken. A donor that broke at the SAME step exonerates nothing.
    if step not in tj.STEPS or not (b.failure_stage in tj.STEPS or b.passed):
        refusals["no_attributed_step"] += 1
        return None
    if step == b.failure_stage:
        refusals["same_failing_step"] += 1
        return None
    ok, code, why = compatible(a, b)
    if not ok:
        refusals[code] += 1
        return None
    if step == "mechanism":
        symbol, family, params = a.symbol, b.family, dict(b.params)
        how = f"{b.family}'s mechanism on {a.symbol}, the ground {a.family} could not hold"
    else:
        keys = [k for k in STEP_KEYS.get(step, ()) if k in a.params and k in b.params]
        if not keys:
            refusals["no_graftable_segment"] += 1
            return None
        symbol, family = a.symbol, a.family
        params = {**a.params, **{k: b.params[k] for k in keys}}
        how = f"{a.family} keeps everything but its {step}: {keys} taken from {b.cell}"
    child = tj.crossover(trajectory_of(a), trajectory_of(b), (step,))
    if child is None:
        refusals["refused_by_trajectory"] += 1
        return None
    row = _child([a, b], "crossover", step, symbol, family, params,
                 f"crossover at {step}: {how}. {why}", refusals, known)
    if row is not None:
        row["lineage"].update(fingerprint=child.fingerprint(), compatibility=code)
    return row


# --------------------------------------------------------------------------- the run
def lineage_graph(genomes: list[Genome], memory: dict[str, Any]) -> ld.LineageDAG:
    """Genomes as roots, their JUDGED children as descendants. Fertility needs the edges."""
    dag = ld.LineageDAG()
    index = {g.cell: g for g in genomes}
    for g in genomes:
        dag.add(ld.Node(artifact_id=g.cell, hypothesis_id=g.node_id, mechanism=g.causal_hypothesis,
                        coordinate=g.information_axes["asset_class"], concepts=g.concepts,
                        furthest_stage="CERTIFIED" if g.passed else "COMPILED", survived=g.passed,
                        failure_class=GATE_FAILURE_CLASS.get(_tok(g.terminal_gate), ""),
                        failing_step=g.failure_stage if g.failure_stage in tj.STEPS else ""))
    for parent, row in (memory.get("genomes") or {}).items():
        for kid in (row.get("children") or []) if parent in index else ():
            cell, outcome = str(kid.get("cell") or ""), str(kid.get("outcome") or "UNMEASURED")
            if not cell or cell in dag.nodes or outcome == "UNMEASURED":
                continue
            dag.add(ld.Node(artifact_id=cell, parents=(parent,), generation=1,
                            mechanism=index[parent].causal_hypothesis,
                            concepts=index[parent].concepts, survived=outcome == "CERTIFIED",
                            failure_class=GATE_FAILURE_CLASS.get(_tok(kid.get("terminal_gate")),
                                                                 "")))
    return dag


def seeds(genomes: list[Genome], memory: dict[str, Any], dag: ld.LineageDAG, k: int,
          seed: int) -> tuple[list[Genome], dict[tuple[str, ...], dict[str, Any]]]:
    """Retrieve by posterior fertility, then DRAW by fertility x uncertainty x novelty.

    `retrieve_seeds` is Thompson over the DAG's branch posteriors and narrows the graveyard to a
    pool; `draw_parents` weights that pool by the FACTOR MEMORY -- children spent, cashed, pending.
    """
    # ONLY AN ACTIONABLE GENOME IS A SEED: an unattributed death names no step, so a seat spent on
    # one learns nothing. MEASURED on the first live dry run -- four of five seeds were wasted.
    index = {g.cell: g for g in genomes if g.failure_stage in tj.STEPS}
    ruts = ld.subtree_penalty([n for n in dag.nodes.values() if not n.survived and n.failure_class])
    pool_ids = [cid for cid, _ in ld.retrieve_seeds(dag, min(SEED_POOL, len(index)), seed=seed,
                                                    candidates=list(index))] if index else []
    pool = [index[cid] for cid in pool_ids if cid in index]
    drawn = tj.draw_parents(parent_rows(memory, pool, ruts), k, seed=seed)
    by_cell = {g.cell: g for g in pool}
    return [by_cell[r["cell"]] for r in drawn if r["cell"] in by_cell], ruts


def evolve(genomes: list[Genome], memory: dict[str, Any], max_children: int, deadline: float,
           seed: int) -> dict[str, Any]:
    """One generation: seeds, surgical mutations, compatible crossovers, and every refusal."""
    refusals: Counter[str] = Counter()
    children: list[dict[str, Any]] = []
    known = {str(c.get("cell")) for row in (memory.get("genomes") or {}).values()
             for c in (row.get("children") or []) if c.get("cell")}
    dag = lineage_graph(genomes, memory)
    drawn, ruts = seeds(genomes, memory, dag, min(N_SEEDS, max(1, max_children)), seed)
    try:
        from research.axis_registry import compiler_vocab
        prefer = compiler_vocab()
    except Exception:
        prefer = frozenset()
    stopped = ""
    by_cell = {g.cell: g for g in genomes}
    pairs = [(by_cell[p["parents"][0]], by_cell[p["parents"][1]])
             for p in ld.crossover_candidates(dag, seed=seed, k=max(1, max_children))
             if p["parents"][0] in by_cell and p["parents"][1] in by_cell]
    pairs += [(drawn[i], drawn[j]) for i in range(len(drawn)) for j in range(len(drawn)) if i != j]
    #: A CERTIFIED GENOME IS A DONOR, NEVER A RECIPIENT: its segments are the only ones on the desk
    #: that nothing has indicted, and it has no failing step of its own to repair.
    pairs += [(a, s) for a in drawn for s in [g for g in genomes if g.passed][:SURVIVOR_DONORS]]
    for op, work in (("mutate", drawn), ("crossover", pairs)):
        for item in work:
            if len(children) >= max_children:
                stopped = stopped or "max_children"
                break
            if time.monotonic() > deadline:
                stopped = "budget"
                break
            row = (mutate_child(item, refusals, known, prefer) if op == "mutate"
                   else crossover_child(item[0], item[1], refusals, known))
            if row is not None:
                children.append(row)
        if stopped == "budget":
            break
    return {"children": children, "refusals": dict(refusals), "n_seeds": len(drawn),
            "stopped": stopped, "ruts": len(ruts),
            "by_operation": dict(Counter(c["lineage"]["operation"] for c in children))}


def build(*, max_children: int = MAX_CHILDREN, budget_s: int = BUDGET_S,
          seed: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """(report, children, memory). Measures and evolves; writes nothing, donates nothing."""
    started = time.monotonic()
    deadline = started + max(1, int(budget_s))
    at = datetime.now(UTC).isoformat(timespec="seconds")
    memory = load_memory()
    outcomes = refresh_memory(memory, verdict_index())
    genomes, inputs, unmeasured, census = assemble(deadline)
    run_seed = int(seed) if seed is not None else _salt(at[:10], len(genomes))
    out = evolve(genomes, memory, max(0, int(max_children)), deadline, run_seed)
    report = {
        # n_genomes is the CENSUS -- every judged cell the graph and ledger name. `genomes_held`
        # is what fitted in memory and could therefore be evolved this hour.
        "at": at, "n_genomes": int(sum(census.values())),
        "by_failure_stage": dict(sorted(census.items(), key=lambda kv: -kv[1])),
        "genomes_held": len(genomes),
        "n_seeds": out["n_seeds"], "n_children": len(out["children"]),
        "by_operation": out["by_operation"], "compatibility_refusals": out["refusals"],
        "donated": 0, "unmeasured": unmeasured, "rule": RULE, "inputs": inputs, "seed": run_seed,
        "budget_s": int(budget_s), "elapsed_s": round(time.monotonic() - started, 2),
        "stopped_early": out["stopped"], "conceptual_ruts": out["ruts"],
        "memory": {"path": str(MEMORY), "runs": int(memory.get("runs") or 0),
                   "genomes_tracked": len(memory.get("genomes") or {}),
                   "child_outcomes": outcomes},
        "children": [{"cell": c["cell"], "symbol": c["symbol"], "family": c["family"],
                      "params": c["params"], "source": c["source"], "lineage": c["lineage"]}
                     for c in out["children"]],
        "genome_schema": sorted(Genome.__dataclass_fields__)}
    return report, out["children"], memory


def donate_children(rows: list[dict[str, Any]]) -> tuple[Any, dict[str, Any]]:
    """The seam. ONE donation for both operators: `donate` names the DIRECTORY and two calls in the
    same minute would write one filename twice, so the operation rides on each row's own `source`
    (`trajectory_evolution:mutate`) -- also the only spelling NTFS accepts for a path."""
    from research.proposer_common import donate, donation_counts
    return donate(SOURCE, rows, len(rows)), donation_counts()


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only destination is legal on
    POSIX and raises WinError 5 here -- the way a VPS-tested fix once broke the box that trades."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(body, encoding="utf-8")


def run(*, dry_run: bool = False, max_children: int = MAX_CHILDREN, budget_s: int = BUDGET_S,
        seed: int | None = None) -> dict[str, Any]:
    """Evolve, donate the children, persist the factor memory, write the artifact."""
    report, children, memory = build(max_children=max_children, budget_s=budget_s, seed=seed)
    if dry_run:
        report["intake"] = "DRY RUN (nothing written, nothing donated)"
        return report
    if children:
        path, counts = donate_children(children)
        report["donated"] = int(counts.get("donated") or 0)
        report["intake"] = str(path) if path else "nothing admitted at the intake door"
        report["donation_counts"] = counts
        for key in ("refused_unstamped", "refused_wrong_lane"):
            if counts.get(key):
                report["unmeasured"].append({"what": f"{counts[key]} child(ren) {key}",
                                             "why": "refused at the donation door and counted"})
    memory["runs"] = int(memory.get("runs") or 0) + 1
    memory["updated_at"] = report["at"]
    record_children(memory, children, report["at"])
    _write_atomic(MEMORY, memory)
    _write_atomic(OUT, report)
    return report


def summary_lines(report: dict[str, Any]) -> list[str]:
    """Six lines. The rule is the last one a reader may lose."""
    def joined(d: dict, sep: str = "  ") -> str:
        return sep.join(f"{k}={v}" for k, v in d.items()) or "none"

    return [f"TRAJECTORY EVOLUTION {report['at']}  inputs: {joined(report['inputs'], ', ')}",
            f"  genomes {report['n_genomes']} judged, {report['genomes_held']} held  "
            f"{joined(report['by_failure_stage'])}",
            f"  seeds {report['n_seeds']} by fertility x uncertainty x novelty; "
            f"{report['conceptual_ruts']} conceptual rut(s) discounted",
            f"  children {report['n_children']} ({joined(report['by_operation'], ' ')})"
            f" -> donated {report['donated']}",
            f"  refusals  {joined(dict(sorted(report['compatibility_refusals'].items())))}",
            "  unmeasured  " + ("; ".join(u["what"] for u in report["unmeasured"][:3]) or "none"),
            f"  rule: {report['rule']}"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="evolve research TRAJECTORIES at the step that failed")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--max-children", type=int, default=MAX_CHILDREN)
    ap.add_argument("--budget-s", type=int, default=BUDGET_S)
    ap.add_argument("--seed", type=int, default=None, help="reproduce a generation exactly")
    a = ap.parse_args(argv)
    report = run(dry_run=a.dry_run, max_children=a.max_children, budget_s=a.budget_s, seed=a.seed)
    for line in summary_lines(report):
        print(line)
    print(f"-> {report.get('intake', OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
