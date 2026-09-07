"""Research compute must be bought with portfolio dE[log W], not with a price list.

MEASURED ON THIS TREE 2026-09-07, and it is the reason this file exists. `RESEARCH_BANDIT.json`
carried `worth = 1.000` for all eleven arms -- `_marginal_by_arm` needs a `pf_allocator.json`
with arm-attributable certified sleeves and there is not one -- and nine of the eleven arms
carried zero judged hypotheses. With worth flat and evidence absent, `score = worth x p / cost`
collapses to `p_pooled / cost`, and the budget was decided by the declared cost table:

    corr(share, 1/cost) = +0.87

    new_mechanism      cost 9.0   share  5.81%    <- owns every one of the 11 empty clusters
    combine_survivors  cost 3.0   share 13.57%    <- ensembles of sleeves the book already holds

The desk was spending its research compute buying more of the bet it already owned.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import bandit  # noqa: E402
from libs.research.breadth_credit import (  # noqa: E402
    ARM_BREADTH_WEIGHT,
    DECLARED,
    MAX_CREDIT,
    MEASURED,
    MIN_CREDIT,
    UNMEASURED,
    credits,
    implied_rho,
    marginal_k_eff,
)

#: The book as `reports/EFFECTIVE_BREADTH.json` measured it on 2026-09-05.
N, K, RHO_CROSS = 31.0, 1.324, 0.2118
BOOK = {
    "effective": {"n_nominal": N, "effective_breadth": K,
                  "readings": [{"name": "exposure_full_sample",
                                "detail": {"mean_pairwise_corr": RHO_CROSS}}]},
    "clusters": {"occupied_either": ["session_liquidity", "mean_reversion", "macro_rates",
                                     "fixing_roll_calendar"],
                 "empty_in_both": ["trend", "carry_risk_premium", "event_surprise"]},
}


# ------------------------------------------------------------------------------- the arithmetic
def test_a_duplicate_REDUCES_effective_breadth_and_the_algebra_says_so() -> None:
    """The finding the whole change rests on, and it is derived rather than asserted.

    A perfectly correlated addition adds nominal risk and no bets, so (sum|w|)^2 / x'Cx falls.
    Nothing in a standalone Sharpe screen can express this: the sleeve can look excellent and
    still make the portfolio worse.
    """
    assert marginal_k_eff(N, K, 1.0) < 0.0
    assert marginal_k_eff(N, K, 0.0) > 0.0


def test_the_marginal_is_monotonically_worse_in_correlation() -> None:
    ds = [marginal_k_eff(N, K, r) for r in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
    assert all(a > b for a, b in zip(ds, ds[1:], strict=False)), ds


def test_an_independent_sleeve_is_worth_many_times_a_correlated_one() -> None:
    """The number that should have been in the bandit and was not: on THIS book a new payer at
    the desk's own measured cross-correlation buys ~5.8x the breadth of another sleeve in an
    occupied cluster."""
    rho_book = implied_rho(N, K)
    assert rho_book == pytest.approx(0.747, abs=0.002)
    ratio = marginal_k_eff(N, K, RHO_CROSS) / marginal_k_eff(N, K, rho_book)
    assert 4.0 < ratio < 8.0, ratio


def test_the_implied_rho_is_solved_from_the_measurement_not_assumed() -> None:
    """k_eff = n / (1 + (n-1) rho) inverted. A round trip pins it."""
    for rho in (0.1, 0.5, 0.9):
        k = N / (1.0 + (N - 1.0) * rho)
        assert implied_rho(N, k) == pytest.approx(rho, abs=1e-9)


def test_a_degenerate_book_refuses_rather_than_returning_a_number() -> None:
    assert implied_rho(1.0, 1.0) is None
    for bad in ((0.0, 1.0), (31.0, 0.0), (float("nan"), 1.0)):
        with pytest.raises(ValueError):
            marginal_k_eff(bad[0], bad[1], 0.5)


# ------------------------------------------------------------------------------- the two channels
def test_a_pure_quality_arm_is_left_exactly_neutral() -> None:
    """THE CORRECTION THAT MATTERS MOST HERE, and the first version of this module got it wrong.

    `execution_improvement` makes the sleeves the book already holds cheaper. That raises s_bar
    and buys real growth; it buys zero breadth. Scoring it on the breadth channel cut it from
    12.2% of research compute to 3.6% on an instrument that has nothing to say about execution --
    a category error, and one the desk's own law already forbids: UNMEASURED is a verdict, not a
    zero. It must come out at exactly 1.0.
    """
    c = credits(bandit.ARMS, doc=BOOK)
    assert c["status"] == MEASURED
    for arm in ("execution_improvement", "exit_improvement"):
        assert ARM_BREADTH_WEIGHT[arm] == 0.0
        assert c["credit"][arm] == pytest.approx(1.0), arm
        assert "cannot measure" in c["arms"][arm]["why"]


def test_the_breadth_arms_are_lifted_and_the_duplicate_arms_are_cut() -> None:
    c = credits(bandit.ARMS, doc=BOOK)["credit"]
    for arm in ("new_mechanism", "cross_asset_signal", "alt_data_hypothesis"):
        assert c[arm] > 1.2, (arm, c[arm])
    for arm in ("mutate_survivor", "combine_survivors"):
        assert c[arm] < 0.75, (arm, c[arm])
    assert c["new_mechanism"] > c["mutate_survivor"] * 2


def test_every_credit_stays_inside_the_declared_bounds() -> None:
    """A model with an unbounded multiplier hands one arm the whole budget, which is the exact
    trap the exploration floor exists to prevent."""
    c = credits(bandit.ARMS, doc=BOOK)["credit"]
    assert all(MIN_CREDIT <= v <= MAX_CREDIT for v in c.values()), c


def test_the_credit_redistributes_and_does_not_inflate() -> None:
    """Mean-normalised over the arms that run through the breadth channel, so the arms still
    divide ONE budget however extreme the arithmetic gets."""
    c = credits(bandit.ARMS, doc=BOOK)
    breadth_arms = [a for a in bandit.ARMS if ARM_BREADTH_WEIGHT[a] > 0]
    mean_channel = float(np.mean([c["arms"][a]["credit_breadth_channel"] for a in breadth_arms]))
    assert mean_channel == pytest.approx(1.0, abs=0.35), mean_channel


# --------------------------------------------------------------------------- measured beats declared
def test_a_measured_occupied_share_overrides_the_declared_one() -> None:
    ms = {"new_mechanism": {"share": 0.95, "n_classified": 40, "in_occupied": 38, "in_empty": 2}}
    c = credits(bandit.ARMS, doc=BOOK, measured_shares=ms)
    assert c["arms"]["new_mechanism"]["source"] == MEASURED
    assert c["arms"]["new_mechanism"]["occupied_share"] == pytest.approx(0.95)
    # an arm measured to work almost entirely in occupied ground loses its lift, which is the
    # point of measuring rather than declaring
    assert c["credit"]["new_mechanism"] < 1.0


def test_a_thin_measured_share_falls_back_to_the_declaration() -> None:
    ms = {"new_mechanism": {"share": 0.95, "n_classified": 3, "in_occupied": 3, "in_empty": 0}}
    c = credits(bandit.ARMS, doc=BOOK, measured_shares=ms)
    assert c["arms"]["new_mechanism"]["source"] == DECLARED


def test_unclassified_proposals_vote_for_neither_bucket() -> None:
    """A proposal whose phenomenon the desk cannot name is evidence the desk cannot name it --
    a finding, not a vote. It must not be counted into the share in either direction."""
    from libs.research.breadth_credit import occupied_shares
    rows = [{"a": "x"}] * 5
    out = occupied_shares(rows, lambda r: "new_mechanism", lambda r: None, set())
    assert out["new_mechanism"]["n_classified"] == 0
    assert out["new_mechanism"]["share"] is None
    assert out["new_mechanism"]["unclassified"] == 5


# -------------------------------------------------------------------------- absence is neutral
def test_no_breadth_report_means_every_credit_is_one() -> None:
    """A broken or missing measurement must not be able to change an allocation in EITHER
    direction. Neutral is the only safe value for an instrument that did not read."""
    for doc in ({}, {"effective": {}}, {"effective": {"n_nominal": 1, "effective_breadth": 1.0}},
                {"effective": {"n_nominal": 31, "effective_breadth": 0.0}}):
        c = credits(bandit.ARMS, doc=doc)
        assert c["status"] == UNMEASURED, doc
        assert set(c["credit"].values()) == {1.0}, doc


def test_a_new_payer_is_credited_at_the_measured_cross_correlation_never_at_zero() -> None:
    """Assuming a new mechanism is independent is the error that raises leverage. The desk's own
    measured cross-instrument correlation is the floor, and it is read from the report."""
    c = credits(bandit.ARMS, doc=BOOK)
    assert c["book"]["rho_cross"] == pytest.approx(RHO_CROSS)
    assert c["book"]["rho_cross_source"].startswith("measured")
    # an arm with occupied_share 0 would sit at rho_cross, not at 0
    assert min(r["rho_to_book"] for r in c["arms"].values()) >= RHO_CROSS - 1e-9


# ------------------------------------------------------------------------------ the bandit wiring
def _flat_evidence() -> dict[str, dict[str, float]]:
    """The state actually measured on 2026-09-07: worth flat, nine arms with no judged rows."""
    return {a: {"born": 0, "failed": 0, "certified": 0, "alpha": 1.9, "beta": 39.1,
                "p_survivor": 0.0462, "worth": 1.0, "cost": float(sum(bandit.COST[a]))}
            for a in bandit.ARMS}


def test_the_OLD_clamp_let_the_cost_table_decide_the_budget() -> None:
    """The defect, reproduced from the code that had it, so the fix has something to be a fix OF.

    `min(ratio, pooled)` with worth flat at 1.0 leaves every expensive arm at 1/cost and pulls
    every cheap one down to the pooled ratio -- so the ONLY surviving signal is price, in the
    direction that starves the expensive arms. This recomputes the old expression directly rather
    than calling `allocate`, because `allocate` no longer contains it.
    """
    ev = _flat_evidence()
    ratio = {a: ev[a]["worth"] / ev[a]["cost"] for a in bandit.ARMS}
    pooled = float(np.mean(list(ratio.values())))
    old = {a: min(ratio[a], pooled) for a in bandit.ARMS}          # <- the clamp as it was
    cost = np.array([sum(bandit.COST[a]) for a in bandit.ARMS])
    got = np.array([old[a] for a in bandit.ARMS])
    assert float(np.corrcoef(1.0 / cost, got)[0, 1]) > 0.8
    assert old["new_mechanism"] < old["combine_survivors"], (
        "the arm owning every empty cluster ranked below the ensembling arm, on price alone")


def test_with_the_credit_the_cost_table_no_longer_decides_it() -> None:
    credit = credits(bandit.ARMS, doc=BOOK)["credit"]
    sh = bandit.allocate(_flat_evidence(), np.random.default_rng(0), credit=credit)
    cost = np.array([sum(bandit.COST[a]) for a in bandit.ARMS])
    got = np.array([sh[a] for a in bandit.ARMS])
    assert float(np.corrcoef(1.0 / cost, got)[0, 1]) < 0.3
    assert sh["new_mechanism"] > sh["combine_survivors"] * 2, (
        "the arm that owns every empty cluster must outrank the arm that ensembles held sleeves")


def test_the_cold_arm_clamp_is_symmetric() -> None:
    """It used to be `min(ratio, pooled)`, which removed a cheap arm's ADVANTAGE and left an
    expensive arm's PENALTY -- so 'evidence, not price, allocates' was false in exactly the
    direction that starved the expensive arms, which are the ones that buy breadth.

    With no evidence and no credit anywhere, every arm must get the same share.
    """
    ev = _flat_evidence()
    for a in ev:
        ev[a]["cost"] = float(sum(bandit.COST[a]))
    sh = bandit.allocate(ev, np.random.default_rng(0),
                         credit={a: 1.0 for a in bandit.ARMS})
    cost = np.array([sum(bandit.COST[a]) for a in bandit.ARMS])
    got = np.array([sh[a] for a in bandit.ARMS])
    # The residual spread is Thompson sampling noise across 400 draws from eleven IDENTICAL
    # posteriors, which is exploration doing its job. What must be gone is any relationship to
    # PRICE: that is the thing the clamp was supposed to remove and only half removed.
    assert abs(float(np.corrcoef(1.0 / cost, got)[0, 1])) < 0.35, dict(zip(bandit.ARMS, got))
    assert max(sh.values()) - min(sh.values()) < 0.05, sh


def test_a_broken_credit_cannot_change_an_allocation() -> None:
    base = bandit.allocate(_flat_evidence(), np.random.default_rng(0))
    same = bandit.allocate(_flat_evidence(), np.random.default_rng(0),
                           credit={a: 1.0 for a in bandit.ARMS})
    assert base == same
    none = bandit.allocate(_flat_evidence(), np.random.default_rng(0), credit=None)
    assert base == none


def test_every_arm_has_a_declared_breadth_weight_and_occupied_share() -> None:
    """A new arm that nobody classified would silently take the default. Both tables must cover
    the arm list exactly, or the credit is a guess wearing a measurement's name."""
    from libs.research.breadth_credit import ARM_OCCUPIED_SHARE
    assert set(ARM_BREADTH_WEIGHT) == set(bandit.ARMS)
    assert set(ARM_OCCUPIED_SHARE) == set(bandit.ARMS)
    assert all(0.0 <= v <= 1.0 for v in ARM_BREADTH_WEIGHT.values())
    assert all(0.0 <= s <= 1.0 and w for s, w in ARM_OCCUPIED_SHARE.values())


def test_the_bandit_still_writes_a_budget_when_the_credit_is_unavailable() -> None:
    doc = bandit.run(seed=0, write=False)
    assert set(doc["shares"]) == set(bandit.ARMS)
    assert math.isclose(sum(doc["shares"].values()), 1.0, abs_tol=0.01)
    assert "breadth_credit" in doc
