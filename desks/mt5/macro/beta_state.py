"""UPGRADED BETA -- conditional (up/down) beta, tail dependence, cointegration and regime beta.

WHY (DATA-22, the BETA row). `market_state.betas` measured one number per instrument: a 63-day
OLS beta of the daily return to US500's. A single beta hides the three things a book actually
pays for: whether the co-movement is ASYMMETRIC (an instrument that falls with the index but does
not rise with it is a worse diversifier than its average beta says), whether it CONCENTRATES IN
THE TAILS (the 5% days are the days a diversified book stops being diversified), and whether the
two price LEVELS are tied (a cointegrated pair mean-reverts in spread, a merely correlated one
does not). And none of them is constant across the risk regime.

WHAT EACH NUMBER IS, per instrument against the benchmark (US500), on daily UTC closes:

    up_beta, down_beta     OLS beta on the days the benchmark rose / fell (window WINDOW days);
                           beta_asym = down_beta - up_beta (> 0: falls harder than it rises)
    lower_tail, upper_tail empirical co-exceedance P(y <= q_y | x <= q_x) at q = TAIL_Q, and the
                           mirror at 1 - TAIL_Q. Independence reads TAIL_Q; perfect dependence 1.
                           A tail with fewer than MIN_TAIL_HITS benchmark exceedances is
                           UNMEASURED, never a zero
    coint_*                Engle-Granger two-step on LOG prices: OLS hedge ratio, then an ADF
                           (one lagged difference, no constant) on the residual. The t is read
                           against MacKinnon's two-variable constant-term critical values
                           (EG_CRIT); half_life = -ln 2 / ln(1 + phi) when phi < 0; resid_z is
                           the newest residual's z against the window's residuals
    regime_beta            beta inside each risk regime of the PERMITTED own-bars state
                           (`market_state.own_regime`'s key, libs.data.own_risk), each day's
                           return conditioned on the regime known at the PRIOR close; a regime
                           with fewer than REGIME_MIN_DAYS days is UNMEASURED

PIT. A day's close is knowable at the next UTC midnight (the last H1 bar of the day closes then);
the lake series stamps exactly that, and nothing dated after `now` is read.

SOURCE. The desk's own MT5 bars only (`mt5:bars`, admitted by the terms gate). Cells go through
`sensor_engines.emit_conditioner_cells`; this module never sizes and never names a direction.
"""
from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np

UNMEASURED = "UNMEASURED"
DATA_SOURCE = "mt5:bars"
BENCH = "US500"
WINDOW = 252
TAIL_Q = 0.05
MIN_TAIL_HITS = 10
MIN_SIDE_DAYS = 20
REGIME_MIN_DAYS = 30
TRAIL = 252
#: Days of rolling state written to the lake series (each day = one window ending that day).
ROLL_DAYS = 500
#: MacKinnon (2010) asymptotic critical values, Engle-Granger residual ADF, N=2, constant term.
EG_CRIT: dict[str, float] = {"1%": -3.90, "5%": -3.34, "10%": -3.04}
SIGNALS = ("beta_asym", "coint_resid_z")
ENGINE = "beta_state"


def _un(why: str) -> dict[str, Any]:
    return {"status": UNMEASURED, "why": why}


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None or not math.isfinite(x) else round(float(x), nd)


def ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float] | None:
    """(alpha, beta) of y on x; None when x has no variance."""
    if x.size < 3:
        return None
    mx, my = float(x.mean()), float(y.mean())
    vx = float(((x - mx) ** 2).sum())
    if vx <= 0:
        return None
    b = float(((x - mx) * (y - my)).sum()) / vx
    return my - b * mx, b


