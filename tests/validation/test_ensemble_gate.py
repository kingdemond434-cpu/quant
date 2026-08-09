"""THE CAPABILITY THAT WAS MISSING, AND THE FAILURE MODE THAT MUST STAY CLOSED.

The desk's gate asked one question -- does candidate i clear the bar STANDING ALONE -- and that
question is structurally incapable of finding a portfolio of individually-weak, mutually-orthogonal
edges. N uncorrelated components of Sharpe 0.2 are a Sharpe-2.0 book at N=100 and every one of
them is rejected on its own. So the first test here asserts a CAPABILITY: enough orthogonal weak
series must produce a passing ensemble. Every other test asserts that the capability did not
arrive as a loophole:

  * the same weak series, highly correlated, must NOT pass -- otherwise the module launders noise;
  * the N_eff arithmetic must match the hand computation in `ensemble_gate`'s docstring, because
    that arithmetic is what says orthogonality rather than candidate count is the binding
    constraint;
  * an ensemble whose composition was chosen after seeing outcomes must be REFUSED, which is the
    one property separating this from the most productive p-hacking device available to a desk;
  * marginal contribution must invert the standalone ranking, putting a weak orthogonal candidate
    above a strong redundant one -- the direct E[log W] statement.

DETERMINISTIC PANELS. `exact_panel` whitens a random draw and re-colours it through a target
Cholesky factor, so the SAMPLE correlation matrix and the SAMPLE Sharpes are exactly the design
values rather than approximately them. That matters for the marginal-contribution test: the claim
is about the estimator's ordering, and a construction where the "weak" leg drew a lucky sample
would be testing sampling noise instead.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.research.cohort_independence import effective_bets
from libs.validation.dsr import deflated_sharpe_ratio
from libs.validation.ensemble_gate import (
    ALPHA,
    CombinationRule,
    EnsembleDeclaration,
    PostHocSelectionError,
    PreRegistry,
    combine,
    rank_by_marginal_contribution,
    score_ensemble,
    sharpe_ceiling,
)
from libs.validation.errors import ValidationError

PPY = 365.0
_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------------------------- builders

def weak_cohort(*, n: int, t: int, ann_sharpe: float, rho: float, seed: int,
                vol: float = 0.01) -> dict[str, np.ndarray]:
    """`n` series of the given true annualised Sharpe, sharing a common factor at `rho`."""
    rng = np.random.default_rng(seed)
    common = rng.standard_normal(t)
    mu = ann_sharpe * vol / np.sqrt(PPY)
    out: dict[str, np.ndarray] = {}
    for i in range(n):
        z = np.sqrt(rho) * common + np.sqrt(1.0 - rho) * rng.standard_normal(t)
        out[f"c{i:03d}"] = mu + vol * z
    return out


def exact_panel(corr: np.ndarray, ann_sharpes: np.ndarray, t: int, *, vol: float = 0.01,
                seed: int = 0) -> np.ndarray:
    """A (t x k) panel whose SAMPLE correlation and SAMPLE Sharpes are exactly as specified.

    Whitening the draw against its own sample covariance and re-colouring through the target
    Cholesky factor removes estimation noise entirely, so the test asserts the estimator's
    ordering rather than a lucky draw's.
    """
    c = np.asarray(corr, dtype="float64")
    z = np.random.default_rng(seed).standard_normal((t, c.shape[0]))
    z = z - z.mean(axis=0)
    whitened = z @ np.linalg.inv(np.linalg.cholesky((z.T @ z) / (t - 1))).T
    coloured = whitened @ np.linalg.cholesky(c).T
    return np.asarray(coloured * vol + np.asarray(ann_sharpes, dtype="float64") / np.sqrt(PPY)
                      * vol, dtype="float64")


def sealed(candidates: tuple[str, ...], rule: CombinationRule = CombinationRule.EQUAL_WEIGHT,
           ) -> tuple[PreRegistry, EnsembleDeclaration]:
    reg = PreRegistry(campaign="test")
    decl = reg.declare(EnsembleDeclaration(
        candidates=candidates, rule=rule, declared_utc=_NOW,
        rationale="declared before any series was measured"))
    reg.seal()
    return reg, decl


# ------------------------------------------------- 1. the capability that was structurally absent

def test_many_uncorrelated_weak_series_DO_produce_a_passing_ensemble() -> None:
    """200 orthogonal components at true annualised Sharpe 0.2 -- each hopeless alone.

    THE POINT. Every one of these fails a standalone bar by construction: at 0.2 annualised over
    2,000 daily bars the t-statistic is 0.2*sqrt(2000/365) = 0.47, nowhere near significance at any
    alpha this desk uses. Combined equal-weight at rho=0 the portfolio carries 0.2*sqrt(200) = 2.83
    annualised, which clears a deflated Sharpe charged for all 201 trials. That is the edge class
    the per-candidate gate could never admit, and admitting it required no threshold to move.
    """
    book = weak_cohort(n=200, t=2000, ann_sharpe=0.2, rho=0.0, seed=7)
    reg, decl = sealed(tuple(book))
    v = score_ensemble(decl, book, registry=reg, pool_trials=len(book), n_boot=200)

    standalone = np.array(list(v.component_sharpes.values()))
    assert float(standalone.mean() * np.sqrt(PPY)) < 0.4, "components must be individually weak"
    # NOT ONE of them clears the per-candidate deflated Sharpe at the same charged trial count.
    # This is the gap, measured rather than asserted: the standalone path admits zero of two
    # hundred, and the portfolio they form passes the identical bar.
    n_standalone_passes = sum(
        deflated_sharpe_ratio(r, n_trials=201, sharpe_estimates=standalone).passed
        for r in book.values())
    assert n_standalone_passes == 0

    assert v.sharpe_annualised > 2.0
    assert v.passed, v.summary()
    assert v.failed_gates == []
    # multiplicity was PAID, not skipped: 200 pool candidates plus the declared rule.
    assert v.n_trials_charged == 201
    assert v.adjusted_p <= ALPHA
    assert v.n_eff > 100.0     # rho ~ 0 over 200 legs


# --------------------------------------------------- 2. the failure mode that must stay closed

def test_many_CORRELATED_weak_series_do_NOT_produce_a_passing_ensemble() -> None:
    """The same 200 weak components at rho=0.9 -- a large pile of one bet, and it must fail.

    N_eff = 200/(1+199*0.9) = 1.11, so the portfolio Sharpe is 0.2*sqrt(1.11) = 0.21 and the book
    is a single mediocre bet wearing two hundred names. If this passed, the module would be a
    machine for laundering correlated noise into an admission, which is exactly the objection the
    ensemble idea has to survive.
    """
    book = weak_cohort(n=200, t=2000, ann_sharpe=0.2, rho=0.9, seed=7)
    reg, decl = sealed(tuple(book))
    v = score_ensemble(decl, book, registry=reg, pool_trials=len(book), n_boot=200)

    assert not v.passed, v.summary()
    assert "dsr" in v.failed_gates
    assert v.n_eff < 2.0
    assert v.mean_component_corr > 0.8


def test_the_two_cohorts_differ_ONLY_in_correlation() -> None:
    """Same true component Sharpe, same seed, same length -- only rho changes.

    The two cohorts above get opposite verdicts, and this pins the reason: the builder plants the
    identical drift in both and varies nothing but the shared factor loading. A correlated
    cohort's REALISED component Sharpes are of course not the orthogonal one's -- two hundred legs
    riding one factor draw move together, which is the whole point -- so the invariant asserted
    here is the design, and the measured correlations are what separate them.
    """
    def mean_corr(book: dict[str, np.ndarray]) -> float:
        m = np.column_stack(list(book.values()))
        c = np.corrcoef(m, rowvar=False)
        return float(c[np.triu_indices(c.shape[0], k=1)].mean())

    orth = weak_cohort(n=60, t=2000, ann_sharpe=0.2, rho=0.0, seed=7)
    corr = weak_cohort(n=60, t=2000, ann_sharpe=0.2, rho=0.9, seed=7)
    assert mean_corr(orth) == pytest.approx(0.0, abs=0.02)
    assert mean_corr(corr) == pytest.approx(0.9, abs=0.02)
    # identical planted drift: 0.2 annualised at 1% per-period vol
    planted = 0.2 * 0.01 / np.sqrt(PPY)
    assert np.mean([r.mean() for r in orth.values()]) == pytest.approx(planted, abs=2e-4)
    assert np.mean([r.mean() for r in corr.values()]) == pytest.approx(planted, abs=2e-3)
    assert effective_bets(60, mean_corr(orth)) > 50.0
    assert effective_bets(60, mean_corr(corr)) < 2.0


# ------------------------------------------------------------------ 3. the N_eff ceiling, by hand

def test_n_eff_ceiling_matches_the_hand_computation_in_the_docstring() -> None:
    """The arithmetic `ensemble_gate`'s docstring states, recomputed here rather than trusted.

        rho = 0.348, N = 10        N_eff = 10/(1 + 9*0.348) = 10/4.132 = 2.4201  -> 1.5557x
        rho = 0.348, N -> infinity N_eff -> 1/0.348          = 2.8736            -> 1.6952x
        Sharpe 2.0 from Sharpe-0.2 components needs N_eff = 100 -> rho <= 0.01

    The middle line is why candidate count is not the lever: stacking a THOUSAND candidates at the
    desk's measured same-mechanism correlation still buys 2.87 bets and a 1.70x multiplier.
    """
    rho = 0.348
    ceil10 = sharpe_ceiling(10, rho)
    assert ceil10["n_eff"] == pytest.approx(10.0 / (1.0 + 9.0 * rho), rel=1e-12)
    assert ceil10["n_eff"] == pytest.approx(2.4201, abs=1e-4)
    assert ceil10["sharpe_multiplier"] == pytest.approx(1.5557, abs=1e-4)

    assert ceil10["asymptotic_n_eff"] == pytest.approx(2.8736, abs=1e-4)
    assert ceil10["asymptotic_sharpe_multiplier"] == pytest.approx(1.6952, abs=1e-4)

    # The convergence is real, not an approximation that loosens at large N.
    assert effective_bets(1000, rho) == pytest.approx(2.8736, abs=1e-2)
    assert effective_bets(100000, rho) == pytest.approx(1.0 / rho, abs=1e-3)

    # What Sharpe 2.0 from 0.2-Sharpe components actually demands.
    n_eff_required = (2.0 / 0.2) ** 2
    assert n_eff_required == 100.0
    assert 1.0 / n_eff_required == pytest.approx(0.01)
    # ... and 0.01 is 35x tighter than the correlation the desk has actually measured.
    assert rho / 0.01 == pytest.approx(34.8)


def test_a_scored_ensemble_reports_its_own_ceiling() -> None:
    """The verdict carries N_eff computed on the legs actually combined, not an assumption."""
    book = weak_cohort(n=30, t=800, ann_sharpe=0.2, rho=0.348, seed=3)
    reg, decl = sealed(tuple(book))
    v = score_ensemble(decl, book, registry=reg, pool_trials=len(book), n_boot=100)
    assert v.mean_component_corr == pytest.approx(0.348, abs=0.06)
    assert v.ceiling["asymptotic_n_eff"] == pytest.approx(1.0 / v.mean_component_corr, rel=1e-9)
    assert v.n_eff < 4.0


# --------------------------------------------------------------- 4. post-hoc composition REFUSED

def test_an_ensemble_chosen_AFTER_seeing_outcomes_is_refused() -> None:
    """The loophole this module would otherwise open, closed structurally rather than by advice.

    The researcher scores a pre-registered ensemble, sees the result, and then wants to declare the
    subset that happened to work. `declare()` on a sealed registry raises, and a declaration minted
    outside the registry is refused at scoring time -- so the winning subset can never acquire a
    digest that was sealed before the outcome was visible.
    """
    book = weak_cohort(n=12, t=600, ann_sharpe=0.2, rho=0.0, seed=5)
    reg, decl = sealed(tuple(book))
    score_ensemble(decl, book, registry=reg, pool_trials=len(book), n_boot=100)

    winners = tuple(sorted(book, key=lambda k: -float(book[k].mean()))[:6])
    post_hoc = EnsembleDeclaration(candidates=winners, rule=CombinationRule.EQUAL_WEIGHT,
                                   declared_utc=_NOW + timedelta(hours=1),
                                   rationale="these are the ones that worked")

    with pytest.raises(PostHocSelectionError, match="SEALED"):
        reg.declare(post_hoc)

    with pytest.raises(PostHocSelectionError, match="never pre-registered"):
        score_ensemble(post_hoc, book, registry=reg, pool_trials=len(book), n_boot=50)


def test_scoring_before_the_registry_is_sealed_is_refused() -> None:
    """An OPEN registry means the composition could still change after the outcome is visible."""
    book = weak_cohort(n=8, t=400, ann_sharpe=0.2, rho=0.0, seed=6)
    reg = PreRegistry(campaign="unsealed")
    decl = reg.declare(EnsembleDeclaration(tuple(book), CombinationRule.EQUAL_WEIGHT, _NOW,
                                           "declared but not sealed"))
    with pytest.raises(PostHocSelectionError, match="still OPEN"):
        score_ensemble(decl, book, registry=reg, pool_trials=len(book), n_boot=50)


def test_reordering_the_same_legs_does_not_mint_a_fresh_declaration() -> None:
    """An ensemble is a SET. Shuffling the names must not walk past the registry check."""
    book = weak_cohort(n=6, t=400, ann_sharpe=0.2, rho=0.0, seed=8)
    names = tuple(book)
    reg, _ = sealed(names)
    shuffled = EnsembleDeclaration(tuple(reversed(names)), CombinationRule.EQUAL_WEIGHT, _NOW,
                                   "same legs, different order")
    assert reg.contains(shuffled)


def test_every_rule_tried_is_charged_as_a_trial() -> None:
    """Searching over combination rules raises the ensemble's own bar. The search is not free."""
    book = weak_cohort(n=20, t=800, ann_sharpe=0.2, rho=0.0, seed=9)
    reg = PreRegistry(campaign="rule-search")
    decls = [reg.declare(EnsembleDeclaration(tuple(book), rule, _NOW, f"rule {rule}"))
             for rule in CombinationRule]
    reg.seal()
    assert reg.n_declarations == 3

    one = PreRegistry(campaign="single")
    solo = one.declare(EnsembleDeclaration(tuple(book), CombinationRule.EQUAL_WEIGHT, _NOW, "one"))
    one.seal()

    searched = score_ensemble(decls[0], book, registry=reg, pool_trials=20, n_boot=100)
    single = score_ensemble(solo, book, registry=one, pool_trials=20, n_boot=100)
    assert searched.n_trials_charged > single.n_trials_charged
    assert searched.dsr_threshold_sharpe > single.dsr_threshold_sharpe


