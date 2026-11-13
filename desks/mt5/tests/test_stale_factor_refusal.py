"""A factor that stopped updating is refused BY NAME, never handed to an inner join that empties.

Measured on the box 2026-11-11: UST10Y has no bars after 2025-12-31, so every cross_asset_residual
clock naming it joined to zero rows and sat at n=0 reading as a mechanism that never fires.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DESK), str(DESK / 'scripts')]
from mt5desk import family_inputs  # noqa: E402
from research import orthogonal_sweep  # noqa: E402


def bars(start: str, end: str) -> pd.DataFrame:
    idx = pd.date_range(start, end, freq='5min', tz='UTC')
    px = 100 + np.cumsum(np.random.default_rng(0).normal(0, .01, len(idx)))
    return pd.DataFrame({'open': px, 'high': px, 'low': px, 'close': px}, index=idx)


def test_a_factor_that_stopped_updating_is_named() -> None:
    own = bars('2026-11-01', '2026-11-10')
    dead = bars('2025-12-20', '2025-12-31')
    live = bars('2026-11-01', '2026-11-10')
    stale = family_inputs.stale_inputs([('UST10Y', dead), ('USDX', live)], own)
    assert list(stale) == ['UST10Y'] and '2025-12-31' in stale['UST10Y']


def test_a_holiday_run_shorter_than_the_window_is_not_stale() -> None:
    own = bars('2026-02-01', '2026-02-20')
    paused = bars('2026-02-01', '2026-02-14')
    assert family_inputs.stale_inputs([('CN50', paused)], own) == {}


def test_an_unreadable_index_is_not_evidence_of_staleness() -> None:
    own = bars('2026-11-01', '2026-11-10')
    assert family_inputs.stale_inputs([('X', object())], own) == {}
    assert family_inputs.stale_inputs([('X', own)], object()) == {}


def test_resolve_refuses_the_cell_and_names_the_factor(monkeypatch) -> None:
    own = bars('2026-11-01', '2026-11-10')
    frames = {'UST10Y': bars('2025-12-20', '2025-12-31'), 'USDX': bars('2026-11-01', '2026-11-10')}
    monkeypatch.setattr(orthogonal_sweep, '_bars', lambda sym, tf: frames.get(sym))
    extra, why = family_inputs.resolve(
        'XAUEUR', 'cross_asset_residual',
        {'timeframe': 'M5', 'factor_symbols': ['USDX', 'UST10Y']}, own)
    assert extra is None
    assert 'UST10Y' in why and 'USDX' not in why.split(';')[0].split('{')[1]


def test_live_factors_still_resolve(monkeypatch) -> None:
    own = bars('2026-11-01', '2026-11-10')
    frames = {'USDX': bars('2026-11-01', '2026-11-10')}
    monkeypatch.setattr(orthogonal_sweep, '_bars', lambda sym, tf: frames.get(sym))
    extra, why = family_inputs.resolve(
        'XAUEUR', 'cross_asset_residual', {'timeframe': 'M5', 'factor_symbols': ['USDX']}, own)
    assert why == 'ok' and extra is not None and len(extra['factors']) == 1
