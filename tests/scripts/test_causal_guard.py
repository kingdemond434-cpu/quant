"""The leakage PROOF must bite where heuristics do not.

scripts/leakage_detector.py polices leakage by suspicious output (|IC|>0.35, Sharpe>6). A signal
can leak and still post ordinary-looking numbers, sail through every rail, and be promoted.
Future invariance is constructive: mutate the future 1000x and prove the past cannot move. These
tests pin that the guard catches leaks a heuristic would pass, and does not false-positive on
legitimately causal signals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.features.causal_guard import LeakageError, assert_causal, check_causal, self_test


def _bars(n=400, seed=3):
    c = 100 * np.cumprod(1 + np.random.default_rng(seed).normal(0, 0.01, n))
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c})


def test_self_test_proves_the_guard_fires():
    self_test()


def test_causal_signal_passes():
    r = check_causal(lambda d: d["close"].pct_change().rolling(10).mean(), _bars(),
                     name="momentum", min_periods=10)
    assert r.ok and r.n_leaked == 0


def test_blatant_lookahead_is_caught():
    with pytest.raises(LeakageError, match="leakage"):
        assert_causal(lambda d: d["close"].shift(-1), _bars(), name="peek")


def test_subtle_leak_heuristics_would_miss_is_caught():
    """A 1-bar-ahead return smoothed over 5 bars -- plausible IC, ordinary Sharpe, still leaking."""
    r = check_causal(lambda d: (d["close"].shift(-1) / d["close"] - 1).rolling(5).mean(),
                     _bars(), name="subtle", min_periods=5)
    assert not r.ok and r.n_leaked > 0


def test_full_sample_normalisation_is_caught():
    """Z-scoring against the WHOLE sample uses future mean/std -- the classic silent leak."""
    r = check_causal(lambda d: (d["close"] - d["close"].mean()) / d["close"].std(),
                     _bars(), name="full_sample_z", min_periods=1)
    assert not r.ok


def test_failure_message_states_it_is_a_proof_not_a_warning():
    with pytest.raises(LeakageError) as e:
        assert_causal(lambda d: d["close"].shift(-1), _bars(), name="peek")
    assert "constructive proof" in str(e.value)
