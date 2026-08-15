"""Leverage as much as growth permits -- pinned on the arithmetic that makes "permits" a maximum.

The instruction was "no fixed ceiling, minimum 3x, as much as growth permits". The first two are
settings. The third is a computation, and its answer is a MAXIMUM: past Kelly, more leverage buys
less growth, and past 2x Kelly it buys negative growth. These tests exist so that fact stays in the
code rather than in a conversation.
"""

from __future__ import annotations

import math

import pytest

from libs.execution import binance_margin_live as margin
from libs.execution.leverage_policy import (
    MIN_LEVERAGE,
    VENUE_MAX_LEVERAGE,
    choose,
    growth_rate,
    kelly_leverage,
    leverage_for_distance,
    realised_vol,
)


def test_GROWTH_IS_A_DOWNWARD_PARABOLA_PEAKING_AT_KELLY() -> None:
    """THE WHOLE ARGUMENT. If this is not true, "as much as growth permits" would mean "as much as
    possible", and the desk's objective would be unbounded in leverage."""
    mu, sigma = 0.60, 0.60
    f_star = kelly_leverage(mu, sigma)
    assert abs(f_star - mu / sigma ** 2) < 1e-12
    peak = growth_rate(f_star, mu, sigma)
    for f in (f_star * 0.5, f_star * 0.9, f_star * 1.1, f_star * 2.0, f_star * 3.0):
        assert growth_rate(f, mu, sigma) <= peak + 1e-12, (
            f"growth at {f:.2f}x exceeds the Kelly peak -- the objective is not being maximised "
            "at f*, and every conclusion drawn from it is wrong")


def test_GROWTH_IS_ZERO_AT_TWICE_KELLY_AND_NEGATIVE_BEYOND() -> None:
    """The number that turns 'aggressive' into 'worse'. A book past 2x Kelly with a positive
    expected return compounds to zero almost surely."""
    mu, sigma = 0.60, 0.60
    f_star = kelly_leverage(mu, sigma)
    assert abs(growth_rate(2 * f_star, mu, sigma)) < 1e-12
    assert growth_rate(2.5 * f_star, mu, sigma) < 0


def test_THE_BORROW_COST_COMES_OFF_THE_NUMERATOR() -> None:
    """Levered capital is rented. Omitting the rent overstates Kelly by exactly the rate paid --
    the direction that over-levers."""
    free = kelly_leverage(0.60, 0.60, borrow_rate=0.0)
    paid = kelly_leverage(0.60, 0.60, borrow_rate=0.10)
    assert paid < free
    assert kelly_leverage(0.05, 0.60, borrow_rate=0.10) == 0.0, (
        "an edge that does not beat its own borrow cost must return zero leverage; borrowing more "
        "of a losing trade does not make it a winning one")


def test_THE_LIQUIDATION_BOUND_INVERTS_THE_CONNECTORS_OWN_FORMULA() -> None:
    """Two modules computing the same relationship must agree, or one of them is silently wrong on
    the path that ends the account."""
    for lev in (2.0, 3.0, 5.0, 8.0):
        d = margin.liquidation_distance(lev)
        assert abs(leverage_for_distance(d) - lev) < 1e-9


def test_THE_SMALLER_OF_GROWTH_AND_SURVIVAL_WINS() -> None:
    """Kelly is about compounding; liquidation is about surviving to compound. Neither substitutes
    for the other, so the binding one must be the minimum and must be NAMED."""
    d = choose(0.03, sharpe=1.0, borrow_rate=0.08)
    assert d["binding_constraint"] in {"growth (Kelly)", "survival", "venue/ceiling"}
    assert d["raw_leverage"] <= d["survival_leverage"] + 1e-9
    assert d["raw_leverage"] <= d["kelly"] + 1e-9


