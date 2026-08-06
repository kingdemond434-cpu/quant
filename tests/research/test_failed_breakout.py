"""THE LEVEL/SWEEP/FAILURE DEFINITIONS -- 91 statements, zero tests, and they carry the study.

`docs/research/FAILED_BREAKOUT_PREREGISTRATION.md` declares 16,200 trials against these three
definitions. If any of them reads a bar it should not, the entire pre-registration measures a time
machine and the kill criteria are decoration -- so the definitions themselves need testing before
the study they bind ever runs.

THE ONE THAT MATTERS MOST. The pre-registration says, of the level definition:

    *Rejected alternative:* `rolling(window).max()` centred on the bar -- that is the standard
    formulation and it is a time machine.

`swing_levels` marks a swing high at the bar where the extreme OCCURRED, which is correct and
useful (it is where the price is) and which is ALSO the exact shape of the rejected alternative.
What makes it honest is `confirmed_idx = level_idx + k` and the rule that the level is unusable
before it. Marking at i is correct; USING it at i is the bug. Both halves are asserted below,
because a test that only checked the marking would pass on the time machine.

The other two are ordinary off-by-ones with extraordinary consequences: a failure resolved from
the sweep bar's own close, or an entry at the failure bar's close rather than the next bar's open,
each hands the strategy a price it could not have traded at.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research.failed_breakout import (
    LevelParams,
    SweepEvent,
    atr,
    find_events,
    swing_levels,
)


def _bars(high, low, close) -> pd.DataFrame:
    return pd.DataFrame({"high": np.asarray(high, dtype="float64"),
                         "low": np.asarray(low, dtype="float64"),
                         "close": np.asarray(close, dtype="float64")})


# ============================================================ the trial-budget surface

def test_every_hyperparameter_is_a_DECLARED_FIELD_and_therefore_countable() -> None:
    """Declared as a dataclass rather than loose arguments so the sweep cannot quietly grow an
    axis the deflation never hears about. `len(fields)` is auditable; a call site is not."""
    from dataclasses import fields
    names = {f.name for f in fields(LevelParams)}
    assert names == {"k", "n_touch", "tol_atr", "theta_atr", "n_fail", "atr_window"}


def test_the_params_are_FROZEN_so_a_sweep_cannot_mutate_one_in_place() -> None:
    """A mutated params object is an axis the grid hash never saw."""
    p = LevelParams()
    with pytest.raises(AttributeError):       # frozen dataclasses raise FrozenInstanceError
        p.k = 50                              # type: ignore[misc]


def test_the_defaults_match_the_pre_registration() -> None:
    p = LevelParams()
    assert (p.k, p.n_touch, p.tol_atr, p.theta_atr, p.n_fail, p.atr_window) == \
        (20, 1, 0.10, 0.25, 3, 14)


# ============================================================ ATR

def test_atr_is_NaN_until_the_window_fills_rather_than_a_partial_mean() -> None:
    """A partial ATR is systematically SMALL, and every threshold here is a multiple of ATR -- so
    early bars would clear the sweep threshold on ordinary moves and the study would find its
    densest event cluster in its own warmup."""
    n = 40
    a = atr(np.arange(n) + 10.0, np.arange(n) + 9.0, np.arange(n) + 9.5, window=14)
    assert np.all(np.isnan(a[:14]))
    assert np.all(np.isfinite(a[14:]))


def test_atr_at_t_uses_only_bars_up_to_t() -> None:
    """Truncation, the only test that proves causality: recomputing on the prefix must reproduce
    the value."""
    rng = np.random.default_rng(5)
    n = 120
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    h, low_ = c + np.abs(rng.normal(0, 0.5, n)), c - np.abs(rng.normal(0, 0.5, n))
    full = atr(h, low_, c, 14)
    for t in (30, 80, 119):
        assert atr(h[:t + 1], low_[:t + 1], c[:t + 1], 14)[t] == pytest.approx(full[t])


def test_atr_includes_the_GAP_terms_not_just_the_bar_range() -> None:
    """True range is max(h-l, |h-prev_c|, |l-prev_c|). Dropping the gap terms understates ATR
    exactly on the days that gap -- which are the days a sweep threshold most needs to be wide."""
    n = 20
    h = np.full(n, 101.0)
    low_ = np.full(n, 100.0)
    c = np.full(n, 100.5)
    c[9] = 50.0                                # an enormous gap into bar 10
    a_gap = atr(h, low_, c, 5)
    c_flat = np.full(n, 100.5)
    a_flat = atr(h, low_, c_flat, 5)
    assert a_gap[12] > a_flat[12]


def test_a_series_shorter_than_the_window_is_all_NaN_not_an_error() -> None:
    a = atr(np.arange(5.0), np.arange(5.0) - 1, np.arange(5.0), window=14)
    assert a.shape == (5,) and np.all(np.isnan(a))


# ============================================================ the time machine

def test_a_swing_high_is_marked_where_the_extreme_OCCURRED() -> None:
    """Correct and useful -- it is where the PRICE is. It is also the exact shape of the rejected
    centred-rolling-max, which is why the confirmation rule below is what makes it honest."""
    h = np.array([1.0, 2, 3, 9, 3, 2, 1], dtype="float64")
    low_ = np.array([0.0, 1, 2, 8, 2, 1, 0], dtype="float64")
    is_hi, _ = swing_levels(h, low_, k=3)
    assert is_hi[3] and not is_hi.copy().tolist()[:3].count(True)


def test_the_swing_window_is_CENTRED_which_is_why_it_needs_k_BARS_ON_BOTH_SIDES() -> None:
    """A high at i must be the max of [i-k, i+k]. That is a statement about the past ONLY once bar
    i+k has closed -- and the first k and last k bars can never qualify."""
    h = np.array([9.0] + [1.0] * 6, dtype="float64")
    is_hi, _ = swing_levels(h, h - 1, k=3)
    assert not is_hi[0], "index 0 has no left window and must never be marked"
    h2 = np.array([1.0] * 6 + [9.0], dtype="float64")
    is_hi2, _ = swing_levels(h2, h2 - 1, k=3)
    assert not is_hi2[-1], "the last bar has no right window"


def test_a_LEVEL_IS_NEVER_USABLE_BEFORE_ITS_CONFIRMATION_BAR() -> None:
    """THE NO-LOOK-AHEAD ARGUMENT IN ONE ASSERTION. Marking at i is correct; USING it at i is the
    bug the pre-registration names. `confirmed_idx` must be exactly level_idx + k, and every sweep
    must occur strictly after it."""
    p = LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3)
    rng = np.random.default_rng(11)
    n = 200
    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    h, low_ = c + 1.0, c - 1.0
    for e in find_events(_bars(h, low_, c), p):
        assert e.confirmed_idx == e.level_idx + p.k
        assert e.sweep_idx > e.confirmed_idx, (
            f"sweep at {e.sweep_idx} used a level only confirmed at {e.confirmed_idx}")


def test_swing_detection_is_causal_by_truncation_at_the_confirmation_bar() -> None:
    """The honest claim is that the level is knowable at i+k. So recomputing on bars[:i+k+1] must
    still mark i -- if it does not, the confirmation lag is understated."""
    rng = np.random.default_rng(12)
    n = 120
    h = 100 + np.cumsum(rng.normal(0, 1, n))
    low_ = h - 2.0
    k = 5
    full_hi, _ = swing_levels(h, low_, k)
    for i in np.flatnonzero(full_hi)[:6]:
        prefix_hi, _ = swing_levels(h[:i + k + 1], low_[:i + k + 1], k)
        assert prefix_hi[i], f"level at {i} was not knowable at its own confirmation bar {i + k}"


# ============================================================ sweeps and failures

def _sweep_tape() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A flat tape with one clean resistance level, one sweep of it, and a close back inside."""
    n = 60
    h = np.full(n, 101.0)
    low_ = np.full(n, 99.0)
    c = np.full(n, 100.0)
    h[10] = 110.0                       # the swing high, confirmed at 15 with k=5
    h[40] = 120.0                       # the sweep, well beyond 110 + theta*ATR
    c[40] = 115.0                       # the sweep bar closes OUTSIDE
    c[41] = 100.0                       # and the next bar closes back INSIDE -- the failure
    return h, low_, c


