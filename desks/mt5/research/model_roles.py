#!/usr/bin/env python3
"""THE DECISION ROLE OF EVERY MODEL FAMILY -- what each one is ALLOWED to change, and nothing more.

WHY A REGISTRY OF ROLES AND NOT A PILE OF OVERLAYS. The desk grew a dozen model families -- an
HMM regime engine, a hierarchical posterior on each edge, a drift monitor, a macro kernel, a cost
surface, a capacity ceiling, leg factors -- and each one reached the allocator through its own
private door, decided by whoever wired it. Nothing said what a model was FOR. So nothing stopped a
volatility model from tilting a mean, a regime classifier from being read as a direction call, or
two views of the same tape from being counted as two votes. Each of those is a way to manufacture
conviction the evidence never supplied, and none of them looks wrong from inside the arithmetic.

This module states it once, in data. A family's ROLES are a closed set (`Role`); a family whose
roles exclude DIRECTION_MEAN cannot move a mean, however confident it sounds. Some families only
change SIZING (VOLATILITY_SCALE, LIQUIDITY_CAP, COST) or UNCERTAINTY (UNCERTAINTY_WIDTH,
DECAY_HAZARD); they never say which way. That is the separation `forecast_contract` makes between
forecasting and sizing, carried one level down: between saying WHERE and saying HOW SURE / HOW BIG.

FOUR PROPERTIES, each a pure function so it can be tested without a filesystem or a solve:

  (a) `combine` -- beliefs about one subject at one horizon are POOLED, never voted. Precision
      weighting is the start; then DISAGREEMENT INFLATES the pooled variance (a Birge ratio on
      Cochran's Q), so two confident models that contradict each other produce LESS confidence
      than either alone, not a confident average. And CORRELATED SOURCES ARE NOT INDEPENDENT
      VOTES: the pooled variance is a'Σa under the declared (or measured) source correlation, so
      two copies of one signal pool to exactly one signal's variance, and the effective number of
      sources is reported beside the raw count.
  (b) `update` -- an observation carries a FINGERPRINT (model, subject, as-of of its inputs,
      value digest). A fingerprint already consumed is a no-op. The same bar re-published an hour
      later at a new `at` is the same evidence, and counting it twice is how a posterior becomes
      certain of something it saw once.
  (c) `staleness_clamp` -- a CRITICAL input past its staleness budget may only reduce or hold
      risk, never add it. The clamp is a HOLD (max heat multiplier 1.0, no new adds), not a cut:
      growth governance forbids shrinking the book by fiat, and stale evidence is a reason not to
      ADD, never by itself a reason to subtract. Absent is stale (L1.28a): an input with no as-of
      is not fresh, it is unmeasured.
  (d) `enforce_role` -- a model may speak only in the roles its family declares. Asked to move a
      mean, a VOLATILITY_SCALE model is refused with the reason, never silently down-weighted.

THE INVENTORY IS RECORDED HERE TOO (`FamilySpec.module`, `reaches_allocator`), measured by grep on
2026-10-06, because a role for a model that does not exist is a claim the desk cannot cash
(L1.49). A family with `module=""` is a DECLARED SLOT, not a running organ: its role is fixed now
so that whoever builds it inherits the boundary instead of inventing one.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    """THE CLOSED SET OF THINGS A MODEL MAY CHANGE. Adding a member is a governance act."""

    #: The expected value of a sleeve's return -- the ONLY role that says which way.
    DIRECTION_MEAN = "DIRECTION_MEAN"
    #: Scales size inversely to forecast volatility; never signs the bet.
    VOLATILITY_SCALE = "VOLATILITY_SCALE"
    #: Widens (or, with evidence, narrows) the variance around a mean it does not own.
    UNCERTAINTY_WIDTH = "UNCERTAINTY_WIDTH"
    #: Probabilities over regimes -- reweights WHICH history the worlds are drawn from.
    REGIME_PROBS = "REGIME_PROBS"
    #: Correlation / co-movement between sleeves; changes concentration, not means.
    DEPENDENCE = "DEPENDENCE"
    #: Round-trip execution cost charged against a move.
    COST = "COST"
    #: An upper bound on size from what the venue can absorb.
    LIQUIDITY_CAP = "LIQUIDITY_CAP"
    #: The probability an edge has decayed or a regime is about to end.
    DECAY_HAZARD = "DECAY_HAZARD"
    #: When this input is stale, its staleness forbids adding risk. Held by every CRITICAL family.
    VETO_STALENESS = "VETO_STALENESS"


HOUR = 3600.0
DAY = 86400.0


@dataclass(frozen=True)
class FamilySpec:
    """One model family's contract with the allocator."""

    family: str
    roles: frozenset[Role]
    #: The horizon its output is ABOUT, in seconds. Pooling only ever happens within one horizon.
    horizon_s: float
    #: How old its inputs may be before it is stale. Measured from the as-of of its INPUTS, not
    #: from when the report was written -- a fresh file over a week-old fit is a week old.
    staleness_budget_s: float
    #: Critical: stale -> the book may not ADD. Must coincide with VETO_STALENESS in `roles`.
    critical: bool
    #: Whether its beliefs are formed on features. A family that uses none publishes with no
    #: feature list and no availability stamps; one that does must stamp every feature.
    uses_features: bool
    #: Where it lives in the repo ("" = declared slot, not built).
    module: str
    #: How (or whether) it reaches pf_allocator / robust_elog today.
    reaches_allocator: str
    why: str = ""

    def may(self, role: Role | str) -> bool:
        return str(role) in {str(r) for r in self.roles}


