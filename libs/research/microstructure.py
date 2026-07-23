"""Order-book microstructure features (method from nkaz001/algotrading-example).

Depth (queue) imbalance ``= (bid_size - ask_size) / (bid_size + ask_size)`` in ``[-1, 1]``: ``>0``
means more resting size on the bid than the ask (buy pressure). It is the order-flow cousin of the
taker-buy fraction the existing ``taker_flow`` sleeve already trades, provided here as an owned,
lagged, smoothed panel that ``crypto_sleeves._book`` can consume with no look-ahead.

NO repo contains alpha. This is a *feature*, not an edge: if it is ever screened into a sleeve it
counts as a trial in the DSR/trials ledger like any other. Ships as a construction primitive only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def book_imbalance(bid_size: np.ndarray, ask_size: np.ndarray) -> np.ndarray:
    """Depth imbalance in ``[-1, 1]``; ``0`` wherever total resting size is ``0`` (no book)."""
    b = np.asarray(bid_size, dtype="float64")
    a = np.asarray(ask_size, dtype="float64")
    total = b + a
    result: np.ndarray = np.divide(b - a, total, out=np.zeros_like(total), where=total > 0.0)
    return result


def depth_imbalance_signal(
    bid_size: pd.DataFrame, ask_size: pd.DataFrame, *, lookback: int
) -> pd.DataFrame:
    """Lagged-ready, smoothed cross-sectional depth-imbalance panel (a signal, not a fill model).

    Mirrors the sleeve convention: a rolling mean over ``lookback`` bars; callers still ``shift(1)``
    before trading it (as ``_book`` does). Cells with no resting book become ``NaN`` and are dropped
    by the sleeve's ``min_names`` gate rather than silently treated as neutral.
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    total = bid_size + ask_size
    imb = (bid_size - ask_size).where(total > 0.0) / total.where(total > 0.0)
    return imb.rolling(lookback).mean()