def test_a_sweep_is_resolved_as_FAILED_by_a_LATER_close_not_its_own() -> None:
    """Resolving failure from the sweep bar's own close would make the event known at the moment
    it happened -- and the whole hypothesis is about what happens AFTER."""
    h, low_, c = _sweep_tape()
    ev = find_events(_bars(h, low_, c), LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3))
    hits = [e for e in ev if e.sweep_idx == 40]
    assert hits, "the sweep at 40 was not detected"
    e = hits[0]
    assert e.failed is True
    assert e.failure_idx == 41
    assert e.failure_idx > e.sweep_idx


def test_ENTRY_IS_THE_BAR_AFTER_THE_FAILURE_never_the_failure_close() -> None:
    """The failure close is not obtainable: it is the price at the instant the signal fires. Using
    it hands the strategy a fill nobody could have got, on the single most favourable tick."""
    h, low_, c = _sweep_tape()
    e = next(e for e in find_events(_bars(h, low_, c),
                                    LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3))
             if e.sweep_idx == 40)
    assert e.entry_idx == e.failure_idx + 1 == 42


def test_a_sweep_that_never_closes_back_inside_is_NOT_a_failure() -> None:
    """It is a real breakout. Recording it as failed would mean the study measured every
    penetration rather than the failed ones, which is a different hypothesis with a much larger
    sample and no mechanism."""
    h, low_, c = _sweep_tape()
    c[41:] = 115.0                              # it never comes back
    e = next(e for e in find_events(_bars(h, low_, c),
                                    LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3))
             if e.sweep_idx == 40)
    assert e.failed is False
    assert e.failure_idx is None and e.entry_idx is None


