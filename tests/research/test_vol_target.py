"""Gross exposure at the growth optimum -- pinned on the identity and on what makes it dynamic.

THE IDENTITY: at the Kelly optimum, portfolio volatility EQUALS the Sharpe ratio. f* = S/sigma, so
the vol actually run is f*sigma = S. That is why the target is computed rather than chosen, and why
"target 50% vol" and "run full Kelly on a Sharpe-0.5 book" are the same instruction.
"""

from __future__ import annotations

from libs.research.vol_target import (
    DEFAULT_KELLY_FRACTION,
    DEFAULT_MIN_GROSS,
    REBALANCE_BAND,
    gross_exposure,
    growth_optimal_vol,
    sharpe_lower_bound,
)


def test_THE_GROWTH_OPTIMAL_VOL_IS_THE_SHARPE() -> None:
    """Not a risk budget somebody picked -- the same arithmetic as Kelly in portfolio units."""
    assert growth_optimal_vol(1.0, kelly_fraction=1.0) == 1.0
    assert growth_optimal_vol(0.50, kelly_fraction=1.0) == 0.50
    assert growth_optimal_vol(0.50, kelly_fraction=0.5) == 0.25


def test_FULL_KELLY_IS_THE_DEFAULT() -> None:
    """Principal's instruction: grow as fast as possible. Full Kelly is the maximum, not an
    overshoot of it, and a fraction of it is a slower book chosen on purpose."""
    assert DEFAULT_KELLY_FRACTION == 1.0


def test_A_NON_POSITIVE_SHARPE_TARGETS_NO_VOLATILITY() -> None:
    """A book with no measured edge has a growth-optimal exposure of zero. Inventing a floor here
    would be inventing an edge."""
    assert growth_optimal_vol(-0.5) == 0.0
    assert growth_optimal_vol(0.0) == 0.0


def test_EXPOSURE_RISES_AS_EVIDENCE_ACCUMULATES() -> None:
    """THE POINT OF DISCOUNTING THE SHARPE RATHER THAN THE KELLY FRACTION. A fixed fraction never
    rises however much the desk learns; a confidence-discounted Sharpe does, automatically."""
    thin = gross_exposure(0.03, sharpe=1.0, n_obs=40)
    thick = gross_exposure(0.03, sharpe=1.0, n_obs=4000)
    assert thin.target_vol < thick.target_vol
    assert thin.raw_gross < thick.raw_gross
    assert sharpe_lower_bound(1.0, 1) == 0.0, "one observation supports no exposure"


def test_GROSS_MOVES_INVERSELY_WITH_REALISED_VOL() -> None:
    """The whole mechanism: hold RISK constant, let exposure float. A fixed gross runs too hot in
    violent clusters and too cold in quiet ones, and the variance drag punishes the hot half more
    than the cold half rewards."""
    quiet = gross_exposure(0.015, sharpe=1.0, n_obs=1000)
    loud = gross_exposure(0.06, sharpe=1.0, n_obs=1000)
    assert quiet.raw_gross > loud.raw_gross


def test_IT_IS_CAPPED_AND_THE_CAP_COMES_FROM_THE_SAME_ESTIMATE() -> None:
    """Past the Kelly point more exposure LOWERS growth, so a flattering Sharpe must never push
    the book past the cap. Unlevered that cap is 1.0 -- a spot account cannot hold more than it
    paid for."""
    d = gross_exposure(0.005, sharpe=3.0, n_obs=5000, max_gross=1.0)
    assert d.gross == 1.0 and d.state == "CAPPED"


def test_UNMEASURED_VOL_SHEDS_RATHER_THAN_LEANS_IN() -> None:
    """Being under-exposed costs return; being over-exposed on a tape nobody has measured costs
    the account. The asymmetry decides the direction of the default."""
    for bad in (None, 0.0, -1.0, float("nan")):
        d = gross_exposure(bad, sharpe=2.0, n_obs=5000)
        assert d.gross == DEFAULT_MIN_GROSS and d.state == "UNMEASURED"


def test_NO_SHARPE_MEANS_NO_OPTIMUM_TO_AIM_AT() -> None:
    """The target is a function of the EDGE. Without one there is no growth optimum, and guessing
    would be inventing the very thing being sized against."""
    d = gross_exposure(0.03, sharpe=None)
    assert d.state == "NO-EDGE-ESTIMATE" and d.gross == DEFAULT_MIN_GROSS


def test_IT_NEVER_DE_GROSSES_TO_ZERO_FROM_A_VOL_READING() -> None:
    """A book that goes flat has to time its own re-entry, which is a second and harder bet nobody
    asked for. Shedding is risk control; going to cash is a market call."""
    d = gross_exposure(0.40, sharpe=0.2, n_obs=1000)
    assert d.gross == DEFAULT_MIN_GROSS and d.state == "FLOORED"


def test_THE_BAND_SUPPRESSES_CHURN_BUT_NOT_A_REAL_MOVE() -> None:
    """Sigma wobbles daily; trading every wobble pays turnover for noise. A move that clears the
    band must still go through."""
    d = gross_exposure(0.03, sharpe=1.0, n_obs=1000)
    inside = gross_exposure(0.03, sharpe=1.0, n_obs=1000,
                            current_gross=d.gross * (1 + REBALANCE_BAND / 2))
    assert inside.gross != d.gross, "a move inside the band holds the current gross"
    outside = gross_exposure(0.03, sharpe=1.0, n_obs=1000, current_gross=d.gross * 2.0)
    assert abs(outside.gross - d.gross) < 1e-9, "a move past the band must be taken"


def test_NOTHING_IS_PUBLISHED_WITHOUT_ITS_BASIS() -> None:
    d = gross_exposure(0.03, sharpe=1.0, n_obs=1000)
    row = d.as_row()
    for k in ("target_vol", "realised_vol", "raw_gross", "state", "why"):
        assert k in row, f"{k} missing -- a gross published bare is a number nobody can audit"
    assert "standard error" in d.why
