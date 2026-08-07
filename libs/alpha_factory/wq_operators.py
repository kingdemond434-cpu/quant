"""OPERATORS THE DESK'S EXPRESSION LANGUAGE DID NOT HAVE -- and the bar it must NOT import.

SOURCE: a community summary of WorldQuant BRAIN practice, forwarded by the principal 2026-08-07.
Two kinds of content arrived together and they must be handled in opposite ways.

**THE TRANSFERABLE HALF: GROUP-RELATIVE OPERATORS.** The canonical construct in that taxonomy is
`group_rank(-ts_delta(log(close), 1), subindustry)` -- rank a signal WITHIN A PEER GROUP, not
across the whole universe. The desk had no group operator of any kind: `combination_engine`'s
`rank` and `zscore` are universe-wide, so every cross-sectional cell in the 898,560-candidate
sweep asked "is this coin extreme against ALL coins?" and none asked "is it extreme against its
PEERS?". Those are different questions, and on a book where BTC and a small-cap L1 share almost no
volatility regime the second is usually the better one -- a universe-wide rank is dominated by the
group a name belongs to rather than by anything specific to the name.

Also here: `ts_backfill` (sparse crypto series are full of holes that a naive transform propagates)
and `trade_when` -- which is NOT the desk's existing `condition` operator. `condition` goes FLAT
when its gate fails; `trade_when` HOLDS THE PREVIOUS POSITION. That difference is entirely about
turnover, and turnover is what killed the desk's strongest measured signal (WS-006: order-flow
momentum, Holm-cleared at t=+3.95, netting -0.656 bp/bar). An operator that expresses "keep the
position rather than churn out and back in" attacks the exact term that has been fatal.

**THE HALF THAT MUST NOT BE IMPORTED: THE SUBMISSION BAR.** The same source reports "in-sample
Sharpe >= 1.25, turnover in a band, and a fitness score". IT IS AN IN-SAMPLE SUBMISSION FILTER FOR
A PLATFORM THAT DOES ITS OWN OUT-OF-SAMPLE VALIDATION AFTERWARDS AND PAYS PER ACCEPTED ALPHA. Their
economics make a permissive in-sample screen rational: they can afford false positives because
they, not the contributor, run the expensive stage.

This desk's economics are the opposite -- it eats every false positive itself, with its own
capital. Its bar is a DEFLATED t of 5.236 over a declared 898,560-candidate universe, plus
out-of-sample, walk-forward, leakage and independence. Adopting "in-sample Sharpe >= 1.25" would
not be borrowing a respected institution's standard; it would be a bar reduction of roughly an
order of magnitude wearing that institution's name (L1.6: never lower a bar). So `fitness()` is
here as a DIAGNOSTIC and there is no `passes_submission_bar()` function -- deliberately, because
the function that does not exist cannot be called by an organ that read the same screenshot.

WHAT IS USEFUL IN THE FITNESS FORMULA is its shape, not its threshold: `Sharpe x sqrt(|annual
return| / max(turnover, 0.125))` penalises churn explicitly, which is the same lesson WS-006 paid
for in measurement. Used as a ranking diagnostic it is informative. Used as a gate it is a
different bar than the one the desk declared.

**THESE OPERATORS EXPAND THE SEARCH SPACE AND ARE THEREFORE NOT IN `TRANSFORMS` YET.** Adding three
transforms takes the universe from 898,560 to 1,698,840 and would silently invalidate
FULL_SWEEP_PREREGISTRATION.md's declared count -- the hurdle IS the universe size. They must be
declared in a NEW pre-registered family before any sweep uses them, and `run_full_sweep.py` will
refuse to start if the two disagree. That refusal is the fence working, not a bug.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

__all__ = [
    "GROUP_TRANSFORMS",
    "UNIVERSE_IF_ADOPTED",
    "fitness",
    "group_rank",
    "group_zscore",
    "trade_when",
    "ts_backfill",
]

#: The new transforms, kept SEPARATE from `combination_engine.TRANSFORMS` until a pre-registration
#: declares the enlarged universe. Listing them here makes them usable and reviewable without
#: changing the hurdle of a family that is already declared.
GROUP_TRANSFORMS: tuple[str, ...] = ("group_rank", "group_zscore", "ts_backfill")

#: What the declared universe becomes if all three are adopted, at 13 features. Written down so the
#: cost of adoption is visible BEFORE it is paid: the bar moves from 5.236 to 5.356.
UNIVERSE_IF_ADOPTED: int = 1_698_840


def _require_groups(panel: pd.DataFrame, groups: dict[str, str] | None) -> dict[str, str] | None:
    """Group map, or None when it cannot be used.

    REFUSING IS THE POINT. With no group map, a `group_rank` that silently fell back to a
    universe-wide rank would be indistinguishable from the existing `rank` transform -- it would
    consume a whole new arm of the search space while computing something the desk already has,
    and every result would look like a new finding. A missing map is UNMEASURABLE, not universal.
    """
    if not groups:
        return None
    named = {c: groups[c] for c in panel.columns if c in groups}
    if len(named) < 2 or len(set(named.values())) < 2:
        return None                       # one group is the universe; that is `rank`, not this
    return named


def group_rank(x: pd.Series, panel: pd.DataFrame,
               groups: dict[str, str] | None) -> pd.Series | None:
    """Percentile of `x` WITHIN ITS PEER GROUP at each bar. None when groups are unusable.

    Members outside the map are excluded rather than pooled into a residual group: an "other"
    bucket built from whatever was unlabelled is not a peer group, and ranking within it would
    manufacture a comparison nobody intended.
    """
    named = _require_groups(panel, groups)
    if named is None or x.name not in named:
        return None
    peers = [c for c, g in named.items() if g == named[str(x.name)]]
    if len(peers) < 2:
        return None                       # a group of one has no rank to compute
    return panel[peers].rank(axis=1, pct=True)[x.name]


def group_zscore(x: pd.Series, panel: pd.DataFrame,
                 groups: dict[str, str] | None) -> pd.Series | None:
    """Standardise `x` against its peer group at each bar. None when groups are unusable."""
    named = _require_groups(panel, groups)
    if named is None or x.name not in named:
        return None
    peers = [c for c, g in named.items() if g == named[str(x.name)]]
    if len(peers) < 2:
        return None
    sub = panel[peers]
    sd = sub.std(axis=1).replace(0.0, np.nan)
    return sub.sub(sub.mean(axis=1), axis=0).div(sd, axis=0)[x.name]


def ts_backfill(x: pd.Series, *, limit: int = 5) -> pd.Series:
    """Carry the last valid observation forward, BOUNDED.

    `limit` is not a tuning knob, it is a leakage guard. An unbounded forward-fill turns a series
    that stopped updating into a flat line the harness reads as a live signal, and on a delisted or
    halted name that flat line persists against real forward returns for as long as the sample
    runs. Bounded fill covers a gap; unbounded fill invents data.

    FORWARD ONLY. There is no backward fill here despite the operator's name in the source
    taxonomy: filling backwards writes a future observation into a past bar, which is leakage by
    construction and would be invisible in every result it contaminated.
    """
    return x.ffill(limit=max(0, limit))


def trade_when(condition: pd.Series, signal: pd.Series) -> pd.Series:
    """Take `signal` where `condition` holds; otherwise HOLD THE PREVIOUS VALUE.

    THE DIFFERENCE FROM THE DESK'S `condition` OPERATOR IS THE WHOLE POINT, and it is a turnover
    difference. `condition` multiplies the signal by a gate, so a failed gate means FLAT -- the
    book exits and re-enters every time the gate flickers, paying the round trip twice for a view
    that never changed. `trade_when` holds, so the cost is paid only when the view itself changes.

    This is aimed squarely at the desk's most expensive measured lesson: WS-006's order-flow
    momentum cleared Holm at t=+3.95 and still netted -0.656 bp/bar, because turnover ate it. An
    operator that expresses persistence is the cheapest available attack on that term.

    NOT A COST MODEL AND NOT A FIX. It changes what the signal IS, so a `trade_when` version of a
    cell is a DIFFERENT hypothesis that owes its own trial, not a repaired version of the old one.
    """
    gated = signal.where(condition.astype(bool))
    return gated.ffill()


def fitness(sharpe: float, annual_return: float, turnover: float,
            *, floor: float = 0.125) -> float:
    """`Sharpe x sqrt(|annual return| / max(turnover, floor))` -- a DIAGNOSTIC, never a gate.

    Reproduced because its SHAPE encodes something the desk paid to learn: it penalises churn
    explicitly, so two strategies with identical Sharpe rank differently when one trades ten times
    as often. As a ranking aid within an already-validated set, that is useful.

    **IT IS NOT A BAR AND THERE IS DELIBERATELY NO `passes_submission_bar()` IN THIS MODULE.** The
    source's "in-sample Sharpe >= 1.25" is a submission filter for a platform that runs its own
    out-of-sample validation afterwards and pays per accepted alpha -- their economics make a
    permissive in-sample screen rational because they, not the contributor, bear the cost of a
    false positive. This desk bears it, with its own capital, and its declared bar is a deflated t
    of 5.236 plus out-of-sample, walk-forward, leakage and independence. A function that returned
    True/False against 1.25 would be an order-of-magnitude bar reduction wearing a respected
    institution's name (L1.6), and the function that does not exist cannot be called by an organ
    that read the same summary.
    """
    if turnover < 0 or not math.isfinite(sharpe) or not math.isfinite(annual_return):
        return float("nan")
    return float(sharpe * math.sqrt(abs(annual_return) / max(turnover, floor)))