def conditional_beta(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    up, dn = x > 0, x < 0
    out: dict[str, Any] = {"n_up": int(up.sum()), "n_down": int(dn.sum())}
    for name, m in (("up_beta", up), ("down_beta", dn)):
        fit = ols(x[m], y[m]) if int(m.sum()) >= MIN_SIDE_DAYS else None
        out[name] = _r(fit[1]) if fit else None
    out["beta_asym"] = (_r(out["down_beta"] - out["up_beta"])
                        if out["down_beta"] is not None and out["up_beta"] is not None else None)
    if out["beta_asym"] is None:
        out["why"] = f"fewer than {MIN_SIDE_DAYS} up or down benchmark days"
    return out


def tail_dependence(x: np.ndarray, y: np.ndarray, q: float = TAIL_Q) -> dict[str, Any]:
    """Empirical co-exceedance at the q and 1-q quantiles of each margin."""
    out: dict[str, Any] = {"q": q}
    if x.size < 3:
        return {**out, "lower_tail": None, "upper_tail": None, "why": "no sample"}
    qx_lo, qy_lo = np.quantile(x, q), np.quantile(y, q)
    qx_hi, qy_hi = np.quantile(x, 1 - q), np.quantile(y, 1 - q)
    lo, hi = x <= qx_lo, x >= qx_hi
    out["n_lower"], out["n_upper"] = int(lo.sum()), int(hi.sum())
    out["lower_tail"] = (_r(float((y[lo] <= qy_lo).mean()))
                         if lo.sum() >= MIN_TAIL_HITS else None)
    out["upper_tail"] = (_r(float((y[hi] >= qy_hi).mean()))
                         if hi.sum() >= MIN_TAIL_HITS else None)
    if out["lower_tail"] is None or out["upper_tail"] is None:
        out["why"] = f"fewer than {MIN_TAIL_HITS} benchmark exceedances in a tail"
    out["independence"] = q
    return out


def engle_granger(ly: np.ndarray, lx: np.ndarray) -> dict[str, Any]:
    """Two-step Engle-Granger on log prices: hedge ratio, residual ADF t, half-life, resid z."""
    if ly.size < 60:
        return _un(f"{ly.size} common days < 60")
    fit = ols(lx, ly)
    if fit is None:
        return _un("benchmark log price has no variance")
    a, b = fit
    e = ly - a - b * lx
    de = np.diff(e)
    # ADF with one lagged difference, no constant (the residual is mean zero by construction)
    dy, e1, d1 = de[1:], e[1:-1], de[:-1]
    X = np.column_stack([e1, d1])
    try:
        coef, *_ = np.linalg.lstsq(X, dy, rcond=None)
    except np.linalg.LinAlgError:
        return _un("ADF regression is singular")
    resid = dy - X @ coef
    dof = dy.size - X.shape[1]
    s2 = float(resid @ resid) / dof if dof > 0 else float("nan")
    try:
        cov = s2 * np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return _un("ADF regression is singular")
    phi = float(coef[0])
    se = math.sqrt(float(cov[0, 0])) if cov[0, 0] > 0 else float("nan")
    t = phi / se if se and math.isfinite(se) else float("nan")
    band = next((k for k, c in EG_CRIT.items() if math.isfinite(t) and t < c), ">10%")
    hl = (-math.log(2) / math.log(1 + phi)) if -1 < phi < 0 else None
    sd = float(e.std(ddof=1))
    return {"status": "MEASURED", "hedge_ratio": _r(b), "adf_t": _r(t), "p_band": band,
            "cointegrated_5pct": bool(math.isfinite(t) and t < EG_CRIT["5%"]),
            "phi": _r(phi, 6), "half_life_days": _r(hl, 2),
            "resid_z": _r(float(e[-1] - e.mean()) / sd) if sd > 0 else None,
            "n": int(ly.size), "critical_values": EG_CRIT}


# ============================================================================== regimes (PIT)
def _pct(hist: Sequence[float], x: float) -> float | None:
    if len(hist) < 20:
        return None
    return (sum(1 for v in hist if v < x) + 0.5 * sum(1 for v in hist if v == x)) / len(hist)


def regime_by_day(own: Mapping[str, Sequence[tuple[str, float]]]) -> dict[str, str]:
    """Each day's own-bars regime key, computed with only that day's and earlier values: the
    same key `market_state.own_regime` gives as of that day's close."""
    level = list(own.get("OWN_VIX") or [])
    flag = dict(own.get("OWN_VIX_INVERTED") or [])
    out: dict[str, str] = {}
    for i, (d, v) in enumerate(level):
        if i < 20 or d not in flag:
            continue
        shape = "backwardation" if flag[d] > 0.5 else "contango"
        pct = _pct([x for _, x in level[max(0, i - TRAIL):i]], v)
        tier = ("" if pct is None else "_low" if pct < 1 / 3 else
                "_high" if pct > 2 / 3 else "_mid")
        out[d] = f"vol_{shape}{tier}"
    return out


def regime_betas(days: Sequence[str], x: np.ndarray, y: np.ndarray,
                 regimes: Mapping[str, str]) -> dict[str, Any]:
    """Beta inside each regime; a return on day d is keyed by the regime at the prior close."""
    if not regimes:
        return _un("no own-bars regime series on this host (libs.data.own_risk archive absent)")
    keyed: dict[str, list[int]] = {}
    known = sorted(regimes)
    for i, d in enumerate(days):
        j = bisect.bisect_left(known, d) - 1          # strictly before d: the prior close
        if j >= 0:
            keyed.setdefault(regimes[known[j]], []).append(i)
    out: dict[str, Any] = {}
    for key, idx in sorted(keyed.items()):
        if len(idx) < REGIME_MIN_DAYS:
            out[key] = {"status": UNMEASURED, "n": len(idx),
                        "why": f"{len(idx)} days < {REGIME_MIN_DAYS}"}
            continue
        fit = ols(x[idx], y[idx])
        out[key] = {"status": "MEASURED", "n": len(idx), "beta": _r(fit[1]) if fit else None}
    return out or _un("no day of the window has a prior-close regime")


# ============================================================================== per symbol
def _align(bench: Sequence[tuple[str, float]], sym: Sequence[tuple[str, float]]
           ) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Common days with both closes, then (days[1:], log bench, log sym) on those days."""
    b, s = dict(bench), dict(sym)
    days = sorted(set(b) & set(s))
    lb = np.log(np.asarray([b[d] for d in days], dtype=float))
    ls = np.log(np.asarray([s[d] for d in days], dtype=float))
    return days, lb, ls


def window_state(days: Sequence[str], lb: np.ndarray, ls: np.ndarray,
                 regimes: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Every upgraded-beta number on one aligned window of log closes."""
    x, y = np.diff(lb), np.diff(ls)
    rdays = list(days[1:])
    fit = ols(x, y)
    out: dict[str, Any] = {"status": "MEASURED", "first_day": days[0], "last_day": days[-1],
                           "n_returns": int(x.size), "beta": _r(fit[1]) if fit else None,
                           "conditional": conditional_beta(x, y),
                           "tail": tail_dependence(x, y),
                           "cointegration": engle_granger(ls, lb)}
    if regimes is not None:
        out["regime_beta"] = regime_betas(rdays, x, y, regimes)
    return out


def symbol_state(bench: Sequence[tuple[str, float]], sym: Sequence[tuple[str, float]],
                 regimes: Mapping[str, str] | None = None, window: int = WINDOW
                 ) -> dict[str, Any]:
    days, lb, ls = _align(bench, sym)
    if len(days) < window + 1:
        return _un(f"{len(days)} common days with the benchmark < {window + 1}")
    out = window_state(days[-window - 1:], lb[-window - 1:], ls[-window - 1:])
    # the regime beta reads the whole common history: a regime is visited a few weeks a year
    if regimes is not None:
        out["regime_beta"] = regime_betas(days[1:], np.diff(lb), np.diff(ls), regimes)
        out["regime_beta_window_days"] = len(days) - 1
    return out


def available_time(day: str) -> str:
    d = date.fromisoformat(day[:10]) + timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=UTC).isoformat()


