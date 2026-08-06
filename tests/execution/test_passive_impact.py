"""R0267 passive-fill impact model.

THE CONTROL THAT MATTERS. Every estimator here is asked to recover a coefficient this file
PLANTED, so a broken fit fails loudly rather than returning a plausible number. The desk has
shipped two instruments whose rejections were observed but whose acceptances never were
(certify_gauntlet exists for that reason); a decay-length estimator with no positive control is
the same defect one subsystem over.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.execution.passive_impact import (
    MIN_DECAY_POINTS,
    MIN_OFI_POINTS,
    fill_probability_curve,
    fit_fill_decay,
    fit_ofi_response,
    identifiability,
    passive_impact_curve,
    signed_flow,
    window_ofi,
)


class TestFillDecay:
    def test_positive_control_recovers_the_planted_decay_length(self):
        """POSITIVE CONTROL: plant lam=25bps, p0=0.9, demand it back."""
        d = np.linspace(0.0, 60.0, 40)
        p = 0.9 * np.exp(-d / 25.0)
        fit = fit_fill_decay(d, p)
        assert fit.ok, fit.why
        assert fit.lam_bps == pytest.approx(25.0, rel=1e-6)
        assert fit.p0 == pytest.approx(0.9, rel=1e-6)
        assert fit.r2 == pytest.approx(1.0, abs=1e-9)
        assert fit.n == 40

    def test_recovers_decay_under_noise(self):
        rng = np.random.default_rng(20260806)
        d = np.linspace(0.0, 60.0, 400)
        p = 0.8 * np.exp(-d / 30.0) * np.exp(rng.normal(0.0, 0.05, d.size))
        fit = fit_fill_decay(d, p)
        assert fit.ok
        assert fit.lam_bps == pytest.approx(30.0, rel=0.05)

    def test_underpowered_below_the_floor(self):
        d = np.linspace(0.0, 10.0, MIN_DECAY_POINTS - 1)
        fit = fit_fill_decay(d, np.exp(-d / 10.0))
        assert fit.status == "UNDERPOWERED"
        assert not fit.ok
        assert np.isnan(fit.lam_bps)

    def test_zero_variance_regressor_is_unidentified_not_underpowered(self):
        """THE DESK'S ACTUAL CASE: every quote at the touch. Distinct from too-few-rows, and the
        distinction is the whole point -- more fills fix UNDERPOWERED and never fix this."""
        d = np.full(500, 3.0)
        p = np.full(500, 0.42)
        fit = fit_fill_decay(d, p)
        assert fit.status == "UNIDENTIFIED"
        assert "ZERO VARIANCE" in fit.why

    def test_wrong_sign_refuses(self):
        d = np.linspace(0.0, 50.0, 30)
        fit = fit_fill_decay(d, 0.1 * np.exp(d / 20.0))     # RISES with distance
        assert fit.status == "UNIDENTIFIED"
        assert "not negative" in fit.why

    def test_censored_zeros_are_dropped_not_clipped(self):
        """A zero means 'not observed to fill', not 'probability zero'. Clipping would invent a
        point at the chosen floor and drag lam toward it."""
        d = np.linspace(0.0, 60.0, 40)
        p = 0.9 * np.exp(-d / 25.0)
        p_with_zeros = p.copy()
        p_with_zeros[-5:] = 0.0
        fit = fit_fill_decay(d, p_with_zeros)
        assert fit.ok
        assert fit.n == 35
        assert fit.lam_bps == pytest.approx(25.0, rel=1e-6)

    def test_empty_is_no_data(self):
        assert fit_fill_decay([], []).status == "NO-DATA"

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            fit_fill_decay([1.0, 2.0], [0.5])


class TestCurve:
    def test_curve_matches_the_model(self):
        got = fill_probability_curve([0.0, 25.0], lam_bps=25.0, p0=1.0)
        assert got[0] == pytest.approx(1.0)
        assert got[1] == pytest.approx(np.exp(-1.0))

    @pytest.mark.parametrize("lam", [0.0, -5.0, float("nan")])
    def test_bad_decay_length_raises_rather_than_plotting(self, lam):
        with pytest.raises(ValueError):
            fill_probability_curve([1.0], lam_bps=lam)

    def test_signed_distance_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            fill_probability_curve([-1.0], lam_bps=10.0)


class TestSignedFlow:
    def test_binance_maker_flag_signs_the_aggressor(self):
        """m=True means the BUYER was the maker, so the aggressor SOLD -> negative."""
        rows = [{"k": "t", "t": 1, "q": "2.0", "m": True},
                {"k": "t", "t": 2, "q": "3.0", "m": False}]
        t, q = signed_flow(rows)
        assert list(t) == [1.0, 2.0]
        assert list(q) == [-2.0, 3.0]

    def test_bybit_side_is_the_taker_side(self):
        rows = [{"k": "trades", "t": 5, "v": [
            {"side": "Buy", "size": "1.5", "time": 5},
            {"side": "Sell", "size": "0.5", "time": 6}]}]
        t, q = signed_flow(rows)
        assert list(q) == [1.5, -0.5]
        assert list(t) == [5.0, 6.0]

    def test_undirected_rows_are_dropped_not_zeroed(self):
        """A manufactured zero is a real 'balanced flow' observation and would bias every
        downstream imbalance toward the middle."""
        rows = [{"k": "t", "t": 1, "q": "2.0"},              # no m
                {"k": "trades", "t": 2, "v": [{"size": "1.0"}]},   # no side
                {"k": "t", "t": 3, "q": "1.0", "m": False}]
        _, q = signed_flow(rows)
        assert list(q) == [1.0]

    def test_depth_rows_ignored_and_output_sorted(self):
        rows = [{"k": "d", "t": 9, "b": [], "a": []},
                {"k": "t", "t": 7, "q": "1.0", "m": False},
                {"k": "t", "t": 3, "q": "1.0", "m": True}]
        t, q = signed_flow(rows)
        assert list(t) == [3.0, 7.0]
        assert list(q) == [-1.0, 1.0]

    def test_empty(self):
        t, q = signed_flow([])
        assert t.size == 0 and q.size == 0


class TestWindowOfi:
    def test_normalised_imbalance(self):
        t = np.array([1.0, 2.0, 11.0])
        q = np.array([3.0, -1.0, 5.0])
        got = window_ofi(t, q, [0.0, 10.0, 20.0])
        assert got[0] == pytest.approx(2.0 / 4.0)     # net 2 of gross 4
        assert got[1] == pytest.approx(1.0)

    def test_empty_window_is_zero_imbalance(self):
        got = window_ofi(np.array([1.0]), np.array([1.0]), [0.0, 5.0, 10.0])
        assert got[1] == 0.0

    def test_bounded_by_one(self):
        rng = np.random.default_rng(7)
        t = np.sort(rng.uniform(0, 100, 500))
        q = rng.normal(0, 1, 500)
        got = window_ofi(t, q, np.linspace(0, 100, 11))
        assert np.all(np.abs(got) <= 1.0 + 1e-12)

    def test_non_monotone_edges_raise(self):
        with pytest.raises(ValueError, match="strictly increasing"):
            window_ofi(np.array([1.0]), np.array([1.0]), [0.0, 5.0, 5.0])


class TestOfiResponse:
    def test_positive_control_recovers_planted_beta(self):
        rng = np.random.default_rng(11)
        x = rng.normal(0, 1, 500)
        fit = fit_ofi_response(x, 7.5 * x)
        assert fit.ok
        assert fit.beta_bps == pytest.approx(7.5, rel=1e-9)
        assert fit.r2 == pytest.approx(1.0, abs=1e-9)

    def test_no_intercept_absorbed(self):
        """A pure drift with ZERO flow must not read as a flow response."""
        x = np.zeros(100)
        fit = fit_ofi_response(x, np.full(100, 5.0))
        assert fit.status == "UNIDENTIFIED"

    def test_underpowered(self):
        x = np.linspace(-1, 1, MIN_OFI_POINTS - 1)
        assert fit_ofi_response(x, x).status == "UNDERPOWERED"

    def test_empty_is_no_data(self):
        assert fit_ofi_response([], []).status == "NO-DATA"


class TestCombination:
    def _good(self):
        d = np.linspace(0.0, 60.0, 40)
        decay = fit_fill_decay(d, 0.9 * np.exp(-d / 25.0))
        rng = np.random.default_rng(3)
        x = rng.normal(0, 1, 400)
        return decay, fit_ofi_response(x, 4.0 * x)

    def test_combined_curve_decays(self):
        decay, resp = self._good()
        out = passive_impact_curve(decay, resp, distance_bps=[0.0, 25.0, 50.0])
        assert out.status == "OK"
        assert out.impact_bps[0] > out.impact_bps[1] > out.impact_bps[2]
        assert out.fill_prob[0] == pytest.approx(0.9, rel=1e-6)

    def test_refuses_when_either_half_failed(self):
        """L1.55: a well-formed artifact built from an unmeasured input is the failure."""
        decay, resp = self._good()
        bad_decay = fit_fill_decay(np.full(50, 3.0), np.full(50, 0.4))
        out = passive_impact_curve(bad_decay, resp, distance_bps=[0.0, 10.0])
        assert out.status == "UNIDENTIFIED"
        assert out.impact_bps == []
        assert "fabricated half" in out.why

        bad_resp = fit_ofi_response([], [])
        out2 = passive_impact_curve(decay, bad_resp, distance_bps=[0.0, 10.0])
        assert out2.status == "UNIDENTIFIED"
        assert out2.impact_bps == []


class TestIdentifiability:
    def test_the_desks_actual_tape_is_unidentified(self):
        """NO-TREATMENT CONTROL: rows that look like real tape rows but carry no placement
        offset, which is every row the desk has ever written."""
        rows = [{"event": "open", "symbol": "BTCUSDT", "notional": 100.0,
                 "spot_mid": 60000.0, "spot_fill": 60001.0, "wait_s": 12.0}
                for _ in range(500)]
        got = identifiability(rows)
        assert got.status == "UNIDENTIFIED"
        assert "OFFSET ARM" in got.why
        assert got.n_with_offset == 0

    def test_constant_offset_still_unidentified(self):
        """Recording the offset is NOT enough -- quoting at the touch keeps it constant."""
        rows = [{"quote_offset_bps": 2.5} for _ in range(50)]
        got = identifiability(rows)
        assert got.status == "UNIDENTIFIED"
        assert got.offset_variance == 0.0

    def test_flips_to_ok_once_an_offset_arm_varies(self):
        """The verdict must flip on its own the day excitation adds an offset arm."""
        rows = [{"quote_offset_bps": float(i % 7)} for i in range(50)]
        assert identifiability(rows).status == "OK"

    def test_underpowered_when_few_rows_carry_it(self):
        rows = [{"quote_offset_bps": float(i)} for i in range(MIN_DECAY_POINTS - 1)]
        assert identifiability(rows).status == "UNDERPOWERED"

    def test_empty_tape(self):
        assert identifiability([]).status == "NO-DATA"
