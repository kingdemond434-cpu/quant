"""Q1 / W12 -- A POPULATION OF RESEARCH POLICIES, COMPETING ON WHAT RESEARCH IS ACTUALLY FOR.

THE PRINCIPAL, 2026-09-16: the research system may evolve itself, behind an immutable
constitution. `meta_rnd` (F25) opened that door and kept ONE champion holding six scalar knobs in
`data/meta_champion.json`. One champion is a hill climb, and a hill climb on a search system is
the failure the Darwin Godel Machine literature names by name: the incumbent's neighbourhood is
the only place anything is ever tried, so the first local optimum is permanent and every stepping
stone that looks worse today is discarded before it can pay. This supersedes that design with an
ARCHIVE -- a population of variants kept for their DIVERSITY as well as their score, each with
its lineage, each still reachable.

A VARIANT IS A POLICY, AND A POLICY IS DATA, NEVER CODE. Nothing here edits a module, rewrites a
constant or ships a patch. A variant says how the hour's research should be SPENT:

    leg_budget_factors   per hourly leg, a multiplier on the seconds `research_budget.budget_s`
                         hands it -- the same [0.5, 2.0] clip that module already enforces
    arm_weights          per bandit arm, a tilt on the proposal mix the arms price
    population_mix       shares over the nine search populations of `search_populations`
    retrieval_depth      how many similar failures the deepening worker reads before it writes
    prompt_template      which declared extraction style the seat runs under
    exploration_floor    the share of admissions reserved for the cells the model scores WORST
                         (`negative_knowledge.EXPLORE_FLOOR`, 0.20 as written)
    department_factors   per research department, an elastic factor on its share of the hour
    miner                MinerOS A/B/C -- retrieval (bm25 | embedding | hybrid), ranking (score |
                         novelty_first | roi_first), ontology_version, and a search_mix over
                         exploration / exploitation / COLD. The mining machinery competes too.
    meta_knobs           OPTIONAL, and the reason F25's knobs are not orphaned by this file: a
                         variant may name any knob in `meta_rnd.META_KNOBS` inside its own
                         declared range. One champion becomes one lineage among many.

FITNESS IS SEVEN MEASUREMENTS OF THE RESEARCH ITSELF -- never a coding benchmark, never a self-
report, never a proxy for how clever the search looks. A research system graded on its own
cleverness optimises cleverness. Each field is read from the ledger that owns it, and each is
NULL when that ledger cannot answer for the window (L1.28a: absence is a verdict, not a zero):

    forward_valid_alpha_per_cost   NEW INDEPENDENT forward-valid survivors born in the window per
                           second of compute + data + wall. THE HEADLINE, and first in the
                           composite: survivors from shadow_state, independence from
                           EXPOSURE_DECOMPOSITION (or CREDIT_ASSIGNMENT). With neither, the count
                           would be of NAMES rather than of bets, so the field is UNMEASURED.
    survivor_yield         CERTIFIED / BORN in the window          data/hypothesis_graph.jsonl
    delta_n_eff            change in effective breadth             data/effective_breadth.jsonl
    novel_mechanism_rate   novel / (novel + redundant)             reports/NOVELTY_GATE.json
    false_discovery_rate   certified clocks retired in the window  reports/shadow/shadow_state.json
                           (fallback: passed cells whose downstream_status later failed, in
                           data/hypotheses/gate_verdict_ledger.jsonl)
    compute_per_survivor   wall hours / survivors                  data/compute_ledger.jsonl
    forward_success        promoted / touched forward clocks       reports/shadow/shadow_state.json

SELECTION IS UCB, PRUNING IS BY CLUSTER. The composite is a declared exchange rate over unlike
units; optimism about the untried is the archive's MEAN, never its maximum, or every freshly bred
child would top the board and the seat would be a random walk. The archive keeps the best of every
cluster -- the knob a variant moved furthest from the incumbent -- before any second member of
any cluster, because a population that collapses to one member is a champion with extra
bookkeeping. Rotation is capped at once per --window-hours: fitness is measured over the window a
variant was actually seated for, and a system that reseats every pass selects on noise.

THE WALL HAS TWO LISTS. `assert_constitution` refuses any policy that names a file in
`check_immutable_evaluator.IMMUTABLE`, touches a class in `meta_rnd.FORBIDDEN_KNOBS` (gate
thresholds, heat, the lot floor, daily loss, sizing, the trial charge -- what the desk RISKS), or
touches a class in `FORBIDDEN_MOAT_KNOBS` (source provenance, PIT rules, trial accounting, sealed
holdouts, forward clocks, actual costs and fills -- what the desk KNOWS). The cold-search floor
sits in the same wall. EVERY write goes through it, the seed included, and so does every READ by
`active_policy()`, because a hand-edited archive is the obvious way around a check that guards
only its own mutations. The point is not that a mutation would aim there: it is that a search
which COULD reach the judge would eventually find that lowering the bar is cheaper than clearing
it, so the path must not exist.

    python research_os_archive.py [--dry-run] [--window-hours 6]

Consumers read `active_policy()` -- `research_budget.budget_s` for the leg factor, the deepening
worker for `retrieval_depth`. It never raises: an unreadable or breaching archive returns the
incumbent with the reason attached, because a research policy that can stall the hour is worse
than none.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ARCHIVE = DESK / "data" / "research_os_archive.json"
OUT = DESK / "reports" / "RESEARCH_OS_ARCHIVE.json"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
BREADTH_HIST = DESK / "data" / "effective_breadth.jsonl"
NOVELTY = DESK / "reports" / "NOVELTY_GATE.json"
COMPUTE = DESK / "data" / "compute_ledger.jsonl"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
BANDIT = DESK / "reports" / "RESEARCH_BANDIT.json"
EXPOSURE = DESK / "reports" / "EXPOSURE_DECOMPOSITION.json"
CREDIT = DESK / "reports" / "CREDIT_ASSIGNMENT.json"

#: The nine search populations of `libs/research/search_populations.py`. Enumerated here because
#: `population_mix` is a simplex and a mutation needs a fixed set of coordinates to renormalise on.
POPULATIONS: tuple[str, ...] = ("gp", "gflownet", "symreg", "program_synthesis", "bayesian",
                                "zoo_mutation", "graveyard_derived", "causal_derived",
                                "claims_derived")
#: `hourly_cycle.DEPARTMENTS`, measured 2026-09-17.
DEPARTMENTS: tuple[str, ...] = ("data", "intel", "discovery", "validate", "macro", "execution",
                                "forward", "meta", "rest")
#: Declared extraction styles a seat may run under. A consumer that does not know an id runs
#: "incumbent"; the id is a REQUEST, never an instruction to build a prompt out of free text.
PROMPT_TEMPLATES: tuple[str, ...] = ("incumbent", "mechanism_first", "falsifier_first",
                                     "data_first")
#: The bandit's arms, as a fallback when RESEARCH_BANDIT.json is unreadable.
SEED_ARMS: tuple[str, ...] = ("new_mechanism", "mutate_survivor", "combine_survivors",
                              "conditional_state_edge", "execution_improvement",
                              "exit_improvement", "cross_asset_signal", "alt_data_hypothesis",
                              "failure_derived", "model_architecture", "external_screen")

#: THE MINER BLOCK (MinerOS A/B/C). The intelligence-mining machinery is itself a competing
#: version, not a fixed service: how it retrieves, how it ranks what it retrieved, which ontology
#: it reads the world through, and how it splits its search between what it knows, what it is
#: exploiting, and GROUND IT HAS NEVER TOUCHED.
MINER_RETRIEVAL: tuple[str, ...] = ("bm25", "embedding", "hybrid")
MINER_RANKING: tuple[str, ...] = ("score", "novelty_first", "roi_first")
MINER_SEARCH_LANES: tuple[str, ...] = ("exploration", "exploitation", "cold")
#: THE COLD-SEARCH FLOOR IS CONSTITUTIONAL, not a tuning parameter. Cold search is the only lane
#: that can find ground the desk's own history cannot point at, and it is always the lane a
#: short-horizon score says to cut -- it pays last and it pays rarely. A variant that could take
#: it to zero would optimise itself into the neighbourhood of what it already knows, which is the
#: same local-optimum failure the archive exists to prevent, one level down.
COLD_SEARCH_FLOOR = 0.10
ONTOLOGY_MAX = 9                          # ontology ids are bounded: v1..v9, never free text
FACTOR_LO, FACTOR_HI = 0.5, 2.0           # the clip `research_budget` already enforces
DEPTH_LO, DEPTH_HI = 0, 20
EXPLORE_LO, EXPLORE_HI = 0.05, 0.50
DEFAULT_RETRIEVAL_DEPTH = 5
DEFAULT_EXPLORATION_FLOOR = 0.20          # negative_knowledge.EXPLORE_FLOOR as written
WINDOW_HOURS = 6.0
WINDOW_CAP_H = 168.0                      # a window is never read further back than a week
MAX_VARIANTS = 24
UCB_C = 0.35
#: Declared exchange rates. A composite over unlike units is only honest if the rates are named.
DELTA_NEFF_SCALE = 1.0                    # one whole effective bet is worth one composite point
CPS_SCALE_H = 10.0                        # 10 wall-hours per survivor is a full point of cost
ALPHA_COST_SCALE = 1.0 / 3600.0           # one independent survivor per hour of TOTAL spend = 1.0
DUP_COSINE = 0.9                          # above this, two sleeves are one bet under two names
TAIL_BYTES = 4_000_000
CERTIFIED_ADMISSION = "ORIGINAL_UNIVERSAL_10_PASS"
#: `forward_valid_alpha_per_cost` LEADS the list and leads the composite: it is the only field
#: that divides what the research actually produced by what it actually cost, and every other
#: field is a leading indicator of it.
FITNESS_FIELDS: tuple[str, ...] = ("forward_valid_alpha_per_cost", "survivor_yield",
                                   "delta_n_eff", "novel_mechanism_rate",
                                   "false_discovery_rate", "compute_per_survivor",
                                   "forward_success")
RULE = ("variants compete on survivor yield, delta n_eff, novelty rate, FDR, compute per "
        "survivor and forward success -- never on a coding benchmark; the constitution is not "
        "a knob")


class ConstitutionBreach(Exception):
    """A policy that reached for the judge. Raised, never logged and continued."""


# ------------------------------------------------------------------------------------------- io
def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only destination is legal
    on POSIX and raises WinError 5 here -- the way a VPS-tested fix once broke the box that
    trades."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    path.write_text(body, encoding="utf-8")


def _parse_at(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        d = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _tail_rows(path: Path, max_bytes: int = TAIL_BYTES) -> list[dict[str, Any]]:
    """The last `max_bytes` of an append-ordered jsonl, parsed. Bounded because
    hypothesis_graph.jsonl is 18 MB and growing, and a window is hours, not months."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()
            raw = fh.read()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if isinstance(d, dict):
            rows.append(d)
    return rows