def test_A_STRONG_EDGE_CAN_EXCEED_EIGHT_BECAUSE_NOTHING_IS_HARDCODED() -> None:
    """THE INSTRUCTION, HONOURED. The ceiling moves with the evidence: a high-Sharpe, low-vol book
    is allowed past 8x, because at that point growth genuinely permits it."""
    d = choose(0.004, sharpe=4.0, borrow_rate=0.02, k=1.0)
    assert d["kelly"] > 8.0, f"a Sharpe-4 book at 0.4%/day vol has Kelly {d['kelly']}, not <8"
    assert d["leverage"] > 8.0


def test_FULL_KELLY_IS_THE_DEFAULT_BECAUSE_IT_IS_THE_MAXIMUM() -> None:
    """Principal's instruction 2026-08-15: grow as fast as possible. Full Kelly IS the growth
    maximum; taking a fraction of it is choosing a slower book on purpose."""
    from libs.execution.leverage_policy import DEFAULT_KELLY_FRACTION
    assert DEFAULT_KELLY_FRACTION == 1.0


def test_THE_SHARPE_IS_DISCOUNTED_FOR_ESTIMATION_ERROR_NOT_THE_KELLY_FRACTION() -> None:
    """THE SHAPE THAT MATTERS. A fixed fraction never rises -- it stays timid forever however much
    evidence arrives. A confidence-discounted Sharpe RISES as n grows, which is the right response
    to a desk that is accumulating forward observations."""
    from libs.execution.leverage_policy import sharpe_lower_bound
    thin = sharpe_lower_bound(1.0, 30)
    thick = sharpe_lower_bound(1.0, 5000)
    assert thin < thick < 1.0, "more observations must buy more exposure, never less"
    assert sharpe_lower_bound(1.0, 1) == 0.0, "one observation supports no leverage at all"
    lo = choose(0.03, sharpe=1.0, n_obs=30, borrow_rate=0.0)
    hi = choose(0.03, sharpe=1.0, n_obs=5000, borrow_rate=0.0)
    assert lo["kelly"] < hi["kelly"]


def test_BOTH_MODULES_DISCOUNT_THE_SHARPE_IDENTICALLY() -> None:
    """Leverage and gross exposure are the same decision expressed twice. Two different confidence
    adjustments would let the book run one size while reporting another."""
    from libs.execution.leverage_policy import sharpe_lower_bound as a
    from libs.research.vol_target import sharpe_lower_bound as b
    for s_, n in ((0.5, 2534), (1.2, 90), (2.0, 400)):
        assert abs(a(s_, n) - b(s_, n)) < 1e-12


def test_THE_FLOOR_IS_FULLY_INVESTED_AND_CANNOT_FORCE_A_BORROW() -> None:
    """THE CHANGE THAT MATTERS. A 3.0 floor was set and removed the same day: the live book's Kelly
    was 1.49x and its ZERO-GROWTH point 2.99x, so 3.0 forced the one configuration the objective
    forbids -- roughly zero expected growth carrying full liquidation risk.

    1.0 cannot do that. It is unlevered by definition, so it can never push a book past its own
    zero-growth line; it only says 'do not hold idle cash on a margin account'."""
    assert MIN_LEVERAGE == 1.0
    weak = choose(0.05, sharpe=0.2, n_obs=4000, borrow_rate=0.08)
    assert weak["leverage"] == 1.0, "a thin edge is held fully invested, never borrowed against"
    assert weak["floor_binding"] is True


def test_THE_FLOOR_NEVER_EXCEEDS_THE_ZERO_GROWTH_POINT() -> None:
    """THE PROPERTY THE 3.0 FLOOR VIOLATED, asserted so it cannot come back. Any floor at or above
    2x Kelly forces negative-growth leverage on a book that cannot support it."""
    for sharpe, sigma in ((0.2, 0.05), (0.5, 0.03), (1.0, 0.04)):
        d = choose(sigma, sharpe=sharpe, n_obs=2000, borrow_rate=0.10)
        if d["zero_growth_leverage"]:
            assert max(1.0, d["zero_growth_leverage"]) >= MIN_LEVERAGE, (
                "the floor forces leverage past the point where growth turns negative")


