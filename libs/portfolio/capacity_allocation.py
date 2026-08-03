"""CROSS-FAMILY ALLOCATION, CAPPED BY WHAT EACH STRATEGY CAN ACTUALLY CARRY.

TWO GAPS THIS CLOSES, AND NEITHER WAS A MISSING PRIMITIVE. `libs/portfolio/` already holds
max-Sharpe, risk parity, HRP, covariance, a factor model and concentration caps -- a real toolkit.
What was missing sat on either side of it:

  NOTHING FED FAMILIES IN. The breadth work built for ICT
  (`libs/ict/cross_sectional.effective_breadth`) measures how many INDEPENDENT bets a set of
  return streams really represents, and it was pointed only at ICT symbols. Two families that
  turn out to be the same trade in different vocabulary are one bet, and a sleeve allocator fed
  their separate Sharpes will happily double the position. Measured breadth across families is
  the check that catches it.

  NOTHING CAPPED A WEIGHT BY CAPACITY. Allocation ran in Sharpe space, where a strategy with a
  30bp edge and 5bp of tradeable capacity looks identical to one that can carry the whole book.
  `libs/execution/book_walk.capacity_at_impact` measures capacity from the desk's own recorded
  depth, and this is where that number becomes binding rather than informative.

THE ORDER MATTERS AND IS NOT NEGOTIABLE. Optimise first, then cap, then RENORMALISE ONTO THE
STRATEGIES THAT STILL HAVE ROOM -- never scale everything down uniformly. Capping without
redistributing silently leaves the book under-invested; redistributing without re-capping pushes
the freed capital into names that were already at their limit. Both are single-line mistakes with
the same signature: a book that reports full allocation and cannot execute it.

CAPACITY IS A HARD CONSTRAINT, NOT A PENALTY. A soft version -- shading weights toward capacity --
reads as prudent and is worse: it lets a strategy hold slightly more than it can trade, forever,
and the excess only shows up as slippage nobody attributes back here. If the desk cannot execute
it, it cannot hold it.

Pure numpy. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from libs.ict.cross_sectional import effective_breadth
from libs.portfolio.construction import concentration_cap, max_sharpe_weights
from libs.risk.edge_gate import gated_leverage

#: Prepended when the gross target was EARNED from forward evidence rather than chosen.
_GATE_NOTE = ("Gross target came from libs/risk/edge_gate -- forward-validated edge, not a "
              "hand-picked number. ")

#: Why capacity is a wall rather than a nudge.
_CAPACITY_NOTE = (
    "Capacity is a HARD constraint, not a penalty: a strategy the desk cannot execute cannot be "
    "held, and shading weights toward capacity instead would let it hold slightly too much "
    "forever while the excess showed up only as unattributed slippage. Unallocated capital is "
    "REPORTED -- if every strategy is at its cap, the honest answer is that the book cannot "
    "absorb the target.")

__all__ = [
    "AllocationResult",
    "allocate_with_capacity",
    "family_correlation",
]


@dataclass(frozen=True)
class AllocationResult:
    """Weights the desk can actually execute, and the evidence behind them."""

    names: tuple[str, ...]
    weights: np.ndarray = field(repr=False)
    capacity_frac: np.ndarray = field(repr=False)
    capped: tuple[str, ...] = field(default=())
    n_eff: float = float("nan")
    mean_corr: float = float("nan")
    gross: float = 0.0
    unallocated: float = 0.0
    note: str = ""

    @property
    def ir_multiple(self) -> float:
        """sqrt of measured effective breadth -- what diversification actually bought."""
        return float(np.sqrt(self.n_eff)) if np.isfinite(self.n_eff) else float("nan")

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.names, (float(w) for w in self.weights), strict=True))


def family_correlation(streams: pd.DataFrame) -> tuple[np.ndarray, float, float]:
    """(correlation matrix, measured effective breadth, mean pairwise correlation).

    THE CHECK NOTHING WAS DOING. Two families can be the same trade wearing different vocabulary --
    an ICT liquidity sweep and a mean-reversion-after-stop-run are not obviously the same thing on
    paper and may be identical in P&L. A sleeve allocator handed their separate Sharpes doubles
    the position and reports diversification. Effective breadth is measured from the streams
    rather than assumed from the fact that they have different names.
    """
    d = streams.dropna(how="all").fillna(0.0)
    if d.shape[1] == 0:
        return np.empty((0, 0)), float("nan"), float("nan")
    n_eff, corr = effective_breadth(d)
    return d.corr().to_numpy(), n_eff, corr


def allocate_with_capacity(streams: pd.DataFrame, sharpes: dict[str, float],
                           capacity_frac: dict[str, float], *,
                           gross_target: float | None = None,
                           concentration: float = 0.35,
                           fwd_sharpe: float | None = None,
                           fwd_days: int = 0) -> AllocationResult:
    """Allocate across strategies of ANY family, then bind each weight to its tradeable capacity.

    `capacity_frac[name]` is the largest fraction of the book that strategy can carry at the
    desk's impact budget -- from `book_walk.capacity_at_impact` divided by book size. A capacity
    of 0 means the strategy cannot be traded at any size and its weight is 0, whatever its Sharpe.

    Returns the executable book. `unallocated` is reported rather than hidden: if every strategy
    is at its cap and the target is not met, the honest answer is that the desk cannot deploy that
    much capital, not that it should pretend to.
    """
    names = tuple(streams.columns)
    if not names:
        raise ValueError("no strategies to allocate across")
    missing = [n for n in names if n not in sharpes or n not in capacity_frac]
    if missing:
        raise ValueError(
            f"missing Sharpe or capacity for {missing}. A strategy with unknown capacity cannot "
            "be sized -- defaulting it to unlimited is how an unexecutable book gets built.")

    # GROSS IS EARNED, NOT CHOSEN. `libs/risk/edge_gate.gated_leverage` sizes to FORWARD-validated
    # edge -- floor until a 90-day shadow accumulates positive out-of-sample evidence, then ramping
    # toward half-Kelly of the FORWARD Sharpe. It sat unwired, which meant every allocation ran at
    # a hand-picked gross regardless of whether anything had proven itself live. On a desk with
    # zero forward days that is the difference between the floor and a number somebody typed.
    #
    # An explicit `gross_target` still wins, because a caller stress-testing a book must be able to
    # ask "what if". Absent one, the gate decides -- and with no forward evidence it returns the
    # floor, which is the honest answer for this desk today.
    if gross_target is None:
        gross_target = gated_leverage(fwd_sharpe, fwd_days) / gated_leverage(None, 0)

    corr, n_eff, mean_corr = family_correlation(streams)
    mu = np.array([sharpes[n] for n in names], dtype="float64")
    cap = np.array([max(capacity_frac[n], 0.0) for n in names], dtype="float64")

    w = max_sharpe_weights(mu, corr)
    w = concentration_cap(w, concentration)
    w = w * gross_target

    # CAP, THEN REDISTRIBUTE ONTO WHAT STILL HAS ROOM, THEN RE-CAP. Scaling everything down
    # uniformly would leave the book under-invested; redistributing once without re-capping pushes
    # the freed capital into names already at their limit. Iterating to a fixed point is the only
    # version that both respects every cap and deploys what it can.
    capped: set[str] = set()
    for _ in range(len(names) + 2):
        over = w > cap + 1e-12
        if not over.any():
            break
        capped.update(n for n, o in zip(names, over, strict=True) if o)
        spill = float((w[over] - cap[over]).sum())
        w = np.where(over, cap, w)
        room = np.maximum(cap - w, 0.0)
        total_room = float(room.sum())
        if total_room <= 1e-12 or spill <= 1e-12:
            break
        w = w + spill * (room / total_room)

    w = np.minimum(w, cap)                        # final guard: no weight may exceed its capacity
    gross = float(w.sum())
    return AllocationResult(
        names=names, weights=w, capacity_frac=cap, capped=tuple(sorted(capped)),
        n_eff=n_eff, mean_corr=mean_corr, gross=gross,
        unallocated=max(gross_target - gross, 0.0),
        note=(_GATE_NOTE if fwd_sharpe is not None else "") + _CAPACITY_NOTE)
