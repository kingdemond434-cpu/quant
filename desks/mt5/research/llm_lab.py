"""THE OWNED 24/7 MULTI-LAB LLM RESEARCH CIVILIZATION -- reckless questions, ruthless judging.

    py -3 desks/mt5/research/llm_lab.py --once --budget-s 600     # one pass (the hourly leg)
    py -3 desks/mt5/research/llm_lab.py --dry-run                 # plan the pass, call nothing

THE PRINCIPAL'S ORDERS (2026-10-11 / 2026-10-12, standing): a permanent, desk-OWNED laboratory of
independent research labs that continuously invents genuinely novel, economically coherent,
EXECUTABLE strategy hypotheses for the canonical gauntlet -- free-first, never banal, never a
duplicate, never a raw row left sitting untestable, and never with any authority of its own.

WHAT THE DESK OWNS HERE, AND WHAT IS ONLY RENTED. Owned: the lab mandates, the prompts (through
`proposer_seat.build_prompt`, the one hygiene-scanned composer), the coverage map, the ontology,
the novelty classes, the banal filter, the genealogy, the exact-rule compiler, the conversion
debt, the model registry and every artifact. Rented: completions, from `libs.ops.free_chain`
(free cloud providers, then a LOCAL model) and the existing free panel / seat behind
`proposer_seat._ask`. Any provider can vanish and the lab keeps running on the next rung.

THE FUNDAMENTAL LAW, AS CODE.

    GENERATION   sixteen labs (A-P), each with its own scientific mandate, each asked about one
                 coordinate of the research tensor per pass WITHOUT seeing any other lab's current
                 answers (the independent first pass). Then a synthesis call composes across labs
                 and the red team (Lab P) attacks what came back. No lab ever sees a score.
    VALIDATION   none here. An accepted mechanism becomes an ordinary `kind: hypothesis` row with
                 an exact registered-family recipe under `data/intelligence/llm_lab/`, which the
                 miner candidate compiler reads like every other seat's donation, and the same ten
                 gates judge it. Models have ZERO promotion authority: `proposer_seat` strips any
                 verdict a model volunteers and charges every accepted proposal its trials.

EVERY PROPOSAL ENDS IN EXACTLY ONE OF THESE, NEVER SILENTLY:

    EMITTED              an exact cell of a registered family (or a valid `formula` expression),
                         novelty class MECHANISM_NEIGHBOUR / COMPOSITIONAL_DESCENDANT /
                         GENUINELY_NOVEL, donated for the gauntlet
    EXACT_DUPLICATE      collapsed onto the twin it names (no trial spent)
    PARAMETER_NEIGHBOUR  recorded under its parent's genealogy (a sweep step, not a new bet)
    BANAL_BASELINE       a generic indicator recipe; kept as a baseline, never credited as research
    CONVERSION DEBT      NEEDS_DATA / NEEDS_EXACT_RULE_EXTRACTION / NEEDS_PIT_SOURCE /
                         NEEDS_EXECUTABLE_FAMILY / NEEDS_PARAMETER_INFERENCE /
                         NEEDS_INSTRUMENT_MAPPING -- persisted, re-compiled every pass (temporal
                         reopening: a new family, series or symbol resolves it), and the
                         rule-shaped debts are re-asked to a converter call. NEEDS_DATA writes a
                         named data request for the miners. Nothing is invented to close a gap.
    REFUSED              a banned family, or a symbol the lane policy forbids for that family

COVERAGE CONSERVATION. The coordinate space is lab x mechanism class x asset class x horizon, and
the mechanism ontology is NEVER closed: any class a lab names that the ontology lacks is added and
becomes owed work for every lab. A per-pass cap means NOT THIS PASS -- owed coordinates are kept,
counted and visited in stable cursor order, with a permanent cold-exploration share drawn at
random so no region ever has zero probability, and a yield share that returns to coordinates
whose descendants survived.

MODELS COMPETE FOR WORK. Every free model the chain can list is registered (local models only
after a license review against an allowlist); each lab's model is drawn by Thompson sampling on
that model's measured rate of novel exact cells, so new models are tried and productive ones earn
more of the hour. A model's record is a measurement of usefulness, never of truth.

BUDGET. Paid spend is OFF: this process forces QUANT_FREE_TIER=1 unless the principal sets
QUANT_LLM_LAB_PAID=1, and then `llm_seat`'s own monthly cap still binds. Calls per pass and per
day are capped (QUANT_LLM_LAB_MAX_CALLS, QUANT_LLM_LAB_DAILY_CALLS); a capped pass is owed work.

JEV (Lab L). The semantic lab writes typed questions into a persistent job queue and compiles each
into an `exogenous_conditioner` cell on the question's own series. Until a Jev feature series
exists in the lake the cell is NEEDS_DATA debt, and the Jev provider reads UNMEASURED: no
TypeSafe adapter is wired because no key is acquired and its current API was not verified, and
this module will not guess an API's fields.

CENTRAL-BANK TONE (role CB_TONE, `cb_tone_lab.py`). PBoC, BoJ, SARB, RBA and CBRT statements read
in their original language, scored by a native lexicon and by a free-tier model, written as PIT
lake series `cb_tone_<bank>` and donated as conditioner cells; contaminated model readings are
kept out of the donated columns by the look-ahead guard.

    desks/mt5/reports/LLM_LAB.json                     the pass, the coverage, the models, the debt
    desks/mt5/data/intelligence/llm_lab/discoveries_*  the donations the compiler reads
    desks/mt5/data/llm_lab/*                           the lab's own state (outside intelligence/)
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import json
import math
import os
import random
import re
import sys
import threading
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if "libs" in sys.modules and not getattr(sys.modules["libs"], "__file__", None):
    for _m in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
        del sys.modules[_m]

STATE_DIR = BASE / "data" / "llm_lab"
DONATE_DIR = BASE / "data" / "intelligence" / "llm_lab"
REPORT = BASE / "reports" / "LLM_LAB.json"
GAUNTLET = BASE / "scripts" / "external_gauntlet.py"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SARES_DIR = BASE / "data" / "intelligence" / "sares"

GENEALOGY = STATE_DIR / "genealogy.jsonl"
DEBT = STATE_DIR / "conversion_debt.json"
COVERAGE = STATE_DIR / "coverage.json"
ONTOLOGY = STATE_DIR / "ontology.json"
MODELS = STATE_DIR / "model_registry.json"
DATA_REQUESTS = STATE_DIR / "data_requests.jsonl"
JEV_JOBS = STATE_DIR / "jev_jobs.jsonl"
CALLS = STATE_DIR / "calls.json"
ROTATION = STATE_DIR / "model_rotation.json"

ORGAN = "llm_lab"
UNMEASURED = "UNMEASURED"
RULE = ("THE LAB PROPOSES, THE DESK JUDGES: every row here is a hypothesis for the canonical "
        "gauntlet with no credibility inherited and no bypass")

# ============================================================================ the labs
@dataclass(frozen=True)
class Lab:
    key: str
    name: str
    mandate: str
    seeds: tuple[str, ...]                    #: mechanism classes this lab starts the map with
    feeds: tuple[str, ...] = ()               #: graveyard | sares | survivors | disagreement | jev
    families: tuple[str, ...] = ()            #: families this lab should see first in its menu


LABS: tuple[Lab, ...] = (
    Lab("A", "unknown_unknown",
        "Search for mechanism CLASSES absent from the current ontology. Question the search "
        "space itself: what participant, constraint, clock or information path does no listed "
        "class represent? Name the new class.",
        ("ontology_gap", "unrepresented_participant", "hidden_constraint", "unmeasured_clock")),
    Lab("B", "market_mechanism",
        "Participant incentives, forced flows, hedging, auctions, fixings, liquidity provision, "
        "positioning and institutional calendars. Who MUST trade, when, and why can they not wait?",
        ("forced_flow", "hedging_demand", "fixing_auction", "rebalancing_calendar",
         "liquidity_withdrawal", "positioning_unwind"),
        families=("forced_flow", "fx_fixing_reversal", "hedging_demand_close", "turn_of_month",
                  "cot_positioning")),
    Lab("C", "mathematical",
        "Probability, stochastic processes, information theory, optimisation, nonlinear systems "
        "and signal processing. Derive a trading rule from a mathematical structure, then say "
        "what economic process would generate that structure.",
        ("hawkes_clustering", "entropy_regime", "fractional_memory", "spectral_cycle",
         "jump_diffusion", "optimal_stopping"),
        families=("formula", "jump", "vol_transition", "regime_transition")),
    Lab("D", "cross_domain",
        "Transfer a mechanism from physics, control theory, network science, biology, operations "
        "research, epidemiology or game theory. State the analogy AND where it breaks.",
        ("critical_transition", "percolation_contagion", "control_feedback", "queueing_delay",
         "predator_prey_flow", "phase_locking"),
        families=("formula", "gnn_propagation", "correlation_regime")),
    Lab("E", "macro_cross_asset",
        "Rates, curves, FX differentials, commodities, indices and cross-market transmission. "
        "Find a path by which a macro state reaches an MT5 price with a measurable delay.",
        ("rate_differential", "curve_transmission", "commodity_currency_link",
         "risk_on_off_rotation", "real_rate_gold", "policy_divergence"),
        families=("macro_conditional", "world_macro_state", "lead_lag", "carry",
                  "cross_asset_residual")),
    Lab("F", "data_axis",
        "Invent an economically useful VARIABLE the desk does not measure yet. Name it, name a "
        "lawful public point-in-time source by NAME only, and the cell it would condition.",
        ("unmeasured_flow", "public_registry_state", "physical_activity_proxy",
         "official_calendar_state", "survey_state"),
        families=("exogenous_conditioner", "alt_conditioned", "alt_series_momentum")),
    Lab("G", "representation",
        "Invent a new TRANSFORMATION of information the desk already has (bars, spreads, "
        "sessions, cross-asset bars): a state, a residual, a rank, an acceleration, a "
        "multi-horizon disagreement. Express it in the formula grammar.",
        ("residual_state", "multi_horizon_disagreement", "acceleration_state",
         "cross_sectional_rank", "path_shape"),
        families=("formula", "pca_residual", "multi_speed_trend", "cross_sectional")),
    Lab("H", "program_synthesis",
        "Write executable strategy PROGRAMS in the formula grammar that an LLM would not write by "
        "habit: unusual operator compositions with a stated economic reading.",
        ("operator_composition", "conditional_program", "gated_signal"),
        families=("formula",)),
    Lab("I", "quality_diversity",
        "Fill EMPTY niches: a mechanism, horizon, session or asset class no other bet on the desk "
        "occupies. Prefer an orthogonal modest idea over another variant of a known winner.",
        ("empty_niche", "orthogonal_horizon", "unused_session", "unused_asset_class"),
        families=("session_handoff", "clock_transition", "opening_range", "spread_state")),
    Lab("J", "failure",
        "Turn graveyard failures into CONDITIONAL, INVERTED or RE-SCOPED descendants. Name the "
        "failure, the missing conditioning variable, and the descendant cell.",
        ("conditional_rescue", "inverted_failure", "regime_scoped_descendant"),
        feeds=("graveyard",), families=("regime_split", "exit_operated", "drawdown_conditional")),
    Lab("K", "sares_donor",
        "Independently reconstruct mechanism FRAGMENTS from extreme-return and championship "
        "archaeology (given below). Never copy a claim: rebuild the mechanism that could explain "
        "it and the cell that would falsify it.",
        ("donor_fragment", "championship_mechanism", "absurd_return_reconstruction"),
        feeds=("sares",)),
    Lab("L", "jev_semantic",
        "Write typed SEMANTIC QUESTIONS (probability / score / choice) an LLM judge could answer "
        "point-in-time about public text, and the cell that conditions on the answer's series.",
        ("semantic_state", "central_bank_tone", "event_relevance", "narrative_shift"),
        feeds=("jev",), families=("exogenous_conditioner", "event_reaction")),
    Lab("M", "disagreement",
        "Mine DISAGREEMENT: between assets that should agree, horizons, macro vs price, models, "
        "regimes. Disagreement resolving is the trade; name which side resolves and why.",
        ("cross_asset_disagreement", "horizon_disagreement", "macro_price_divergence"),
        feeds=("disagreement",), families=("relative_value", "triangle", "cross_asset_residual",
                                           "lead_lag")),
    Lab("N", "execution_microstructure",
        "Spread, session, quote, rollover, swap and broker-specific structure of a small MT5 "
        "account. What edge exists only because of how THIS venue executes?",
        ("spread_regime", "rollover_window", "session_liquidity_gap", "quote_staleness"),
        families=("spread_state", "execution_state", "liquidity_regime",
                  "liquidity_gamma_reversal")),
    Lab("O", "portfolio_edge",
        "Strategies valuable for ORTHOGONALITY to the live book even if modest alone: a hedge that "
        "pays in the book's bad states, a bet uncorrelated with every survivor named below.",
        ("book_hedge", "drawdown_state_payer", "uncorrelated_carry"),
        feeds=("survivors",), families=("crisis_only_class_defensive", "drawdown_conditional",
                                        "style_premia")),
    Lab("P", "red_team",
        "Destroy hypotheses: for each mechanism below give the strongest ALTERNATIVE explanation "
        "(leakage, selection, cost, regime, data-snooping) and the cheapest falsifier.",
        ("alternative_explanation",)),
)
#: ROLES (2026-10-13, "max edge discoveries"): run by `llm_lab_roles` inside the pass, not in the
#: independent rotation, so the sixteen inventors keep their budget. Registered here so their
#: proposals carry a lab name, a tally and verdict credit like every other lab's.
ROLE_LABS: tuple[Lab, ...] = (
    Lab("Q", "missed_move_archaeology",
        "Explain the largest recent moves no live sleeve traded, as rules testable on every past "
        "occurrence.", ("missed_move",)),
    Lab("R", "code_lab", "Write sandboxed feature code for rule-shaped conversion debt.",
        ("converted_rule",)),
    Lab("S", "source_scout", "Name non-English official public sources the desk lacks.", ()),
    Lab("T", "sleeve_red_team", "Argue why each live sleeve will fail; advisory only.", ()),
)
LAB_BY_KEY = {lab.key: lab for lab in (*LABS, *ROLE_LABS)}
#: Labs that run in the independent first pass. P attacks phase-1 output; it does not invent.
INVENTORS = tuple(lab for lab in LABS if lab.key != "P")

#: Coordinate axes besides lab and mechanism. Equities are hypothesis-lane only through the
#: cross-sectional families (universe_policy); the compiler's lane check enforces it per cell.
ASSET_CLASSES = ("forex", "forex exotics", "indices", "commodities", "energy", "soft commodity",
                 "bonds", "crypto", "equities")
HORIZONS = ("intraday", "swing", "position")

#: Cold-exploration and yield shares of each lab's coordinate choice; the rest is owed-first.
COLD_SHARE = 0.15
YIELD_SHARE = 0.20

BLOCKERS = ("NEEDS_DATA", "NEEDS_EXACT_RULE_EXTRACTION", "NEEDS_PIT_SOURCE",
            "NEEDS_EXECUTABLE_FAMILY", "NEEDS_PARAMETER_INFERENCE", "NEEDS_INSTRUMENT_MAPPING")
NOVELTY_CLASSES = ("EXACT_DUPLICATE", "PARAMETER_NEIGHBOUR", "MECHANISM_NEIGHBOUR",
                   "COMPOSITIONAL_DESCENDANT", "GENUINELY_NOVEL")
EMITTED_CLASSES = ("MECHANISM_NEIGHBOUR", "COMPOSITIONAL_DESCENDANT", "GENUINELY_NOVEL")
COVERAGE_STATES = ("UNSEEN", "DISCOVERED", "PARTIAL", "QUEUED", "TESTED", "DUPLICATE",
                   "UNMEASURED", "INVALID", "BLOCKED", "GRAVEYARDED", "CERTIFIED", "FORWARD")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _h(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:                                   # WinError 5 onto a read-only destination
        with contextlib.suppress(OSError):
            path.chmod(0o666)
        path.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
        tmp.unlink(missing_ok=True)


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    return len(rows)


def _jsonl(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    if limit:
        lines = lines[-limit:]
    out = []
    for ln in lines:
        with contextlib.suppress(ValueError):
            row = json.loads(ln)
            if isinstance(row, dict):
                out.append(row)
    return out


_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
_STOP = frozenset({
    "the", "and", "for", "with", "when", "that", "this", "from", "into", "than", "then", "are",
    "was", "were", "will", "can", "its", "their", "they", "our", "not", "but", "over", "under",
    "each", "per", "via", "any", "all", "one", "two", "has", "have", "trade", "trades",
    "trading", "price", "prices", "market", "markets", "signal", "long", "short",
})


def tokens(text: str) -> frozenset[str]:
    return frozenset(w for w in _WORD.findall(str(text).lower()) if w not in _STOP)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    return s[:limit]


# ============================================================================ the family menu
@dataclass(frozen=True)
class FamilySpec:
    name: str
    params: dict[str, Any]                 #: keyword parameters and their defaults
    doc: str
    inputs: str


_SKIP_PARAMS = frozenset({"df", "cot", "macro", "driver", "drivers", "events", "series_root",
                          "peer", "peers", "population", "bars", "frames"})


def family_registry() -> dict[str, FamilySpec]:
    """Every registered, NON-BANNED executable family with its keyword parameters. Never raises.

    Read from the families modules themselves, so a family landed tomorrow appears in the next
    pass's menu and resolves any debt that was waiting for it.
    """
    out: dict[str, FamilySpec] = {}
    try:
        from mt5desk import families, families_orthogonal
    except Exception:                                  # pragma: no cover - box without pandas
        return out
    try:
        from family_policy import family_banned
    except ImportError:                                # pragma: no cover
        try:
            from research.family_policy import family_banned
        except ImportError:
            def family_banned(_f: object) -> bool:     # type: ignore[misc]
                return False
    inputs = getattr(families_orthogonal, "FAMILY_INPUTS", {}) or {}
    fns: dict[str, Any] = {n[len("family_"):]: getattr(families, n) for n in dir(families)
                           if n.startswith("family_") and callable(getattr(families, n))}
    fns.update(getattr(families_orthogonal, "ORTHOGONAL_FAMILIES", {}) or {})
    for name, fn in sorted(fns.items()):
        if family_banned(name):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        params = {k: (None if v.default is inspect.Parameter.empty else v.default)
                  for k, v in sig.parameters.items()
                  if k not in _SKIP_PARAMS and v.kind in (v.KEYWORD_ONLY, v.POSITIONAL_OR_KEYWORD)
                  and v.default is not inspect.Parameter.empty}
        inp = inputs.get(name)
        out[name] = FamilySpec(name, params, (inspect.getdoc(fn) or "").split("\n")[0][:140],
                               str(inp[0]) if isinstance(inp, (tuple, list)) and inp else "bars")
    return out


def registry_fingerprint(reg: dict[str, FamilySpec]) -> str:
    return _h(*sorted(f"{k}:{sorted(v.params)}" for k, v in reg.items()))


def menu_lines(reg: dict[str, FamilySpec], lab: Lab, rng: random.Random, k: int = 14) -> list[str]:
    """The families this lab sees: its own first, `formula` always, then a rotating sample."""
    first = [f for f in (*lab.families, "formula") if f in reg]
    rest = [f for f in sorted(reg) if f not in first]
    rng.shuffle(rest)
    chosen = list(dict.fromkeys(first + rest))[:max(k, len(first))]
    lines = []
    for f in chosen:
        spec = reg[f]
        shown = list(spec.params.items())[:9]
        ps = ", ".join(f"{p}={json.dumps(d, default=str)}" for p, d in shown)
        lines.append(f"{f}({ps}) -- needs {spec.inputs[:60]}")
    return lines


def all_family_names(reg: dict[str, FamilySpec]) -> str:
    return ", ".join(sorted(reg))


FORMULA_GRAMMAR = ("formula expr: prefix calls over terminals close, open, high, low, ret, range, "
                   "body, activity, spread, usd, rates, risk, gold, oil, growth; unary neg/abs/"
                   "sign; windowed (x, w) delay, delta, mean, std, min, max, ts_rank, zscore, "
                   "decay, sum; binary add, sub, mul, div, max2, min2, trade_when; (x, y, w) corr, "
                   "residual, cov; windows 2,3,5,8,12,24,48,120,240; depth <= 5; units must agree. "
                   "e.g. zscore(sub(ret, mean(ret, 24)), 120)")


# ============================================================================ the universe
def universe() -> dict[str, str]:
    """{symbol: asset class} from the registry, in the registry's own spelling."""
    doc = _read_json(UNIVERSE, {}) or {}
    names = list(doc) if isinstance(doc, dict) else []
    try:
        import universe_policy as up
        return {s: up.asset_class_of(s) for s in names}
    except Exception:                                  # pragma: no cover
        return dict.fromkeys(names, "unclassified")


