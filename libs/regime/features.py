"""Regime feature construction -- the observation vector the regime models see.

Returns + realised volatility + trend, standardised. Deliberately small and economically meaningful
(not a kitchen sink) so the latent states map onto interpretable market regimes.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def raw_regime_features(close: pd.Series, *, vol_window: int = 20) -> np.ndarray:
    """The (T, 3) UNSTANDARDISED observation matrix: [return, realised vol, price vs its MA].

    Every column is causal -- each row uses only bars up to and including its own. Exposed
    separately so a walk-forward consumer can standardise a block with its TRAINING window's
    mean and sd rather than with statistics that have seen the days being labelled. Standardising
    is the only step in `regime_features` that looks at the whole sample, and a second
    implementation of these three columns is exactly the drift this desk keeps paying for.
    """
    ret = close.pct_change().fillna(0.0)
    rv = ret.rolling(vol_window).std().bfill().fillna(0.0)
    trend = (close / close.rolling(vol_window).mean() - 1.0).fillna(0.0)
    return np.column_stack([ret.to_numpy(), rv.to_numpy(), trend.to_numpy()])


def standardise(raw: np.ndarray, mu: np.ndarray | None = None,
                sd: np.ndarray | None = None) -> np.ndarray:
    """Standardise an observation matrix, optionally with statistics measured elsewhere."""
    mu = raw.mean(axis=0) if mu is None else mu
    sd = (raw.std(axis=0) + 1e-9) if sd is None else sd
    return cast("np.ndarray", (raw - mu) / sd)


def regime_features(close: pd.Series, *, vol_window: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """Build the (T, 3) standardised feature matrix and return the RAW daily returns alongside it.

    Columns: [daily return, rolling realised vol, trend (price vs its MA)]. The raw returns are
    returned too so the engine can characterise each latent state in real units."""
    raw = raw_regime_features(close, vol_window=vol_window)
    ret = close.pct_change().fillna(0.0)
    return standardise(raw), ret.to_numpy()
