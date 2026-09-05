"""The two estimators that decide whether the macro layer is intelligence or a news bot.

PRICED VERSUS UNPRICED. If the move already happened there is nothing to trade, however credible
and well-understood the event is. These pin that the estimate is zero when the desk was late,
UNMEASURED (never 1.0) when the category has no denominator, UNMEASURABLE when the desk's bars
are coarser than the question, and that uncertainty can only ever make the desk abstain -- never
act.

SURPRISE. The principal's own test is here by name: a hot CPI where real yields barely move and
the dollar sells off must NOT produce a mechanical short-gold. `interpret` takes its SIGN from
the measured cross-asset response, so the naive z reading loses the argument. That is the whole
difference between "what the number says" and "what the market is doing with the number".
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.ledger import CategoryStats  # noqa: E402
from macro.priced import (  # noqa: E402
    LARGE_MOVE_SIGMA,
    already_priced,
    estimate,
    realised_unpriced,
)
from macro.prices import FakePriceReader, synthetic_series  # noqa: E402
from macro.schema import Status, SurpriseEstimate  # noqa: E402
from macro.surprise import MIN_SURPRISE_N, interpret, z_score  # noqa: E402

T0 = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
SPAN = 60.0
#: History starts far enough back that the trailing sigma has well over MIN_VOL_BARS returns.
START = T0 - timedelta(seconds=SPAN * 400)


def _reader(jump: float = 0.0, jump_offset_bars: int = 401) -> FakePriceReader:
    """M1-shaped series for one symbol; `jump` lands `jump_offset_bars` after START."""
    series = synthetic_series(START, 800, SPAN, step=0.001,
                              jump_at=jump_offset_bars if jump else None, jump=jump)
    return FakePriceReader({"XAUUSD": series}, {"XAUUSD": SPAN})


def _stats(total: float = 4.0, n: int = 50) -> CategoryStats:
    return CategoryStats("inflation_release", n, n, total, 30.0, Status.MEASURED)


# ------------------------------------------------------------------- priced vs unpriced ----

def test_a_desk_that_arrived_before_the_move_has_everything_left() -> None:
    r = _reader()
    est = estimate(r, symbols=["XAUUSD"], published_at=T0.isoformat(),
                   received_at=(T0 + timedelta(seconds=120)).isoformat(), stats=_stats())
    assert est.status == Status.MEASURED
    assert est.unpriced_fraction is not None and est.unpriced_fraction > 0.9
    assert already_priced(est) is False


def test_a_desk_that_arrived_after_a_large_move_has_nothing_left() -> None:
    """The forty-dollars-of-gold case. High credibility, zero opportunity."""
    r = _reader(jump=0.05, jump_offset_bars=402)
    est = estimate(r, symbols=["XAUUSD"], published_at=T0.isoformat(),
                   received_at=(T0 + timedelta(seconds=600)).isoformat(), stats=_stats())
    assert est.status == Status.MEASURED
    assert est.pre_move_sigma is not None and est.pre_move_sigma > LARGE_MOVE_SIGMA
    assert est.unpriced_fraction == 0.0
    assert already_priced(est) is True


def test_a_category_with_no_denominator_is_UNMEASURED_never_defaulted_to_one() -> None:
    """Defaulting to 1.0 would say 'all of it is still tradeable' and would be the single most
    expensive default in the package."""
    r = _reader()
    thin = CategoryStats("brand_new", 3, 3, None, None, Status.UNMEASURED)
    est = estimate(r, symbols=["XAUUSD"], published_at=T0.isoformat(),
                   received_at=(T0 + timedelta(seconds=120)).isoformat(), stats=thin)
    assert est.status == Status.UNMEASURED
    assert est.unpriced_fraction is None
    assert "NOT defaulted to 1.0" in est.note
    # It still reports the pre-move: what CAN be measured is measured.
    assert est.pre_move_sigma is not None


def test_uncertainty_abstains_it_never_authorises() -> None:
    """No category denominator AND an obviously large pre-move: still UNMEASURED, but the desk
    treats it as priced. Not knowing whether we are late may never make us bold."""
    r = _reader(jump=0.05, jump_offset_bars=402)
    thin = CategoryStats("brand_new", 3, 3, None, None, Status.UNMEASURED)
    est = estimate(r, symbols=["XAUUSD"], published_at=T0.isoformat(),
                   received_at=(T0 + timedelta(seconds=600)).isoformat(), stats=thin)
    assert est.status == Status.UNMEASURED
    assert already_priced(est) is True
    assert "abstain" in est.note


def test_a_question_finer_than_the_bars_is_UNMEASURABLE_not_answered_with_an_hourly_move() -> None:
    hourly = FakePriceReader(
        {"XAUUSD": synthetic_series(START, 800, 3600.0, step=0.001)}, {"XAUUSD": 3600.0})
    est = estimate(hourly, symbols=["XAUUSD"], published_at=T0.isoformat(),
                   received_at=(T0 + timedelta(seconds=180)).isoformat(), stats=_stats())
    assert est.status == Status.UNMEASURABLE
    assert "UNMEASURABLE at this granularity" in est.note


def test_a_source_that_does_not_stamp_publication_makes_lateness_unknowable() -> None:
    est = estimate(_reader(), symbols=["XAUUSD"], published_at=None,
                   received_at=T0.isoformat(), stats=_stats())
    assert est.status == Status.UNMEASURED
    assert est.unpriced_fraction is None


def test_the_realised_fraction_is_measurable_so_the_estimator_can_be_marked() -> None:
    """Without this the unpriced estimate is an opinion that never gets scored."""
    r = _reader(jump=0.02, jump_offset_bars=402)
    got = realised_unpriced(r, symbols=["XAUUSD"], published_at=T0.isoformat(),
                            received_at=(T0 + timedelta(seconds=600)).isoformat(),
                            horizon_end=T0 + timedelta(seconds=6000))
    assert got is not None and 0.0 <= got <= 1.0


# --------------------------------------------------------------------------- surprise ----

def test_z_is_against_this_release_s_own_surprise_history() -> None:
    hist = [0.1, -0.1, 0.2, -0.2, 0.0, 0.1, -0.1, 0.15, -0.15, 0.05, 0.0, -0.05]
    est = z_score(actual=2.9, consensus=2.5, history=hist, release_id="US_CPI")
    assert est.status == Status.MEASURED
    assert est.z is not None and est.z > 0
    assert est.direction_from == "not_used_for_direction"


def test_thin_surprise_history_is_UNMEASURED_not_a_pooled_sigma() -> None:
    est = z_score(2.9, 2.5, [0.1] * (MIN_SURPRISE_N - 1), release_id="US_CPI")
    assert est.status == Status.UNMEASURED and est.z is None
    assert f"MIN_SURPRISE_N={MIN_SURPRISE_N}" in est.note


def test_missing_actual_is_named_as_the_licensed_calendar_gap() -> None:
    est = z_score(None, 2.5, [0.1] * 30)
    assert est.status == Status.UNMEASURED
    assert "no actual" in est.note


def test_the_hot_cpi_that_must_not_short_gold() -> None:
    """THE PRINCIPAL'S OWN TEST, pinned.

    CPI prints hot (z > 0). The mechanical reading is 'higher rates, gold down'. But the measured
    cross-asset response says real yields barely moved and the dollar SOLD OFF -- so the factor
    the desk actually observes is positive for the metal. The layer must follow the measurement.
    """
    hist = [0.1, -0.1, 0.2, -0.2, 0.0, 0.1, -0.1, 0.15, -0.15, 0.05, 0.0, -0.05]
    hot = z_score(actual=3.2, consensus=2.5, history=hist, release_id="US_CPI")
    assert hot.z is not None and hot.z > 0

    # What the market actually did: real yields flat, dollar lower, metal bid.
    measured = {"F1[+XAUUSD,+XAGUSD,-USDX]": +1.4, "F2[+UST10Y]": -0.05}
    out = interpret(hot, measured, unpriced_fraction=0.8)

    assert out.direction_from == "measured_factor_response"
    assert out.status == Status.MEASURED
    # The metal-loaded factor stays POSITIVE despite a positive z.
    assert out.factor_deltas["F1[+XAUUSD,+XAGUSD,-USDX]"] > 0
    # And the divergence is visible rather than silently resolved.
    assert out.mechanical_z_sign == 1
    assert out.diverges_from_mechanical is True


def test_with_no_measured_reaction_the_layer_refuses_rather_than_using_the_sign_of_z() -> None:
    """A layer that falls back to a sign table under time pressure IS a sign table."""
    hot = z_score(3.2, 2.5, [0.1, -0.1, 0.2, -0.2, 0.0, 0.1, -0.1, 0.15, -0.15, 0.05, 0.0])
    out = interpret(hot, {})
    assert out.status == Status.UNMEASURED
    assert out.factor_deltas == {}
    assert "NOT taken from the sign of z" in out.note


def test_conditioners_shrink_and_can_never_flip_a_sign() -> None:
    """A conditioner that can flip a sign is a second model smuggled in as an adjustment."""
    base = SurpriseEstimate(1.0, 1.0, 30, Status.MEASURED)
    measured = {"F1": +1.0}
    plain = interpret(base, measured)
    crowded = interpret(base, measured, positioning_z=4.0, liquidity_stress=3.0,
                        pre_event_move_sigma=2.5, credibility_uncertainty=2.0)
    assert plain.factor_deltas["F1"] > crowded.factor_deltas["F1"] > 0
    assert crowded.shrinkage < plain.shrinkage


def test_a_zero_unpriced_fraction_zeroes_the_response() -> None:
    """The arithmetic, not a remembered rule: nothing left to trade means nothing to do."""
    base = SurpriseEstimate(3.0, 1.0, 30, Status.MEASURED)
    out = interpret(base, {"F1": +2.0}, unpriced_fraction=0.0)
    assert out.factor_deltas["F1"] == 0.0
    assert out.magnitude == 0.0
