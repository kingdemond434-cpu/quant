"""The llm_lab building blocks that read no state a test or a pass re-points: the lab roster,
the family registry, novelty memory, the coverage map, the model registry, the referee helpers.

Split out of `llm_lab.py` (2026-11-17) so no file is one hunk too large for the independent
reviewers to read whole. `llm_lab` re-exports every name here, so every caller is unchanged.
"""
from __future__ import annotations

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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = BASE / "data" / "llm_lab"
UNIVERSE = BASE / "data" / "universe" / "universe.json"

GENEALOGY = STATE_DIR / "genealogy.jsonl"
DEBT = STATE_DIR / "conversion_debt.json"
COVERAGE = STATE_DIR / "coverage.json"
ONTOLOGY = STATE_DIR / "ontology.json"
MODELS = STATE_DIR / "model_registry.json"
DATA_REQUESTS = STATE_DIR / "data_requests.jsonl"
JEV_JOBS = STATE_DIR / "jev_jobs.jsonl"
CALLS = STATE_DIR / "calls.json"
ROTATION = STATE_DIR / "model_rotation.json"

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

#: PRINCIPAL'S RULE (2026-11-13): at least 90% of hypothesis-generation compute goes to
#: non-exotic markets (majors, crosses, gold and metals, indices, other liquid markets), at most
#: 10% to exotics. Uniform over ASSET_CLASSES the exotic class alone draws 1/9; EXOTIC_KEEP keeps
#: half of those draws (about 5.5%, under the cap with room) and sends the rest to a gap class.
EXOTIC_CLASSES = frozenset({"forex exotics"})
EXOTIC_CAP = 0.10
EXOTIC_KEEP = 0.5
#: The live book's measured gaps (2026-11-13: about 8 bets, all FX, no gold, no indices, nothing
#: entered 02:00-09:00 UTC). GAP_SHARE of every other draw is steered to a gap class, so the
#: gaps get a standing share of compute; the rest of the tensor keeps its owed-first order.
GAP_CLASSES = ("commodities", "indices")
GAP_SHARE = 0.25
GAP_NOTE = ("live book gaps to fill first: no gold or metals, no indices, few USD/JPY/EUR "
            "crosses, and no entries between 02:00 and 09:00 UTC (Asia session and the London "
            "open). Prefer original mechanisms that "
            "trade there. Exotic FX needs twice the live cost to promote, so avoid it unless the "
            "edge is large.")

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
    """May this lab mint `family` on `symbol`? FAILS CLOSED (audit of 538cb964, SF3): with the
    lane policy unreadable the answer is no, never every symbol in every family."""
    try:
        import universe_policy as up
        return bool(up.may_hypothesise(symbol, family))
    except Exception as exc:
        # Closed is safe, but SILENT closed is an idle lab that looks like a quiet one (audit
        # SF4 on 37bb136b4): the pass that read no policy reports it in RED.
        LANE_POLICY_ERRORS.setdefault(type(exc).__name__, str(exc)[:160])
        return False


#: Why the lane policy could not be read this process, by exception type. Non-empty is RED.
LANE_POLICY_ERRORS: dict[str, str] = {}


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