def _lane_ok(symbol: str, family: str) -> bool:
    try:
        import universe_policy as up
        return bool(up.may_hypothesise(symbol, family))
    except Exception:                                  # pragma: no cover
        return True


# ============================================================================ banal filter
_BANAL = (
    ("rsi", re.compile(r"\brsi\b|relative strength index")),
    ("ma_cross", re.compile(r"moving[- ]average cross|\bma cross|\bema cross|\bsma cross|"
                            r"golden cross|death cross")),
    ("macd", re.compile(r"\bmacd\b")),
    ("bollinger", re.compile(r"bollinger")),
    ("stochastic", re.compile(r"stochastic oscillator|\bstoch\b")),
    ("generic_breakout", re.compile(r"\bbreak(?:s|out)? (?:above|below) (?:the )?(?:\d+|n)[- ]"
                                    r"(?:day|bar|period) (?:high|low)")),
)
#: Words that carry a genuinely non-price element; a simple rule carrying one is NOT banal.
_NOVEL_ELEMENT = re.compile(
    r"participant|forced|hedg|fixing|auction|rebalanc|positioning|cot\b|carry|swap|rate|curve|"
    r"macro|inflation|central bank|policy|event|calendar|session|asia|london|new york|rollover|"
    r"spread|liquidity|regime|volatility state|cross-asset|lead|lag|residual|disagree|semantic|"
    r"flow|inventory|settlement|expiry|option|gamma|seasonal|month|holiday")


def banal(payload: dict[str, Any]) -> str:
    """The baseline this proposal is, or "" when it is not banal.

    Simplicity is NOT banality (principal, 2026-10-12): a three-rule strategy built on a new
    mechanism, source, regime dependency or execution effect is research. Banal is a generic
    indicator recipe with nothing but price in it.
    """
    text = " ".join(str(payload.get(k) or "") for k in ("mechanism", "mechanism_class",
                                                        "family", "expr")).lower()
    hit = next((name for name, rx in _BANAL if rx.search(text)), "")
    if not hit:
        return ""
    return "" if _NOVEL_ELEMENT.search(text) else hit


# ============================================================================ compile
@dataclass
class Compiled:
    cells: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    detail: list[str] = field(default_factory=list)
    refused: str = ""
    jev_question: dict[str, Any] | None = None
    data_needed: list[str] = field(default_factory=list)


