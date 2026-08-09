"""The event clock must count evidence, not rows -- and must never invent it.

The whole risk in this module is arithmetic that looks like an improvement while loosening every
downstream bar. "Funding settles 3x a day so 28 days is 84 observations" inflates every t by
sqrt(3). These tests pin the discount, the clamp, and the fact that the bar itself never moves.
"""

from __future__ import annotations

import math
import random

from libs.research.event_density import (
    DAILY_PPY,
    EventClock,
    effective_n,
    event_clock,
    forward_verdict,
    lag1_autocorr,
    t_from_annual_sharpe,
    verdict_line,
)
from libs.research.evidence_clock import MIN_OBS, MIN_T


def _ar1(n: int, rho: float, seed: int, mean: float = 0.0, sd: float = 1.0) -> list[float]:
    rng = random.Random(seed)
    out, prev = [], 0.0
    for _ in range(n):
        prev = rho * prev + rng.gauss(0.0, sd)
        out.append(mean + prev)
    return out


# ---------------------------------------------------------------------------------------------
# The clamp. This is the defect class the module exists to not reproduce.
# ---------------------------------------------------------------------------------------------

def test_effective_n_can_never_exceed_the_events_observed() -> None:
    """A 4,314-row screen once reported n_eff = 1,236,384. This arithmetic may only take away."""
    for rho in (-0.99, -0.9, -0.5, -0.1, 0.0):
        assert effective_n(100, rho) <= 100.0, rho
    assert effective_n(100, -0.99) == 100.0


def test_effective_n_discounts_positive_autocorrelation() -> None:
    assert effective_n(100, 0.0) == 100.0
    assert math.isclose(effective_n(90, 0.5), 30.0, rel_tol=1e-9)
    assert effective_n(100, 0.9) < 6.0
    assert effective_n(100, 0.99) >= 1.0          # floors at 1, never 0 or negative


def test_effective_n_of_no_events_is_zero_not_one() -> None:
    assert effective_n(0, 0.0) == 0.0


def test_autocorr_is_bounded_and_neutral_on_degenerate_input() -> None:
    assert lag1_autocorr([1.0] * 50) == 0.0        # constant series: no defined rho
    assert lag1_autocorr([1.0, 2.0]) == 0.0        # below MIN_FOR_RHO
    assert -1.0 < lag1_autocorr(_ar1(200, 0.8, 1)) < 1.0
    assert lag1_autocorr(_ar1(400, 0.8, 2)) > 0.5


# ---------------------------------------------------------------------------------------------
# The point of the module: dense INDEPENDENT evidence clears sooner; dense DEPENDENT does not.
# ---------------------------------------------------------------------------------------------

def test_independent_events_clear_the_same_bar_in_fewer_days() -> None:
    n = 90                                          # 3/day for 30 days
    rng = random.Random(11)
    vals = [rng.gauss(0.0015, 0.004) for _ in range(n)]
    stamps = [i * (86400 / 3) for i in range(n)]
    c = event_clock(vals, stamps, mechanism="iid")
    assert c.sufficient, c.reason
    assert c.discount > 0.6                         # barely discounted -- events are independent
    assert c.span_days < 31                          # cleared well inside a 90-day calendar gate
    assert math.isclose(c.events_per_day, 3.0, rel_tol=0.05)


def test_autocorrelated_events_are_discounted_not_credited() -> None:
    """Same row count, same span -- but the evidence is worth a fraction of it."""
    n = 90
    vals = [0.0015 + v * 0.002 for v in _ar1(n, 0.8, 3)]
    stamps = [i * (86400 / 3) for i in range(n)]
    c = event_clock(vals, stamps, mechanism="ar1")
    assert c.autocorr > 0.4, c.autocorr
    assert c.n_effective < n / 2, c
    assert c.discount < 0.5


