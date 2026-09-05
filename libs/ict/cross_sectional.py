"""CROSS-SECTIONAL ICT -- the only breadth lever that survives a highly correlated universe.

THE ARITHMETIC THAT FORCED THIS, AND THE CORRECTION IT NEEDED. Information ratio scales as
IC x sqrt(N) for INDEPENDENT bets. A directional book run across one factor complex -- the USD
majors, or an equity-index basket, where members routinely sit 0.8 correlated with the common
factor -- has far less breadth than its symbol count claims: N_eff = N / (1 + (N-1) * rho) puts
25 symbols at 1.24 effective bets, an IR multiple of 1.11x.

THAT ARITHMETIC WAS APPLIED TO THE WRONG OBJECT, and this module is what caught it. 0.8 is the
correlation of the ASSETS. The book is long some names and short others and holds sparsely, so its
P&L STREAMS correlate at about +0.06, not +0.80. Measured directional breadth is 9.77 of 20
symbols (IR 3.13x), not 1.1x. The directional lever is far better than the asset correlation
suggests, and the difference is the difference between a premise and a measurement.

Removing the common factor still helps, and by a measured amount rather than an assumed one: long
the symbol with the setup, short the index against it, and judge the residual.

THAT NUMBER IS AN ASSUMPTION AND THIS MODULE REFUSES TO INHERIT IT. `effective_breadth` MEASURES
what the residual streams actually achieved:

    N_eff = (sum_i sigma_i)^2 / Var(sum_i r_i)

which is exactly N for independent equal-vol streams and exactly 1 for perfectly correlated ones,
with no rho to assume and nothing to tune. Quoting 2.08x as a result when it was a premise is the
same error as reading "not measured" as "measured and fine", one level up.

TWO COSTS THE BREADTH GAIN HAS TO CLEAR, both modelled rather than waved through:
  THE HEDGE IS A SECOND TRADE. Every position now pays fees on two legs, so transaction costs
  roughly double. A 2x IR multiple bought with 2x costs is not obviously a gain, and on a
  strategy already losing ~19%/yr to fees it may be a loss. This is measured, not assumed.
  OVERNIGHT FINANCING, which is the one line item where the hedge PAYS FOR ITSELF. On MT5/Fusion
  this is the SWAP charged at the broker's daily rollover: it accrues per leg -- a long pays when
  the rate is against it, a short receives -- so it is charged on NET exposure. A market-neutral
  book nets close to zero and is largely immune; a directional one pays full notional. Charging it
  on gross would have erased the hedge's real advantage. Measured: raising the rate from 0 to
  5bp/day moves the hedged book's total cost by well under a percent of itself.

BETA IS ESTIMATED CAUSALLY, on a trailing window, and that is not a detail. A full-sample beta is
lookahead of the most flattering kind available here -- it would hedge each position using the
covariance the position itself helped produce, making the residual artificially clean and the
breadth artificially high. The number this module exists to produce would be the number the leak
manufactured.

Pure numpy/pandas. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from libs.ict.strategy import ICTParams, schedule

__all__ = [
    "BETA_WINDOW",
    "CrossSectionalResult",
    "effective_breadth",
    "equal_weight_index",
    "residualise",
    "rolling_beta",
    "run_cross_sectional",
]

#: Trailing bars used to estimate each symbol's beta to the index. Long enough that the estimate
#: is not noise, short enough to track a regime. Never the full sample -- see the module note.
BETA_WINDOW = 200

#: Below this many overlapping observations a correlation is not a measurement.
MIN_OVERLAP = 30

#: Overnight financing, basis points per DAILY ROLLOVER, applied to NET exposure. On the MT5
#: universe this is the broker's swap: one stamp per trading day at server midnight, triple-charged
#: on the day that carries the weekend. A ~1bp/day default is the right order of magnitude for a
#: liquid FX cross, but it is per-symbol, signed, asymmetric between long and short, and revised by
#: the broker without notice. It is a PARAMETER, not a constant, because assuming a rate and then
#: reporting the result as measured is the error this module was built to avoid; the realised
#: per-symbol series belongs here as soon as the MT5 lake carries it.
FINANCING_BPS_PER_DAY = 1.0

#: Hedge is left alone until its required notional drifts this far (in units of position size).
#: A continuously-rebalanced hedge cost 490% of capital a year in fees on the control panel --
#: an artifact of re-trading beta noise, not a property of the strategy.
HEDGE_BAND = 0.25


def equal_weight_index(returns: pd.DataFrame) -> pd.Series:
    """The 'market' as an equal-weight mean of the panel's own returns.

    Deliberately built FROM the panel rather than taken as a named index instrument (a dollar
    index, a benchmark future). A hedge against an instrument the desk does not hold is a second
    bet; the equal-weight mean is the factor these names actually share, and it is what a
    market-neutral book would be short.
    """
    return returns.mean(axis=1)


def rolling_beta(sym: pd.Series, idx: pd.Series, window: int = BETA_WINDOW) -> pd.Series:
    """Trailing OLS beta of `sym` on `idx`, published with no lookahead.

    `cov`/`var` over a trailing window that ENDS AT THE PREVIOUS BAR: the current bar's own return
    must not inform the beta used to hedge it, or the hedge is fitted to the move it is hedging.
    """
    cov = sym.rolling(window, min_periods=window // 2).cov(idx).shift(1)
    var = idx.rolling(window, min_periods=window // 2).var().shift(1)
    beta = (cov / var.replace(0.0, np.nan))
    # A symbol with no usable history is hedged one-for-one rather than left unhedged: assuming
    # beta 0 would leave full market exposure in a book whose whole premise is not having any.
    return beta.fillna(1.0).clip(-3.0, 3.0)


def residualise(sym_ret: pd.Series, idx_ret: pd.Series, beta: pd.Series) -> pd.Series:
    """r_residual = r_symbol - beta * r_index. What is left after the common factor is removed."""
    return sym_ret - beta * idx_ret


def effective_breadth(streams: pd.DataFrame) -> tuple[float, float]:
    """(N_eff, mean pairwise correlation) MEASURED from the return streams themselves.

    N_eff = (sum_i sigma_i)^2 / Var(sum_i r_i). Independent equal-vol streams give exactly N;
    perfectly correlated ones give exactly 1. There is no rho to assume and nothing to tune, which
    is the point: the 2.08x that motivated this module was a premise, and a premise reported as a
    result is how a desk convinces itself of something it never measured.
    """
    d = streams.dropna(how="all")
    if d.shape[1] == 0 or len(d) < MIN_OVERLAP:
        return float("nan"), float("nan")
    d = d.fillna(0.0)
    sig = d.std(ddof=1)
    tot = float(d.sum(axis=1).std(ddof=1))
    n_eff = float((sig.sum() ** 2) / (tot ** 2)) if tot > 0 else float("nan")
    if d.shape[1] < 2:
        return n_eff, float("nan")
    c = d.corr().to_numpy()
    off = c[~np.eye(c.shape[0], dtype=bool)]
    return n_eff, float(np.nanmean(off))


@dataclass(frozen=True)
class CrossSectionalResult:
    """What the market-neutral book achieved, and what the directional one would have."""

    symbols: list[str]
    bars: int
    n_positions: int
    #: MEASURED effective breadth of the residual streams, and of the raw directional streams.
    n_eff_residual: float
    n_eff_directional: float
    mean_corr_residual: float
    mean_corr_directional: float
    ir_multiple_residual: float
    ir_multiple_directional: float
    #: Portfolio return series, net of the modelled two-leg cost.
    net_return: pd.Series = field(repr=False)
    gross_return: pd.Series = field(repr=False)
    cost_drag_annual: float = 0.0
    note: str = ""

    @property
    def breadth_gain(self) -> float:
        """How much the hedge actually bought, in IR terms. 1.0 means it bought nothing."""
        if not np.isfinite(self.ir_multiple_directional) or self.ir_multiple_directional <= 0:
            return float("nan")
        return self.ir_multiple_residual / self.ir_multiple_directional


def _band_hold(target: pd.DataFrame, band: float) -> pd.DataFrame:
    """Hold each column's position until it drifts more than `band` from what is held.

    NO LOOKAHEAD: the decision on bar t uses only the target at t and what was already held. A
    band of 0 reduces exactly to continuous rebalancing, which is the behaviour it replaces.
    """
    if band <= 0:
        return target
    out = np.zeros(target.shape, dtype="float64")
    tv = target.to_numpy(dtype="float64")
    cur = np.zeros(tv.shape[1], dtype="float64")
    for t in range(tv.shape[0]):
        # THE BAND GOVERNS ADJUSTMENTS, NEVER ENTRIES OR EXITS -- and getting that wrong fails
        # OPEN. With a wide band the first version never crossed the threshold from flat, so the
        # hedge was simply never put on: a book reporting itself market-neutral while carrying
        # full directional exposure. Its own test caught it. Opening from flat and returning to
        # flat both always execute; only the drift in between is allowed to wait.
        opening = (cur == 0.0) & (tv[t] != 0.0)
        closing = tv[t] == 0.0
        drifted = np.abs(tv[t] - cur) > band
        cur = np.where(opening | closing | drifted, tv[t], cur)
        out[t] = cur
    return pd.DataFrame(out, index=target.index, columns=target.columns)


def run_cross_sectional(bars_by_symbol: dict[str, pd.DataFrame],
                        params: ICTParams | None = None, *,
                        taker_bps: float = 7.5, maker_bps: float = 1.0,
                        beta_window: int = BETA_WINDOW, hedge_band: float = HEDGE_BAND,
                        financing_bps_per_day: float = FINANCING_BPS_PER_DAY,
                        gross_cap: float = 1.0) -> CrossSectionalResult:
    """Run the ICT setup across a panel and hedge each position back to the equal-weight index.

    `gross_cap` bounds total absolute exposure across both legs, so breadth cannot be smuggled in
    as leverage -- the whole question is whether MORE INDEPENDENT BETS help, not whether a bigger
    book does.
    """
    p = params or ICTParams()
    if len(bars_by_symbol) < 2:
        raise ValueError("cross-sectional needs at least 2 symbols -- one symbol has no cross")

    closes = pd.DataFrame({s: d["close"].reset_index(drop=True)
                           for s, d in bars_by_symbol.items()})
    rets = closes.pct_change().fillna(0.0)
    idx = equal_weight_index(rets)

    # Per-symbol target weights from the same state machine used directionally.
    tgt = pd.DataFrame({s: schedule(d, p)[0].reset_index(drop=True)
                        for s, d in bars_by_symbol.items()}).fillna(0.0)
    n_pos = int((tgt != 0).to_numpy().sum())

    betas = pd.DataFrame({s: rolling_beta(rets[s], idx, beta_window) for s in rets.columns})

    # Per-symbol P&L streams. Position held INTO the next bar's return, so the target is shifted.
    #
    # THE GROSS CAP IS APPLIED TO POSITIONS, NOT TO THE RETURN SERIES. An earlier version scaled
    # the P&L down to the cap and then charged fees on the UNSCALED positions, which reported a
    # 490%-of-capital annual cost for a book that was never that big: twelve symbols each running
    # the full single-symbol size. The error was pessimistic rather than flattering, which is
    # exactly why it survived a reading -- a number that looks bad does not get questioned. Costs
    # and returns must come off the same book.
    raw_held = tgt.shift(1).fillna(0.0)
    avg_gross = float(raw_held.abs().sum(axis=1).mean() or 0.0)
    scale = min(float(gross_cap) / avg_gross, 1.0) if avg_gross > 0 else 1.0
    held = raw_held * scale

    direct = held * rets
    resid = held * pd.DataFrame({s: residualise(rets[s], idx, betas[s]) for s in rets.columns})

    n_eff_r, corr_r = effective_breadth(resid)
    n_eff_d, corr_d = effective_breadth(direct)

    # THE HEDGE IS A SECOND TRADE. Turnover is charged on the symbol leg AND on the index leg the
    # hedge implies, so costs roughly double -- which is exactly what the breadth gain must clear.
    #
    # AND IT MUST NOT BE RE-TRADED EVERY BAR. A continuously-updated beta implies touching the
    # hedge on every bar as the estimate drifts. No desk rebalances a hedge on beta noise, so the
    # hedge notional is held until it drifts outside a band.
    turn_sym = held.diff().abs().fillna(0.0).sum(axis=1)
    hedge_held = _band_hold(held * betas, hedge_band)
    turn_hedge = hedge_held.diff().abs().fillna(0.0).sum(axis=1)
    one_way = (taker_bps if p.entry_mode == "market" else maker_bps) / 10_000.0
    cost = (turn_sym + turn_hedge) * one_way

    # OVERNIGHT FINANCING, AND IT IS THE ONE PLACE THE HEDGE PAYS FOR ITSELF. The swap accrues on
    # each leg separately: a long pays when the rate is against it, a short receives. So it is
    # charged on NET exposure, and a market-neutral book -- long the symbol, short the index --
    # nets close to zero and is largely immune, while a directional book pays the full notional at
    # every rollover. Charging it on gross would have erased exactly the advantage the hedge has.
    net_exposure = (held.sum(axis=1) - hedge_held.sum(axis=1)).abs()
    bars_per_day = 96                                  # 15-minute bars
    financing = net_exposure * (financing_bps_per_day / 10_000.0) / bars_per_day

    gross = resid.sum(axis=1)
    cost = cost + financing
    net = gross - cost
    bars_per_year = 365 * 24 * 4                      # 15-minute bars
    drag = float(cost.mean() * bars_per_year)

    return CrossSectionalResult(
        symbols=list(closes.columns), bars=len(closes), n_positions=n_pos,
        n_eff_residual=n_eff_r, n_eff_directional=n_eff_d,
        mean_corr_residual=corr_r, mean_corr_directional=corr_d,
        ir_multiple_residual=float(np.sqrt(n_eff_r)) if np.isfinite(n_eff_r) else float("nan"),
        ir_multiple_directional=(float(np.sqrt(n_eff_d)) if np.isfinite(n_eff_d)
                                 else float("nan")),
        net_return=net, gross_return=gross, cost_drag_annual=drag,
        note=("Effective breadth is MEASURED from the realised streams, never assumed from a rho. "
              "The hedge is charged as a second trade because it is one. Overnight financing IS "
              "now modelled, on NET exposure -- a long pays and a short receives, so a "
              "market-neutral book nets near zero while a directional one pays full notional at "
              "every rollover; that is the one place the hedge pays for itself. The financing RATE "
              "is a parameter at a plausible default, not a measurement, so the total remains a "
              "LOWER BOUND until the MT5 lake supplies the realised per-symbol swap series. Market "
              "impact is not modelled at all and needs the book depth the desk has yet to "
              "record."))