def _coerce(value: Any, default: Any) -> Any:
    if default is None or value is None:
        return value
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "yes"):
            return True
        if str(value).lower() in ("false", "0", "no"):
            return False
        raise ValueError(f"not a bool: {value!r}")
    if isinstance(default, int):
        f = float(value)
        if not math.isfinite(f):
            raise ValueError("non-finite")
        return round(f)
    if isinstance(default, float):
        f = float(value)
        if not math.isfinite(f):
            raise ValueError("non-finite")
        return f
    if isinstance(default, str):
        return str(value)
    return value


def _resolve_symbols(raw: Any, uni: dict[str, str]) -> tuple[list[str], list[str]]:
    want = raw if isinstance(raw, list) else [raw] if raw else []
    fold = {s.lower(): s for s in uni}
    got, missing = [], []
    for w in want[:8]:
        s = fold.get(str(w).strip().lower().replace("/", ""))
        (got if s else missing).append(s or str(w))
    return list(dict.fromkeys(got)), missing


def _series_present(source: str) -> bool:
    try:
        from mt5desk.family_exogenous_conditioner import series_path
        return series_path(source) is not None
    except Exception:                                  # pragma: no cover
        return False


def _expr_ok(expr: str) -> tuple[str, str]:
    """(canonical expression, "") or ("", why). The formula family's own production screen."""
    try:
        from libs.research.alpha_grammar import from_str, is_valid, to_str
    except Exception:                                  # pragma: no cover
        return "", "alpha_grammar unimportable"
    try:
        e = from_str(expr)
    except ValueError as exc:
        return "", f"expr does not parse: {str(exc)[:80]}"
    if not is_valid(e):
        return "", "expr fails the grammar's type/unit screen"
    return to_str(e), ""


def jev_series_name(question: str) -> str:
    return f"jev_{_h(question.strip().lower())[:12]}"


def compile_payload(payload: dict[str, Any], reg: dict[str, FamilySpec],
                    uni: dict[str, str]) -> Compiled:
    """Turn one accepted proposal into exact cells, or name every blocker. Invents nothing."""
    out = Compiled()
    fam = str(payload.get("family") or "").strip()
    expr = str(payload.get("expr") or "").strip()
    syms, missing = _resolve_symbols(payload.get("symbols"), uni)
    if missing and not syms:
        out.blockers.append("NEEDS_INSTRUMENT_MAPPING")
        out.detail.append(f"no MT5 symbol for {missing[:4]}")
    if not syms and not missing:
        out.blockers.append("NEEDS_INSTRUMENT_MAPPING")
        out.detail.append("no instrument named")

    jq = payload.get("jev_question")
    if isinstance(jq, dict) and str(jq.get("question") or "").strip():
        q = str(jq["question"]).strip()[:300]
        out.jev_question = {"question": q, "answer_type": str(jq.get("answer_type") or
                                                              "probability")[:20],
                            "entities": [str(x)[:40] for x in (jq.get("entities") or [])][:8],
                            "horizon": str(payload.get("horizon") or "")[:20],
                            "series": jev_series_name(q)}
        if not fam:
            fam = "exogenous_conditioner"
            params_in = dict(payload.get("params") or {})
            params_in.setdefault("source", out.jev_question["series"])
            params_in.setdefault("signal", "p")
            payload = {**payload, "family": fam, "params": params_in}

    if not fam or fam.upper() in ("NONE", "NEW", "UNIMPLEMENTED"):
        if expr:
            fam = "formula"
        else:
            out.blockers.append("NEEDS_EXECUTABLE_FAMILY")
            out.detail.append("no registered family expresses this mechanism yet")
            return out
    try:
        from family_policy import family_banned
    except ImportError:                                # pragma: no cover
        def family_banned(_f: object) -> bool:          # type: ignore[misc]
            return False
    if family_banned(fam):
        out.refused = f"BANNED_FAMILY:{fam}"
        return out
    spec = reg.get(fam)
    if spec is None:
        out.blockers.append("NEEDS_EXECUTABLE_FAMILY")
        out.detail.append(f"family {fam!r} is not registered")
        return out

    raw = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    params: dict[str, Any] = {}
    dropped = []
    for k, v in raw.items():
        if k not in spec.params:
            dropped.append(k)
            continue
        try:
            params[k] = _coerce(v, spec.params[k])
        except (TypeError, ValueError):
            out.blockers.append("NEEDS_PARAMETER_INFERENCE")
            out.detail.append(f"{fam}.{k}={str(v)[:30]!r} is not a {type(spec.params[k]).__name__}")
    if dropped:
        out.detail.append(f"ignored keys outside {fam}'s signature: {dropped[:6]}")
    if fam == "formula":
        canon, why = _expr_ok(expr or str(params.get("expr") or ""))
        if not canon:
            out.blockers.append("NEEDS_EXACT_RULE_EXTRACTION")
            out.detail.append(why)
        else:
            params["expr"] = canon
    for key in ("base_family",):
        if key in spec.params and params.get(key) and params[key] not in reg:
            out.blockers.append("NEEDS_EXECUTABLE_FAMILY")
            out.detail.append(f"base_family {params[key]!r} is not registered")
    if "source" in spec.params and fam in ("exogenous_conditioner", "alt_conditioned",
                                           "alt_series_momentum"):
        src = str(params.get("source") or "")
        if not src:
            out.blockers.append("NEEDS_PIT_SOURCE")
            out.detail.append(f"{fam} names no source series")
        elif not _series_present(src):
            out.blockers.append("NEEDS_DATA")
            out.data_needed.append(src)
            out.detail.append(f"series {src!r} is not in the lake on this host")
    tf = str(payload.get("timeframe") or "").upper()
    if tf in ("M5", "M15", "M30", "H1", "H4", "D1"):
        params.setdefault("timeframe", tf)
    if out.blockers:
        out.blockers = list(dict.fromkeys(out.blockers))
        return out
    refused_lane = []
    for s in syms:
        if not _lane_ok(s, fam):
            refused_lane.append(s)
            continue
        out.cells.append({"symbol": s, "family": fam, "params": dict(params)})
    if refused_lane and not out.cells:
        out.refused = f"LANE_REFUSED:{fam}:{refused_lane[:4]}"
    return out


def cell_identity(cell: dict[str, Any]) -> str:
    try:
        from frontier_identity import cell_id
        return cell_id({"sym": cell["symbol"], "family": cell["family"],
                        "params": cell.get("params") or {}})
    except Exception:                                  # pragma: no cover
        digest = _h(json.dumps(cell.get("params"), sort_keys=True, default=str))
        return f"{cell['symbol']}.{cell['family']}.p={digest}"


# ============================================================================ novelty
@dataclass
class Memory:
    """What the lab and the desk have already investigated. Read once per pass."""

    ids: set[str] = field(default_factory=set)
    by_cell: dict[tuple[str, str, str], list[dict[str, Any]]] = field(default_factory=dict)
    mechanisms: list[tuple[frozenset[str], str, str, str]] = field(default_factory=list)
    nodes: set[str] = field(default_factory=set)
    library: Any = None

    @classmethod
    def load(cls, *, library: bool = True) -> Memory:
        m = cls()
        for row in _jsonl(GENEALOGY):
            m.remember(row)
        if library:
            try:
                import novelty_gate as ng
                m.library = ng.Library.load()
                for mem in m.library.members:
                    if mem.ident:
                        m.ids.add(mem.ident)
                    key = (mem.symbol.upper(), mem.family.lower(), mem.timeframe.upper())
                    m.by_cell.setdefault(key, []).append({"params": mem.params,
                                                          "id": mem.ident or mem.key})
            except Exception:                          # pragma: no cover - empty library
                m.library = None
        return m

    def remember(self, row: dict[str, Any]) -> None:
        node = str(row.get("node") or "")
        if node:
            self.nodes.add(node)
        cid = str(row.get("cell_id") or "")
        if cid:
            self.ids.add(cid)
        cell = row.get("cell") if isinstance(row.get("cell"), dict) else None
        if cell:
            params = cell.get("params") or {}
            key = (str(cell.get("symbol") or "").upper(), str(cell.get("family") or "").lower(),
                   str(params.get("timeframe") or "H1").upper())
            self.by_cell.setdefault(key, []).append({"params": params, "id": cid or node})
        mech = str(row.get("mechanism") or "")
        if mech:
            self.mechanisms.append((tokens(mech), node, str(row.get("lab") or ""),
                                    str((cell or {}).get("family") or "")))


def _param_twin(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if set(a) != set(b):
        return False
    for k, va in a.items():
        vb = b[k]
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) \
                and not isinstance(va, bool):
            scale = max(abs(float(va)), abs(float(vb)), 1e-9)
            if abs(float(va) - float(vb)) / scale > 0.10:
                return False
        elif va != vb:
            return False
    return True


#: Families that wrap another family: a cell of one with a known base is a composition.
WRAPPERS = frozenset({"regime_split", "exit_operated", "ensemble", "exogenous_conditioner"})
MECH_NEIGHBOUR_J = 0.5


def classify(cell: dict[str, Any], mechanism: str, parents: Sequence[str],
             mem: Memory) -> tuple[str, str]:
    """(novelty class, the twin/parent/neighbour it was measured against)."""
    cid = cell_identity(cell)
    if cid in mem.ids:
        return "EXACT_DUPLICATE", cid
    params = cell.get("params") or {}
    key = (cell["symbol"].upper(), cell["family"].lower(),
           str(params.get("timeframe") or "H1").upper())
    for prior in mem.by_cell.get(key, []):
        if _param_twin(params, prior.get("params") or {}):
            return "PARAMETER_NEIGHBOUR", str(prior.get("id") or "")
    known_parents = [p for p in parents if p in mem.nodes]
    if known_parents:
        return "COMPOSITIONAL_DESCENDANT", known_parents[0]
    base = str(params.get("base_family") or "")
    if cell["family"] in WRAPPERS and base and any(k[1] == base for k in mem.by_cell):
        return "COMPOSITIONAL_DESCENDANT", base
    toks = tokens(mechanism)
    best, near = 0.0, ""
    for mt, node, _lab, _fam in mem.mechanisms:
        j = jaccard(toks, mt)
        if j > best:
            best, near = j, node
    if best >= MECH_NEIGHBOUR_J:
        return "MECHANISM_NEIGHBOUR", near
    return "GENUINELY_NOVEL", near


# ============================================================================ coverage
def coord_id(c: dict[str, str]) -> str:
    return _h("coord", c.get("lab"), c.get("mechanism_class"), c.get("asset_class"),
              c.get("horizon"))


@dataclass
class Coverage:
    doc: dict[str, Any]

    @classmethod
    def load(cls) -> Coverage:
        d = _read_json(COVERAGE, {}) or {}
        d.setdefault("coords", {})
        d.setdefault("cursor", {})
        return cls(d)

    def state(self, cid: str) -> str:
        return str((self.doc["coords"].get(cid) or {}).get("state") or "UNSEEN")

    def touch(self, cid: str, coord: dict[str, str], state: str, *, cells: Sequence[str] = (),
              novel: int = 0) -> None:
        row = self.doc["coords"].setdefault(cid, {**coord, "state": "UNSEEN", "visits": 0,
                                                  "cells": [], "novel": 0})
        row["visits"] = int(row.get("visits", 0)) + (state != "QUEUED")
        row["novel"] = int(row.get("novel", 0)) + int(novel)
        rank = {s: i for i, s in enumerate(("UNSEEN", "QUEUED", "INVALID", "BLOCKED",
                                            "DUPLICATE", "PARTIAL", "DISCOVERED", "TESTED",
                                            "GRAVEYARDED", "CERTIFIED", "FORWARD"))}
        if rank.get(state, 0) >= rank.get(str(row.get("state")), 0) or row["state"] == "QUEUED":
            row["state"] = state
        row["cells"] = list(dict.fromkeys([*row.get("cells", []), *cells]))[-200:]
        row["last"] = _now()


