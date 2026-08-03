"""AUDIT AN EXTERNAL TRACK RECORD -- does the curve come from EDGE or from RISK-LOADING?

WHY THIS EXISTS. The desk has a full validation stack for candidates it generates itself -- CPCV,
PBO, Romano-Wolf, DSR, the gauntlet -- and NOTHING that can adjudicate a track record handed to it
from outside. That gap has a concrete cost: the standard way a retail desk loses its capital is by
copying a strategy whose reported returns were never audited, and "I could not check" is not a
risk control. Every organ here judges the desk's own work; this one judges someone else's claim.

THE ARITHMETIC THAT MOTIVATES IT. A claim of 5-10%/week compounds to 12x-141x per year; 30-40% per
month compounds to 23x-57x per year. Renaissance's Medallion, the best record that exists, runs
around 66%/yr gross. Claims in that range are therefore not "very good" -- they are a different
kind of object, and the useful response is not disbelief but MEASUREMENT, because the mechanism
that produces them is identifiable and leaves fingerprints in the trade list.

WHAT ACTUALLY PRODUCES A SMOOTH 5%/WEEK CURVE. Almost always position sizing, not signal. Add to
losers, never stop out, close on any retrace to break-even, and the equity curve is a near-straight
line with a 90%+ win rate -- until one trend runs and the account is gone. The pattern label on the
front (FVG, order block, supply/demand) is decoration; the return profile is a fact about the
SIZING rule. So the fingerprints this module looks for are sizing fingerprints:

  SIZE ESCALATION AFTER LOSS -- the martingale signature. Mean size following a loss against mean
  size following a win, plus the slope of size on consecutive-loss depth. An edge-driven system
  has no reason to size by the last trade's outcome; a martingale has no other rule.
  PAYOFF ASYMMETRY -- win rate far above half while average win is far below average loss. This
  is not by itself a defect (many real strategies are shaped this way), but combined with sizing
  escalation it is the picking-up-pennies profile whose left tail has not been sampled yet.
  UNSAMPLED LEFT TAIL -- the worst loss against the equity it was earned on. A record whose worst
  observed loss is a small fraction of the account has not yet met the event it is exposed to.
  RUIN UNDER RESAMPLING -- the streaks are the risk, so the bootstrap must PRESERVE them. A
  stationary block bootstrap over the trade sequence re-runs the same strategy through orderings
  it happened not to see; a martingale that survived the sample dies in a large share of them.

WHAT THIS CANNOT DO, STATED UP FRONT. An equity curve alone cannot separate edge from sizing --
the information is not in it. Only a TRADE LIST carries the sizing rule. When given a curve, this
module reports the distributional facts and refuses the mechanism question rather than guessing at
it, because a confident wrong answer here is exactly the failure it exists to prevent.

Pure numpy. No I/O, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError

__all__ = [
    "RUIN_FRACTION",
    "TrackRecordAudit",
    "audit_trades",
    "compound",
    "years_to_significance",
]

#: Equity drop that counts as ruin. Not zero: a leveraged retail account is closed out by the
#: broker long before equity reaches zero, and margin call is the operative event.
RUIN_FRACTION = 0.5

#: Size-after-loss / size-after-win above this reads as deliberate escalation rather than noise.
#: 1.5x is well outside what discretionary variation produces and well inside a 2x martingale.
ESCALATION_FLAG = 1.5


def compound(rate: float, periods: int) -> float:
    """Growth multiple from compounding `rate` over `periods`. The claim's own consequence."""
    return float((1.0 + rate) ** periods)


def years_to_significance(sharpe: float, *, t_target: float = 2.0) -> float:
    """Years of track record needed before this Sharpe is distinguishable from zero.

    t = SR * sqrt(T_years), so T = (t_target / SR)^2. This is the number that settles most
    arguments about a short record: at SR 1.0 it takes 4 years to reach t=2, and a three-month
    sample cannot support ANY claim about skill regardless of how good the return looks. Returned
    as inf for a non-positive Sharpe, which is the honest reading -- no amount of further data
    makes a negative edge significant in the intended direction.
    """
    return float("inf") if sharpe <= 0 else float((t_target / sharpe) ** 2)