def test_the_bar_is_imported_never_restated() -> None:
    """This module has no vocabulary in which to lower a bar -- it uses evidence_clock's."""
    import inspect

    import libs.research.event_density as ed
    src = inspect.getsource(ed)
    # No local redefinition of the two constants that decide sufficiency.
    assert "MIN_T =" not in src and "MIN_OBS =" not in src
    assert ed.MIN_T is MIN_T and ed.MIN_OBS is MIN_OBS


def test_shortfall_is_reported_in_events_with_a_measured_eta() -> None:
    """'You need K more events at your measured rate' is actionable; 'wait 90 days' is not.

    This case is the one worth pinning: the t already CLEARS 2.0, but 30 autocorrelated events are
    worth only ~11 effective ones, so the observation floor still binds. The caller is told how
    many EVENTS that is and how long at its own measured rate -- neither of which a day-gate knows.
    """
    n = 30
    vals = [0.0018 + v * 0.004 for v in _ar1(n, 0.3, 1)]
    stamps = [i * (86400 / 2) for i in range(n)]     # 2/day, measured
    c = event_clock(vals, stamps, mechanism="thin")
    assert not c.sufficient and c.t_stat > MIN_T     # t clears; the effective-n floor does not
    assert c.n_effective < MIN_OBS
    assert c.events_short > 0
    assert c.eta_days and c.eta_days > 0
    assert "more event(s)" in verdict_line(c)


def test_a_non_positive_effect_is_told_that_more_data_will_not_fix_it() -> None:
    """The one honest answer a day-gate can never give: this is the wrong sign, stop waiting."""
    c = event_clock([-0.001 + v * 0.004 for v in _ar1(40, 0.2, 5)], None, mechanism="neg")
    assert not c.sufficient
    assert c.events_short == 0 and c.eta_days is None
    assert "will not fix it" in c.reason


def test_no_events_is_unmeasured_never_a_pass() -> None:
    c = event_clock([], None, mechanism="empty")
    assert not c.sufficient and c.n_events == 0
    assert "unmeasured" in c.reason
    assert isinstance(c, EventClock)


def test_rate_is_measured_from_stamps_not_assumed() -> None:
    """A mechanism claiming 3/day and delivering 1.2 is credited 1.2 (L1.46)."""
    n = 36
    vals = [0.001] * n
    stamps = [i * 86400 / 1.2 for i in range(n)]
    c = event_clock(vals, stamps, mechanism="slow")
    assert math.isclose(c.events_per_day, 1.2, rel_tol=0.05)


def test_verdict_never_depends_on_stamps() -> None:
    """Stamps buy an ETA, never a pass -- a mechanism that cannot supply them is judged alike."""
    vals = [0.0015 + v * 0.002 for v in _ar1(60, 0.1, 9)]
    with_s = event_clock(vals, [i * 86400 for i in range(60)], mechanism="a")
    without = event_clock(vals, None, mechanism="a")
    assert with_s.sufficient == without.sufficient
    assert with_s.t_stat == without.t_stat
    assert with_s.n_effective == without.n_effective


# ---------------------------------------------------------------------------------------------
# t_from_annual_sharpe -- the conversion the live capital gate was missing entirely.
# ---------------------------------------------------------------------------------------------

def test_annual_sharpe_alone_cannot_distinguish_sample_sizes() -> None:
    """The exact defect: `sharpe > 0` reads 0.29-on-33 identically to 0.29-on-3300."""
    assert t_from_annual_sharpe(0.29, 33, periods_per_year=365) < 0.2
    assert t_from_annual_sharpe(0.29, 3300, periods_per_year=365) > 0.8


def test_the_live_capital_gate_case_is_below_the_bar() -> None:
    """web/crypto_shadow.json on 2026-08-05: Sharpe 0.29 over 33 days published validated=True."""
    t = t_from_annual_sharpe(0.29, 33, periods_per_year=365.0)
    assert round(t, 3) == 0.087
    assert t < MIN_T


def test_annualisation_factor_must_match_the_producer() -> None:
    """Inverting a 365-annualised Sharpe with the 252 default inflates t by ~20%."""
    a = t_from_annual_sharpe(1.0, 100, periods_per_year=252.0)
    b = t_from_annual_sharpe(1.0, 100, periods_per_year=365.0)
    assert a > b
    assert math.isclose(a / b, math.sqrt(365.0 / 252.0), rel_tol=1e-9)