def coordinates(ontology: Sequence[str], lab: Lab) -> list[dict[str, str]]:
    """This lab's slice of the tensor in STABLE order: its seeds first, then the whole ontology."""
    mechs = list(dict.fromkeys([*lab.seeds, *sorted(ontology)]))
    return [{"lab": lab.key, "mechanism_class": m, "asset_class": a, "horizon": hz}
            for m in mechs for a in ASSET_CLASSES for hz in HORIZONS]


def choose_coordinate(lab: Lab, ontology: Sequence[str], cov: Coverage,
                      rng: random.Random) -> tuple[dict[str, str], str]:
    """(coordinate, why). Owed-first by cursor; a cold random share; a yield share."""
    coords = coordinates(ontology, lab)
    draw = rng.random()
    if draw < COLD_SHARE:
        return rng.choice(coords), "cold_exploration"
    if draw < COLD_SHARE + YIELD_SHARE:
        scored = [(int((cov.doc["coords"].get(coord_id(c)) or {}).get("novel", 0)), i)
                  for i, c in enumerate(coords)]
        best = max(scored, default=(0, 0))
        if best[0] > 0:
            return coords[best[1]], "yield_return"
    start = int(cov.doc["cursor"].get(lab.key, 0))
    for step in range(len(coords)):
        i = (start + step) % len(coords)
        c = coords[i]
        if cov.state(coord_id(c)) in ("UNSEEN", "QUEUED"):
            cov.doc["cursor"][lab.key] = i + 1
            return c, "owed"
    cov.doc["cursor"][lab.key] = start + 1
    return coords[start % len(coords)], "revisit"


def owed(cov: Coverage, ontology: Sequence[str]) -> dict[str, int]:
    total = seen = 0
    for lab in INVENTORS:
        for c in coordinates(ontology, lab):
            total += 1
            seen += cov.state(coord_id(c)) not in ("UNSEEN", "QUEUED")
    return {"coordinates": total, "visited": seen, "owed": total - seen}


# ============================================================================ models
LICENSE_OK = re.compile(r"apache|\bmit\b|bsd|llama \d|llama[- ]?\d community|gemma terms|qwen|"
                        r"deepseek license|openrail|mistral ai research|cc-by|creativeml", re.I)


