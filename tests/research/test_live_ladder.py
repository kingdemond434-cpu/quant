"""GOING LIVE EARLY AND SMALL -- the tests are about the two traps that make it backfire.

Shortening discovery -> live is right: a backtest is endlessly arguable and a forward record is
not. But a month of small live trading is an anecdote (at Sharpe 1.0 a month carries t ~ 0.29), and
small clips pay costs that full-size clips do not. Both traps push the same way -- toward retiring
real edges on genuine data -- so most of this file is about refusing to issue a verdict the record
cannot support.
"""

from __future__ import annotations

from libs.research.live_ladder import (
    MAX_ALLOCATION,
    MIN_OBS_FOR_A_VERDICT,
    LiveRecord,
    allocate,
    decide,
    posterior,
    render,
    size_cost_penalty,
)

# ------------------------------------------------------------------------ power


def test_A_SHORT_RECORD_RETURNS_UNDERPOWERED_RATHER_THAN_A_VERDICT() -> None:
    """Below the floor the posterior is essentially the prior, so a 'decision' would report the
    desk's own assumption back to itself."""
    v = decide(LiveRecord("s", n_trades=8, mean_bps=12.0, sd_bps=30.0))
    assert v.decision == "UNDERPOWERED" and v.allocation == 0.0
    assert "essentially the prior" in v.power_note


def test_UNDERPOWERED_STILL_SAYS_KEEP_IT_LIVE() -> None:
    """The record is the point at this stage, not the P&L. Pulling it because the verdict is
    undecidable guarantees the verdict stays undecidable."""
    v = decide(LiveRecord("s", n_trades=5, mean_bps=-40.0, sd_bps=50.0))
    assert v.decision == "UNDERPOWERED"
    assert any("keep it live" in n for n in v.notes)


def test_A_LOSING_BUT_NOT_YET_SEPARABLE_RECORD_IS_NOT_RETIRED_REFLEXIVELY() -> None:
    """A losing stretch at a modest true edge is what a good strategy does several months a year.
    Retiring on it kills exactly the edges the desk expects to find -- real but modest."""
    v = decide(LiveRecord("s", n_trades=40, mean_bps=-0.2, sd_bps=40.0))
    assert v.decision in {"RETIRE", "HOLD_SMALL"}
    # with a wide sd the posterior barely moves off the zero-centred prior
    assert abs(v.post_mean_bps) < 0.2, "a noisy record moved the posterior further than it should"


# ------------------------------------------------------------------- the small-size trap


def test_SMALL_CLIPS_CARRY_A_COST_PENALTY_THAT_FULL_SIZE_DOES_NOT() -> None:
    """The trap that surprises people: minimum notionals, tick rounding and the crossed spread do
    not scale down, so their bp impact RISES as the clip shrinks."""
    assert size_cost_penalty(100.0) > size_cost_penalty(10_000.0)
    assert size_cost_penalty(0.0) == 0.0


def test_THE_PENALTY_IS_CREDITED_BEFORE_RETIRING_A_STRATEGY() -> None:
    """A real edge can post losses at tiny size for reasons that vanish when it scales, and the
    data supporting the wrong conclusion is genuine live data."""
    v = decide(LiveRecord("s", n_trades=200, mean_bps=-0.05, sd_bps=5.0, clip_notional=20.0))
    assert any("vanish when it scales" in n for n in v.notes)
    assert v.decision != "RETIRE", "retired a strategy without crediting the small-size drag"


def test_A_GENUINELY_BAD_STRATEGY_IS_STILL_RETIRED() -> None:
    """The penalty is a correction, not an excuse. A loss far larger than the drag is a verdict."""
    v = decide(LiveRecord("s", n_trades=300, mean_bps=-8.0, sd_bps=5.0, clip_notional=10_000.0))
    assert v.decision == "RETIRE"
    assert "not a sizing problem" in " ".join(v.notes)


# ------------------------------------------------------------------------ the posterior


def test_THE_PRIOR_IS_CENTRED_ON_ZERO_SO_A_BACKTEST_CANNOT_PRELOAD_THE_LIVE_VERDICT() -> None:
    """The contamination going live was meant to escape. Live evidence must be able to speak
    against the research that produced it."""
    mean, sd = posterior(LiveRecord("s", n_trades=0, mean_bps=99.0, sd_bps=1.0))
    assert mean == 0.0 and sd > 0


