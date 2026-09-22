"""Every mathematical discovery carries its own search burden. This is that arithmetic.

    candidate value = predictive evidence - complexity penalty - multiple-testing burden

THE THREE TERMS, EXACTLY.

  PREDICTIVE EVIDENCE is the HELD-OUT t-statistic of the object's signal against the residual it
  claims to explain, on a time-ordered split with an embargo, with the sample size discounted for
  the overlap of a multi-bar horizon. Never the in-sample fit: `test_mathlab_burden.py` plants a
  beautiful nonsense formula with a near-perfect in-sample fit and this is the term that refuses
  it.

  COMPLEXITY PENALTY is MDL over the expression tree -- node count and free parameters -- entered
  as `LAMBDA_C * sqrt(2 ln(1 + nodes + parameters))`, the same shape as the burden term so the
  two are in the same units and can be read against each other. Simple beats clever at equal
  evidence, which is the whole preference the principal named.

  MULTIPLE-TESTING BURDEN is `sqrt(2 ln(effective trials))`: the expected maximum of that many
  standard normals, which is the deflated-Sharpe intuition written in one line. EFFECTIVE trials
  are the DISTINCT canonical forms the tradition actually evaluated (equivalent formulas
  simplified to the same tree are one hypothesis, not two) PLUS the tradition's lifetime charge,
  so the bar ratchets up as a tradition keeps searching and never resets at midnight.

WHAT THIS IS NOT. It is not a gauntlet and it never certifies anything. It is the SCREEN that
decides which inventions are worth spending the desk's sealed trial budget on; DSR/PBO/SPA, CPCV,
walk-forward, perturbation, cost stress, regime tests, causal falsifiers and the forward clock all
happen downstream in `scripts/external_gauntlet.py` exactly as they do for every other hypothesis.
The desk's canonical trial charge is sealed (gate_spec.yaml) and nothing here changes it; what is
recorded here is the SEARCH SIZE, into the registry's hash-chained trials ledger.

STABILITY, TRANSFER, PERTURBATION, INTERPRETATION, FALSIFICATION are measured beside the value and
reported whether they pass or not. An object that cannot be interpreted is kept as `uninterpreted`
at a lower prior -- never discarded, because a mechanism nobody has thought of is what an
unknown-unknown search is for.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import grammar as G
from .objects import Evidence, Interpretation, MathObject, Panel

#: Weight on the MDL term. Deliberately modest: complexity is a tiebreak between hypotheses with
#: comparable evidence, not a veto on structure. Raising it is a research decision with a ledger
#: line, never a tidy-up.
LAMBDA_C = 0.45
#: The prior an interpreted object is read at, and the prior an uninterpreted one keeps. The value
#: is shifted by log(prior / BASE_PRIOR), so an uninterpreted object competes at a disadvantage
#: rather than not competing.
BASE_PRIOR = 0.5
INTERPRETED_PRIOR = 0.80
UNINTERPRETED_PRIOR = 0.35

#: The normalisation window `mt5desk.family_formula` uses. Evidence is measured on the SAME
#: transform the family will trade, so the number screened is the number executed.
NORM = 240
PERMUTATIONS = 200
#: Circular-block length in bars: long enough to carry a day of H1 autocorrelation into the null.
BLOCK = 24
P_MAX = 0.10
MIN_ERA_STABILITY = 0.6
MIN_TEST_ROWS = 120

UNMEASURED = "UNMEASURED"
COST_SURFACE = Path(__file__).resolve().parents[2] / "data" / "cost_surface.json"


@dataclass
class Burden:
    """The verdict on one object: the three terms, the gates, and what was not measurable."""

    value: float
    evidence_t: float
    complexity_penalty: float
    trials_penalty: float
    prior_shift: float
    effective_trials: int
    passed: bool
    gates: dict[str, Any] = field(default_factory=dict)
    unmeasured: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return {"value": round(self.value, 6), "evidence_t": round(self.evidence_t, 6),
                "complexity_penalty": round(self.complexity_penalty, 6),
                "trials_penalty": round(self.trials_penalty, 6),
                "prior_shift": round(self.prior_shift, 6),
                "effective_trials": self.effective_trials, "passed": self.passed,
                "gates": self.gates, "unmeasured": self.unmeasured,
                "rule": "value = held-out t - MDL penalty - sqrt(2 ln effective trials) "
                        "+ log(prior / 0.5)"}


# ----------------------------------------------------------------------------- the three terms
def complexity_penalty(obj: MathObject) -> float:
    c = obj.complexity
    size = float(c["nodes"]) + float(c["parameters"])
    return LAMBDA_C * math.sqrt(2.0 * math.log(1.0 + max(0.0, size)))


def trials_penalty(effective_trials: int) -> float:
    """The expected maximum of N standard normals: what a search of size N gets for free."""
    return math.sqrt(2.0 * math.log(max(2.0, float(effective_trials))))


def effective_trials(distinct_forms: int, lifetime: int = 0) -> int:
    """Distinct CANONICAL forms evaluated, plus the tradition's lifetime charge.

    Canonical, not raw: `x + 0` and `x` are one hypothesis after `grammar.simplify`, and charging
    two would make the burden a number rather than a measurement. Lifetime, not per-pass: a
    tradition that searches every hour has tested more hypotheses than one that started today,
    and the bar it must clear says so.
    """
    return max(1, int(distinct_forms)) + max(0, int(lifetime))


# --------------------------------------------------------------------------------- statistics
def signal_of(obj: MathObject, panel: Panel) -> np.ndarray:
    """The traded signal: the expression, z-scored on its own trailing window, sided.

    THE SAME TRANSFORM THE FAMILY APPLIES. `mt5desk.family_formula` evaluates the expression,
    z-scores it over `norm` bars and trades the sign when |z| is extreme. Measuring evidence on
    the raw expression instead would screen one quantity and execute another.
    """
    raw = G.evaluate(obj.expression, panel.columns, panel.n)
    z = G.evaluate(["z", "__raw__", NORM], {**panel.columns, "__raw__": raw}, panel.n)
    return z * (1.0 if obj.side_mode == "follow" else -1.0)


def _overlap(panel: Panel) -> int:
    """Bars of overlap in the residual's horizon; 1 when the horizon does not name a number.

    An h-bar forward return measured every bar gives h-fold overlapping samples, and a t-stat
    computed on the raw count is inflated by about sqrt(h). The discount is applied, not noted.
    """
    digits = "".join(ch for ch in str(panel.horizon) if ch.isdigit())
    return max(1, int(digits)) if digits else 1


def _finite(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(a) & np.isfinite(b)
    return a[mask], b[mask]


def ic(signal: np.ndarray, target: np.ndarray) -> float | None:
    """Pearson information coefficient on the finite intersection; None when it is undefined."""
    x, y = _finite(np.asarray(signal, dtype=float), np.asarray(target, dtype=float))
    if x.size < 8 or float(np.std(x)) < 1e-12 or float(np.std(y)) < 1e-12:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def t_of(value: float | None, n: int, overlap: int = 1) -> float | None:
    """The IC as a t-statistic, with the effective sample size discounted for overlap."""
    if value is None or not math.isfinite(value):
        return None
    n_eff = max(3.0, float(n) / max(1.0, float(overlap)))
    denom = math.sqrt(max(1e-9, 1.0 - value * value))
    return float(value * math.sqrt(n_eff - 2.0) / denom)


def circular_block_p(signal: np.ndarray, target: np.ndarray, rng: np.random.Generator,
                     *, permutations: int = PERMUTATIONS, block: int = BLOCK) -> float | None:
    """Two-sided p from a circular-block null: the SIGNAL is rolled, the path is preserved.

    Rolling in blocks keeps the signal's own autocorrelation -- a shuffle would destroy it and
    produce a null far too easy to beat, which is how a serially correlated nothing gets called
    an edge.
    """
    x, y = _finite(np.asarray(signal, dtype=float), np.asarray(target, dtype=float))
    if x.size < max(4 * block, 40):
        return None
    observed = ic(x, y)
    if observed is None:
        return None
    n = x.size
    hits = 0
    for _ in range(int(permutations)):
        shift = int(rng.integers(block, n - block)) if n > 2 * block else int(rng.integers(1, n))
        rolled = np.roll(x, shift)
        null = ic(rolled, y)
        if null is not None and abs(null) >= abs(observed):
            hits += 1
    return float((hits + 1) / (permutations + 1))


def era_stability(signal: np.ndarray, target: np.ndarray, eras: np.ndarray) -> float | None:
    """Fraction of eras whose IC carries the same sign as the whole sample's.

    CROSS-PERIOD INVARIANCE IS A PREFERENCE THE PRINCIPAL NAMED. A relation that only holds in one
    era is a description of that era.
    """
    full = ic(signal, target)
    if full is None or full == 0.0:
        return None
    agree, seen = 0, 0
    for era in np.unique(eras):
        mask = eras == era
        if int(mask.sum()) < 30:
            continue
        local = ic(signal[mask], target[mask])
        if local is None:
            continue
        seen += 1
        agree += int(np.sign(local) == np.sign(full))
    return None if seen < 2 else float(agree / seen)


def cross_market_transfer(obj: MathObject, peers: list[Panel]) -> tuple[float | None, str | None]:
    """The SAME expression on a DIFFERENT instrument. Transfer is evidence the law is a law."""
    for peer in peers:
        if peer.target == obj.target:
            continue
        missing = [v for v in G.variables_in(obj.expression) if v not in peer.columns]
        if missing:
            continue
        value = ic(signal_of(obj, peer), peer.epsilon)
        if value is not None:
            return value, peer.target
    return None, None


def perturbation(obj: MathObject, panel: Panel, test: np.ndarray) -> float | None:
    """Smallest |t| over neighbouring window choices. A cliff edge is not a discovery."""
    windows = _window_sites(obj.expression)
    if not windows or test.size < MIN_TEST_ROWS:
        return None
    overlap = _overlap(panel)
    worst: float | None = None
    for index in windows[:4]:
        for delta in (-1, 1):
            tree = _shift_window(obj.expression, index, delta, [0])
            if tree is None:
                continue
            probe = MathObject(kind=obj.kind, tradition=obj.tradition, expression=tree,
                               target=obj.target, horizon=obj.horizon, side_mode=obj.side_mode)
            value = t_of(ic(signal_of(probe, panel)[test], panel.epsilon[test]), test.size,
                         overlap)
            if value is None:
                continue
            worst = abs(value) if worst is None else min(worst, abs(value))
    return worst


def _window_sites(node: Any, counter: list[int] | None = None) -> list[int]:
    """Indices (in a fixed pre-order walk) of every windowed node."""
    counter = counter if counter is not None else [0]
    out: list[int] = []
    if not isinstance(node, (list, tuple)) or not node:
        return out
    here = counter[0]
    counter[0] += 1
    if str(node[0]) in G.WINDOWED:
        out.append(here)
    for child in node[1:]:
        if isinstance(child, (list, tuple)):
            out.extend(_window_sites(child, counter))
    return out


def _shift_window(node: Any, index: int, delta: int, counter: list[int]) -> Any | None:
    if not isinstance(node, (list, tuple)) or not node:
        return node
    here = counter[0]
    counter[0] += 1
    out: list[Any] = [node[0]]
    changed = False
    if here == index and str(node[0]) in G.WINDOWED and isinstance(node[2], int):
        pos = G.WINDOWS.index(node[2]) if node[2] in G.WINDOWS else None
        if pos is None:
            return None
        new = pos + delta
        if not 0 <= new < len(G.WINDOWS):
            return None
        child = node[1]
        if isinstance(child, (list, tuple)):
            counter[0] += _count(child)
        return [node[0], child, int(G.WINDOWS[new])]
    for child in node[1:]:
        if isinstance(child, (list, tuple)):
            replaced = _shift_window(child, index, delta, counter)
            if replaced is None:
                return None
            changed = changed or replaced is not child
            out.append(replaced)
        else:
            out.append(child)
    return out


def _count(node: Any) -> int:
    if not isinstance(node, (list, tuple)) or not node:
        return 0
    return 1 + sum(_count(c) for c in node[1:] if isinstance(c, (list, tuple)))


# ------------------------------------------------------------------------- economic reading
def _contracts() -> dict[str, Any]:
    """The desk's mechanism ontology, or {} when it is not importable from here."""
    try:
        from research.transformation_miners import CONTRACTS
    except Exception:
        try:
            from transformation_miners import CONTRACTS  # type: ignore[no-redef]
        except Exception:
            return {}
    return dict(CONTRACTS)


