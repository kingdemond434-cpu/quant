"""Growth-optimal (Kelly) leverage analysis -- optimize geometric CAGR, not Sharpe.

For a daily net-return stream this computes, across a leverage ladder, the *geometric* growth and
its costs: CAGR, annual vol, max drawdown, and a bootstrapped risk-of-ruin. It finds the
growth-optimal (Kelly) leverage -- the point where ``E[log(1 + L*r)]`` peaks, after which volatility
drag destroys compounding -- and the robust fractional-Kelly recommendation.

Honesty: Kelly leverage assumes the edge estimate is TRUE. On an unvalidated edge (in-sample, fails
DSR) the realized edge is almost surely lower, so full Kelly over-levers and risks ruin. The
recommended size is therefore *fractional* Kelly, and only after forward validation. Pure functions;
realistic -- the input returns must already be net of spread/swap/commission/financing/slippage.
"""

from __future__ import annotations

import numpy as np

LADDER: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)


def ann_geom_growth(returns: np.ndarray, leverage: float, ppy: float = 252.0) -> float:
    """Annualized geometric growth ``ppy * E[log(1 + L*r)]`` (-inf if a path is wiped out)."""
    x = 1.0 + leverage * np.asarray(returns, dtype="float64")
    if np.any(x <= 0.0):
        return float("-inf")                       # a single >100% loss day => ruin
    return float(np.mean(np.log(x)) * ppy)


def cagr(returns: np.ndarray, leverage: float, ppy: float = 252.0) -> float:
    g = ann_geom_growth(returns, leverage, ppy)
    return -1.0 if not np.isfinite(g) else float(np.exp(g) - 1.0)


def max_drawdown(returns: np.ndarray, leverage: float) -> float:
    eq = np.cumprod(1.0 + leverage * np.asarray(returns, dtype="float64"))
    if np.any(eq <= 0.0):
        return -1.0
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1.0).min())


def risk_of_ruin(
    returns: np.ndarray,
    leverage: float,
    *,
    horizon: int = 252,
    threshold: float = 0.2,
    n_paths: int = 1500,
    seed: int = 0,
) -> float:
    """Bootstrapped P(equity falls below ``threshold`` within ``horizon`` days) at this leverage.

    IID resample of the realized non-zero daily returns (preserves the fat tails); ``threshold=0.2``
    means an 80% drawdown is treated as ruin. Conservative and assumption-light.
    """
    a = np.asarray(returns, dtype="float64")
    a = a[a != 0.0]
    if len(a) < 20:
        return float("nan")
    rng = np.random.default_rng(seed)
    paths = rng.choice(a, size=(n_paths, horizon), replace=True)
    eq = np.cumprod(1.0 + leverage * paths, axis=1)
    return float(np.mean(eq.min(axis=1) < threshold))


def kelly_optimal(returns: np.ndarray, *, cap: float = 10.0, points: int = 200) -> float:
    """Growth-optimal leverage = argmax of geometric growth on a fine grid (capped)."""
    grid = np.linspace(0.0, cap, points + 1)[1:]
    growths = np.array([ann_geom_growth(returns, float(g), 1.0) for g in grid])
    if not np.any(np.isfinite(growths)) or np.nanmax(growths) <= 0.0:
        return 0.0
    return float(grid[int(np.nanargmax(growths))])


def leverage_ladder(
    returns: np.ndarray,
    *,
    ppy: float = 252.0,
    ladder: tuple[float, ...] = LADDER,
    ruin_threshold: float = 0.2,
) -> list[dict[str, float]]:
    return [
        {
            "leverage": L,
            "cagr": round(cagr(returns, L, ppy), 4),
            "ann_vol": round(float(np.std(returns) * L * np.sqrt(ppy)), 4),
            "max_dd": round(max_drawdown(returns, L), 4),
            "risk_of_ruin": round(risk_of_ruin(returns, L, threshold=ruin_threshold), 4),
        }
        for L in ladder
    ]


def _skew(returns: np.ndarray) -> float:
    a = np.asarray(returns, dtype="float64")
    a = a[a != 0.0]
    if len(a) < 8 or a.std() == 0:
        return 0.0
    return float(np.mean(((a - a.mean()) / a.std()) ** 3))


def analyze(
    returns: np.ndarray,
    *,
    ppy: float = 252.0,
    kelly_fraction: float = 0.5,
    governance_cap: float = 1.0,
) -> dict[str, object]:
    """Full growth-optimal vs aggressive leverage report for one return stream.

    ``kelly_fraction`` is the robust de-rating (default half-Kelly); ``governance_cap`` is an
    absolute leverage ceiling from risk policy (the recommendation is the min of the two).
    """
    kelly = kelly_optimal(returns, cap=10.0)
    recommended = min(kelly * kelly_fraction, governance_cap)
    aggressive = min(kelly * 2.0, 10.0)            # 2x Kelly: the over-bet that ruins compounding

    def row(label: str, lev: float) -> dict[str, object]:
        return {
            "label": label, "leverage": round(lev, 2),
            "cagr": round(cagr(returns, lev, ppy), 4),
            "ann_vol": round(float(np.std(returns) * lev * np.sqrt(ppy)), 4),
            "max_dd": round(max_drawdown(returns, lev), 4),
            "risk_of_ruin": round(risk_of_ruin(returns, lev), 4),
        }

    return {
        "skew": round(_skew(returns), 3),
        "growth_optimal_leverage": round(kelly, 2),
        "recommended_leverage": round(recommended, 2),
        "ladder": leverage_ladder(returns, ppy=ppy),
        "points": {
            "growth_optimal": row("growth-optimal (full Kelly)", kelly),
            "recommended": row(f"recommended ({kelly_fraction:g}x Kelly, capped)", recommended),
            "aggressive": row("aggressive (2x Kelly)", aggressive),
        },
    }