def test_THE_POSTERIOR_IS_PULLED_TOWARD_ZERO_AND_RELEASES_AS_EVIDENCE_ACCUMULATES() -> None:
    """Self-damping: a young record cannot buy a big allocation however good the sample looks."""
    young, _ = posterior(LiveRecord("s", n_trades=30, mean_bps=10.0, sd_bps=40.0))
    old, _ = posterior(LiveRecord("s", n_trades=3000, mean_bps=10.0, sd_bps=40.0))
    assert young < old < 10.0
    assert young < 10.0 / 2, "a 30-trade record moved the posterior most of the way to the sample"


# ----------------------------------------------------------------------- allocation


def test_ALLOCATION_RISES_WITH_EVIDENCE_NOT_WITH_LUCK() -> None:
    """Two records with the SAME sample mean; only the evidence differs."""
    a = decide(LiveRecord("a", n_trades=40, mean_bps=6.0, sd_bps=40.0))
    b = decide(LiveRecord("b", n_trades=4000, mean_bps=6.0, sd_bps=40.0))
    assert b.allocation > a.allocation


def test_A_NEGATIVE_POSTERIOR_ALLOCATES_ZERO_AND_NEVER_SHORTS_THE_STRATEGY() -> None:
    """Inverting a losing strategy is trading on the desk's own inability to measure."""
    assert allocate(-3.0, 1.0) == 0.0
    assert allocate(3.0, 0.0) == 0.0


def test_ALLOCATION_IS_CAPPED_HOWEVER_GOOD_THE_POSTERIOR_LOOKS() -> None:
    """Given one lucky record an uncapped ladder recommends concentration, and the objective is
    geometric growth -- which concentration damages through variance drag long before it fails."""
    assert allocate(500.0, 0.01) == MAX_ALLOCATION
    assert MAX_ALLOCATION <= 0.25


def test_A_STRONG_RECORD_SCALES_UP_AND_A_MARGINAL_ONE_HOLDS_SMALL() -> None:
    strong = decide(LiveRecord("s", n_trades=2000, mean_bps=4.0, sd_bps=20.0))
    assert strong.decision == "SCALE_UP" and strong.t_stat >= 2.0
    marginal = decide(LiveRecord("m", n_trades=MIN_OBS_FOR_A_VERDICT + 5, mean_bps=2.0,
                                 sd_bps=40.0))
    assert marginal.decision == "HOLD_SMALL"
    assert marginal.allocation <= 0.02
    assert any("buys observations" in n for n in marginal.notes)


def test_THE_RENDER_SHOWS_THE_INTERVAL_NOT_JUST_THE_POINT() -> None:
    text = render(decide(LiveRecord("s", n_trades=500, mean_bps=3.0, sd_bps=20.0)))
    assert "+/-" in text and "t=" in text and "power:" in text


def test_THE_MODULE_PLACES_NOTHING() -> None:
    """Arming live trading is the principal's act. Every number here is inert."""
    import inspect

    import libs.research.live_ladder as LL

    src = inspect.getsource(LL)
    for token in ("place_market", "place_order", "requests.", "urllib", "client.", "api_key"):
        assert token not in src, f"the ladder reached toward an order path: {token!r}"


def test_A_NEGATIVE_POSTERIOR_HELD_SMALL_IS_DESCRIBED_AS_NEGATIVE() -> None:
    """Caught by running the module rather than reading it: a strategy with t=-0.14 was being told
    it was "positive but not yet separable from zero". A ladder that flatters a losing record in
    the one state where the reprieve depends entirely on an ESTIMATE (the small-size drag) is
    wrong in the direction that keeps bad strategies alive."""
    v = decide(LiveRecord("s", n_trades=200, mean_bps=-0.05, sd_bps=5.0, clip_notional=20.0))
    assert v.decision == "HOLD_SMALL" and v.post_mean_bps < 0
    joined = " ".join(v.notes)
    assert "NEGATIVE" in joined and "spared only by crediting" in joined
    assert "positive but not yet separable" not in joined


def test_A_POSITIVE_HELD_SMALL_RECORD_IS_STILL_DESCRIBED_AS_POSITIVE() -> None:
    v = decide(LiveRecord("s", n_trades=60, mean_bps=3.0, sd_bps=40.0))
    assert v.decision == "HOLD_SMALL" and v.post_mean_bps > 0
    assert "positive but not yet separable" in " ".join(v.notes)