def test_a_follow_on_campaign_cannot_buy_a_discount_by_opening_a_fresh_ledger() -> None:
    """The accounting hole a two-phase registry alone leaves open, and the argument that closes it.

    A sealed registry refuses new declarations, so a desk that wants a fourth rule after seeing
    three results must open a NEW registry. If that registry started its count at one it would
    charge FEWER trials than the campaign it descends from -- looking again would buy a DISCOUNT on
    the bar, which is exactly backwards. `carried_trials` makes the follow-on strictly dearer, and
    it lands in the verdict where an auditor can see whether it was paid.
    """
    book = weak_cohort(n=20, t=800, ann_sharpe=0.2, rho=0.0, seed=13)
    first = PreRegistry(campaign="round-1")
    for rule in CombinationRule:
        first.declare(EnsembleDeclaration(tuple(book), rule, _NOW, f"rule {rule}"))
    first.seal()
    assert first.trials_spent == 3

    honest = PreRegistry(campaign="round-2", carried_trials=first.trials_spent)
    d2 = honest.declare(EnsembleDeclaration(tuple(book)[:10], CombinationRule.EQUAL_WEIGHT,
                                            _NOW, "a narrower set, declared after round 1"))
    honest.seal()
    assert honest.trials_spent == 4

    cheating = PreRegistry(campaign="round-2-amnesia")
    d3 = cheating.declare(EnsembleDeclaration(tuple(book)[:10], CombinationRule.EQUAL_WEIGHT,
                                              _NOW, "same set, ledger reopened at zero"))
    cheating.seal()

    paid = score_ensemble(d2, book, registry=honest, pool_trials=20, n_boot=100)
    unpaid = score_ensemble(d3, book, registry=cheating, pool_trials=20, n_boot=100)
    assert paid.n_trials_charged == 24
    assert unpaid.n_trials_charged == 21
    assert paid.dsr_threshold_sharpe > unpaid.dsr_threshold_sharpe
    assert paid.carried_trials == 3
    assert unpaid.carried_trials == 0     # visible in the artifact, which is the only defence


