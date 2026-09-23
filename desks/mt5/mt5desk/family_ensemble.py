"""Many predictors that cannot cover their costs alone, combined into one that can.

Peter Brown's public statement of Medallion's architecture: a single weak signal -- his example
was cloud cover -- was not enough to overcome transaction costs, but many weak signals together
were. This desk had no way to express that. Every cell faces the gauntlet on its own, so a
predictor with E[R] below the round trip fails `expected_value` and is discarded, however much it
would have added to a combination. Six hundred such cells sat in the funnel census as failures.

WHAT THIS FAMILY IS. A weighted vote over MEMBER cells -- ordinary (symbol, family, params)
identities the desk can already build -- that emits a signal when the vote crosses a threshold.
The members' individual results are irrelevant; only the combination faces the gauntlet, as ONE
candidate with ONE certificate, and the members are its parameters.

NOT A SECOND DOOR. The ensemble is registered as a family, so it is compiled, rebuilt, judged,
clocked forward and allocated exactly as any other cell. Its members are named on the certificate
and `family_inputs.resolve` rebuilds them from their own params, which means a member's family
cannot be edited out from under an ensemble without the ensemble's identity changing.

WHAT THE WEIGHTS ARE NOT. They are inputs, chosen by `weak_signal_compiler` on a training block
and then FROZEN; this family does not fit anything. A family that re-estimated its weights on the
bars it was about to be judged on would be the leak this desk has removed three times today.

SIDE AND TIMING. Each member contributes +-1 at each of its signal bars (0 elsewhere), scaled by
its weight. At bars where the weighted sum crosses `threshold`, one signal is emitted with the
sum's sign. Stops and targets are ATR-based like every other family, so the ensemble's R has the
same meaning as its members'.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1, bars_per_day


def family_ensemble(
    df: pd.DataFrame,
    *,
    members: list[dict] | None = None,
    weights: list[float] | None = None,
    threshold: float = 0.5,
    hold_bars: int = 12,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    _runner: Callable[[str, str, dict, pd.DataFrame], list[Any]] | None = None,
) -> list[Signal]:
    """`members` are (symbol, family, params) dicts; `_runner` builds each member's signals.

    `_runner` is injected by `family_inputs.resolve` and the gauntlet, which know how to rebuild
    a member cell with its own inputs. Without it the family cannot run and returns nothing,
    which is the correct answer for an ensemble whose members cannot be resolved.
    """
    if not members or _runner is None:
        return []
    if weights is None:
        weights = [1.0] * len(members)
    if len(weights) != len(members) or not np.isfinite(weights).all():
        return []
    d = _h1(df)
    # 120 DAYS of history, on whatever chart this is (identical on H1, where it is 24 bars/day).
    if len(d) < bars_per_day(d) * 120:
        return []
    vote = pd.Series(0.0, index=d.index)
    n_ok = 0
    for m, w in zip(members, weights):
        try:
            sigs = _runner(str(m.get("symbol") or ""), str(m.get("family") or ""),
                           dict(m.get("params") or {}), df)
        except Exception:                                        # noqa: BLE001
            continue
        if not sigs:
            continue
        n_ok += 1
        for s in sigs:
            if s.time in vote.index:
                vote.loc[s.time] += float(w) * int(s.side)
    if n_ok == 0:
        return []
    total_w = float(np.sum(np.abs(weights))) or 1.0
    vote = vote / total_w
    atr = _atr(d, atr_n)
    close = d["close"].astype(float)
    signals: list[Signal] = []
    last = -10 ** 9
    idx = d.index
    v = vote.to_numpy()
    for i in range(len(idx) - 1):
        if abs(v[i]) < threshold or i - last < hold_bars:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = 1 if v[i] > 0 else -1
        px = float(close.iloc[i])
        signals.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                              tag="ensemble", trigger=None, wait_bars=1))
        last = i
    return signals
