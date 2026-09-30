"""intelligent-trading-bot's generators and labels, Deep-Trading's window and volatility target.

Pinned: every ITB feature is a past window (truncating the future changes nothing); the port
matches the upstream arithmetic; the top/bottom label looks at most `h` bars ahead; and the model
search judges the new representations and targets as ordinary charged trials whose winners leave
only as conditioning models.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.features import itb  # noqa: E402
from libs.research import model_families as MF  # noqa: E402
from research import model_search as MS  # noqa: E402
from research import proposer_common as pc  # noqa: E402


def _bars(n: int = 4000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.001, n) * (1 + 3 * (idx.hour < 8))))
    w = np.abs(rng.normal(0, 0.0004, n))
    return pd.DataFrame({"open": close, "high": close + w, "low": close - w, "close": close,
                         "tick_volume": rng.integers(50, 500, n).astype(float)}, index=idx)


def test_port_matches_upstream_arithmetic():
    x = np.array([1.0, 3.0, 2.0, 5.0, 4.0])
    assert itb.slope_fn(x) == pytest.approx(np.polyfit(np.arange(5), x, 1)[0])
    assert itb.fmax_fn(x) == pytest.approx(3 / 5)
    assert itb.lsbm_fn(np.array([1.0, 1.0, 5.0, 1.0, 1.0, 1.0])) == pytest.approx(3 / 6)
    assert itb.area_fn(np.array([1.0, 2.0, 3.0])) == pytest.approx(-1.0)   # all below newest
    assert itb.area_fn(np.array([3.0, 2.0, 1.0])) == pytest.approx(1.0)    # all above newest
    assert np.isnan(itb.area_fn(np.ones(4)))


def test_every_itb_feature_is_a_past_window():
    d = _bars()
    full = itb.features(d)
    cut = itb.features(d.iloc[:1800])
    pd.testing.assert_frame_equal(full.iloc[:1800], cut)
    assert full.iloc[100:].notna().all().all()


def test_extremum_label_marks_a_planted_top_and_sees_only_h_bars_ahead():
    d = _bars()
    c = d["close"].copy()
    i = 1500
    c.iloc[i - 3:i + 4] *= np.array([1.00, 1.01, 1.02, 1.03, 1.02, 1.01, 1.00])
    lab = itb.extremum_labels(c, is_max=True, horizon=6)
    assert lab.iloc[i] == 1.0
    assert itb.extremum_labels(c, is_max=False, horizon=6).iloc[i] == 0.0
    short = itb.extremum_labels(c.iloc[:i + 7], is_max=True, horizon=6)
    assert short.iloc[i] == lab.iloc[i]
    pd.testing.assert_series_equal(short.iloc[:i + 1], lab.iloc[:i + 1])


def test_grid_crosses_extra_targets_only_on_their_representations():
    assert {"itb", "dt_window"} <= set(MS.REPRESENTATIONS)
    assert set(MS.TARGETS) == {"sign", "top", "bot", "vol_up"}
    d = _bars()
    y = MS._target(d, 6, "vol_up")
    assert np.isfinite(y[:-6]).mean() > 0.9 and np.isnan(y[-6:]).all()
    assert MS.cell_name("itb", "sign") == "itb" and MS.cell_name("itb", "top") == "itb@top"


def test_model_search_judges_the_new_rows_as_charged_trials(monkeypatch, tmp_path):
    monkeypatch.setattr(MF, "_health_cache",
                        {"measured_utc": 9e18, "probe_complete": True, "passes": 0,
                         "state": dict.fromkeys(MF.FAMILIES, "ok")})
    d = _bars()
    monkeypatch.setattr(pc, "bars", lambda s: d)
    monkeypatch.setattr(MS, "_symbols", lambda explicit: (["TESTFX"], {"source": "test"}))
    monkeypatch.setattr(MS, "TRIALS", tmp_path / "trials.jsonl")
    doc = MS.run(budget_s=240.0, families=("linear", "tree"), reps=("itb", "dt_window"),
                 allow_heavy=False, write_queue=False, enqueue=False, n_bars=4000,
                 report=tmp_path / "MODEL_SEARCH.json")
    rows = set(doc["compatibility_matrix"]["representations"])
    assert rows == {"itb", "itb@top", "itb@bot", "itb@vol_up", "dt_window", "dt_window@vol_up"}
    assert doc["cells_tested"] == 12 and doc["trials"]["n_raw"] == 12
    # the session-volatility planted in the bars is what dt_window@vol_up should find
    assert doc["representation_verdicts"]["dt_window@vol_up"]["verdict"] == "ALIVE"