@dataclass(frozen=True)
class TrackRecordAudit:
    """What the trade list says about where the returns came from."""

    n_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float                       # positive magnitude
    payoff_ratio: float                   # avg_win / avg_loss; inf when there are no losses
    total_pnl: float
    max_drawdown: float                   # positive magnitude, on the realised equity path
    worst_trade: float                    # most negative single trade
    sharpe_per_trade: float
    size_after_loss: float
    size_after_win: float
    escalation_ratio: float               # size_after_loss / size_after_win
    loss_depth_slope: float               # regression of size on consecutive-loss depth
    ruin_probability: float               # P(equity falls RUIN_FRACTION) under resampled orderings
    deepest_loss_streak: int
    ruin_is_lower_bound: bool             # True when the sample cannot contain the rule's tail
    verdict: str
    reasons: tuple[str, ...] = field(default=())

    @property
    def risk_loaded(self) -> bool:
        return self.verdict == "RISK-LOADED"


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float(np.max(peak - equity)) if equity.size else 0.0


def _loss_depth(pnl: np.ndarray) -> np.ndarray:
    """Consecutive losses immediately BEFORE each trade. depth[0] is 0 by construction."""
    depth = np.zeros(pnl.size, dtype="float64")
    run = 0
    for i in range(1, pnl.size):
        run = run + 1 if pnl[i - 1] < 0 else 0
        depth[i] = run
    return depth


