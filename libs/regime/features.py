"""Regime feature construction -- the observation vector the regime models see.

Returns + realised volatility + trend, standardised. Deliberately small and economically meaningful
(not a kitchen sink) so the latent states map onto interpretable market regimes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def regime_features(close: pd.Series, *, vol_window: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """Build the (T, 3) standardised feature matrix and return the RAW daily returns alongside it.

    Columns: [daily return, rolling realised vol, trend (price vs its MA)]. The raw returns are
    returned too so the engine can characterise each latent state in real units."""
    ret = close.pct_change().fillna(0.0)
    rv = ret.rolling(vol_window).std().bfill().fillna(0.0)
    trend = (close / close.rolling(vol_window).mean() - 1.0).fillna(0.0)
    raw = np.column_stack([ret.to_numpy(), rv.to_numpy(), trend.to_numpy()])
    mu = raw.mean(axis=0)
    sd = raw.std(axis=0) + 1e-9
    return (raw - mu) / sd, ret.to_numpy()