def test_A_STRONG_EDGE_STILL_LEVERS_ABOVE_THE_FLOOR() -> None:
    """Maximum growth means levering up when the edge supports it. The floor is a minimum, not a
    target."""
    strong = choose(0.01, sharpe=2.5, n_obs=4000, borrow_rate=0.02)
    assert strong["leverage"] > 1.0


def test_UNMEASURED_VOLATILITY_TAKES_THE_FLOOR_NOT_THE_CEILING() -> None:
    """The direction that survives being wrong. Choosing high leverage from an absent measurement
    is inventing confidence out of missing data, on the one path that can end the account."""
    for bad in (None, float("nan"), 0.0, 0.0001):
        d = choose(bad, sharpe=3.0)
        assert d["leverage"] == MIN_LEVERAGE
        assert d["state"] == "UNMEASURED"


def test_WITHOUT_A_SHARPE_ONLY_SURVIVAL_BINDS_AND_IT_SAYS_SO() -> None:
    """Half the calculation missing must be visible as missing, not silently dropped."""
    d = choose(0.03)
    assert d["kelly"] is None
    assert d["binding_constraint"] in {"survival", "venue/ceiling"}


def test_REALISED_VOL_IS_NONE_NOT_ZERO_WHEN_UNESTIMABLE() -> None:
    """Zero divides into infinite leverage -- the one value a missing-data path would most
    naturally produce is the one that must never appear."""
    assert realised_vol([]) is None
    assert realised_vol([0.01, 0.02]) is None
    assert realised_vol([0.0] * 40) is None, "a flat series is not 0% vol, it is unmeasurable here"
    v = realised_vol([0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, 0.02])
    assert v is not None and v > 0


def test_THE_VENUE_CEILING_IS_NOT_A_RISK_PREFERENCE() -> None:
    """It exists so the policy cannot emit an order the venue refuses -- a refused order at
    rebalance time is an intent nobody notices."""
    d = choose(0.002, sharpe=10.0, borrow_rate=0.0, k=0.5)
    assert d["leverage"] <= VENUE_MAX_LEVERAGE


def test_THE_DECISION_NEVER_PUBLISHES_A_NUMBER_WITHOUT_ITS_BASIS() -> None:
    d = choose(0.03, sharpe=1.0)
    for key in ("sigma", "survivable_move", "survival_leverage", "binding_constraint", "why"):
        assert key in d, f"{key} missing -- a leverage published bare is half the trade"
    assert "not a tail-risk control" in d["why"]


def test_THE_SIGMA_ANNUALISATION_USES_A_365_DAY_YEAR() -> None:
    """Crypto does not close. A 252-day year understates annual vol by ~20%, which overstates
    Kelly by ~45% -- the error compounds in the direction that over-levers."""
    d = choose(0.03, sharpe=1.0)
    # the field is rounded for reporting, so compare at the reporting precision
    assert abs(d["sigma_annual"] - 0.03 * math.sqrt(365.0)) < 1e-4


def test_INTEREST_IS_CHARGED_ON_THE_BORROWED_PART_NOT_THE_WHOLE_POSITION() -> None:
    """At f=1.0 nothing is borrowed, so no interest is due. The old form read
    `f*(mu - borrow)` and billed the rate against the principal's own equity too -- understating
    every published growth number by exactly `r`, which at the live 5.1% venue rate was most of a
    small book's expected growth."""
    mu, sigma, r = 0.0816, 0.17, 0.051
    assert growth_rate(1.0, mu, sigma, borrow_rate=r) == pytest.approx(
        growth_rate(1.0, mu, sigma, borrow_rate=0.0)), "an unlevered book pays no interest"
    # and a levered one pays on (f-1) only
    assert growth_rate(3.0, mu, sigma, borrow_rate=r) == pytest.approx(
        3.0 * mu - 2.0 * r - 9.0 * sigma * sigma / 2)