def _choose_coordinate(lab: Lab, ontology: Sequence[str], cov: Coverage,
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


def choose_coordinate(lab: Lab, ontology: Sequence[str], cov: Coverage,
                      rng: random.Random) -> tuple[dict[str, str], str]:
    """`_choose_coordinate`, then the principal's market mix: an exotic draw survives with
    probability EXOTIC_KEEP, otherwise it moves to a gap class; any other draw moves to a gap
    class with probability GAP_SHARE. The mechanism and horizon are kept; only the market moves,
    and the why says so, so the report can count the steering."""
    coord, why = _choose_coordinate(lab, ontology, cov, rng)
    asset = coord.get("asset_class", "")
    if asset in EXOTIC_CLASSES:
        if rng.random() < EXOTIC_KEEP:
            return coord, why
        return {**coord, "asset_class": rng.choice(GAP_CLASSES)}, f"{why}+exotic_cap"
    if asset not in GAP_CLASSES and rng.random() < GAP_SHARE:
        return {**coord, "asset_class": rng.choice(GAP_CLASSES)}, f"{why}+book_gap"
    return coord, why


def enforce_exotic_cap(coord: dict[str, str], why: str, taken: Sequence[dict[str, str]],
                       rng: random.Random) -> tuple[dict[str, str], str]:
    """HARD per-pass cap: an exotic coordinate that would lift this pass's exotic share above
    EXOTIC_CAP moves to a gap class. The draw-level steering keeps the expected share near 5%;
    this guarantees no pass, whatever the owed-first cursor serves, ever reports OVER_CAP."""
    if coord.get("asset_class") not in EXOTIC_CLASSES:
        return coord, why
    rows = [c for c in taken if c.get("asset_class")]
    exotic = sum(1 for c in rows if c["asset_class"] in EXOTIC_CLASSES)
    if (exotic + 1) / (len(rows) + 1) <= EXOTIC_CAP:
        return coord, why
    return {**coord, "asset_class": rng.choice(GAP_CLASSES)}, f"{why}+exotic_cap_hard"


def market_share(coords: Iterable[dict[str, str]]) -> dict[str, Any]:
    """Non-exotic versus exotic share of this pass's asks, against the principal's 10% cap."""
    rows = [c for c in coords if c.get("asset_class")]
    exotic = sum(1 for c in rows if c["asset_class"] in EXOTIC_CLASSES)
    gap = sum(1 for c in rows if c["asset_class"] in GAP_CLASSES)
    if not rows:
        return {"asks": 0, "verdict": UNMEASURED, "cap": EXOTIC_CAP}
    share = exotic / len(rows)
    return {"asks": len(rows), "non_exotic": len(rows) - exotic, "exotic": exotic,
            "exotic_share": round(share, 4), "gap_class_asks": gap, "cap": EXOTIC_CAP,
            "verdict": "OVER_CAP" if share > EXOTIC_CAP else "OK"}


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
LITERATURE_DIRS = ("arxiv_qfin", "academic", "literature", "central_banks", "bis_speeches")
LITERATURE_FILES_PER_DIR = 120


# ============================================================================ referee loop
#: THE REFEREE LOOP (principal, 2026-11-13: senior-PhD-level research). An emitted idea goes to a
#: skeptical referee on a DIFFERENT model, who attacks the mechanism and the data-snooping risk;
#: the proposer's model then revises it with competing explanations and a separating test. The
#: revision is a new descendant cell (lab REVISION, parent = the original); the original is never
#: dropped, and the referee's report rides on its donation. The gauntlet judges both, so the
#: funnel measures whether refereeing raises survival. No LLM decides anything here.
REFEREE_MAX = int(os.environ.get("QUANT_LLM_LAB_REFEREES", "6"))
REFEREE_GRAMMAR = (
    '{"target": "<node id>", "attacks": ["<a flaw in the causal story or its evidence>"], '
    '"snooping_risk": "<how this could be a fitted artefact: multiple testing, look-ahead, '
    'survivorship, regime luck; <=240 chars>", "competing_explanations": ["<rival story>"], '
    '"separating_test": "<cheapest test that separates them, <=200 chars>", '
    '"verdict": "sound|revise|unsound"}'
)
REFEREE_TASK = (
    "You are a skeptical referee at a top finance journal and a senior researcher at a "
    "systematic fund. Attack this hypothesis: is the causal story economically forced, is the "
    "evidence a data-snooping artefact, what else explains the same pattern, and what is the "
    "cheapest test that separates the explanations? Be specific; vague praise is worthless. "
    "One JSON object."
)
REVISION_TASK = (
    "Revise your hypothesis in light of the referee's report. Keep what survives, fix what was "
    "attacked, add the competing explanations and a separating test, and put the original node id "
    "in parents. If the referee showed it unsound, propose the best repaired mechanism instead. "
)


def _validate_referee(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "not a JSON object"
    if not payload.get("attacks") or not str(payload.get("separating_test") or "").strip():
        return "a referee report needs attacks and a separating test"
    return None


def referee_model(models: dict[str, Any], proposer: str, rng: random.Random,
                  credit: dict[str, Any] | None) -> str:
    """The referee is never the proposer's model: the strongest REGISTERED other model by judge
    credit (Thompson on certified k_eff per call), or the default route when none is free."""
    pool = sorted(k for k, r in models.items() if r.get("status") == "REGISTERED" and k != proposer)
    if not pool:
        return ""
    import llm_lab_roles as roles
    return roles.thompson((credit or {}).get("models") or {}, pool, rng)[0]


def referee_targets(outputs: dict[str, list[dict[str, Any]]], k: int) -> list[dict[str, Any]]:
    """This pass's emitted nodes, genuinely novel first, one per node, at most k."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    rows = [g for g in outputs["genealogy"] if g.get("disposition") == "EMITTED"
            and g.get("lab") not in ("REVISION",)]
    rows.sort(key=lambda g: g.get("novelty_class") != "GENUINELY_NOVEL")
    for g in rows:
        if g["node"] in seen:
            continue
        seen.add(g["node"])
        out.append(g)
        if len(out) >= k:
            break
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
    '"literature": ["<paper URL from the context>"], '
    '"competing_explanations": ["<rival story for the same pattern>"], '
    '"separating_test": "<cheapest test that tells the explanations apart, <=200 chars>", '
    '"jev_question": {"question": "...", "answer_type": "probability|score|choice", '
    '"entities": ["..."]}  (Lab L only, optional)}'
)

TASK_RULES = (
    "Invent mechanisms, not parameters. Never propose a generic RSI/MACD/Bollinger/moving-average "
    "crossover/plain breakout recipe as research. Simple is fine when the mechanism, the "
    "information or the regime dependence is new. Use ONLY a family from the menu with ONLY its "
    "keywords, or family NONE with the missing rule named in needs. Never invent data: if the "
    "mechanism needs a series the desk lacks, name it in needs. One JSON object per line. "
    + "Work as a senior PhD researcher with years at a top systematic fund: ground the mechanism "
    "in the papers listed (put their URLs in literature) or say what that literature misses; "
    "check it against the graveyard so a dead idea is not proposed again; give at least two "
    "competing explanations for the same price pattern and the cheapest test that separates "
    "them."
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


#: The live book's breadth gaps (2026-11-13) a donation can fill, so the math lab can pick the
#: [ORIG] hypotheses that widen the book: gold/metals, indices, USD/JPY/EUR crosses (USDJPY and
#: the JPY and EUR crosses; EURUSD is the major, not a cross), and 02:00-09:00 UTC entries.


def breadth_gap(symbol: str, payload: dict[str, Any]) -> list[str]:
    try:
        import universe_policy as up
        cls = str(up.asset_class_of(symbol) or "")
    except Exception:                                  # pragma: no cover
        cls = ""
    out = []
    if cls == "commodities":
        out.append("gold_metals")
    if cls == "indices":
        out.append("indices")
    sym = symbol.upper()
    if cls == "forex" and any(c in sym[:6] for c in ("JPY", "EUR")) \
            and not sym.startswith("EURUSD"):
        out.append("usd_jpy_eur_cross")
    text = " ".join(str(payload.get(k) or "") for k in ("session", "entry", "mechanism",
                                                        "horizon")).lower()
    if re.search(r"\b0[2-8](:\d\d)?\s*(utc|z)\b|asia|tokyo|london open|pre-?london", text):
        out.append("02_09_utc")
    return out


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


def _cb_tone_role(*, budget_s: float, max_llm: int) -> dict[str, Any]:
    """The central-bank tone role (`cb_tone_lab`). One role failing never fails the lab pass."""
    try:
        import cb_tone_lab
        return cb_tone_lab.run(budget_s=budget_s, max_llm=max_llm)
    except Exception as exc:                           # pragma: no cover - defensive
        return {"state": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}


#: THE TRIM CONTRACT the sealed patch `llm_lookahead_gauntlet` must meet, checked by BEHAVIOUR
#: (audit of 538cb964, SF1). The release used to be a substring match on two function names, so
#: a stub defining `llm_born` and `evidence_trim` that did nothing would have freed every held
#: cell UNTRIMMED, with the model's own training window counting as evidence. Now the gauntlet
#: module is imported in a child process and its two functions are run on a fixture:
#:   llm_born(cell) -> True for a cell carrying a `lookahead_guard`, False for one without;
#:   evidence_trim(cell, frame) -> the frame (DatetimeIndex, UTC) with every row before the
#:   cell's own `lookahead_guard.evidence_from` dropped, and unchanged for a non-LLM cell.
#: Anything else -- an import error, a timeout, a wrong answer -- keeps every cell HELD.
GAUNTLET_PROBE = """
import importlib.util, sys
import pandas as pd
path, root = sys.argv[1], sys.argv[2]
for p in (root, root + "/desks/mt5", root + "/desks/mt5/scripts"):
    sys.path.insert(0, p)
try:
    spec = importlib.util.spec_from_file_location("gauntlet_under_probe", path)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
except SyntaxError as exc:
    print("TRIM_CONTRACT_FAIL", "gauntlet does not compile:", exc); sys.exit(2)
except BaseException as exc:
    print("PROBE_UNMEASURED", "gauntlet import:", type(exc).__name__, str(exc)[:160])
    sys.exit(3)
llm = {"cell_id": "probe-llm", "lookahead_guard": {"evidence_from": "2024-01-03"}}
plain = {"cell_id": "probe-plain"}
frame = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]},
                     index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"))