def interpret(obj: MathObject, panel: Panel) -> Interpretation:
    """Map the object's variables and statement onto an actor and a mechanism, or say it cannot.

    The vocabulary is the desk's own (`transformation_miners.CONTRACTS`, whose mechanism ids are
    `axis_registry.MECHANISM_ACTOR`'s), so an interpreted object lands on the SAME grid coordinate
    the breadth registry already keeps rather than opening a second ontology.
    """
    text = " ".join([obj.statement, obj.canonical, obj.tradition,
                     " ".join(v.dataset for v in obj.variables),
                     " ".join(v.source for v in obj.variables)]).lower()
    best: tuple[int, Any] = (0, None)
    for contract in _contracts().values():
        hits = [k for k in getattr(contract, "keywords", ()) if k and k.lower() in text]
        if len(hits) > best[0]:
            best = (len(hits), (contract, hits))
    if best[0] and best[1] is not None:
        contract, hits = best[1]
        return Interpretation(mechanism_id=str(contract.mechanism_id), actor=str(contract.actor),
                              rationale=str(contract.rationale), falsifier=str(contract.falsifier),
                              matched_on=list(hits), status="interpreted",
                              prior=INTERPRETED_PRIOR)
    return Interpretation(
        mechanism_id="", actor="",
        rationale=(f"UNINTERPRETED: the {obj.tradition} object over "
                   f"{sorted(G.variables_in(obj.expression))} matches no registered mechanism "
                   f"contract for {panel.target}. Kept at a lower prior, never discarded -- an "
                   f"unknown-unknown search that refuses unnamed mechanisms only confirms the "
                   f"ontology it started with."),
        falsifier=("the held-out relation does not survive the circular-block null once the "
                   "mechanism is named and its actor's flow is controlled for"),
        matched_on=[], status="uninterpreted", prior=UNINTERPRETED_PRIOR)


