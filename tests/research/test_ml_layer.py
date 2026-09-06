"""THE AI LAYER (P6 / P8 / P9 / P42).

Three properties, and every one of them is about refusing to admit something.

LOOKAHEAD. A representation fitted on the whole series and scored out-of-sample is the most common
mistake in applied ML and it is invisible in the result -- it just looks like a good model. Fitting
and standardisation must use the training slice alone, and that is asserted directly.

THE GATE. A mixture-of-experts gate fitted and scored in sample routes each bar to whichever
expert happened to do well on it, manufacturing skill from nothing. It must beat a uniform blend
out of sample or be refused.

THE STUDENT. A distilled model that reproduces its teacher perfectly -- including the teacher's
errors -- has learned to imitate, not to predict. Agreement is deliberately not the test.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_mllayer", _ROOT / "desks" / "mt5" / "research" / "ml_layer.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ml():
    return _load()


def _walk(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    return np.exp(np.cumsum(rng.normal(0, 0.001, n)) + 7.0)


# --------------------------------------------------------------------------- P6
def test_features_are_computable_at_the_bar_they_describe(ml) -> None:
    """TRAILING ONLY. A centred window or a global statistic leaks the future into every row,
    and the resulting backtest is excellent and worthless."""
    close = _walk()
    x, names = ml.features(close)
    assert x.shape[1] == len(names) == 2 * len(ml.HORIZONS)
    # Truncating the series must not change any feature value that was already computable.
    cut = 2000
    x2, _ = ml.features(close[:cut])
    a, b = x[:cut][~np.isnan(x[:cut]).any(axis=1)], x2[~np.isnan(x2).any(axis=1)]
    m = min(len(a), len(b))
    assert np.allclose(a[:m], b[:m], atol=1e-9), (
        "a feature changed when later bars were removed -- it is reading the future")


def test_the_projection_is_fitted_on_the_training_slice_only(ml) -> None:
    """The invisible lookahead. Components chosen knowing the test period's variance structure
    produce a model that scores beautifully and generalises to nothing."""
    close = _walk()
    rep = ml.representation(close)
    assert rep["status"] == "FITTED"
    # Changing ONLY the test tail must leave the fitted components untouched.
    tampered = close.copy()
    tampered[rep["fit_rows"] + 500:] *= 1.5
    rep2 = ml.representation(tampered)
    assert np.allclose(rep["components"], rep2["components"], atol=1e-6), (
        "altering data AFTER the training slice changed the fitted projection -- the "
        "representation is being fitted on the whole series")


def test_a_short_series_is_refused_rather_than_fitted(ml) -> None:
    rep = ml.representation(_walk(120))
    assert rep["status"] == "INSUFFICIENT" and "rows" in rep


# --------------------------------------------------------------------------- P8
def test_the_pretext_uses_no_return_label(ml) -> None:
    """The point of self-supervision here: the whole series is training data."""
    out = ml.pretext(_walk())
    assert out["status"] == "FITTED"
    assert "why_not_admission" in out and "downstream" in out["why_not_admission"]


def test_the_pretext_score_is_not_the_admission_criterion(ml) -> None:
    """A pretext task that learns something real and useless is the normal outcome."""
    src = (_ROOT / "desks" / "mt5" / "research" / "ml_layer.py").read_text("utf-8")
    assert "pretext_r2" in src
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "admitted=pretext" not in body and "pretext_r2 >" not in body, (
        "the pretext score gates an admission; it must never do that")


# --------------------------------------------------------------------------- P9
def test_the_gate_is_refused_on_pure_noise(ml) -> None:
    """THE PROPERTY THAT MATTERS. On a random walk no router can genuinely help, so a mixture
    that admits itself here is routing on noise and would do so on real data too."""
    v = ml.mixture(_walk(seed=11))
    assert v.admitted is False, f"a gate admitted itself on a random walk: {v.why}"
    assert "uniform blend" in v.why


def test_the_gate_is_measured_against_both_baselines(ml) -> None:
    """Beating the best single expert is not enough: a uniform blend is free, and a gate that
    cannot beat free is not a gate."""
    v = ml.mixture(_walk(seed=3))
    assert v.baseline is not None
    assert "best-expert" in v.why and "uniform blend" in v.why


def test_a_short_series_yields_no_admission(ml) -> None:
    v = ml.mixture(_walk(300))
    assert v.admitted is False and v.n_oos >= 0
    assert "rows" in v.why


# --------------------------------------------------------------------------- P42
def test_the_student_is_scored_against_truth_not_the_teacher(ml) -> None:
    """A perfect imitator reproduces the teacher's errors. Agreement would admit it every time."""
    v = ml.distil(_walk())
    assert v.baseline is not None, "no teacher score recorded"
    src = (_ROOT / "desks" / "mt5" / "research" / "ml_layer.py").read_text("utf-8")
    assert "AGREEMENT WITH THE TEACHER IS NOT THE TEST" in src
    assert "_skill(emb[fit_rows:m] @ student_w, y[fit_rows:m])" in src, (
        "the student is no longer scored against y (the truth); if it is scored against the "
        "teacher's output the test has become an agreement test")


# --------------------------------------------------------------------------- contract
def test_nothing_here_owns_a_position(ml) -> None:
    """Challenger-only. A route from a research model to capital is the one thing forbidden."""
    src = (_ROOT / "desks" / "mt5" / "research" / "ml_layer.py").read_text("utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    for banned in ("lot", "order_send", "position_size", "risk_units", "place_order"):
        assert f"def {banned}" not in body and f"return {banned}" not in body, (
            f"ml_layer exposes {banned} -- a challenger model has acquired a route to money "
            "without passing the capital allocator")
    assert ml.run()["challenger_only"] is True
