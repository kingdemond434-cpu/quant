"""Point-in-time replay, and the attribution loop that makes the layer learn.

REPLAY. Nothing here may size a position until it has been replayed honestly, and the guard has
teeth: it RAISES on a read past the replay clock rather than clipping. Clipping is exactly how a
backtest reads Friday's report on Wednesday and reports an edge. One asymmetry is deliberate and
is pinned as such -- prices BETWEEN publication and arrival are readable, because that window is
in the past by the time the desk has the bytes and is precisely what tells the desk it was late.

ATTRIBUTION. The loop that answers "not just hardcoded data". These pin that it produces the
exact shapes the learners consume, that it measures the desk's own overreaction, that it scores
the unpriced estimator against what actually happened, and that it is honest about what it can
and cannot verify: it measures whether a claim was FOLLOWED BY a move, which is not the same as
whether the claim was true.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.attribution import attribute, feedback, report  # noqa: E402
from macro.ledger import MIN_CATEGORY_N, EventLedger  # noqa: E402
from macro.prices import FakePriceReader, synthetic_series  # noqa: E402
from macro.replay import (  # noqa: E402
    PITGuardedReader,
    PITViolation,
    clearance,
    coverage,
    default_scorer,
    replay,
)
from macro.schema import EventRecord, Status  # noqa: E402

SPAN = 60.0
T0 = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
START = T0 - timedelta(seconds=SPAN * 400)


def _reader(jump: float = 0.0, jump_at: int = 402) -> FakePriceReader:
    return FakePriceReader(
        {"XAUUSD": synthetic_series(START, 900, SPAN, step=0.001,
                                    jump_at=jump_at if jump else None, jump=jump)},
        {"XAUUSD": SPAN})


def _rec(eid: str, received: datetime, *, published: datetime | None = None,
         category: str = "inflation_release", forecast: float = 0.0) -> EventRecord:
    return EventRecord(
        event_id=eid, received_at=received.isoformat(),
        processed_at=(received + timedelta(seconds=1)).isoformat(),
        published_at=(published or received - timedelta(seconds=120)).isoformat(),
        source_id="src", title=f"headline {eid}", category=category,
        instruments=("XAUUSD",),
        priced={"status": Status.MEASURED, "unpriced_fraction": 0.6, "total_move_sigma": 3.0},
        forecasts=([{"symbol": "XAUUSD", "expected_move_sigma": forecast,
                     "status": Status.MEASURED, "n": 100, "path": ["factor"]}]
                   if forecast else []))


# ------------------------------------------------------------------------- replay ----

def test_the_guard_raises_on_a_read_past_the_replay_clock() -> None:
    guarded = PITGuardedReader(_reader(), T0)
    assert guarded.price_at("XAUUSD", T0 - timedelta(seconds=60)) is not None
    with pytest.raises(PITViolation):
        guarded.price_at("XAUUSD", T0 + timedelta(seconds=60))


def test_the_guard_raises_rather_than_clipping() -> None:
    """A clipped reader would silently return a weaker number and the desk could never tell the
    difference between 'no leak' and 'leak that returned little'."""
    guarded = PITGuardedReader(_reader(), T0)
    with pytest.raises(PITViolation):
        guarded.returns_before("XAUUSD", T0 + timedelta(days=1), 100)
    assert guarded.violations, "the violation is recorded, not just raised"


def test_the_publication_to_arrival_window_is_readable_and_that_is_not_a_leak() -> None:
    """The deliberate asymmetry: that window is in the past by the time the desk has the bytes,
    and reading it is how the desk learns it was late."""
    received = T0
    published = T0 - timedelta(seconds=300)
    guarded = PITGuardedReader(_reader(), received)
    assert guarded.price_at("XAUUSD", published) is not None
    assert guarded.price_at("XAUUSD", received) is not None


def test_a_replay_releases_events_in_arrival_order_with_only_prior_history() -> None:
    recs = [_rec(f"e{i}", T0 + timedelta(seconds=SPAN * i)) for i in range(6)]
    seen: list[int] = []

    def scorer(rec, reader, history):
        seen.append(len(history))
        return {"ok": True}

    rep = replay(recs, _reader(), scorer)
    assert rep.n_scored == 6
    assert rep.n_violations == 0
    assert seen == [0, 1, 2, 3, 4, 5], "each event sees only what was already processed"


def test_a_leaky_scorer_fails_the_replay_rather_than_passing_quietly() -> None:
    recs = [_rec("e0", T0)]

    def leaky(rec, reader, history):
        return {"peek": reader.price_at("XAUUSD", T0 + timedelta(days=1))}

    with pytest.raises(PITViolation):
        replay(recs, _reader(), leaky)
    rep = replay(recs, _reader(), leaky, strict=False)
    assert rep.n_violations == 1 and rep.n_scored == 0


def test_a_scorer_bug_does_not_read_as_a_clean_replay() -> None:
    def broken(rec, reader, history):
        raise ValueError("boom")

    rep = replay([_rec("e0", T0)], _reader(), broken, strict=False)
    assert rep.errors and rep.n_scored == 0
    assert rep.to_dict()["clean"] is False


def test_clearance_needs_both_a_clean_replay_and_sample() -> None:
    """A category replayed six times cleanly has been replayed six times. That is not evidence."""
    thin = [_rec(f"e{i}", T0 + timedelta(seconds=SPAN * i)) for i in range(5)]
    cleared, refused = clearance(replay(thin, _reader(), default_scorer()))
    assert cleared == [] and refused == ["inflation_release"]

    many = [_rec(f"e{i}", T0 + timedelta(seconds=SPAN * i)) for i in range(MIN_CATEGORY_N)]
    cleared, refused = clearance(replay(many, _reader(), default_scorer()))
    assert cleared == ["inflation_release"] and refused == []


def test_a_replay_with_violations_clears_nothing() -> None:
    rep = replay([_rec("e0", T0)] * 1, _reader(), default_scorer())
    rep.n_violations = 1
    assert clearance(rep) == ([], ["inflation_release"])


def test_the_coverage_statement_is_explicit_about_what_it_does_not_cover(
        tmp_path: Path) -> None:
    """A replay that overstates its reach is worse than no replay."""
    led = EventLedger(tmp_path / "l.jsonl")
    cov = coverage(led)
    assert cov["ledger_rows"] == 0
    assert cov["categories_cleared_for_capital"] == []
    text = " ".join(cov["does_not_cover"])
    assert "ZERO" in text
    assert "CPI" in text and "FOMC" in text
    assert "can size a position today" in cov["gate"]
    assert "refuses capital authority" in cov["gate"]


# -------------------------------------------------------------------- attribution ----

def test_attribution_finds_the_leading_instrument_and_the_lag() -> None:
    r = _reader(jump=0.03, jump_at=405)
    rec = _rec("e0", T0, published=T0 - timedelta(seconds=180))
    a = attribute(rec, r, horizon_s=3600.0)
    assert a.status == Status.MEASURED
    assert a.leading_instrument == "XAUUSD"
    assert a.arrival_lag_s == 180.0
    assert a.lead_s is not None and a.lead_s > 0


def test_attribution_scores_the_unpriced_estimator_against_what_happened() -> None:
    """Without this the unpriced estimate is an opinion that never gets marked."""
    r = _reader(jump=0.03, jump_at=405)
    a = attribute(_rec("e0", T0), r, horizon_s=3600.0)
    assert a.estimated_unpriced == 0.6
    assert a.realised_unpriced is not None
    assert a.unpriced_error is not None


def test_attribution_measures_the_layer_s_own_overreaction() -> None:
    r = _reader(jump=0.02, jump_at=405)
    modest = attribute(_rec("small", T0, forecast=0.1), r, horizon_s=3600.0)
    wild = attribute(_rec("big", T0, forecast=50.0), r, horizon_s=3600.0)
    assert wild.overreaction is not None and modest.overreaction is not None
    assert wild.overreaction > modest.overreaction


def test_the_best_response_benchmark_is_computed_in_log_growth() -> None:
    """'Which forecast was right' is weaker than 'what would have maximised E[log W]', and only
    the second is comparable across events of different sizes."""
    r = _reader(jump=0.03, jump_at=405)
    a = attribute(_rec("e0", T0, forecast=1.0), r, horizon_s=3600.0)
    assert a.best_response is not None
    assert a.best_log_growth is not None and a.best_log_growth >= 0.0
    assert a.realised_log_growth is not None
    assert a.best_log_growth >= a.realised_log_growth


def test_feedback_produces_exactly_the_shapes_the_learners_consume() -> None:
    """THE GROWTH LOOP. credibility.fit and factors.category_loadings must be able to eat this
    without translation, or the loop is decorative."""
    r = _reader(jump=0.03, jump_at=405)
    atts = [attribute(_rec(f"e{i}", T0 + timedelta(seconds=SPAN * i), forecast=1.0), r,
                      horizon_s=3600.0) for i in range(4)]
    fb = feedback(atts)
    assert set(fb) >= {"source_outcomes", "factor_samples", "priced_calibration"}
    src = fb["source_outcomes"]["src"]
    assert set(src) == {"verified", "falsified", "leads"}
    assert src["verified"] + src["falsified"] == 4
    assert len(src["leads"]) == 4

    from macro.credibility import CredibilityModel
    m = CredibilityModel().fit(fb["source_outcomes"], tier_of={"src": "WIRE"})
    assert m.posterior("src").n_verified + m.posterior("src").n_falsified == 4


def test_the_decay_half_life_is_measured_here_and_nowhere_else() -> None:
    """The number the interrupt gate depends on. Nothing else in the package measures it, so
    without this the gate would be permanently UNMEASURED and the interrupt would be dead code
    by construction."""
    r = _reader(jump=0.03, jump_at=405)
    a = attribute(_rec("e0", T0), r, horizon_s=7200.0)
    assert a.unpriced_half_life_s is not None
    assert a.unpriced_half_life_s > 0
    fb = feedback([a])
    assert fb["decay_samples"]["inflation_release"] == [a.unpriced_half_life_s]


def test_a_flat_tape_yields_no_half_life_rather_than_a_made_up_one() -> None:
    """Nothing decayed because nothing happened. Quoting a half-life there would gate the
    interrupt on noise."""
    a = attribute(_rec("e0", T0), _reader(), horizon_s=7200.0)
    assert a.unpriced_half_life_s is None


def test_the_decay_loop_is_closed_and_not_circular(tmp_path: Path) -> None:
    """REGRESSION. `decay_half_life_s` used to be read off the event rows, which are the very
    rows it would have to be written to -- so nothing ever seeded it. It now arrives from the
    attribution record, which is where a quantity only knowable AFTER the horizon belongs."""
    led = EventLedger(tmp_path / "l.jsonl")
    for i in range(MIN_CATEGORY_N):
        led.append(EventRecord(
            event_id=f"m{i}", category="inflation_release",
            received_at=(T0 + timedelta(days=i)).isoformat(),
            processed_at=(T0 + timedelta(days=i)).isoformat(),
            priced={"status": Status.MEASURED, "total_move_sigma": 3.0}))
    # Without attribution samples the half-life is unknown, and says so.
    assert led.category_stats("inflation_release").decay_half_life_s is None
    # With them, it is measured.
    samples = {"inflation_release": [30.0] * MIN_CATEGORY_N}
    stats = led.category_stats("inflation_release", decay_samples=samples)
    assert stats.status == Status.MEASURED
    assert stats.decay_half_life_s == 30.0
    # And a thin sample still refuses.
    thin = {"inflation_release": [30.0] * (MIN_CATEGORY_N - 1)}
    assert led.category_stats("inflation_release", decay_samples=thin).decay_half_life_s is None


def test_the_calibration_reading_names_the_direction_of_the_error() -> None:
    r = _reader(jump=0.03, jump_at=405)
    atts = [attribute(_rec(f"e{i}", T0 + timedelta(seconds=SPAN * i)), r, horizon_s=3600.0)
            for i in range(3)]
    cal = feedback(atts)["priced_calibration"]
    assert cal["n"] == 3
    assert "OPTIMISTIC" in cal["reading"] or "PESSIMISTIC" in cal["reading"]


def test_empty_attributions_read_UNMEASURED_not_zero() -> None:
    cal = feedback([])["priced_calibration"]
    assert cal["n"] == 0 and cal["mean_error"] is None
    assert "UNMEASURED" in cal["reading"]
    rep = report([])
    assert rep["median_overreaction_ratio"] is None
    assert rep["overreaction_reading"] == "UNMEASURED"


def test_attribution_is_honest_that_it_measures_moves_not_facts() -> None:
    """Conflating 'the market moved as implied' with 'the claim was true' would score a true
    report the market ignored as a falsehood."""
    a = attribute(_rec("e0", T0), _reader(jump=0.03, jump_at=405), horizon_s=3600.0)
    assert "not factual verification" in a.note
    assert "move_confirmed" in a.note
    assert "not fact-checking" in report([a])["note"]


def test_attribution_refuses_rather_than_inventing_a_verdict() -> None:
    bare = EventRecord(event_id="x", received_at=T0.isoformat(), category="c")
    a = attribute(bare, _reader(), horizon_s=3600.0)
    assert a.status == Status.UNMEASURED
    assert "no candidate instruments" in a.note
