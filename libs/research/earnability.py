"""EARNABILITY -- the PAYOUT side of a backtest (L1.49).

Every leakage instrument this desk owns validates the FEATURE. `leakage_detector.audit` is
`audit(feature, fwd_ret, same_ret)` and all eight of its contracts regress the *feature* against
the return. `libs/features/validation.py` "target leakage" means the feature reads the label.
`axis_screen`'s angle-20 gate de-contaminates the *signal*. CPCV purge/embargo protects the
*split*. NOT ONE of them takes the return series as the object under test -- it is the axiom they
all assume.

That makes payout contamination not merely undetected but ANTI-DETECTED: a P&L series crediting
flows the position could not have held for passes every instrument MORE cleanly than a real edge
would, because the contamination sits in the term each test treats as ground truth.

THE DISTINCTION THIS MODULE IS BUILT ON, and it is the whole reason the live instance survived
review: a phase error PRESERVES THE COUNT. Three settlements are booked and three were earnable,
so totals, means and every aggregate reconciliation agree. Only the PAIRING of a flow with the
weight that earned it is wrong. Measured over 2,517 daily bars the booked and earnable panels had
identical means to 8 decimal places and correlated 0.961 -- an estimator can be exactly right on
average and mis-paired on every single bar (the L1.47 shape, one layer up).

THE MT5 INSTANCE OF THE PROBLEM, and it is the one that matters now. On the MT5/Fusion universe
the discrete payout is the broker's SWAP ROLLOVER: financing is credited or debited at one instant
per trading day (the broker's 00:00 server time, triple-charged on the Wednesday that carries the
weekend), never accrued minute by minute. Share-CFD and index-CFD DIVIDEND adjustments behave the
same way. A position opened after the stamp and closed before the next one earns NOTHING; one held
across a single stamp earns a FULL day of financing. So the booked/earnable phase question this
module answers is live on the MT5 lake (`libs/data/lake.py`, `desks/mt5/data/`) exactly as it was
on the venue it was first written against, and the module reads whatever stamped-flow series the
caller hands it -- it has never fetched anything itself.

THE TWO CONVENTIONS, and the desk currently runs both:
  BOOKED    bins [t, t+1) -- pandas `resample("1D")` default, left-closed and left-labelled. Bar
            t is credited every payout stamped DURING day t.
  EARNABLE  bins (t, t+1] -- payouts strictly AFTER entry through exit inclusive, because a
            position closed exactly ON a stamp has already been paid. The research panel never
            got the memo.

A position established at the open of bar t cannot earn the settlement stamped at that same
instant -- the decision consumes the close of bar t-1, which IS 00:00 of day t, so any non-zero
latency misses it (the desk's own measured maker waits are 14-247s, L1.45). It holds instead
through 00:00 of day t+1. Booked and earnable therefore run ONE SETTLEMENT OUT OF PHASE, and the
error is signed rather than random whenever selection and phase are coupled -- which is precisely
the case for a rule that ranks on RECENT FINANCING (an MT5 swap-carry sleeve ranks exactly this
way), since the settlement adjoining the signal window carries more of the signal's own
autocorrelation than the one a day further out.

WHAT THIS MODULE REFUSES TO DO. It does not claim a phase choice is right or wrong in general;
it MEASURES the dependence. A result whose sign or significance survives rebinning is robust to
the convention, and that is a fact worth having. A result that does not is a convention artifact,
and the desk needs to know which of its numbers those are before sizing anything on them.

Generalises to every DISCRETE flow: swap/rollover financing, dividend adjustments on share and
index CFDs, maker rebates, index-rebalance payments. Anything paid AT an instant rather than
accrued over one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

#: Hours between discrete payout stamps. 24.0 is the MT5/Fusion default -- one SWAP ROLLOVER per
#: trading day at the broker's server midnight -- and it is a DEFAULT, not a law: a caller whose
#: flow settles on a different grid (an intraday financing schedule, a dividend calendar) passes
#: its own. The number is never inferred from the data, because inferring a settlement cadence
#: from the series being tested is how a phase artifact hides inside its own diagnosis.
DEFAULT_INTERVAL_H = 24.0

#: Phase conventions. BOOKED is what a naive daily resample of a stamped flow series produces;
#: EARNABLE is the window a position is actually paid for -- strictly after entry, through exit.
BOOKED = "booked"
EARNABLE = "earnable"
PHASES = (BOOKED, EARNABLE)

#: A rebinning that moves |ΔSharpe| by less than this is not a convention artifact. Pre-registered
#: so the threshold cannot be chosen after seeing the number.
SHARPE_TOLERANCE = 0.10

#: Likewise for the mean, in bps per bar.
MEAN_BPS_TOLERANCE = 2.0


def normalise_stamps(ts: pd.DatetimeIndex, interval_h: float = DEFAULT_INTERVAL_H
                     ) -> pd.DatetimeIndex:
    """Floor settlement stamps onto the settlement grid.

    A settlement engine stamps its payouts a few MILLISECONDS PAST the boundary -- measured on the
    series this module was first written against, the offsets spanned 0-37ms across 38 distinct
    values, and an MT5 broker's swap-rollover stamps drift the same way because both are a batch
    job that starts AT the boundary and takes time to finish. Those milliseconds are a bookkeeping
    artifact of the settlement job, not an economic fact, and left unnormalised they scatter a
    right-closed binning into the wrong bar for every stamp with a non-zero offset. Flooring first
    is what makes the two phase conventions differ by exactly one settlement and nothing else.

    Anchored to the UTC day: the grid starts at midnight and steps by ``interval_h``.
    """
    if interval_h <= 0:
        raise ValueError(f"interval_h must be positive, got {interval_h}")
    if not isinstance(ts, pd.DatetimeIndex):
        raise TypeError(f"expected a DatetimeIndex, got {type(ts).__name__}")
    if ts.tz is None:
        raise ValueError("settlement stamps must be tz-aware (UTC) -- a naive stamp has no clock")
    day = ts.normalize()
    elapsed_h = (ts - day).total_seconds() / 3600.0
    return day + pd.to_timedelta(np.floor(elapsed_h / interval_h) * interval_h, unit="h")


def bin_flows(flows: pd.Series, *, phase: str, freq: str = "1D",
              interval_h: float = DEFAULT_INTERVAL_H) -> pd.Series:
    """Aggregate discrete settlement flows into bars under an explicit phase convention.

    BOOKED   -> bins [t, t+freq)  (pandas default; what the lake holds today)
    EARNABLE -> bins (t, t+freq]  (strictly after entry, through exit inclusive)

    Both are labelled by the LEFT edge, so the two results are directly comparable bar-for-bar and
    the only difference is which settlements land in which bar.
    """
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}, got {phase!r}")
    if not isinstance(flows.index, pd.DatetimeIndex):
        raise TypeError("flows must be indexed by a DatetimeIndex of settlement stamps")
    if flows.empty:
        return pd.Series(dtype="float64")
    f = flows.sort_index()
    f.index = normalise_stamps(f.index, interval_h)
    closed = "left" if phase == BOOKED else "right"
    return f.resample(freq, closed=closed, label="left").sum()


def bin_panel(flows: dict[str, pd.Series] | pd.DataFrame, *, phase: str, freq: str = "1D",
              interval_h: float = DEFAULT_INTERVAL_H) -> pd.DataFrame:
    """`bin_flows` across a panel of symbols, returned on the union index."""
    if isinstance(flows, pd.DataFrame):
        flows = {c: flows[c].dropna() for c in flows.columns}
    if not flows:
        return pd.DataFrame()
    binned = {s: bin_flows(v, phase=phase, freq=freq, interval_h=interval_h)
              for s, v in flows.items()}
    binned = {s: v for s, v in binned.items() if not v.empty}
    return pd.DataFrame(binned).sort_index() if binned else pd.DataFrame()


@dataclass(frozen=True)
class Attribution:
    """Per-position earnability of the flows a backtest credited to it."""

    n_flows: int
    n_earnable: int
    n_unearnable: int
    booked: float
    earnable: float
    unearnable: float

    @property
    def unearnable_share(self) -> float:
        """Share of credited flow VALUE the position could not have held for. 0.0 when nothing
        was credited -- an empty position is not a contaminated one."""
        tot = abs(self.booked)
        return 0.0 if tot == 0.0 else abs(self.unearnable) / tot


def attributable(flows: pd.Series, entry_ts: datetime, exit_ts: datetime, *,
                 decision_ts: datetime | None = None, latency_s: float = 0.0) -> Attribution:
    """Which credited flows was this position actually open for?

    A flow is EARNABLE iff its stamp falls in (entry + latency, exit] -- strictly after the
    position could have been established, through the exit inclusive -- the window a held
    position is actually paid for, applied to VALUES rather than to counts.

    `decision_ts` tightens it: a flow stamped before the decision that selected the position is
    unearnable however the fill went, because the position did not exist as an intention yet.
    Passing it is how a caller checks the SELECTION boundary rather than only the FILL boundary.
    """
    if latency_s < 0:
        raise ValueError(f"latency_s must be non-negative, got {latency_s}")
    if flows.empty:
        return Attribution(0, 0, 0, 0.0, 0.0, 0.0)
    if not isinstance(flows.index, pd.DatetimeIndex):
        raise TypeError("flows must be indexed by a DatetimeIndex of settlement stamps")
    open_from = pd.Timestamp(entry_ts) + pd.Timedelta(seconds=latency_s)
    if decision_ts is not None:
        open_from = max(open_from, pd.Timestamp(decision_ts) + pd.Timedelta(seconds=latency_s))
    held = (flows.index > open_from) & (flows.index <= pd.Timestamp(exit_ts))
    earn, un = flows[held], flows[~held]
    return Attribution(
        n_flows=len(flows), n_earnable=int(held.sum()), n_unearnable=int((~held).sum()),
        booked=float(flows.sum()), earnable=float(earn.sum()), unearnable=float(un.sum()),
    )


@dataclass(frozen=True)
class PhaseSensitivity:
    """Result of rebinning a strategy's payout stream under each phase convention."""

    sharpe: dict[str, float]
    mean_bps: dict[str, float]
    n: int
    d_sharpe: float
    d_mean_bps: float
    convention_dependent: bool
    sign_flip: bool
    detail: dict[str, float] = field(default_factory=dict)


