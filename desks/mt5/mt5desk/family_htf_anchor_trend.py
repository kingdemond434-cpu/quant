"""A higher-timeframe trend ANCHOR gating a lower-timeframe entry, with two conditional exits.

WHAT IS BEING STOLEN, AND FROM WHOM. A public video walkthrough (2026-09-23) in which an agent
built a trend follower and searched about 200 variations of it. The desk mines and tests
everything it can see; a video is a source like any other and the claim arrives here with no
privilege whatsoever (LAWS: a public claim is a hypothesis, never evidence).

THE HONEST PRIOR, recorded so the video's number is never re-quoted as a result. It reported a
Sharpe of 1.87. That was the MAXIMUM over ~200 searched variations, with NO multiplicity charge
applied, on ONE single-name equity (Apple). The author's own Monte Carlo put the MEDIAN of the
search near 1.30. A maximum over 200 trials is not an estimate of anything; this desk's deflated
Sharpe charges n_trials=597 with sr0=0.3786 and would price 1.87-at-200-trials well down. 1.30 is
the closer reading of the video's own evidence and even that is in-sample, on one name, in one
asset class this desk does not hunt for statistical hypotheses at all. Apple is therefore OUT OF
SCOPE for this family by the two-lane law; the mechanism is tested on the hypothesis lane -- FX
majors, crosses and exotics, metals, energy, softs, indices, bonds and Fusion's crypto CFDs.

THE FOUR PARTS, and which of them was actually new.

  1. ANCHOR GATE. A higher-timeframe direction is computed and the lower-timeframe entry only
     fires when it agrees. Both sides traded.
  2. ATR STOP set at entry.
  3. EXIT ON ANCHOR FLIP -- flat the moment the anchor turns against the position.
  4. EXIT ON VOLATILITY EXPANSION -- flat when current ATR exceeds `expansion_mult` x the ATR
     observed AT ENTRY. The video's author said he had never seen this rule before, and neither
     had this desk: of 65 registered families, `volatility_squeeze`, `vol_transition` and
     `vol_mean_reversion` all condition an ENTRY on volatility and not one conditions an EXIT on
     volatility relative to its own value at the moment the trade was opened.

WHY THIS IS NOT `multi_speed_trend`, which is the nearest neighbour and was checked first.
`multi_speed_trend` derives a DAILY series from the bars it is handed and TIMES one entry per
`hold_days` on the first bar after a day's close. The higher timeframe there is the DECISION
CLOCK: there is no lower-timeframe trigger at all, the fine bar only supplies the fill. Here the
fine chart carries its OWN entry condition, which can fire many times inside one anchor bar or
not at all, and the anchor is a PERMISSION rather than a trigger -- a different mechanism with a
different failure mode (it is wrong when the fine trigger is noise inside a true trend; the other
is wrong when the daily sign is late). `multi_speed_trend` also has no anchor-flip exit and no
volatility exit; its exits are stop, target and a fixed daily hold. It does not subsume this.

THE RATIO IS THE CLAIM, NOT THE HOUR. `anchor_mult` is the SPEED RATIO between gate and trigger
in bars of whatever chart the cell names, so the video's 4H-over-1H is the single point
(timeframe=H1, anchor_mult=4) and the same mechanism is expressible on the whole ladder. A
hard-coded "4H" would mean a different thing on every chart while wearing one name.

NO CONSTANT IS BORROWED. `expansion_mult` is swept over `EXIT_OPERATORS.EXPANSION_MULT_GRID` and
so is `anchor_mult`; the video's 4.0 and 4 sit inside those grids with no standing of their own. A
constant lifted from one person's search over one equity is a borrowed overfit, and adopting it
would import their selection without importing their trials.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.exit_operators import EXPANSION_MULT_GRID, anchor_direction, apply_exit_operators
from mt5desk.families import Signal, _atr, _ema, _h1, register_family

#: The video searched ~200 variations. This grid is 5 x 3 x 2 x 3 x 3 = 270 points per instrument
#: per chart BEFORE the operator's on/off arm, which is the same order of magnitude searched with
#: the multiplicity charge actually paid rather than discarded.
HTF_ANCHOR_GRID: dict[str, list] = {
    "expansion_mult": [0.0, *EXPANSION_MULT_GRID],
    "anchor_mult": [3, 4, 6],
    "exit_on_anchor_flip": [True, False],
    "entry_fast": [8, 12, 20],
    "stop_atr": [1.5, 2.0, 3.0],
}


@register_family(
    param_grid=HTF_ANCHOR_GRID,
    tags=["trend", "multi_timeframe", "conditional_exit", "public_claim"],
)
def family_htf_anchor_trend(
    df: pd.DataFrame,
    *,
    anchor_mult: int = 4,
    anchor_n: int = 50,
    entry_fast: int = 12,
    entry_slow: int = 36,
    atr_n: int = 14,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    max_hold_bars: int = 120,
    expansion_mult: float = 4.0,
    exit_on_anchor_flip: bool = True,
) -> list[Signal]:
    """Fine-chart EMA cross, permitted only when the anchor agrees; exits on flip or vol blow-out.

    `expansion_mult=0.0` and `exit_on_anchor_flip=False` give the SAME entries with the plain
    stop/target/time exit, which is the control arm. The operator's contribution is the difference
    between two cells that faced the same bar, not an assertion in a docstring.
    """
    anchor_mult = max(2, int(anchor_mult))
    entry_fast = max(2, int(entry_fast))
    entry_slow = max(entry_fast + 1, int(entry_slow))
    if stop_atr <= 0 or rr <= 0 or max_hold_bars < 1:
        return []
    d = _h1(df)
    need = max(anchor_mult * (int(anchor_n) + 2), entry_slow * 3, int(atr_n) * 3) + 10
    if len(d) < need:
        return []

    close = d["close"].astype(float)
    anchor = anchor_direction(d, anchor_mult=anchor_mult, anchor_n=int(anchor_n))
    fast = _ema(close, entry_fast)
    slow = _ema(close, entry_slow)
    # STRICTLY TRAILING TRIGGER: the cross is read from bars that have CLOSED, and the signal is
    # stamped on the bar that closed it. `Signal` fills on the following open (wait_bars=1), the
    # desk's standard convention, so nothing here sees its own fill bar.
    diff = (fast - slow).to_numpy(dtype=float)
    anch = anchor.to_numpy(dtype=float)
    atr = _atr(d, max(2, int(atr_n))).to_numpy(dtype=float)
    px = close.to_numpy(dtype=float)
    idx = d.index

    signals: list[Signal] = []
    last_exit = -1
    for i in range(1, len(d) - 1):
        prev, cur = diff[i - 1], diff[i]
        if not (np.isfinite(prev) and np.isfinite(cur)):
            continue
        if prev <= 0.0 < cur:
            side = 1
        elif prev >= 0.0 > cur:
            side = -1
        else:
            continue
        # THE ANCHOR IS A PERMISSION, NOT A TRIGGER -- this is the whole of part 1.
        if anch[i] * side <= 0.0:
            continue
        # ONE POSITION AT A TIME, RESERVED AGAINST THE UN-OPERATED HOLD, and that is a choice
        # worth naming. The operators run after this loop, so an operated arm that goes flat
        # early does NOT re-enter in the window its own exit freed -- it trades the same entries
        # as the control arm and no more. That biases AGAINST the operator (it gives up the
        # re-entries its rule created) and it is the bias to have: it makes the two arms share
        # an entry set exactly, so the gauntlet's difference between them is the exits alone
        # rather than exits plus a different trade count. Under-crediting an exit rule is the
        # safe direction for a judge; `test_htf_anchor_trend_control_arm_and_operated_arm_share
        # _their_entries` pins the property this buys.
        if i <= last_exit:
            continue
        a = float(atr[i])
        if not np.isfinite(a) or a <= 0:
            continue
        entry = float(px[i])
        signals.append(Signal(
            time=idx[i], side=side,
            stop=entry - side * stop_atr * a,
            target=entry + side * stop_atr * a * rr,
            ttl_bars=int(max_hold_bars),
            tag=f"htf_anchor_trend:x{anchor_mult}",
            trigger=None, wait_bars=1,
        ))
        last_exit = i + int(max_hold_bars)

    return apply_exit_operators(
        d, signals,
        expansion_mult=float(expansion_mult),
        exit_on_anchor_flip=bool(exit_on_anchor_flip),
        anchor=anchor,
        atr_n=int(atr_n),
    )
