"""Trade the regime CHANGE itself, using the hazard rather than a proxy for it.

WHY THIS IS NOT `vol_transition`. That family fires when fast realised vol crosses above slow --
a good, cheap proxy for "something is changing". This one fires on P(the regime ENDS within h),
conditioned on how long the regime has already run. Those are different claims: a vol ratio can
cross inside a stable regime and stay there, and a mature trend can be one bar from exhaustion
with its vol ratio perfectly quiet. The hazard is the quantity the mechanism is actually about,
and `libs.regime.transitions` already computes it for the allocator.

THE TWO CLAIMS, both economically real and both TESTED so neither is chosen after the fact:

    exhaustion   a regime about to end has run its move; fade the direction it produced
    expansion    a regime about to end is about to reprice; follow the impulse that breaks it

WALK-FORWARD OR IT IS WORTHLESS. A regime model fitted on the whole sample and then used to label
history is the same lookahead that made `cross_asset_residual` fail 348 times. The engine is
refitted every `refit_days` on the TRAILING `window` only, and each day is labelled by the most
recent fit that could not have seen it. The filter posterior is causal by construction; the
PARAMETERS are what leak, so the parameters are what get walked forward.

DAILY STATE, HOURLY ENTRY, and that is the structure rather than a compromise. The macro regime
is a daily object -- fitting an HMM to hourly bars mostly finds the session, which this desk
already models explicitly in `session_phase`. So the daily hazard decides WHETHER, and the first
bar of the day decides WHEN. It is also what makes the family affordable: a daily fit on a 750-day
window costs ~7s, so a 2,000-day history is eight fits rather than two thousand.

REFUSES rather than degrading. Too little history, an engine that will not converge, a series with
no variance -- all return no signals. A regime family that silently falls back to price behaviour
is a momentum family with a grander name.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1, bars_per_day

#: Trailing days each fit sees. Long enough for the hazard to have runs to count, short enough
#: that the vocabulary describes the recent market and that eight fits cover a full history.
DEFAULT_WINDOW = 750
#: Days between refits. The parameters, not the filter, are what would leak.
DEFAULT_REFIT = 250


def _daily_close(d: pd.DataFrame) -> pd.Series:
    c = d["close"].astype(float)
    return c.groupby(c.index.date).last()


def _hazard_path(daily: pd.Series, window: int, refit: int, horizon: int,
                 ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Per-day P(leave within `horizon`), regime age and the regime's own trailing move.

    THREE THINGS MAKE THIS CAUSAL, and each was got wrong once before it was got right.

    1. THE FEATURES, NOT THE PRICES. `GaussianHMM` here is fitted on the standardised
       [return, realised vol, trend] matrix `regime_features` builds, so filtering it on log
       prices -- as the first version of this did -- feeds it a series it has never seen. It does
       not raise. It returns a single-state path, an age equal to the whole window, and a hazard
       pinned at the memoryless rate: a plausible-looking answer to a question nobody asked.

    2. THE STANDARDISATION IS THE TRAINING WINDOW'S. Column means and sds are the only part of
       feature construction that looks across rows, so they are measured on the training window
       and applied to the block being labelled.

    3. THE DECODE IS THE FILTER, NOT VITERBI. Viterbi is a GLOBAL decode -- the state it assigns
       to day t depends on days after t, so a run length read off it is contaminated at exactly
       the point the hazard is about to be evaluated. The filtered argmax uses only data up to t.
    """
    from libs.regime.engine import RegimeEngine
    from libs.regime.features import raw_regime_features, standardise
    from libs.regime.transitions import forecast

    n = daily.size
    p_leave = pd.Series(np.nan, index=daily.index)
    age = pd.Series(np.nan, index=daily.index)
    move = pd.Series(np.nan, index=daily.index)
    if n < window + refit:
        return p_leave, age, move

    logp = np.log(daily.to_numpy(dtype=float))
    raw = raw_regime_features(daily)
    for start in range(window, n, refit):
        train_raw = raw[start - window:start]
        try:
            eng = RegimeEngine().fit(daily.iloc[start - window:start])
            lab = {j: str(ch["label"]) for j, ch in eng.hmm_char.items()}
        except Exception:                                            # noqa: BLE001
            continue
        stop = min(start + refit, n)
        mu, sd = train_raw.mean(axis=0), train_raw.std(axis=0) + 1e-9
        # ONE filter pass over [train | block]. The forward filter is causal, so row t of the
        # result depends only on rows up to t -- re-running it per day would cost O(n^2) to
        # compute the identical numbers.
        seen = standardise(raw[max(0, start - window):stop], mu, sd)
        try:
            post_all = eng.hmm.filter_posterior(seen)
        except Exception:                                            # noqa: BLE001
            continue
        decoded = post_all.argmax(axis=1)
        offset = stop - post_all.shape[0]
        for t in range(start, stop):
            i = t - offset
            try:
                fc = forecast(eng.hmm.transmat, post_all[i], lab, decoded[:i + 1],
                              horizons=(horizon,))
            except Exception:                                        # noqa: BLE001
                continue
            p_leave.iloc[t] = fc.p_leave.get(horizon, np.nan)
            age.iloc[t] = fc.age_bars
            look = min(int(fc.age_bars), t)
            move.iloc[t] = float(logp[t] - logp[t - look]) if look >= 1 else 0.0
    return p_leave, age, move


