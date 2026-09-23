"""cvxportfolio adapter -- an INDEPENDENT allocator challenger: a single-period optimisation
(returns forecast minus risk, leverage 1) back-tested on the bundle's own returns. What it
would have held is EVIDENCE about the book's diversification, never a size (LAWS 5h).
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "cvxportfolio"
CAPABILITY_FAMILY = "portfolio_optimization"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 5
GAMMA = 0.5


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    cvx = A.library("cvxportfolio")
    pd = A.library("pandas")
    if cvx is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "cvxportfolio (or pandas) is not importable here "
                                            "(pip install cvxportfolio==1.5.1)")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 800][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    n = min(len(f) for f in frames) - 1
    idx = pd.to_datetime(list(frames[0].time[-n:]))
    rets = pd.DataFrame({f.symbol: f.log_returns()[-n:] for f in frames}, index=idx)
    rets["USDOLLAR"] = 0.0
    try:
        md = cvx.UserProvidedMarketData(returns=rets, cash_key="USDOLLAR",
                                        min_history=pd.Timedelta(hours=200))
        sim = cvx.MarketSimulator(market_data=md)
        policy = cvx.SinglePeriodOptimization(cvx.ReturnsForecast() - GAMMA * cvx.FullCovariance(),
                                              [cvx.LeverageLimit(1)])
        result = sim.backtest(policy, start_time=idx[400])
        w = result.w.iloc[-1]
        weights = {str(k): float(v) for k, v in w.items()}
        growth = float(np.log(max(float(result.v.iloc[-1] / result.v.iloc[0]), 1e-12)))
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=1, research_methods=[
            {"kind": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}])
    return A.packet(SYSTEM, bundle, trials=1, research_methods=[
        {"kind": "portfolio_evidence", "challenger": "cvxportfolio SinglePeriodOptimization",
         "gamma_risk": GAMMA, "weights_evidence": weights, "log_growth_in_sample": growth,
         "n_bars": n, "authority": "none: a challenger's view of diversification; the "
                                   "allocator proof decides fractions by dE[log W]"}])


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
