"""THE ICT SETUP AS AN EXECUTABLE STRATEGY -- detectors were never a strategy on their own.

WHAT WAS MISSING. Twenty-two ICT detectors exist, are causally guarded and go through the desk's
stage-A screen. None of them takes a position. A detector answers "is this pattern present"; a
strategy answers "how much do I hold, where do I stop, and what closes it" -- and the second
question is where essentially all of the P&L variance lives. Screening features and never building
the sequence they belong to is the desk's own "built but never runs" class, one level up.

THE SEQUENCE, FROM THE MENTORSHIP MATERIAL, IN ORDER. A single ICT trade is not a pattern, it is a
four-step story, and each step must complete before the next is looked for:

  1. SWEEP    price takes out a confirmed prior swing and closes back through it. Liquidity was
              taken. Settled ON the sweeping bar, never from the reversal that followed, which
              would be circular.
  2. SHIFT    within a bounded window, a displacement leg AND a close through the opposing swing.
              A sweep with no structural break is just a wick, and trading it is trading noise.
  3. ENTRY    price retraces into the imbalance the displacement left -- the FVG, or the 62-79%
              OTE band of the leg. This is the only step that puts on risk.
  4. EXIT     stop beyond the sweep extreme (the level whose violation refutes the story), target
              a fixed multiple of that risk.

THE WINDOW IS WHAT MAKES IT FALSIFIABLE. Without a bound on step 2, any sweep eventually gets a
structure break and the setup becomes unconditional -- the "detector that fires 89% of the time"
failure this family already produced once. `setup_window` bars is the deadline, and a setup that
misses it is DISCARDED rather than left pending.

SIZING IS FIXED-FRACTIONAL AND CANNOT ESCALATE. This is a hard property, tested, not a default:
the whole reason this desk can look at a 5%/week gold EA and say something useful is that the
returns of such systems come from adding to losers. An ICT strategy that did the same would be the
same object wearing better vocabulary. `risk_fraction` is constant across every trade regardless
of what the previous trade did -- see `libs/validation/track_record.py`, which exists to catch the
alternative, and would flag this module's own output if that ever changed.

STRICTLY CAUSAL. The state machine walks bars forward and reads only closed bars; the engine
executes at the NEXT bar's open. The detectors it consumes publish swing levels `confirm` bars
late, so "the prior high" here is a level that was actually knowable at the time.

NO PROMOTION AUTHORITY. This produces a target series. Whether it survives contact with costs,
CPCV, Romano-Wolf and the gauntlet is decided by those organs, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from libs.ict.canonical import OTE_HI, OTE_LO, OTE_MID
from libs.ict.patterns import (
    displacement,
    fair_value_gap,
    liquidity_sweep,
    market_structure_shift,
    swing_high,
    swing_low,
)

__all__ = ["ICTParams", "ICTSetup", "ict_targets", "schedule", "setups"]


@dataclass(frozen=True)
class ICTParams:
    """Every knob, in one place, so a fitted variant is visible as a diff rather than hidden."""

    confirm: int = 2
    disp_window: int = 20
    disp_k: float = 2.0
    #: Bars allowed between the sweep and the structure shift. Bounded on purpose: unbounded, the
    #: setup becomes unconditional, since any sweep eventually gets a break.
    setup_window: int = 12
    #: Bars allowed between the shift and the retrace entry, for the same reason.
    entry_window: int = 12
    #: Fraction of equity at risk per trade. CONSTANT -- never a function of the last outcome.
    risk_fraction: float = 0.01
    #: Target as a multiple of the stop distance.
    reward_multiple: float = 2.0
    #: Require the retrace to land in the 62-79% OTE band as well as in an FVG.
    require_ote: bool = False
    #: "market" -- signal on the close, cross the spread next open (taker both ways).
    #: "limit"  -- rest an order at the 70.5% OTE level and be filled only if price comes to it.
    #: The second is what the setup actually describes, and it moves the cost of this strategy
    #: from ~19% of capital a year to ~2.5%. It also means a level that is never touched is NO
    #: TRADE, which is the honest price of waiting and must never be silently waived.
    entry_mode: str = "market"
    #: Require price to trade strictly THROUGH the resting level before claiming a fill. Touching
    #: it is not being filled -- that assumes queue priority the desk has not earned.
    limit_through: bool = True
    #: Cap on |target| as a fraction of equity, so a tight stop cannot imply absurd leverage.
    max_leverage: float = 3.0

    def __post_init__(self) -> None:
        if not 0 < self.risk_fraction < 1:
            raise ValueError("risk_fraction must be in (0, 1)")
        if self.setup_window < 1 or self.entry_window < 1:
            raise ValueError("setup_window and entry_window must be >= 1")
        if self.reward_multiple <= 0:
            raise ValueError("reward_multiple must be positive")
        if self.entry_mode not in ("market", "limit"):
            raise ValueError("entry_mode must be 'market' or 'limit'")


@dataclass(frozen=True)
class ICTSetup:
    """One completed trade story, with the bar index of each step it actually reached."""

    direction: int          # +1 long, -1 short
    sweep_i: int
    shift_i: int
    entry_i: int
    entry_price: float
    stop: float
    target: float


def _leg_extremes(bars: pd.DataFrame, a: int, b: int) -> tuple[float, float]:
    """(low, high) of the displacement leg spanning bars a..b inclusive."""
    seg = bars.iloc[a:b + 1]
    return float(seg["low"].min()), float(seg["high"].max())


def setups(bars: pd.DataFrame, params: ICTParams | None = None) -> list[ICTSetup]:
    """Walk the bars once and return every completed sweep -> shift -> entry sequence.

    Deliberately a forward loop rather than a vectorised expression. The sequence has STATE -- a
    pending sweep, a deadline, a leg whose extremes define the entry band -- and the vectorised
    version of that is where lookahead gets in: `shift(-k)`, a rolling window that includes the
    current bar, or an extreme computed over the whole leg before the leg has finished.
    """
    p = params or ICTParams()
    need = {"open", "high", "low", "close"}
    if not need <= set(bars.columns):
        raise KeyError(f"ICT strategy needs {sorted(need)} -- got {sorted(bars.columns)}")
    n = len(bars)
    if n == 0:
        return []

    sweep = liquidity_sweep(bars, p.confirm).to_numpy()
    disp = displacement(bars, p.disp_window, p.disp_k).to_numpy()
    mss = market_structure_shift(bars, p.confirm).to_numpy()
    fvg = fair_value_gap(bars).to_numpy()
    s_hi = swing_high(bars, p.confirm).to_numpy()
    s_lo = swing_low(bars, p.confirm).to_numpy()
    low, high, close = (bars["low"].to_numpy(), bars["high"].to_numpy(),
                        bars["close"].to_numpy())

    out: list[ICTSetup] = []
    # Pending state. `direction` 0 means nothing is in progress.
    direction = 0
    sweep_i = shift_i = -1
    sweep_extreme = np.nan
    leg_lo = leg_hi = np.nan

    for i in range(n):
        # --- step 1: a sweep opens a story, and REPLACES any stale one ------------------------
        if sweep[i] != 0 and shift_i < 0:
            # liquidity_sweep is +1 for a SELL-SIDE sweep (a prior low taken, close back above),
            # which is the setup for a LONG. The sign already points at the trade.
            direction = int(sweep[i])
            sweep_i = i
            sweep_extreme = low[i] if direction > 0 else high[i]
            continue

        if direction == 0:
            continue

        # --- deadline on step 2 ---------------------------------------------------------------
        if shift_i < 0 and i - sweep_i > p.setup_window:
            direction, sweep_i = 0, -1
            continue

        # --- step 2: displacement AND a structure break, both in the sweep's direction ---------
        if shift_i < 0:
            if disp[i] == direction and mss[i] == direction:
                shift_i = i
                leg_lo, leg_hi = _leg_extremes(bars, sweep_i, i)
            continue

        # --- deadline on step 3 ---------------------------------------------------------------
        if i - shift_i > p.entry_window:
            direction, sweep_i, shift_i = 0, -1, -1
            continue

        # --- step 3: the retrace into the imbalance -------------------------------------------
        span = leg_hi - leg_lo
        if not np.isfinite(span) or span <= 0:
            direction, sweep_i, shift_i = 0, -1, -1
            continue
        # Retracement measured from the leg's terminal extreme back toward its origin.
        if direction > 0:
            retrace = (leg_hi - low[i]) / span
            in_band = OTE_LO <= retrace <= OTE_HI
        else:
            retrace = (high[i] - leg_lo) / span
            in_band = OTE_LO <= retrace <= OTE_HI
        # LIMIT ENTRY -- THE MODE THAT CHANGES THE ECONOMICS, AND THE ONE EASIEST TO FAKE.
        #
        # The ICT entry IS a resting order by construction: you are waiting for price to retrace
        # into a level you identified in advance. Crossing the spread for that is a choice, and an
        # expensive one -- 15bp round trip taker against ~2bp maker, which on this strategy's
        # turnover is 19% of capital a year against 2.5%. That single difference is larger than any
        # plausible edge in the signal, so modelling it is not an optimisation, it is the question.
        #
        # IT MUST NOT BE MODELLED FLATTERINGLY, and there are exactly two ways to cheat:
        #   NON-FILL. A limit at a level price never reaches is NO TRADE. Silently falling back to
        #   a market entry would keep every winner and pay maker fees for it -- the single most
        #   flattering bug available here. A setup whose level is never touched inside the window
        #   is DISCARDED, and the fill rate is reported so the cost of waiting is visible.
        #   QUEUE PRIORITY. Filling whenever the bar's low merely TOUCHES the level assumes the
        #   book handed us the print. `limit_through` requires price to trade strictly THROUGH it,
        #   which is the conservative reading and the default.
        if p.entry_mode == "limit":
            level = (leg_hi - OTE_MID * span) if direction > 0 else (leg_lo + OTE_MID * span)
            hit = (low[i] < level) if direction > 0 else (high[i] > level)
            if p.limit_through is False:
                hit = (low[i] <= level) if direction > 0 else (high[i] >= level)
            if not hit:
                continue                       # not filled yet; the deadline above ends the story
            entry = float(level)
        else:
            touched_fvg = fvg[i] == direction
            if not (touched_fvg or (in_band and not p.require_ote)):
                continue
            if p.require_ote and not in_band:
                continue
            entry = float(close[i])
        # The stop sits beyond the level whose violation REFUTES the story -- the sweep extreme,
        # not a round number and not a fixed distance. If price returns through it, liquidity was
        # not taken and reversed; it was taken and continued.
        stop = float(sweep_extreme)
        if direction > 0:
            stop = min(stop, float(s_lo[i]) if np.isfinite(s_lo[i]) else stop)
            risk = entry - stop
        else:
            stop = max(stop, float(s_hi[i]) if np.isfinite(s_hi[i]) else stop)
            risk = stop - entry
        if not np.isfinite(risk) or risk <= 0:
            direction, sweep_i, shift_i = 0, -1, -1
            continue
        target = entry + direction * p.reward_multiple * risk
        out.append(ICTSetup(direction=direction, sweep_i=sweep_i, shift_i=shift_i, entry_i=i,
                            entry_price=entry, stop=stop, target=float(target)))
        direction, sweep_i, shift_i = 0, -1, -1

    return out


def schedule(bars: pd.DataFrame,
             params: ICTParams | None = None) -> tuple[pd.Series, list[ICTSetup]]:
    """(targets, setups actually TAKEN) -- the two halves of the same walk, computed once.

    THE SECOND RETURN VALUE IS NOT A CONVENIENCE. `setups()` reports every completed sequence,
    including ones that arrive while a trade is already live and are therefore skipped. Anything
    reading `setups()` and the target series together -- a report, an attribution, a test -- will
    otherwise line up a skipped setup's entry bar against the PREVIOUS trade's position and draw a
    confident wrong conclusion from it. Which setups were traded is a fact the strategy knows and
    must publish, rather than one the caller has to reconstruct.
    """
    p = params or ICTParams()
    tgt = np.zeros(len(bars), dtype="float64")
    if len(bars) == 0:
        return pd.Series(tgt, index=bars.index, dtype="float64"), []

    taken: list[ICTSetup] = []
    high, low = bars["high"].to_numpy(), bars["low"].to_numpy()
    n = len(bars)
    # ONE POSITION AT A TIME. The state machine can open a new sweep on the bar after an entry, so
    # two setups' holding periods can overlap. Writing both into the same array silently let the
    # later one overwrite the earlier -- which is not "the second trade won", it is a position
    # that closed for no reason the strategy can state. A setup arriving while a trade is live is
    # SKIPPED, and the skip is visible here rather than being an artifact of assignment order.
    busy_until = -1
    for s in setups(bars, p):
        if s.entry_i <= busy_until:
            continue
        risk_frac = abs(s.entry_price - s.stop) / s.entry_price
        if risk_frac <= 0:
            continue
        size = min(p.risk_fraction / risk_frac, p.max_leverage) * s.direction

        # SIGNAL ON THE ENTRY BAR'S CLOSE, filled by the engine at the next bar's open. An earlier
        # draft set the target on entry_i+1, which fills a bar later still -- a full extra bar of
        # delay that is not conservatism but a different strategy.
        # A resting limit is filled DURING its bar, so the rest of that bar can already stop it
        # out; a market order is not filled until the next open. Using entry_i+1 for both let the
        # limit variant escape the fill bar's own adverse move -- see run_ict_strategy.trade_pnl.
        exit_j = n
        limit = p.entry_mode == "limit"
        for j in range(s.entry_i if limit else s.entry_i + 1, n):
            # On the fill bar only the STOP can close the position: the limit was filled by that
            # bar's low, and its high may have printed BEFORE that low. Counting a same-bar target
            # assumes the favourable intrabar path and manufactures edge out of noise.
            fill_bar = limit and j == s.entry_i
            hit = ((s.direction > 0 and (low[j] <= s.stop
                                         or (not fill_bar and high[j] >= s.target)))
                   or (s.direction < 0 and (high[j] >= s.stop
                                            or (not fill_bar and low[j] <= s.target))))
            if hit:
                exit_j = j
                break
        tgt[s.entry_i:exit_j] = size
        busy_until = exit_j
        taken.append(s)
    return pd.Series(tgt, index=bars.index, dtype="float64"), taken


def ict_targets(bars: pd.DataFrame, params: ICTParams | None = None) -> pd.Series:
    """Signed target position as a fraction of equity, one value per bar.

    Signalled on the entry bar's close and filled by the engine at the next bar's open, held until
    the stop or target is touched. Sizing is risk_fraction / (stop distance) -- a wider stop takes
    a SMALLER position, which is what makes risk-per-trade constant, and is the exact opposite of
    the escalate-after-loss rule that produces the equity curves this desk audits other people for.
    """
    return schedule(bars, params)[0]