def _f(*roles: Role) -> frozenset[Role]:
    return frozenset(roles)


R = Role
#: THE REGISTRY. Roles are chosen by one rule: a family may DIRECT only if its output is itself a
#: scored claim about a sleeve's return. Everything that describes the ENVIRONMENT (volatility,
#: regime, liquidity, cost, dependence, crowding) changes size or uncertainty, never sign -- a
#: high-volatility regime is a reason to be smaller, not a reason to be short.
FAMILIES: dict[str, FamilySpec] = {s.family: s for s in (
    FamilySpec("hmm_regime", _f(R.REGIME_PROBS), 1 * DAY, 2 * DAY, False, True,
               "libs/regime/engine.py, libs/regime/hmm.py, libs/regime/transitions.py",
               "YES: pf_allocator.regime_state -> regime mixture of the world population",
               "Probabilities over regimes reweight which days the worlds sample; the regime "
               "mix is bounded [REGIME_MIN_SHARE, REGIME_MAX_SHARE] so it cannot direct alone."),
    FamilySpec("hsmm_regime", _f(R.REGIME_PROBS, R.DECAY_HAZARD), 1 * DAY, 2 * DAY, False, True,
               "",
               "NO: no HSMM exists; libs/regime/transitions.py's age-conditioned hazard is the "
               "nearest organ and is part of hmm_regime",
               "A duration model's extra output is the hazard of leaving the regime by age."),
    FamilySpec("bayesian_edge", _f(R.DIRECTION_MEAN, R.UNCERTAINTY_WIDTH, R.VETO_STALENESS),
               1 * DAY, 2 * DAY, True, True,
               "pf_allocator._posterior_mu, research/posterior_alpha (POSTERIOR_ALPHA.json), "
               "libs/portfolio/posterior_growth.py",
               "YES: _posterior_mu is the sleeve mean; POSTERIOR_ALPHA enters as heat-neutral "
               "tilts",
               "The one family whose output is a scored claim about a sleeve's return."),
    FamilySpec("garch_vol", _f(R.VOLATILITY_SCALE, R.UNCERTAINTY_WIDTH, R.VETO_STALENESS),
               1 * DAY, 2 * DAY, True, True,
               "libs/research/volatility_signals.py (EWMA/Garman-Klass, no GARCH fit)",
               "NO: no GARCH model reaches the allocator; volatility_signals feeds research only",
               "Volatility sizes a bet; it never signs one."),
    FamilySpec("change_point", _f(R.DECAY_HAZARD, R.UNCERTAINTY_WIDTH, R.VETO_STALENESS),
               1 * DAY, 1 * DAY, True, True,
               "desks/mt5/research/drift_monitor.py (DRIFT.json), libs/research/dist_shift.py",
               "YES: read_drift -> crisis_share_from_drift (crisis worlds) and hazard_by_sleeve "
               "(per-sleeve decay)",
               "A break says the past is less informative, not which way the future goes."),
    FamilySpec("macro_state", _f(R.REGIME_PROBS, R.UNCERTAINTY_WIDTH), 1 * DAY, 3 * DAY, False,
               True, "libs/portfolio/macro_state.py, desks/mt5/mt5desk/macro_regime.py",
               "YES: _MacroContext kernel weights reweight history days inside _posterior_mu",
               "It supplies WEIGHTS over history; the mean those weights produce is owned by "
               "bayesian_edge, which is where its effect on direction is scored."),
    FamilySpec("alt_data", _f(R.UNCERTAINTY_WIDTH), 1 * DAY, 7 * DAY, False, True,
               "desks/mt5/research/alt_proxies.py, libs/research/asia_alt_digest.py",
               "NO: research hypotheses only",
               "An alt-data DIRECTION claim enters as a certified sleeve's own edge, never as an "
               "overlay on someone else's mean."),
    FamilySpec("flows", _f(R.UNCERTAINTY_WIDTH, R.LIQUIDITY_CAP), 1 * HOUR, 4 * HOUR, False,
               True, "desks/mt5/mt5desk/microstructure.py, desks/mt5/recorders/tape_features.py",
               "NO: hypothesis families only",
               "Order flow says how much the venue can take and how noisy the next hour is."),
    FamilySpec("positioning", _f(R.UNCERTAINTY_WIDTH, R.DECAY_HAZARD), 7 * DAY, 10 * DAY, False,
               True, "libs/data/cot_source.py, desks/mt5/fetch_tff.py",
               "NO: hypothesis families only (crowding is info-only in _regime_hierarchy_report)",
               "Crowding raises the hazard of an unwind; it does not say the unwind's sign. "
               "COT is published Friday for Tuesday, hence a 10-day budget."),
    FamilySpec("liquidity", _f(R.LIQUIDITY_CAP, R.VETO_STALENESS), 1 * DAY, 2 * DAY, True, True,
               "research/capacity.py (CAPACITY.json), libs/regime/liquidity_state.py",
               "YES: _capacity_ceiling -> survival envelope capacity clause; liquidity_state is "
               "information only",
               "A cap on size from what the venue absorbs."),
    FamilySpec("execution_cost", _f(R.COST, R.VETO_STALENESS), 1 * DAY, 3 * DAY, True, True,
               "libs/portfolio/execution_cost.py, data/cost_surface.json",
               "YES: cost_surface priced per sleeve; TURNOVER_COST_R in the no-trade filter",
               "Under-charged cost on a stale surface is risk added for free."),
    FamilySpec("dependence", _f(R.DEPENDENCE, R.VETO_STALENESS), 1 * DAY, 2 * DAY, True, True,
               "libs/portfolio/leg_factors.py, latent_factors.py, conditional_covariance.py",
               "YES: leg factor loadings -> _corr_abs; crisis calibration of the covariance",
               "A stale correlation understates concentration exactly when it matters."),
)}

