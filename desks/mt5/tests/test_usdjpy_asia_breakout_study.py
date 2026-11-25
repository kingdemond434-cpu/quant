"""The USDJPY asia breakout study judges at the Tier S bar (N = 5, variance 1/(T-1)) and never
charges a zero spread on an arm it selects on."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import usdjpy_asia_breakout_study as study  # noqa: E402

from libs.validation.dsr import deflated_sharpe_ratio  # noqa: E402


def test_the_bar_is_n5_with_per_cell_null_variance() -> None:
    r = np.random.default_rng(7).normal(0.1, 1.0, 400)
    got = study.tier_s_dsr(r)
    want = deflated_sharpe_ratio(r, n_trials=5, variance_of_sharpes=1.0 / 399, threshold=0.95)
    assert study.BAR_N == 5
    assert got["dsr"] == round(want.dsr, 4)
    assert got["sr0"] == round(want.sr0_threshold, 4)


def test_too_few_observations_is_unmeasured_not_a_verdict() -> None:
    assert study.tier_s_dsr(np.array([0.5, -1.0]))["status"] == "UNMEASURED"


def test_the_selection_arm_is_never_zero_cost() -> None:
    assert study.ARMS["PRIMARY"][0] > 0
    assert study.ARMS["STRESS"][0] >= 2 * study.ARMS["PRIMARY"][0]
    assert len(study.VARIANTS) == study.BAR_N


def test_noise_band_contains_its_own_mean() -> None:
    r = np.random.default_rng(1).normal(0.1, 1.0, 600)
    band = study.noise_band(r, 20, float(r.mean()), draws=2000)
    assert band["inside_95"] is True
    assert band["bootstrap_95"][0] < band["backtest_mean_r"] < band["bootstrap_95"][1]


def test_report_paths_are_repo_relative_never_absolute(tmp_path) -> None:
    assert study._rel(study.BARS) == "desks/mt5/data/universe/USDJPY_H1.parquet"
    assert study._rel(tmp_path / "x.parquet") == "x.parquet"
    assert study.OUT.parent.name == "reports"


def test_the_hourly_leg_never_runs_the_gauntlet(tmp_path, monkeypatch) -> None:
    """SF2: the hourly leg calls the study with NO arguments, so `--gauntlet` (a full
    external_gauntlet run) is never reached from the schedule; only a human passes it."""
    import importlib
    import re

    import hourly_cycle as hc

    src = Path(hc.__file__).read_text(encoding="utf-8")
    calls = re.findall(r'_report_step\(\s*"usdjpy_asia_breakout_study"([^)]*)\)', src)
    assert calls == [""], calls                 # one call site, no extra arguments
    assert "--gauntlet" not in src

    mod = importlib.import_module("research.usdjpy_asia_breakout_study")
    seen: list[bool] = []

    def fake_run(bars, gauntlet, forward_ledger):
        seen.append(gauntlet)
        return {"selection": None, "noise": None}

    monkeypatch.setattr(mod, "run", fake_run)
    monkeypatch.setattr(mod, "OUT", tmp_path / "USDJPY_ASIA_BREAKOUT_STUDY.json")
    leg = hc._report_step("usdjpy_asia_breakout_study")
    assert leg.get("exit_code") == 0, leg
    assert seen == [False]
    assert (tmp_path / "USDJPY_ASIA_BREAKOUT_STUDY.json").is_file()
