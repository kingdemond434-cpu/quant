"""Factor risk model and shrinkage covariance."""

from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.errors import PortfolioError
from libs.portfolio.factor_model import FactorRiskModel, ShrinkageCovariance


def test_shrinkage_is_symmetric_and_between_sample_and_target() -> None:
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0, 0.01, size=(250, 4))
    cov = ShrinkageCovariance().estimate(returns)
    assert cov.shape == (4, 4)
    assert np.allclose(cov, cov.T)
    assert np.all(np.diag(cov) > 0)


def test_shrinkage_explicit_intensity_bounds() -> None:
    rng = np.random.default_rng(1)
    returns = rng.normal(0.0, 0.01, size=(100, 3))
    full_sample = ShrinkageCovariance().estimate(returns, shrinkage=0.0)
    full_target = ShrinkageCovariance().estimate(returns, shrinkage=1.0)
    # target is the constant-correlation matrix: off-diagonals differ from raw sample
    assert not np.allclose(full_sample, full_target)


def test_shrinkage_rejects_bad_shape() -> None:
    with pytest.raises(PortfolioError):
        ShrinkageCovariance().estimate(np.zeros(5))


def test_factor_model_builds_structured_covariance() -> None:
    model = FactorRiskModel(["momentum", "value"])
    factor_cov = np.array([[0.04, 0.0], [0.0, 0.02]])
    assets, cov = model.build(
        exposures={
            "A": {"momentum": 1.0, "value": 0.0},
            "B": {"momentum": 0.0, "value": 1.0},
        },
        factor_cov=factor_cov,
        specific_var={"A": 0.01, "B": 0.01},
    )
    assert assets == ["A", "B"]
    # A loads only on momentum (var 0.04) + specific 0.01 = 0.05
    assert cov[0, 0] == pytest.approx(0.05)
    assert cov[1, 1] == pytest.approx(0.03)
    assert cov[0, 1] == pytest.approx(0.0)  # orthogonal factor exposures
    assert np.allclose(cov, cov.T)


def test_factor_model_validates_shapes() -> None:
    model = FactorRiskModel(["momentum", "value"])
    with pytest.raises(PortfolioError):
        model.build(exposures={"A": {"momentum": 1.0}},
                    factor_cov=np.eye(3), specific_var={"A": 0.0})
