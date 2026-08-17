"""A contest between representations is only worth running if it can return "none of them".

Three ways this kind of tournament lies, and the tests that stop each: a leaking split, a winner
that simply searched harder, and no floor to beat.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.tournament import (  # noqa: E402
    Entrant, purged_folds, run, score, shuffled_null)

RNG = np.random.default_rng(31337)


def _noise(n=1200, k=6):
    return RNG.normal(size=(n, k))


def _signal(n=1200, k=6, strength=0.6):
    """One feature genuinely predicts; the rest are noise."""
    x = RNG.normal(size=(n, k))
    y = strength * x[:, 0] + RNG.normal(size=n)
    return x, y


# --------------------------------------------------------------------- the split

def test_folds_never_train_on_the_future():
    for tr, te in purged_folds(1000, 5, horizon=1):
        assert tr.max() < te.min(), "a training row sits after a test row"


def test_the_boundary_is_purged_by_the_label_horizon():
    """A label over the next h bars overlaps the test window for the last h training rows. Those
    rows carry test information into the fit, and dropping them is the whole difference between
    an honest OOS number and a flattering one."""
    for h in (1, 10, 50):
        for tr, te in purged_folds(1000, 5, horizon=h):
            assert te.min() - tr.max() >= h, f"gap {te.min() - tr.max()} < horizon {h}"


def test_a_short_sample_yields_no_folds_rather_than_bad_ones():
    assert list(purged_folds(60, 5, 1)) == []


# ------------------------------------------------------------------- can it fail?

def test_pure_noise_scores_near_zero():
    """THE TEST THAT MAKES A WIN MEAN ANYTHING. If noise scores well, nothing scored here is
    evidence of anything."""
    r = score(Entrant("noise", _noise()), RNG.normal(size=1200))
    assert abs(r.ic_mean) < 0.10, f"found IC {r.ic_mean:.3f} in pure noise"


def test_a_real_signal_is_found():
    x, y = _signal()
    r = score(Entrant("signal", x), y)
    assert r.ic_mean > 0.20, f"missed a planted signal: IC {r.ic_mean:.3f}"


def test_the_tournament_can_return_that_nothing_worked():
    out = run([Entrant("a", _noise()), Entrant("b", _noise())], RNG.normal(size=1200))
    assert out["beat_the_null"] == []
    assert "NO representation beat" in out["verdict"]


def test_a_genuine_entrant_beats_the_null_and_noise_does_not():
    x, y = _signal()
    out = run([Entrant("real", x), Entrant("noise", _noise())], y)
    assert "real" in out["beat_the_null"]
    assert "noise" not in out["beat_the_null"]


# ----------------------------------------------------------------------- the floor

def test_every_tournament_runs_a_shuffled_null():
    out = run([Entrant("a", _noise())], RNG.normal(size=1200))
    assert out["nulls"] and "null_ceiling" in out


def test_the_null_scores_near_zero_on_a_real_signal():
    """The null must destroy the relationship, not merely resample it."""
    x, y = _signal()
    n = shuffled_null(Entrant("real", x), y)
    assert abs(n.ic_mean) < 0.10, f"shuffling left IC {n.ic_mean:.3f}"


# --------------------------------------------------------------- multiplicity

def test_trial_counts_are_carried_into_the_result():
    """A representation with 40 features searched a wider space than one with 6 and can win by
    search rather than signal. A tournament that reports only scores is a multiplicity engine."""
    out = run([Entrant("wide", _noise(k=6), n_trials=40),
               Entrant("narrow", _noise(k=6), n_trials=2)], RNG.normal(size=1200))
    assert out["n_trials_total"] == 42
    assert "Deflate" in out["multiplicity"]


def test_the_table_is_the_result_not_a_single_winner():
    out = run([Entrant("a", _noise()), Entrant("b", _noise())], RNG.normal(size=1200))
    assert "winner" not in out
    assert len(out["ranked"]) == 2
    assert "conditional model-selection edge" in out["why_no_single_winner"]


# --------------------------------------------------------------------- leakage

def test_standardisation_uses_training_moments_only():
    """Scaling with test-fold moments is leakage that looks like nothing and lifts every score.
    Shifting the test half must not change the training fit's view of it."""
    from mt5desk.tournament import _ridge_fit_predict
    xtr, ytr = RNG.normal(size=(300, 4)), RNG.normal(size=300)
    xte = RNG.normal(size=(120, 4))
    a = _ridge_fit_predict(xtr, ytr, xte)
    b = _ridge_fit_predict(xtr, ytr, xte + 100.0)
    assert not np.allclose(a, b), "test-fold shift ignored -- moments came from the test set"


def test_every_entrant_gets_the_same_learner():
    """Otherwise the contest silently becomes model-family versus model-family, which is a
    different question than the one being asked."""
    src = (_DESK / "mt5desk" / "tournament.py").read_text(encoding="utf-8")
    assert src.count("_ridge_fit_predict(") >= 2
    assert "SAME learner" in src


def test_an_unscoreable_entrant_reports_nothing_rather_than_zero():
    r = score(Entrant("tiny", _noise(n=80)), RNG.normal(size=80))
    assert r.folds_scored == 0
    assert "scored nothing rather than guessing" in r.why