def test_the_failure_window_is_BOUNDED_by_n_fail() -> None:
    """A close back inside four bars later is not a 3-bar failure. Without the bound the window is
    'eventually', and price eventually returns to almost any level."""
    h, low_, c = _sweep_tape()
    c[41:45] = 115.0
    c[45] = 100.0                               # comes back at +5, outside a 3-bar window
    p = LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3)
    e = next(e for e in find_events(_bars(h, low_, c), p) if e.sweep_idx == 40)
    assert e.failed is False

    wide = LevelParams(k=5, n_touch=0, atr_window=5, n_fail=10)
    e2 = next(e for e in find_events(_bars(h, low_, c), wide) if e.sweep_idx == 40)
    assert e2.failed is True and e2.failure_idx == 45


def test_a_penetration_SMALLER_than_theta_ATR_is_not_a_sweep() -> None:
    """Otherwise every bar that touched the level counts, and the event becomes 'price was near a
    number' rather than 'price broke it and failed'."""
    h, low_, c = _sweep_tape()
    h[40] = 110.05                              # barely above the level, well inside theta*ATR
    c[40] = 100.0
    p = LevelParams(k=5, n_touch=0, atr_window=5, theta_atr=5.0)
    assert [e for e in find_events(_bars(h, low_, c), p) if e.sweep_idx == 40] == []


def test_a_level_that_never_earned_its_TOUCHES_produces_no_event() -> None:
    """`n_touch` is what separates a level from an arbitrary extreme. A level swept before it was
    ever tested is not the setup the mechanism describes."""
    h, low_, c = _sweep_tape()
    strict = LevelParams(k=5, n_touch=3, atr_window=5, tol_atr=0.001)
    # Scoped to the level at bar 10 -- the 110.0 extreme this tape was built around. The flat
    # stretch either side ties at 101.0 and is marked as a swing at every bar (see the test
    # below), so an unscoped assertion here would be about the flat tape rather than about
    # `n_touch`.
    from_level_10 = [e for e in find_events(_bars(h, low_, c), strict)
                     if e.level_idx == 10 and e.side == "high"]
    assert from_level_10 == [], "a level swept before earning 3 touches must not be an event"


def test_a_PERFECTLY_FLAT_stretch_marks_a_swing_at_every_bar() -> None:
    """Recorded rather than asserted-away, because it surprised me and a future reader deserves it
    in writing.

    `swing_levels` uses `h[i] == window.max()`, so on a flat series every bar ties and is marked.
    That is arithmetically right and it is not a defect here: a flat stretch has no meaningful
    levels either way, and nothing downstream fires without a real penetration of theta*ATR plus
    the touch count. It matters only for FIXTURES -- a flat synthetic tape produces hundreds of
    coincident levels, which is how the n_touch test above was scoped to the wrong thing first.

    Where it WOULD matter is an illiquid symbol whose high genuinely repeats for long stretches;
    that is a data-quality condition the study's symbol selection has to exclude, not a rule to
    change here.
    """
    flat = np.full(30, 100.0)
    is_hi, is_lo = swing_levels(flat, flat - 1.0, k=5)
    interior = slice(5, 25)
    assert is_hi[interior].all() and is_lo[interior].all()
    assert not is_hi[:5].any() and not is_hi[25:].any(), "the k-bar margins are still excluded"


