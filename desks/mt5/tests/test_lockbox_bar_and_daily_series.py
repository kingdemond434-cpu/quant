"""The v4 lockbox bar, the measured DSR variance, and the per-day trade sum (2026-09-30).

    python -m pytest desks/mt5/tests/test_lockbox_bar_and_daily_series.py -q

The sealed 2,100-case suite showed the deflated-Sharpe gate rejected all 600 planted real edges
under the old variance constant, and that lowering the variance alone let overfit lookup tables
through, because gate 9 passed any held-out Sharpe >= 0. On the desktop re-run of the patched
judge (448 cases, 130 real, 318 traps) this bar certified 15 real edges and 0 traps.

WHAT MUST NOT REGRESS:
  1. a held-out Sharpe >= 0 but under the cell's deflated hurdle FAILS gate 9
  2. an edge that lives only in the first half of the series FAILS gate 9 (half-split read)
  3. a persistent edge that clears the hurdle everywhere PASSES gate 9
  4. the spec's variance and the attested basis name the same number
  5. two trades on one entry day are SUMMED, never overwritten by the later one
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    sys.path.insert(0, str(p))

from research import gate_policy as gp  # noqa: E402

from libs.validation.dsr import sharpe_ratio  # noqa: E402


def _series(mu: float, n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).normal(mu, 1.0, n)


def test_a_held_out_sharpe_under_the_hurdle_fails_even_when_positive() -> None:
    dev = _series(0.30, 320, 1)
    held = np.full(80, 0.01) + _series(0.0, 80, 2) * 1e-3   # Sharpe > 0, far under sr0
    assert sharpe_ratio(held) > 0.0
    out = gp.lockbox_stage(held, sharpe_ratio, dev=dev, sr0=0.2)
    assert out["passed"] is False, out
    assert out["hurdle_sr0"] == 0.2


def test_an_edge_that_decays_after_the_fitted_window_fails_the_half_split() -> None:
    dev = np.concatenate([_series(0.6, 200, 3), _series(0.05, 120, 4)])
    held = _series(0.05, 80, 5)
    out = gp.lockbox_stage(held, sharpe_ratio, dev=dev, sr0=0.0)
    assert out["half_degradation_z"] > gp.LOCKBOX_MAX_HALF_Z
    assert out["passed"] is False, out


def test_a_persistent_edge_passes() -> None:
    # One 40-day noise block repeated: every window carries the same edge, so the half-split
    # read is exactly 0 and the test pins the rule rather than a lucky random draw.
    full = np.tile(_series(0.35, 40, 6), 10)
    dev, held = full[:320], full[320:]
    out = gp.lockbox_stage(held, sharpe_ratio, dev=dev, sr0=0.036)
    assert out["passed"] is True, out


def test_too_few_held_out_rows_still_fail_closed() -> None:
    out = gp.lockbox_stage(np.ones(5), sharpe_ratio, dev=np.ones(300), sr0=0.0)
    assert out["passed"] is False and out["lockbox_sharpe"] is None


def test_the_attested_basis_names_the_spec_variance() -> None:
    v = gp.FIXED_VARIANCE_OF_SHARPES
    assert isinstance(v, float) and 0 < v < 0.014863
    assert f"fixed_variance_of_sharpes({v:g})" in gp.TRIAL_COUNT_BASIS
    assert "(v4)" in gp.ATTESTATION["lockbox_basis"]


def test_two_trades_on_one_day_are_summed(monkeypatch) -> None:
    import external_gauntlet as eg
    d0 = datetime(2026, 1, 5, 9)
    trades = [SimpleNamespace(entry_time=d0, r_multiple=1.0),
              SimpleNamespace(entry_time=d0 + timedelta(hours=3), r_multiple=-2.0),
              SimpleNamespace(entry_time=d0 + timedelta(days=1), r_multiple=0.5)]
    monkeypatch.setattr(eg, "run_backtest", lambda df, sigs, costs: SimpleNamespace(trades=trades))
    s = eg.daily_series(pd.DataFrame(), [], None)
    assert list(s.to_numpy()) == [-1.0, 0.5], "the later same-day trade overwrote the first"