def family_regime_transition(
    df: pd.DataFrame,
    *,
    window: int = DEFAULT_WINDOW,
    refit_days: int = DEFAULT_REFIT,
    horizon_days: int = 1,
    entry_p_leave: float = 0.30,
    min_age: int = 5,
    side_mode: str = "exhaustion",
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Enter on the first bar of a day whose regime is likely to end.

    `min_age` refuses a regime the model has only just entered: a two-day-old state with a high
    hazard is usually the classifier still making up its mind, and trading that is trading the
    estimator rather than the market.
    """
    if side_mode not in {"exhaustion", "expansion"}:
        return []
    d = _h1(df)
    # `window` and `refit_days` are DAYS (the hazard is fitted on a daily close series), so the
    # history guard counts this chart's own bars per day. Identical on H1.
    if len(d) < bars_per_day(d) * (window + refit_days):
        return []
    daily = _daily_close(d)
    if daily.size < window + refit_days or float(daily.std()) <= 0:
        return []

    p_leave, age, move = _hazard_path(daily, window, refit_days, horizon_days)
    if not np.isfinite(p_leave.to_numpy(dtype=float)).any():
        return []

    atr = _atr(d, atr_n)
    # THE LAST BAR OF THE DAY, NOT THE FIRST. The hazard for day t is computed from day t's
    # CLOSE, so the first bar strictly after day t's first bar is still inside day t -- entering
    # there trades a number that will not exist for another twenty-three hours. Caught by
    # `test_entries_are_after_the_day_whose_hazard_triggered_them`, which is the only reason it
    # is not still in here: the signals looked entirely reasonable.
    by_day: dict[object, pd.Timestamp] = {}
    for ts in d.index:
        by_day[ts.date()] = ts

    signals: list[Signal] = []
    for day, pl in p_leave.items():
        if not np.isfinite(pl) or pl < entry_p_leave:
            continue
        a_days = age.get(day, np.nan)
        if not np.isfinite(a_days) or a_days < min_age:
            continue
        mv = move.get(day, np.nan)
        if not np.isfinite(mv) or mv == 0.0:
            continue
        ts = by_day.get(day)
        if ts is None:
            continue
        # ENTER ON THE NEXT DAY'S FIRST BAR. The hazard for day t is known at t's close, so
        # entering at t's open would be trading on a number that did not exist yet.
        later = d.index[d.index > ts]
        if later.empty:
            continue
        entry = later[0]
        a = float(atr.reindex([entry]).iloc[0]) if entry in atr.index else np.nan
        if not np.isfinite(a) or a <= 0:
            continue
        trend = 1 if mv > 0 else -1
        side = -trend if side_mode == "exhaustion" else trend
        px = float(d["close"].reindex([entry]).iloc[0])
        signals.append(Signal(time=entry, side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag=f"regime_transition:{side_mode}", trigger=None, wait_bars=1))
    return signals
