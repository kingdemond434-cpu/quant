"""Two more allocator inputs for the out-of-sample re-test: VIX own-risk and GARCH volatility.

BACKLOG (2026-10-06 growth allocator overhaul): "VIXCLS -> own_risk consumers". The VIX was
collected (`macro_state` dim `risk`) and read by a per-ORDER lean (`mt5desk.macro_view`), the
kernel tilt and the factor frame. Nothing let it move the desk's OWN RISK BELIEF, meaning the
share of crisis worlds the book is scored against. BACKLOG (2026-10-27): "constantly maximise
the allocator: every input re-tested, winners promoted, losers off (HMM, macro, GARCH, ...)".
GARCH had no arm.

Both are pure functions of data up to an as-of day, so `research.input_ablation` can replay
them walk-forward exactly as a live pass would have seen them.

VIX OWN-RISK (`vix_crisis_share`). The crisis share is a BELIEF about how often the book's worst
days come. It is not a rail. This module asks the book's own history the question directly:

    crisis day   a day whose equal-weight book return is in the bottom `base` quantile of the
                 history (so the unconditional crisis rate is `base` by construction)
    predictor    the VIX rank tercile of the PREVIOUS calendar day (VIXCLS prints after the US
                 close; a lag of one day keeps it point-in-time on every venue clock)
    belief       P(crisis | today's tercile) under a Beta prior centred on `base` carrying ONE
                 crisis day of weight (`1 / base` pseudo-days), so a thin tercile says little

The share is `base * lift`, where lift = posterior / base. It is TWO-SIDED (Auditor, 2026-11-11;
GROWTH_GOVERNANCE: every capital modifier is two-sided): a high-VIX tercile with a measured crisis
rate above base raises the share, and a calm tercile with a measured rate below base LOWERS it,
with the same Beta prior both ways. It is clipped to [`crisis_share_min(base)`,
`latent_factors.CRISIS_SHARE_MAX`], the floor being the cap mirrored in log space around base.
A tercile with fewer than `MIN_STATE_DAYS` history days changes nothing, and says so.

GARCH VOLATILITY (`garch_vol_ratio`). A Gaussian QMLE GARCH(1,1) per sleeve, variance-targeted
(omega = s2 * (1 - a - b)), forecasting the mean variance over the next `horizon` days. The input
is the ratio sqrt(forecast / sample variance). The arm rescales each sleeve's deviations around
its own mean by that ratio, so the solver sees the volatility the sleeve is expected to have
next week rather than its lifetime average. The mean is untouched. Under `MIN_GARCH_OBS`
observations, or on a fit that does not converge to a stationary process, the ratio is None
and the sleeve is left as it is.

Neither function holds any authority. `input_ablation` measures them, and `pf_allocator` reads
the verdict.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

import numpy as np

from libs.portfolio.latent_factors import CRISIS_SHARE_MAX

#: Days of history a VIX tercile needs before it may move the belief. 20 is the desk's standing
#: minimum state sample (`black_litterman.MIN_STATE_DAYS`, `STATE_ADMISSION`).
MIN_STATE_DAYS = 20
#: Tercile edges, the same as `macro_state.LOW_EDGE / HIGH_EDGE`.
LOW_EDGE, HIGH_EDGE = 1.0 / 3.0, 2.0 / 3.0
#: Observations a GARCH(1,1) fit needs. About 100 is the usual floor for a stable a+b estimate.
MIN_GARCH_OBS = 100
#: Persistence ceiling. At a+b >= 1 the process is integrated and the variance target is void.
MAX_PERSISTENCE = 0.999


def _tercile(rank: float) -> str:
    return "low" if rank < LOW_EDGE else "high" if rank >= HIGH_EDGE else "mid"


def _prev_day(d: str) -> str:
    return (date.fromisoformat(d[:10]) - timedelta(days=1)).isoformat()


def crisis_share_min(base: float) -> float:
    """The floor of the two-sided share: the cap mirrored around `base` in log space,
    base^2 / CRISIS_SHARE_MAX (derived: 0.06^2 / 0.35 = 0.0103 at the standing 6% share), so the
    VIX can move the share by the same multiple down as up."""
    b = float(base)
    return min(b, b * b / CRISIS_SHARE_MAX) if b > 0 else 0.0


def vix_crisis_share(book_r: Sequence[float], dates: Sequence[str],
                     vix_rank: Mapping[str, float], asof: str, base: float,
                     ) -> tuple[float, dict[str, Any]]:
    """The crisis-world share the VIX argues for as of `asof`, and why. Two-sided."""
    base = float(base)
    diag: dict[str, Any] = {"base": base, "asof": str(asof)[:10]}
    if base <= 0.0:
        return base, {**diag, "status": "UNMEASURED", "why": "standing share is zero"}
    today = vix_rank.get(str(asof)[:10])
    if today is None or not math.isfinite(float(today)):
        return base, {**diag, "status": "UNMEASURED", "why": "no VIX rank on the as-of day"}
    r = np.asarray(book_r, dtype=float)
    ok = np.isfinite(r)
    if ok.sum() < MIN_STATE_DAYS:
        return base, {**diag, "status": "UNMEASURED", "why": f"{int(ok.sum())} book days"}
    cut = float(np.quantile(r[ok], base))
    want = _tercile(float(today))
    n = k = 0
    for d, x in zip(dates, r, strict=True):
        if not math.isfinite(x):
            continue
        prev = vix_rank.get(_prev_day(str(d)))
        if prev is None or not math.isfinite(float(prev)) or _tercile(float(prev)) != want:
            continue
        n += 1
        k += int(x <= cut)
    diag.update(tercile=want, vix_rank=round(float(today), 4), days=n, crisis_days=k,
                crisis_cut=round(cut, 8))
    if n < MIN_STATE_DAYS:
        return base, {**diag, "status": "UNMEASURED",
                      "why": f"{n} history days in the {want} tercile; {MIN_STATE_DAYS} needed"}
    prior_n = 1.0 / base                        # one crisis day of prior weight, centred on base
    post = (k + base * prior_n) / (n + prior_n)
    floor = crisis_share_min(base)
    share = min(max(floor, post), CRISIS_SHARE_MAX)
    diag.update(status="MEASURED", posterior=round(post, 6), lift=round(share / base, 4),
                share=round(share, 6), floor=round(floor, 6),
                why=(f"{k}/{n} crisis days after a {want}-VIX day -> P(crisis)={post:.3f} vs "
                     f"standing {base:.3f}; two-sided, clipped to [{floor:.4f}, "
                     f"{CRISIS_SHARE_MAX}]"))
    return share, diag


def _garch_nll(params: np.ndarray, e: np.ndarray, s2: float) -> float:
    a, b = float(params[0]), float(params[1])
    if a < 0 or b < 0 or a + b >= MAX_PERSISTENCE:
        return 1e12
    w = s2 * (1.0 - a - b)
    h = np.empty_like(e)
    h[0] = s2
    for t in range(1, e.size):
        h[t] = w + a * e[t - 1] ** 2 + b * h[t - 1]
    if np.any(h <= 0) or not np.all(np.isfinite(h)):
        return 1e12
    return float(0.5 * np.sum(np.log(h) + e * e / h))


def garch_vol_ratio(r: Sequence[float], horizon: int = 5) -> tuple[float | None, dict[str, Any]]:
    """sqrt(mean forecast variance over `horizon` days / sample variance), or None."""
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < MIN_GARCH_OBS:
        return None, {"status": "UNMEASURED", "why": f"{x.size} obs; {MIN_GARCH_OBS} needed"}
    e = x - x.mean()
    s2 = float(e.var())
    if not s2 > 0:
        return None, {"status": "UNMEASURED", "why": "no variance"}
    from scipy.optimize import minimize
    best_fun, best_x = math.inf, np.zeros(2)
    for a0, b0 in ((0.05, 0.90), (0.10, 0.80), (0.02, 0.97)):
        res = minimize(_garch_nll, np.array([a0, b0]), args=(e, s2), method="Nelder-Mead",
                       options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 400})
        if float(res.fun) < best_fun:
            best_fun, best_x = float(res.fun), np.asarray(res.x, dtype=float)
    a, b = float(best_x[0]), float(best_x[1])
    if best_fun >= 1e12 or a < 0 or b < 0 or a + b >= MAX_PERSISTENCE:
        return None, {"status": "UNMEASURED", "why": "no stationary fit"}
    w = s2 * (1.0 - a - b)
    h = s2
    for t in range(1, e.size):
        h = w + a * e[t - 1] ** 2 + b * h
    h_next = w + a * e[-1] ** 2 + b * h
    p = a + b
    fc = [s2 + (p ** j) * (h_next - s2) for j in range(max(int(horizon), 1))]
    ratio = math.sqrt(max(float(np.mean(fc)), 0.0) / s2)
    return ratio, {"status": "MEASURED", "alpha": round(a, 5), "beta": round(b, 5),
                   "ratio": round(ratio, 5)}


def rescale(r: np.ndarray, ratio: float) -> np.ndarray:
    """Deviations around the sleeve's own (NaN-skipping) mean scaled by `ratio`; NaN stays NaN."""
    r = np.asarray(r, dtype=float)
    ok = np.isfinite(r)
    if not ok.any() or not math.isfinite(ratio) or ratio <= 0:
        return r
    m = float(r[ok].mean())
    return np.where(ok, m + (r - m) * float(ratio), r)