#: DECLARED SOURCE CORRELATION between families, used when no measured correlation is supplied.
#: Not a tuning knob: each pair is two views of overlapping evidence, and the number says how
#: much of one is already in the other. Pairs absent here are treated as independent (0.0), which
#: is the generous direction -- so a pair is added here the day two families are found to share
#: inputs, and a measured matrix passed to `combine` always outranks this table.
DECLARED_SOURCE_RHO: dict[frozenset[str], float] = {
    frozenset({"hmm_regime", "hsmm_regime"}): 0.85,   # same returns, same latent states
    frozenset({"hmm_regime", "macro_state"}): 0.40,
    frozenset({"garch_vol", "change_point"}): 0.30,   # a vol burst reads as a break
    frozenset({"flows", "positioning"}): 0.50,        # two lags of the same crowd
    frozenset({"flows", "liquidity"}): 0.50,
}


def registry_defects() -> list[str]:
    """The registry checking itself: critical <=> VETO_STALENESS, budgets positive."""
    out = []
    for name, s in FAMILIES.items():
        if s.critical != s.may(Role.VETO_STALENESS):
            out.append(f"{name}: critical={s.critical} but VETO_STALENESS "
                       f"{'absent' if s.critical else 'present'} -- one fact, stated twice")
        if not (s.horizon_s > 0 and s.staleness_budget_s > 0):
            out.append(f"{name}: horizon and staleness budget must be positive")
        if not s.roles:
            out.append(f"{name}: a family with no role has no business reaching the allocator")
    return out


