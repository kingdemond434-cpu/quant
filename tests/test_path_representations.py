"""Path representations recover planted shapes."""
from __future__ import annotations

import numpy as np

from libs.research import path_representations as pr


def _fbm_like(h: float, n: int, seed: int) -> np.ndarray:
    """Persistent or anti-persistent increments by fractional differencing of white noise."""
    rng = np.random.default_rng(seed)
    d = h - 0.5
    k = np.arange(1, 200)
    w = np.r_[1.0, np.cumprod((k - 1 - d) / k)]
    e = rng.normal(0, 1, n + w.size)
    inc = np.convolve(e, w, mode="valid")[:n]
    return np.cumsum(inc)


def test_hurst_orders_persistent_random_and_antipersistent_paths():
    rng = np.random.default_rng(0)
    walk = np.cumsum(rng.normal(0, 1, 4000))
    assert abs(pr.hurst_variogram(walk) - 0.5) < 0.05
    assert pr.hurst_variogram(_fbm_like(0.75, 4000, 1)) > 0.6
    assert pr.hurst_variogram(_fbm_like(0.25, 4000, 2)) < 0.4


def test_bridge_excursion_is_small_on_a_line_and_large_on_a_hump():
    t = np.linspace(0, 1, 49)
    rng = np.random.default_rng(3)
    line = 0.5 * t * 48 + rng.normal(0, 0.01, 49).cumsum()
    hump = np.sin(np.pi * t) * 5 + rng.normal(0, 0.01, 49).cumsum()
    assert pr.bridge_excursion(line) < pr.bridge_excursion(hump)


def test_kl_basis_recovers_the_dominant_shape_and_coeffs_are_causal():
    rng = np.random.default_rng(4)
    x = np.cumsum(rng.normal(0, 1, 3000))
    basis = pr.kl_basis(x[:2000], 24, 3)
    assert basis.shape == (3, 24)
    full = pr.kl_coeffs(x, basis)
    assert np.allclose(full[:2500], pr.kl_coeffs(x[:2500], basis), equal_nan=True)


def test_levy_area_sign_flips_with_the_path_orientation():
    t = np.linspace(0, 1, 50)
    x = t ** 2
    a = pr.signature_level2(t, x)["levy_area"]
    b = pr.signature_level2(t, np.sqrt(t))["levy_area"]
    assert a * b < 0
