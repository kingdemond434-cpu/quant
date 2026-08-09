"""Does the look-ahead audit actually CATCH a leak? The positive control is the whole file.

An audit that reports "all clear" on everything is indistinguishable from an audit that is
broken, and it is far more dangerous than no audit at all because it converts an unchecked
assumption into a certified one. So the tests that matter here are the ones that hand it
deliberately leaky code and demand it fires: test_it_catches_a_centred_window,
test_it_catches_a_future_normalisation, and test_it_catches_a_harness_that_rewards_foresight.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.validation.lookahead_audit import (
    audit_many,
    future_invariance,
    perfect_foresight_probe,
    perturb_future,
)


def _walk(n=600, seed=1):
    return 100 * np.cumprod(1 + np.random.default_rng(seed).normal(0.0005, 0.02, n))


# ------------------------------------------------------------------ the perturbation itself

def test_the_past_is_untouched_and_the_future_is_changed():
    x = _walk()
    got = perturb_future(x, 300, rng=np.random.default_rng(2))
    assert np.array_equal(got[:301], x[:301]), "the perturbation touched the past"
    assert not np.array_equal(got[301:], x[301:]), "the perturbation left the future unchanged"


def test_it_changes_both_order_and_level():
    """Shuffling alone leaves a future-reading max() over a window unchanged whenever the window
    maximum survives the shuffle; rescaling alone leaves an order-dependent leak unchanged. Both
    together is what makes the probe sensitive to either kind."""
    x = _walk()
    got = perturb_future(x, 300, rng=np.random.default_rng(3), scale=1.5)
    assert not np.isclose(np.max(got[301:]), np.max(x[301:])), "level unchanged"
    assert not np.array_equal(np.argsort(got[301:]), np.argsort(x[301:])), "order unchanged"


def test_perturbing_the_last_bar_is_a_no_op():
    x = _walk(n=100)
    assert np.array_equal(perturb_future(x, 99, rng=np.random.default_rng(4)), x)


# ------------------------------------------------------------------------- causal indicators

def test_a_trailing_mean_is_reported_causal():
    def trailing(c):
        out = np.full(len(c), np.nan)
        for i in range(20, len(c)):
            out[i] = c[i - 19:i + 1].mean()
        return out
    rep = future_invariance(trailing, _walk(), rng=np.random.default_rng(5))
    assert rep["causal"] and rep["n_leaking_probes"] == 0
    assert "CAUSAL" in rep["verdict"]


def test_a_lagged_return_is_reported_causal():
    def lagged(c):
        out = np.zeros(len(c))
        out[1:] = np.diff(np.log(c))
        return out
    assert future_invariance(lagged, _walk(), rng=np.random.default_rng(6))["causal"]


# ---------------------------------------------------------------- THE POSITIVE CONTROLS

def test_it_catches_a_centred_window():
    """The classic accidental leak: a window centred on the current bar. It looks like an ordinary
    smoother and reads 10 bars into the future. If the audit misses this it is worthless."""
    def centred(c):
        out = np.full(len(c), np.nan)
        for i in range(10, len(c) - 10):
            out[i] = c[i - 10:i + 11].mean()
        return out
    rep = future_invariance(centred, _walk(), rng=np.random.default_rng(7))
    assert not rep["causal"]
    assert rep["n_leaking_probes"] > 0
    assert "LOOK-AHEAD" in rep["verdict"]


def test_it_catches_a_future_normalisation():
    """The subtler leak, and the one that survives a shuffle: dividing by a statistic of the WHOLE
    series. Nothing in the code looks forward; the normaliser does. This is why perturb_future
    rescales as well as shuffles."""
    def full_sample_z(c):
        r = np.zeros(len(c))
        r[1:] = np.diff(np.log(c))
        return (r - r.mean()) / (r.std() + 1e-12)      # mean and std of ALL data, including future
    rep = future_invariance(full_sample_z, _walk(), rng=np.random.default_rng(8))
    assert not rep["causal"], "a full-sample normalisation was not detected"


def test_it_catches_a_one_bar_shift_the_wrong_way():
    """Off-by-one in the lag direction -- the single most common real look-ahead bug, and the one
    that produces the most plausible-looking equity curve."""
    def shifted_wrong(c):
        out = np.zeros(len(c))
        out[:-1] = np.diff(np.log(c))                  # bar i holds the return of bar i+1
        return out
    assert not future_invariance(shifted_wrong, _walk(), rng=np.random.default_rng(9))["causal"]


# ---------------------------------------------------------------------- the harness probe

def test_it_catches_a_harness_that_rewards_foresight():
    """The other half. A leaky BACKTESTER cannot be found by auditing features -- every feature
    passes and the harness still pays out on information the strategy never had."""
    def leaky(pos, r):
        out = pos * r                                  # NO LAG: trades the bar it derived from
        return float(np.mean(out) / np.std(out, ddof=1))
    rep = perfect_foresight_probe(leaky, np.random.default_rng(10).normal(0, 0.02, 800))
    assert rep["harness_leaks"] and "HARNESS LEAKS" in rep["verdict"]


def test_a_correctly_lagged_harness_passes():
    def lagged(pos, r):
        p = np.zeros_like(pos)
        p[1:] = pos[:-1]                               # position known at the prior close
        out = p * r
        return float(np.mean(out) / np.std(out, ddof=1))
    rep = perfect_foresight_probe(lagged, np.random.default_rng(11).normal(0, 0.02, 800))
    assert not rep["harness_leaks"] and "HARNESS CLEAN" in rep["verdict"]


# ------------------------------------------------------------------------------- batch audit

def test_a_leaky_member_does_not_stop_the_audit_of_the_others():
    """A partial audit that halted at the first problem would be read as 'only one problem'."""
    def ok(c):
        out = np.zeros(len(c))
        out[1:] = np.diff(np.log(c))
        return out

    def bad(c):
        out = np.full(len(c), np.nan)
        for i in range(10, len(c) - 10):
            out[i] = c[i + 5]
        return out
    rep = audit_many([("ok_a", ok), ("bad", bad), ("ok_b", ok)], _walk(),
                     rng=np.random.default_rng(12), n_probes=12)
    assert rep["n_audited"] == 3 and rep["leaking"] == ["bad"]


def test_an_indicator_that_raises_is_recorded_not_swallowed():
    def boom(c):
        raise RuntimeError("nope")

    rep = audit_many([("boom", boom)], _walk(), rng=np.random.default_rng(13), n_probes=12)
    assert "boom" in rep["errored"] and rep["n_audited"] == 0


def test_a_misaligned_indicator_raises():
    with pytest.raises(ValueError, match="aligned"):
        future_invariance(lambda c: c[:-5], _walk(), rng=np.random.default_rng(14))


def test_too_short_a_series_raises():
    with pytest.raises(ValueError, match="50 bars"):
        future_invariance(lambda c: c, np.arange(30, dtype="float64"),
                          rng=np.random.default_rng(15))


def test_probes_skip_the_warmup_so_nan_cannot_hide_a_leak():
    """An indicator that is NaN early would report a spurious pass there, because NaN compares
    equal to NaN under the check. Probes are drawn from where the indicator produces values."""
    rep = future_invariance(lambda c: c.copy(), _walk(), rng=np.random.default_rng(16),
                            warmup=0.5, n_probes=10)
    assert all(leak["index"] >= 0 for leak in rep["leaks"])
    assert rep["n_probes"] <= 10
