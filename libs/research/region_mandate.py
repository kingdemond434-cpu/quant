"""THE REGION MANDATE FRAMEWORK -- the template every country research department instantiates.

THE PRINCIPAL'S JAPAN MANDATE (2026-09-17) is forty-seven numbered sections long and not one of
them is about Japan. Strip the nouns and what is left is a SHAPE: a mission, an objective that
multiplies seven qualities and subtracts five wastes, a region read as a complete economic system
of ACTORS under CONSTRAINTS, a list of research DOMAINS, a native-language intelligence layer, a
data-discovery swarm, a point-in-time law, a cell compiler, fourteen transformation operators, a
conversion-debt ledger, an eight-axis frontier map, a named list of specialist miners, permanent
exploration alongside permanent exploitation, failure and residual mining, twenty-five fields
every candidate must carry, dedupe across six notions of sameness, source ROI, a twenty-step loop
run HOURLY, self-improvement reporting, anti-complexity, immutable boundaries, and ZERO capital
authority. Japan first, macro second, then China, Korea, India, Australia, Europe, the UK, North
America, LatAm and Africa -- and section 46 says each region discovers its OWN mechanics rather
than inheriting Japan's.

So the mandate is written ONCE, here, region-agnostic, and a region is DATA: a `Mandate` object
in `desks/mt5/research/<region>/mandate.py` with its own actors, domains, datasets and miners.
This module is what the framework KNOWS -- the vocabularies that must not drift between regions
(the fourteen operators, the seven dispositions, the ten failure classes, the twenty-five
candidate requirements, the nine frontier states, the six point-in-time stamps, the twenty loop
steps) and the measurements every region owes: conversion registers, the frontier map, saturation
per axis, source ROI, research ROI and the dashboard.

WHAT IS DELIBERATELY ABSENT. No capital, no sizing, no gate threshold, no promotion. A region
department's output TERMINATES at a GAUNTLET_READY_CANDIDATE (section 42) and `validate` refuses
any mandate that claims otherwise. `assert_boundaries` refuses a policy knob that so much as NAMES
point-in-time, trial accounting, multiple testing, a sealed holdout, a gauntlet threshold, forward
evidence, a cost assumption or provenance -- the same wall `research_os_archive` puts around the
judge, for the same reason: a search permitted to reach its own judge eventually finds that
lowering the bar is cheaper than clearing it.

AND RAW CANDIDATE COUNT HAS ZERO VALUE (section 1). Every number this module publishes is a
DENOMINATOR-HONEST one: cells with a disposition over cells that exist, new distinct values per
discovery rather than discoveries, independent survivors per compute hour rather than candidates
per hour. A region that donates ten thousand near-identical USDJPY H1 cells has produced nothing,
and `frontier` is built so that it reads as nothing -- the empty valuable cell outranks the
fiftieth sibling by construction.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from libs.moat import registry as R

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The executable universe. Module-level so a test can point it somewhere else; read fresh (with
#: an mtime cache) because the broker registry is rewritten by the collector while the desk runs.
UNIVERSE_JSON: Path = DESK / "data" / "universe" / "universe.json"

# --------------------------------------------------------------------------- the vocabularies
#: Section 1. The objective is a PRODUCT of seven qualities summed over candidates, minus five
#: wastes. Raw candidate count appears in neither list, and that is the whole point of it.
OBJECTIVE_TERMS: tuple[str, ...] = ("P_edge", "novelty", "orthogonality",
                                    "economic_mechanism_quality", "data_readiness",
                                    "pit_integrity", "executability")
MINIMISE_TERMS: tuple[str, ...] = ("duplicates", "data_leakage", "unsupported_claims",
                                   "search_waste", "complexity")

#: Section 2. The eleven things a mandate must be able to say about an economic actor before the
#: chain Actor -> Constraint -> Observable -> Flow -> MarketImpact -> Candidate can be walked.
ACTOR_FIELDS: tuple[str, ...] = ("holds", "forced_to", "when", "information", "constraints",
                                 "instruments", "counterparties", "observables", "impact",
                                 "persistence", "falsifier")
RESEARCH_TARGET: tuple[str, ...] = ("actor", "constraint", "observable", "flow", "market_impact",
                                    "candidate")

#: Section 23. Fourteen transformation operators. ORIGINAL is one of them: the untransformed cell
#: is a child like any other and must receive a disposition like any other.
OPERATORS: tuple[str, ...] = (
    "ORIGINAL", "INVERSE", "ASSET_TRANSFER", "CROSS_ASSET", "SESSION_TRANSFER",
    "HORIZON_TRANSFER", "REGIME_CONDITION", "RESIDUALIZATION", "FACTOR_NEUTRALIZATION",
    "EVENT_CONDITION", "POSITIONING_CONDITION", "VOLATILITY_CONDITION", "EXECUTION_VARIANT",
    "MECHANISM_COMBINATION")

#: Section 23, the other half: every operator receives EXACTLY ONE of these, and silence is not
#: one of them. `possible - generated - blocked` is the subtraction that finds a silent omission.
DISPOSITIONS: tuple[str, ...] = ("GENERATED", "DUPLICATE", "ECONOMICALLY_INVALID", "DATA_BLOCKED",
                                 "PIT_BLOCKED", "COST_BLOCKED", "ALREADY_TESTED")
#: The dispositions that mean a child LEFT the compiler. Everything else is owed an explanation.
PRODUCTIVE_DISPOSITIONS: tuple[str, ...] = ("GENERATED",)

#: Section 29. The region's failure vocabulary, and its bridge to the registry's own, so a region
#: verdict and a desk verdict are the same fact in two spellings rather than two facts.
#: DATA_PROBLEM -> `unstable` is the loosest of the ten and it is named as such: the registry has
#: no data class, and `unstable` is its nearest ("the measurement did not reproduce"). The other
#: nine are exact.
FAILURE_CLASSES_REGION: tuple[str, ...] = (
    "NO_EFFECT", "WRONG_DIRECTION", "COST_KILLED", "REGIME_DEPENDENT", "HORIZON_MISMATCH",
    "ASSET_MISMATCH", "EXECUTION_FAILURE", "REDUNDANT", "DATA_PROBLEM", "STRUCTURAL_DECAY")
FAILURE_TO_REGISTRY: dict[str, str] = {
    "NO_EFFECT": "no_edge", "WRONG_DIRECTION": "wrong_direction", "COST_KILLED": "cost_killed",
    "REGIME_DEPENDENT": "regime_specific", "HORIZON_MISMATCH": "wrong_horizon",
    "ASSET_MISMATCH": "wrong_asset", "EXECUTION_FAILURE": "execution_killed",
    "REDUNDANT": "redundant", "DATA_PROBLEM": "unstable", "STRUCTURAL_DECAY": "forward_decay",
}
#: Section 29 again: a failure is EXPLOITED, not filed. These classes name the transformation
#: that is JUSTIFIED by the death; the others (NO_EFFECT, REDUNDANT, STRUCTURAL_DECAY) justify
#: nothing, and inventing a descendant for them is search waste wearing a lineage.
FAILURE_DESCENDANT: dict[str, str] = {
    "WRONG_DIRECTION": "INVERSE", "COST_KILLED": "EXECUTION_VARIANT",
    "REGIME_DEPENDENT": "REGIME_CONDITION", "HORIZON_MISMATCH": "HORIZON_TRANSFER",
    "ASSET_MISMATCH": "ASSET_TRANSFER", "EXECUTION_FAILURE": "EXECUTION_VARIANT",
    "DATA_PROBLEM": "RESIDUALIZATION",
}

#: Section 33. Twenty-five fields. An incomplete candidate STAYS UPSTREAM -- it is not a weaker
#: candidate, it is a discovery that has not finished becoming one.
REQUIREMENTS: tuple[str, ...] = (
    "candidate_id", "parent_discovery", "canonical_source", "original_language", "mechanism",
    "economic_actor", "constraint", "counterparty", "causal_rationale", "symbol", "chart",
    "session", "horizon", "regime", "exact_entry", "exact_exit", "parameters", "required_data",
    "pit_status", "expected_costs", "capacity", "negative_control", "falsifier", "trial_family",
    "search_count_lineage")
#: How the desk's existing writers spell the same field. A requirement satisfied under another
#: name is SATISFIED; a requirement missing under every name it has ever had is missing.
REQUIREMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "candidate_id": ("id", "cell", "cell_id"),
    "parent_discovery": ("discovery_id", "parent_ids", "parent_discovery_ids", "parent"),
    "canonical_source": ("source_id", "source_url", "source", "url"),
    "original_language": ("language", "lang"),
    "constraint": ("constraint_text",),
    "symbol": ("sym", "instrument"),
    "chart": ("timeframe", "tf"),
    "exact_entry": ("entry_logic", "entry", "exact_rules", "exact_rule"),
    "exact_exit": ("exit_logic", "exit", "exact_rules", "exact_rule"),
    "parameters": ("params", "params_json"),
    "required_data": ("required_data_json", "needs"),
    "expected_costs": ("expected_cost", "cost_estimate"),
    "capacity": ("expected_capacity", "capacity_usd"),
    "negative_control": ("control", "placebo"),
    "trial_family": ("family",),
    "search_count_lineage": ("search_count", "lineage", "lineage_json"),
}

#: Section 25. The frontier's nine states, in PRECEDENCE ORDER: a later state outranks an earlier
#: one when two sources describe the same cell, because what HAPPENED beats what is possible.
FRONTIER_STATES: tuple[str, ...] = ("UNSEEN", "DISCOVERED", "DATA_BLOCKED", "COMPILED",
                                    "SCREENED", "FAILED", "SURVIVED", "FORWARD", "LIVE")
FRONTIER_RANK: dict[str, int] = {s: i for i, s in enumerate(FRONTIER_STATES)}
#: The eight axes of section 25. NOT the registry's eight (which carry chart and no constraint):
#: a region's question is "which actor, under which constraint" and the constraint axis is the
#: one that makes the map a map of ECONOMICS rather than of parameter slots.
FRONTIER_AXES: tuple[str, ...] = ("asset", "actor", "constraint", "mechanism", "information",
                                  "session", "horizon", "regime")
#: A populated cell is one somebody actually reached; the rest are the ground the region owes.
POPULATED_STATES: tuple[str, ...] = ("COMPILED", "SCREENED", "FAILED", "SURVIVED", "FORWARD",
                                     "LIVE")
#: How close a hole is to being askable. DATA_BLOCKED is discounted, never zeroed: acquiring the
#: series is a real path, a slower one (the same weighting `research_gap_map` uses).
HOLE_READINESS: dict[str, float] = {"DISCOVERED": 1.0, "UNSEEN": 0.6, "DATA_BLOCKED": 0.25}

#: Section 21. The six stamps. A row that cannot carry all six is NOT_PIT_SAFE, and NOT_PIT_SAFE
#: is a disposition (PIT_BLOCKED), never a silent drop.
PIT_FIELDS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")
PIT_SAFE, PIT_UNSAFE, PIT_UNKNOWN = "PIT_SAFE", "NOT_PIT_SAFE", "UNKNOWN"

#: Section 38. Twenty steps, hourly -- "exploit hourly, not daily" (the principal). The ORDER is
#: load-bearing: verdicts arrive before priors update, priors before descendants, descendants
#: before the next pass compiles them.
LOOP_STEPS: tuple[str, ...] = (
    "ingest_sources", "update_source_graph", "ingest_datasets", "update_policy_event_state",
    "discover_mechanisms", "update_frontier", "exploit_mechanisms", "mine_failures",
    "mine_residuals", "inspect_conversion_debt", "inspect_research_debt", "compile_cells",
    "dedupe", "score_orthogonality", "rank_queue", "submit_to_gauntlet", "ingest_verdicts",
    "update_priors", "create_descendants", "simplify")

#: Section 26/37. What kind of specialist a miner is; the runner routes each kind to its step.
MINER_KINDS: tuple[str, ...] = ("mechanism", "scout", "data", "failure", "residual", "transfer",
                                "calendar")

#: Section 34. The six notions of sameness a region dedupes across. Named here so a region that
#: only checks the content hash is visibly checking one of six.
DEDUPE_AXES: tuple[str, ...] = ("semantic", "mechanism", "structural", "factor", "return",
                                "ancestry")

#: Section 44. Saturation is MEASURED PER AXIS, never assumed, and never for the region as a whole
#: -- "we have mined Japan" is not a claim anybody can cash.
SATURATION_AXES: tuple[str, ...] = ("source", "language", "actor", "mechanism", "asset", "dataset",
                                    "session", "horizon")
SATURATION_VERDICTS: tuple[str, ...] = ("saturated", "unsaturated", "poorly_measured",
                                        "data_blocked", "UNMEASURED")
#: The discovery curve's two windows (section 44) and the thresholds that read it.
SATURATION_WINDOW_DAYS = 7
#: Below this many rows in the recent window the axis is POORLY MEASURED -- a verdict about the
#: measurement, not about the ground.
SATURATION_MIN_ROWS = 5
#: New distinct values per discovery at or below this, AND at or below half the earlier window's
#: rate, reads as saturated. Two conditions, because a rate that was always low was never mined.
SATURATION_RATE = 0.10
SATURATION_DECAY = 0.5

#: Section 41. The eight boundaries no region policy, miner, knob or mutation may reach.
IMMUTABLE_BOUNDARIES: tuple[str, ...] = (
    "point-in-time discipline", "trial accounting", "multiple-testing correction",
    "sealed holdouts", "gauntlet thresholds", "forward evidence", "cost assumptions",
    "provenance")
#: The spellings a knob would actually use. Matched on WORD boundaries, not substrings: "capital"
#: contains "pit" and refusing it would be a checker that cannot be trusted about anything.
BOUNDARY_TOKENS: tuple[str, ...] = (
    "pit", "point in time", "pit lag", "pit status", "lookahead", "look ahead", "available time",
    "publication lag", "trial accounting", "trial count", "trial charge", "trials ledger",
    "multiple testing", "family wise", "deflated sharpe", "sealed holdout", "holdout",
    "gauntlet threshold", "gate threshold", "promotion threshold", "forward evidence",
    "forward clock", "cost assumption", "actual cost", "actual fill", "spread assumption",
    "provenance", "source provenance", "capital", "lot size", "heat floor", "risk per trade")

#: Section 42. The one output a region department is allowed to produce.
TERMINAL_OUTPUT = "GAUNTLET_READY_CANDIDATE"

#: Section 43. The dashboard's fields, declared so a renderer and a test read the same list.
DASHBOARD_FIELDS: tuple[str, ...] = (
    "region", "at", "capital_authority", "terminal_output", "registers", "frontier_by_state",
    "frontier_holes", "saturation", "roi_by_source", "research_roi", "discoveries_recent",
    "mechanisms", "valid_cells", "compiled", "queued", "tested", "blocked", "unexplained_debt",
    "duplicates", "survivors", "deaths", "miners", "unmeasured", "rule")

#: The frontier's closed axis vocabularies. Small on purpose: the product of eight open axes is
#: astronomical and mostly meaningless, and a map nobody can read ranks nothing.
SESSIONS: tuple[str, ...] = ("tokyo", "london", "ny", "all")
HORIZONS: tuple[str, ...] = ("intraday", "overnight", "multi_day")
REGIMES: tuple[str, ...] = ("unconditional", "high_volatility", "risk_off")
#: Enumeration caps, stated as the COMPUTE BUDGETS they are. A truncated frontier says so.
MAX_MECHANISMS = 12
MAX_FRONTIER_CELLS = 20_000
MAX_ROWS = 20_000
TOP_HOLES = 40

#: Section 45. There is no permanent completion, and the artifact says so in its own body.
RULE = ("a region is never finished: saturation is measured per axis and expires, the frontier's "
        "empty valuable cells are the work, and the department's output terminates at a "
        "gauntlet-ready candidate with zero capital authority")

#: Asset-class spellings that may never enter a region's hypothesis instruments (the two-lane
#: mandate, 2026-09-06). Single names are traded on disclosures and hunted by nothing here.
EQUITY_CLASSES: frozenset[str] = frozenset({
    "equities", "equity", "equities us", "shares", "share", "stock", "stocks", "us shares"})


class BoundaryBreach(ValueError):
    """Raised when a region policy names something the region may never move."""


# --------------------------------------------------------------------------- the objects
@dataclass(frozen=True)
class Actor:
    """Section 2. One participant of the region's economic system, described completely enough
    that the chain Actor -> Constraint -> Observable -> Flow -> MarketImpact -> Candidate can be
    walked without inventing a link. Every one of the eleven content fields must be non-empty:
    an actor whose FALSIFIER is blank is a story, and a story is not a research object."""

    name: str
    holds: str = ""
    forced_to: tuple[str, ...] = ()
    when: str = ""
    information: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    counterparties: tuple[str, ...] = ()
    observables: tuple[str, ...] = ()
    impact: str = ""
    persistence: str = ""
    falsifier: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Domain:
    """Sections 3..17. One mandatory research domain: what it studies, what it conditions on,
    what it may trade and -- never optional -- what its NEGATIVE CONTROLS are."""

    id: str
    title: str = ""
    objects: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class DatasetSpec:
    """Section 20. One entry of the data-discovery swarm's catalogue. `pit_feasible` is the field
    the whole catalogue exists for: a dataset whose six stamps cannot be reconstructed is not a
    slower dataset, it is a dataset that can only produce NOT_PIT_SAFE cells."""

    name: str
    source: str = ""
    coverage: str = ""
    frequency: str = ""
    publication_lag_days: float = 0.0
    revisions: str = ""
    licence: str = ""
    history_from: str = ""
    pit_feasible: bool = False
    assets: tuple[str, ...] = ()
    mechanism_families: tuple[str, ...] = ()
    how_to_fetch: str = ""


@dataclass(frozen=True)
class MinerSpec:
    """Section 26. A named specialist. `entry` is a dotted "module:function" or a CLI path, so a
    miner can be an in-process callable or a script; `steerable` says whether the department may
    re-budget it by measured ROI, or whether it is a fixed cost (a calendar that must be read
    every pass regardless of what it yielded last week)."""

    name: str
    domain_ids: tuple[str, ...] = ()
    kind: str = "mechanism"
    entry: str = ""
    cadence_s: float = 3600.0
    steerable: bool = True
    notes: str = ""


@dataclass(frozen=True)
class Mandate:
    """One region's whole standing order, as data. Region-agnostic by construction: nothing in
    this class knows what Japan is, and section 46 requires that each region discover its own
    mechanics rather than inherit another's."""

    region: str
    mission: str = ""
    objective_terms: tuple[str, ...] = OBJECTIVE_TERMS
    minimise_terms: tuple[str, ...] = MINIMISE_TERMS
    actors: tuple[Actor, ...] = ()
    domains: tuple[Domain, ...] = ()
    instruments: tuple[str, ...] = ()
    native_languages: tuple[str, ...] = ()
    terminology: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    source_classes: tuple[str, ...] = ()
    datasets: tuple[DatasetSpec, ...] = ()
    miners: tuple[MinerSpec, ...] = ()
    loop_steps: tuple[str, ...] = LOOP_STEPS
    immutable_boundaries: tuple[str, ...] = IMMUTABLE_BOUNDARIES
    capital_authority: bool = False
    controls_default: tuple[str, ...] = ()


