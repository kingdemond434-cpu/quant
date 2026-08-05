"""Tests for the mandated target/horizon sweep (work order `screen-target-horizon-harness`).

The order called this out as CAREFUL BUILD / stats-sensitive and required a synthetic-signal test
before first real use, so these pin the two properties that make the sweep worth having:

  1. it FINDS a mechanism that the next-day-absolute reflex misses (the dev-momentum episode), and
  2. it cannot be used to launder a cherry-picked cell -- every fork it considered is returned and
     counted, including the ones it could not screen.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.axis_screen import target_horizon_sweep


def _panel(n_periods=5000, n_inst=12, seed=0):
    """A price panel with a strong COMMON factor -- the reason an absolute target drowns."""
    rng = np.random.default_rng(seed)
    market = rng.normal(0, 0.03, size=n_periods)          # common move, same for every instrument
    idio = rng.normal(0, 0.01, size=(n_periods, n_inst))
    rets = market[:, None] + idio
    prices = 100 * np.exp(np.cumsum(rets, axis=0))
    return prices, idio, rng


def test_cross_sectional_target_finds_a_selection_signal_absolute_misses():
    """THE DEV-MOMENTUM EPISODE, synthetically. A signal that predicts an instrument's return
    RELATIVE to its peers carries no information about the market's direction. Screened against an
    absolute target the common factor is pure added noise and the IC collapses; demeaning the
    cross-section removes exactly that factor and the mechanism appears."""
    prices, idio, rng = _panel()
    # A REALISTIC signal, not an oracle: it mostly reflects the CURRENT period (weight 1.875) and
    # leads the next one only weakly (weight 1.0), buried in 12x noise. The contemporaneous
    # component is deliberate -- a signal with zero same-period correlation but a strong forward
    # IC is what the harness's lookahead rail exists to reject, so an oracle-shaped synthetic
    # tests the rail rather than the sweep.
    signal = np.zeros_like(idio)
    signal[:-1] = (1.875 * idio[:-1] + 1.0 * idio[1:]
                   + rng.normal(0, 0.123, size=(idio.shape[0] - 1, idio.shape[1])))

    out = target_horizon_sweep(signal, prices, name="synthetic-selection", horizons=(1,))
    by_target = {c["target"]: c for c in out["cells"]}
    xs, ab = by_target["cross_sectional"], by_target["absolute"]
    # THE WHOLE POINT: the same signal, the same data, the same horizon -- found or missed purely
    # on the choice of target. The absolute cell lands under the 0.03 IC floor and is written off.
    assert xs["verdict"] == "SCREEN-INTERESTING"
    assert ab["verdict"] == "SCREEN-WEAK"
    assert abs(xs["ic"]) > 2 * abs(ab["ic"])
    # and it is a real lead, not the contemporaneous component leaking through the de-contam gate
    assert abs(xs["residual_ic"]) >= 0.5 * abs(xs["ic"])


def test_panel_stacking_is_deflated_not_counted_as_independent():
    """Why the test panel needs 5000 periods and not 400: a 12-instrument panel flattens to
    12*T rows, and counting those as independent would inflate every t-stat by sqrt(12). The
    harness deflates by panel_width, so n_eff is T -- and a cell only reads as powered when the
    number of PERIODS (not rows) could have detected an effect at ic_min."""
    prices, _, _ = _panel(n_periods=1200, n_inst=12)
    signal = np.random.default_rng(4).normal(size=prices.shape)
    out = target_horizon_sweep(signal, prices, name="deflation", horizons=(1,))
    cell = next(c for c in out["cells"] if c["target"] == "absolute")
    assert cell["n"] > 12000                    # rows actually screened
    assert cell["n_eff"] < 1300                 # ...but only ~T independent ones
    assert cell["verdict"] == "SCREEN-UNDERPOWERED"


def test_every_cell_is_returned_and_counted_as_a_trial():
    """No cherry-picking: the full grid comes back, and n_trials is the denominator for DSR."""
    prices, _, _ = _panel()
    signal = np.random.default_rng(5).normal(size=prices.shape)
    out = target_horizon_sweep(signal, prices, name="noise")
    assert out["n_trials"] == 6                              # 2 targets x 3 horizons
    assert out["n_screened"] + out["n_skipped"] == out["n_trials"]
    assert {(c["target"], c["horizon_days"]) for c in out["cells"]} == {
        (t, float(h)) for t in ("absolute", "cross_sectional") for h in (1, 5, 20)
    }


def test_pure_noise_produces_no_interesting_cell():
    """Six cells of noise must not yield a survivor -- otherwise the sweep is a phantom-edge
    factory that manufactures one finding per axis by construction."""
    prices, _, _ = _panel(seed=3)
    signal = np.random.default_rng(9).normal(size=prices.shape)
    out = target_horizon_sweep(signal, prices, name="pure-noise")
    assert out["n_interesting"] == 0


def test_skipped_cells_are_named_and_still_cost_multiplicity():
    """A single instrument cannot support a cross-sectional claim. The cell is skipped with a
    reason rather than silently returning noise -- but it was still a fork that was considered, so
    it must not quietly shrink the denominator the DSR bar is computed from."""
    prices, _, _ = _panel(n_inst=1)
    signal = np.random.default_rng(1).normal(size=prices.shape)
    out = target_horizon_sweep(signal, prices, name="single")
    assert out["n_trials"] == 6
    assert out["n_skipped"] == 3
    assert all(s["target"] == "cross_sectional" for s in out["skipped"])
    assert all("cross-section" in s["reason"] for s in out["skipped"])


def test_one_d_input_is_treated_as_a_single_instrument_panel():
    prices, _, _ = _panel(n_inst=1)
    flat = prices[:, 0]
    signal = np.random.default_rng(2).normal(size=flat.shape)
    out = target_horizon_sweep(signal, flat, name="1d")
    assert out["n_screened"] == 3 and out["n_skipped"] == 3


def test_mismatched_panel_shapes_are_rejected_loudly():
    """Silently broadcasting a mismatched panel would align a signal to the wrong instrument."""
    prices, _, _ = _panel(n_inst=12)
    with pytest.raises(ValueError, match="same panel shape"):
        target_horizon_sweep(np.zeros((prices.shape[0], 5)), prices, name="bad")


def test_period_returns_are_backward_looking_as_the_harness_contracts():
    """Row t holds the return over the h periods ENDING at t, so the LEADING h rows are unusable.

    This is the harness's contract, not a preference: `stage_a_screen` computes its own
    `np.roll(target, -1)`, so it wants the contemporaneous period return and shifts to the future
    itself.
    """
    from libs.research.axis_screen import _period_returns

    px = np.array([[1.0], [2.0], [4.0], [8.0]])
    r1 = _period_returns(px, 1)
    assert not np.isfinite(r1[0, 0])                      # nothing precedes the first bar
    assert np.allclose(r1[1:, 0], [1.0, 1.0, 1.0])        # each period doubles
    r2 = _period_returns(px, 2)
    assert not np.isfinite(r2[:2, 0]).any()
    assert np.allclose(r2[2:, 0], [3.0, 3.0])             # 1->4 and 2->8


def test_the_harness_roll_lands_on_the_true_future_return():
    """THE DOUBLE-SHIFT REGRESSION, pinned end to end.

    Passing an already-forward return double-shifts against `stage_a_screen`'s internal roll: the
    signal at t is then tested against the return from t+1 to t+1+h, one period past the one it
    predicts. It fails silently -- no error, no warning, just a true IC of ~0.45 reported as 0.004
    and a real mechanism graveyarded as noise. This asserts the composition directly.
    """
    from libs.research.axis_screen import _period_returns

    px = np.array([[1.0], [2.0], [4.0], [8.0], [16.0]])
    r = _period_returns(px, 1)
    harness_forward = np.roll(r, -1, axis=0)              # exactly what stage_a_screen does
    # at t=1 (price 2.0) the harness must see the return from 2.0 -> 4.0, i.e. strictly future
    assert harness_forward[1, 0] == pytest.approx(1.0)
    assert harness_forward[1, 0] == pytest.approx(px[2, 0] / px[1, 0] - 1.0)
