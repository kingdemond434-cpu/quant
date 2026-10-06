"""The Roman Kalman and Hawkes families: registered, seeded on their pairs, causal."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import families_roman as rm  # noqa: E402
from mt5desk.family_inputs import IDENTITY_KEYS  # noqa: E402
from research import axis_registry as ax  # noqa: E402
from research import elitequant_breadth as eb  # noqa: E402
from research import orthogonal_sweep as osw  # noqa: E402

N = 5000


def _bars(seed: int = 1, close: np.ndarray | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    r = rng.standard_t(4, N) * 0.001
    c = 1.3 * np.exp(np.cumsum(r)) if close is None else close
    o = np.r_[c[0], c[:-1]]
    w = np.abs(rng.normal(0, 0.0005, N)) * c
    idx = pd.date_range("2020-01-01", periods=N, freq="h", tz="UTC")
    vol = rng.lognormal(5, 0.5, N)
    burst = rng.choice(N, 60, replace=False)
    for b in burst:                                       # clustered activity
        vol[b:b + 6] *= 4
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + w, "low": np.minimum(o, c) - w,
                         "close": c, "tick_volume": vol.round(),
                         "spread": rng.integers(5, 15, N).astype(float)}, index=idx)


@pytest.fixture
def pair(monkeypatch):
    rng = np.random.default_rng(9)
    lx = np.cumsum(rng.normal(0, 0.001, N))
    ly = 0.8 * lx + np.r_[0, np.cumsum(rng.normal(0, 0.0004, N - 1))] * 0.2 + \
        np.convolve(rng.normal(0, 0.002, N), np.ones(5) / 5, mode="same")
    peer = _bars(2, np.exp(lx) * 1.1)
    me = _bars(3, np.exp(ly) * 1.2)
    stamps = peer.index.asi8.astype("int64")
    monkeypatch.setattr(rm.xs, "_load_series",
                        lambda s: (stamps, peer["close"].to_numpy(dtype="float32")))
    return me


def test_registered_mapped_seeded_and_kept_out_of_the_blind_sweep():
    for name, fn in rm.ROMAN_FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[name] is fn and fo.FAMILY_INPUTS[name][0] == "price only"
        assert eb.FAMILIES[name] is fn and "rewritten" in eb.ORIGIN[name]
        assert name in ax.FAMILY_TABLE
    for name in rm.PEER_KEYED:
        assert name in osw.NOT_SOURCED_HERE and eb.PAIR_OF[name] is rm.PAIRS
    assert "pair_symbol" not in IDENTITY_KEYS    # the gauntlet must hand it to the family


@pytest.mark.parametrize("mode", ["beta", "mean"])
def test_hedge_spread_fires_and_is_causal(pair, mode):
    sigs = rm.family_kalman_hedge_spread(pair, pair_symbol="P", mode=mode, entry_z=1.5)
    assert len(sigs) >= 10
    cut = pair.index[4000]
    part = {(s.time, s.side) for s in rm.family_kalman_hedge_spread(
        pair.iloc[:4200], pair_symbol="P", mode=mode, entry_z=1.5) if s.time < cut}
    assert part == {(s.time, s.side) for s in sigs if s.time < cut}


def test_no_pair_no_signals():
    assert rm.family_kalman_hedge_spread(_bars(), pair_symbol="") == []


@pytest.mark.parametrize("name,kw", [("kalman_beta_residual", {"pair_symbol": "P"}),
                                     ("kalman_trend", {}), ("kalman_vol_residual", {}),
                                     ("hawkes_flow", {"mode": "sell_cascade_skew",
                                                      "window": 2000, "min_events": 60}),
                                     ("hawkes_flow", {"mode": "arrival_breakout",
                                                      "window": 2000, "min_events": 60})])
def test_fires_with_a_sane_bracket_and_is_causal(pair, name, kw):
    fn = rm.ROMAN_FAMILIES[name]
    if name != "kalman_beta_residual":
        pair = _bars()                                    # fat-tailed bars for the solo legs
    sigs = fn(pair, **kw)
    assert sigs, name
    for s in sigs:
        px = float(pair["close"].loc[s.time])
        assert (px - s.stop) * s.side > 0 and (s.target - px) * s.side > 0
    cut = pair.index[4300]
    part = {(s.time, s.side) for s in fn(pair.iloc[:4500], **kw) if s.time < cut}
    assert part == {(s.time, s.side) for s in sigs if s.time < cut}


def test_bar_events_thresholds_are_read_before_the_bar():
    d = _bars()
    full = rm.bar_events(d)
    part = rm.bar_events(d.iloc[:3000])
    for k in full:
        assert np.array_equal(full[k][:3000], part[k])


def test_cross_excitation_report_names_every_set_and_why(monkeypatch, tmp_path):
    from research import cross_excitation as ce
    from research import proposer_common as pc

    bars = _bars()
    monkeypatch.setattr(pc, "bars", lambda s: bars if s == "XAUUSD" else None)
    monkeypatch.setattr(ce, "OUT", tmp_path / "CROSS_EXCITATION.json")
    monkeypatch.setattr(ce, "WINDOW", 3000)
    rep = ce.run(budget_s=60.0)
    assert rep["status"] == "RAN" and rep["ran"] == ["XAUUSD"]
    x = rep["sets"]["XAUUSD"]
    assert set(x["branching"]) <= {"buy", "sell", "large", "depletion", "vshock"}
    assert all(v["status"] == "UNMEASURED" and v["why"] for k, v in rep["sets"].items()
               if k != "XAUUSD")
    assert (tmp_path / "CROSS_EXCITATION.json").exists()