def test_a_declaration_whose_legs_are_missing_is_refused_rather_than_discounted() -> None:
    """Dropping an unscorable declaration would charge fewer trials than the search cost."""
    book = weak_cohort(n=6, t=400, ann_sharpe=0.2, rho=0.0, seed=10)
    reg = PreRegistry(campaign="incomplete")
    first = reg.declare(EnsembleDeclaration(tuple(book), CombinationRule.EQUAL_WEIGHT, _NOW, "a"))
    reg.declare(EnsembleDeclaration(("c000", "ghost"), CombinationRule.EQUAL_WEIGHT, _NOW, "b"))
    reg.seal()
    with pytest.raises(ValidationError, match="ghost"):
        score_ensemble(first, book, registry=reg, pool_trials=6, n_boot=50)


def test_a_naive_declaration_timestamp_is_refused() -> None:
    """A pre-registration that cannot be ordered against anything is not a pre-registration."""
    with pytest.raises(ValidationError, match="timezone-aware"):
        EnsembleDeclaration(("a", "b"), CombinationRule.EQUAL_WEIGHT,
                            datetime(2026, 8, 5, 12, 0), "naive")


def test_a_single_name_ensemble_is_refused() -> None:
    with pytest.raises(ValidationError, match=">= 2 candidates"):
        EnsembleDeclaration(("a",), CombinationRule.EQUAL_WEIGHT, _NOW, "one leg")