def test_t_refuses_degenerate_inputs() -> None:
    assert t_from_annual_sharpe(1.0, 0) == 0.0
    assert t_from_annual_sharpe(float("nan"), 100) == 0.0
    assert t_from_annual_sharpe(1.0, 100, periods_per_year=0.0) == 0.0
    assert DAILY_PPY == 252.0


# ---------------------------------------------------------------------------------------------
# forward_verdict -- both directions, which is how you can tell it is not a loosening.
# ---------------------------------------------------------------------------------------------

def test_a_fast_book_is_promoted_before_ninety_days() -> None:
    """40 observations at a carry-grade Sharpe clears -- the calendar would have held it to 90.

    8.0 is not a fantasy figure here: web/cashcarry_shadow.json carries a forward annualised
    Sharpe of 14.84 and its own Newey-West t of 2.48 at day 40, and the calendar gate made it wait
    anyway. At ppy=365, t = 8.0*sqrt(40/365) = 2.65.
    """
    v = forward_verdict(40, 8.0, 2.0, periods_per_year=365.0)
    assert v.startswith("ON TRACK"), v


def test_ninety_days_at_a_mediocre_sharpe_was_never_evidence() -> None:
    """What the old gate passed: day 90, Sharpe 0.5 -- t = 0.25. It cleared on the calendar."""
    assert t_from_annual_sharpe(0.5, 90, periods_per_year=365.0) < 0.3
    v = forward_verdict(90, 0.5, 0.5, periods_per_year=365.0)
    assert v.startswith("ACCUMULATING"), v


def test_a_slow_book_no_longer_clears_on_the_technicality_of_existing() -> None:
    """THE CASE THE CALENDAR WAS SILENTLY PASSING: day 90+, t well under the bar."""
    v = forward_verdict(120, 0.4, 0.5, periods_per_year=365.0)
    assert v.startswith("ACCUMULATING"), v
    assert "t=" in v


def test_negative_forward_is_still_a_kill_first() -> None:
    v = forward_verdict(200, -0.8, 1.0, periods_per_year=365.0)
    assert v.startswith("FAILING FORWARD"), v


def test_too_few_observations_is_never_a_pass_however_good_the_sharpe() -> None:
    v = forward_verdict(MIN_OBS - 1, 40.0, 1.0, periods_per_year=365.0)
    assert v.startswith("ACCUMULATING") and "too few" in v


def test_clearing_the_t_but_not_the_sharpe_floor_stays_undeployed() -> None:
    """t >= bar is necessary and NOT sufficient: the economic floor still has to be cleared."""
    assert t_from_annual_sharpe(0.4, 12_000, periods_per_year=365.0) > MIN_T
    v = forward_verdict(12_000, 0.4, 0.5, periods_per_year=365.0)
    assert v.startswith("WEAK forward"), v


def test_callers_keep_their_own_wording() -> None:
    v = forward_verdict(200, -1.0, 1.0, kill_action="kill challenger (regime gate did not help)")
    assert "kill challenger" in v
    v2 = forward_verdict(5, 1.0, 1.0, accruing_tail=" -- zero capital until it holds")
    assert v2.endswith("zero capital until it holds")


def test_every_shadow_runner_passes_its_own_annualisation() -> None:
    """A 365-annualised Sharpe inverted at the 252 default is a 20% silent loosening."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[2]
    for name in ("run_shadow_forward", "run_crossasset_shadow", "run_crypto_shadow",
                 "run_trend_shadow", "run_trend_regime_shadow"):
        src = (root / f"scripts/{name}.py").read_text("utf-8")
        assert "forward_verdict(" in src, name
        assert "periods_per_year=_PPY" in src, f"{name} does not pass its own _PPY"
        assert re.search(r"^_PPY\s*=", src, re.M), name
