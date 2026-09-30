"""EXIT OPERATORS: post-entry, state-conditional exits expressed in an engine that has none.

WHERE THIS CAME FROM, SO NOBODY LATER READS IT AS THE DESK'S OWN IDEA. A public video walkthrough
(2026-09-23, an agent building a trend follower and searching ~200 variations) demonstrated two
exits this desk could not express, and its author said of the second that he had never seen it
before:

  (a) EXIT ON ANCHOR FLIP -- when the higher-timeframe trend direction turns against the open
      position, go flat immediately, without waiting for stop, target or time.
  (b) EXIT ON VOLATILITY EXPANSION -- when current ATR exceeds `k` times the ATR that was
      observed AT ENTRY, go flat. The claim is that a regime whose volatility has multiplied
      since the trade was opened is no longer the regime the trade was opened into, so the
      position's edge is gone whatever the price has done.

THE HONEST PRIOR ON IT, recorded here because the number will be quoted at this desk otherwise.
The video reported a Sharpe of 1.87. That was the MAXIMUM over ~200 searched variations with NO
multiplicity charge applied, on ONE single-name equity (Apple), and the author's own Monte Carlo
put the median of the search at about 1.30. A maximum over 200 trials is not an estimate of the
mechanism; under this desk's deflated-Sharpe charge it is a number that has already spent its
significance. 1.30 is the closer reading and even that is in-sample. The mechanism is a
HYPOTHESIS here, privileged by nothing (LAWS: a public claim is a hypothesis, never evidence).

WHY AN OPERATOR AND NOT A FAMILY. (a) and (b) are not entry claims. They compose with ANY entry
this desk already has -- there are 65 registered families and neither exit exists in any of them
(`volatility_squeeze`, `vol_transition` and `vol_mean_reversion` all condition ENTRY on
volatility; no family conditions an EXIT on volatility relative to its own value at entry).
Writing them as one more family would have tested the pair on one entry rule and left the other
64 untouched, which is the narrower and less honest question.

HOW A CONDITIONAL EXIT IS EXPRESSED WITHOUT TOUCHING THE SIMULATOR. `mt5desk.engine.run_backtest`
has a fixed exit machine: stop, bank, chandelier trail, then `ttl_bars`. Nothing in it re-reads a
feature series after entry, `Signal` has no callback and no metadata field, and the loop only
materialises open/high/low. Adding a hook would mean a new `Signal` field plus an insertion into
the bar loop every certificate on this desk has been judged by -- a blast radius this research
work has no business taking on, and `engine.py` is the one file both the backtest and
`shadow_forward` share.

So the exit is encoded as a TRUNCATED `ttl_bars`, computed inside the family, with the bar index
of the first post-entry bar at which the condition is true. `run_backtest` checks stop and target
on bars `fill_bar .. fill_bar + ttl - 1` and otherwise exits at `open[fill_bar + ttl]`, so setting
`ttl = j - fill_bar + 1` for a condition first true at bar `j` exits at the OPEN OF BAR j+1 --
the condition is read at the close of `j` from bars that had already printed, and the fill is the
next open. That is causally identical to a live "flat on the next bar" and it is the same
convention every entry on this desk already uses (`wait_bars=1`, fill at the following open).

WHAT IS LOST BY THAT ENCODING, said out loud: the engine records `reason="ttl"` for these exits,
so a conditional exit and a timeout are indistinguishable in the trade log. `exit_reasons()` below
recovers the distinction for reporting; the R and the equity curve are unaffected because the exit
BAR and PRICE are the ones the rule names.

WHAT IS NOT LOST: stop and target still win when they fire first, on the pessimistic intrabar
ordering `run_backtest` already applies. The operator only ever SHORTENS a hold. It can never
extend one, never move a stop, never add size -- so it is not a risk-reduction mechanism under
Growth Governance Rule 1 in the sense that needs a proof, it is a competing EXIT RULE whose whole
claim is that it raises terminal wealth, and the gauntlet is what decides that. A cell carrying
the operator and a cell without it are two candidates judged against the same bar.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr

__all__ = [
    "EXPANSION_MULT_GRID",
    "anchor_direction",
    "apply_exit_operators",
    "exit_reasons",
    "vol_expansion_bar",
]

#: The swept grid for the volatility-expansion multiple. THE VIDEO'S 4.0 IS ONE POINT IN IT AND
#: HAS NO STANDING. A constant lifted from one person's search over one single-name equity is a
#: borrowed overfit; the desk's answer to a borrowed constant is to sweep the neighbourhood and
#: let the gauntlet say which end of it, if any, survives. Values below 1.0 are excluded because
#: "ATR has fallen since entry" is a DIFFERENT mechanism (vol compression), not this one, and
#: mixing the two into one parameter would let a survivor at 0.8 be reported as evidence for a
#: claim about expansion.
#:
#: THE GRID REACHES DOWN BECAUSE THE VIDEO'S 4.0 MEASURED AS NEARLY INERT HERE (2026-09-23,
#: EURUSD H1, 54,205 bars). At 4.0 the rule shortened 2.1% of a 120-bar hold and 0.05% of a
#: 12-bar hold: ATR does not quadruple inside twelve hours of FX. At 1.5 it shortened 56% of the
#: 120-bar holds. So on this desk's instruments the video's constant would have minted thousands
#: of cells that are EXACT DUPLICATES of their control arms -- each paying a multiplicity charge
#: for a question it does not ask. That is the concrete cost of borrowing a constant from someone
#: else's search over one single-name equity, and it is the reason the multiple is swept.
EXPANSION_MULT_GRID: tuple[float, ...] = (1.25, 1.5, 2.0, 3.0, 4.0, 6.0)


def anchor_direction(
    d: pd.DataFrame,
    *,
    anchor_mult: int = 4,
    anchor_n: int = 50,
) -> pd.Series:
    """The higher-timeframe trend direction, as +1/-1/0 on THIS chart's bars.

    THE RATIO IS THE CLAIM, NOT THE HOUR. The video computed a FOUR-HOUR anchor for a ONE-HOUR
    entry. Hard-coding "4H" would make the mechanism inexpressible on every other chart of the
    desk's seven-chart ladder and would silently mean something different on each: the same
    family on M15 would be reading a 16x anchor and on D1 a four-day one, both called "4H". What
    the mechanism actually names is a SPEED RATIO between the gate and the trigger, so
    `anchor_mult` is that ratio in bars of the chart in hand, and the video's setup is exactly
    the point (chart=H1, anchor_mult=4). The ratio is a swept dimension like any other.

    The anchor is built by aggregating `anchor_mult` consecutive bars into one anchor bar and
    taking the sign of (close - SMA(anchor_n)) on that aggregated series, forward-filled back onto
    the fine bars. STRICTLY TRAILING: an anchor bar is only published on the fine bar that CLOSES
    it, so a fine bar is never gated by an anchor bar that had not finished printing. Getting that
    wrong is the standard way this shape of family leaks, and it leaks in the direction that makes
    it look good.
    """
    anchor_mult = max(1, int(anchor_mult))
    anchor_n = max(2, int(anchor_n))
    if len(d) < anchor_mult * (anchor_n + 2):
        return pd.Series(0.0, index=d.index, dtype=float)
    close = d["close"].astype(float)
    n = len(d)
    # Group index: bars [0..m-1] are anchor bar 0, [m..2m-1] anchor bar 1, ...  The anchor bar is
    # COMPLETE at the fine bar whose position is the last of its group, so that is the only fine
    # bar allowed to publish it.
    pos = np.arange(n)
    grp = pos // anchor_mult
    last_of_group = (pos % anchor_mult) == (anchor_mult - 1)
    agg = close.groupby(grp).last()
    sma = agg.rolling(anchor_n, min_periods=anchor_n).mean()
    sign = np.sign((agg - sma).to_numpy(dtype=float))
    sign = np.nan_to_num(sign, nan=0.0)
    # Publish each anchor bar's sign on the fine bar that closed it; everything else inherits the
    # last PUBLISHED value, so bar i is gated by anchor information strictly older than itself.
    raw = np.full(n, np.nan)
    raw[last_of_group] = sign[grp[last_of_group]]
    out = pd.Series(raw, index=d.index).shift(1).ffill().fillna(0.0)
    return out.astype(float)


def vol_expansion_bar(
    atr: np.ndarray,
    entry_pos: int,
    *,
    expansion_mult: float,
    horizon: int,
) -> int | None:
    """First bar in `(entry_pos, entry_pos+horizon]` where ATR exceeds `expansion_mult` x entry ATR.

    Returns the POSITION of that bar, or None if it never happens inside the horizon. The ATR at
    entry is the one printed by the entry bar itself, which is the value a live desk would have
    recorded when it sent the order.
    """
    if expansion_mult <= 0 or horizon <= 0:
        return None
    a0 = float(atr[entry_pos]) if entry_pos < atr.size else float("nan")
    if not np.isfinite(a0) or a0 <= 0:
        return None
    hi = min(atr.size - 1, entry_pos + int(horizon))
    if hi <= entry_pos:
        return None
    window = atr[entry_pos + 1: hi + 1]
    hit = np.flatnonzero(np.isfinite(window) & (window > expansion_mult * a0))
    if hit.size == 0:
        return None
    return int(entry_pos + 1 + hit[0])


def apply_exit_operators(
    d: pd.DataFrame,
    signals: Sequence[Signal],
    *,
    expansion_mult: float = 0.0,
    exit_on_anchor_flip: bool = False,
    anchor: pd.Series | None = None,
    atr_n: int = 14,
) -> list[Signal]:
    """Shorten each signal's `ttl_bars` to the first bar where an exit condition fires.

    `expansion_mult <= 0` disables (b); `exit_on_anchor_flip=False` or `anchor is None` disables
    (a). With both off this is the identity, which is what makes the operator's own contribution
    measurable: the SAME entry rule is judged with and without it and the two cells face the same
    bar.

    Applies to any signal list from any price-only family. The signal's own stop, target, side,
    trigger and wait_bars pass through untouched -- this operator has no opinion about entry.
    """
    sigs = [s for s in signals if s is not None]
    if not sigs:
        return []
    if expansion_mult <= 0 and not (exit_on_anchor_flip and anchor is not None):
        return list(sigs)
    idx = d.index
    atr = _atr(d, max(2, int(atr_n))).to_numpy(dtype=float)
    anch = None
    if exit_on_anchor_flip and anchor is not None:
        anch = anchor.reindex(idx).fillna(0.0).to_numpy(dtype=float)
    # ONE LOOKUP FOR THE WHOLE LIST, not one per signal. A family like `momentum_volgate` emits
    # 24,000 signals on a single instrument's hourly history and the operator is applied at every
    # point of its own grid, so a per-signal `get_indexer` turns an hourly leg into a stall.
    try:
        positions = idx.get_indexer(pd.DatetimeIndex([s.time for s in sigs]))
    except (TypeError, ValueError):
        positions = np.full(len(sigs), -1, dtype=int)
    out: list[Signal] = []
    for s, i0 in zip(sigs, (int(p) for p in positions), strict=True):
        if i0 < 0:
            out.append(s)
            continue
        # THE ENGINE COUNTS `ttl_bars` FROM THE FILL BAR, and the fill bar is the one after the
        # signal (`i = i0 + 1`). A resting trigger can fill later still, which this cannot see --
        # in that case the truncation is CONSERVATIVE (the hold ends no later than the rule says),
        # never permissive, so the operator can only ever take a trade off earlier than the live
        # rule would. Under-crediting an exit rule is the safe direction for a judge.
        fill = i0 + 1
        ttl = max(1, int(s.ttl_bars))
        stop_at: int | None = None
        if expansion_mult > 0:
            stop_at = vol_expansion_bar(atr, fill, expansion_mult=float(expansion_mult),
                                        horizon=ttl)
        if anch is not None and fill < anch.size:
            side = 1.0 if s.side > 0 else -1.0
            hi = min(anch.size - 1, fill + ttl)
            if hi > fill:
                window = anch[fill + 1: hi + 1]
                flipped = np.flatnonzero(window * side < 0.0)
                if flipped.size:
                    j = int(fill + 1 + flipped[0])
                    stop_at = j if stop_at is None else min(stop_at, j)
        if stop_at is None:
            out.append(s)
            continue
        new_ttl = max(1, stop_at - fill + 1)
        if new_ttl >= ttl:
            out.append(s)
            continue
        out.append(_replace_ttl(s, new_ttl))
    return out


def _replace_ttl(s: Signal, ttl: int) -> Signal:
    """A copy of `s` with `ttl_bars=ttl` and the operator recorded in the tag.

    `Signal` is a plain dataclass and is not frozen, but mutating the caller's object would make
    the with/without comparison depend on evaluation order. The tag carries `+xexit` so a trade
    log can tell an operator exit from a plain timeout, which the engine's own `reason` cannot
    (it records "ttl" for both).
    """
    from dataclasses import replace
    tag = s.tag if s.tag.endswith("+xexit") else f"{s.tag}+xexit"
    return replace(s, ttl_bars=int(ttl), tag=tag)


def exit_reasons(before: Sequence[Signal], after: Sequence[Signal]) -> dict[str, Any]:
    """How much the operator actually did, for the report that has to say so.

    An operator that shortened nothing is UNMEASURED on that cell, not vindicated: it means the
    condition never fired inside the holds the entry rule produced, and the cell is then a
    duplicate of the un-operated one carrying its own multiplicity charge. That is worth seeing.
    """
    n = min(len(before), len(after))
    cut = [(int(before[i].ttl_bars), int(after[i].ttl_bars)) for i in range(n)]
    shortened = [(a, b) for a, b in cut if b < a]
    return {
        "signals": len(before),
        "shortened": len(shortened),
        "shortened_share": (len(shortened) / len(before)) if before else 0.0,
        "median_ttl_before": float(np.median([a for a, _ in cut])) if cut else 0.0,
        "median_ttl_after": float(np.median([b for _, b in cut])) if cut else 0.0,
    }