def _in_window(row: dict[str, Any], start: datetime, end: datetime, field: str = "at") -> bool:
    t = _parse_at(row.get(field))
    return t is not None and start <= t <= end


# ----------------------------------------------------------------------------------------- wall
def immutable_paths() -> tuple[str, ...]:
    """`check_immutable_evaluator.IMMUTABLE`, loaded by file path. `scripts/` is not a package and
    putting it on sys.path would shadow modules; an empty tuple here is reported as
    immutable_checked=false rather than passed off as a clean wall."""
    spec = importlib.util.spec_from_file_location(
        "_roa_immutable", ROOT / "scripts" / "check_immutable_evaluator.py")
    if spec is None or spec.loader is None:
        return ()
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return tuple(str(x) for x in getattr(mod, "IMMUTABLE", ()))
    except Exception:
        return ()


def forbidden_knobs() -> dict[str, str]:
    try:
        return dict(importlib.import_module("meta_rnd").FORBIDDEN_KNOBS)
    except Exception:
        return {}


def meta_knob_specs() -> dict[str, dict[str, Any]]:
    try:
        return dict(importlib.import_module("meta_rnd").META_KNOBS)
    except Exception:
        return {}


def _norm(s: str) -> str:
    return " ".join(str(s).lower().replace("_", " ").replace("-", " ").replace("\\", "/").split())


_ONTOLOGY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,15}$")


#: THE MOAT KNOBS: the second refusal list, and the one a MINER would reach for. FORBIDDEN_KNOBS
#: guards what the desk RISKS; these guard what the desk KNOWS -- the machinery that makes a mined
#: claim mean anything. A miner version graded on how much alpha it finds per unit of cost has an
#: obvious cheapest path to a better number through every one of them, and none of it is research.
FORBIDDEN_MOAT_KNOBS: dict[str, str] = {
    "source provenance": (
        "where a claim came from is the moat. A miner that could relabel provenance would turn a "
        "forum rumour into a fund disclosure, and the desk would no longer know what it tested."),
    "pit rules, point in time discipline": (
        "point-in-time is the whole difference between a backtest and a memory of the answer. A "
        "search permitted to relax it finds enormous alpha immediately and none of it exists."),
    "trial accounting, trial count": (
        "the multiplicity charge is one family-wise error budget shared by every hypothesis the "
        "desk tests. A miner that could stop counting its own trials would spend that budget for "
        "free, and every FX and metals cell would pay for it."),
    "sealed holdouts, holdout access": (
        "a holdout is only evidence while it is unseen. One look converts the desk's last honest "
        "sample into another training set, permanently and silently."),
    "forward clocks": (
        "a forward clock is elapsed time. Nothing that searches may set it, shorten it or restart "
        "it -- that is the one measurement no amount of compute can manufacture."),
    "actual costs, actual fills": (
        "the cost engine and the fill record are measurements of the VENUE, not parameters of a "
        "search. Edge that only survives an optimistic spread is a rounding choice, not an edge."),
}

#: Extra spellings of both forbidden classes. The prose above is written for a reader ("any gate
#: threshold", "forward clocks"); a policy would spell it `gate_threshold` or `forward_clock`, so
#: the token set is the prose split on commas with its articles stripped, PLUS the singular and
#: knob-shaped forms a mutation would actually produce.
EXTRA_FORBIDDEN: tuple[str, ...] = ("gate threshold", "heat floor", "heat ceiling", "min lot",
                                    "minimum lot", "lot size", "daily loss", "risk per trade",
                                    "sizing parameter", "trial charge", "deflated sharpe "
                                    "threshold", "promotion threshold")
EXTRA_MOAT: tuple[str, ...] = ("provenance", "pit rule", "point in time", "trial accounting",
                               "trial count", "sealed holdout", "holdout", "forward clock",
                               "actual cost", "actual fill", "realised cost", "realised fill",
                               "fill record", "cost engine")


def forbidden_tokens() -> tuple[str, ...]:
    """Every refusal token, from both lists. One scan, so a policy cannot slip past by naming the
    moat instead of the money."""
    toks = set(EXTRA_FORBIDDEN) | set(EXTRA_MOAT)
    for phrase in (*forbidden_knobs(), *FORBIDDEN_MOAT_KNOBS):
        for part in str(phrase).split(","):
            t = _norm(part)
            for article in ("any ", "the ", "every "):
                if t.startswith(article):
                    t = t[len(article):]
            if len(t) >= 6:
                toks.add(t)
    return tuple(sorted(toks))


