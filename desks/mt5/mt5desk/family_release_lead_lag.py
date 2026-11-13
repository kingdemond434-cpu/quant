"""Trade the follower after the leader moved ON A SCHEDULED RELEASE: the leadership atlas's claim.

    at the first bar that opens at or after a release of `event_type`:
        z    = driver's log return over that bar / the driver's 1-bar sigma over the `norm`
               bars BEFORE the release
        side = sign(z) x direction                   when |z| >= entry_z
    entry at the close of bar e + lag - 1: the last bar before the follower's measured catch-up
    (the atlas's lag, in this chart's bars, from the leader's first move); one signal per
    release, held `hold_bars` (default 2 x lag + 1), stop `stop_atr` ATR.

THE LAG IS THE CLAIM, NOT ONLY THE HOLD (Auditor SF1 on #1146). Entering at bar e would test
"the follower moves within the hold window"; entering at e + lag - 1 tests what the atlas measured
-- the follower has NOT yet moved one bar before its measured lag, and moves after. lag = 1 is
entry at e itself.

WHY A FAMILY OF ITS OWN AND NOT `lead_lag` (Auditor HOLD on #1146, MF2). The atlas measures a
lead that exists only around one release type, in one causal regime, on a minute chart. Mapped
onto the unconditional `family_lead_lag` it became sixteen cells (every chart x every session)
testing a different claim -- "the driver's z-scored return leads the target on every bar" -- and
`lead_lag` is admissible only at H1 and above, where a seconds-to-minutes lead is invisible. This
family keeps all three conditions on the recipe, so the Judge tests what the atlas found.

THE RELEASES COME FROM `mt5desk.release_calendar`, the same reader and the same classifier the
atlas uses, converted to the bar clock by `libs.research.bar_clock.to_bar_time` (the bars carry
broker time under a UTC tzinfo; an unconvertible instant is DROPPED, never used raw). Entry is on
the first bar that OPENS at or after the release, signalled at its close: nothing inside the bar
that contains the release is read before it is complete.

THE REGIME IS CAUSAL AND IS THE ATLAS'S DEFINITION: the driver's pre-release sigma against the
median of its pre-release sigmas on the previous releases of THIS type (at least `MIN_PRIOR`);
above is `stressed`, at or below `calm`. With too few prior releases the regime is unknown and a
regime-conditioned cell does not fire on that release.

REFUSES (returns []) without driver bars, with a driver that is the target, an unknown direction
or regime, or no event type. The forward engine hands the driver over (`family_inputs.resolve`,
where a named driver with no bars is a failed build); the sealed judge passes only the NAME, so
the family reads the driver itself through `family_inputs.bars_named`, exactly as `lead_lag`
does -- the sealed evaluator is never edited for a new family.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

DIRECTIONS = ("same", "opposite")
REGIMES = ("all", "calm", "stressed")
MIN_PRIOR = 10


def _bar_instants(times: Sequence[Any]) -> list[pd.Timestamp]:
    from libs.research.bar_clock import to_bar_time
    out: list[pd.Timestamp] = []
    for t in times:
        ts = pd.Timestamp(t)
        if ts.tzinfo is None:
            continue
        moved, _status, _why = to_bar_time(ts.tz_convert("UTC").to_pydatetime(), fallback=True)
        if moved is not None:
            out.append(pd.Timestamp(moved))
    return sorted(set(out))


def family_release_lead_lag(
    df: pd.DataFrame,
    *,
    driver: pd.DataFrame | None = None,
    driver_symbol: str = "",
    event_type: str = "",
    regime: str = "all",
    lag: int = 1,
    direction: str = "same",
    entry_z: float = 2.0,
    norm: int = 60,
    hold_bars: int = 0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 3.0,
    events: Sequence[Any] | None = None,
    bar_events: Sequence[Any] | None = None,
    calendar_root: str | Path | None = None,
) -> list[Signal]:
    if driver is None and driver_symbol:
        from mt5desk.family_inputs import bars_named
        driver = bars_named(driver_symbol, df)
    if (driver is None or direction not in DIRECTIONS or regime not in REGIMES
            or not event_type or "close" not in driver.columns):
        return []
    d = _h1(df)
    if len(d) < norm + atr_n + 2:
        return []
    dc = driver["close"].astype(float).copy()
    dc.index = pd.DatetimeIndex(pd.to_datetime(dc.index, utc=True, errors="coerce"))
    dc = dc[~dc.index.duplicated(keep="last")].sort_index()
    if dc.index.equals(d.index) and np.allclose(dc.to_numpy(), d["close"].to_numpy()):
        return []                                            # the driver is the target
    if bar_events is not None:                              # already on the bar clock (tests)
        instants = sorted({pd.Timestamp(t) for t in bar_events})
    else:
        if events is None:
            from mt5desk.release_calendar import release_instants
            root = Path(calendar_root) if calendar_root else None
            events = release_instants(event_type, root)
        instants = _bar_instants(events)
    if not instants:
        return []
    x = np.log(dc.reindex(d.index).ffill()).diff().to_numpy(dtype=float)
    atr = _atr(d, atr_n).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    idx = d.index
    flip = 1 if direction == "same" else -1
    hold = int(hold_bars) if int(hold_bars) > 0 else 2 * int(lag) + 1
    prior: list[float] = []
    out: list[Signal] = []
    last = -10 ** 9
    for te in instants:
        e = int(idx.searchsorted(te))                        # first bar opening at/after release
        if e < norm + 1 or e >= len(idx) - 1:
            continue
        pre = x[e - norm:e]
        pre = pre[np.isfinite(pre)]
        if len(pre) < norm // 2:
            continue
        sigma = float(pre.std(ddof=0))
        if not np.isfinite(sigma) or sigma <= 0:
            continue
        reg = ("unknown" if len(prior) < MIN_PRIOR else
               "stressed" if sigma > float(np.median(prior)) else "calm")
        prior.append(sigma)
        if regime != "all" and reg != regime:
            continue
        if e - last < hold:
            continue
        xe, a = x[e], atr[e]
        if not np.isfinite(xe) or not np.isfinite(a) or a <= 0:
            continue
        z = xe / sigma
        if abs(z) < float(entry_z):
            continue
        side = int(np.sign(z)) * flip
        k = e + max(0, int(lag) - 1)                      # one bar before the measured catch-up
        if k >= len(idx) - 1:
            continue
        a = atr[k]
        if not np.isfinite(a) or a <= 0:
            continue
        px = close[k]
        out.append(Signal(time=idx[k], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=hold,
                          tag=f"release_lead_lag:{event_type}:{driver_symbol or 'driver'}:"
                              f"{direction}:{regime}",
                          trigger=None, wait_bars=1))
        last = k
    return out
