"""Rough-path signature family sig_path (2026-10-13, GAP_MAP row 54).

The signature is checked against its closed forms (level one is the total increment, the
symmetric part of level two is half its outer square, the antisymmetric part is the Levy
area), and the family carries the same three duties as the other learned families: recover a
planted order effect, find nothing on noise, never let the future change a past prediction.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.models import learned_propagation as LP  # noqa: E402

WF = {"min_train": 300, "refit_every": 50, "window": 600}


def _panel(ret: np.ndarray) -> LP.Panel:
    dates = pd.bdate_range("2019-01-01", periods=ret.shape[0], tz="UTC")
    return LP.Panel(dates, [f"S{j:02d}" for j in range(ret.shape[1])], ret,
                    np.full(ret.shape, 5e-5))


def _order_returns(t_n: int = 1000, seed: int = 8) -> np.ndarray:
    """Each node catches up next day with what the panel did BEFORE it over the last three days
    (a lead-lag area), with no linear own-lag content."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, (t_n, 8))
    for t in range(3, t_n - 1):
        mkt = r[t - 2:t + 1].mean(axis=1)
        for i in range(8):
            area = float(np.sum(mkt[:-1] * r[t - 1:t + 1, i] - r[t - 2:t, i] * mkt[1:]))
            r[t + 1, i] += 60.0 * area
    return r


def test_level_one_and_two_match_the_closed_forms() -> None:
    d = LP.design(_panel(np.random.default_rng(3).normal(0, 0.01, (120, 4))))
    lk = 10
    f = LP.signature_features(d, depth=2, lookback=lk)
    seq = LP._sequences(np.stack([LP.tokens(d)[..., 0], LP.tokens(d)[..., 2],
                                  np.ones_like(d.z)], axis=-1), lk) / np.sqrt(lk)
    t, i = 80, 2
    inc = seq[t, i][::-1]                       # oldest first
    total = inc.sum(axis=0)
    np.testing.assert_allclose(f[t, i, :3], total, atol=1e-12)
    s2 = f[t, i, 3:12].reshape(3, 3)
    np.testing.assert_allclose((s2 + s2.T) / 2.0, np.outer(total, total) / 2.0, atol=1e-12)
    path = np.vstack([np.zeros(3), np.cumsum(inc, axis=0)])
    levy = 0.5 * np.sum(path[:-1, 0] * inc[:, 1] - path[:-1, 1] * inc[:, 0])
    assert (s2[0, 1] - s2[1, 0]) / 2.0 == pytest.approx(levy, abs=1e-12)


def test_depth_three_has_its_closed_form_symmetric_part() -> None:
    d = LP.design(_panel(np.random.default_rng(5).normal(0, 0.01, (90, 3))))
    f = LP.signature_features(d, depth=3, lookback=10)
    assert f.shape[-1] == 3 + 9 + 27
    s1, s3 = f[60, 1, :3], f[60, 1, 12:].reshape(3, 3, 3)
    assert s3[0, 0, 0] == pytest.approx(s1[0] ** 3 / 6.0, rel=1e-9, abs=1e-15)
    with pytest.raises(ValueError):
        LP.signature_features(d, depth=4, lookback=10)


def test_the_signature_recovers_a_planted_order_effect_that_ridge_misses() -> None:
    panel = _panel(_order_returns())
    d = LP.design(panel)
    sig = LP.evaluate(LP.predictions(d, "signature", LP.SIG_GRID[0], **WF), panel, d,
                      start=WF["min_train"])
    ridge = LP.evaluate(LP.predictions(d, "ridge", {}, **WF), panel, d, start=WF["min_train"])
    assert sig["ic_mean"] is not None and sig["ic_t"] > 3.0, sig
    assert sig["ic_mean"] > (ridge["ic_mean"] or 0.0), (sig, ridge)


def test_pure_noise_carries_no_significant_ic() -> None:
    panel = _panel(np.random.default_rng(23).normal(0, 0.01, (1000, 8)))
    d = LP.design(panel)
    ev = LP.evaluate(LP.predictions(d, "signature", LP.SIG_GRID[1], **WF), panel, d,
                     start=WF["min_train"])
    assert ev["ic_t"] is not None and abs(ev["ic_t"]) < 3.0, ev


def test_perturbing_the_future_never_changes_a_past_prediction() -> None:
    ret = _order_returns(t_n=700)
    t0 = 520
    fut = ret.copy()
    fut[t0 + 1:] = np.random.default_rng(99).normal(0, 0.05, fut[t0 + 1:].shape)
    p1 = LP.predictions(LP.design(_panel(ret)), "signature", LP.SIG_GRID[3], **WF)
    p2 = LP.predictions(LP.design(_panel(fut)), "signature", LP.SIG_GRID[3], **WF)
    assert np.isfinite(p1[WF["min_train"]:t0 + 1]).all()
    np.testing.assert_allclose(p1[:t0 + 1], p2[:t0 + 1], equal_nan=True)


def test_sig_path_is_registered_charged_and_refuses_bare_proposals() -> None:
    import axis_registry as AR
    import learned_miners as LM
    from mt5desk import families_orthogonal as FO
    assert "sig_path" in FO.ORTHOGONAL_FAMILIES and "sig_path" in FO.FAMILY_INPUTS
    assert "sig_path" in FO.FAMILY_TIMEFRAMES
    assert "sig_path" in AR.NOT_A_FAMILY and "sig_path" in AR.FAMILY_TABLE
    assert LM.MINERS["signature"]["family"] == "sig_path"
    assert LM.MINERS["signature"]["grid"] is LP.SIG_GRID
    assert FO.ORTHOGONAL_FAMILIES["sig_path"](pd.DataFrame(), symbol="", peer_symbols=[]) == []
    assert FO.ORTHOGONAL_FAMILIES["sig_path"](pd.DataFrame(), symbol="", peer_symbols=[],
                                              depth=5) == []
