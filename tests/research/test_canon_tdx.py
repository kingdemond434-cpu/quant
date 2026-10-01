"""The Tongdaxin indicator canon (QUANTAXIS `QAIndicator`): constructible, evaluable, seeded."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research import alpha_grammar as ag

N = 3000


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.Series]:
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, N)))
    idx = pd.date_range("2024-01-01", periods=N, freq="1h", tz="UTC")
    o = np.concatenate([[100.0], close[:-1]]) * (1 + rng.normal(0, 2e-4, N))
    df = pd.DataFrame({"open": o, "high": np.maximum(o, close) * (1 + rng.uniform(0, 2e-3, N)),
                       "low": np.minimum(o, close) * (1 - rng.uniform(0, 2e-3, N)),
                       "close": close, "tick_volume": rng.integers(50, 500, N).astype(float),
                       "spread": 5.0}, index=idx)
    return ag.terminal_frames(df, raw=df)


def test_the_tdx_canon_is_in_the_canon_and_disjoint_from_the_alphas() -> None:
    assert len(ag.CANON_TDX) == 12
    assert set(ag.CANON_TDX) <= set(ag.CANON)
    assert not set(ag.CANON_TDX) & set(ag.CANON_ALPHA101_IDS)
    assert all(n.startswith("tdx_") for n in ag.CANON_TDX)


@pytest.mark.parametrize("name", sorted(ag.CANON_TDX))
def test_each_is_constructible_and_evaluable(name: str, frames) -> None:
    e = ag.CANON[name]
    assert ag.is_valid(e, allow_drivers=False), (name, ag.type_of(e), ag.unit_of(e))
    v = ag.evaluate(e, frames, {}).to_numpy(dtype=float)
    assert np.isfinite(v).sum() > N // 2
    assert float(np.nanstd(v)) > 0.0


def test_kdj_reads_where_the_close_sits_in_its_range(frames) -> None:
    k = ag.evaluate(ag.CANON["tdx_kdj_k_8"], frames, {})
    assert float(k.min()) >= 0.0 and float(k.max()) <= 1.0
    psy = ag.evaluate(ag.CANON["tdx_psy_12"], frames, {})
    assert float(psy.min()) >= -1.0 and float(psy.max()) <= 1.0