# ------------------------------------------ 5. marginal contribution inverts standalone ranking

def _redundancy_book() -> dict[str, np.ndarray]:
    """Three correlated core sleeves, one strong-but-redundant leg, one weak-but-orthogonal leg.

    Sample moments are EXACT by construction: annualised Sharpes 1.0 / 1.0 / 1.0 / 1.1 / 0.4, core
    legs correlated at 0.95 with each other, the strong leg at 0.97 with each core leg, and the
    weak leg at 0.0 with everything.
    """
    names = ["core_a", "core_b", "core_c", "strong_redundant", "weak_orthogonal"]
    c = np.eye(5)
    for i in range(3):
        for j in range(3):
            if i != j:
                c[i, j] = 0.95
        c[i, 3] = c[3, i] = 0.97
    panel = exact_panel(c, np.array([1.0, 1.0, 1.0, 1.1, 0.4]), 3000, seed=3)
    return {n: panel[:, i] for i, n in enumerate(names)}


def test_a_weak_ORTHOGONAL_candidate_outranks_a_strong_REDUNDANT_one() -> None:
    """MC_i = E[log W|S] - E[log W|S\\{i}] inverts the standalone ranking, and must.

    Standalone, `strong_redundant` (annualised Sharpe 1.10) beats `weak_orthogonal` (0.40) by
    almost 3x, and any Sharpe-ranked selection takes the strong one. Its edge is already owned by
    the core, though: at rho 0.962 to the portfolio its marginal Sharpe is
    1.10 - 0.962*1.107 = +0.035, while the orthogonal leg's is 0.40 - 0.246*1.107 = +0.128 --
    3.7x larger from a third of the standalone Sharpe. Ranking by contribution to portfolio log
    growth reproduces that ordering; ranking by standalone Sharpe reverses it and builds one bet
    wearing five names.
    """
    book = _redundancy_book()
    ranked = rank_by_marginal_contribution(book)
    by_name = {r.name: r for r in ranked}

    # the premise: standalone, the redundant leg looks strictly better
    assert (by_name["strong_redundant"].standalone_sharpe
            > by_name["weak_orthogonal"].standalone_sharpe)
    assert by_name["strong_redundant"].standalone_sharpe * np.sqrt(PPY) == pytest.approx(1.1,
                                                                                        abs=1e-6)
    assert by_name["weak_orthogonal"].standalone_sharpe * np.sqrt(PPY) == pytest.approx(0.4,
                                                                                        abs=1e-6)

    # the inversion
    assert ranked[0].name == "weak_orthogonal", [r.name for r in ranked]
    assert by_name["weak_orthogonal"].mc > by_name["strong_redundant"].mc
    assert by_name["weak_orthogonal"].mc > 0.0
    # ... and the evidence, not only the point estimate, favours it
    assert by_name["weak_orthogonal"].t_paired > by_name["strong_redundant"].t_paired > 0.0

    # and the analytic reason, SR_i - rho_iP * SR_P, agrees with the empirical MC ordering
    assert by_name["weak_orthogonal"].marginal_sharpe * np.sqrt(PPY) == pytest.approx(0.128,
                                                                                      abs=0.01)
    assert by_name["strong_redundant"].marginal_sharpe * np.sqrt(PPY) == pytest.approx(0.035,
                                                                                       abs=0.01)
    assert (by_name["weak_orthogonal"].marginal_sharpe
            > by_name["strong_redundant"].marginal_sharpe)


