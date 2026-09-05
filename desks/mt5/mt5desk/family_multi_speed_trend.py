"""Time-series momentum at several speeds, vol-scaled, with a crisis-alpha variant.

WHAT IS BEING STOLEN, AND FROM WHOM. AQR's published time-series momentum (Moskowitz, Ooi and
Pedersen) and Man AHL's published multi-speed trend: the sign of the trailing return over several
lookbacks, each position scaled to a constant volatility target, aggregated across speeds. Man's
public material adds that the fastest speeds carry the crisis alpha -- trend earns most of its
convexity in equity drawdowns, and mostly through the speeds that turn inside a month. Both
publish that naive timing of the factor deteriorates after proper lags and costs, which is why
this family does not try to time itself.

WHY THIS IS NOT ANOTHER BREAKOUT. `session_range_breakout` fires when price leaves a session's
range; it is a level claim on an hourly clock. This fires on the SIGN OF THE TRAILING RETURN over
weeks to months, holds through sessions, and sizes inversely to realised vol. Its failure regime
-- a sharp reversal after a long run -- is the mirror of a breakout's, and the two are the
textbook pairing of an uncorrelated book.

THE SPEEDS ARE AN ENSEMBLE, NOT A CHOICE. Picking the lookback that backtested best is the
error AQR documents; every speed listed votes, and the position is the vol-scaled mean of the
votes. `crisis_only` restricts entries to bars where the fastest speed disagrees with the
slowest -- the turning point -- which is Man's crisis-alpha claim stated as a filter.

DAILY DECISION, HOURLY ENTRY. The trend is measured on daily closes derived from the bars, the
position is taken on the first bar of the next day, and it is held `hold_days`. A trend family
re-evaluated every hour is a noise family.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1, bars_per_day

DEFAULT_SPEEDS = (10, 21, 63, 126, 252)


def family_multi_speed_trend(
    df: pd.DataFrame,
    *,
    speeds: tuple[int, ...] | list[int] = DEFAULT_SPEEDS,
    vol_window: int = 21,
    hold_days: int = 5,
    min_agreement: float = 0.6,
    crisis_only: bool = False,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    rr: float = 2.0,
) -> list[Signal]:
    """Vol-scaled vote across speeds; enter when at least `min_agreement` of them agree."""
    speeds = tuple(int(s) for s in speeds if int(s) > 1)
    if not speeds or not (0.0 < min_agreement <= 1.0):
        return []
    d = _h1(df)
    # `speeds` and `hold_days` are DAYS already (the votes are computed on a daily series), so
    # this guard is days-of-history and must be counted in the chart's own bars per day.
    if len(d) < bars_per_day(d) * (max(speeds) + 60):
        return []
    close = d["close"].astype(float)
    daily = close.groupby(close.index.date).last()
    if daily.size < max(speeds) + 60:
        return []
    logp = np.log(daily.to_numpy(dtype=float))
    ret = np.diff(logp, prepend=np.nan)
    vol = pd.Series(ret).rolling(vol_window).std(ddof=1).to_numpy()

    votes = np.zeros((daily.size, len(speeds)))
    for k, s in enumerate(speeds):
        tr = np.full(daily.size, np.nan)
        tr[s:] = logp[s:] - logp[:-s]
        # Vol-scaled sign: the vote is +-1, and its confidence is the trend in vol units so a
        # drift inside the noise does not count as agreement.
        z = tr / np.maximum(vol * np.sqrt(s), 1e-12)
        votes[:, k] = np.where(np.abs(z) >= 0.5, np.sign(z), 0.0)
    agree = votes.mean(axis=1)
    fastest, slowest = votes[:, 0], votes[:, -1]

    first_bar_of_day: dict[object, pd.Timestamp] = {}
    for ts in d.index:
        first_bar_of_day.setdefault(ts.date(), ts)
    last_bar_of_day: dict[object, pd.Timestamp] = {}
    for ts in d.index:
        last_bar_of_day[ts.date()] = ts
    atr = _atr(d, atr_n)
    days = list(daily.index)
    signals: list[Signal] = []
    last_entry_day = -10 ** 9
    for i in range(max(speeds), daily.size - 1):
        a = float(agree[i])
        if abs(a) < min_agreement:
            continue
        if crisis_only and not (fastest[i] != 0 and slowest[i] != 0 and fastest[i] != slowest[i]):
            continue
        if i - last_entry_day < hold_days:
            continue
        side = 1 if a > 0 else -1
        if crisis_only:
            side = int(fastest[i])           # the turn is the claim; follow the fast speed
        # Enter on the first bar strictly after this day's last bar.
        ts_last = last_bar_of_day.get(days[i])
        if ts_last is None:
            continue
        later = d.index[d.index > ts_last]
        if later.empty:
            continue
        entry = later[0]
        at = float(atr.reindex([entry]).iloc[0])
        if not np.isfinite(at) or at <= 0:
            continue
        px = float(close.reindex([entry]).iloc[0])
        signals.append(Signal(time=entry, side=side, stop=px - side * stop_atr * at,
                              target=px + side * stop_atr * at * rr,
                              ttl_bars=int(hold_days) * bars_per_day(d),
                              tag=f"multi_speed_trend:{'crisis' if crisis_only else 'all'}",
                              trigger=None, wait_bars=1))
        last_entry_day = i
    return signals