try:
    assert g.llm_born(llm) is True and g.llm_born(plain) is False
    cut = g.evidence_trim(llm, frame.copy())
    assert len(cut) == 3 and cut.index.min() == pd.Timestamp("2024-01-03", tz="UTC")
    assert len(g.evidence_trim(plain, frame.copy())) == 5
except (MemoryError, RecursionError, OSError) as exc:
    print("PROBE_UNMEASURED", type(exc).__name__); sys.exit(3)
except BaseException as exc:
    print("TRIM_CONTRACT_FAIL", type(exc).__name__, str(exc)[:160]); sys.exit(2)
print("TRIM_CONTRACT_OK")
"""
PROBE_TIMEOUT_S = 180.0
UNMEASURED_TAG = "UNMEASURED"
PROBE_CACHE_NAME = "gauntlet_trim_probe.json"


def _probe_gauntlet(path: Path) -> tuple[bool | None, str]:
    """Run GAUNTLET_PROBE against `path` in a child process. Never raises; fails closed.

    THREE ANSWERS, AND ONLY TWO ARE VERDICTS (audit SF2 on 37bb136b4): True (the contract is
    met), False (the gauntlet was read and does not meet it), or None -- the probe could not
    judge (timeout, no interpreter, out of memory, a dependency the gauntlet imports was
    missing). None holds the cells this pass like False, but is never cached, so the next pass
    probes again instead of holding the lab for the life of the gauntlet version."""
    import subprocess
    try:
        proc = subprocess.run([sys.executable, "-c", GAUNTLET_PROBE, str(path), str(ROOT)],
                              capture_output=True, text=True, timeout=PROBE_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError, MemoryError) as exc:
        return None, f"probe {UNMEASURED_TAG}: did not run ({type(exc).__name__})"
    out = proc.stdout or ""
    if proc.returncode == 0 and "TRIM_CONTRACT_OK" in out:
        return True, "trim contract met"
    tail = (out or proc.stderr or "").strip().splitlines()[-1:] or ["no output"]
    if proc.returncode == 2 and "TRIM_CONTRACT_FAIL" in out:
        return False, f"trim contract NOT met: {tail[0][:200]}"
    return None, f"probe {UNMEASURED_TAG} (exit {proc.returncode}): {tail[0][:200]}"


def _collector_role(*, budget_s: float, max_llm: int) -> dict[str, Any]:
    """collector_author's replacement (`collector_lab`): declarative specs, fixed fetcher."""
    try:
        import collector_lab
        return collector_lab.run(budget_s=budget_s, max_llm=max_llm)
    except Exception as exc:                           # pragma: no cover - defensive
        return {"state": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}

