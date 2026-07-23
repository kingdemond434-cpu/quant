"""Tests for the stationarity / GARCH wrappers (statsmodels + arch).

Skipped unless the optional ``[stats]`` extra is installed. Warnings are ignored here because
statsmodels/arch emit convergence and future warnings that the project's warnings-as-errors policy
would otherwise turn into failures — the wrapper's job is the numeric result, not warning hygiene.
"""

from __future__ import annotations

import numpy as np
import pytest

# The wrapper module imports fine without the backends (they are imported lazily inside each
# function), so the import leads; importorskip then skips the whole module if the extra is absent.
from libs.research.stationarity import (
    adf_pvalue,
    engle_granger_pvalue,
    garch_conditional_vol,
)

pytest.importorskip("statsmodels")
pytest.importorskip("arch")


@pytest.mark.filterwarnings("ignore")
def test_random_walk_nonstationary_but_its_diff_is_stationary() -> None:
    rng = np.random.default_rng(0)
    rw = np.cumsum(rng.normal(size=500))
    assert adf_pvalue(rw) > 0.10           # unit root not rejected -> non-stationary
    assert adf_pvalue(np.diff(rw)) < 0.05  # first difference is stationary


@pytest.mark.filterwarnings("ignore")
def test_cointegrated_pair_has_low_pvalue() -> None:
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.normal(size=500))
    y = x + rng.normal(scale=0.5, size=500)  # y = x + stationary noise -> cointegrated
    assert engle_granger_pvalue(y, x) < 0.05


@pytest.mark.filterwarnings("ignore")
def test_garch_conditional_vol_shape_and_positivity() -> None:
    rng = np.random.default_rng(2)
    cv = garch_conditional_vol(rng.normal(scale=1.0, size=400))
    assert cv.shape == (400,)
    assert np.all(cv > 0.0)