def test_SUPPORT_sweeps_are_detected_with_the_signs_mirrored() -> None:
    """Half the events are on the low side. A high-only detector halves the sample and biases it
    toward whatever the period's trend was."""
    n = 60
    h = np.full(n, 101.0)
    low_ = np.full(n, 99.0)
    c = np.full(n, 100.0)
    low_[10] = 90.0                             # swing low
    low_[40] = 80.0                             # swept
    c[40] = 85.0
    c[41] = 100.0                               # back inside
    ev = find_events(_bars(h, low_, c), LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3))
    lows = [e for e in ev if e.side == "low"]
    assert lows and lows[0].failed is True
    assert lows[0].level_price == pytest.approx(90.0)


def test_events_come_out_in_SWEEP_ORDER() -> None:
    """Highs and lows are scanned in separate passes. Returning them unsorted would make any
    walk-forward split cut the sample at the wrong place."""
    rng = np.random.default_rng(13)
    n = 400
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    ev = find_events(_bars(c + 1.5, c - 1.5, c),
                     LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3))
    idx = [e.sweep_idx for e in ev]
    assert idx == sorted(idx)


def test_only_the_FIRST_sweep_of_a_level_is_recorded() -> None:
    """A level swept, failed, then swept again is one setup and one observation of it. Recording
    each re-test as an independent event inflates n and every t-stat computed from it."""
    h, low_, c = _sweep_tape()
    h[45] = 120.0                               # a second penetration of the same level
    c[45] = 115.0
    c[46] = 100.0
    ev = find_events(_bars(h, low_, c), LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3))
    from_level_10 = [e for e in ev if e.level_idx == 10 and e.side == "high"]
    assert len(from_level_10) == 1


def test_a_level_confirmed_too_late_to_be_swept_is_skipped() -> None:
    """`confirmed + 1 >= n` means there is no bar left to trade it on. Emitting it would put an
    event in the sample with no possible outcome."""
    n = 30
    h = np.full(n, 100.0)
    h[26] = 200.0
    ev = find_events(_bars(h, h - 2, h - 1), LevelParams(k=3, n_touch=0, atr_window=5))
    assert all(e.level_idx != 26 for e in ev)


# ============================================================ contract

def test_missing_columns_RAISE_and_NAME_what_is_missing() -> None:
    """'bars is invalid' sends someone to read the source. Naming the columns does not."""
    with pytest.raises(ValueError, match=r"\['close', 'low'\]"):
        find_events(pd.DataFrame({"high": [1.0, 2.0]}), LevelParams())


def test_INDEX_POSITION_is_used_throughout_not_timestamps() -> None:
    """A '3-bar failure window' across a two-hour data gap is not a 3-bar window -- the same
    mistake the moat screen made with horizons. A caller with gaps must resample first, and the
    contract is that a non-monotonic or exotic index changes nothing."""
    h, low_, c = _sweep_tape()
    df = _bars(h, low_, c)
    shuffled_index = df.copy()
    shuffled_index.index = pd.Index(range(1000, 1000 + len(df)))
    p = LevelParams(k=5, n_touch=0, atr_window=5, n_fail=3)
    assert [e.as_dict() for e in find_events(df, p)] == \
        [e.as_dict() for e in find_events(shuffled_index, p)]


def test_an_empty_or_tiny_frame_returns_no_events_rather_than_raising() -> None:
    assert find_events(_bars([], [], []), LevelParams()) == []
    assert find_events(_bars([1.0], [0.5], [0.8]), LevelParams()) == []


def test_the_event_is_serialisable_and_carries_every_index_it_used() -> None:
    """A verdict that cannot be re-derived from its own record is one nobody can audit. Every bar
    the definition touched is on the row."""
    e = SweepEvent(level_idx=10, level_price=110.0, confirmed_idx=15, sweep_idx=40,
                   side="high", failed=True, failure_idx=41, entry_idx=42)
    d = e.as_dict()
    import json
    json.dumps(d)
    assert set(d) == {"level_idx", "level_price", "confirmed_idx", "sweep_idx", "side",
                      "failed", "failure_idx", "entry_idx"}


def test_failed_is_documented_as_NOT_A_FEATURE() -> None:
    """It is only known n_fail bars after the sweep. A rule that read it at signal time would be
    conditioning on the outcome -- and it is the field most likely to be used that way, because it
    is the one the hypothesis is about."""
    assert "NOT a feature" in (SweepEvent.__doc__ or "")
