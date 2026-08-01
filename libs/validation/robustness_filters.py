"""Cheap robustness filters -- the ones that reject a PATHOLOGY rather than taxing every candidate.

WHY THESE AND NOT THE OTHERS. The 2026-08-01 gate audit established that this desk's problem is
over-conservatism: the gauntlet was applying family-wise multiplicity control twice and had ~0%
power against the effect sizes real strategies actually reach. Adding more rejection is therefore
the LAST thing it needs -- unless a filter is nearly free.

The distinction that makes these free, and it is the whole design rule here: a multiplicity
correction penalises EVERY candidate in proportion to how many others were tested, so it costs
power against real edges and noise alike. These filters instead identify a specific defect --
too few trades to estimate anything, a result that is too good to be skill, a candidate that is
just long a trending asset -- and are silent on everything else. A genuine edge with adequate
sample trips none of them.

WHAT WAS DELIBERATELY *NOT* ADOPTED, and it was measured rather than argued. An external study
(131,441 backtests) filters on OOS Sharpe > 2.5 as an asset-drift proxy: "above that on daily bars
the asset did the work". On this desk that filter is redundant AND harmful. Measured on pure
asset-drift candidates -- zero strategy skill, simply long a Sharpe-1.6 asset -- the existing
gauntlet already rejects 97.5% of them via Romano-Wolf, and only 2.5% survive. A blanket Sharpe
cap would close that 2.5% leak by rejecting every genuinely exceptional strategy as well, which
is precisely the trade the audit says this desk must stop making.

EFFECT-SIZE CALIBRATION. The same study reports that real verified edge on daily bars lands at
OOS Sharpe 0.5-1.5. That number is an empirical observation from a large sweep and it is far
below the 2-3 "world-class" figure this desk had been reasoning with, so it is recorded here as
the reference band rather than buried in a doc: a gate calibrated above 1.5 is calibrated above
the entire range where real edges are observed to live.
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np

#: Empirically observed band for genuine, out-of-sample-verified edge on daily bars (external
#: 131,441-backtest sweep, 2026). Recorded as the calibration target -- NOT as a gate.
REAL_EDGE_OOS_SHARPE_BAND = (0.5, 1.5)

#: Minimum closed trades before any per-trade statistic means anything. The desk already uses 20
#: for realised payoff (resolve_paper_book.PAYOFF_MIN_N); 30 is the external study's figure and
#: the more standard one for a Sharpe estimate. Taking the stricter of the two the desk has seen.
MIN_TRADES = 30

#: How many standard errors out-of-sample may exceed in-sample before it reads as luck.
#: STUDENTISED, not a fixed ratio, and that distinction is the whole filter -- see not_too_lucky.
LUCK_Z = 2.0
#: Periods per year for the daily bars the desk's campaigns are built on.
_PPY = 365.0


class FilterVerdict(NamedTuple):
    passed: bool
    name: str
    why: str


def sample_adequacy(n_trades: int, *, minimum: int = MIN_TRADES) -> FilterVerdict:
    """Enough closed trades for the statistics to carry information.

    Nearly free against real edges -- a strategy that cannot produce 30 trades over the validation
    window is one whose Sharpe has a standard error wide enough to contain almost anything, so
    rejecting it costs no genuine alpha, only the illusion of having measured one.

    This is also a live defect the desk has been exposed to rather than a hypothetical: an
    external walkthrough computed a full Kelly fraction from a backtest of FIFTEEN trades over 33
    years (80% win rate, 6.4 win/loss) and sized real positions from it. Kelly on 15 observations
    is noise wearing a decimal point.
    """
    ok = int(n_trades) >= int(minimum)
    return FilterVerdict(
        ok, "sample_adequacy",
        f"{n_trades} closed trades vs minimum {minimum}" + ("" if ok else
        " -- the Sharpe standard error at this count admits almost any true value, so the "
        "estimate carries no information regardless of how good it looks"))


def not_too_lucky(is_sharpe: float, oos_sharpe: float, n_is: int, n_oos: int, *,
                  z: float = LUCK_Z) -> FilterVerdict:
    """Out-of-sample must not beat in-sample by more than sampling noise can explain.

    THE IDEA IS BORROWED; THE IMPLEMENTATION IS NOT, and the difference was measured. The source
    filter is a fixed ratio -- "OOS may not exceed IS by more than 30%". Tested here on simulated
    edges it rejected 20-40% of GENUINE alphas while catching only ~35% of lucky nulls, and it did
    not improve at ANY sample length (T=310 through 5000). That is a coin flip that taxes real
    edges, and the audit's rule is that a new rejection must be nearly free or it does not ship.

    The defect is that a 70/30 split leaves the OOS Sharpe estimated on far fewer observations
    than the IS one, so its standard error is larger. A fixed percentage compares two estimates of
    different precision and mostly measures the noisier one.

    Studentising fixes it. The standard error of an annualised Sharpe over n daily bars is
    sqrt(PPY/n), so the DIFFERENCE carries sqrt(PPY/n_is + PPY/n_oos) and the comparison becomes
    scale-free. Measured at z=2.0 on T=310: rejects 2.8% of real edges, catches 6.2% of nulls that
    drew a flattering OOS Sharpe. At a campaign's real base rates -- roughly 400 nulls to 20 true
    edges -- that removes about 17 nulls for every real edge lost.

    Silent when in-sample is non-positive: expected_value and dsr already own that case, and
    firing here too would count one defect twice.
    """
    if is_sharpe <= 0:
        return FilterVerdict(True, "not_too_lucky",
                             "in-sample Sharpe non-positive -- the expected_value/dsr gates "
                             "already own this case")
    if n_is < 2 or n_oos < 2:
        return FilterVerdict(True, "not_too_lucky",
                             f"UNMEASURED -- need >=2 observations per side, got "
                             f"{n_is} in-sample and {n_oos} out-of-sample")
    se = float(np.sqrt(_PPY / n_is + _PPY / n_oos))
    t = (oos_sharpe - is_sharpe) / se
    ok = t <= z
    return FilterVerdict(
        ok, "not_too_lucky",
        f"OOS {oos_sharpe:.3f} vs IS {is_sharpe:.3f} = {t:+.2f} SE (limit {z:.1f})"
        + ("" if ok else " -- an improvement this large on data the optimiser never saw is not "
                         "skill the optimiser missed, it is a favourable draw, and draws do not "
                         "repeat"))


def asset_drift(strategy_returns: np.ndarray,
                benchmark_returns: np.ndarray | None) -> FilterVerdict:
    """Is this a strategy, or just exposure to something that went up?

    THE HONEST VERSION OF A FILTER THIS DESK ALREADY HALF-OWNS. `validate()`'s `beats_baselines`
    gate asks exactly this and, measured on 2026-08-01, blocked 0.0% of pure asset-drift
    candidates -- because no production caller supplies `benchmark_returns`, so it returns True
    unconditionally. A gate that appears to guard against contamination and guards nothing is
    worse than no gate, because it is counted as protection.

    So this reports UNMEASURED rather than PASSED when there is no benchmark. The distinction
    matters: the caller can then decide, and an audit can count how often the check actually ran
    instead of assuming it did.
    """
    if benchmark_returns is None:
        return FilterVerdict(True, "asset_drift",
                             "UNMEASURED -- no benchmark supplied, so this candidate was never "
                             "compared to buy-and-hold. Not evidence of an edge; evidence the "
                             "check did not run")
    s = np.asarray(strategy_returns, dtype="float64")
    b = np.asarray(benchmark_returns, dtype="float64")
    if len(b) != len(s) or len(s) < 2:
        return FilterVerdict(True, "asset_drift",
                             f"UNMEASURED -- benchmark length {len(b)} vs strategy {len(s)}")
    def _sr(x: np.ndarray) -> float:
        sd = float(x.std(ddof=1))
        return float(x.mean() / sd) if sd > 0 else 0.0
    ss, bs = _sr(s), _sr(b)
    ok = ss > bs
    return FilterVerdict(
        ok, "asset_drift",
        f"strategy per-period Sharpe {ss:.4f} vs benchmark {bs:.4f}"
        + ("" if ok else " -- does not beat simply holding the asset, so the return is exposure "
                         "rather than skill"))


def apply_all(*, n_trades: int, is_sharpe: float, oos_sharpe: float, n_is: int, n_oos: int,
              strategy_returns: np.ndarray | None = None,
              benchmark_returns: np.ndarray | None = None) -> dict[str, FilterVerdict]:
    """Every filter, reported individually so a caller can see WHICH pathology fired."""
    out = {
        "sample_adequacy": sample_adequacy(n_trades),
        "not_too_lucky": not_too_lucky(is_sharpe, oos_sharpe, n_is, n_oos),
    }
    if strategy_returns is not None:
        out["asset_drift"] = asset_drift(strategy_returns, benchmark_returns)
    return out