def test_marginal_contribution_carries_the_doctrine_verdict() -> None:
    """The ranking is the doctrine object, not a lookalike: portfolio_law decides the wording."""
    ranked = rank_by_marginal_contribution(_redundancy_book())
    top = ranked[0]
    assert top.doctrine["name"] == top.name
    assert top.doctrine["mc"] == pytest.approx(top.mc, abs=1e-6)   # portfolio_law rounds to 6dp
    # portfolio_law combines the two portfolios' standard errors as if independent; they are
    # strongly positively correlated, so its SE is the conservative one.
    assert top.doctrine["se"] > top.se_paired


def test_a_redundant_leg_can_have_a_NEGATIVE_marginal_contribution() -> None:
    """Adding a copy of what the book already owns subtracts, and the ranking says so."""
    names = ["a", "b", "clone_of_a"]
    c = np.array([[1.0, 0.0, 0.99], [0.0, 1.0, 0.0], [0.99, 0.0, 1.0]])
    panel = exact_panel(c, np.array([1.0, 1.0, 0.6]), 3000, seed=4)
    ranked = rank_by_marginal_contribution({n: panel[:, i] for i, n in enumerate(names)})
    assert ranked[-1].name == "clone_of_a"
    assert ranked[-1].mc < 0.0


# ---------------------------------------------------------------------------- combination rules

