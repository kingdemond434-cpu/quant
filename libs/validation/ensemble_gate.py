"""THE PORTFOLIO AS THE UNIT OF SELECTION -- the second question the desk's gate never asked.

THE ARCHITECTURAL GAP. Every gate in `libs/validation` and `libs/autodiscovery/validation` asks
one question: does candidate i clear the bar STANDING ALONE, after paying for multiplicity? That
is the right question for finding a single strong strategy and it is the wrong question for the
architecture this desk says it wants. N mutually-uncorrelated edges of Sharpe s combine to a
portfolio Sharpe of s*sqrt(N); a Sharpe-0.2 component is worthless alone and a hundred orthogonal
ones are a Sharpe-2.0 book. Under a purely per-candidate gate the Sharpe-0.2 component is rejected
forever, no matter how many of them exist and no matter how orthogonal they are, so the desk was
structurally incapable of finding the exact edge class it most wants. This module adds the missing
question. It does not touch the first one: alpha stays 0.05, no per-candidate threshold moves, and
an ensemble faces the SAME deflated Sharpe, the SAME PBO bar, the SAME purged-CV bar and a
multiplicity charge that is strictly larger than a single candidate's.

WHY THIS IS NOT A LOOPHOLE, AND WHY THE PRE-REGISTRATION IS THE LOAD-BEARING PART. "Test the
portfolio instead of the candidate" is one small step from the most productive p-hacking device
available to a research desk. Given k candidates there are 2^k subsets and an unbounded number of
weighting rules, so a desk that is allowed to look at outcomes and then choose the combination can
manufacture a passing ensemble out of pure noise essentially every time -- and unlike ordinary
overfitting it will look principled, because every component was honestly measured. The garden of
forking paths is the entire hazard here, so the defence is structural rather than advisory:

  1. THE CANDIDATE SET AND THE COMBINATION RULE ARE DECLARED BEFORE ANY OUTCOME IS SEEN. A
     `PreRegistry` has two phases. While it is OPEN, declarations may be added and NOTHING can be
     scored. `seal()` closes it; after that, scoring is permitted and `declare()` raises
     `PostHocSelectionError`. There is no flag that reopens a sealed registry -- the only way to
     add a declaration is to start a new campaign carrying the old one's trial count forward
     (see `carried_trials`), which is exactly the cost that makes the pre-registration bite.
  2. EVERY RULE TRIED IS CHARGED AS A TRIAL. The deflated Sharpe's `n_trials` is the registry's
     `trials_spent` -- declarations sealed here plus any `carried_trials` inherited from an
     earlier campaign -- PLUS the candidate-level trials that produced the pool (`pool_trials`,
     which the caller must state; there is no default, because a forgotten zero is a silent
     discount on the bar). Searching over three combination rules therefore raises the ensemble's
     own bar, and a follow-on campaign that carries its predecessor's count forward cannot buy a
     discount by starting a fresh ledger.
  3. AN ENSEMBLE THE REGISTRY NEVER SAW IS REFUSED. `score_ensemble` recomputes the declaration's
     digest and refuses anything not sealed into the registry it is handed. A composition chosen
     after seeing outcomes cannot acquire a digest that was sealed before them.
  4. THE WHOLE PRE-REGISTERED FAMILY MUST BE RECONSTRUCTIBLE. If any declared candidate's returns
     are missing, scoring refuses rather than quietly charging a smaller multiplicity than the
     search actually incurred.

WHAT THIS CANNOT ENFORCE, said plainly rather than left for someone to discover. No code can see
what a researcher already knows: a desk that studied the outcomes yesterday can open a registry,
declare the winners, seal it and score them today, and every check above passes. What the module
can do is leave an AUDITABLE RECORD -- each declaration carries a timezone-aware `declared_utc`
and a content digest, and both land in the verdict's artifact -- so the claim "this was declared
before the outcome was known" becomes a dated, hashed statement that can be checked against when
the return series were built rather than an assertion nobody can revisit. The in-process checks
close the accidental path; the timestamp is what makes the deliberate one falsifiable.

WHAT AN ENSEMBLE IS SCORED AGAINST, and why the competitor family is vol-normalised. PBO and
Romano-Wolf both rank columns by MEAN return, which is not scale-free. An ensemble has lower
volatility than its components BY CONSTRUCTION -- that is the point of it -- so an unnormalised
family would compare a diversified book against undiversified components at unequal risk and
penalise the ensemble for the very property being tested. Every column of the competitor matrix is
therefore scaled to unit standard deviation first, which turns both statistics into Sharpe
comparisons and makes `sqrt(T)*mean` in Romano-Wolf exactly a t-statistic. The family itself is
the honest one: every OTHER pre-registered ensemble (that is the rule search being audited) plus
this ensemble's own components (the alternative to holding the book is holding one of its legs).

THE ORTHOGONALITY ARITHMETIC THAT CONSTRAINS ANY USE OF THIS MODULE. N candidates at average
pairwise correlation rho are worth N_eff = N/(1+(N-1)*rho) independent bets
(`libs.research.cohort_independence.effective_bets`), and that expression CONVERGES to 1/rho as
N grows. Hand-computed, and the arithmetic the tests assert against:

    rho = 0.348 (the desk's measured same-mechanism cross-symbol figure), N = 10
        N_eff = 10 / (1 + 9*0.348) = 10 / 4.132 = 2.4201   ->  sqrt = 1.5557x on Sharpe
    rho = 0.348, N -> infinity
        N_eff -> 1/0.348 = 2.8736                          ->  sqrt = 1.6952x, a HARD CEILING
    Sharpe 2.0 from Sharpe-0.2 components needs N_eff = (2.0/0.2)^2 = 100
        1/rho >= 100  ->  rho <= 0.01

So stacking candidates does not buy Sharpe; ORTHOGONALITY buys Sharpe, and past a few dozen
correlated candidates N stops buying information and only buys multiplicity burden. Admitting weak
candidates without measuring rho would build a large pile of correlated noise. `n_eff` is
therefore reported on every verdict, computed on the components actually combined.

WHAT THAT ARITHMETIC SAYS ABOUT THIS DESK, measured rather than assumed
(scripts/measure_cross_mechanism_corr.py, data/cross_mechanism_corr.json, 2026-08-05). Cross-
MECHANISM correlation across the desk's 19 mechanisms on 2,037 real daily bars gives a calibrated
breadth of 4.08 effective bets and a 2.02x Sharpe ceiling -- better than the 1.70x that
same-mechanism cross-symbol stacking buys, and 25x short of the N_eff 100 the Medallion target
needs. Its signed mean off-diagonal correlation is +0.005, which reads as nineteen independent
mechanisms and is pure cancellation between a trend bloc and a mean-reversion bloc (mean |rho|
0.375). So this module is worth having and it is not a Sharpe-2.0 machine on the current library:
the binding constraint is the number of GENUINELY DISTINCT mechanisms, not the candidate count and
not the combination rule.

RANKING BY MARGINAL CONTRIBUTION, NOT BY STANDALONE SHARPE. `libs.doctrine.portfolio_law` already
defines the correct object -- MC_i = E[log W | S] - E[log W | S\\{i}] -- and nothing was using it
to select candidates. `rank_by_marginal_contribution` does, so a weak but orthogonal candidate
correctly outranks a stronger but redundant one. Each leave-one-out portfolio is scaled to the
SAME target volatility before its log-growth is taken, which is load-bearing: without it the
comparison is dominated by how much exposure each subset happens to carry and MC ranks by size
rather than by contribution. This is the direct E[log W] link -- MC_i is literally the change in
expected log growth from holding i, which is the desk's objective and not a proxy for it.

Depends only on libs/validation/*, libs/research/cohort_independence and libs/doctrine. No I/O.
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

import numpy as np

from libs.doctrine.estimate import ADMIT_Z, Estimate
from libs.doctrine.portfolio_law import marginal_contribution
from libs.research.cohort_independence import effective_bets
from libs.validation.cpcv import CPCV
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.errors import ValidationError
from libs.validation.per_candidate import per_candidate_pbo, romano_wolf

__all__ = [
    "ALPHA",
    "CombinationRule",
    "EnsembleDeclaration",
    "EnsembleVerdict",
    "MarginalRank",
    "PostHocSelectionError",
    "PreRegistry",
    "combine",
    "rank_by_marginal_contribution",
    "score_ensemble",
    "sharpe_ceiling",
]

#: Family-wise error level. IDENTICAL to the per-candidate path's. This module adds a question, it
#: does not lower a bar, and this constant is the first place anyone would try to.
ALPHA = 0.05

#: Mirrors of the per-candidate gate's thresholds (libs/autodiscovery/validation). Restated rather
#: than imported because that module is the campaign orchestrator and importing it here would make
#: a validation primitive depend on its own caller. If either moves, these must move with it --
#: `test_ensemble_thresholds_match_the_per_candidate_path` is the tripwire.
_DSR_THRESHOLD = 0.95
_PBO_THRESHOLD = 0.5
_CPCV_MIN_POSITIVE = 0.6
_CPCV_GROUPS = 6
_CPCV_TEST_GROUPS = 2

# DECLARED INERT FOR THIS CONSUMER (R0240, measured 2026-08-19). Identical to the per-candidate
# path's declaration and deliberately kept in step with it -- one defect in two files means
# fixing one leaves the other authoritative. `CPCV.split()` purges and embargoes `train` only;
# `_cpcv_positive_fraction` below scores `returns[s.test]` and never reads `s.train`, so neither
# constant can reach the statistic. Held honest by `scripts/check_knob_sensitivity.py`, which
# probes BOTH copies.
_CPCV_PURGE = 2
_CPCV_EMBARGO = 0.01

#: Below this many observations there is nothing to purge and nothing to be combinatorial about,
#: so the ensemble cannot be scored at all. Refusing is the honest answer; a fallback would score
#: an ensemble on evidence that cannot support any of these statistics.
MIN_OBS = 60

#: A one-name "ensemble" is a candidate, and the per-candidate path already judges those.
MIN_CANDIDATES = 2

#: Return standard deviation below which a series is treated as DEAD rather than quiet. A flat
#: column correlates with nothing because it does nothing, so leaving one in would read as the
#: most diversifying leg in the book -- exactly backwards.
_SD_FLOOR = 1e-12

#: Leverage guard for the log-growth estimator. log(1+r) is undefined at r <= -1, so the scaling
#: applied for the E[log W] comparison is capped to keep the worst scaled observation above this.
_MIN_GROSS = 0.05


class CombinationRule(StrEnum):
    """The weighting rules that may be pre-registered. A closed set on purpose.

    An open-ended rule space is an open-ended search space, and the deflation can only charge for
    trials it can count. Adding a rule here is a deliberate act that widens the family for
    everyone; inventing one at a call site is not possible.
    """

    EQUAL_WEIGHT = "equal_weight"
    INVERSE_VOL = "inverse_vol"
    SHRUNK_INVERSE_VOL = "shrunk_inverse_vol"


class PostHocSelectionError(ValidationError):
    """The composition was chosen, or changed, after outcomes could have been seen."""


# ------------------------------------------------------------------------------ pre-registration

@dataclass(frozen=True)
class EnsembleDeclaration:
    """A candidate set and a combination rule, fixed BEFORE any outcome is observed.

    `declared_utc` must be timezone-aware. A naive timestamp cannot be ordered against anything
    else on this desk, and an unorderable pre-registration timestamp is not a pre-registration.
    """

    candidates: tuple[str, ...]
    rule: CombinationRule
    declared_utc: datetime
    rationale: str
    shrink: float = 0.5

    def __post_init__(self) -> None:
        if len(self.candidates) < MIN_CANDIDATES:
            raise ValidationError(
                f"an ensemble needs >= {MIN_CANDIDATES} candidates; the per-candidate path "
                "already judges a single strategy")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValidationError("duplicate candidate in the declaration: a repeated leg is a "
                                  "silent overweight, not a second bet")
        tz = self.declared_utc.tzinfo
        if tz is None or tz.utcoffset(self.declared_utc) is None:
            raise ValidationError("declared_utc must be timezone-aware")
        if not self.rationale.strip():
            raise ValidationError("a declaration needs a rationale -- WHY these candidates and "
                                  "this rule, written down before the answer is known")
        if not 0.0 <= float(self.shrink) <= 1.0:
            raise ValidationError("shrink must lie in [0, 1]")

    @property
    def digest(self) -> str:
        """Content hash of everything that defines the composition. Order-insensitive on names.

        Sorting the candidate names is deliberate: an ensemble is a SET, so reordering the same
        legs must not mint a fresh declaration that dodges the registry check.
        """
        payload = json.dumps({
            "candidates": sorted(self.candidates),
            "rule": str(self.rule),
            "shrink": round(float(self.shrink), 12),
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidates": list(self.candidates),
            "rule": str(self.rule),
            "shrink": float(self.shrink),
            "declared_utc": self.declared_utc.isoformat(),
            "rationale": self.rationale,
            "digest": self.digest,
        }


class PreRegistry:
    """The trial ledger. OPEN accepts declarations and refuses scoring; SEALED does the reverse.

    THE TWO PHASES ARE THE WHOLE MECHANISM. Pre-registration means the composition was fixed
    before the outcome was known, and the only way to enforce that mechanically is to make the two
    operations mutually exclusive in time. So there is no `unseal`, no `force`, and no way to
    append after the first look.

    `carried_trials` IS THE PART THAT MAKES THE SECOND LOOK EXPENSIVE, and the first version of
    this class got the argument backwards. A desk that wants a fourth combination rule after
    seeing three results must open a NEW registry -- and a new registry that started its count at
    one would charge FEWER trials than the campaign it descends from, i.e. looking again would buy
    a DISCOUNT on the bar. So a follow-on registry must carry the spent count forward:

        second = PreRegistry(campaign="rule-search-2", carried_trials=first.trials_spent)

    The module cannot detect a caller that omits it -- nothing in a process can see a search that
    happened in another process last week. What it can do is make the honest path one argument
    wide, put `carried_trials` in the verdict's artifact where an auditor reads it, and state here
    that a follow-on registry opened at zero is an understated multiplicity charge rather than a
    default.

    `trials_spent` -- declarations plus whatever was carried in -- is the rule-search multiplicity
    charge and is fed straight into the deflated Sharpe's trial count.
    """

    def __init__(self, *, campaign: str = "", carried_trials: int = 0) -> None:
        if int(carried_trials) < 0:
            raise ValidationError("carried_trials must be >= 0")
        self._campaign = campaign
        self._carried = int(carried_trials)
        self._declarations: list[EnsembleDeclaration] = []
        self._sealed = False

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def campaign(self) -> str:
        return self._campaign

    @property
    def carried_trials(self) -> int:
        return self._carried

    @property
    def trials_spent(self) -> int:
        """Every ensemble hypothesis this campaign has cost, including inherited ones."""
        return self._carried + len(self._declarations)

    @property
    def declarations(self) -> tuple[EnsembleDeclaration, ...]:
        return tuple(self._declarations)

    @property
    def n_declarations(self) -> int:
        return len(self._declarations)

    def declare(self, declaration: EnsembleDeclaration) -> EnsembleDeclaration:
        """Seal one composition into the ledger. Refused once the registry is closed."""
        if self._sealed:
            raise PostHocSelectionError(
                "this registry is SEALED: outcomes may already have been observed, so a "
                "composition declared now is a post-hoc choice. Ensembles picked after seeing "
                "results cannot be scored -- open a new registry, which charges this search as a "
                "fresh trial rather than hiding it inside an old one.")
        if any(d.digest == declaration.digest for d in self._declarations):
            raise ValidationError("this exact composition is already declared; declaring it twice "
                                  "would inflate the trial count without widening the search")
        self._declarations.append(declaration)
        return declaration

    def seal(self) -> PreRegistry:
        """Close the ledger. Nothing may be declared afterwards; scoring becomes possible."""
        if not self._declarations:
            raise ValidationError("nothing was pre-registered -- sealing an empty registry would "
                                  "let any composition be chosen after the outcome")
        self._sealed = True
        return self

    def contains(self, declaration: EnsembleDeclaration) -> bool:
        return any(d.digest == declaration.digest for d in self._declarations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaign": self._campaign,
            "sealed": self._sealed,
            "n_declarations": self.n_declarations,
            "carried_trials": self._carried,
            "trials_spent": self.trials_spent,
            "declarations": [d.as_dict() for d in self._declarations],
        }


# ------------------------------------------------------------------------------- the combination

def _weights(rule: CombinationRule, cols: np.ndarray, shrink: float) -> np.ndarray:
    """Weights implied by a PRE-REGISTERED rule. Never fitted to the outcome being scored.

    INVERSE_VOL uses in-sample volatilities, which is itself a mild fit -- volatility is estimated
    from the same sample the ensemble is scored on. That is why SHRUNK_INVERSE_VOL exists and why
    the shrink coefficient is part of the declaration's digest: it is a parameter, so it is
    pre-registered like any other. None of the three rules reads a mean return, so no rule can
    tilt toward whichever leg happened to pay.
    """
    n = cols.shape[1]
    equal = np.full(n, 1.0 / n, dtype="float64")
    if rule is CombinationRule.EQUAL_WEIGHT:
        return equal
    sd = np.std(cols, axis=0, ddof=1)
    if np.any(sd <= _SD_FLOOR):
        raise ValidationError("a component has zero variance; inverse-vol weighting is undefined "
                              "and a flat leg would read as the most diversifying one")
    inv = 1.0 / sd
    inv = inv / inv.sum()
    if rule is CombinationRule.INVERSE_VOL:
        return np.asarray(inv, dtype="float64")
    lam = float(shrink)
    return np.asarray((1.0 - lam) * inv + lam * equal, dtype="float64")


def combine(returns_by_id: Mapping[str, np.ndarray], declaration: EnsembleDeclaration,
            ) -> np.ndarray:
    """The combined return series of a pre-registered ensemble, in declared order."""
    cols = _stack(returns_by_id, declaration.candidates)
    w = _weights(declaration.rule, cols, declaration.shrink)
    return np.asarray(cols @ w, dtype="float64")


def _stack(returns_by_id: Mapping[str, np.ndarray], names: Sequence[str]) -> np.ndarray:
    missing = [n for n in names if n not in returns_by_id]
    if missing:
        raise ValidationError(f"no return series for pre-registered candidate(s): {missing}")
    cols = [np.asarray(returns_by_id[n], dtype="float64").ravel() for n in names]
    lengths = {c.size for c in cols}
    if len(lengths) != 1:
        raise ValidationError(f"component series have differing lengths {sorted(lengths)}; an "
                              "ensemble must be formed on aligned observations")
    m = np.column_stack(cols)
    if not np.all(np.isfinite(m)):
        raise ValidationError("component series contain non-finite values")
    return m


def _unit_vol(matrix: np.ndarray) -> np.ndarray:
    sd = np.std(matrix, axis=0, ddof=1)
    if np.any(sd <= _SD_FLOOR):
        raise ValidationError("a competitor column has zero variance")
    return np.asarray(matrix / sd, dtype="float64")


def sharpe_ceiling(n: int, mean_corr: float) -> dict[str, float]:
    """N_eff and the Sharpe multiplier it permits. The arithmetic that constrains the whole idea.

    `N_eff = N/(1+(N-1)*rho)` converges to `1/rho`, so `asymptotic_n_eff` is the ceiling that no
    amount of stacking passes. Hand-check in the module docstring: at rho=0.348, N=10 gives
    N_eff 2.4201 and a 1.5557x multiplier, and N -> infinity gives 2.8736 and 1.6952x.
    """
    n_eff = effective_bets(n, mean_corr)
    asymptotic = 1.0 / mean_corr if mean_corr > 0 else float(n)
    return {
        "n_eff": float(n_eff),
        "sharpe_multiplier": float(math.sqrt(max(n_eff, 0.0))),
        "asymptotic_n_eff": float(asymptotic),
        "asymptotic_sharpe_multiplier": float(math.sqrt(max(asymptotic, 0.0))),
    }


def _cpcv_positive_fraction(returns: np.ndarray) -> float:
    """Fraction of COMBINATORIAL test paths whose test slice is positive.

    Same splitter, same settings and the SAME HONEST SCOPE as the per-candidate gate: this is a
    sub-period consistency statistic over 15 combinatorial test paths, NOT a leakage test. Purge
    and embargo act on `CPCVSplit.train`, which this function never reads, so they are inert here
    by construction (measured 2026-08-19, R0240; the previous wording claimed they were "the
    difference between a real out-of-sample reading and a leaked one", and they were not).
    """
    splitter = CPCV(n_groups=_CPCV_GROUPS, n_test_groups=_CPCV_TEST_GROUPS,
                    purge=_CPCV_PURGE, embargo=_CPCV_EMBARGO)
    positive = [bool(returns[s.test].mean() > 0)
                for s in splitter.split(len(returns)) if len(s.test) > 1]
    return float(np.mean(positive)) if positive else 0.0


# --------------------------------------------------------------------------------- the verdict

@dataclass(frozen=True)
class EnsembleVerdict:
    """PASS/FAIL on the PORTFOLIO, with every number that produced it."""

    declaration: EnsembleDeclaration
    passed: bool
    gates: dict[str, bool]
    sharpe: float
    sharpe_annualised: float
    dsr: float
    dsr_threshold_sharpe: float
    pbo: float
    cpcv_positive_fraction: float
    adjusted_p: float
    n_trials_charged: int
    pool_trials: int
    n_rules_declared: int
    carried_trials: int
    n_obs: int
    n_components: int
    mean_component_corr: float
    n_eff: float
    ceiling: dict[str, float]
    component_sharpes: dict[str, float] = field(repr=False, default_factory=dict)

    def __bool__(self) -> bool:
        return self.passed

    @property
    def failed_gates(self) -> list[str]:
        return sorted(g for g, ok in self.gates.items() if not ok)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pre_registration": self.declaration.as_dict(),
            "passed": self.passed,
            "gates": dict(self.gates),
            "failed_gates": self.failed_gates,
            "sharpe": self.sharpe,
            "sharpe_annualised": self.sharpe_annualised,
            "dsr": self.dsr,
            "dsr_threshold_sharpe": self.dsr_threshold_sharpe,
            "pbo": self.pbo,
            "cpcv_positive_fraction": self.cpcv_positive_fraction,
            "adjusted_p": self.adjusted_p,
            "alpha": ALPHA,
            "n_trials_charged": self.n_trials_charged,
            "pool_trials": self.pool_trials,
            "n_rules_declared": self.n_rules_declared,
            "carried_trials": self.carried_trials,
            "n_obs": self.n_obs,
            "n_components": self.n_components,
            "mean_component_corr": self.mean_component_corr,
            "n_eff": self.n_eff,
            "ceiling": dict(self.ceiling),
            "component_sharpes": dict(self.component_sharpes),
        }

    def summary(self) -> str:
        verdict = "PASS" if self.passed else f"FAIL ({', '.join(self.failed_gates)})"
        return (f"{self.n_components} components at mean corr {self.mean_component_corr:.3f} "
                f"-> {self.n_eff:.2f} effective bets, ann Sharpe "
                f"{self.sharpe_annualised:.2f}; DSR {self.dsr:.3f} PBO {self.pbo:.3f} "
                f"CPCV {self.cpcv_positive_fraction:.2f} p_adj {self.adjusted_p:.3f} "
                f"over {self.n_trials_charged} charged trials :: {verdict}")


def score_ensemble(
    declaration: EnsembleDeclaration,
    returns_by_id: Mapping[str, np.ndarray],
    *,
    registry: PreRegistry,
    pool_trials: int,
    sharpe_estimates: np.ndarray | None = None,
    periods_per_year: float = 365.0,
    n_boot: int = 500,
    seed: int = 0,
) -> EnsembleVerdict:
    """Run a PRE-REGISTERED ensemble through the same rigor a single candidate faces.

    REFUSES BEFORE IT MEASURES, and the refusals are the point of the module:

      * the registry is still OPEN            -- nothing is pre-registered, so any composition
                                                 could still be chosen after the outcome;
      * the declaration is not in the registry -- it was minted after the seal;
      * a declared candidate's returns are missing -- the pre-registered family cannot be
        reconstructed, so the multiplicity charge would be smaller than the search that happened.

    `pool_trials` is REQUIRED and is the number of candidate-level hypotheses the pool came from.
    The ensemble's Sharpe is a maximum over two searches -- the candidate search that produced the
    pool and the rule search that produced this combination -- and both are charged, so the
    deflation bar here is strictly higher than the one a single candidate from the same pool pays.
    """
    if not registry.sealed:
        raise PostHocSelectionError(
            "the pre-registration is still OPEN. Scoring now would let the composition be chosen "
            "after the outcome is visible -- call registry.seal() before any series is measured, "
            "and understand that sealing permanently closes the ledger.")
    if not registry.contains(declaration):
        raise PostHocSelectionError(
            f"composition {declaration.digest[:12]} was never pre-registered in campaign "
            f"'{registry.campaign or 'unnamed'}'. An ensemble assembled after outcomes were seen "
            "is a garden-of-forking-paths result however honestly each component was measured.")
    if int(pool_trials) < 0:
        raise ValidationError("pool_trials must be >= 0")

    cols = _stack(returns_by_id, declaration.candidates)
    t_obs = int(cols.shape[0])
    if t_obs < MIN_OBS:
        raise ValidationError(f"{t_obs} observations; >= {MIN_OBS} needed to purge folds and run "
                              "a combinatorial split at all")
    if np.any(np.std(cols, axis=0, ddof=1) <= _SD_FLOOR):
        raise ValidationError("a component series is flat; it would read as the most diversifying "
                              "leg in the book while contributing nothing")

    combined = combine(returns_by_id, declaration)

    # The pre-registered family, reconstructed in full. A declaration whose legs are absent is a
    # refusal rather than a skip: skipping would charge fewer trials than the search cost.
    others = [d for d in registry.declarations if d.digest != declaration.digest]
    family = [combined] + [combine(returns_by_id, d) for d in others]
    competitors = _unit_vol(np.column_stack(family + [cols[:, i] for i in range(cols.shape[1])]))

    n_trials = int(pool_trials) + registry.trials_spent
    if sharpe_estimates is None:
        pool = [np.asarray(v, dtype="float64").ravel() for v in returns_by_id.values()]
        sharpe_estimates = np.array([sharpe_ratio(p) for p in pool], dtype="float64")
    est = np.asarray(sharpe_estimates, dtype="float64")
    if est.size < 2:
        raise ValidationError("need >= 2 sharpe estimates to price the deflation's search space")

    dsr = deflated_sharpe_ratio(combined, n_trials=max(n_trials, 2), sharpe_estimates=est,
                                threshold=_DSR_THRESHOLD)
    pbo = per_candidate_pbo(competitors, threshold=_PBO_THRESHOLD)
    stepdown = romano_wolf(competitors, n_boot=n_boot, alpha=ALPHA, seed=seed)
    cpcv_fraction = _cpcv_positive_fraction(combined)

    corr = np.corrcoef(cols, rowvar=False)
    iu = np.triu_indices(cols.shape[1], k=1)
    pair = corr[iu]
    pair = pair[np.isfinite(pair)]
    mean_corr = float(pair.mean()) if pair.size else 0.0
    ceiling = sharpe_ceiling(cols.shape[1], mean_corr)

    gates = {
        "dsr": bool(dsr.passed),
        "pbo": bool(pbo.pbo_for(0) <= _PBO_THRESHOLD),
        "cpcv": bool(cpcv_fraction >= _CPCV_MIN_POSITIVE),
        "multiplicity": bool(stepdown.significant(0)),
    }
    per_period = sharpe_ratio(combined)
    return EnsembleVerdict(
        declaration=declaration,
        passed=all(gates.values()),
        gates=gates,
        sharpe=per_period,
        sharpe_annualised=per_period * math.sqrt(float(periods_per_year)),
        dsr=float(dsr.dsr),
        dsr_threshold_sharpe=float(dsr.sr0_threshold),
        pbo=float(pbo.pbo_for(0)),
        cpcv_positive_fraction=cpcv_fraction,
        adjusted_p=float(stepdown.p_for(0)),
        n_trials_charged=max(n_trials, 2),
        pool_trials=int(pool_trials),
        n_rules_declared=registry.n_declarations,
        carried_trials=registry.carried_trials,
        n_obs=t_obs,
        n_components=int(cols.shape[1]),
        mean_component_corr=mean_corr,
        n_eff=float(ceiling["n_eff"]),
        ceiling=ceiling,
        component_sharpes={name: sharpe_ratio(cols[:, i])
                           for i, name in enumerate(declaration.candidates)},
    )


# ------------------------------------------------------- ranking by marginal contribution to logW

@dataclass(frozen=True)
class MarginalRank:
    """One candidate's MC_i = E[log W | S] - E[log W | S\\{i}], and what it is ranked against."""

    name: str
    mc: float
    se_paired: float
    t_paired: float
    significant: bool
    standalone_sharpe: float
    rho_to_portfolio: float
    marginal_sharpe: float
    doctrine: dict[str, Any] = field(repr=False, default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "mc": self.mc, "se_paired": self.se_paired,
            "t_paired": self.t_paired, "significant": self.significant,
            "standalone_sharpe": self.standalone_sharpe,
            "rho_to_portfolio": self.rho_to_portfolio,
            "marginal_sharpe": self.marginal_sharpe,
            "doctrine": dict(self.doctrine),
        }


def _log_growth(series: np.ndarray, target_vol: float) -> tuple[np.ndarray, Estimate]:
    """E[log W] of a series levered to `target_vol`, plus the per-period log-return path.

    THE VOLATILITY NORMALISATION IS LOAD-BEARING, not tidiness. A leave-one-out portfolio holds a
    different amount of risk than the full one, and raw log-growth is dominated by how much
    exposure a subset happens to carry. Holding risk fixed is what makes the difference between
    the two a measure of DIVERSIFICATION AND EDGE rather than of size -- which is the only reading
    under which a weak orthogonal leg can out-rank a strong redundant one.
    """
    sd = float(np.std(series, ddof=1))
    if sd <= _SD_FLOOR:
        raise ValidationError("a leave-one-out portfolio is flat; log growth is undefined")
    scale = float(target_vol) / sd
    worst = float(np.min(series)) * scale
    if worst <= _MIN_GROSS - 1.0:
        # Cap leverage rather than raise: a fat left tail is a property of the return stream, and
        # refusing to rank a book because one leg had a bad day would hide the ranking entirely.
        scale *= (_MIN_GROSS - 1.0) / worst
    path = np.log1p(series * scale)
    return np.asarray(path, dtype="float64"), Estimate(
        float(path.mean()), float(path.std(ddof=1) / math.sqrt(path.size)), int(path.size),
        "E[logW]")


def rank_by_marginal_contribution(
    returns_by_id: Mapping[str, np.ndarray],
    *,
    rule: CombinationRule = CombinationRule.EQUAL_WEIGHT,
    shrink: float = 0.5,
    target_vol: float = 0.01,
    z: float = ADMIT_Z,
) -> list[MarginalRank]:
    """Rank candidates by MC_i = E[log W | S] - E[log W | S\\{i}], highest first.

    THE INVERSION THIS EXISTS FOR. Ranking candidates by standalone Sharpe builds a book of
    correlated winners -- one bet wearing five names -- because the ranking is blind to what each
    leg adds on top of the others. MC is not: a leg's contribution is governed by
    `SR_i - rho_iP * SR_P`, so a weak but ORTHOGONAL candidate correctly outranks a stronger but
    REDUNDANT one. That is the whole reason `libs.doctrine.portfolio_law` defines MC and says a
    strategy is judged by its marginal contribution and never by its standalone record; until now
    nothing was using it to select candidates.

    THE DIRECT E[log W] LINK. MC_i is literally the change in the desk's objective -- expected log
    growth of wealth -- from holding i alongside the rest. It is not a proxy for the objective and
    not a risk heuristic that correlates with it; it is the derivative of the objective with
    respect to including this candidate, which is why it is the correct selection statistic and
    standalone Sharpe is not.

    Two standard errors are reported. `doctrine` carries `portfolio_law.marginal_contribution`'s
    verdict, whose SE combines the two portfolios' as if independent -- they are strongly
    positively correlated, so that reading is CONSERVATIVE. `se_paired` is the standard error of
    the paired per-period difference, which is the correct and much sharper one, and it is what
    `significant` uses.
    """
    names = list(returns_by_id)
    if len(names) < MIN_CANDIDATES:
        raise ValidationError(f"need >= {MIN_CANDIDATES} candidates to rank marginal contribution")
    # A fixed epoch stamp: these leave-one-out declarations are internal scaffolding for the
    # arithmetic, never pre-registrations of anything, and none of them is ever scored.
    stamp = datetime.fromtimestamp(0, tz=UTC)

    def _portfolio(subset: Sequence[str]) -> np.ndarray:
        if len(subset) == 1:
            return _stack(returns_by_id, subset)[:, 0]
        decl = EnsembleDeclaration(tuple(subset), rule, stamp, "leave-one-out", shrink)
        return combine(returns_by_id, decl)

    full = _portfolio(names)
    full_path, full_est = _log_growth(full, target_vol)
    sr_p = sharpe_ratio(full)

    ranks: list[MarginalRank] = []
    for name in names:
        rest = [n for n in names if n != name]
        wo_path, wo_est = _log_growth(_portfolio(rest), target_vol)
        diff = full_path - wo_path
        se = float(diff.std(ddof=1) / math.sqrt(diff.size))
        mc = float(diff.mean())
        leg = np.asarray(returns_by_id[name], dtype="float64").ravel()
        rho = float(np.corrcoef(leg, full)[0, 1])
        paired = Estimate(mc, se, int(diff.size), name)
        ranks.append(MarginalRank(
            name=name,
            mc=mc,
            se_paired=se,
            t_paired=float(mc / se) if se > 0 else 0.0,
            significant=bool(paired.significant_positive(z)),
            standalone_sharpe=sharpe_ratio(leg),
            rho_to_portfolio=rho,
            marginal_sharpe=float(sharpe_ratio(leg) - rho * sr_p),
            doctrine=marginal_contribution(full_est, wo_est, name),
        ))
    return sorted(ranks, key=lambda r: -r.mc)