def spec(family: str) -> FamilySpec | None:
    return FAMILIES.get(str(family or ""))


# --------------------------------------------------------------------------- (d) role enforcement
class RoleViolation(ValueError):
    """A model asked to change something its family's role does not cover."""


def enforce_role(family: str, role: Role | str) -> None:
    """Raise unless `family` may speak in `role`. Unknown family is a violation, not a pass."""
    s = spec(family)
    if s is None:
        raise RoleViolation(f"family {family!r} is not registered in model_roles.FAMILIES; an "
                            f"unregistered model has no declared role and may change nothing")
    if not s.may(role):
        raise RoleViolation(f"{family} may change {sorted(str(r) for r in s.roles)}, not "
                            f"{role}: a model whose role excludes it cannot move it")


# --------------------------------------------------------------------------- (b) fingerprints
@dataclass(frozen=True)
class Estimate:
    """One model's numeric belief about one quantity, as the pooling functions read it.

    Deliberately separate from `forecast_contract.Belief`: that is the PUBLICATION contract
    (scoreable, auditable), this is the arithmetic. `inputs_as_of` is the as-of of the data the
    estimate was formed on, which is what staleness and fingerprints are measured from.
    """

    model_id: str
    family: str
    subject: str
    horizon_s: float
    role: str
    mean: float
    variance: float
    inputs_as_of: str
    confidence: float = 1.0

    def fingerprint(self) -> str:
        return fingerprint(self.model_id, self.subject, self.inputs_as_of,
                           {"role": str(self.role), "horizon_s": float(self.horizon_s),
                            "mean": self.mean, "variance": self.variance})