def test_the_combination_rule_is_part_of_the_pre_registered_identity() -> None:
    """Two rules over the same legs are two hypotheses, so they must be two digests."""
    book = weak_cohort(n=4, t=200, ann_sharpe=0.2, rho=0.0, seed=11)
    names = tuple(book)
    eq = EnsembleDeclaration(names, CombinationRule.EQUAL_WEIGHT, _NOW, "equal")
    iv = EnsembleDeclaration(names, CombinationRule.INVERSE_VOL, _NOW, "inverse vol")
    assert eq.digest != iv.digest
    assert not np.allclose(combine(book, eq), combine(book, iv))


def test_shrunk_inverse_vol_sits_between_its_two_endpoints() -> None:
    """shrink=0 is inverse-vol, shrink=1 is equal-weight, and the digest records which."""
    rng = np.random.default_rng(12)
    book = {"a": rng.normal(0, 0.01, 300), "b": rng.normal(0, 0.04, 300)}
    names = ("a", "b")
    iv = combine(book, EnsembleDeclaration(names, CombinationRule.INVERSE_VOL, _NOW, "iv"))
    eq = combine(book, EnsembleDeclaration(names, CombinationRule.EQUAL_WEIGHT, _NOW, "eq"))
    at0 = combine(book, EnsembleDeclaration(names, CombinationRule.SHRUNK_INVERSE_VOL, _NOW,
                                            "s0", 0.0))
    at1 = combine(book, EnsembleDeclaration(names, CombinationRule.SHRUNK_INVERSE_VOL, _NOW,
                                            "s1", 1.0))
    assert np.allclose(at0, iv)
    assert np.allclose(at1, eq)


def test_ensemble_thresholds_match_the_per_candidate_path() -> None:
    """The tripwire on the one thing this module must never do: move a bar.

    alpha stays 0.05 and the ensemble's DSR/PBO/CPCV bars are the per-candidate path's own. If
    `libs/autodiscovery/validation` moves one of them, this fails and the mirror gets updated
    rather than silently drifting apart.
    """
    from libs.autodiscovery import validation as per_candidate_path
    from libs.validation import ensemble_gate as eg

    assert ALPHA == 0.05
    assert eg._DSR_THRESHOLD == per_candidate_path._DSR_THRESHOLD
    assert eg._PBO_THRESHOLD == per_candidate_path._PBO_THRESHOLD
    assert eg._CPCV_MIN_POSITIVE == per_candidate_path._CPCV_MIN_POSITIVE
    assert eg._CPCV_GROUPS == per_candidate_path._CPCV_GROUPS
    assert eg._CPCV_TEST_GROUPS == per_candidate_path._CPCV_TEST_GROUPS
    assert eg._CPCV_PURGE == per_candidate_path._CPCV_PURGE
    assert eg._CPCV_EMBARGO == per_candidate_path._CPCV_EMBARGO
