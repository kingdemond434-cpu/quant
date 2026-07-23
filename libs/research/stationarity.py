"""Cointegration / stationarity tests and GARCH volatility — thin wrappers over statsmodels + arch.

The constitution bans hand-rolled ADF/GARCH: a subtly-wrong stationarity test admits a spurious
stat-arb card (gold-silver / pairs style), which is exactly the leak this desk exists to catch. So
rather than own these, we defer to the battle-tested references and keep only a thin, typed seam.

Optional dependency (kept out of the core install): ``pip install -e ".[stats]"``. Each function
raises :class:`StatsBackendMissing` with the exact remedy if its backend is absent, so a lean core
install still imports this module fine — the cost lands only when a stat-arb card is actually built.
"""

from __future__ import annotations

import numpy as np

_REMEDY = "install the optional extra: pip install -e '.[stats]'"


class StatsBackendMissing(RuntimeError):
    """Raised when an optional statistics backend (statsmodels / arch) is not installed."""


def adf_pvalue(series: np.ndarray) -> float:
    """Augmented Dickey-Fuller p-value. H0 = a unit root (non-stationary); a low p-value (<0.05)
    rejects it — evidence the series is stationary. AIC-selected lag order."""
    try:
        from statsmodels.tsa.stattools import adfuller
    except ImportError as exc:  # pragma: no cover
        raise StatsBackendMissing(f"statsmodels missing; {_REMEDY}") from exc
    return float(adfuller(np.asarray(series, dtype="float64"), autolag="AIC")[1])


def engle_granger_pvalue(y: np.ndarray, x: np.ndarray) -> float:
    """Engle-Granger cointegration p-value for ``y`` on ``x``. A low p-value (<0.05) is evidence the
    pair is cointegrated (a stationary linear combination exists) — the precondition for a pairs /
    stat-arb card."""
    try:
        from statsmodels.tsa.stattools import coint
    except ImportError as exc:  # pragma: no cover
        raise StatsBackendMissing(f"statsmodels missing; {_REMEDY}") from exc
    return float(coint(np.asarray(y, dtype="float64"), np.asarray(x, dtype="float64"))[1])


def garch_conditional_vol(returns: np.ndarray, *, p: int = 1, q: int = 1) -> np.ndarray:
    """Fitted conditional volatility series from a GARCH(``p``, ``q``) on ``returns`` (same length).

    Returns per-period conditional standard deviations in the units of ``returns``. Use for a
    volatility-regime / vol-targeting input where a rolling std is too naive."""
    try:
        from arch import arch_model
    except ImportError as exc:  # pragma: no cover
        raise StatsBackendMissing(f"arch missing; {_REMEDY}") from exc
    r = np.asarray(returns, dtype="float64")
    res = arch_model(r, vol="GARCH", p=p, q=q, mean="Zero", rescale=False).fit(disp="off")
    return np.asarray(res.conditional_volatility, dtype="float64")
