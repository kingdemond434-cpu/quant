"""The lookahead sentinel: a family's signals up to bar t may not change when bars after t vanish.

Freqtrade ships a lookahead-analysis command and a recursive-indicator check; Vibe-Trading
bans lookahead at the operator layer. The desk's version is one function any family can be
run through: compute the signals on the full history and on the history truncated at a cut,
and every signal at or before the cut must be identical -- same time, same side, same stop,
same target. A family that fails is leaking the future through a rolling window that centres,
a resample that peeks, or a normalisation fitted on the whole sample.

`recursive_check` covers the second Freqtrade discipline: the signals must not depend on how
much history PRECEDES the window either, beyond a declared warm-up -- a family whose signals in
the last N bars change when the first 1000 bars are dropped is carrying state it should not.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd


def _sig_key(s: Any) -> tuple[Any, ...]:
    return (pd.Timestamp(s.time), int(s.side), round(float(s.stop), 8),
            round(float(s.target), 8), int(s.ttl_bars))


def truncation_test(fn: Callable[..., Sequence[Any]], df: pd.DataFrame, cut: int,
                    **kw: Any) -> dict[str, Any]:
    """Signals at or before `cut` computed on the full frame must equal those on df[:cut]."""
    full = fn(df, **kw)
    part = fn(df.iloc[:cut], **kw)
    edge = df.index[cut - 1]
    a = {_sig_key(s) for s in full if pd.Timestamp(s.time) <= edge}
    b = {_sig_key(s) for s in part}
    only_full = sorted(a - b)
    only_part = sorted(b - a)
    return {"ok": not only_full and not only_part, "n_full": len(a), "n_truncated": len(b),
            "only_with_future": [str(x[0]) for x in only_full[:5]],
            "only_without_future": [str(x[0]) for x in only_part[:5]],
            "verdict": "CAUSAL" if not only_full and not only_part else "LOOKAHEAD"}


def recursive_check(fn: Callable[..., Sequence[Any]], df: pd.DataFrame, drop: int,
                    warmup: int, **kw: Any) -> dict[str, Any]:
    """Dropping the first `drop` bars may change signals only inside the declared warm-up."""
    full = fn(df, **kw)
    short = fn(df.iloc[drop:], **kw)
    start = df.index[drop + warmup] if drop + warmup < len(df) else df.index[-1]
    a = {_sig_key(s) for s in full if pd.Timestamp(s.time) >= start}
    b = {_sig_key(s) for s in short if pd.Timestamp(s.time) >= start}
    diff = len(a ^ b)
    return {"ok": diff == 0, "n_compared": len(a | b), "n_different": diff,
            "verdict": "STATELESS_BEYOND_WARMUP" if diff == 0 else "HISTORY_DEPENDENT"}