def rolling_rows(bench: Sequence[tuple[str, float]], sym: Sequence[tuple[str, float]], *,
                 now: datetime, window: int = WINDOW, roll_days: int = ROLL_DAYS
                 ) -> list[dict[str, Any]]:
    """One lake row per day: the state of the window ENDING that day, stamped at the next UTC
    midnight. A row knowable after `now` is never written."""
    days, lb, ls = _align(bench, sym)
    rows: list[dict[str, Any]] = []
    start = max(window, len(days) - roll_days)
    for end in range(start, len(days)):
        at = available_time(days[end])
        if datetime.fromisoformat(at) > now:
            continue
        sl = slice(end - window, end + 1)
        x, y = np.diff(lb[sl]), np.diff(ls[sl])
        cb = conditional_beta(x, y)
        eg = engle_granger(ls[sl], lb[sl])
        rows.append({"available_time": at, "event_time": days[end], "source_id": DATA_SOURCE,
                     "up_beta": cb["up_beta"], "down_beta": cb["down_beta"],
                     "beta_asym": cb["beta_asym"], "coint_resid_z": eg.get("resid_z"),
                     "coint_adf_t": eg.get("adf_t")})
    return rows


def series_id(symbol: str) -> str:
    return f"ws_beta_{symbol.lower()}"