def test_THE_KELLY_POINT_IS_UNCHANGED_BY_THE_FIX() -> None:
    """The two forms differ by the CONSTANT r, so their derivatives are identical -- which is
    exactly why the error survived: every comparison between two leverages came out the same and
    only the LEVEL was wrong. Pinned so a future 'simplification' back to f*(mu-r) is caught."""
    mu, sigma, r = 0.0816, 0.17, 0.051
    f_star = kelly_leverage(mu, sigma, borrow_rate=r)
    for delta in (0.05, 0.2, 0.5):
        assert growth_rate(f_star, mu, sigma, borrow_rate=r) > growth_rate(
            f_star + delta, mu, sigma, borrow_rate=r)
        assert growth_rate(f_star, mu, sigma, borrow_rate=r) > growth_rate(
            max(0.0, f_star - delta), mu, sigma, borrow_rate=r)


# ---------------------------------------------------- THE MARGIN-CALL BAND (added 2026-08-15)
def test_A_FRESH_POSITION_HITS_THE_CALL_BAND_AT_EXACTLY_THREE_X() -> None:
    """Entry level is f/(f-1), fixed the instant the order fills. At Binance's 1.5 call level that
    is 3.00x -- above it the account opens ALREADY IN MARGIN CALL, before the market has moved."""
    from libs.execution.leverage_policy import MARGIN_CALL_LEVEL, leverage_at_margin_call

    assert MARGIN_CALL_LEVEL == 1.5
    assert leverage_at_margin_call() == pytest.approx(3.0)
    assert leverage_at_margin_call(2.0) == pytest.approx(2.0)
    assert leverage_at_margin_call(1.1) == pytest.approx(11.0)   # the liquidation line


def test_A_VENUE_THAT_NEVER_CALLS_IMPOSES_NO_BOUND() -> None:
    from libs.execution.leverage_policy import leverage_at_margin_call

    assert leverage_at_margin_call(1.0) == float("inf")


def test_THE_BAND_DEFAULTS_OFF_BECAUSE_ONLY_A_BORROWING_BOOK_CAN_BE_CALLED() -> None:
    """A spot book at 1x has no liability and no level. Applying the bound there would refuse
    leverage against a hazard that cannot occur -- and would silently lower a ceiling the principal
    set at 8x, which is theirs to move."""
    assert choose(0.03)["binding_constraint"] in {"survival", "venue/ceiling"}


def test_THE_BAND_BINDS_WHEN_PASSED_AND_CUTTING_COSTS_IS_WHAT_MAKES_IT_BIND() -> None:
    """Kelly is (mu-r)/sigma^2, so cheaper execution RAISES it. The maker routing and the BNB
    interest discount moved this book's optimum from 2.31x through the 3.00x line -- a saving that
    walks the book into a margin call is not a saving."""
    dear = choose(0.0089, sharpe=0.69, n_obs=5000, borrow_rate=0.051, margin_call_level=1.5)
    cheap = choose(0.0089, sharpe=0.83, n_obs=5000, borrow_rate=0.0382, margin_call_level=1.5)
    assert cheap["kelly"] > dear["kelly"], "the cost work must raise the growth optimum"
    assert cheap["leverage"] <= 3.0 + 1e-9
    assert cheap["binding_constraint"] == "margin-call band"
    assert "ALREADY IN MARGIN CALL" in cheap["why"]


def test_THE_BAND_NEVER_RAISES_LEVERAGE_ONLY_LOWERS_IT() -> None:
    for sh in (0.2, 0.5, 0.9, 1.5):
        free = choose(0.02, sharpe=sh, n_obs=2000, borrow_rate=0.04)
        held = choose(0.02, sharpe=sh, n_obs=2000, borrow_rate=0.04, margin_call_level=1.5)
        assert held["leverage"] <= free["leverage"] + 1e-9