def _local_license(base_url: str, model: str) -> str:
    """Ollama's own /api/show license text, or "" when the server cannot say."""
    root = base_url.rsplit("/v1", 1)[0]
    try:
        import urllib.request
        req = urllib.request.Request(f"{root}/api/show", data=json.dumps({"model": model}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            doc = json.loads(r.read() or b"{}")
        return str(doc.get("license") or "")[:4000]
    except Exception:
        return ""


def hunt_models(registry: dict[str, Any], *, budget_s: float = 30.0) -> list[str]:
    """Register every free model the chain can list. discover -> license review -> register.

    Local models are used only once their license text matches the allowlist; an unreadable or
    unmatched license is REVIEW_PENDING and never assigned. Cloud models are governed by their
    provider's own terms of the free tier and register directly.
    """
    try:
        from libs.ops import free_chain
    except Exception:                                  # pragma: no cover
        return []
    found: list[str] = []
    started = time.time()
    for p in free_chain.providers():
        if time.time() - started > budget_s:
            break
        models, err = free_chain.list_models(p, timeout=6.0)
        if err:
            continue
        # EVERY free model, not the first forty (principal 2026-10-13: "all openrouter models
        # must be running"). Embedders, guards and speech models cannot answer a lab and are
        # skipped by the chain's own capability filter.
        listed = {f"{p.name}:{m}" for m in models}
        for key, row in registry.items():
            if row.get("provider") == p.name and key not in listed and \
                    row.get("status") == "REGISTERED" and p.tier != "local":
                row["status"] = "DELISTED"          # gone from the provider's free catalogue
                row["delisted_at"] = _now()
        for m in free_chain._cheapest_capable(models):
            key = f"{p.name}:{m}"
            row = registry.setdefault(key, {"provider": p.name, "model": m, "tier": p.tier,
                                            "first_seen": _now(), "status": "DISCOVERED",
                                            "asked": 0, "replies": 0, "accepted": 0, "exact": 0,
                                            "novel": 0})
            if row["status"] == "DELISTED":
                row["status"] = "REGISTERED"        # back in the free catalogue
                row["relisted_at"] = _now()
            if row["status"] == "DISCOVERED":
                if p.tier == "local":
                    lic = _local_license(p.url(), m)
                    row["license"] = (lic[:120] if lic else UNMEASURED)
                    row["status"] = "REGISTERED" if lic and LICENSE_OK.search(lic) \
                        else "REVIEW_PENDING"
                else:
                    row["status"] = "REGISTERED"
                found.append(key)
            row["last_listed"] = _now()
    return found


def observe_model(registry: dict[str, Any], key: str) -> None:
    """A model that answered gets a row for attribution even if the hunter never listed it.

    Only a "<free_chain provider>:<model>" key is ASSIGNABLE (status REGISTERED), because that is
    the only shape `free_chain.chat(model_hint=...)` can route; a free-panel or seat model is
    OBSERVED -- measured, credited, but reached through its own rotation rather than pinned.
    """
    if key in registry:
        return
    provider, _, model = key.partition(":")
    try:
        from libs.ops import free_chain
        names = {p.name for p in free_chain.providers()}
    except Exception:                                  # pragma: no cover
        names = set()
    registry[key] = {"provider": provider if provider in names else "route",
                     "model": model if provider in names else key,
                     "status": "REGISTERED" if provider in names and model else "OBSERVED",
                     "first_seen": _now(), "asked": 0, "replies": 0, "accepted": 0, "exact": 0,
                     "novel": 0}


def assign_model(registry: dict[str, Any], rng: random.Random, used: set[str],
                 credit: dict[str, Any] | None = None) -> str:
    """Thompson draw over REGISTERED models on CERTIFIED INCREMENTAL k_eff PER CALL (the verdict
    loop's `verdict_credit.json`). "" = default route. Novel-cell counts no longer rank a model:
    a model that floods the docket with novel cells the gauntlet kills ranks below one whose
    fewer cells certify as new independent bets.

    `used` keeps the first pass independent: two labs are not given the same model while another
    registered model is free, because ten agents repeating one model's habit is not ten labs.
    """
    pool = [(k, r) for k, r in registry.items() if r.get("status") == "REGISTERED"]
    if not pool:
        return ""
    fresh = [k for k, _ in pool if k not in used] or [k for k, _ in pool]
    import llm_lab_roles as roles
    rows = (credit if credit is not None else
            (_read_json(roles.CREDIT, {}) or {})).get("models") or {}
    return roles.thompson(rows, sorted(fresh), rng)[0]


# ============================================================================ feeds
def feed_lines(lab: Lab, extra: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for f in lab.feeds:
        if f == "graveyard":
            import llm_lab_roles as roles
            dead = [r for r in _jsonl(VERDICTS, limit=4000) if r.get("passed") is False
                    and not roles.held_out(str(r.get("terminal_gate") or r.get("gate") or ""),
                                           str(r.get("reason") or r.get("why") or ""))]
            for r in dead[-8:]:
                out.append(f"graveyard: {str(r.get('cell'))[:70]} family={r.get('family')} "
                           f"died at gate {r.get('gate')}")
            if not dead:
                out.append("graveyard: UNMEASURED on this host (no verdict ledger)")
        elif f == "sares":
            files = sorted(SARES_DIR.glob("discoveries_*.json"))[-2:]
            rows: list[dict[str, Any]] = []
            for p in files:
                doc = _read_json(p, {}) or {}
                rows += [r for r in doc.get("discoveries") or [] if isinstance(r, dict)]
            for r in rows[-8:]:
                frag = r.get("mechanism") or r.get("testable_claim") or r.get("title")
                out.append(f"donor fragment: {str(frag)[:150]}")
            if not rows:
                out.append("donor fragments: UNMEASURED on this host (no SARES donations)")
        elif f == "survivors":
            try:
                import novelty_gate as ng
                lib = ng.Library.load()
                fams = Counter(m.family for m in lib.members if m.origin in ("survivor", "sleeve"))
                out.append("book holds: " + ", ".join(f"{f}x{n}" for f, n in fams.most_common(12))
                           if fams else "book: UNMEASURED on this host")
            except Exception:                          # pragma: no cover
                out.append("book: UNMEASURED")
            try:
                import lab_style
                out.append(lab_style.prompt_line())
            except Exception:                          # pragma: no cover
                out.append("styles the book owns: UNMEASURED")
        else:
            out.extend(extra.get(f, [])[:8])
    return out


# ============================================================================ the pass
GRAMMAR = (
    '{"mechanism_class": "<snake_case class, NEW names welcome>", '
    '"mechanism": "<causal story: who is forced or informed, what they do, why price must move, '
    '<=300 chars>", "falsifier": "<the observation that would kill it, <=200 chars>", '
    '"symbols": ["<MT5 symbol>"], "timeframe": "M15|H1|H4|D1", '
    '"horizon": "intraday|swing|position", "family": "<one registered family, or NONE>", '
    '"params": {"<that family\'s keyword>": <value>}, "expr": "<formula expression or empty>", '
    '"needs": ["<missing data or rule, by name>"], "parents": ["<node id it descends from>"], '
    '"jev_question": {"question": "...", "answer_type": "probability|score|choice", '
    '"entities": ["..."]}  (Lab L only, optional)}'
)

TASK_RULES = (
    "Invent mechanisms, not parameters. Never propose a generic RSI/MACD/Bollinger/moving-average "
    "crossover/plain breakout recipe as research. Simple is fine when the mechanism, the "
    "information or the regime dependence is new. Use ONLY a family from the menu with ONLY its "
    "keywords, or family NONE with the missing rule named in needs. Never invent data: if the "
    "mechanism needs a series the desk lacks, name it in needs. One JSON object per line."
)


@dataclass
class Ask:
    lab: Lab
    coord: dict[str, str]
    why: str
    model: str
    context: list[str]
    task: str


def _symbols_for(asset: str, uni: dict[str, str], rng: random.Random, k: int = 12) -> list[str]:
    syms = sorted(s for s, c in uni.items() if c == asset)
    rng.shuffle(syms)
    return syms[:k]


def build_ask(lab: Lab, coord: dict[str, str], why: str, model: str, reg: dict[str, FamilySpec],
              uni: dict[str, str], rng: random.Random, own_recent: Sequence[str],
              extra: dict[str, list[str]]) -> Ask:
    ctx = [f"lab {lab.key} ({lab.name}): {lab.mandate[:220]}",
           f"coordinate: mechanism_class={coord['mechanism_class']} asset_class="
           f"{coord['asset_class']} horizon={coord['horizon']}",
           "symbols in that class: " + ", ".join(_symbols_for(coord["asset_class"], uni, rng)),
           "all registered families: " + all_family_names(reg)[:900],
           FORMULA_GRAMMAR]
    ctx += [f"menu: {ln}" for ln in menu_lines(reg, lab, rng)]
    ctx += feed_lines(lab, extra)
    ctx += [f"gauntlet {ln}" for ln in (extra.get(f"verdicts:{lab.key}") or [])[:6]]
    ctx += [f"already proposed by this lab here (do NOT repeat): {m[:120]}" for m in own_recent[:5]]
    task = (f"{lab.mandate} Propose genuinely new mechanisms for the coordinate given. "
            f"{TASK_RULES}")
    return Ask(lab, coord, why, model, ctx[:40], task)


def _validate(payload: Any) -> str | None:
    """Shape only. The compiler, the novelty classes and the gauntlet decide everything else."""
    if not isinstance(payload, dict):
        return "not a JSON object"
    if len(str(payload.get("mechanism") or "").strip()) < 24:
        return "no causal mechanism (need >=24 chars)"
    if len(str(payload.get("falsifier") or "").strip()) < 10:
        return "no falsifier"
    if not payload.get("symbols") and not payload.get("needs"):
        return "names neither an instrument nor what is missing"
    return None


def _validate_attack(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "not a JSON object"
    if not payload.get("target") or len(str(payload.get("alternative") or "")) < 16:
        return "an attack needs a target node and an alternative explanation"
    return None


def _seat() -> Any:
    """The proposer seat, or None. Guarded: a box without it plans the pass and calls nothing."""
    try:
        from libs.research import proposer_seat
    except Exception:                                  # pragma: no cover - defensive
        return None
    return proposer_seat


def _call(ask: Ask, n: int, timeout: float) -> list[Any]:
    ps = _seat()
    if ps is None:
        return []
    return ps._asked(ORGAN, role="generation", task=ask.task, grammar=GRAMMAR,
                     context=ask.context, n=n, label="candidate", validate=_validate,
                     timeout=timeout, model_hint=ask.model)


@dataclass
class Tally:
    asked: int = 0
    replies: int = 0
    proposals: int = 0
    accepted: int = 0
    discarded: int = 0
    banal: int = 0
    refused: int = 0
    debt: int = 0
    emitted: int = 0
    novelty: Counter = field(default_factory=Counter)
    blockers: Counter = field(default_factory=Counter)
    reasons: Counter = field(default_factory=Counter)

    def row(self) -> dict[str, Any]:
        return {"asked": self.asked, "replies": self.replies, "proposals": self.proposals,
                "accepted": self.accepted, "discarded": self.discarded, "banal": self.banal,
                "refused": self.refused, "debt": self.debt, "emitted": self.emitted,
                "novelty": dict(self.novelty), "blockers": dict(self.blockers),
                "discard_reasons": dict(self.reasons.most_common(6))}


#: THE HIGH-YIELD ROLES GO FIRST (2026-10-13): turning what the desk already holds into testable
#: cells beats inventing more of it. Conversion of owed debt runs BEFORE any inventor (phase 0);
#: then donor reconstruction (K), semantic/policy text into PIT cells (L), graveyard descendants
#: (J) and new data axes (F); raw idea generation takes whatever budget is left, in random order
#: so no inventor is permanently last.
PRIORITY_LABS = ("K", "L", "J", "F")


def prioritised(rng: random.Random, credit: dict[str, Any] | None = None) -> list[Lab]:
    """Priority labs first; the rest by a Thompson draw on their certified k_eff per call, so a
    lab that has earned independent bets is reached first when the call cap binds and an unproven
    lab is still explored from the flat prior."""
    first = [LAB_BY_KEY[k] for k in PRIORITY_LABS]
    rest = [lab.key for lab in INVENTORS if lab.key not in PRIORITY_LABS]
    import llm_lab_roles as roles
    rows = (credit if credit is not None else
            (_read_json(roles.CREDIT, {}) or {})).get("labs") or {}
    return first + [LAB_BY_KEY[k] for k in roles.thompson(rows, sorted(rest), rng)]


def openrouter_pass_share(now: datetime | None = None) -> dict[str, Any]:
    """This pass's share of OpenRouter's MEASURED daily allowance, spread over the hours left.

    The account's limit is read from its /key endpoint (50 a day without credit, 1,000 with).
    The lab takes QUANT_LLM_LAB_OR_SHARE of it (default half: the deepening worker and the
    seats draw on the same allowance) and divides what is left today by the UTC hours left, so
    the day's requests land evenly across every hourly pass rather than in the first ones.
    `{}` while the limit is UNMEASURED: the pass then runs on the older call caps.
    """
    from libs.ops import openrouter_guard
    lim = openrouter_guard.daily_limit(cached_only=True)
    if not lim:
        return {}
    try:
        share = min(1.0, max(0.0, float(os.environ.get("QUANT_LLM_LAB_OR_SHARE", "0.5"))))
    except ValueError:
        share = 0.5
    t = now or datetime.now(UTC)
    lab_day = int(lim * share)
    used = int((_read_json(CALLS, {}) or {}).get(t.strftime("%Y-%m-%d"), 0))
    hours_left = max(1, 24 - t.hour)
    per_pass = max(0, lab_day - used) // hours_left
    return {"account_daily_limit": lim, "lab_share": share, "lab_daily": lab_day,
            "lab_used_today": used, "hours_left": hours_left, "per_pass": per_pass}


def _calls_left(daily_cap: int) -> int:
    doc = _read_json(CALLS, {}) or {}
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return max(0, daily_cap - int(doc.get(day, 0)))


def _count_calls(n: int) -> None:
    doc = _read_json(CALLS, {}) or {}
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    doc = {day: int(doc.get(day, 0)) + n}
    _write_json(CALLS, doc)


def _ontology() -> list[str]:
    doc = _read_json(ONTOLOGY, {}) or {}
    base = {m for lab in LABS for m in lab.seeds}
    return sorted(base | set(doc.get("classes") or []))


def _save_ontology(classes: Iterable[str], born: dict[str, str]) -> None:
    doc = _read_json(ONTOLOGY, {}) or {}
    doc["classes"] = sorted(set(doc.get("classes") or []) | set(classes))
    doc.setdefault("born", {}).update(born)
    _write_json(ONTOLOGY, doc)


def process(prop: Any, lab_key: str, coord: dict[str, str], reg: dict[str, FamilySpec],
            uni: dict[str, str], mem: Memory, tally: Tally, models: dict[str, Any],
            outputs: dict[str, list[dict[str, Any]]]) -> None:
    """One proposal to exactly one disposition, recorded in the genealogy."""
    model = str(getattr(prop.provenance, "model", "") or "")
    mrow = models.get(model)
    tally.proposals += 1
    if not prop.accepted:
        tally.discarded += 1
        tally.reasons[str(prop.reason)[:80]] += 1
        return
    tally.accepted += 1
    if mrow is not None:
        mrow["accepted"] = int(mrow.get("accepted", 0)) + 1
    payload = dict(prop.payload)
    mech = str(payload.get("mechanism") or "")[:400]
    mclass = slug(payload.get("mechanism_class") or coord["mechanism_class"]) or "unnamed"
    pkey = json.dumps(payload.get("params"), sort_keys=True, default=str)
    node = f"LLMLAB-{_h(lab_key, mech, pkey)}"
    base_row = {"node": node, "lab": lab_key, "at": _now(), "model": model,
                "prompt_hash": getattr(prop.provenance, "prompt_hash", ""),
                "coordinate": coord, "mechanism_class": mclass, "mechanism": mech,
                "falsifier": str(payload.get("falsifier") or "")[:300],
                "parents": [str(p) for p in payload.get("parents") or []][:6],
                "stripped": list(getattr(prop, "stripped", ()) or ())}
    outputs["classes"].append({"class": mclass, "lab": lab_key})
    b = banal(payload)
    if b:
        tally.banal += 1
        outputs["genealogy"].append({**base_row, "disposition": "BANAL_BASELINE", "baseline": b})
        return
    comp = compile_payload(payload, reg, uni)
    if comp.jev_question:
        outputs["jev"].append({**comp.jev_question, "node": node, "lab": lab_key,
                               "state": "QUEUED", "at": _now(),
                               # A Jev answer series labelled over historical text inherits the
                               # labelling model's cutoff, set when the job is answered.
                               "lookahead_guard": "set from the answering model's cutoff"})
    if comp.refused:
        tally.refused += 1
        outputs["genealogy"].append({**base_row, "disposition": "REFUSED", "why": comp.refused})
        return
    if comp.blockers:
        tally.debt += 1
        for bl in comp.blockers:
            tally.blockers[bl] += 1
        for src in comp.data_needed:
            outputs["data_requests"].append({"series": src, "node": node, "lab": lab_key,
                                             "mechanism": mech[:200], "at": _now()})
        outputs["debt"].append({"id": node, "lab": lab_key, "payload": payload,
                                "blockers": comp.blockers, "detail": comp.detail[:6],
                                "coordinate": coord, "first_seen": _now(), "attempts": 0,
                                "state": "OPEN"})
        outputs["genealogy"].append({**base_row, "disposition": "CONVERSION_DEBT",
                                     "blockers": comp.blockers, "detail": comp.detail[:6]})
        return
    for cell in comp.cells:
        cid = cell_identity(cell)
        klass, against = classify(cell, mech, base_row["parents"], mem)
        tally.novelty[klass] += 1
        g = {**base_row, "cell": cell, "cell_id": cid, "novelty_class": klass,
             "measured_against": against}
        if klass in EMITTED_CLASSES:
            tally.emitted += 1
            if mrow is not None:
                mrow["exact"] = int(mrow.get("exact", 0)) + 1
                mrow["novel"] = int(mrow.get("novel", 0)) + int(klass == "GENUINELY_NOVEL")
            outputs["donate"].append(donation_row(cell, cid, g, payload))
            g["disposition"] = "EMITTED"
        else:
            g["disposition"] = klass
        outputs["genealogy"].append(g)
        mem.remember(g)


def donation_row(cell: dict[str, Any], cid: str, g: dict[str, Any],
                 payload: dict[str, Any]) -> dict[str, Any]:
    """The exact shape `miner_candidate_compiler.compile_row` admits as EXACT_RECIPE."""
    return {"kind": "hypothesis", "family": cell["family"], "params": cell["params"],
            "symbols": [cell["symbol"]], "symbol": cell["symbol"],
            "mechanism": g["mechanism"], "falsifier": g["falsifier"],
            "title": f"llm_lab {g['lab']}: {g['mechanism'][:120]}",
            "lab": g["lab"], "lab_name": LAB_BY_KEY[g["lab"]].name if g["lab"] in LAB_BY_KEY
            else g["lab"], "novelty_class": g["novelty_class"], "cell_id": cid,
            "genealogy": {"node": g["node"], "parents": g["parents"],
                          "measured_against": g["measured_against"]},
            "lineage": {"root": g["node"], "operator": "llm_lab"},
            "mechanism_class": g["mechanism_class"], "coordinate": g["coordinate"],
            "model": g["model"], "prompt_hash": g["prompt_hash"],
            "horizon": str(payload.get("horizon") or "")[:20],
            "url": f"llm_lab://{g['lab']}/{g['node']}",
            "lookahead_guard": lookahead_guard(g["model"]),
            "copy_trade": False, "credibility_inherited": False, "gauntlet_bypass": False}


#: KNOWN TRAINING CUTOFFS, by model-id fragment -> "YYYY-MM-DD". Empty by default ON PURPOSE: a
#: cutoff written from memory is a claim, and a wrong one that is too EARLY would let in-sample
#: history count as evidence. `desks/mt5/data/llm_lab/model_cutoffs.json` ({"<fragment>":
#: "<date>", ...}, each with the provider's own documentation as its source) may name one.
MODEL_CUTOFFS = STATE_DIR / "model_cutoffs.json"


def lookahead_guard(model: str, *, at: str | None = None) -> dict[str, Any]:
    """THE LOOK-AHEAD GUARD (2026-10-13). A model that proposed or labelled a cell has READ the
    history the cell is about to be backtested on: anything before its training cutoff is
    contaminated -- the cell may go to the gauntlet, but that window is not evidence.

    `evidence_from` is the LATER of the model's documented cutoff and the date the cell was born
    (audit must-fix 2, 2026-10-13: it was the earlier, so a 2023-12-01 cutoff let 34 months the
    model had seen count). Only data after both counts: the model has not read it, and the cell
    was not shaped by it. With no registered cutoff it is the birth date, so ONLY forward
    (post-generation) data is evidence -- which the forward clocks already require before any
    promotion, so the guard tightens nothing that is live and loosens nothing.
    """
    day = (at or _now())[:10]
    table = _read_json(MODEL_CUTOFFS, {}) or {}
    hit = next((str(d)[:10] for frag, d in table.items()
                if isinstance(frag, str) and frag and frag.lower() in model.lower()), "")
    return {"model": model, "model_training_cutoff": hit or UNMEASURED,
            "evidence_from": max(hit, day) if hit else day,
            "basis": ("registered cutoff" if hit else
                      "cutoff UNMEASURED: generation date, so only post-generation data counts"),
            "rule": "backtest data before evidence_from is contaminated; it may be run, never "
                    "counted as evidence"}


def synthesis_lines(outputs: dict[str, list[dict[str, Any]]]
                    ) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Cross-lab reading of the INDEPENDENT pass: rediscoveries, disagreements, and the menu
    the synthesis call composes from."""
    emitted = [g for g in outputs["genealogy"] if g.get("disposition") == "EMITTED"]
    groups: dict[tuple[str, str, str], set[str]] = {}
    sides: dict[tuple[str, str], set[int]] = {}
    for g in emitted:
        c = g["cell"]
        groups.setdefault((g["mechanism_class"], c["symbol"], c["family"]), set()).add(g["lab"])
        p = c.get("params") or {}
        side = p.get("side") or p.get("side_when_high") or p.get("side_in_high")
        if isinstance(side, (int, float)) and side:
            sides.setdefault((g["mechanism_class"], c["symbol"]), set()).add(1 if side > 0 else -1)
    redisc = [{"mechanism_class": k[0], "symbol": k[1], "family": k[2], "labs": sorted(v)}
              for k, v in groups.items() if len(v) >= 2]
    disagree = [f"disagreement: {k[0]} on {k[1]} -- labs proposed BOTH directions"
                for k, v in sides.items() if len(v) == 2]
    menu = [f"node {g['node']} (lab {g['lab']}): {g['mechanism'][:140]}" for g in emitted[:12]]
    return menu, redisc, disagree


def retry_debt(reg: dict[str, FamilySpec], uni: dict[str, str], mem: Memory, tally: Tally,
               outputs: dict[str, list[dict[str, Any]]], fingerprint: str,
               limit: int = 400, write: bool = True) -> dict[str, Any]:
    """TEMPORAL REOPENING: every open debt is re-compiled when the families, the universe or the
    lake could have changed. Deterministic, no model call, bounded per pass by a rotating cursor."""
    doc = _read_json(DEBT, {}) or {}
    rows: dict[str, dict[str, Any]] = doc.get("rows") or {}
    opened = [r for r in rows.values() if r.get("state") == "OPEN"]
    opened.sort(key=lambda r: (str(r.get("last_attempt") or ""), str(r.get("first_seen") or "")))
    resolved = 0
    for r in opened[:limit]:
        r["attempts"] = int(r.get("attempts", 0)) + 1
        r["last_attempt"] = _now()
        comp = compile_payload(dict(r.get("payload") or {}), reg, uni)
        if comp.cells and not comp.blockers:
            r["state"] = "RESOLVED"
            r["resolved_at"] = _now()
            resolved += 1
            for cell in comp.cells:
                cid = cell_identity(cell)
                mech = str((r.get("payload") or {}).get("mechanism") or "")[:400]
                klass, against = classify(cell, mech, [], mem)
                g = {"node": r["id"], "lab": r.get("lab"), "at": _now(), "model": "debt_reopen",
                     "prompt_hash": "", "coordinate": r.get("coordinate") or {},
                     "mechanism_class": slug((r.get("payload") or {}).get("mechanism_class")
                                             or "reopened"),
                     "mechanism": mech, "falsifier": str((r.get("payload") or {})
                                                         .get("falsifier") or "")[:300],
                     "parents": [], "cell": cell, "cell_id": cid, "novelty_class": klass,
                     "measured_against": against}
                tally.novelty[klass] += 1
                if klass in EMITTED_CLASSES:
                    tally.emitted += 1
                    outputs["donate"].append(donation_row(cell, cid, g, r.get("payload") or {}))
                    g["disposition"] = "EMITTED"
                else:
                    g["disposition"] = klass
                outputs["genealogy"].append(g)
                mem.remember(g)
        else:
            r["blockers"] = comp.blockers or r.get("blockers") or []
            r["detail"] = comp.detail[:6] or r.get("detail") or []
            if comp.refused:
                r["state"] = "REFUSED"
                r["why"] = comp.refused
    for d in outputs["debt"]:
        rows.setdefault(d["id"], d)
    doc["rows"] = rows
    doc["fingerprint"] = fingerprint
    if write:
        _write_json(DEBT, doc)
    open_rows = [r for r in rows.values() if r.get("state") == "OPEN"]
    by = Counter(b for r in open_rows for b in r.get("blockers") or [])
    return {"open": len(open_rows), "resolved_this_pass": resolved,
            "retried_this_pass": min(limit, len(opened)), "by_blocker": dict(by),
            "rule_shaped_open": [r["id"] for r in open_rows
                                 if set(r.get("blockers") or []) & {
                                     "NEEDS_EXACT_RULE_EXTRACTION", "NEEDS_PARAMETER_INFERENCE",
                                     "NEEDS_EXECUTABLE_FAMILY"}][:50]}


def converter_asks(debt_ids: Sequence[str], reg: dict[str, FamilySpec], uni: dict[str, str],
                   rng: random.Random, k: int) -> list[Ask]:
    """Rule-shaped debt goes back to a model as a CONVERSION task: map this mechanism onto an
    exact registered recipe or a valid formula -- never invent data it does not have."""
    doc = _read_json(DEBT, {}) or {}
    rows = doc.get("rows") or {}
    out = []
    for i in debt_ids[:k]:
        r = rows.get(i) or {}
        p = r.get("payload") or {}
        lab = LAB_BY_KEY.get(str(r.get("lab")), LABS[0])
        ctx = [f"raw mechanism: {str(p.get('mechanism'))[:280]}",
               f"its falsifier: {str(p.get('falsifier'))[:160]}",
               f"symbols named: {p.get('symbols')}",
               f"why it is not executable yet: {r.get('blockers')} {r.get('detail')}",
               f"parents: [\"{i}\"]  (copy this into parents)",
               "all registered families: " + all_family_names(reg)[:900], FORMULA_GRAMMAR]
        ctx += [f"menu: {ln}" for ln in menu_lines(reg, lab, rng, k=16)]
        task = ("CONVERSION: make this raw mechanism an exact, falsifiable, executable cell. Use a "
                "registered family with its own keywords, or a formula expression. If it cannot be "
                "done without data the desk lacks, return family NONE and name the data in needs. "
                + TASK_RULES)
        out.append(Ask(lab, r.get("coordinate") or {"lab": lab.key, "mechanism_class": "conversion",
                                                     "asset_class": "", "horizon": ""},
                       "conversion_debt", "", ctx[:40], task))
    return out


def coverage_from_outcomes(cov: Coverage) -> dict[str, int]:
    """Lift coordinates whose emitted cells the gauntlet has since judged or certified."""
    judged: dict[str, bool] = {}
    for r in _jsonl(VERDICTS, limit=200000):
        c = str(r.get("cell") or "")
        if c:
            judged[c] = judged.get(c, True) and bool(r.get("passed"))
    certified: set[str] = set()
    forward: set[str] = set()
    try:
        import novelty_gate as ng
        lib = ng.Library.load()
        for m in lib.members:
            if m.origin == "sleeve" and m.ident:
                forward.add(m.ident)
            elif m.origin == "survivor" and m.ident:
                certified.add(m.ident)
    except Exception:                                  # pragma: no cover
        pass
    for row in cov.doc["coords"].values():
        cells = row.get("cells") or []
        state = None
        if any(c in forward for c in cells):
            state = "FORWARD"
        elif any(c in certified for c in cells):
            state = "CERTIFIED"
        elif cells and all(c in judged and not judged[c] for c in cells):
            state = "GRAVEYARDED"
        elif any(c in judged for c in cells):
            state = "TESTED"
        if state:
            row["state"] = state
    return dict(Counter(str(r.get("state")) for r in cov.doc["coords"].values()))


def _cb_tone_role(*, budget_s: float, max_llm: int) -> dict[str, Any]:
    """The central-bank tone role (`cb_tone_lab`). One role failing never fails the lab pass."""
    try:
        import cb_tone_lab
        return cb_tone_lab.run(budget_s=budget_s, max_llm=max_llm)
    except Exception as exc:                           # pragma: no cover - defensive
        return {"state": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}


def gauntlet_trims() -> bool:
    """True only when the canonical gauntlet carries the look-ahead trim (the sealed patch
    `llm_lookahead_gauntlet`). Until then the lab's cells would reach every gate untrimmed, so
    they are HELD, never donated (audit blocker on #332, 2026-10-13). Read from the source each
    call: the first pass after the laptop lands the patch releases them with no other step."""
    try:
        text = GAUNTLET.read_text("utf-8", errors="replace")
    except OSError:
        return False
    return "def llm_born(" in text and "def evidence_trim(" in text


def donation_target(default: Path) -> Path:
    """Where an LLM-lab donation may be written: the compiler's seat dir, or the held queue."""
    return default if gauntlet_trims() else STATE_DIR / "held_donations" / default.name


def release_held(dest: Path | None = None) -> dict[str, Any]:
    """Move held donations into the seat dir once the gauntlet trims. Nothing is lost while held."""
    held = STATE_DIR / "held_donations"
    # One held subdirectory per destination seat, so a release keeps each donor's attribution.
    files = sorted(held.glob("*/*.json")) if held.is_dir() else []
    if not gauntlet_trims():
        return {"state": "HELD", "files": len(files),
                "why": "external_gauntlet.py lacks the look-ahead trim (sealed patch "
                       "llm_lookahead_gauntlet not landed): LLM-born cells are not donated"}
    root = (dest or DONATE_DIR).parent
    moved = 0
    for f in files:
        seat = root / f.parent.name
        seat.mkdir(parents=True, exist_ok=True)
        os.replace(f, seat / f.name)
        moved += 1
    return {"state": "DONATING", "released": moved}


def style_screened(rows: list[dict[str, Any]], *, deadline: float | None = None
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """`lab_style.screen`: rows to donate (each stamped `style_screen`) and a summary. A cell
    whose style the book already owns is held in `style_held.json`, never dropped. A crashing
    screen donates every row unchanged: the screen can only hold, never lose."""
    if not rows:
        return rows, {"screened": 0}
    try:
        import lab_style
        return lab_style.screen(rows, deadline=deadline)
    except Exception as exc:                           # pragma: no cover - defensive
        why = f"{type(exc).__name__}: {str(exc)[:120]}"
        _style_event("screen_error", why)
        return rows, {"state": "ERROR", "why": why}


def _style_event(kind: str, why: str) -> None:
    """A style-screen failure reaches the leg event log, not only this pass's report."""
    try:
        from libs.ops import events
        events.emit("lab_style", leg="llm_lab", status=kind, why=why)
    except Exception:                                  # pragma: no cover - defensive
        pass


def release_restyled() -> dict[str, Any]:
    """Donate held cells whose style the book no longer owns (to the seat dir or the hold)."""
    try:
        import lab_style
        freed, still = lab_style.release()
        rows = list(freed.values())
        if rows:
            import llm_lab_roles as roles
            roles.record_evidence_start(rows, STATE_DIR / "evidence_start.json")
            target = donation_target(DONATE_DIR)
            target.mkdir(parents=True, exist_ok=True)
            stamp = _now().replace(":", "").replace("-", "")[:15]
            # The donation is on disk BEFORE the hold forgets it (audit should-fix 4).
            _write_json(target / f"discoveries_restyled_{stamp}.json",
                        {"source": ORGAN, "generated_at": _now(), "rule": RULE,
                         "discoveries": rows})
            lab_style.forget(freed)
        expired = sum(1 for r in rows
                      if (r.get("style_screen") or {}).get("release_reason") == "HELD_EXPIRED")
        holds = lab_style.publish_holds(
            credit=_read_json(STATE_DIR / "verdict_credit.json", {}) or {},
            released=len(rows) - expired, expired=expired)
    except Exception as exc:                           # pragma: no cover - defensive
        why = f"{type(exc).__name__}: {str(exc)[:120]}"
        _style_event("release_error", why)
        return {"state": "ERROR", "why": why}
    return {"released": len(rows) - expired, "expired": expired, "still_held": still,
            "oldest_hold_days": holds.get("oldest_hold_days"),
            "keff_days_deferred": holds.get("keff_days_deferred")}


def _collector_role(*, budget_s: float, max_llm: int) -> dict[str, Any]:
    """collector_author's replacement (`collector_lab`): declarative specs, fixed fetcher."""
    try:
        import collector_lab
        return collector_lab.run(budget_s=budget_s, max_llm=max_llm)
    except Exception as exc:                           # pragma: no cover - defensive
        return {"state": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}


def run(*, budget_s: float = 600.0, max_calls: int | None = None, dry_run: bool = False,
        seed: int | None = None, workers: int = 4) -> dict[str, Any]:
    started = time.time()
    if os.environ.get("QUANT_LLM_LAB_PAID", "0") != "1":
        os.environ["QUANT_FREE_TIER"] = "1"
    donations = release_held() if not dry_run else {"state": "dry run"}
    if not dry_run:
        donations["restyled"] = release_restyled()
    max_calls = int(max_calls if max_calls is not None else
                    os.environ.get("QUANT_LLM_LAB_MAX_CALLS", "24"))
    # The provider's own quota (a 429 cools the rung) is the binding daily limit; this cap only
    # stops a runaway loop, so it sits far above an hourly pass that covers every model.
    daily_cap = int(os.environ.get("QUANT_LLM_LAB_DAILY_CALLS", "3000"))
    # Refresh OpenRouter's own account limits once a pass (cached an hour): every budget that
    # reads them moves from 50 to 1,000 a day when credit lands, and the report shows whether a
    # paid id could ever leave this box (it cannot unless QUANT_LLM_LAB_PAID=1).
    from libs.ops import openrouter_guard
    or_key = {} if dry_run else openrouter_guard.key_info()
    rng = random.Random(seed if seed is not None else int(started))  # noqa: S311 - not crypto
    reg = family_registry()
    uni = universe()
    fp = registry_fingerprint(reg)
    ontology = _ontology()
    cov = Coverage.load()
    models: dict[str, Any] = _read_json(MODELS, {}) or {}
    mem = Memory.load()
    ps = _seat()
    try:
        seat_on = bool(ps is not None and ps.enabled())
    except Exception:                                  # pragma: no cover
        seat_on = False
    try:
        from libs.ops import free_chain
        chain_status = free_chain.status()
    except Exception:                                  # pragma: no cover
        chain_status = {"verdict": UNMEASURED}

    tallies: dict[str, Tally] = {lab.key: Tally() for lab in LABS}
    tallies["SYNTHESIS"] = Tally()
    tallies["CONVERTER"] = Tally()
    outputs: dict[str, list[dict[str, Any]]] = {k: [] for k in (
        "genealogy", "donate", "debt", "data_requests", "jev", "classes", "attacks")}
    plan: list[dict[str, Any]] = []
    calls_budget = min(max_calls, _calls_left(daily_cap))
    hunted: list[str] = []
    if seat_on and not dry_run:
        hunted = hunt_models(models, budget_s=min(30.0, budget_s / 10))
    # EVERY MODEL, EVERY CYCLE: the pass is sized to give each registered model one call on top of
    # the labs' own, inside the daily cap. A model the cap still leaves out is named in the
    # coverage report, never silently skipped.
    n_registered = sum(1 for r in models.values() if r.get("status") == "REGISTERED")
    calls_budget = min(max(max_calls, n_registered + len(INVENTORS) + 6), _calls_left(daily_cap))
    # ...unless OpenRouter's MEASURED allowance says otherwise: then the pass spends exactly its
    # even share of the day, and models rotate least-recently-asked first inside it.
    share = openrouter_pass_share() if seat_on and not dry_run else {}
    if share:
        calls_budget = min(int(share["per_pass"]), _calls_left(daily_cap))
    rotation: dict[str, str] = _read_json(ROTATION, {}) or {}

    def _go(ask: Ask) -> tuple[Ask, list[Any]]:
        left = budget_s - (time.time() - started)
        if left < 30:
            return ask, []
        try:
            return ask, _call(ask, n=4, timeout=min(120.0, left))
        except Exception as exc:          # pragma: no cover - one lab never kills the pass
            return ask, [("error", str(exc)[:160])]

    calls_made = 0
    # ---- phase 0: conversion FIRST. Re-compile everything owed; re-ask the rule-shaped debt.
    debt = retry_debt(reg, uni, mem, tallies["CONVERTER"], outputs, fp, write=not dry_run)
    if seat_on and not dry_run and calls_made < calls_budget:
        conv = converter_asks(debt["rule_shaped_open"], reg, uni, rng,
                              k=min(4, calls_budget - calls_made))
        for ask in conv:
            if budget_s - (time.time() - started) < 45:
                break
            _, props = _go(ask)
            calls_made += 1
            t = tallies["CONVERTER"]
            t.asked += 1
            for p in [p for p in props if not isinstance(p, tuple)]:
                process(p, "CONVERTER", ask.coord, reg, uni, mem, t, models, outputs)

    # ---- phase 0b: the CENTRAL-BANK TONE role (idea 18). Native-language statements scored
    # into point-in-time lake series; the lexicon half runs even with the seat dark.
    cb_tone: dict[str, Any] = {"state": "NOT_RUN"} if not dry_run else {"state": "dry run"}
    if not dry_run and budget_s - (time.time() - started) > 90:
        cb_tone = _cb_tone_role(budget_s=min(150.0, budget_s * 0.25),
                                max_llm=max(0, min(8, calls_budget - calls_made)) if seat_on
                                else 0)
        calls_made += int((cb_tone.get("model") or {}).get("calls") or 0)

    # ---- phase 0c: the COLLECTOR role. Breadth-feed sources become declarative specs a fixed
    # fetcher runs (no model-written code); working specs refresh every pass with no call.
    collector: dict[str, Any] = {"state": "NOT_RUN"} if not dry_run else {"state": "dry run"}
    if not dry_run and budget_s - (time.time() - started) > 90:
        collector = _collector_role(budget_s=min(120.0, budget_s * 0.2),
                                    max_llm=max(0, min(4, calls_budget - calls_made)) if seat_on
                                    else 0)
        calls_made += int(collector.get("asked") or 0)

    # ---- phase 1: the independent first pass. No lab sees another lab's current answers.
    own_recent: dict[tuple[str, str], list[str]] = {}
    for g in _jsonl(GENEALOGY, limit=5000):
        c = g.get("coordinate") or {}
        own_recent.setdefault((str(g.get("lab")), str(c.get("mechanism_class"))), []).append(
            str(g.get("mechanism") or ""))
    used_models: set[str] = set()
    asks: list[Ask] = []
    extra: dict[str, list[str]] = {"disagreement": list((_read_json(REPORT, {}) or {})
                                                        .get("disagreements") or [])[:8],
                                   "jev": ["Jev answers are typed: probability in [0,1], a "
                                           "score in [-1,1] or a choice; the answer series is "
                                           "point-in-time by publication stamp"]}
    import llm_lab_roles as roles
    credit: dict[str, Any] = _read_json(STATE_DIR / "verdict_credit.json", {}) or {}
    for key, lines in (credit.get("feedback") or {}).items():
        extra[f"verdicts:{key}"] = list(lines)
    order = prioritised(rng, credit)
    # Under a measured share the labs draw models from the rotation queue (least recently asked
    # first), so a capped pass never spends its few calls on models the last pass already asked;
    # with room to spare the verdict loop's yield ranking picks.
    queue = sorted((k for k, r in models.items() if r.get("status") == "REGISTERED"),
                   key=lambda k: (str(rotation.get(k) or ""), k)) if share else []
    for lab in order:
        coord, why = choose_coordinate(lab, ontology, cov, rng)
        model = (next((k for k in queue if k not in used_models), None) if share
                 else assign_model(models, rng, used_models, credit))
        if model:
            used_models.add(model)
        recent = own_recent.get((lab.key, coord["mechanism_class"]), [])[-5:]
        ask = build_ask(lab, coord, why, model, reg, uni, rng, recent, extra)
        if len(asks) < calls_budget - calls_made:
            asks.append(ask)
            plan.append({"lab": lab.key, "coordinate": coord, "why": why, "model": model or
                         "default_route"})
        else:
            cov.touch(coord_id(coord), coord, "QUEUED")
            plan.append({"lab": lab.key, "coordinate": coord, "why": why, "state": "QUEUED",
                         "reason": "per-pass call cap: NOT THIS PASS, owed"})

    # MODEL COVERAGE: every registered model the labs' draws left out gets its own ask, labs in
    # rotation, so each free model produces on every cycle and earns (or fails to earn) credit.
    registered = [k for k, r in models.items() if r.get("status") == "REGISTERED"]
    # Least recently asked first (never-asked before all), so a capped pass still reaches every
    # model within the rotation window; any share left after one call each goes round again.
    uncovered = sorted((k for k in registered if k not in used_models),
                       key=lambda k: (str(rotation.get(k) or ""), k))
    if share and registered:
        spare = calls_budget - calls_made - len(asks) - len(uncovered)
        again = sorted(registered, key=lambda k: (str(rotation.get(k) or ""), k))
        uncovered += [again[i % len(again)] for i in range(max(0, spare))]
    for i, mkey in enumerate(uncovered):
        lab = order[i % len(order)]
        if len(asks) >= calls_budget - calls_made:
            plan.append({"lab": lab.key, "model": mkey, "state": "QUEUED",
                         "reason": "daily call cap: model coverage owed this cycle"})
            continue
        coord, why = choose_coordinate(lab, ontology, cov, rng)
        recent = own_recent.get((lab.key, coord["mechanism_class"]), [])[-5:]
        asks.append(build_ask(lab, coord, why, mkey, reg, uni, rng, recent, extra))
        used_models.add(mkey)
        plan.append({"lab": lab.key, "coordinate": coord, "why": "model_coverage",
                     "model": mkey})

    pass_cov: dict[str, dict[str, Any]] = {}
    if seat_on and not dry_run and asks:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            results = list(pool.map(_go, asks))
        for ask, props in results:
            t = tallies[ask.lab.key]
            t.asked += 1
            calls_made += 1
            props = [p for p in props if not isinstance(p, tuple)]
            if any(getattr(p, "payload", None) is not None or p.accepted for p in props):
                t.replies += 1
            answered = [p for p in props if getattr(p, "payload", None) is not None]
            model_key = next((str(p.provenance.model) for p in props
                              if getattr(p.provenance, "model", "")), "")
            if ask.model:
                pc = pass_cov.setdefault(ask.model, {"asked": 0, "answered": 0,
                                                     "fell_through_to": []})
                pc["asked"] += 1
                if model_key == ask.model and answered:
                    pc["answered"] += 1
                elif model_key and model_key not in pc["fell_through_to"]:
                    pc["fell_through_to"].append(model_key)
            if model_key:
                observe_model(models, model_key)
            for key in {ask.model, model_key} - {""}:
                m = models.get(key)
                if m is not None:
                    m["asked"] = int(m.get("asked", 0)) + 1
                    m["replies"] = int(m.get("replies", 0)) + int(bool(answered))
            before = len(outputs["genealogy"])
            for p in props:
                process(p, ask.lab.key, ask.coord, reg, uni, mem, t, models, outputs)
            new = outputs["genealogy"][before:]
            disp = Counter(g.get("disposition") for g in new)
            state = ("DISCOVERED" if disp.get("EMITTED") else
                     "PARTIAL" if disp.get("CONVERSION_DEBT") else
                     "DUPLICATE" if disp.get("EXACT_DUPLICATE") or disp.get("PARAMETER_NEIGHBOUR")
                     else "BLOCKED" if disp.get("REFUSED") or disp.get("BANAL_BASELINE")
                     else "INVALID")
            cov.touch(coord_id(ask.coord), ask.coord, state,
                      cells=[g["cell_id"] for g in new if g.get("disposition") == "EMITTED"],
                      novel=sum(1 for g in new if g.get("novelty_class") == "GENUINELY_NOVEL"))
    elif asks and not dry_run:
        for ask in asks:
            cov.touch(coord_id(ask.coord), ask.coord, "QUEUED")

    # ---- phase 2: synthesis across the independent answers, then the red team.
    menu, redisc, disagree = synthesis_lines(outputs)
    if seat_on and not dry_run and menu and calls_made < calls_budget \
            and budget_s - (time.time() - started) > 60:
        syn = Ask(LAB_BY_KEY["A"], {"lab": "SYNTHESIS", "mechanism_class": "composition",
                                    "asset_class": "", "horizon": ""}, "synthesis", "",
                  [*menu, "all registered families: " + all_family_names(reg)[:900],
                   FORMULA_GRAMMAR, *[f"menu: {ln}" for ln in
                                      menu_lines(reg, LABS[0], rng, k=10)]][:40],
                  "SYNTHESIS: combine mechanisms from DIFFERENT labs above into compositions whose "
                  "joint condition is economically meaningful. Put the source node ids in parents. "
                  + TASK_RULES)
        _, props = _go(syn)
        calls_made += 1
        t = tallies["SYNTHESIS"]
        t.asked += 1
        for p in [p for p in props if not isinstance(p, tuple)]:
            process(p, "SYNTHESIS", syn.coord, reg, uni, mem, t, models, outputs)
        if calls_made < calls_budget and budget_s - (time.time() - started) > 60:
            red = Ask(LAB_BY_KEY["P"], {"lab": "P", "mechanism_class": "alternative_explanation",
                                        "asset_class": "", "horizon": ""}, "red_team", "",
                      menu[:20],
                      LAB_BY_KEY["P"].mandate + ' Return {"target": "<node id>", "alternative": '
                      '"<the rival explanation>", "falsifier": "<cheapest test that separates '
                      'them>"} per line. You have no authority: attacks are recorded, not obeyed.')
            got = ps._asked(ORGAN, role="generation", task=red.task, grammar=(
                '{"target": "<node id>", "alternative": "<rival explanation, <=240 chars>", '
                '"falsifier": "<cheapest separating test, <=200 chars>"}'),
                context=red.context, n=8, label="attack", validate=_validate_attack,
                timeout=120.0) if ps is not None else []
            calls_made += 1
            tallies["P"].asked += 1
            for p in got:
                if p.accepted and isinstance(p.payload, dict):
                    pl = p.payload
                    outputs["attacks"].append({"target": str(pl.get("target"))[:60],
                                               "alternative": str(pl.get("alternative"))[:300],
                                               "falsifier": str(pl.get("falsifier"))[:200],
                                               "model": p.provenance.model, "at": _now()})
            tallies["P"].accepted += len(outputs["attacks"])

    # ---- phase 3: the roles -- missed moves (Q), code lab (R), source scout (S), sleeve red team
    # (T). Same call budget, same free chain, same zero authority.
    role_report: dict[str, Any] = {"state": "dry run"} if dry_run else {}
    if not dry_run and budget_s - (time.time() - started) > 60:
        try:
            role_report, role_calls = roles.run(
                lab=sys.modules[__name__], reg=reg, uni=uni, mem=mem, tallies=tallies,
                models=models, outputs=outputs, rng=rng,
                calls_left=max(0, calls_budget - calls_made),
                deadline=started + budget_s - 30, seat_on=seat_on)
            calls_made += role_calls
        except Exception as exc:                       # pragma: no cover - a role never kills it
            role_report = {"state": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}

    # ---- the debt ledger again, so phase-1 and synthesis debt is persisted with its blockers.
    debt = {**retry_debt(reg, uni, mem, tallies["CONVERTER"], outputs, fp, limit=0,
                         write=not dry_run),
            "resolved_this_pass": debt["resolved_this_pass"],
            "retried_this_pass": debt["retried_this_pass"]}

    # ---- persist
    donated = None
    if not dry_run:
        new_classes = {c["class"] for c in outputs["classes"]} - set(ontology)
        _save_ontology(new_classes, {c["class"]: c["lab"] for c in outputs["classes"]
                                     if c["class"] in new_classes})
        _append_jsonl(GENEALOGY, outputs["genealogy"])
        _append_jsonl(DATA_REQUESTS, outputs["data_requests"])
        known_q = {str(r.get("series")) for r in _jsonl(JEV_JOBS)}
        _append_jsonl(JEV_JOBS, [j for j in outputs["jev"] if j["series"] not in known_q])
        # THE EVIDENCE MAP FIRST (audit must-fix 4): the compiler may read a donation the moment
        # it lands, so the guard's start dates are on disk before any donation is.
        outputs["donate"], style = style_screened(outputs["donate"],
                                                  deadline=time.time() + 60.0)
        donations["style_screen"] = style
        roles.record_evidence_start(outputs["donate"], STATE_DIR / "evidence_start.json")
        if outputs["donate"]:
            target = donation_target(DONATE_DIR)
            target.mkdir(parents=True, exist_ok=True)
            stamp = _now().replace(":", "").replace("-", "")[:15]
            donated = target / f"discoveries_{stamp}.json"
            _write_json(donated, {"source": ORGAN, "generated_at": _now(), "rule": RULE,
                                  "discoveries": outputs["donate"]})
        _write_json(MODELS, models)
        _count_calls(calls_made)
        # THE VERDICT LOOP: this pass's calls are charged to their lab and model, every verdict on
        # a lab cell is credited back, and the next pass ranks on certified k_eff per call.
        pairs = [(a.lab.key, a.model) for a in asks] if seat_on else []
        pairs += [(k, "") for k, t in tallies.items()
                  for _ in range(max(0, t.asked - sum(1 for a in asks if a.lab.key == k)))]
        try:
            credit = roles.verdict_loop(VERDICTS, DONATE_DIR,
                                        pairs[:calls_made] if calls_made else [],
                                        STATE_DIR / "verdict_credit.json")
        except Exception as exc:          # a broken credit file never loses the pass's report
            credit = {"error": f"verdict_loop: {type(exc).__name__}: {str(exc)[:160]}"}
    now_iso = _now()
    for mkey in pass_cov:
        rotation[mkey] = now_iso
    per_pass = int(share.get("per_pass") or 0) if share else 0
    window_h = (-(-len(registered) // per_pass) + 1) if per_pass else None
    if not dry_run:
        _write_json(ROTATION, rotation)
    coverage = roles.coverage_report(models, pass_cov, {k: t.row() for k, t in tallies.items()},
                                     role_report, cb_tone, credit, chain_status,
                                     seat_on=seat_on, dry_run=dry_run, rotation=rotation,
                                     window_h=window_h,
                                     budget_bound=bool(share) and calls_made >= calls_budget,
                                     collector=collector)
    coverage["openrouter_share"] = share or UNMEASURED
    if not dry_run:
        _write_json(STATE_DIR / "model_yield.json", coverage["models"])
        _write_json(REPORT.parent / "LLM_COVERAGE.json", coverage)
    states = coverage_from_outcomes(cov)
    if not dry_run:
        _write_json(COVERAGE, cov.doc)
    ont_after = _ontology() if not dry_run else ontology
    total_novelty: Counter = Counter()
    for t in tallies.values():
        total_novelty.update(t.novelty)
    jev_jobs = _jsonl(JEV_JOBS)
    doc = {
        "generated_utc": _now(), "organ": ORGAN, "law": RULE,
        "verdict": ("RAN" if calls_made else UNMEASURED),
        "why": ("" if calls_made else
                "dry run" if dry_run else
                "no free provider resolves on this host (seat dark): the lab planned its pass, "
                "re-compiled its debt and kept every coordinate owed" if not seat_on else
                "daily call cap reached: the pass is owed"),
        "seat_enabled": seat_on, "free_chain": chain_status, "paid_enabled":
            os.environ.get("QUANT_LLM_LAB_PAID", "0") == "1",
        "openrouter_account": {
            "daily_free_limit": or_key.get("daily_limit") or UNMEASURED,
            "limit_source": or_key.get("limit_source") or UNMEASURED,
            "is_free_tier": or_key.get("is_free_tier", UNMEASURED),
            "credit_limit_usd": or_key.get("credit_limit_usd", UNMEASURED),
            "usage_usd": or_key.get("usage_usd", UNMEASURED),
            "paid_ids_refused": not openrouter_guard.paid_allowed()},
        "budget": {"max_calls_per_pass": max_calls, "daily_calls_cap": daily_cap,
                   "calls_this_pass": calls_made, "calls_left_today": _calls_left(daily_cap),
                   "budget_s": budget_s, "elapsed_s": round(time.time() - started, 1)},
        "labs": {k: {"name": LAB_BY_KEY[k].name if k in LAB_BY_KEY else k.lower(), **t.row()}
                 for k, t in tallies.items()},
        "plan": plan,
        "novelty": {c: int(total_novelty.get(c, 0)) for c in NOVELTY_CLASSES},
        "emitted": len(outputs["donate"]), "donation": _rel(donated) if donated else None,
        "independent_rediscoveries": redisc, "disagreements": disagree,
        "red_team_attacks": outputs["attacks"][:30],
        "conversion_debt": debt,
        "cb_tone": cb_tone,
        "collector": collector,
        "donations": donations,
        "roles": role_report,
        "model_coverage": {k: coverage.get(k) for k in ("verdict", "red", "models_available",
                                                  "models_answered")},
        "verdict_loop": {k: credit.get(k) for k in ("keff_basis", "judged_cells",
                                                    "certified_cells", "ranking_rule")},
        "data_requests_this_pass": len(outputs["data_requests"]),
        "jev": {"provider": UNMEASURED,
                "why": ("no TypeSafe/Jev key is acquired and its current API is unverified; "
                        "questions queue and their cells wait as NEEDS_DATA until a Jev series "
                        "lands in the lake"),
                "queued_questions": sum(1 for j in jev_jobs if j.get("state") == "QUEUED")},
        "coverage": {**owed(cov, ont_after), "states": states,
                     "ontology_classes": len(ont_after),
                     "new_classes_this_pass": sorted({c["class"] for c in outputs["classes"]}
                                                     - set(ontology))[:40]},
        "models": {"registered": sum(1 for r in models.values()
                                     if r.get("status") == "REGISTERED"),
                   "review_pending": sum(1 for r in models.values()
                                         if r.get("status") == "REVIEW_PENDING"),
                   "hunted_this_pass": hunted[:20],
                   "top": sorted(({"model": k, "novel": r.get("novel", 0),
                                   "exact": r.get("exact", 0), "replies": r.get("replies", 0)}
                                  for k, r in models.items()),
                                 key=lambda r: (-int(r["novel"]), -int(r["exact"])))[:10]},
        "families_registered": len(reg), "universe_symbols": len(uni),
        "registry_fingerprint": fp,
    }
    if not dry_run:
        _write_json(REPORT, doc)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's mode)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--max-calls", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, max_calls=a.max_calls, dry_run=a.dry_run, workers=a.workers)
    print(json.dumps({k: doc[k] for k in ("verdict", "why", "emitted", "novelty", "coverage",
                                          "conversion_debt")}, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