def build(closes: Callable[[str], Sequence[tuple[str, float]]], symbols: Sequence[str], *,
          now: datetime, own: Mapping[str, Sequence[tuple[str, float]]] | None = None,
          bench: str = BENCH) -> dict[str, Any]:
    """The upgraded-beta block for MARKET_STATE.json. `closes(sym)` returns PIT daily closes."""
    b = list(closes(bench))
    regimes = regime_by_day(own) if own else {}
    out: dict[str, Any] = {"engine": ENGINE, "benchmark": bench, "window_days": WINDOW,
                           "tail_q": TAIL_Q, "data_source": DATA_SOURCE,
                           "regime_source": "mt5:bars:OWN_VIX (libs.data.own_risk)",
                           "regime_days": len(regimes), "symbols": {}}
    if len(b) < WINDOW + 1:
        out.update(_un(f"{len(b)} daily closes for {bench} < {WINDOW + 1}"))
        return out
    out["status"] = "MEASURED"
    for sym in symbols:
        out["symbols"][sym] = symbol_state(b, list(closes(sym)), regimes)
    return out


def emit(closes: Callable[[str], Sequence[tuple[str, float]]], block: Mapping[str, Any], *,
         now: datetime, dry_run: bool = False, lake_root: Any = None) -> list[dict[str, Any]]:
    """Lake series + cells for every MEASURED symbol, through the one terms-gated door."""
    from libs.research import sensor_engines as se
    out: list[dict[str, Any]] = []
    if block.get("status") != "MEASURED":
        return out
    b = list(closes(str(block.get("benchmark") or BENCH)))
    for sym, st in (block.get("symbols") or {}).items():
        if not isinstance(st, dict) or st.get("status") != "MEASURED":
            continue
        rows = rolling_rows(b, list(closes(sym)), now=now)
        sid = series_id(sym)
        info: dict[str, Any] = {"symbol": sym, "series_id": sid, "rows": len(rows)}
        if not dry_run and rows:
            info["lake"] = se.write_lake_series(sid, rows, root=lake_root)
        info["cells"] = se.emit_conditioner_cells(
            sid, list(SIGNALS), [sym],
            mechanism=(f"{sym} against {BENCH}: an instrument that falls with the index harder "
                       "than it rises (beta asymmetry) carries crash exposure its average beta "
                       "hides; a cointegrated pair's stretched residual mean-reverts"),
            falsifier="gate effect indistinguishable from the shuffled-state gate across the "
                      "judged cells", generator=ENGINE, sides=(1, -1), dry_run=dry_run,
            data_source=DATA_SOURCE)
        out.append(info)
    return out


def observations(block: Mapping[str, Any], received_at: datetime) -> list[Any]:
    """Sensor-ledger rows for the newest window of every MEASURED symbol."""
    from libs.research import sensor_contract as sc
    out: list[Any] = []
    for sym, st in (block.get("symbols") or {}).items():
        if not isinstance(st, dict) or st.get("status") != "MEASURED":
            continue
        at = available_time(str(st["last_day"]))
        if datetime.fromisoformat(at) > received_at:
            continue
        vals = {"up_beta": st["conditional"].get("up_beta"),
                "down_beta": st["conditional"].get("down_beta"),
                "beta_asym": st["conditional"].get("beta_asym"),
                "lower_tail_dependence": st["tail"].get("lower_tail"),
                "upper_tail_dependence": st["tail"].get("upper_tail"),
                "coint_adf_t": st["cointegration"].get("adf_t"),
                "coint_half_life_days": st["cointegration"].get("half_life_days"),
                "coint_resid_z": st["cointegration"].get("resid_z")}
        for metric, v in vals.items():
            if not isinstance(v, int | float) or isinstance(v, bool):
                continue
            out.append(sc.make(sensor_class="market_state", kind="state",
                               sensor_id="market:beta_upgraded", source_id=DATA_SOURCE,
                               commercial_rights="own data", licence="the desk's own MT5 bars",
                               metric=metric, value=float(v), entity=sym,
                               asset_domain="cross_asset", event_time=st["last_day"],
                               knowable_at=at, knowable_basis="declared_lag",
                               received_at=received_at, parse_complete_at=received_at,
                               benchmark=block.get("benchmark")))
    return out