def _walk_strings(obj: Any, path: str = "policy") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append((f"{path}.{k}", str(k)))
            out.extend(_walk_strings(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.extend(_walk_strings(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        out.append((path, obj))
    return out


def assert_constitution(policy: Any) -> None:
    """THE WALL. Raises ConstitutionBreach; returns None on a policy the desk may act on.

    Checked in this order on purpose: the wall first, the shape second. A policy that names the
    judge is refused for naming the judge, not for having an unknown key -- the refusal has to
    read as what it is the day it fires.
    """
    if not isinstance(policy, dict):
        raise ConstitutionBreach(f"a policy must be an object, got {type(policy).__name__}")

    immut = immutable_paths()
    immut_names = {_norm(p) for p in immut} | {_norm(Path(p).name) for p in immut}
    toks = forbidden_tokens()
    for where, text in _walk_strings(policy):
        n = _norm(text)
        for name in immut_names:
            if name and name in n:
                raise ConstitutionBreach(
                    f"{where} names {text!r}, which is an IMMUTABLE evaluator file. A research "
                    f"variant may change the hypothesis; it may never reach the judge.")
        for tok in toks:
            if tok in n:
                raise ConstitutionBreach(
                    f"{where} names {text!r}, which touches the forbidden knob class {tok!r}. "
                    f"Gate thresholds, heat, sizing and the trial charge are what a variant is "
                    f"JUDGED by; a search allowed to move them lowers its own bar.")

    unknown = sorted(set(policy) - set(POLICY_KNOBS))
    if unknown:
        raise ConstitutionBreach(
            f"unknown policy knob(s) {unknown}; declared: {sorted(POLICY_KNOBS)}")
    missing = sorted(k for k, s in POLICY_KNOBS.items()
                     if k not in policy and not s.get("optional"))
    if missing:
        raise ConstitutionBreach(f"policy is missing declared knob(s) {missing}")

    for knob, spec in POLICY_KNOBS.items():
        if knob not in policy:
            continue
        _assert_knob(knob, spec, policy[knob])


def _assert_knob(knob: str, spec: dict[str, Any], value: Any) -> None:
    kind = spec["kind"]
    if kind == "factors":
        if not isinstance(value, dict) or not value:
            raise ConstitutionBreach(f"{knob} must be a non-empty object of name -> factor")
        domain = spec.get("domain")
        for name, f in value.items():
            if domain is not None and name not in domain:
                raise ConstitutionBreach(f"{knob}: {name!r} is not one of {sorted(domain)}")
            if not isinstance(f, (int, float)) or isinstance(f, bool):
                raise ConstitutionBreach(f"{knob}[{name}] must be a number, got {f!r}")
            if not FACTOR_LO <= float(f) <= FACTOR_HI:
                raise ConstitutionBreach(
                    f"{knob}[{name}]={f} is outside [{FACTOR_LO}, {FACTOR_HI}]")
    elif kind == "shares":
        if not isinstance(value, dict) or set(value) != set(spec["domain"]):
            raise ConstitutionBreach(f"{knob} must carry exactly {sorted(spec['domain'])}")
        vals = []
        for name, s in value.items():
            if not isinstance(s, (int, float)) or isinstance(s, bool) or float(s) < 0.0:
                raise ConstitutionBreach(f"{knob}[{name}]={s!r} must be a share >= 0")
            vals.append(float(s))
        if abs(sum(vals) - 1.0) > 1e-6:
            raise ConstitutionBreach(f"{knob} sums to {sum(vals):.6f}, not 1.0")
    elif kind in ("int", "float"):
        ok = isinstance(value, int) if kind == "int" else isinstance(value, (int, float))
        if isinstance(value, bool) or not ok:
            raise ConstitutionBreach(f"{knob} must be a{'n int' if kind == 'int' else ' number'}, "
                                     f"got {value!r}")
        if not spec["lo"] <= float(value) <= spec["hi"]:
            raise ConstitutionBreach(f"{knob}={value} is outside [{spec['lo']}, {spec['hi']}]")
    elif kind == "choice":
        if value not in spec["domain"]:
            raise ConstitutionBreach(f"{knob}={value!r} is not one of {sorted(spec['domain'])}")
    elif kind == "miner":
        _assert_miner(knob, value)
    elif kind == "meta":
        if not isinstance(value, dict):
            raise ConstitutionBreach(f"{knob} must be an object of meta knob -> value")
        specs = meta_knob_specs()
        for name, v in value.items():
            if name not in specs:
                raise ConstitutionBreach(
                    f"{knob}: {name!r} is not a meta_rnd.META_KNOBS knob ({sorted(specs)})")
            lo, hi = specs[name]["lo"], specs[name]["hi"]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
                raise ConstitutionBreach(f"{knob}[{name}]={v!r} is outside [{lo}, {hi}]")


def _assert_miner(knob: str, value: Any) -> None:
    """The MinerOS block, including the ONE floor in it that is constitutional rather than tuned."""
    if not isinstance(value, dict) or set(value) != {"retrieval", "ranking", "ontology_version",
                                                     "search_mix"}:
        raise ConstitutionBreach(
            f"{knob} must carry exactly retrieval, ranking, ontology_version, search_mix")
    if value["retrieval"] not in MINER_RETRIEVAL:
        raise ConstitutionBreach(f"{knob}.retrieval={value['retrieval']!r} is not one of "
                                 f"{list(MINER_RETRIEVAL)}")
    if value["ranking"] not in MINER_RANKING:
        raise ConstitutionBreach(f"{knob}.ranking={value['ranking']!r} is not one of "
                                 f"{list(MINER_RANKING)}")
    ont = value["ontology_version"]
    if not isinstance(ont, str) or not _ONTOLOGY_RE.match(ont):
        raise ConstitutionBreach(f"{knob}.ontology_version={ont!r} must be a short declared id "
                                 f"like 'v1'..'v{ONTOLOGY_MAX}', never free text")
    mix = value["search_mix"]
    if not isinstance(mix, dict) or set(mix) != set(MINER_SEARCH_LANES):
        raise ConstitutionBreach(f"{knob}.search_mix must carry exactly "
                                 f"{list(MINER_SEARCH_LANES)}")
    for lane, s in mix.items():
        if not isinstance(s, (int, float)) or isinstance(s, bool) or float(s) < 0.0:
            raise ConstitutionBreach(f"{knob}.search_mix[{lane}]={s!r} must be a share >= 0")
    if abs(sum(float(s) for s in mix.values()) - 1.0) > 1e-6:
        raise ConstitutionBreach(f"{knob}.search_mix sums to "
                                 f"{sum(float(s) for s in mix.values()):.6f}, not 1.0")
    if float(mix["cold"]) < COLD_SEARCH_FLOOR - 1e-9:
        raise ConstitutionBreach(
            f"{knob}.search_mix.cold={mix['cold']} is below the COLD-SEARCH FLOOR "
            f"{COLD_SEARCH_FLOOR}. The floor is constitutional, not a tuning parameter: cold "
            f"search is the only lane that reaches ground the desk's own history cannot point "
            f"at, it pays last and rarely, and it is therefore the first thing any short-horizon "
            f"fitness would cut. A miner permitted to zero it optimises itself into the "
            f"neighbourhood of what it already knows.")


#: The knobs a variant may carry, with the bounds the wall enforces. `leg_budget_factors` and
#: `arm_weights` have NO enumerated domain: hourly_cycle's leg table moves weekly and a stale copy
#: here would refuse a live leg. The bound on the FACTOR is what protects the hour, and the wall
#: still reads every name.
POLICY_KNOBS: dict[str, dict[str, Any]] = {
    "leg_budget_factors": {"kind": "factors", "domain": None,
                           "consumer": "research_budget.budget_s (seconds per leg)"},
    "arm_weights": {"kind": "factors", "domain": None,
                    "consumer": "the proposal mix over research_bandit's arms"},
    "population_mix": {"kind": "shares", "domain": POPULATIONS,
                       "consumer": "search_populations.run (weights)"},
    "retrieval_depth": {"kind": "int", "lo": DEPTH_LO, "hi": DEPTH_HI,
                        "consumer": "deepening_worker (similar failures read per task)"},
    "prompt_template": {"kind": "choice", "domain": PROMPT_TEMPLATES,
                        "consumer": "the extraction seats"},
    "exploration_floor": {"kind": "float", "lo": EXPLORE_LO, "hi": EXPLORE_HI,
                          "consumer": "negative_knowledge.EXPLORE_FLOOR"},
    "department_factors": {"kind": "factors", "domain": DEPARTMENTS,
                           "consumer": "research_departments.factor_for"},
    "miner": {"kind": "miner",
              "consumer": "the intelligence miners (retrieval, ranking, ontology, search mix)",
              "bounds": {"retrieval": list(MINER_RETRIEVAL), "ranking": list(MINER_RANKING),
                         "ontology_version": f"v1..v{ONTOLOGY_MAX}",
                         "search_mix": f"{list(MINER_SEARCH_LANES)} sum to 1, "
                                       f"cold >= {COLD_SEARCH_FLOOR}"}},
    "meta_knobs": {"kind": "meta", "optional": True,
                   "consumer": "meta_rnd.META_KNOBS, one lineage among many"},
}


# --------------------------------------------------------------------------------------- policy
def _seed_arms() -> tuple[str, ...]:
    doc = _read_json(BANDIT)
    shares = doc.get("shares") if isinstance(doc, dict) else None
    names = set(SEED_ARMS) | (set(shares) if isinstance(shares, dict) else set())
    return tuple(sorted(names))


def _seed_legs() -> tuple[str, ...]:
    try:
        return tuple(sorted(importlib.import_module("research_budget").LEG_ARMS))
    except Exception:
        return ("alpha_evolution", "deepen")


def _equal_shares(names: tuple[str, ...]) -> dict[str, float]:
    share = round(1.0 / len(names), 6)
    out = dict.fromkeys(names, share)
    out[names[-1]] = round(1.0 - share * (len(names) - 1), 6)
    return out


def incumbent_policy() -> dict[str, Any]:
    """The desk as it runs today: every factor 1.0, every population equal, the constants as
    written. The incumbent is not a guess at a good policy -- it is the control arm."""
    return {
        "leg_budget_factors": dict.fromkeys(_seed_legs(), 1.0),
        "arm_weights": dict.fromkeys(_seed_arms(), 1.0),
        "population_mix": _equal_shares(POPULATIONS),
        "retrieval_depth": DEFAULT_RETRIEVAL_DEPTH,
        "prompt_template": "incumbent",
        "exploration_floor": DEFAULT_EXPLORATION_FLOOR,
        "department_factors": dict.fromkeys(DEPARTMENTS, 1.0),
        "miner": {"retrieval": "bm25", "ranking": "score", "ontology_version": "v1",
                  "search_mix": {"exploration": 0.30, "exploitation": 0.55, "cold": 0.15}},
        "meta_knobs": {},
    }


def policy_hash(policy: dict[str, Any]) -> str:
    body = json.dumps(policy, sort_keys=True, default=str).encode("utf-8")
    return hashlib.blake2b(body, digest_size=5).hexdigest()


def _knob_distance(knob: str, mine: Any, base: Any) -> float:
    """How far one knob moved from the incumbent, on a common 0..1-ish scale."""
    spec = POLICY_KNOBS[knob]
    kind = spec["kind"]
    if kind == "factors":
        keys = set(mine or {}) | set(base or {})
        return max((abs(float((mine or {}).get(k, 1.0)) - float((base or {}).get(k, 1.0)))
                    for k in keys), default=0.0)
    if kind == "shares":
        return max((abs(float((mine or {}).get(k, 0.0)) - float((base or {}).get(k, 0.0)))
                    * len(POPULATIONS) for k in POPULATIONS), default=0.0)
    if kind == "int":
        return abs(int(mine) - int(base)) / max(1, spec["hi"] - spec["lo"])
    if kind == "float":
        return abs(float(mine) - float(base)) / max(1e-9, spec["hi"] - spec["lo"])
    if kind == "choice":
        return 0.0 if mine == base else 1.0
    if kind == "miner":
        m, b = dict(mine or {}), dict(base or {})
        d = max(float(m.get(f) != b.get(f))
                for f in ("retrieval", "ranking", "ontology_version"))
        mm, bm = m.get("search_mix") or {}, b.get("search_mix") or {}
        return max(d, *(abs(float(mm.get(x, 0.0)) - float(bm.get(x, 0.0))) * len(
            MINER_SEARCH_LANES) for x in MINER_SEARCH_LANES))
    return 1.0 if (mine or {}) != (base or {}) else 0.0


def cluster_of(policy: dict[str, Any], base: dict[str, Any] | None = None) -> str:
    """The knob this variant moved FURTHEST from the incumbent. The archive keeps the best of each
    cluster, so a lineage that is behind today but exploring a knob nothing else touches is not
    deleted by a lineage that is ahead on a different one."""
    ref = base or incumbent_policy()
    dists = {k: _knob_distance(k, policy.get(k, ref.get(k)), ref.get(k))
             for k in POLICY_KNOBS if k in policy or k in ref}
    best = max(dists.items(), key=lambda kv: kv[1], default=("incumbent", 0.0))
    return best[0] if best[1] > 1e-9 else "incumbent"


# -------------------------------------------------------------------------------------- archive
def _new_variant(vid: str, parent: str | None, policy: dict[str, Any], born: str,
                 why: str) -> dict[str, Any]:
    return {"variant_id": vid, "parent": parent, "born_at": born, "why": why,
            "policy": policy, "fitness": dict.fromkeys(FITNESS_FIELDS), "active_windows": []}


def seed_archive(now: datetime) -> dict[str, Any]:
    pol = incumbent_policy()
    assert_constitution(pol)
    stamp = now.isoformat(timespec="seconds")
    inc = _new_variant("incumbent", None, pol, stamp,
                       "the desk as written: the control arm, never deleted")
    return {"variants": [inc], "active": "incumbent", "active_since": stamp,
            "history": [{"at": stamp, "event": "SEED", "to": "incumbent",
                         "why": "first run; the incumbent is the code as written"}],
            "rule": RULE}


def load_archive(now: datetime | None = None) -> dict[str, Any]:
    doc = _read_json(ARCHIVE)
    if not isinstance(doc, dict) or not isinstance(doc.get("variants"), list) \
            or not doc["variants"]:
        return seed_archive(now or datetime.now(tz=UTC))
    doc.setdefault("history", [])
    if not any(v.get("variant_id") == doc.get("active") for v in doc["variants"]
               if isinstance(v, dict)):
        doc["active"] = str(doc["variants"][0].get("variant_id"))
    return doc


def save_archive(arch: dict[str, Any]) -> None:
    """EVERY write goes through the wall, not just the mutations. A hand-edited archive is exactly
    the path a search would take to the judge if this only checked its own descendants."""
    for v in arch.get("variants", []):
        assert_constitution((v or {}).get("policy"))
    arch["rule"] = RULE
    _atomic_json(ARCHIVE, arch)


# -------------------------------------------------------------------------------------- fitness
def _graph_counts(start: datetime, end: datetime) -> dict[str, int]:
    born = certified = failed = 0
    for r in _tail_rows(GRAPH):
        if not _in_window(r, start, end):
            continue
        fate = str(r.get("fate") or "")
        born += fate == "BORN"
        certified += fate == "CERTIFIED"
        failed += fate == "FAILED"
    return {"born": born, "certified": certified, "failed": failed}


def _delta_n_eff(start: datetime, end: datetime) -> tuple[float | None, str]:
    rows = [(t, float(r["effective_breadth"])) for r in _tail_rows(BREADTH_HIST)
            if isinstance(r.get("effective_breadth"), (int, float))
            and (t := _parse_at(r.get("at"))) is not None and t <= end]
    if len(rows) < 2:
        return None, (f"{BREADTH_HIST.name} holds fewer than two readings at or before the "
                      f"window end")
    rows.sort(key=lambda x: x[0])
    inside = [v for t, v in rows if t >= start]
    before = [v for t, v in rows if t < start]
    if not inside:
        return None, "no effective-breadth reading inside the window at all"
    baseline = before[-1] if before else inside[0]
    if not before and len(inside) < 2:
        return None, "only one reading inside the window and none before it: no delta exists"
    return round(inside[-1] - baseline, 4), ""


def _novelty_rate(start: datetime, end: datetime) -> tuple[float | None, str]:
    doc = _read_json(NOVELTY)
    if not isinstance(doc, dict):
        return None, f"no readable {NOVELTY.name}"
    t = _parse_at(doc.get("at"))
    if t is None or not (start <= t <= end):
        return None, (f"{NOVELTY.name} is stamped {doc.get('at')!r}, outside this variant's "
                      f"window; a novelty rate from another window is not this one's measurement")
    novel, redundant = doc.get("n_novel"), doc.get("n_redundant")
    if not isinstance(novel, int) or not isinstance(redundant, int) or novel + redundant <= 0:
        return None, f"{NOVELTY.name} screened nothing in the window"
    return round(novel / (novel + redundant), 4), ""


def _shadow_counts(start: datetime, end: datetime) -> dict[str, int] | None:
    doc = _read_json(SHADOW)
    if not isinstance(doc, dict):
        return None
    c = {"certified_touched": 0, "certified_retired": 0, "touched": 0, "promoted": 0}
    for v in doc.values():
        if not isinstance(v, dict):
            continue
        status = str(v.get("status") or "")
        certified = (str(v.get("gate_admission") or "") == CERTIFIED_ADMISSION
                     or bool(v.get("promotion_authority")))
        touched = _in_window(v, start, end, "last_attempt_at")
        retired = _in_window(v, start, end, "retired_at")
        if certified and (touched or retired):
            c["certified_touched"] += 1
            if retired and status.startswith(("RETIRED", "QUARANTINED")):
                c["certified_retired"] += 1
        if touched and not status.startswith("BLOCKED"):
            c["touched"] += 1
            if bool(v.get("promotion_authority")) or status == "PROMOTION CANDIDATE":
                c["promoted"] += 1
    return c


def _verdict_fdr(start: datetime, end: datetime) -> tuple[float | None, int]:
    """Fallback FDR: cells the gates PASSED whose downstream_status later says they did not hold."""
    passed = failed = 0
    for r in _tail_rows(VERDICTS):
        if not _in_window(r, start, end) or not r.get("passed"):
            continue
        passed += 1
        ds = str(r.get("downstream_status") or "").upper()
        failed += any(w in ds for w in ("FAIL", "RETIR", "KILL", "QUARANT"))
    return (round(failed / passed, 4) if passed else None), passed


def _compute_cost(start: datetime, end: datetime) -> dict[str, float]:
    """The window's total spend, in the three currencies the ledger can carry.

    `data_s` is summed from whatever rows declare it and is 0.0 today, because the compute ledger
    does not yet record acquisition time separately. That is stated rather than hidden: the
    denominator is compute + data + wall, and one of its three terms is currently always zero.
    """
    cpu = wall = data = 0.0
    rows = 0
    for r in _tail_rows(COMPUTE):
        if not _in_window(r, start, end):
            continue
        rows += 1
        for key, add in (("cpu_s", "cpu"), ("wall_s", "wall"), ("data_s", "data")):
            v = r.get(key)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if add == "cpu":
                    cpu += float(v)
                elif add == "wall":
                    wall += float(v)
                else:
                    data += float(v)
    return {"cpu_s": round(cpu, 3), "wall_s": round(wall, 3), "data_s": round(data, 3),
            "total_s": round(cpu + wall + data, 3), "rows": float(rows),
            "compute_hours": round(wall / 3600.0, 4)}


#: A forward clock counts as FORWARD-VALID when the desk would act on it: it holds promotion
#: authority, it is standing as a promotion candidate, or it carries the ten-gate certificate and
#: is still running. Retired, quarantined, blocked and policy-refused rows are none of those.
def _forward_valid(v: dict[str, Any]) -> bool:
    status = str(v.get("status") or "")
    if status.startswith(("RETIRED", "QUARANTINED", "BLOCKED", "REFUSED")):
        return False
    return (bool(v.get("promotion_authority")) or status == "PROMOTION CANDIDATE"
            or (str(v.get("gate_admission") or "") == CERTIFIED_ADMISSION and status == "ACTIVE"))


def _independence_basis() -> tuple[str, dict[str, str], dict[str, set[str]]] | None:
    """(source, member -> independence class, member -> near-twins), or None when the desk cannot
    currently say whether two survivors are the same bet. NEVER guesses: without one of these
    artifacts the count is UNMEASURED, because "independent" is the whole content of the claim."""
    d = _read_json(EXPOSURE)
    if isinstance(d, dict) and isinstance(d.get("sleeves"), list):
        classes: dict[str, str] = {}
        for row in [*d.get("sleeves", []), *(d.get("positions") or [])]:
            if isinstance(row, dict) and row.get("name"):
                classes[str(row["name"])] = str(row["name"])
        twins: dict[str, set[str]] = {}
        for pair in d.get("duplicate_heat") or []:
            if not isinstance(pair, dict) or float(pair.get("cosine") or 0.0) < DUP_COSINE:
                continue
            a, b = str(pair.get("a")), str(pair.get("b"))
            twins.setdefault(a, set()).add(b)
            twins.setdefault(b, set()).add(a)
            classes.setdefault(a, a)
            classes.setdefault(b, a)          # a twin belongs to its partner's class, not its own
        if classes:
            return EXPOSURE.name, classes, twins
    c = _read_json(CREDIT)
    lanes = c.get("by_representation_lane") if isinstance(c, dict) else None
    if isinstance(lanes, list):
        classes = {}
        for lane in lanes:
            if not isinstance(lane, dict):
                continue
            name = str(lane.get("lane") or lane.get("name") or "")
            for m in (lane.get("members") or lane.get("cells") or lane.get("sleeves") or []):
                classes[str(m)] = name or str(m)
        if classes:
            return CREDIT.name, classes, {}
    return None


def _alpha_per_cost(start: datetime, end: datetime,
                    cost: dict[str, float]) -> tuple[float | None, str, dict[str, Any]]:
    """NEW INDEPENDENT forward-valid survivors born in the window, per second of total spend.

    THE HEADLINE TERM, and the only one that divides what the research produced by what it cost.
    Two ways it comes back UNMEASURED and neither is a zero: no spend was recorded (the rate has
    no denominator) or the desk cannot establish independence for the survivors it found (the
    numerator would then be a count of names, not of bets). Zero survivors against a real spend IS
    a measurement -- it says this window bought nothing -- and it is reported as 0.0.
    """
    doc = _read_json(SHADOW)
    detail: dict[str, Any] = {"n_born": 0, "n_independent": None, "basis": None}
    if not isinstance(doc, dict):
        return None, f"no readable {SHADOW.name} to count survivors in", detail
    born = [(str(k), v) for k, v in doc.items()
            if isinstance(v, dict) and _in_window(v, start, end, "forward_start")
            and _forward_valid(v)]
    detail["n_born"] = len(born)
    if cost["total_s"] <= 0.0:
        return None, ("no compute, data or wall seconds were recorded in the window "
                      f"({COMPUTE.name}); a rate per unit of spend has no denominator"), detail
    basis = _independence_basis()
    if basis is None:
        return None, (f"neither {EXPOSURE.name} nor {CREDIT.name} can say whether two survivors "
                      f"are the same bet, so 'independent' cannot be established -- a raw count "
                      f"of names would be a different and weaker claim"), detail
    source, classes, twins = basis
    detail["basis"] = source
    counted: dict[str, str] = {}
    unresolved = 0
    for key, v in sorted(born):
        names = [str(v.get("sleeve_id") or ""), key, key.split(".")[0]]
        name = next((n for n in names if n and n in classes), None)
        if name is None:
            unresolved += 1
            continue
        cls = classes[name]
        if cls in counted.values() or any(t in counted for t in twins.get(name, ())):
            continue
        counted[name] = cls
    detail.update({"n_independent": len(counted), "n_unresolved": unresolved,
                   "counted": sorted(counted)})
    if born and not counted and unresolved == len(born):
        return None, (f"{len(born)} forward-valid survivor(s) were born in the window and none "
                      f"of them appears in {source}; independence is unmeasurable for every one"), \
            detail
    return round(len(counted) / cost["total_s"], 9), "", detail


def measure_fitness(start: datetime, end: datetime) -> tuple[dict[str, Any], list[dict[str, str]],
                                                             dict[str, Any]]:
    """The active variant's seven numbers over its own window. A field the ledgers cannot answer
    stays NULL and is named in `unmeasured` -- a zero would say the research ran and produced
    nothing, which is a different and much stronger claim (L1.28a)."""
    fit: dict[str, Any] = dict.fromkeys(FITNESS_FIELDS)
    un: list[dict[str, str]] = []
    g = _graph_counts(start, end)
    cost = _compute_cost(start, end)
    hours = cost["compute_hours"]
    sh = _shadow_counts(start, end)
    counts: dict[str, Any] = {**g, "compute_hours": hours, "compute_rows": int(cost["rows"]),
                              "cost": cost, "shadow": sh}

    apc, why, detail = _alpha_per_cost(start, end, cost)
    fit["forward_valid_alpha_per_cost"] = apc
    counts["alpha_per_cost"] = detail
    if apc is None:
        un.append({"field": "forward_valid_alpha_per_cost", "why": why})

    if g["born"] > 0:
        fit["survivor_yield"] = round(g["certified"] / g["born"], 5)
    else:
        un.append({"field": "survivor_yield",
                   "why": f"no hypothesis was BORN in the window in {GRAPH.name}"})

    d, why = _delta_n_eff(start, end)
    fit["delta_n_eff"] = d
    if d is None:
        un.append({"field": "delta_n_eff", "why": why})

    nr, why = _novelty_rate(start, end)
    fit["novel_mechanism_rate"] = nr
    if nr is None:
        un.append({"field": "novel_mechanism_rate", "why": why})

    if sh and sh["certified_touched"] > 0:
        fit["false_discovery_rate"] = round(sh["certified_retired"] / sh["certified_touched"], 4)
    else:
        alt, n_passed = _verdict_fdr(start, end)
        counts["verdict_passed_rows"] = n_passed
        fit["false_discovery_rate"] = alt
        if alt is None:
            un.append({"field": "false_discovery_rate",
                       "why": ("no certified forward clock was touched or retired in the window "
                               f"({SHADOW.name}) and no passed cell in {VERDICTS.name} carries a "
                               "downstream status")})

    if g["certified"] > 0:
        fit["compute_per_survivor"] = round(hours / g["certified"], 4)
    else:
        un.append({"field": "compute_per_survivor",
                   "why": (f"{hours} wall-hour(s) of compute and zero survivors in the window: "
                           "the ratio has no denominator. The cost is reported in `counts`, "
                           "because calling it zero would invert its sign.")})

    if sh and sh["touched"] > 0:
        fit["forward_success"] = round(sh["promoted"] / sh["touched"], 4)
    else:
        un.append({"field": "forward_success",
                   "why": f"no forward clock was attempted in the window ({SHADOW.name})"})
    return fit, un, counts


#: THE DECLARED EXCHANGE RATE, (sign, scale) per field, IN ORDER. A composite over unlike units --
#: a rate, a count of bets, an hour of CPU -- is honest only if the rates are written down; these
#: are them, and nothing else in this file weights anything. Every term is clipped to [-1, 1] so no
#: single pathological reading (a compute spike, an n_eff jump) can swamp the other six.
#: `forward_valid_alpha_per_cost` is FIRST because it is the only term that is the thing itself;
#: the six behind it are leading indicators of it, and they are here because it is thin.
COMPOSITE_TERMS: dict[str, tuple[float, float]] = {
    "forward_valid_alpha_per_cost": (+1.0, ALPHA_COST_SCALE),
    "survivor_yield": (+1.0, 1.0), "delta_n_eff": (+1.0, DELTA_NEFF_SCALE),
    "novel_mechanism_rate": (+1.0, 1.0), "false_discovery_rate": (-1.0, 1.0),
    "compute_per_survivor": (-1.0, CPS_SCALE_H), "forward_success": (+1.0, 1.0),
}


def composite_of(fit: dict[str, Any]) -> tuple[float | None, int, dict[str, float]]:
    """The declared exchange rate applied. Only MEASURED components enter the sum; `n_measured`
    travels with it so a variant judged on two fields is never silently compared to one judged on
    six, and an all-null fitness returns None rather than a flattering 0.0."""
    terms: dict[str, float] = {}
    for field, (sign, scale) in COMPOSITE_TERMS.items():
        v = fit.get(field)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            terms[field] = round(sign * max(-1.0, min(1.0, float(v) / scale)), 5)
    if not terms:
        return None, 0, {}
    return round(sum(terms.values()), 5), len(terms), terms


# ------------------------------------------------------------------------------------ selection
def variant_composite(v: dict[str, Any]) -> tuple[float | None, int]:
    """A variant's score is the MEAN composite over the windows it was actually seated for, not
    the reading taken mid-window. The in-progress `fitness` is used only by a variant that has
    never completed a window, so one quiet hour cannot erase a lineage's record."""
    comps, meas = [], 0
    for w in v.get("active_windows") or []:
        if isinstance(w, dict) and isinstance(w.get("composite"), (int, float)):
            comps.append(float(w["composite"]))
            meas = max(meas, int(w.get("n_measured") or 0))
    if comps:
        return round(sum(comps) / len(comps), 5), meas
    comp, n_meas, _ = composite_of(v.get("fitness") or {})
    return comp, n_meas


def leaderboard(arch: dict[str, Any]) -> list[dict[str, Any]]:
    """UCB over the archive.

    OPTIMISM ABOUT THE UNTRIED IS THE ARCHIVE'S MEAN, NOT ITS MAXIMUM. A descendant that has shown
    nothing does not inherit the best member's score -- if it did, every freshly bred child would
    top the board and the seat would be a random walk over one-window mutations, which is the
    failure mode of an archive that explores without ever accumulating evidence.
    """
    rows: list[dict[str, Any]] = []
    base = incumbent_policy()
    for v in arch.get("variants", []):
        if not isinstance(v, dict):
            continue
        comp, n_meas = variant_composite(v)
        rows.append({"variant_id": v.get("variant_id"), "parent": v.get("parent"),
                     "cluster": cluster_of(v.get("policy") or {}, base),
                     "composite": comp, "n_measured": n_meas,
                     "n_windows": len(v.get("active_windows") or []),
                     "fitness": v.get("fitness") or {}})
    measured = [r["composite"] for r in rows if r["composite"] is not None]
    optimistic = round(sum(measured) / len(measured), 5) if measured else 0.0
    total = max(2, sum(r["n_windows"] for r in rows))
    for r in rows:
        base_score = r["composite"] if r["composite"] is not None else optimistic
        bonus = UCB_C * math.sqrt(math.log(total) / max(1, r["n_windows"]))
        r["ucb"] = round(base_score + bonus, 5)
        r["optimistic"] = r["composite"] is None
        r["prior"] = optimistic if r["optimistic"] else None
    rows.sort(key=lambda r: (-r["ucb"], str(r["variant_id"])))
    return rows


def prune(arch: dict[str, Any], keep: int = MAX_VARIANTS) -> list[str]:
    """The diverse-archive rule: the best of EVERY occupied cluster survives before any second
    member of any cluster does. The incumbent and the seated variant are never dropped."""
    variants = [v for v in arch.get("variants", []) if isinstance(v, dict)]
    if len(variants) <= keep:
        return []
    by_id = {str(v.get("variant_id")): v for v in variants}
    rank = {r["variant_id"]: i for i, r in enumerate(leaderboard(arch))}
    ordered = sorted(by_id, key=lambda vid: rank.get(vid, 10**6))
    protected = {"incumbent", str(arch.get("active"))}
    kept: list[str] = [vid for vid in ordered if vid in protected]
    seen_clusters = {cluster_of(by_id[vid].get("policy") or {}) for vid in kept}
    for vid in ordered:                      # one per cluster first
        c = cluster_of(by_id[vid].get("policy") or {})
        if vid not in kept and c not in seen_clusters:
            kept.append(vid)
            seen_clusters.add(c)
    for vid in ordered:                      # then fill by rank
        if len(kept) >= keep:
            break
        if vid not in kept:
            kept.append(vid)
    dropped = [vid for vid in ordered if vid not in kept]
    arch["variants"] = [by_id[vid] for vid in ordered if vid in kept]
    return dropped


# ------------------------------------------------------------------------------------- mutation
def _mutate_miner(miner: dict[str, Any], rng: Any) -> tuple[dict[str, Any], str]:
    """One sub-knob of the MinerOS block. The cold lane is restored to its floor AFTER
    renormalisation, never before: a mutation that pushed the other two lanes up would otherwise
    take cold under the floor by arithmetic rather than by intent, and arrive at the same place."""
    which = str(rng.choice(np.array(["retrieval", "ranking", "ontology_version", "search_mix"],
                                    dtype=object)))
    if which in ("retrieval", "ranking"):
        domain = MINER_RETRIEVAL if which == "retrieval" else MINER_RANKING
        options = [o for o in domain if o != miner.get(which)]
        new = str(rng.choice(np.array(options, dtype=object)))
        detail = f"{which} {miner.get(which)} -> {new}"
        miner[which] = new
        return miner, detail
    if which == "ontology_version":
        cur = str(miner.get("ontology_version") or "v1")
        n_cur = int("".join(c for c in cur if c.isdigit()) or "1")
        options = [i for i in range(1, ONTOLOGY_MAX + 1) if i != n_cur]
        new_v = f"v{int(rng.choice(np.array(options)))}"
        detail = f"ontology_version {cur} -> {new_v}"
        miner["ontology_version"] = new_v
        return miner, detail
    lane = str(rng.choice(np.array(list(MINER_SEARCH_LANES), dtype=object)))
    raw = {k: max(0.005, float(v)) for k, v in (miner.get("search_mix") or {}).items()}
    before = round(raw.get(lane, 0.0), 6)
    raw[lane] = max(0.005, raw[lane] * float(rng.uniform(0.5, 1.8)))
    tot = sum(raw.values())
    mix = {k: v / tot for k, v in raw.items()}
    if mix["cold"] < COLD_SEARCH_FLOOR:                     # the floor, restored by construction
        spare = 1.0 - COLD_SEARCH_FLOOR
        rest = mix["exploration"] + mix["exploitation"]
        mix = {"cold": COLD_SEARCH_FLOOR,
               "exploration": spare * (mix["exploration"] / rest if rest else 0.5),
               "exploitation": spare * (mix["exploitation"] / rest if rest else 0.5)}
    mix = {k: round(mix[k], 6) for k in MINER_SEARCH_LANES}
    mix["exploitation"] = round(1.0 - mix["exploration"] - mix["cold"], 6)
    miner["search_mix"] = mix
    return miner, f"search_mix.{lane} {before} -> {mix[lane]}"


def propose_descendant(arch: dict[str, Any], now: datetime,
                       seed: int | None = None) -> tuple[dict[str, Any] | None, str]:
    """One descendant per run, ONE knob moved, inside the declared bounds, lineage recorded.

    One knob because a child that moves five knobs and scores better tells the archive nothing
    about which of the five did it -- and the archive is the only thing here that learns.
    """
    parent = next((v for v in arch.get("variants", [])
                   if isinstance(v, dict) and v.get("variant_id") == arch.get("active")), None)
    if parent is None:
        return None, "no active variant to breed from"
    if seed is None:
        key = f"{arch.get('active')}|{len(arch.get('variants', []))}|{len(arch.get('history', []))}"
        seed = int.from_bytes(hashlib.blake2b(key.encode("utf-8"), digest_size=4).digest(), "big")
    rng = np.random.default_rng(seed)
    pol = json.loads(json.dumps(parent.get("policy") or incumbent_policy()))

    knobs = [k for k in POLICY_KNOBS if k in pol]
    knob = str(rng.choice(np.array(knobs, dtype=object)))
    spec = POLICY_KNOBS[knob]
    detail = ""
    if spec["kind"] == "factors":
        names = sorted(pol[knob])
        name = str(rng.choice(np.array(names, dtype=object)))
        new = float(np.clip(float(pol[knob][name]) * float(rng.uniform(0.75, 1.35)),
                            FACTOR_LO, FACTOR_HI))
        detail = f"{name} {pol[knob][name]} -> {round(new, 4)}"
        pol[knob][name] = round(new, 4)
    elif spec["kind"] == "shares":
        name = str(rng.choice(np.array(list(POPULATIONS), dtype=object)))
        raw = {k: max(0.005, float(v)) for k, v in pol[knob].items()}
        raw[name] = max(0.005, raw[name] * float(rng.uniform(0.5, 1.8)))
        tot = sum(raw.values())
        shares = {k: round(v / tot, 6) for k, v in raw.items()}
        shares[POPULATIONS[-1]] = round(1.0 - sum(v for k, v in shares.items()
                                                  if k != POPULATIONS[-1]), 6)
        detail = f"{name} {pol[knob][name]} -> {shares[name]}"
        pol[knob] = shares
    elif spec["kind"] == "int":
        step = int(rng.integers(1, 4)) * (1 if rng.random() < 0.5 else -1)
        new_i = int(np.clip(int(pol[knob]) + step, spec["lo"], spec["hi"]))
        detail = f"{pol[knob]} -> {new_i}"
        pol[knob] = new_i
    elif spec["kind"] == "float":
        new_f = float(np.clip(float(pol[knob]) + float(rng.uniform(-0.08, 0.08)),
                              spec["lo"], spec["hi"]))
        detail = f"{pol[knob]} -> {round(new_f, 4)}"
        pol[knob] = round(new_f, 4)
    elif spec["kind"] == "choice":
        options = [o for o in spec["domain"] if o != pol[knob]]
        new_c = str(rng.choice(np.array(options, dtype=object)))
        detail = f"{pol[knob]} -> {new_c}"
        pol[knob] = new_c
    elif spec["kind"] == "miner":
        pol[knob], detail = _mutate_miner(dict(pol[knob]), rng)
    elif spec["kind"] == "meta":
        specs = meta_knob_specs()
        if not specs:
            return None, "meta_rnd.META_KNOBS is not importable; nothing to move there"
        name = str(rng.choice(np.array(sorted(specs), dtype=object)))
        lo, hi = float(specs[name]["lo"]), float(specs[name]["hi"])
        val: float | int = float(round(rng.uniform(lo, hi), 4))
        if isinstance(specs[name]["lo"], int) and isinstance(specs[name]["hi"], int):
            val = round(val)
        detail = f"{name} -> {val}"
        pol[knob] = {**(pol.get(knob) or {}), name: val}

    try:
        assert_constitution(pol)
    except ConstitutionBreach as exc:
        return None, f"REFUSED BY THE WALL: {exc}"
    h = policy_hash(pol)
    if any(policy_hash((v or {}).get("policy") or {}) == h for v in arch.get("variants", [])):
        return None, f"the descendant ({knob}: {detail}) is already in the archive"
    vid = f"v{len(arch.get('variants', [])):03d}_{knob}_{h[:4]}"
    child = _new_variant(vid, str(parent.get("variant_id")), pol,
                         now.isoformat(timespec="seconds"),
                         f"descendant of {parent.get('variant_id')}: {knob} {detail}")
    child["mutated_knob"] = knob
    child["mutation"] = detail
    return child, ""


# ------------------------------------------------------------------------------------ the organ
def build(window_hours: float = WINDOW_HOURS, now: datetime | None = None,
          seed: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Measure the seat, select, mutate. Returns (report, archive); the caller decides to write."""
    now = now or datetime.now(tz=UTC)
    refused: list[str] = []
    arch = load_archive(now)
    active = str(arch.get("active"))
    since = _parse_at(arch.get("active_since")) or now
    start = max(since, now - timedelta(hours=WINDOW_CAP_H))
    elapsed_h = round((now - since).total_seconds() / 3600.0, 3)

    fit, unmeasured, counts = measure_fitness(start, now)
    comp, n_meas, terms = composite_of(fit)
    seated = next((v for v in arch["variants"] if v.get("variant_id") == active), None)
    if seated is not None:
        seated["fitness"] = fit
        if elapsed_h >= window_hours:
            seated.setdefault("active_windows", []).append(
                {"from": start.isoformat(timespec="seconds"),
                 "to": now.isoformat(timespec="seconds"), "hours": elapsed_h,
                 "fitness": fit, "composite": comp, "n_measured": n_meas})

    board = leaderboard(arch)
    best = board[0] if board else None
    rotation: dict[str, Any] = {"rotated": False, "from": active, "to": active,
                                "elapsed_h": elapsed_h, "window_hours": window_hours}
    if elapsed_h < window_hours:
        rotation["why"] = (f"seated {elapsed_h}h of a {window_hours}h window; rotating now would "
                           f"leave a window too short to measure and select on its noise")
    elif best is None or best["variant_id"] == active:
        rotation["why"] = "the seated variant still leads the UCB board; ties hold the incumbent"
    else:
        cur = next((r for r in board if r["variant_id"] == active), None)
        if cur is not None and best["ucb"] <= cur["ucb"] + 1e-9:
            rotation["why"] = "no challenger is strictly ahead on UCB"
        else:
            seen = " (optimistic: never seated)" if best["optimistic"] else ""
            why_rotate = (f"UCB {best['ucb']} beats the seated "
                          f"{cur['ucb'] if cur else None}{seen}")
            arch["active"] = str(best["variant_id"])
            arch["active_since"] = now.isoformat(timespec="seconds")
            rotation.update({"rotated": True, "to": arch["active"],
                             "why": why_rotate})
            arch.setdefault("history", []).append(
                {"at": arch["active_since"], "event": "ROTATE", "from": active,
                 "to": arch["active"], "why": rotation["why"]})

    child, why_no_child = propose_descendant(arch, now, seed)
    if child is not None:
        arch["variants"].append(child)
        arch.setdefault("history", []).append(
            {"at": now.isoformat(timespec="seconds"), "event": "PROPOSE",
             "to": child["variant_id"], "parent": child["parent"], "why": child["why"]})
    elif why_no_child.startswith("REFUSED"):
        refused.append(why_no_child)

    dropped = prune(arch)
    board = leaderboard(arch)
    clusters: dict[str, Any] = {}
    for r in board:
        c = str(r["cluster"])
        if c not in clusters:
            clusters[c] = {"n": 0, "best": r["variant_id"], "best_composite": r["composite"]}
        clusters[c]["n"] += 1

    immut = immutable_paths()
    report = {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "n_variants": len(arch["variants"]),
        "active": arch["active"],
        "active_since": arch.get("active_since"),
        "window_hours": window_hours,
        "measured_window": {"from": start.isoformat(timespec="seconds"),
                            "to": now.isoformat(timespec="seconds"), "hours": elapsed_h},
        "fitness_active": {**fit, "composite": comp, "n_measured": n_meas, "terms": terms},
        "counts": counts,
        "leaderboard": board[:MAX_VARIANTS],
        "descendant_proposed": ({"variant_id": child["variant_id"], "parent": child["parent"],
                                 "knob": child["mutated_knob"], "change": child["mutation"]}
                                if child is not None else None),
        "descendant_why_not": None if child is not None else why_no_child,
        "clusters": clusters,
        "dropped": dropped,
        "rotation": rotation,
        "policy_knobs": {k: {kk: vv for kk, vv in v.items() if kk != "domain"}
                         for k, v in POLICY_KNOBS.items()},
        "wall": {"immutable_checked": bool(immut), "n_immutable_files": len(immut),
                 "forbidden_knob_classes": sorted(forbidden_knobs()),
                 "forbidden_moat_classes": sorted(FORBIDDEN_MOAT_KNOBS),
                 "cold_search_floor": COLD_SEARCH_FLOOR,
                 "refused": refused,
                 "why": ("a variant that could name the gate, the heat law, the lot floor, the "
                         "trial charge, a claim's provenance, point-in-time, the trial count, a "
                         "sealed holdout, a forward clock or the realised cost would eventually "
                         "find that moving it is the cheapest way to raise its own score. The "
                         "path does not exist here, and neither does a cold lane below "
                         f"{COLD_SEARCH_FLOOR}.")},
        "unmeasured": unmeasured,
        "rule": RULE,
    }
    return report, arch


def run(window_hours: float = WINDOW_HOURS, dry_run: bool = False,
        now: datetime | None = None, seed: int | None = None) -> dict[str, Any]:
    report, arch = build(window_hours, now, seed)
    if not dry_run:
        save_archive(arch)
        _atomic_json(OUT, report)
    report["written"] = not dry_run
    return report


# ------------------------------------------------------------------------------------- consumer
def active_policy() -> dict[str, Any]:
    """What the hour should do, for `research_budget` (leg factors) and the deepening worker
    (retrieval_depth). NEVER raises: an unreadable or breaching archive returns the incumbent with
    the reason attached, because a research policy that can stall the hour is worse than none."""
    inc = incumbent_policy()
    doc = _read_json(ARCHIVE)
    if not isinstance(doc, dict) or not isinstance(doc.get("variants"), list):
        return {"variant_id": "incumbent", "source": "incumbent_fallback",
                "why": f"no readable {ARCHIVE.name}", **inc}
    vid = str(doc.get("active") or "incumbent")
    var = next((v for v in doc["variants"]
                if isinstance(v, dict) and v.get("variant_id") == vid), None)
    pol = (var or {}).get("policy")
    try:
        assert_constitution(pol)
    except ConstitutionBreach as exc:
        return {"variant_id": "incumbent", "source": "incumbent_fallback",
                "why": f"the seated variant {vid!r} was refused by the wall: {exc}", **inc}
    return {"variant_id": vid, "source": "archive", "why": "", **{**inc, **pol}}


def leg_factor(leg: str) -> float:
    """The seated variant's multiplier for one leg; 1.0 when it names none."""
    f = (active_policy().get("leg_budget_factors") or {}).get(leg)
    return float(f) if isinstance(f, (int, float)) and FACTOR_LO <= f <= FACTOR_HI else 1.0


def retrieval_depth() -> int:
    d = active_policy().get("retrieval_depth")
    return int(d) if isinstance(d, int) and DEPTH_LO <= d <= DEPTH_HI else DEFAULT_RETRIEVAL_DEPTH


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ResearchOS variant archive (Q1/W12)")
    ap.add_argument("--window-hours", type=float, default=WINDOW_HOURS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(argv)
    r = run(a.window_hours, a.dry_run, seed=a.seed)
    print(f"research OS archive: {r['n_variants']} variant(s), active {r['active']} "
          f"(since {r['active_since']}, {r['measured_window']['hours']}h)")
    f = r["fitness_active"]
    shown = "  ".join(f"{k}={'UNMEASURED' if f.get(k) is None else f[k]}" for k in FITNESS_FIELDS)
    print(f"  fitness: {shown}")
    print(f"  composite {f['composite']} over {f['n_measured']}/{len(FITNESS_FIELDS)} measured")
    for row in r["leaderboard"][:5]:
        print(f"    {row['variant_id']!s:<28} cluster={row['cluster']!s:<20} "
              f"comp={row['composite']} ucb={row['ucb']} windows={row['n_windows']}")
    clusters = ", ".join(f"{k}:{v['n']}" for k, v in r["clusters"].items())
    print(f"  clusters: {clusters}")
    rot = r["rotation"]
    moved = f"ROTATED -> {rot['to']}" if rot["rotated"] else "HELD"
    print(f"  rotation: {moved} -- {str(rot.get('why', ''))[:90]}")
    d = r["descendant_proposed"]
    kid = f"{d['variant_id']} ({d['knob']}: {d['change']})" if d else r["descendant_why_not"]
    print(f"  descendant: {kid}")
    print(f"  wall: immutable_checked={r['wall']['immutable_checked']} "
          f"({r['wall']['n_immutable_files']} files), refused={len(r['wall']['refused'])}")
    for u in r["unmeasured"]:
        print(f"    UNMEASURED {u['field']}: {u['why'][:100]}")
    print(f"  {'-> ' + str(OUT) if r['written'] else '--dry-run; nothing written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
