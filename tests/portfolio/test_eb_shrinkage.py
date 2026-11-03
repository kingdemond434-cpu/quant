"""Data-driven (James-Stein) shrinkage: inert when off, never looser than the fixed k when on."""

from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio import eb_shrinkage as ebs
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, _posterior_mu


def _family(rng: np.random.Generator, true_means: list[float], *, n: int, sd: float,
            family: str, symbol: str = "XAUUSD") -> list[SleeveEvidence]:
    return [SleeveEvidence(name=f"{family}_{i}", daily_r=rng.normal(mu, sd, n),
                           family=family, symbol=symbol)
            for i, mu in enumerate(true_means)]


def _post(ev: list[SleeveEvidence], *, eb: bool, diag: dict | None = None) -> np.ndarray:
    return _posterior_mu(ev, np.random.default_rng(3), 16, diag, eb=eb)[1]


def test_off_is_bit_identical_to_the_fixed_k_posterior() -> None:
    rng = np.random.default_rng(0)
    ev = _family(rng, [0.05, 0.02, -0.01, 0.08], n=300, sd=1.0, family="gold_asia")
    d0, p0 = _posterior_mu(ev, np.random.default_rng(3), 16)
    d1, p1 = _posterior_mu(ev, np.random.default_rng(3), 16, eb=False)
    assert np.array_equal(p0, p1) and np.array_equal(d0, d1)


def test_k_stays_inside_its_preregistered_bounds() -> None:
    rng = np.random.default_rng(1)
    for _ in range(20):
        m = rng.normal(0, rng.uniform(0.001, 0.5), 8)
        s = rng.uniform(0.2, 2.0, 8)
        eff = rng.uniform(5, 3000, 8)
        k = ebs.eb_k(m, s, eff, ["a"] * 4 + ["b"] * 4, 60.0)
        assert np.all(k >= ebs.K_MIN_RATIO * 60.0) and np.all(k <= ebs.K_MAX)


def test_homogeneous_family_is_pooled_harder_than_fixed_k() -> None:
    # Four sleeves with the SAME true edge: the spread in their sample means is pure noise, so
    # James-Stein finds tau^2 ~ 0 and pulls each toward the family far harder than k=60 does.
    rng = np.random.default_rng(2)
    ev = _family(rng, [0.03] * 5, n=120, sd=1.0, family="gold_asia")
    p_fix, p_eb = _post(ev, eb=False), _post(ev, eb=True)
    assert np.std(p_eb) < 0.5 * np.std(p_fix)


def test_heterogeneous_family_is_pooled_less_two_sided() -> None:
    # True means far apart relative to their standard errors: tau^2 is large, so James-Stein
    # pools LESS than k=60 (down to the 0.25x bound) and each sleeve keeps more of its own,
    # measurably different, mean -- strong evidence may raise capital (two-sided modifier).
    rng = np.random.default_rng(4)
    ev = _family(rng, [0.6, -0.4, 0.2, 1.0], n=200, sd=0.5, family="fx_carry",
                 symbol="AUDJPY")
    diag: dict = {}
    p_fix, p_eb = _post(ev, eb=False), _post(ev, eb=True, diag=diag)
    ks = list(diag["eb"]["k_sleeve"].values())
    assert all(ebs.K_MIN_RATIO * 60.0 <= k < 60.0 for k in ks)
    raw = np.array([e.daily_r.mean() for e in ev])
    assert np.abs(p_eb - raw).sum() < np.abs(p_fix - raw).sum()


def test_small_family_keeps_the_fixed_k() -> None:
    rng = np.random.default_rng(5)
    ev = _family(rng, [0.03, 0.03], n=120, sd=1.0, family="pair")
    diag: dict = {}
    _post(ev, eb=True, diag=diag)
    assert all(v == 60.0 for v in diag["eb"]["k_sleeve"].values())


def test_pooled_vol_never_narrows_the_standard_error() -> None:
    rng = np.random.default_rng(6)
    ev = (_family(rng, [0.02, 0.01, 0.03], n=40, sd=0.3, family="f1")
          + _family(rng, [0.02, 0.01, 0.03], n=40, sd=2.0, family="f1b"))
    d_fix: dict = {}
    d_eb: dict = {}
    _post(ev, eb=False, diag=d_fix)
    _post(ev, eb=True, diag=d_eb)
    for name, se in d_fix["se"].items():
        assert d_eb["se"][name] >= se - 1e-15


def test_pooled_vol_moves_a_short_sleeve_toward_its_family() -> None:
    s = np.array([0.5, 1.0, 1.0, 1.0])
    obs = np.array([10.0, 1000.0, 1000.0, 1000.0])
    out = ebs.pooled_vol(s, obs, ["g"] * 4)
    assert 0.5 < out[0] < 1.0 and np.allclose(out[1:], 1.0, atol=0.01)


@pytest.mark.parametrize("val,want", [("1", True), ("on", True), ("0", False), ("", False)])
def test_arm_reads_env_and_reaches_every_world_config(monkeypatch: pytest.MonkeyPatch,
                                                      val: str, want: bool) -> None:
    # One arm, read by WorldConfig itself: every book that samples worlds (E8 pf_allocator,
    # Fusion kelly_survival, FTMO prop_challenge_allocator) switches together.
    monkeypatch.setenv(ebs.ARM_ENV, val)
    assert ebs.eb_armed() is want
    assert WorldConfig().eb_shrinkage is want


def test_arm_off_by_default_without_env_or_file(monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv(ebs.ARM_ENV, raising=False)
    monkeypatch.setattr(ebs, "ARM_FILE", tmp_path / "EB_SHRINKAGE_ARMED")
    assert ebs.eb_armed() is False
    (tmp_path / "EB_SHRINKAGE_ARMED").write_text("")
    assert ebs.eb_armed() is True
