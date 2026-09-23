"""PCA against the contrastive encoder, on the same folds, by the same scorer (G13).

`libs/models/embedding.py` carries an InfoNCE encoder, alignment/uniformity diagnostics and
`representation_gain`, and had NO importer outside a test -- a scored representation nothing ran,
while the desk's frontier report ranked REPRESENTATION_LEARNING as its largest capability gap.
The live representation was a k=4 PCA whose only reader was the dashboard. What is pinned: both
encoders are measured on identical windows, identical folds and an identical raw baseline; the
forward series is the one that FOLLOWS each window; the runtime is bounded and declared; a short
series is UNMEASURED rather than a verdict; and the PCA projection every existing consumer reads
is unchanged.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[2] / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ml_layer as ml  # noqa: E402


def _walk(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))


def _autoregressive(n: int, rho: float = 0.6, seed: int = 3) -> np.ndarray:
    """A series whose NEXT return is a known function of the current one: the raw last bar can
    forecast it, which is what makes the window/forward alignment testable."""
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    eps = rng.normal(0, 0.001, n)
    for i in range(1, n):
        r[i] = rho * r[i - 1] + eps[i]
    return 100 * np.exp(np.cumsum(r))


@pytest.fixture(scope="module")
def contest() -> dict:
    return ml.representation_contest(_walk(5000))


def test_both_encoders_are_measured_on_the_same_windows_and_folds(contest) -> None:
    assert contest["status"] == "MEASURED"
    a, b = contest["window_pca"], contest["contrastive"]
    assert a["n"] == b["n"] == contest["windows"]
    assert a["folds"] == b["folds"] == ml.CONTEST_FOLDS
    assert a["raw"] == b["raw"], (
        "the two encoders must face the SAME raw baseline, or the gains are not comparable")
    for side in (a, b):
        assert side["gain"] == pytest.approx(side["embedding"] - side["raw"], abs=1e-6)
        assert side["verdict"] in ("ADMIT", "REFUSE")


def test_the_contest_names_a_winner_and_the_spread(contest) -> None:
    assert contest["better"] in ("window_pca", "contrastive")
    spread = contest["contrastive"]["gain"] - contest["window_pca"]["gain"]
    assert contest["gain_spread"] == pytest.approx(spread, abs=1e-6)
    assert (contest["better"] == "contrastive") == (contest["gain_spread"] > 0)


def test_a_random_walk_admits_neither(contest) -> None:
    """Nothing forecasts a random walk. A representation that ADMITTED here would be measuring
    the fixture, and the rule that stops it is in `representation_gain`: the embedding's OWN
    score must be positive, not merely better than a useless baseline."""
    assert contest["window_pca"]["verdict"] == "REFUSE"
    assert contest["contrastive"]["verdict"] == "REFUSE"
    assert contest["window_pca"]["embedding"] < 0.05


def test_the_forward_series_is_the_one_that_follows_each_window() -> None:
    """On an AR(1) series the LAST BAR of the window predicts the next return, so the raw
    baseline must score well. Shift the alignment by one and this collapses -- which is exactly
    what makes it a pin on the join rather than on the encoders."""
    got = ml.representation_contest(_autoregressive(5000))
    assert got["status"] == "MEASURED"
    assert got["window_pca"]["raw"] > 0.05, got["window_pca"]


def test_a_short_series_is_unmeasured_with_its_reason() -> None:
    got = ml.representation_contest(_walk(400))
    assert got["status"] == "INSUFFICIENT"
    assert "the contest needs" in got["why"]
    assert "window_pca" not in got and "contrastive" not in got


def test_the_runtime_bound_is_declared_and_honoured() -> None:
    """This runs on the hourly leg over several series; the cap is stated in the report rather
    than discovered as a timeout."""
    t0 = time.monotonic()
    got = ml.representation_contest(_walk(20_000))
    elapsed = time.monotonic() - t0
    assert got["windows"] <= ml.CONTEST_MAX_WINDOWS
    assert str(ml.CONTEST_MAX_WINDOWS) in got["bound"] and "Adam steps" in got["bound"]
    assert elapsed < 30.0, f"the bounded contest took {elapsed:.1f}s on 20k bars"


def test_the_pca_projection_every_consumer_reads_is_unchanged() -> None:
    close = _walk(3000)
    with_contest = ml.representation(close)
    without = ml.representation(close, contest=False)
    assert "gain" not in without
    for key in ("status", "k", "rows", "fit_rows", "explained_variance"):
        assert with_contest[key] == without[key]
    assert np.array_equal(with_contest["components"], without["components"])
    assert with_contest["gain"]["status"] == "MEASURED"


def test_the_distillation_does_not_pay_for_the_contest() -> None:
    import inspect
    src = inspect.getsource(ml.distil)
    assert "contest=False" in src, (
        "distillation is scored on its own OOS skill; two encoder fits here buy nothing")


def test_a_missing_embedding_module_is_named_not_fatal(monkeypatch) -> None:
    import builtins
    real = builtins.__import__

    def _blocked(name, *a, **kw):
        if name.startswith("libs.models.embedding"):
            raise ImportError("blocked for the test")
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    got = ml.representation_contest(_walk(3000))
    assert got["status"] == "UNAVAILABLE" and "ImportError" in got["why"]
