"""Trade an instrument while one of its own economy's official statistics sits in a z-score band.

    z_t    = z( world series over its last `z_obs` OBSERVATIONS )   on the series' own clock
    signal = direction                                              when z_lo <= z_t < z_hi

MECHANISM. A point-in-time official statistic of the instrument's own economy or commodity
balance -- a policy rate, CPI, money supply, trade balance, industrial output, reserves, a
commodity stock -- moves the discount rate, the real flows and the relative demand that price
the instrument. When that statistic is unusually high or low against its own recent history, the
flows it describes (carry demand, hedging, trade settlement, reserve management) lean one way
for weeks, and the instrument drifts with them. The claim is falsifiable per cell: it fails when
the statistic's extremes carry no forward return net of cost.

THE SERIES IS NAMED ON THE RECIPE (`series_key`) and loaded HERE, by that key, from the world
dataset hunter's store (`research.world_dataset_hunter.raw_world_series`): the first vintage the
desk saw of each value, keyed on the instant it became knowable. No input resolver has to supply
it, so every caller that invokes the family -- the sweep, the sealed gauntlet's `build_cell`, the
forward clock's `family_call.signals` -- rebuilds the same signals from the same identity, and a
series that rotates out of the hunter's exposure can never orphan a cell.

THE Z IS TAKEN ON THE SERIES' OWN OBSERVATIONS, NOT ON THE BAR CLOCK: a monthly print forward-
filled onto hourly bars is constant for ~500 bars, and a bar-clock z of a constant is undefined.
The z is computed where the value changes, then carried causally onto the bars.

REFUSES (returns []) with too little history, an unnamed series or an unknown direction.

AN ABSENT SERIES IS A NAMED REFUSAL, NOT A CELL THAT NEVER FIRES (2026-11-10). A `series_key`
this host's store cannot resolve -- no `keys.json`, the key not in it, or its parquet gone --
raises `WorldSeriesUnavailable`. Returning [] there made the judge file the cell as UNKNOWN /
never_fires, a statement about the market, when the truth is a statement about the host: the
input is not here. Measured on the box 2026-11-10: 1,074 world_macro_state cells mined, 0 judged,
and all 84 null-lab draws built with zero trades. The sealed builder turns the raise into
`_build_failed("world_macro_state raised WorldSeriesUnavailable: ...")`, and
`research/build_input_probe` parks the cell by the missing input's name (`world_series:<key>`)
and re-admits it the pass the series is present (L1.28a: UNMEASURED is a real answer).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

DIRECTIONS = {"long": 1, "short": -1}


class WorldSeriesUnavailable(LookupError, TypeError):
    """The recipe names a world series this host's store does not hold.

    ALSO A TypeError, ON PURPOSE. The sealed builder (`external_gauntlet.build_cell`) calls a
    family as `fn(h1, side=side, **params)` and catches ONLY TypeError there, retrying without
    `side` under a catch-all that names the failure. Any other exception from the first call
    escapes `build_cell` into the sweep. Being a TypeError routes this refusal through the
    builder's own named door (`_build_failed("world_macro_state raised WorldSeriesUnavailable:
    ...")`) without touching the immutable evaluator.
    """


def _series(series_key: str):
    try:
        from research.world_dataset_hunter import _align, raw_world_series
    except ImportError:                                        # desk-root callers
        from world_dataset_hunter import _align, raw_world_series  # type: ignore[no-redef]
    return raw_world_series(series_key), _align


def world_state_z(series: pd.Series, z_obs: int) -> pd.Series:
    """Trailing z on the series' own observations (each point against its own past only)."""
    s = series.astype(float).dropna()
    r = s.rolling(int(z_obs), min_periods=int(z_obs))
    return ((s - r.mean()) / r.std(ddof=1)).replace([np.inf, -np.inf], np.nan).dropna()


def family_world_macro_state(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    # REQUIRED, WITH NO DEFAULT (2026-11-10). It defaulted to "", and a docket row minted from
    # the family's "defaults" (params {} -- 1,059 such rows, 0 judged, 168 parked never_fires,
    # measured on the box) built a cell with no series and no signals: a recipe that names no
    # statistic read as a market that never moved. With no default, the signature itself says
    # the recipe is incomplete: `gauntlet_buildability.cell_verdict` answers MISSING_PARAMS for
    # such a cell, and the sealed builder names the TypeError instead of filing zero trades.
    series_key: str,
    z_obs: int = 24,
    z_lo: float = 1.0,
    z_hi: float = 99.0,
    direction: str = "long",
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    # THE RECIPE'S `direction` IS THE SIDE. `side` is accepted and deliberately unused: the
    # sealed gauntlet always passes side=1 and the forward clock passes side=-1 for a short cell,
    # so honouring it would make the two callers build different trades from one identity.
    del side
    flip = DIRECTIONS.get(str(direction))
    if not series_key:
        raise WorldSeriesUnavailable(
            "the recipe names no series_key: world_macro_state has no default statistic, so "
            "the cell is incomplete and unjudged")
    if flip is None or float(z_hi) <= float(z_lo):
        return []
    raw, align = _series(str(series_key))
    if raw is None:
        raise WorldSeriesUnavailable(
            f"world series {series_key} is absent from the world dataset store on this host "
            "(keys.json, the key or its parquet); the input is missing, the cell is unjudged")
    if len(raw) < int(z_obs) + 2:
        return []
    z = world_state_z(raw, int(z_obs))
    if z.empty:
        return []
    d = _h1(df)
    if len(d) < 300:
        return []
    zb = align(z, d.index).to_numpy(dtype=float)
    atr = _atr(d, atr_n).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    idx = d.index
    out: list[Signal] = []
    last = -10 ** 9
    for i in range(int(atr_n), len(idx) - 1):
        if i - last < int(hold_bars):
            continue
        zi, a = zb[i], atr[i]
        if not np.isfinite(zi) or not (float(z_lo) <= zi < float(z_hi)):
            continue
        if not np.isfinite(a) or a <= 0:
            continue
        px = close[i]
        out.append(Signal(time=idx[i], side=flip, stop=px - flip * stop_atr * a,
                          target=px + flip * stop_atr * a * rr, ttl_bars=int(hold_bars),
                          tag=f"world_macro_state:{series_key}:{direction}",
                          trigger=None, wait_bars=1))
        last = i
    return out