def audit_trades(pnl: Any, size: Any = None, *, starting_equity: float | None = None,
                 n_boot: int = 2000, mean_block: float = 5.0, seed: int = 0) -> TrackRecordAudit:
    """Audit a closed-trade sequence for the sizing fingerprints of a risk-loaded curve.

    `pnl` is per-trade profit in account currency, in CHRONOLOGICAL order -- the order is the
    whole point, since every signature here is about what the strategy did AFTER a loss. `size` is
    the position size opened for each trade; without it the sizing questions are unanswerable and
    the verdict says so rather than defaulting to clean.

    `starting_equity` anchors drawdown and ruin in account terms. Absent, it is taken as the sum
    of positive P&L, which is a deliberately GENEROUS stand-in: it makes the account look as large
    as the strategy's gross winnings, so any ruin probability reported under it is a lower bound.
    """
    p = np.asarray(pnl, dtype="float64").ravel()
    if p.size < 2:
        raise ValidationError("need at least 2 trades to audit a sequence")
    if not np.isfinite(p).all():
        raise ValidationError("pnl contains non-finite values -- a gap in the record is not a zero")

    wins, losses = p[p > 0], p[p < 0]
    win_rate = float(wins.size / p.size)
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(-losses.mean()) if losses.size else 0.0
    payoff = float(avg_win / avg_loss) if avg_loss > 0 else float("inf")
    sd = float(p.std(ddof=1))
    sharpe_t = float(p.mean() / sd) if sd > 0 else 0.0

    equity0 = (float(starting_equity) if starting_equity is not None
               else max(float(wins.sum()), 1e-9))
    equity = equity0 + np.cumsum(p)
    mdd = _max_drawdown(equity)

    # ---------------------------------------------------------------- sizing
    reasons: list[str] = []
    if size is None:
        s_loss = s_win = escalation = slope = float("nan")
        reasons.append(
            "NO SIZE COLUMN -- the sizing rule is where a risk-loaded curve is visible, and it is "
            "not in this input. Every sizing statistic is undefined and the mechanism question is "
            "refused rather than answered.")
    else:
        s = np.asarray(size, dtype="float64").ravel()
        if s.size != p.size:
            raise ValidationError(f"size has {s.size} rows against {p.size} pnl rows")
        if (s < 0).any():
            raise ValidationError("negative position size -- direction belongs in pnl, not size")
        prev_loss = np.concatenate(([False], p[:-1] < 0))
        prev_win = np.concatenate(([False], p[:-1] > 0))
        s_loss = float(s[prev_loss].mean()) if prev_loss.any() else float("nan")
        s_win = float(s[prev_win].mean()) if prev_win.any() else float("nan")
        escalation = float(s_loss / s_win) if s_win and np.isfinite(s_win) and s_win > 0 \
            else float("nan")
        depth = _loss_depth(p)
        # Slope of size on loss depth, normalised by mean size so it reads as "extra multiples of
        # a normal position per additional consecutive loss" and is comparable across accounts.
        if depth.std() > 0 and s.mean() > 0:
            slope = float(np.polyfit(depth, s, 1)[0] / s.mean())
        else:
            slope = 0.0

    # ------------------------------------------------------------------ ruin
    # THE STREAKS ARE THE RISK, so the resampling must preserve them. An i.i.d. shuffle breaks the
    # very clustering that kills a martingale and would report a reassuring number for exactly the
    # strategies this module exists to catch.
    deepest = int(_loss_depth(p).max())
    rng = np.random.default_rng(seed)
    ruin_hits = 0
    for _ in range(n_boot):
        idx = stationary_block_indices(p.size, mean_block, rng)
        path = equity0 + np.cumsum(p[idx])
        if float(path.min()) <= equity0 * (1.0 - RUIN_FRACTION):
            ruin_hits += 1
    ruin = ruin_hits / n_boot

    # --------------------------------------------------------------- verdict
    if np.isfinite(escalation) and escalation >= ESCALATION_FLAG:
        reasons.append(
            f"SIZE ESCALATES AFTER LOSSES: {escalation:.2f}x larger following a loss than "
            f"following a win. An edge-driven rule has no reason to size on the previous trade's "
            f"outcome; a martingale has no other rule.")
    if np.isfinite(slope) and slope >= 0.25:
        reasons.append(
            f"SIZE GROWS WITH LOSS DEPTH: +{slope:.2f} of a normal position per additional "
            f"consecutive loss. This is the recovery-doubling shape, and it converts a run of "
            f"ordinary losses into a single account-ending one.")
    if win_rate >= 0.8 and payoff < 0.5:
        reasons.append(
            f"PICKING UP PENNIES: {win_rate:.0%} win rate with average win only "
            f"{payoff:.2f}x the average loss. Not a defect by itself, but the left tail is what "
            f"pays for it and this sample has not yet met it.")
    if ruin >= 0.05:
        reasons.append(
            f"RUIN IN {ruin:.1%} OF RESAMPLED ORDERINGS: the same trades in a different order "
            f"take the account down {RUIN_FRACTION:.0%}. Surviving the sequence that happened is "
            f"not evidence of surviving the sequence that did not.")
    # THE STREAK IS WHAT THE ESCALATION RULE HAS NOT YET MET. This originally compared the worst
    # single loss to starting equity, which fired on the negative control: a strategy risking 0.3%
    # a trade is exercising GOOD risk management, and flagging it would have made the module shout
    # at the well-behaved case. The exposure a sizing rule creates is a function of STREAK LENGTH,
    # so the honest question is how deep a run the sample actually contained -- and it is only
    # worth asking once escalation has been established, which is why it is nested.
    #
    # IT ALSO REPAIRS THE RUIN NUMBER, which was the more dangerous half. The bootstrap RESAMPLES
    # OBSERVED TRADES, so it can reorder the sample but can never invent a loss deeper than any
    # that occurred. Measured on a doubling rule with a 70% in-sample win rate: ruin probability
    # came back 0.000 -- maximally reassuring about precisely the strategy the module exists to
    # catch, because the rule's tail is not in the sample to be resampled. Reporting that 0.000
    # unqualified would be this desk's own recurring failure, reading "not measured" as "measured
    # and fine". Under an established escalation rule the figure is therefore published as a LOWER
    # BOUND, and it can never produce a clean verdict on its own.
    ruin_lower_bound = False
    if np.isfinite(escalation) and escalation >= ESCALATION_FLAG and deepest <= 5:
        ruin_lower_bound = True
        reasons.append(
            f"RUIN FIGURE IS A LOWER BOUND: the longest losing run in this record is "
            f"{deepest} trades, and the bootstrap can only reorder losses that actually "
            f"occurred -- it cannot manufacture the deep run this sizing rule is exposed to. "
            f"The {ruin:.1%} above is what the SAMPLE can demonstrate, not what the RULE "
            f"risks. A short record makes an escalation rule look safer, not be safer.")

    # Both RUIN reasons are hard: an observed ruin probability and an unmeasurable one are equally
    # disqualifying, and treating the second as softer is what makes a short record persuasive.
    hard = [r for r in reasons if r.startswith(("SIZE ", "RUIN "))]
    if hard:
        verdict = "RISK-LOADED"
    elif size is None:
        verdict = "UNDECIDABLE"
    elif reasons:
        verdict = "SUSPECT"
    else:
        verdict = "NO-RISK-LOADING-FOUND"
        reasons.append(
            "No sizing fingerprint found. This is NOT a finding of edge -- it says the returns "
            "were not manufactured by the sizing rules this module can see, and says nothing "
            "about whether the signal works out of sample. Absence of one failure mode is not "
            "presence of skill.")

    return TrackRecordAudit(
        n_trades=int(p.size), win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss,
        payoff_ratio=payoff, total_pnl=float(p.sum()), max_drawdown=mdd,
        worst_trade=float(p.min()), sharpe_per_trade=sharpe_t,
        size_after_loss=s_loss, size_after_win=s_win, escalation_ratio=escalation,
        loss_depth_slope=slope, ruin_probability=ruin,
        deepest_loss_streak=deepest, ruin_is_lower_bound=ruin_lower_bound,
        verdict=verdict, reasons=tuple(reasons))