def _sharpe(r: np.ndarray, periods: float = 365.0) -> float:
    r = np.asarray(r, dtype="float64")
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    return float("nan") if sd == 0 else float(r.mean() / sd * np.sqrt(periods))


def phase_sensitivity(build_returns: Callable[[pd.DataFrame], np.ndarray],
                      panels: dict[str, pd.DataFrame], *,
                      periods: float = 365.0,
                      sharpe_tolerance: float = SHARPE_TOLERANCE,
                      mean_bps_tolerance: float = MEAN_BPS_TOLERANCE) -> PhaseSensitivity:
    """THE METAMORPHIC TEST ON THE PAYOUT SIDE.

    `build_returns(flow_panel) -> np.ndarray` rebuilds the strategy's return series from a
    payout panel. `panels` maps each phase name to the panel binned under that convention. The
    strategy code is UNCHANGED between runs -- only which settlement lands in which bar moves.

    A result whose Sharpe or mean depends on that choice beyond the pre-registered tolerances is a
    CONVENTION ARTIFACT: the number is a property of a binning decision nobody voted on rather
    than of the market. A sign flip is the strongest form and is reported separately.

    Refuses rather than guesses: a missing phase raises, and a degenerate series yields NaN which
    propagates to `convention_dependent = False` only through an explicit finite check.
    """
    missing = [p for p in PHASES if p not in panels]
    if missing:
        raise ValueError(f"panels missing required phases: {missing}")
    sharpe, mean_bps, n = {}, {}, 0
    for phase in PHASES:
        r = np.asarray(build_returns(panels[phase]), dtype="float64")
        n = max(n, int(np.isfinite(r).sum()))
        sharpe[phase] = _sharpe(r, periods)
        finite = r[np.isfinite(r)]
        mean_bps[phase] = float(finite.mean() * 1e4) if len(finite) else float("nan")
    ds = sharpe[BOOKED] - sharpe[EARNABLE]
    dm = mean_bps[BOOKED] - mean_bps[EARNABLE]
    both_finite = np.isfinite(ds) and np.isfinite(dm)
    dependent = bool(both_finite and (abs(ds) > sharpe_tolerance or abs(dm) > mean_bps_tolerance))
    flip = bool(np.isfinite(sharpe[BOOKED]) and np.isfinite(sharpe[EARNABLE])
                and np.sign(sharpe[BOOKED]) != np.sign(sharpe[EARNABLE]))
    return PhaseSensitivity(
        sharpe=sharpe, mean_bps=mean_bps, n=n,
        d_sharpe=float(ds), d_mean_bps=float(dm),
        convention_dependent=dependent, sign_flip=flip,
        detail={"sharpe_tolerance": sharpe_tolerance, "mean_bps_tolerance": mean_bps_tolerance},
    )