def _canon(x: Any) -> Any:
    # Floats rounded to 12 significant digits so a re-serialised identical number is identical.
    if isinstance(x, float):
        return float(f"{x:.12g}") if math.isfinite(x) else str(x)
    if isinstance(x, Mapping):
        return {str(k): _canon(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    return x


def fingerprint(model_id: str, subject: str, inputs_as_of: str, value: Any) -> str:
    """(model, subject, as-of of the inputs, value digest) -> one stable id.

    `at` (publication time) is LEFT OUT ON PURPOSE. The failure this exists for is the same
    observation re-published on the next clock with a new `at`; including `at` would make every
    re-publication look new, which is exactly the double-count.
    """
    blob = json.dumps({"m": str(model_id), "s": str(subject), "asof": str(inputs_as_of),
                       "v": _canon(value)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class BeliefState:
    """The latest estimate per (model, subject, horizon, role), plus every fingerprint consumed.

    ONE MODEL, ONE VOTE. A new estimate REPLACES that model's previous one; it never
    accumulates on top of it. Accumulation (posterior precision += observation precision) is the
    textbook conjugate update and on this desk it is the double-count: models re-publish on
    every clock, and each re-publication would add precision the evidence never had.
    """

    latest: Mapping[tuple[str, str, float, str], Estimate] = field(default_factory=dict)
    consumed: frozenset[str] = frozenset()

    def estimates(self, subject: str, horizon_s: float, role: Role | str) -> list[Estimate]:
        return [e for (m, s, h, r), e in sorted(self.latest.items())
                if s == subject and h == float(horizon_s) and r == str(role)]

    def to_json(self) -> dict[str, Any]:
        return {"consumed": sorted(self.consumed),
                "latest": [e.__dict__ for e in self.latest.values()]}

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> BeliefState:
        ests = [Estimate(**e) for e in doc.get("latest") or ()]
        return cls({(e.model_id, e.subject, float(e.horizon_s), str(e.role)): e for e in ests},
                   frozenset(doc.get("consumed") or ()))


def update(state: BeliefState, est: Estimate) -> tuple[BeliefState, bool]:
    """Fold one estimate in. Returns (new_state, applied). A consumed fingerprint is a no-op.

    The no-op returns the SAME state object, so a caller can tell "nothing happened" by identity
    as well as by the flag. Role is enforced here too: an estimate in a role its family does not
    hold raises, because storing it would let `combine` pool it later.
    """
    enforce_role(est.family, est.role)
    fp = est.fingerprint()
    if fp in state.consumed:
        return state, False
    key = (est.model_id, est.subject, float(est.horizon_s), str(est.role))
    latest = dict(state.latest)
    latest[key] = est
    return BeliefState(latest, state.consumed | {fp}), True


# --------------------------------------------------------------------------- (a) combine
@dataclass(frozen=True)
class Pooled:
    subject: str
    horizon_s: float
    role: str
    mean: float | None
    variance: float | None
    confidence: float
    n_sources: int
    n_effective: float
    disagreement_q: float
    inflation: float
    excluded: tuple[tuple[str, str], ...] = ()
    why: str = ""


def source_rho(a: Estimate, b: Estimate,
               measured: Mapping[frozenset[str], float] | None = None) -> float:
    """Correlation between two sources. Same model -> 1. Measured outranks declared.

    Same FAMILY with no declared pair is treated as 0.5, not 0: two fits of one family on
    overlapping data are the commonest way two votes turn out to be one.
    """
    if a.model_id == b.model_id:
        return 1.0
    for key in (frozenset({a.model_id, b.model_id}), frozenset({a.family, b.family})):
        if measured and key in measured:
            return float(measured[key])
    fam = frozenset({a.family, b.family})
    if fam in DECLARED_SOURCE_RHO:
        return DECLARED_SOURCE_RHO[fam]
    return 0.5 if a.family == b.family else 0.0


def combine(estimates: Sequence[Estimate], role: Role | str = Role.DIRECTION_MEAN, *,
            measured_rho: Mapping[frozenset[str], float] | None = None) -> Pooled:
    """Pool estimates of one quantity. Disagreement shrinks confidence; correlation is not votes.

    1. ROLE: an estimate whose family does not hold `role`, or that speaks in another role, is
       EXCLUDED with its reason -- it cannot move the pooled quantity at all.
    2. WEIGHTS: precision discounted by shared correlation, w_i = (1/var_i) / sum_j rho_ij,
       normalised to a_i -- so a copy of a source splits that source's weight, never doubles it.
    3. CORRELATION: pooled variance = a' S a with S_ij = rho_ij sd_i sd_j. Independent sources
       give the familiar 1/sum(w); two identical sources give one source's variance, not half.
       n_effective = 1 / (a' R a) is reported so a reader sees how many votes there really were.
    4. DISAGREEMENT: Cochran's Q = Σ w_i (μ_i - μ)², inflation φ = max(1, Q / max(n_eff-1, 1)).
       The pooled variance is multiplied by φ and the confidence divided by it. φ never goes
       below 1: agreement does not earn MORE certainty than the precisions already gave, because
       agreeing models that share inputs agree for free.
    Refuses (raises ValueError) to pool across subjects or horizons -- that is not pooling, it is
    the unequal comparison the league exists to refuse.
    """
    role_s = str(role)
    if not estimates:
        return Pooled("", 0.0, role_s, None, None, 0.0, 0, 0.0, 0.0, 1.0,
                      why="no estimates: UNMEASURED, not a neutral prior")
    subjects = {e.subject for e in estimates}
    horizons = {float(e.horizon_s) for e in estimates}
    if len(subjects) > 1 or len(horizons) > 1:
        raise ValueError(f"combine pools ONE subject at ONE horizon; got "
                         f"subjects={sorted(subjects)} horizons={sorted(horizons)}")
    subject, horizon = next(iter(subjects)), next(iter(horizons))
    used: list[Estimate] = []
    excluded: list[tuple[str, str]] = []
    for e in estimates:
        if str(e.role) != role_s:
            excluded.append((e.model_id, f"speaks in {e.role}, not {role_s}"))
            continue
        try:
            enforce_role(e.family, role_s)
        except RoleViolation as exc:
            excluded.append((e.model_id, str(exc)))
            continue
        if not (math.isfinite(e.mean) and math.isfinite(e.variance) and e.variance > 0):
            excluded.append((e.model_id, "non-finite mean or non-positive variance"))
            continue
        used.append(e)
    if not used:
        return Pooled(subject, horizon, role_s, None, None, 0.0, 0, 0.0, 0.0, 1.0,
                      tuple(excluded), "every estimate excluded: UNMEASURED")
    n = len(used)
    w = [1.0 / e.variance for e in used]
    sd = [math.sqrt(e.variance) for e in used]
    rho = [[source_rho(used[i], used[j], measured_rho) if i != j else 1.0 for j in range(n)]
           for i in range(n)]
    # CORRELATION-DISCOUNTED WEIGHTS (2026-10-07, found by forecast_scoring's leave-one-source-
    # out test). Plain precision weights counted correlation in the VARIANCE but not in the MEAN:
    # a verbatim copy of a source doubled that source's pull on the pooled mean, so a twin was
    # still two votes exactly where it mattered. Each precision is now divided by the correlation
    # mass the source shares with the pool, sum_j rho_ij (rho_ii = 1): independent sources keep
    # plain precision weights; k identical copies share ONE source's weight between them. Unlike
    # GLS weights (Sigma^-1 1) these are never negative and never blow up on a singular matrix --
    # a pooled mean that shorts one model to buy its twin is not a belief anyone stated.
    w = [w[i] / sum(max(0.0, rho[i][j]) for j in range(n)) for i in range(n)]
    sw = sum(w)
    a = [x / sw for x in w]
    mu = sum(ai * e.mean for ai, e in zip(a, used, strict=True))
    var = sum(a[i] * a[j] * rho[i][j] * sd[i] * sd[j] for i in range(n) for j in range(n))
    ara = sum(a[i] * a[j] * rho[i][j] for i in range(n) for j in range(n))
    n_eff = 1.0 / ara if ara > 0 else float(n)
    q = sum(wi * (e.mean - mu) ** 2 for wi, e in zip(w, used, strict=True))
    phi = max(1.0, q / max(n_eff - 1.0, 1.0))
    base_conf = sum(ai * min(1.0, max(0.0, e.confidence)) for ai, e in zip(a, used, strict=True))
    return Pooled(subject, horizon, role_s, mu, var * phi, base_conf / phi, n, n_eff, q, phi,
                  tuple(excluded),
                  f"{n} source(s), {n_eff:.2f} effective; disagreement inflation x{phi:.2f}")


# --------------------------------------------------------------------------- (c) staleness
def _parse(ts: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Clamp:
    """What the allocator may do given the freshness of its critical inputs.

    `max_heat_multiplier` is None when nothing is stale (no clamp), else <= 1.0 relative to the
    HELD book. `allow_adds` False means no sleeve may rise above its held fraction and no new
    sleeve may open. It never forces a cut: reducing is still the solve's choice.
    """

    max_heat_multiplier: float | None
    allow_adds: bool
    stale: tuple[str, ...]
    reasons: tuple[str, ...]
    ignored_noncritical: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return not self.allow_adds

    def apply_to_book(self, proposed: Mapping[str, float],
                      held: Mapping[str, float]) -> dict[str, float]:
        """Per sleeve min(proposed, held); new sleeves -> 0; total <= multiplier x held total."""
        if not self.active:
            return {k: float(v) for k, v in proposed.items()}
        out = {k: min(float(v), float(held.get(k, 0.0))) for k, v in proposed.items()}
        out = {k: v for k, v in out.items() if v > 0.0}
        cap = (self.max_heat_multiplier if self.max_heat_multiplier is not None else 1.0) \
            * sum(max(0.0, float(v)) for v in held.values())
        tot = sum(out.values())
        if tot > cap > 0:
            out = {k: v * cap / tot for k, v in out.items()}
        elif cap <= 0:
            out = {}
        return out


def staleness_clamp(inputs_as_of: Mapping[str, Any], now: datetime | str | None = None,
                    budgets: Mapping[str, float] | None = None) -> Clamp:
    """Families the allocator READ this pass -> the clamp their freshness imposes.

    Only families passed in are judged: a declared slot that feeds nothing cannot be stale. A
    critical family with no as-of, an unreadable one, one in the future (clock skew is not
    freshness), or one older than its budget -> HOLD. A non-critical stale family imposes no
    clamp; it is returned in `ignored_noncritical` so the caller DROPS its estimate rather than
    pooling an old one. An unregistered family is treated as critical: absence of a declaration
    is never a pass.
    """
    t_now = _parse(now) if now is not None else datetime.now(UTC)
    if t_now is None:
        raise ValueError(f"now={now!r} is not a timestamp")
    stale: list[str] = []
    reasons: list[str] = []
    ignored: list[str] = []
    for fam, raw in sorted(inputs_as_of.items()):
        s = spec(fam)
        critical = True if s is None else s.critical
        budget = (budgets or {}).get(fam, s.staleness_budget_s if s else 0.0)
        when = _parse(raw) if raw not in (None, "") else None
        why = None
        if when is None:
            why = f"{fam}: no readable as-of ({raw!r}) -- unmeasured is not fresh"
        elif when > t_now:
            why = f"{fam}: as-of {raw} is in the future -- clock skew is not freshness"
        elif (t_now - when).total_seconds() > budget:
            why = (f"{fam}: inputs {(t_now - when).total_seconds() / 3600:.1f}h old, budget "
                   f"{budget / 3600:.1f}h")
        if why is None:
            continue
        if critical:
            stale.append(fam)
            reasons.append(why + (" (unregistered -> critical)" if s is None else ""))
        else:
            ignored.append(fam)
    if stale:
        return Clamp(1.0, False, tuple(stale), tuple(reasons), tuple(ignored))
    return Clamp(None, True, (), (), tuple(ignored))


def as_of_from_doc(doc: Mapping[str, Any] | None, mtime: float | None = None) -> str | None:
    """The as-of a report states for itself, else its file mtime, else None (= stale)."""
    for key in ("inputs_as_of", "generated_utc", "generated_at", "measured_at", "at", "asof"):
        v = (doc or {}).get(key)
        if v and _parse(v) is not None:
            return str(v)
    if mtime is not None and math.isfinite(mtime):
        return datetime.fromtimestamp(mtime, UTC).isoformat(timespec="seconds")
    return None


def roles_report() -> dict[str, Any]:
    """The registry as a document, for FORECAST_CONTRACT.json and the reader."""
    return {"families": {k: {"roles": sorted(str(r) for r in s.roles), "horizon_s": s.horizon_s,
                             "staleness_budget_s": s.staleness_budget_s, "critical": s.critical,
                             "uses_features": s.uses_features, "module": s.module or None,
                             "reaches_allocator": s.reaches_allocator, "why": s.why}
                         for k, s in FAMILIES.items()},
            "declared_source_rho": {"|".join(sorted(k)): v
                                    for k, v in DECLARED_SOURCE_RHO.items()},
            "registry_defects": registry_defects()}


def families_with(role: Role | str) -> list[str]:
    return sorted(k for k, s in FAMILIES.items() if s.may(role))
