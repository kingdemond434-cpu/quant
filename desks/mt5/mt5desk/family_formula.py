"""Trade a formulaic alpha: one expression from `libs.research.alpha_grammar`, z-scored, thresholded.

THE FAMILY IS THE EXECUTOR, NOT THE SEARCH. `alpha_evolution` invents expressions; this runs one
of them exactly as a certificate would need it run: the expression evaluated on the bars (and on
the driver frames named in it), normalised by its own trailing mean and standard deviation, and
turned into a signal when the z-score is extreme. Nothing here is fitted -- the expression, the
window, the threshold and the side mode are all on the recipe.

    follow   trade in the direction of the expression's sign when |z| >= entry_z
    fade     trade against it

REFUSES rather than approximates: an expression that names a driver terminal the caller did not
supply evaluates to NaN throughout and produces no signals; a recipe with no expression is not a
cell. Entry is the open of the next bar, stop and target in ATR units, exit at the earlier of
target, stop or `hold_bars`.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

SIDE_MODES = ("follow", "fade")


def family_formula(
    df: pd.DataFrame,
    *,
    expr: Any = None,
    norm: int = 240,
    entry_z: float = 1.5,
    side_mode: str = "follow",
    hold_bars: int = 8,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    drivers: dict[str, pd.DataFrame] | None = None,
    population: str | None = None,
) -> list[Signal]:
    # `population` IS PROVENANCE, NOT A PARAMETER (2026-09-30): the search-paradigm census stamps
    # which search population drew the tree (`"gp"`, ...) into params, where it names the cell.
    # The family did not accept it, so every such row -- 928 of 944 `formula` rows in the docket
    # committed 2026-09-29 -- raised TypeError in the judge's build and the forward clock alike
    # and was parked as NOT_RUN_BUILD_FAILED, a construction failure that was a signature. It is
    # accepted and ignored: two trees that differ only by the population that found them are the
    # same rule and trade the same signals.
    del population
    from libs.research.alpha_grammar import (
        DRIVER_TERMINALS,
        evaluate,
        from_str,
        is_valid,
        terminal_frames,
        terminals_in,
    )
    # AND THE SAME ROWS CARRY THE TREE RENDERED, NOT AS THE PREFIX LIST. `alpha_grammar.to_str`
    # writes "div(open, bars_since_min(high, 5))" and `is_valid` reads a string as a bare TERMINAL
    # name, so all 928 failed the screen and returned [] -- which, once the signature above stopped
    # raising, would have moved them from a named build failure to an UNKNOWN "never fires". A
    # rendered call is parsed back with the grammar's own inverse; a bare terminal ("close") has
    # no parenthesis and is left as the grammar already reads it; an unparseable string stays
    # invalid and returns nothing, exactly as before.
    if isinstance(expr, str) and "(" in expr:
        try:
            expr = from_str(expr)
        except ValueError:
            return []
    if expr is None or side_mode not in SIDE_MODES or not is_valid(expr):
        return []
    d = _h1(df)
    if len(d) < max(2 * int(norm), 300):
        return []
    frames = terminal_frames(d, raw=df, drivers=drivers, atr_n=atr_n)
    if any(t in DRIVER_TERMINALS and t not in frames for t in terminals_in(expr)):
        return []
    v = evaluate(expr, frames)
    r = v.rolling(int(norm), min_periods=int(norm))
    z = ((v - r.mean()) / r.std()).to_numpy(dtype=float)
    if np.isfinite(z).sum() < 0.05 * z.size:
        return []
    atr = _atr(d, atr_n).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    idx = d.index
    flip = 1 if side_mode == "follow" else -1
    signals: list[Signal] = []
    last = -10 ** 9
    for i in range(int(norm), len(idx) - 1):
        if i - last < int(hold_bars):
            continue
        zi = z[i]
        a = atr[i]
        if not np.isfinite(zi) or abs(zi) < float(entry_z) or not np.isfinite(a) or a <= 0:
            continue
        side = int(np.sign(zi)) * flip
        if side == 0:
            continue
        px = close[i]
        signals.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                              tag=f"formula:{side_mode}", trigger=None, wait_bars=1))
        last = i
    return signals