# --------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _tok(value: Any) -> str:
    """One axis value's canonical spelling: lowercase, single-underscore, never blank."""
    text = " ".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())
    return text.replace(" ", "_") or "unknown"


def norm(value: Any) -> str:
    """The public spelling of the axis normaliser, so another organ names a cell the same way."""
    return _tok(value)


def _words(value: Any) -> list[str]:
    return " ".join(str(value or "").lower().replace("-", " ").replace("_", " ").split()).split()


def _jload(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except ValueError:
            return None
    return None


def _first(value: Any, default: str = "unknown") -> str:
    doc = _jload(value)
    if isinstance(doc, list) and doc:
        return _tok(doc[0])
    if isinstance(doc, dict) and doc:
        return _tok(next(iter(doc)))
    if isinstance(value, str) and value.strip():
        return _tok(value)
    return default


def _as_list(value: Any) -> list[str]:
    doc = _jload(value)
    if isinstance(doc, list):
        return [_tok(v) for v in doc if str(v or "").strip()]
    if isinstance(doc, dict):
        return [_tok(k) for k in doc]
    if isinstance(value, str) and value.strip():
        return [_tok(value)]
    return []


def _rows_of(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


_UNIVERSE_CACHE: dict[str, Any] = {}


def universe() -> dict[str, dict[str, Any]]:
    """The broker's own registry, or {} when it is not on this box. ABSENCE IS NOT PERMISSION and
    it is not a refusal either: a mandate is validated against the universe WHEN IT IS PRESENT,
    and `resolve_instruments` reports which of the two happened."""
    path = Path(UNIVERSE_JSON)
    try:
        st = path.stat()
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        _UNIVERSE_CACHE.clear()
        return {}
    if _UNIVERSE_CACHE.get("key") == key:
        cached: dict[str, dict[str, Any]] = _UNIVERSE_CACHE["doc"]
        return cached
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = ({str(k): v for k, v in doc.items() if isinstance(v, dict)}
                                      if isinstance(doc, dict) else {})
    _UNIVERSE_CACHE.clear()
    _UNIVERSE_CACHE.update({"key": key, "doc": out})
    return out


def resolve_instruments(m: Mandate) -> dict[str, Any]:
    """Which of a mandate's instruments the box can actually execute, and which are equities.

    THE TWO-LANE MANDATE IS ENFORCED HERE (principal, 2026-09-06). A region department mints
    STATISTICAL hypotheses, so a single-name equity in its instrument list is not a breadth
    choice: it spends the shared multiple-testing budget on the asset class least suited to the
    method, and every FX and metals cell in the program pays for it."""
    reg = universe()
    known: list[str] = []
    unknown: list[str] = []
    equities: list[str] = []
    for sym in m.instruments:
        row = reg.get(sym)
        if reg and row is None:
            unknown.append(sym)
            continue
        raw = str((row or {}).get("asset_class") or "").lower().replace("_", " ")
        klass = " ".join(raw.split())
        if klass in EQUITY_CLASSES:
            equities.append(sym)
        else:
            known.append(sym)
    return {"resolved": known, "unknown": unknown, "equities": equities,
            "universe": "ABSENT" if not reg else str(UNIVERSE_JSON),
            "measured": bool(reg)}


# --------------------------------------------------------------------------- validation
def validate(m: Mandate) -> list[str]:
    """Every way this mandate is not yet a mandate, named. An empty list is the only pass.

    The checks are the sections that cannot be skipped without the rest becoming decorative: an
    actor missing a field breaks the research target chain (2), a domain without controls cannot
    tell an effect from its own selection (31), a miner pointing at no domain is compute with no
    question (26/37), capital authority is refused outright (42), the loop is the loop (38), and
    an instrument that does not resolve is a cell that can never be compiled (20/22)."""
    problems: list[str] = []
    if not str(m.region).strip():
        problems.append("region: empty; every row this department writes is tagged with it")
    if not str(m.mission).strip():
        problems.append("mission: empty (section 0)")
    if tuple(m.objective_terms) != OBJECTIVE_TERMS:
        problems.append(f"objective_terms: must be {list(OBJECTIVE_TERMS)} (section 1); "
                        f"raw candidate count is not a term and never becomes one")
    if tuple(m.minimise_terms) != MINIMISE_TERMS:
        problems.append(f"minimise_terms: must be {list(MINIMISE_TERMS)} (section 1)")
    if m.capital_authority:
        problems.append("capital_authority: a region department has ZERO capital authority "
                        f"(section 42); its output terminates at {TERMINAL_OUTPUT}")
    if tuple(m.loop_steps) != LOOP_STEPS:
        problems.append(f"loop_steps: must be the twenty steps of section 38 in order; got "
                        f"{len(m.loop_steps)} step(s)")
    if not m.actors:
        problems.append("actors: empty; a region with no actors has no mechanism to find "
                        "(section 2)")
    if not m.domains:
        problems.append("domains: empty; sections 3..17 are mandatory research domains")

    seen_actors: set[str] = set()
    for a in m.actors:
        if not str(a.name).strip():
            problems.append("actor: an actor with no name")
            continue
        if a.name in seen_actors:
            problems.append(f"actor {a.name}: declared twice")
        seen_actors.add(a.name)
        for f_name in ACTOR_FIELDS:
            value = getattr(a, f_name, None)
            empty = (value is None or (isinstance(value, str) and not value.strip())
                     or (isinstance(value, (tuple, list)) and len(value) == 0))
            if empty:
                problems.append(f"actor {a.name}: {f_name} is empty; all eleven fields of "
                                f"section 2 are required")

    domain_ids = {d.id for d in m.domains}
    for d in m.domains:
        if not str(d.id).strip():
            problems.append("domain: a domain with no id")
        if not d.controls and not m.controls_default:
            problems.append(f"domain {d.id}: no negative controls and no controls_default "
                            f"(section 31: a negative control per effect)")
        if not d.objects:
            problems.append(f"domain {d.id}: no research objects")

    seen_miners: set[str] = set()
    for mi in m.miners:
        if not str(mi.name).strip():
            problems.append("miner: a miner with no name")
            continue
        if mi.name in seen_miners:
            problems.append(f"miner {mi.name}: declared twice")
        seen_miners.add(mi.name)
        if mi.kind not in MINER_KINDS:
            problems.append(f"miner {mi.name}: kind {mi.kind!r} is not one of {list(MINER_KINDS)}")
        if not mi.domain_ids:
            problems.append(f"miner {mi.name}: names no domain; compute with no question "
                            f"(section 37)")
        for did in mi.domain_ids:
            if did not in domain_ids:
                problems.append(f"miner {mi.name}: names unknown domain {did!r}; declared: "
                                f"{sorted(domain_ids)}")
        if float(mi.cadence_s) <= 0:
            problems.append(f"miner {mi.name}: cadence_s must be positive")

    names = {d.name for d in m.datasets}
    if len(names) != len(m.datasets):
        problems.append("datasets: two entries share a name")
    for ds in m.datasets:
        if float(ds.publication_lag_days) < 0:
            problems.append(f"dataset {ds.name}: negative publication_lag_days")

    if not m.instruments:
        problems.append("instruments: empty; the region can compile no cell")
    res = resolve_instruments(m)
    for sym in res["unknown"]:
        problems.append(f"instrument {sym}: not in the broker universe at {UNIVERSE_JSON}")
    for sym in res["equities"]:
        problems.append(f"instrument {sym}: single-name equity; the two-lane mandate "
                        f"(2026-09-06) forbids hunting it for statistical hypotheses")
    return problems


def assert_boundaries(policy: Mapping[str, Any]) -> None:
    """THE WALL (section 41). A region may change its own hypothesis; it may never reach its judge.

    Raises BoundaryBreach naming the knob and the boundary. Every key and every string value is
    scanned, on WORD boundaries -- a substring check refuses `capacity` for containing "pit" and a
    checker that cries wolf is a checker nobody keeps.
    """
    if not isinstance(policy, Mapping):
        raise BoundaryBreach(f"a region policy must be a mapping, got {type(policy).__name__}")
    token_words = [tuple(t.split()) for t in BOUNDARY_TOKENS]
    for where, text in _walk_strings(policy):
        words = _words(text)
        for tw in token_words:
            n = len(tw)
            if any(tuple(words[i:i + n]) == tw for i in range(0, max(0, len(words) - n + 1))):
                raise BoundaryBreach(
                    f"{where} names {text!r}, which touches the immutable boundary "
                    f"{' '.join(tw)!r}. Point-in-time, trial accounting, multiple testing, "
                    f"sealed holdouts, gauntlet thresholds, forward evidence, cost assumptions "
                    f"and provenance are what a region is JUDGED by; a search allowed to move "
                    f"them lowers its own bar.")


def _walk_strings(obj: Any, path: str = "policy") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            out.append((f"{path}.{k}", str(k)))
            out.extend(_walk_strings(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.extend(_walk_strings(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        out.append((path, obj))
    return out


# --------------------------------------------------------------------------- identity
def tag(m: Mandate) -> str:
    """The prefix every row this region writes carries: generator, source id, worker, artifact."""
    return f"{_tok(m.region)}:"


def region_match(m: Mandate, row: Mapping[str, Any]) -> str | None:
    """WHICH criterion makes this row the region's, or None. Named rather than boolean because
    the registers built on it must be able to say how they were filtered -- a register that
    counts every USDJPY row on the box because one criterion is broad is a register whose
    denominator nobody can check."""
    t = tag(m)
    for key in ("generator", "source_id", "source_type", "origin", "department", "claimed_by",
                "worker_id"):
        v = row.get(key)
        if isinstance(v, str) and v.lower().startswith(t):
            return f"prefix:{key}"
    if _tok(row.get("region")) == _tok(m.region):
        return "row.region"
    for key in ("payload_json", "payload", "extra_json", "lineage_json"):
        doc = _jload(row.get(key))
        if isinstance(doc, dict) and _tok(doc.get("region")) == _tok(m.region):
            return f"{key}.region"
    syms = {s.upper() for s in m.instruments}
    sym = str(row.get("symbol") or row.get("sym") or "").upper()
    if sym and sym in syms:
        return "symbol"
    for a in _as_list(row.get("assets_json") or row.get("assets")):
        if a.upper() in syms:
            return "assets"
    return None


def is_region_row(m: Mandate, row: Mapping[str, Any]) -> bool:
    """Is this registry row the region's? Generator/source prefix, a declared region in the
    payload, or an instrument the mandate names."""
    return region_match(m, row) is not None


#: The criteria that mean a row is the region's OWN work, as opposed to merely being about an
#: instrument the mandate names. Measured 2026-09-22 on the Japan department: `is_region_row`
#: admitted every queued candidate on USDJPY, XAUUSD and JPN225 -- 1,704 rows, none of them
#: Japan's -- so the department ranked the whole desk's queue, held every row upstream for the
#: ten section-33 fields its own miners had written into their DISCOVERY payloads, and claimed
#: nothing, every pass. Ownership is prefix or declared region; the instrument is a register axis.
OWN_CRITERIA: frozenset[str] = frozenset({
    "prefix:generator", "prefix:source_id", "prefix:source_type", "prefix:origin",
    "prefix:department", "prefix:claimed_by", "prefix:worker_id", "row.region",
    "payload_json.region", "payload.region", "extra_json.region", "lineage_json.region"})


def is_own_row(m: Mandate, row: Mapping[str, Any]) -> bool:
    """The region's OWN row: a generator/source prefix or a declared region, never the symbol."""
    return region_match(m, row) in OWN_CRITERIA


def disposition_of(blocked_reason: str | None, state: str) -> str:
    """ONE of the seven dispositions for every operator, every time (section 23).

    The compiler's refusal vocabulary is `economic:`, `data:`, `novelty:` with a parenthesised
    detail, and two of those prefixes carry POSITIVE verdicts too (`data:ok (PIT_SAFE)`,
    `novelty:new (cell)`), so the prefix alone is not the answer. A reason the vocabulary does
    not recognise maps to ECONOMICALLY_INVALID rather than to GENERATED: a reason existing at all
    means the child did not leave, and the one mapping this function may never make is "I do not
    know why it stopped, so call it produced".
    """
    reason = " ".join(str(blocked_reason or "").strip().lower().split())
    st = str(state or "").strip().upper()
    if not reason:
        if st == "TESTED":
            return "ALREADY_TESTED"
        return "GENERATED"
    if reason.startswith("novelty:"):
        if "new" in reason:
            return "GENERATED"
        # `exact_twin_already_enqueued` carries the word "already" and is NOT ALREADY_TESTED: a
        # twin sitting in the queue has been GENERATED once, never judged. Only "tested" says the
        # judge has spoken, and the two are different facts about the same cell.
        if "tested" in reason:
            return "ALREADY_TESTED"
        return "DUPLICATE"
    if reason.startswith("data:"):
        if reason.startswith("data:ok"):
            return "GENERATED"
        if "pit" in reason:
            return "PIT_BLOCKED"
        return "DATA_BLOCKED"
    if reason.startswith("economic:"):
        return "ECONOMICALLY_INVALID"
    if reason.startswith("cost:") or "cost" in reason or "spread" in reason:
        return "COST_BLOCKED"
    if reason.startswith("pit") or "pit" in reason or "lookahead" in reason:
        return "PIT_BLOCKED"
    if "duplicate" in reason or "twin" in reason or "redundant" in reason:
        return "DUPLICATE"
    if "already" in reason or "tested" in reason:
        return "ALREADY_TESTED"
    if "data" in reason or "bars" in reason or "missing" in reason or "absent" in reason:
        return "DATA_BLOCKED"
    return "ECONOMICALLY_INVALID"


def candidate_complete(c: Mapping[str, Any]) -> list[str]:
    """Which of the twenty-five requirements this candidate is missing (section 33).

    An incomplete candidate STAYS UPSTREAM. It is not donated, not ranked and not claimed -- the
    missing field is the work, and a candidate admitted without its falsifier or its negative
    control is a trial the desk cannot interpret whichever way it comes out."""
    missing: list[str] = []
    for req in REQUIREMENTS:
        keys = (req, *REQUIREMENT_ALIASES.get(req, ()))
        ok = False
        for k in keys:
            v = c.get(k)
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            if isinstance(v, (list, tuple, dict)) and len(v) == 0:
                continue
            ok = True
            break
        if not ok:
            missing.append(req)
    return missing


# --------------------------------------------------------------------------- the registers
def _region_discoveries(m: Mandate, c: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _rows_of(c.execute("SELECT * FROM discoveries ORDER BY created_at LIMIT ?", (MAX_ROWS,)))
    return [r for r in rows if is_region_row(m, r)]


def _region_candidates(m: Mandate, c: sqlite3.Connection,
                       status: str | None = None) -> list[dict[str, Any]]:
    if status is None:
        rows = _rows_of(c.execute("SELECT * FROM research_candidates ORDER BY created_at LIMIT ?",
                                  (MAX_ROWS,)))
    else:
        rows = _rows_of(c.execute("SELECT * FROM research_candidates WHERE status=? "
                                  "ORDER BY score DESC, created_at LIMIT ?", (status, MAX_ROWS)))
    return [r for r in rows if is_region_row(m, r)]


def conversion_registers(m: Mandate, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Section 24. The nine registers, and the one that must reach zero.

    <REGION>_DISCOVERIES   rows the region's miners recorded
    _INTERPRETED           of those, the ones that reached a mechanism (state past UNPROCESSED)
    _MECHANISMS            distinct canonical mechanisms among them
    _VALID_CELLS           children the closure GENERATED (economically valid, not the product)
    _COMPILED / _QUEUED / _TESTED / _BLOCKED   the conversion chain's own counters
    _UNEXPLAINED_DEBT      possible - generated - blocked: children that left with NO disposition

    The last one is the only number here that is allowed to be a target. The others are what the
    region did; this one is what it lost, and section 24 says it goes to zero -- not that every
    cell is tested today.
    """
    c = conn or R.connect()
    try:
        rows = _region_discoveries(m, c)
        prefix = _tok(m.region).upper()
        matched: dict[str, int] = {}
        for r in rows:
            key = region_match(m, r) or "unknown"
            matched[key] = matched.get(key, 0) + 1
        advanced = {"INTERPRETED", "EXPANDED", "COMPILED", "QUEUED", "TESTED"}
        interpreted = sum(1 for r in rows if str(r.get("state") or "") in advanced)
        mechanisms = {_tok(r.get("mechanism")) for r in rows
                      if str(r.get("mechanism") or "").strip()}
        mechanisms.discard("unknown")

        def total(col: str) -> int:
            return int(sum(int(r.get(col) or 0) for r in rows))

        possible, generated = total("possible_cells"), total("generated_cells")
        blocked = total("blocked_cells")
        unexplained = max(0, possible - generated - blocked)
        out: dict[str, Any] = {
            f"{prefix}_DISCOVERIES": len(rows),
            f"{prefix}_INTERPRETED": interpreted,
            f"{prefix}_MECHANISMS": len(mechanisms),
            f"{prefix}_VALID_CELLS": generated,
            f"{prefix}_COMPILED": total("compiled_cells"),
            f"{prefix}_QUEUED": total("queued_cells"),
            f"{prefix}_TESTED": total("tested_cells"),
            f"{prefix}_BLOCKED": blocked,
            f"{prefix}_UNEXPLAINED_DEBT": unexplained,
        }
        out["detail"] = {
            "possible_cells": possible,
            "by_state": {s: sum(1 for r in rows if str(r.get("state") or "") == s)
                         for s in R.DISCOVERY_STATES},
            "blocked_by_disposition": _blocked_by_disposition(rows),
            "matched_by": matched,
            "conversion_coverage": (None if possible == 0
                                    else round(min(1.0, (generated + blocked) / possible), 6)),
        }
        out["rule"] = (f"{prefix}_UNEXPLAINED_DEBT -> 0: every child of every closure carries one "
                       f"of {list(DISPOSITIONS)}, and silence is not one of them")
        return out
    finally:
        if conn is None:
            c.close()


def _blocked_by_disposition(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        reason = r.get("blocked_reason")
        if not str(reason or "").strip():
            continue
        d = disposition_of(str(reason), str(r.get("state") or ""))
        out[d] = out.get(d, 0) + 1
    return out


# --------------------------------------------------------------------------- the frontier
def cell_key(axes: Mapping[str, Any]) -> str:
    """A frontier cell's identity, in FRONTIER_AXES order, so two organs naming the same cell
    produce the same string rather than two strings nobody can join."""
    return "|".join(_tok(axes.get(a)) for a in FRONTIER_AXES)


def axes_of(cell: str) -> dict[str, str]:
    parts = str(cell).split("|")
    return {a: (parts[i] if i < len(parts) else "unknown") for i, a in enumerate(FRONTIER_AXES)}


def axes_of_discovery(r: Mapping[str, Any]) -> dict[str, str]:
    return {"asset": _first(r.get("assets_json") or r.get("assets")),
            "actor": _tok(r.get("actor")),
            "constraint": _tok(r.get("constraint_text") or r.get("constraint")),
            "mechanism": _tok(r.get("mechanism")),
            "information": _tok(r.get("information")),
            "session": _first(r.get("sessions_json") or r.get("sessions")),
            "horizon": _first(r.get("horizons_json") or r.get("horizons")),
            "regime": _first(r.get("regimes_json") or r.get("regimes"))}


def axes_of_candidate(r: Mapping[str, Any]) -> dict[str, str]:
    return {"asset": _tok(r.get("symbol")), "actor": _tok(r.get("economic_actor")),
            "constraint": _tok(r.get("constraint_text") or r.get("constraint")),
            "mechanism": _tok(r.get("mechanism")), "information": _tok(r.get("information")),
            "session": _tok(r.get("session")), "horizon": _tok(r.get("horizon")),
            "regime": _tok(r.get("regime"))}


def mechanism_vocabulary(m: Mandate, observed: Iterable[str] = ()) -> tuple[str, ...]:
    """What the region may be asked about: the mechanism families its datasets declare, plus the
    mechanisms its miners have actually discovered. Capped, because an unbounded mechanism axis
    turns the map into one cell per candidate -- an axis with one value per row measures nothing
    (`research_gap_map` paid for that lesson with 1,569 "regimes")."""
    declared = [_tok(f) for ds in m.datasets for f in ds.mechanism_families]
    seen = [_tok(x) for x in observed if str(x or "").strip()]
    out: list[str] = []
    for v in declared + seen:
        if v != "unknown" and v not in out:
            out.append(v)
    return tuple(out[:MAX_MECHANISMS]) or ("unmapped",)


def enumerate_cells(m: Mandate, mechs: Sequence[str]) -> tuple[dict[str, dict[str, str]], bool]:
    """The region's economically meaningful coordinates, and whether the cap truncated them.

    ACTOR-DRIVEN, not cartesian. An actor brings its own constraints, its own information axes
    and its own instruments, so a cell asks a question somebody could actually ask; the full
    product of eight open vocabularies is millions of coordinates nobody would ask out loud, and
    a map of those ranks nothing (`research_gap_map` reached the same conclusion from the other
    end of the desk). The cap is a COMPUTE BUDGET and the caller reports it as one.
    """
    cells: dict[str, dict[str, str]] = {}
    syms = list(m.instruments)
    for a in m.actors:
        own = [s for s in a.instruments if s in syms] or syms
        constraints = [_tok(x) for x in a.constraints] or ["unknown"]
        infos = [_tok(x) for x in a.information] or ["unknown"]
        for asset in own:
            for con in constraints:
                for info in infos:
                    for mech in mechs:
                        for ses, hor, reg in _SHR:
                            if len(cells) >= MAX_FRONTIER_CELLS:
                                return cells, True
                            axes = {"asset": _tok(asset), "actor": _tok(a.name),
                                    "constraint": con, "mechanism": _tok(mech),
                                    "information": info, "session": ses, "horizon": hor,
                                    "regime": reg}
                            cells[cell_key(axes)] = axes
    return cells, False


#: Session x Horizon x Regime, precomputed: the closed tail of every cell.
_SHR: tuple[tuple[str, str, str], ...] = tuple(
    (s, h, r) for s in SESSIONS for h in HORIZONS for r in REGIMES)


def _normalise_evidence(evidence: Mapping[str, Any] | None) -> dict[str, str]:
    """{cell -> state} from whatever the runner has: cell strings or axis dicts, per state."""
    out: dict[str, str] = {}
    for state, items in (evidence or {}).items():
        st = str(state).strip().upper()
        if st not in FRONTIER_RANK:
            continue
        seq: Sequence[Any] = items if isinstance(items, (list, tuple)) else [items]
        for item in seq:
            key = cell_key(item) if isinstance(item, Mapping) else str(item)
            if FRONTIER_RANK[st] > FRONTIER_RANK.get(out.get(key, "UNSEEN"), 0):
                out[key] = st
    return out


def frontier(m: Mandate, conn: sqlite3.Connection | None = None,
             evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Section 25. The region's eight-axis map, one state per cell, and the holes ranked.

    ENUMERATION IS ACTOR-DRIVEN, not cartesian: an actor brings its OWN constraints, its own
    information and its own instruments, so the grid asks "which constraint on which actor" and
    never "every constraint on every actor", most of which is nobody's question. Sessions,
    horizons and regimes are the closed vocabularies above.

    THE VALUE FUNCTION IS WHY FIFTY USDJPY H1 CELLS ARE WORTH ONE. A hole's value is the mean
    over its eight axes of 1/(1 + cells already populated on that axis value), times readiness.
    Every sibling a coordinate gains makes the next sibling worth less, automatically, with no
    list of forbidden repetitions to maintain.
    """
    c = conn or R.connect()
    try:
        discs = _region_discoveries(m, c)
        cands = _region_candidates(m, c)
        observed = [str(r.get("mechanism") or "") for r in discs + cands]
        mechs = mechanism_vocabulary(m, observed)

        state: dict[str, str] = {}

        def put(key: str, st: str) -> None:
            if FRONTIER_RANK[st] > FRONTIER_RANK.get(state.get(key, "UNSEEN"), 0):
                state[key] = st

        cells, truncated = enumerate_cells(m, mechs)

        outside: dict[str, str] = {}

        def observe(key: str, st: str) -> None:
            """Evidence lands in the grid, or is COUNTED outside it. Never quietly admitted: a
            cell nobody declared is a finding about the mandate, not a ninth axis value."""
            if key in cells:
                put(key, st)
            elif FRONTIER_RANK[st] > FRONTIER_RANK.get(outside.get(key, "UNSEEN"), 0):
                outside[key] = st

        for r in discs:
            blocked = disposition_of(str(r.get("blocked_reason") or ""), str(r.get("state") or ""))
            observe(cell_key(axes_of_discovery(r)),
                    "DATA_BLOCKED" if blocked in ("DATA_BLOCKED", "PIT_BLOCKED") else "DISCOVERED")
        for r in cands:
            status = str(r.get("status") or "").lower()
            if status == "survived" or int(r.get("survived") or 0) == 1:
                st = "SURVIVED"
            elif status == "judged":
                st = "FAILED"
            elif status in ("claimed", "donated"):
                st = "SCREENED"
            else:
                st = "COMPILED"
            observe(cell_key(axes_of_candidate(r)), st)
        for key, st in _normalise_evidence(evidence).items():
            observe(key, st)

        by_state = dict.fromkeys(FRONTIER_STATES, 0)
        for key in cells:
            by_state[state.get(key, "UNSEEN")] += 1

        axis_counts: dict[str, dict[str, int]] = {a: {} for a in FRONTIER_AXES}
        for key, st in state.items():
            if st not in POPULATED_STATES or key not in cells:
                continue
            for axis, value in cells[key].items():
                axis_counts[axis][value] = axis_counts[axis].get(value, 0) + 1

        holes: list[dict[str, Any]] = []
        for key, axes in cells.items():
            st = state.get(key, "UNSEEN")
            if st in POPULATED_STATES:
                continue
            crowd = {a: 1.0 / (1.0 + float(axis_counts[a].get(axes[a], 0))) for a in FRONTIER_AXES}
            room = float(np.mean(np.asarray(list(crowd.values()), dtype=float)))
            hole_value = room * HOLE_READINESS.get(st, 0.5)
            worst = min(crowd, key=lambda a: crowd[a])
            holes.append({
                "cell": key, "state": st, "value": round(hole_value, 6), "axes": dict(axes),
                "why": (f"{st}; the most crowded axis is {worst}={axes[worst]} with "
                        f"{axis_counts[worst].get(axes[worst], 0)} populated sibling(s); "
                        f"readiness {HOLE_READINESS.get(st, 0.5):.2f}")})
        if holes:
            order = np.argsort(-np.asarray([h["value"] for h in holes], dtype=float), kind="stable")
            holes = [holes[int(i)] for i in order]

        populated = sum(by_state[s] for s in POPULATED_STATES)
        return {
            "at": _now(), "region": m.region, "axes": list(FRONTIER_AXES),
            "n_cells": len(cells), "n_populated": populated,
            "populated_share": (round(populated / len(cells), 6) if cells else None),
            "by_state": by_state, "top_holes": holes[:TOP_HOLES],
            "mechanism_vocabulary": list(mechs),
            "coverage_by_axis": {a: dict(sorted(v.items(), key=lambda kv: -kv[1])[:40])
                                 for a, v in axis_counts.items()},
            "unmeasured": {
                "evidence_outside_the_grid": len(outside),
                "evidence_outside_sample": sorted(outside)[:20],
                "truncated": truncated,
                "truncated_why": (
                    None if not truncated else
                    f"the enumeration stopped at MAX_FRONTIER_CELLS={MAX_FRONTIER_CELLS} and it "
                    f"stops at the SAME prefix every pass -- the tail of this region's grid is "
                    f"not unmapped-for-now, it is unmappable until the cap rises or the actors "
                    f"narrow their own instruments, constraints and information axes"),
                "why": ("a cell outside the grid is evidence about the MANDATE -- an actor, "
                        "constraint or instrument somebody tested and nobody declared -- not a "
                        "licence to widen the axes"),
            },
            "rule": ("valuable empty cells first: every sibling a coordinate gains makes the next "
                     "sibling worth less, so fifty near-identical cells rank below one new one"),
        }
    finally:
        if conn is None:
            c.close()


def top_holes(front: Mapping[str, Any], k: int = 10) -> list[dict[str, Any]]:
    """The k highest-value holes of a built frontier."""
    rows = front.get("top_holes")
    return list(rows)[:max(0, int(k))] if isinstance(rows, list) else []


# --------------------------------------------------------------------------- saturation
def _axis_values(axis: str, row: Mapping[str, Any]) -> list[str]:
    payload = _jload(row.get("payload_json")) or {}
    pay: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}
    if axis == "source":
        return [_tok(row.get("source_id"))]
    if axis == "language":
        return [_tok(pay.get("language") or row.get("language"))]
    if axis == "actor":
        return [_tok(row.get("actor"))]
    if axis == "mechanism":
        return [_tok(row.get("mechanism"))]
    if axis == "asset":
        return _as_list(row.get("assets_json")) or [_tok(row.get("symbol"))]
    if axis == "dataset":
        return _as_list(pay.get("datasets") or pay.get("dataset")
                        or row.get("required_data_json")) or ["unknown"]
    if axis == "session":
        return _as_list(row.get("sessions_json")) or ["unknown"]
    if axis == "horizon":
        return _as_list(row.get("horizons_json")) or ["unknown"]
    return ["unknown"]


def _when(row: Mapping[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(row.get("created_at") or ""))
    except ValueError:
        return None


def saturation(m: Mandate, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Section 44. Per axis: the counts, the discovery curve, and one of five verdicts.

    THE CURVE, NOT THE COUNT. "Saturated" is not "we have a lot of rows": it is NEW DISTINCT
    VALUES PER DISCOVERY having collapsed against the previous week. A source that yields its
    hundredth row and its first new mechanism is unsaturated; one that yields a thousand rows and
    nothing unseen is saturated however busy it looks.

    AND FOUR OF THE FIVE VERDICTS ARE ABOUT THE MEASUREMENT. `poorly_measured` (too few rows to
    read a rate), `data_blocked` (the axis's rows are being refused for data or PIT, so the rate
    measures the blockage not the ground) and `UNMEASURED` (no rows at all) are the honest
    answers most axes deserve most weeks, and rendering them as `saturated` is how a region stops
    mining ground it never touched.
    """
    c = conn or R.connect()
    try:
        rows = _region_discoveries(m, c)
        now = datetime.now(tz=UTC)
        recent_cut = now - timedelta(days=SATURATION_WINDOW_DAYS)
        earlier_cut = now - timedelta(days=2 * SATURATION_WINDOW_DAYS)
        older: list[dict[str, Any]] = []
        earlier: list[dict[str, Any]] = []
        recent: list[dict[str, Any]] = []
        undated = 0
        for r in rows:
            when = _when(r)
            if when is None:
                undated += 1
                continue
            if when >= recent_cut:
                recent.append(r)
            elif when >= earlier_cut:
                earlier.append(r)
            else:
                older.append(r)

        out: dict[str, Any] = {"at": _now(), "region": m.region,
                               "window_days": SATURATION_WINDOW_DAYS,
                               "n_rows": len(rows), "n_recent": len(recent),
                               "n_earlier": len(earlier), "n_undated": undated, "axes": {}}
        for axis in SATURATION_AXES:
            def values(rs: Iterable[Mapping[str, Any]], _axis: str = axis) -> list[str]:
                return [v for r in rs for v in _axis_values(_axis, r) if v != "unknown"]

            before_recent = set(values(older)) | set(values(earlier))
            before_earlier = set(values(older))
            new_recent = set(values(recent)) - before_recent
            new_earlier = set(values(earlier)) - before_earlier
            rate_recent = (len(new_recent) / len(recent)) if recent else None
            rate_earlier = (len(new_earlier) / len(earlier)) if earlier else None
            blocked = sum(1 for r in recent if disposition_of(
                str(r.get("blocked_reason") or ""), str(r.get("state") or "")
            ) in ("DATA_BLOCKED", "PIT_BLOCKED"))

            if not rows or (not recent and not earlier):
                verdict = "UNMEASURED"
            elif recent and blocked >= max(1, len(recent) // 2):
                verdict = "data_blocked"
            elif len(recent) < SATURATION_MIN_ROWS:
                verdict = "poorly_measured"
            elif (rate_recent is not None and rate_recent <= SATURATION_RATE
                  and (rate_earlier is None
                       or rate_recent <= SATURATION_DECAY * max(rate_earlier, 1e-9))):
                verdict = "saturated"
            else:
                verdict = "unsaturated"
            out["axes"][axis] = {
                "distinct": len(set(values(rows))), "recent_rows": len(recent),
                "new_recent": len(new_recent), "new_earlier": len(new_earlier),
                "rate_recent": None if rate_recent is None else round(rate_recent, 6),
                "rate_earlier": None if rate_earlier is None else round(rate_earlier, 6),
                "blocked_recent": blocked, "verdict": verdict,
                "why": ("new distinct values per discovery, last "
                        f"{SATURATION_WINDOW_DAYS}d vs the {SATURATION_WINDOW_DAYS}d before; "
                        f"saturated needs both <= {SATURATION_RATE} and <= "
                        f"{SATURATION_DECAY:.0%} of the earlier rate"),
            }
        out["rule"] = ("saturation is measured per axis and expires; there is no permanent "
                       "completion (sections 44 and 45)")
        return out
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- ROI
def roi_by_source(m: Mandate, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Section 36. What each of the region's sources actually bought, per compute second.

    A source is paid by INDEPENDENT SURVIVORS, never by leads: a forum that yields three hundred
    claims and no orthogonal survivor is a cost centre with good throughput. Where compute is
    unrecorded the ROI is UNMEASURED and says so -- a missing denominator is not a zero cost.
    """
    c = conn or R.connect()
    try:
        rows = [r for r in _rows_of(c.execute("SELECT * FROM source_yield"))
                if str(r.get("source_id") or "").lower().startswith(tag(m))]
        out: list[dict[str, Any]] = []
        unmeasured: list[str] = []
        for r in rows:
            compute = float(r.get("compute_s") or 0.0)
            indep = float(r.get("independent_survivors") or 0.0)
            leads = float(r.get("leads") or 0.0)
            roi = None if compute <= 0 else round(indep / (compute / 3600.0), 6)
            if roi is None:
                unmeasured.append(f"{r.get('source_id')}: no compute_s recorded")
            out.append({"source_id": r.get("source_id"), "leads": int(leads),
                        "mechanisms": int(r.get("mechanisms") or 0),
                        "candidates": int(r.get("candidates") or 0),
                        "judged": int(r.get("judged") or 0),
                        "survivors": int(r.get("survivors") or 0),
                        "independent_survivors": int(indep), "compute_s": compute,
                        "independent_survivors_per_compute_hour": roi,
                        "claim_to_mechanism": (None if leads <= 0
                                               else round(float(r.get("mechanisms") or 0) / leads,
                                                          6))})
        out.sort(key=lambda d: (-(d["independent_survivors_per_compute_hour"] or -1.0),
                                str(d["source_id"])))
        return {"at": _now(), "region": m.region, "n_sources": len(out), "sources": out,
                "unmeasured": unmeasured,
                "rule": "a source is paid by independent survivors per compute hour, never by "
                        "lead count"}
    finally:
        if conn is None:
            c.close()


def research_roi(m: Mandate, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Section 39. ResearchROI = OrthogonalGauntletValue / (compute + maintenance + complexity).

    Every term that is not measured on this box is NAMED rather than defaulted, and the ratio is
    None when its denominator is unmeasured. A ROI computed off a silently-zero maintenance cost
    is the number a department would use to justify never simplifying anything.
    """
    c = conn or R.connect()
    try:
        cands = _region_candidates(m, c)
        judged = [r for r in cands if str(r.get("status") or "") in ("judged", "survived")]
        survived = [r for r in judged if int(r.get("survived") or 0) == 1]
        value = float(sum(float(r.get("expected_return_independence") or R.PRIOR)
                          for r in survived))
        gy = [r for r in R.generator_yields(conn=c)
              if str(r.get("generator") or "").lower().startswith(tag(m))]
        sy = [r for r in _rows_of(c.execute("SELECT * FROM source_yield"))
              if str(r.get("source_id") or "").lower().startswith(tag(m))]
        compute_s = float(sum(float(r.get("compute_s") or 0.0) for r in gy)
                          + sum(float(r.get("compute_s") or 0.0) for r in sy))
        unmeasured: list[str] = []
        if compute_s <= 0:
            unmeasured.append("compute: no compute_s on any region generator or source row")
        maintenance = float(len(m.miners))
        if not m.miners:
            unmeasured.append("maintenance: the mandate declares no miners to maintain")
        families = {str(r.get("trial_family") or r.get("family") or "") for r in cands}
        families.discard("")
        params: list[float] = []
        for r in cands:
            doc = _jload(r.get("params_json"))
            params.append(float(len(doc)) if isinstance(doc, dict) else 0.0)
        complexity = float(len(families)) + (float(np.mean(np.asarray(params, dtype=float)))
                                             if params else 0.0)
        if not cands:
            unmeasured.append("complexity: no region candidate carries parameters yet")
        denom = compute_s / 3600.0 + maintenance + complexity
        roi = None if denom <= 0 or not survived else round(value / denom, 6)
        if roi is None and survived:
            unmeasured.append("roi: the denominator is zero; nothing has been spent on record")
        if not survived:
            unmeasured.append("orthogonal gauntlet value: no region candidate has survived yet")
        return {"at": _now(), "region": m.region, "orthogonal_gauntlet_value": round(value, 6),
                "n_judged": len(judged), "n_survived": len(survived),
                "compute_hours": round(compute_s / 3600.0, 6),
                "maintenance_units": maintenance, "complexity_units": round(complexity, 6),
                "denominator": round(denom, 6), "research_roi": roi, "unmeasured": unmeasured,
                "rule": "value is independence-weighted survivors; an unmeasured term is named, "
                        "never defaulted to zero"}
    finally:
        if conn is None:
            c.close()


# --------------------------------------------------------------------------- the dashboard
def dashboard(m: Mandate, conn: sqlite3.Connection | None = None,
              extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Section 43. One object carrying every field the region's dashboard shows.

    It is assembled from the measurements above and nothing else -- no field here is computed a
    second way, so the dashboard and the registers can never disagree about the same number."""
    c = conn or R.connect()
    try:
        regs = conversion_registers(m, conn=c)
        front = frontier(m, conn=c, evidence=(extra or {}).get("evidence")
                         if isinstance((extra or {}).get("evidence"), Mapping) else None)
        sat = saturation(m, conn=c)
        roi_src = roi_by_source(m, conn=c)
        rroi = research_roi(m, conn=c)
        prefix = _tok(m.region).upper()
        cands = _region_candidates(m, c)
        dups = sum(max(0, int(r.get("search_count") or 1) - 1) for r in cands)
        deaths = sum(1 for r in cands
                     if str(r.get("status") or "") == "judged" and int(r.get("survived") or 0) == 0)
        survivors = sum(1 for r in cands if int(r.get("survived") or 0) == 1)
        recent = int(sat.get("n_recent") or 0)
        doc: dict[str, Any] = {
            "region": m.region, "at": _now(), "capital_authority": bool(m.capital_authority),
            "terminal_output": TERMINAL_OUTPUT, "registers": regs,
            "frontier_by_state": front["by_state"], "frontier_holes": top_holes(front, 12),
            "saturation": {a: v["verdict"] for a, v in sat["axes"].items()},
            "roi_by_source": roi_src["sources"][:12], "research_roi": rroi,
            "discoveries_recent": recent, "mechanisms": regs[f"{prefix}_MECHANISMS"],
            "valid_cells": regs[f"{prefix}_VALID_CELLS"], "compiled": regs[f"{prefix}_COMPILED"],
            "queued": regs[f"{prefix}_QUEUED"], "tested": regs[f"{prefix}_TESTED"],
            "blocked": regs[f"{prefix}_BLOCKED"],
            "unexplained_debt": regs[f"{prefix}_UNEXPLAINED_DEBT"],
            "duplicates": dups, "survivors": survivors, "deaths": deaths,
            "miners": [mi.name for mi in m.miners],
            "unmeasured": sorted({*rroi["unmeasured"], *roi_src["unmeasured"],
                                  *([f"saturation:{a}" for a, v in sat["axes"].items()
                                     if v["verdict"] in ("UNMEASURED", "poorly_measured")])}),
            "rule": RULE,
        }
        for k, v in (extra or {}).items():
            if k not in doc and k != "evidence":
                doc[k] = v
        return doc
    finally:
        if conn is None:
            c.close()