def graph_identity(obj: MathObject, family: str, params: dict[str, Any]) -> str:
    """The hypothesis graph's node id for the cell this object would become, or "" if absent."""
    try:
        from libs.research.hypothesis_graph import node_id
    except Exception:
        return ""
    try:
        return str(node_id(obj.target, family, params))
    except Exception:
        return ""


# ----------------------------------------------------------------------------- cost stress
def cost_fraction(symbol: str, path: Path | None = None) -> tuple[float | None, str]:
    """Median one-way cost IN PRICE UNITS for the symbol, from the desk's measured cost surface.

    THE SURFACE IS IN POINTS. `cost_surface.py` writes the hourly `p50` spread as a count of
    `tick_size` units (EURUSD: p50 12.0 at tick 1e-5 = 0.00012), and reading it as a fraction of
    price -- which is what this function did for one afternoon -- priced a 1.2 pip spread as a
    1200% round trip and refused every object on the desk's most liquid pair. Points times tick
    size is price; the caller divides by the price it has.
    """
    target = path or COST_SURFACE
    try:
        doc = json.loads(target.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{UNMEASURED}: cost surface unreadable ({type(exc).__name__}) at {target}"
    row = (doc.get("symbols") or {}).get(symbol)
    if not isinstance(row, dict):
        built = doc.get("built_at")
        return None, f"{UNMEASURED}: {symbol} is not in the cost surface built {built}"
    tick = row.get("tick_size")
    if not isinstance(tick, (int, float)) or tick <= 0:
        return None, f"{UNMEASURED}: {symbol} carries no tick_size in the cost surface"
    values = [float(h["p50"]) for h in (row.get("hours") or {}).values()
              if isinstance(h, dict) and isinstance(h.get("p50"), (int, float))]
    if not values:
        return None, f"{UNMEASURED}: {symbol} has no hourly p50 spread in the cost surface"
    return float(np.median(values)) * float(tick), "MEASURED"


def cost_stress(obj: MathObject, panel: Panel, ic_value: float | None,
                path: Path | None = None) -> dict[str, Any]:
    """Does a one-sigma move of this signal pay for the round trip it must be captured through?

    Both sides are FRACTIONS OF PRICE: the residual is a forward log-return residual, so a
    one-sigma move of it is a return, and the spread in price units is divided by the panel's
    own median close.
    """
    cost_price, status = cost_fraction(panel.target, path)
    with G.quiet():
        sd = float(np.nanstd(panel.epsilon)) if panel.n else 0.0
        close = panel.columns.get("close")
        price = float(np.nanmedian(close)) if close is not None and close.size else None
    gross = abs(ic_value) * sd if ic_value is not None else None
    if cost_price is None or gross is None or not price or not math.isfinite(price):
        why = status if cost_price is None else (
            "no held-out IC" if gross is None else "the panel carries no close to price against")
        return {"status": UNMEASURED, "why": why, "one_way_cost_price": cost_price,
                "gross_edge": gross,
                "measured_by": "desks/mt5/data/cost_surface.json rebuilt for this symbol, and a "
                               "panel with a close column"}
    frac = cost_price / price
    net = gross - 2.0 * frac
    return {"status": "MEASURED", "one_way_cost_price": round(cost_price, 10),
            "one_way_cost_frac": round(frac, 10), "price": round(price, 8),
            "gross_edge": round(gross, 8), "net_edge": round(net, 8), "survives": bool(net > 0),
            "rule": "a one-sigma signal move (a return) must clear a round trip at the median "
                    "hourly spread, points x tick_size / price"}


# --------------------------------------------------------------------------------- the judge
def judge(obj: MathObject, panel: Panel, *, distinct_forms: int, lifetime_trials: int = 0,
          rng: np.random.Generator | None = None, peers: list[Panel] | None = None,
          cost_path: Path | None = None, permutations: int = PERMUTATIONS) -> Burden:
    """Fill the object's evidence block and return its burden verdict. Mutates `obj`."""
    rng = rng or np.random.default_rng(20260917)
    train, test = panel.split()
    overlap = _overlap(panel)
    signal = signal_of(obj, panel)
    unmeasured: list[str] = []

    ic_in = ic(signal[train], panel.epsilon[train]) if train.size else None
    ic_out = ic(signal[test], panel.epsilon[test]) if test.size else None
    t_out = t_of(ic_out, int(test.size), overlap)
    if test.size < MIN_TEST_ROWS:
        unmeasured.append(f"held_out: only {int(test.size)} test rows, fewer than the named "
                          f"minimum {MIN_TEST_ROWS}; a longer panel would measure it")
    p_perm = (circular_block_p(signal[test], panel.epsilon[test], rng, permutations=permutations)
              if test.size else None)
    if p_perm is None:
        unmeasured.append("permutation_null: fewer rows than 4 blocks of 24 bars")
    stability = era_stability(signal, panel.epsilon, panel.eras())
    if stability is None:
        unmeasured.append("era_stability: fewer than two eras carry 30 usable rows")
    transfer_ic, transfer_symbol = cross_market_transfer(obj, peers or [])
    if transfer_ic is None:
        unmeasured.append("cross_market_transfer: no peer panel carries every variable this "
                          "object reads")
    perturb = perturbation(obj, panel, test)
    if perturb is None:
        unmeasured.append("perturbation: the expression has no window argument to jitter")
    costs = cost_stress(obj, panel, ic_out, cost_path)
    if costs.get("status") == UNMEASURED:
        unmeasured.append(f"cost_stress: {costs.get('why')}")

    obj.interpretation = interpret(obj, panel)
    obj.evidence = Evidence(
        n_train=int(train.size), n_test=int(test.size),
        ic_in_sample=None if ic_in is None else round(ic_in, 6),
        ic_held_out=None if ic_out is None else round(ic_out, 6),
        t_held_out=None if t_out is None else round(t_out, 4),
        permutation_p=None if p_perm is None else round(p_perm, 5),
        era_stability=None if stability is None else round(stability, 4),
        transfer_ic=None if transfer_ic is None else round(transfer_ic, 6),
        transfer_symbol=transfer_symbol,
        perturbation_min_t=None if perturb is None else round(perturb, 4),
        cost_stress=costs, diagnostics=dict(obj.diagnostics), unmeasured=list(unmeasured))

    n_eff = effective_trials(distinct_forms, lifetime_trials)
    evidence_t = float(t_out) if t_out is not None else 0.0
    penalty_c = complexity_penalty(obj)
    penalty_t = trials_penalty(n_eff)
    prior_shift = math.log(max(1e-6, obj.interpretation.prior) / BASE_PRIOR)
    value = evidence_t - penalty_c - penalty_t + prior_shift

    gates = {
        "value_positive": bool(value > 0.0),
        "held_out_sign_agrees": bool(ic_in is not None and ic_out is not None
                                     and np.sign(ic_in) == np.sign(ic_out) and ic_out != 0.0),
        "permutation": (p_perm is not None and p_perm <= P_MAX) if p_perm is not None
        else UNMEASURED,
        "era_stability": (stability is not None and stability >= MIN_ERA_STABILITY)
        if stability is not None else UNMEASURED,
        "cost_stress": bool(costs.get("survives")) if costs.get("status") == "MEASURED"
        else UNMEASURED,
        "enough_test_rows": bool(test.size >= MIN_TEST_ROWS),
    }
    passed = all(v is True for k, v in gates.items() if v is not UNMEASURED) \
        and gates["value_positive"] and gates["held_out_sign_agrees"] \
        and gates["enough_test_rows"]

    burden = Burden(value=value, evidence_t=evidence_t, complexity_penalty=penalty_c,
                    trials_penalty=penalty_t, prior_shift=prior_shift, effective_trials=n_eff,
                    passed=bool(passed), gates=gates, unmeasured=list(unmeasured))
    obj.value = round(value, 6)
    obj.passed = bool(passed)
    obj.burden = burden.to_row()
    return burden


def record_trials(tradition: str, *, distinct_forms: int, evaluated: int, target: str,
                  passed: int, conn: Any = None) -> dict[str, Any]:
    """Charge this tradition's search size to the desk's HASH-CHAINED trials ledger.

    The registry's `trials_ledger` is append-only and refuses later edits, which is the property
    that makes a trial count evidence rather than a claim. Never fatal: a ledger that can take
    down the search it measures would be removed within a week, correctly.
    """
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"registry unimportable: {type(exc).__name__}"}
    try:
        row_hash = reg.record_trial(
            f"mathlab:{tradition}", family="formula", method=f"mathlab:{tradition}",
            params={"distinct_canonical_forms": int(distinct_forms),
                    "expressions_evaluated": int(evaluated), "survivors": int(passed),
                    "rule": "effective trials are DISTINCT canonical forms; equivalent "
                            "expressions simplify to one tree and charge one trial"},
            symbol=target, conn=conn)
        return {"status": "RECORDED", "row_hash": row_hash,
                "distinct_forms": int(distinct_forms), "evaluated": int(evaluated)}
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"record_trial failed: {type(exc).__name__}"}
