"""ROCKET random-convolution and autoencoder latent-factor families (2026-10-13).

Same three duties as the GNN and attention families: recover a planted signal, find nothing on
noise, and never let the future change a past prediction. Plus the autoencoder's hand-written
gradients against finite differences, and the miner's retail-heavy panel bookkeeping.
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
META_ROW = {"contract_size": 100000.0, "tick_size": 1e-05, "tick_value": 0.8632298608473467,
            "min_volume": 0.01, "volume_step": 0.01, "median_spread_pts": 12.0}


def _panel(ret: np.ndarray) -> LP.Panel:
    dates = pd.bdate_range("2019-01-01", periods=ret.shape[0], tz="UTC")
    return LP.Panel(dates, [f"S{j:02d}" for j in range(ret.shape[1])], ret,
                    np.full(ret.shape, 5e-5))


def _common_state_returns(t_n: int = 1000, seed: int = 4) -> np.ndarray:
    """Nodes 1..7 load on a NON-LINEAR function of node 0's last three days."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, (t_n, 8))
    for t in range(3, t_n - 1):
        r[t + 1, 1:] += 0.01 * np.tanh(r[t - 2:t + 1, 0].sum() / 0.01)
    return r


def _shape_returns(t_n: int = 1000, seed: int = 6) -> np.ndarray:
    """Each node reverses after a two-day same-sign run: a path SHAPE, not a linear lag."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, (t_n, 8))
    for t in range(2, t_n - 1):
        run = (np.sign(r[t]) == np.sign(r[t - 1])) & (np.abs(r[t]) > 0.008)
        r[t + 1] -= 0.008 * np.sign(r[t]) * run
    return r


def test_autoencoder_gradients_match_finite_differences() -> None:
    v = np.random.default_rng(1).normal(size=(80, 12))
    m = LP.train_autoencoder(v, latent=3, hidden=6, epochs=1)
    vs = (v - m.mu) / m.sd
    _l0, g = LP.ae_loss_grads(m, vs)
    for key in ("w1", "b1", "w2", "b2", "w3", "b3"):
        p = getattr(m, key)
        idx = tuple(np.unravel_index(min(2, p.size - 1), p.shape))
        e = 1e-6
        p[idx] += e
        lp_, _ = LP.ae_loss_grads(m, vs)
        p[idx] -= 2 * e
        lm_, _ = LP.ae_loss_grads(m, vs)
        p[idx] += e
        num = (lp_ - lm_) / (2 * e) + (LP.AE_L2 * p[idx] if key.startswith("w") else 0.0)
        assert g[key][idx] == pytest.approx(num, rel=1e-4, abs=1e-7), key


def test_the_autoencoder_recovers_a_planted_non_linear_common_state() -> None:
    panel = _panel(_common_state_returns())
    d = LP.design(panel)
    ae = LP.evaluate(LP.predictions(d, "autoencoder", LP.AE_GRID[0], **WF), panel, d,
                     start=WF["min_train"])
    ridge = LP.evaluate(LP.predictions(d, "ridge", {}, **WF), panel, d, start=WF["min_train"])
    assert ae["ic_mean"] is not None and ae["ic_t"] > 3.0, ae
    assert ae["ic_mean"] > (ridge["ic_mean"] or 0.0), (ae, ridge)


def test_rocket_recovers_a_planted_path_shape() -> None:
    panel = _panel(_shape_returns())
    d = LP.design(panel)
    ev = LP.evaluate(LP.predictions(d, "rocket", LP.ROCKET_GRID[2], **WF), panel, d,
                     start=WF["min_train"])
    assert ev["ic_mean"] is not None and ev["ic_t"] > 3.0, ev


@pytest.mark.parametrize("model,config", [("rocket", LP.ROCKET_GRID[2]),
                                          ("autoencoder", LP.AE_GRID[0])])
def test_pure_noise_carries_no_significant_ic(model: str, config: dict) -> None:
    panel = _panel(np.random.default_rng(17).normal(0, 0.01, (1000, 8)))
    d = LP.design(panel)
    ev = LP.evaluate(LP.predictions(d, model, config, **WF), panel, d, start=WF["min_train"])
    assert ev["ic_t"] is not None and abs(ev["ic_t"]) < 3.0, ev


@pytest.mark.parametrize("model,config", [("rocket", LP.ROCKET_GRID[2]),
                                          ("autoencoder", LP.AE_GRID[1])])
def test_perturbing_the_future_never_changes_a_past_prediction(model: str, config: dict) -> None:
    ret = _common_state_returns(t_n=700)
    t0 = 520
    fut = ret.copy()
    fut[t0 + 1:] = np.random.default_rng(99).normal(0, 0.05, fut[t0 + 1:].shape)
    p1 = LP.predictions(LP.design(_panel(ret)), model, config, **WF)
    p2 = LP.predictions(LP.design(_panel(fut)), model, config, **WF)
    assert np.isfinite(p1[WF["min_train"]:t0 + 1]).all()
    np.testing.assert_allclose(p1[:t0 + 1], p2[:t0 + 1], equal_nan=True)


def test_rocket_kernels_are_data_free_and_fixed_by_seed() -> None:
    a = LP.rocket_kernels(32, 8, 3)
    b = LP.rocket_kernels(32, 8, 3)
    assert all(np.array_equal(x[0], y[0]) and x[1:] == y[1:] for x, y in zip(a, b, strict=True))
    assert all((LP.ROCKET_KLEN - 1) * k[2] < 32 for k in a)


def test_the_new_families_are_registered_and_refuse_bare_proposals() -> None:
    import axis_registry as AR
    from mt5desk import families_orthogonal as FO
    for fam in ("rocket_ts", "ae_latent"):
        assert fam in FO.ORTHOGONAL_FAMILIES and fam in FO.FAMILY_INPUTS
        assert fam in FO.FAMILY_TIMEFRAMES
        assert fam in AR.NOT_A_FAMILY and fam in AR.FAMILY_TABLE
    assert FO.ORTHOGONAL_FAMILIES["rocket_ts"](pd.DataFrame(), symbol="", peer_symbols=[]) == []


def test_the_retail_panel_is_declared_tagged_and_skipped_when_short(tmp_path: Path) -> None:
    import learned_miners as LM
    assert set(LM.PANELS) == {"core", "retail_heavy"}
    assert all(LM.participant_structure(s) == "retail_heavy"
               for s in ("BTCUSD", "SOLUSD", "CHINAH", "HK50"))
    trial_ids = []

    def fake_mine(model, bars, meta, *, deadline, panel_name="core", **_k):
        trial_ids.append((model, panel_name))
        return {"source": "x", "configs": {}, "proposals": [], "rows": [], "_trials": [],
                "tests_attempted": 0, "effective_trials": 0.0, "panel": sorted(bars)}

    orig_mine, orig_load = LM.mine, LM.load_bars
    try:
        LM.mine = fake_mine
        LM.load_bars = lambda symbols=LM.PANEL, base=None: {}
        res = LM.run(budget_s=1, donate=False, report=tmp_path / "r.json",
                     trials_path=tmp_path / "t.jsonl", publish_axes=False)
    finally:
        LM.mine, LM.load_bars = orig_mine, orig_load
    assert res["panels"]["retail_heavy"]["status"].startswith("UNMEASURED")
    assert res["panels"]["core"]["status"].startswith("UNMEASURED")
    assert trial_ids == []
