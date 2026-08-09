"""Tests for two-book sleeve allocation.

The load-bearing cases are the three that encode the principal's architecture:
  * an UNCORRELATED booster earns more than a correlated one at the SAME Sharpe (why a
    discretionary sleeve is fundable at all),
  * an UNPROVEN sleeve gets a learning stake rather than zero (else the evidence loop never
    closes and it can never earn size),
  * a DISPROVEN sleeve gets exactly zero (unproven and disproven are different states).
The rest check the guards hold.

COLLECTABILITY (2026-08-01). This shipped as a SCRIPT ending in `raise SystemExit`, which pytest
executes at COLLECTION -- killing the collector with INTERNALERROR exit 3 and running zero tests
repo-wide, from any file. Same defect as tests/test_marginal_admission.py, shipped by the very
next commit, 15 minutes after the desk recorded the lesson (L0057/R0337, commit 0240cfa) and
fixed a single instance without fencing the class. Converted to real test functions; the class is
fenced by tests/test_suite_collectable.py.
"""
from __future__ import annotations

from libs.risk import sleeve_allocation as sa


def plan(*sleeves, equity=100_000.0):
    return sa.allocate(list(sleeves), equity)


def by(p, name):
    return next(a for a in p.allocations if a.name == name)


BASE = sa.Sleeve("systematic", sharpe=1.20, n_closes=200, is_base=True)

# Deterministic fixtures -- no RNG here, but built at module level to match the file this
# replaces and to keep each test a pure read.
p_unc = plan(BASE, sa.Sleeve("disc", sharpe=0.60, n_closes=50, rho_to_base=0.0))
p_cor = plan(BASE, sa.Sleeve("disc", sharpe=0.60, n_closes=50, rho_to_base=0.90))
a_unc, a_cor = by(p_unc, "disc"), by(p_cor, "disc")

p_new = plan(BASE, sa.Sleeve("conviction", sharpe=0.0, n_closes=6, rho_to_base=0.0))
a_new = by(p_new, "conviction")
p_bad = plan(BASE, sa.Sleeve("conviction", sharpe=-0.40, n_closes=40, rho_to_base=0.0))
a_bad = by(p_bad, "conviction")

LOSING = sa.Sleeve("systematic", sharpe=-0.50, n_closes=200, is_base=True)
p_lose = plan(LOSING, sa.Sleeve("disc", sharpe=0.60, n_closes=50, rho_to_base=0.80))
a_lose = by(p_lose, "disc")

p_greedy = plan(BASE, sa.Sleeve("disc", sharpe=8.0, n_closes=500, rho_to_base=0.0))
p_many = plan(BASE, *[sa.Sleeve(f"d{i}", sharpe=3.0, n_closes=100, rho_to_base=0.0)
                      for i in range(6)])


# ---- the architecture ------------------------------------------------------------------------
def test_uncorrelated_booster_earns_more_than_correlated_at_equal_sharpe() -> None:
    assert a_unc.share > a_cor.share, (
        f"rho=0 -> {a_unc.share:.3f} vs rho=0.9 -> {a_cor.share:.3f}")


def test_correlated_booster_at_rho_0_9_earns_nothing() -> None:
    """The base already owns that exposure -- paying twice for it is the whole failure mode."""
    assert a_cor.share == 0.0, f"IR {a_cor.marginal_ir:+.3f}"


def test_a_booster_weaker_than_the_base_is_still_fundable_when_uncorrelated() -> None:
    assert a_unc.share > 0 and a_unc.marginal_ir > 0, (
        f"Sharpe 0.60 vs base 1.20, IR {a_unc.marginal_ir:+.3f}")


# ---- unproven vs disproven -------------------------------------------------------------------
def test_unproven_sleeve_gets_a_learning_stake_not_zero() -> None:
    assert a_new.state == "UNPROVEN-LEARNING-STAKE", a_new.state
    assert a_new.share == sa.LEARNING_STAKE, f"{a_new.share:.3f} on {a_new.n_closes} closes"


def test_disproven_sleeve_gets_exactly_zero() -> None:
    assert a_bad.state == "DISPROVEN-ZERO" and a_bad.share == 0.0


def test_unproven_and_disproven_are_distinguished() -> None:
    assert a_new.state != a_bad.state


# ---- the guard I nearly shipped broken -------------------------------------------------------
def test_booster_is_not_inflated_by_a_losing_base() -> None:
    assert a_lose.share <= sa.LEARNING_STAKE, (
        f"{a_lose.share:.3f} ({a_lose.state}) -- naive IR would have rewarded resembling a loser")


def test_losing_base_is_labelled_unproven() -> None:
    assert by(p_lose, "systematic").state == "BASE-UNPROVEN"


# ---- caps and conservation -------------------------------------------------------------------
def test_discretionary_share_is_hard_capped_regardless_of_measured_brilliance() -> None:
    assert by(p_greedy, "disc").share <= sa.MAX_DISCRETIONARY, (
        f"Sharpe 8.0 -> {by(p_greedy, 'disc').share:.3f}, cap {sa.MAX_DISCRETIONARY}")


def test_aggregate_booster_share_respects_the_cap_across_many_sleeves() -> None:
    tot = sum(a.share for a in p_many.allocations if a.name != "systematic")
    assert tot <= sa.MAX_DISCRETIONARY + 1e-9, f"{tot:.3f}"


def test_shares_always_sum_to_one() -> None:
    for q in (p_unc, p_cor, p_new, p_bad, p_lose, p_greedy, p_many):
        assert abs(sum(a.share for a in q.allocations) - 1.0) < 1e-9


def test_base_receives_the_residual() -> None:
    assert abs(by(p_unc, "systematic").share - (1.0 - a_unc.share)) < 1e-9


def test_usd_tracks_share() -> None:
    assert abs(by(p_unc, "disc").usd - a_unc.share * 100_000.0) < 1e-6


# ---- refusals --------------------------------------------------------------------------------
def test_refuses_with_no_base() -> None:
    assert not sa.allocate([sa.Sleeve("a", 1.0, 50)], 100.0).allocations


def test_refuses_with_two_bases() -> None:
    assert not sa.allocate([sa.Sleeve("a", 1.0, 50, is_base=True),
                            sa.Sleeve("b", 1.0, 50, is_base=True)], 100.0).allocations


def test_refuses_on_non_positive_equity() -> None:
    assert not sa.allocate([BASE], 0.0).allocations


# ---- monotonicity ----------------------------------------------------------------------------
def test_share_is_non_increasing_in_correlation_to_the_base() -> None:
    shares = [by(plan(BASE, sa.Sleeve("d", sharpe=0.6, n_closes=50, rho_to_base=r)), "d").share
              for r in (-0.5, 0.0, 0.3, 0.6, 0.9)]
    assert all(shares[i] >= shares[i + 1] - 1e-9 for i in range(len(shares) - 1)), (
        " -> ".join(f"{s:.3f}" for s in shares))


def test_negative_correlation_earns_the_most() -> None:
    shares = [by(plan(BASE, sa.Sleeve("d", sharpe=0.6, n_closes=50, rho_to_base=r)), "d").share
              for r in (-0.5, 0.0, 0.3, 0.6, 0.9)]
    assert shares[0] == max(shares), f"{shares[0]:.3f}"
