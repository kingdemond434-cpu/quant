"""Cross-sleeve structure for the allocator: factor risk model, neutralisation, diversification
multiplier, crowding, and the walk-forward proof that decides whether any of them earns capital.

    GAP_MAP rows built here (2026-11-13, "money-path organs" cluster):
      * Risk model and factor neutralisation (Barra users, DE Shaw, CN shops)
      * Forecast/instrument diversification multiplier (Carver, AHL, Winton)
      * H6 CROWDING AWARENESS
      * Random-matrix cleaning before the allocator solve  (the cleaner is libs/portfolio/rmt.py;
        its out-of-sample proof is here)

THE FACTOR MODEL. A Barra-style model is exposures x factor covariance + specific risk. The desk's
"assets" are sleeves (strategies), not stocks, so exposures are estimated by time-series
regression of each sleeve's daily R on observable FACTOR RETURNS built from the desk's own bars
(`style_factors`): USD strength, global equity risk, gold, oil, the JPY safe haven, and the three
public style premia every CTA and carry fund holds -- trend (time-series momentum, Moskowitz-Ooi-
Pedersen 2012), carry (Koijen-Moskowitz-Pedersen-Vrugt 2018) and short-term reversal. The
regression is exponentially weighted (half-life 126 days) and ridge-stabilised; the t-statistics
use Newey-West standard errors because sleeve returns are autocorrelated. Residuals give specific
variance; the factor covariance is the EWMA covariance of the factor returns.

NEUTRALISATION. A book's factor exposure is B'w. A DE Shaw / Barra-optimiser book is
neutralised against factors it is not paid for: here, against every factor whose book exposure is
significant AND whose factor return the book has no measured edge in. The neutral book is the
Euclidean projection of the heat vector onto {w >= 0, B_S' w = 0} (Dykstra alternating
projections), rescaled to the same total heat -- the heat law is untouched; only its direction
moves.

DIVERSIFICATION MULTIPLIER. Carver's IDM/FDM is 1/sqrt(w' rho w): at fixed per-sleeve risk, a
book of independent sleeves has lower total risk than the sum, and a vol-targeting desk scales up
by exactly that factor. Here it is measured on the CLEANED correlation (a sample rho understates
correlation in its noise modes and overstates the multiplier) and turned into the heat the book
could carry at the floor's ex-ante risk, capped at the 30% ceiling -- a two-sided capital modifier
(Rule 2: a genuinely diversified book is allowed more heat).

CROWDING (H6). Four measured signals per sleeve, each a published number with its own basis:
    style_r2        share of the sleeve's variance the public style premia explain (a sleeve that
                    IS trend or carry is in the most crowded trades in the world)
    comomentum      Lou-Polk (2013): the family's average pairwise RESIDUAL correlation over the
                    last 63 days, as a z-score against its own trailing year. Crowded arbitrage
                    shows up as excess co-movement among the strategies trading it
    cot_pressure    CFTC non-commercial net position z-score (3y) for the sleeve's market, signed
                    by whether the sleeve trades WITH the speculative crowd (its weekly R
                    correlates positively with the change in net speculative position)
    unwind_beta     the sleeve's mean R on the worst 5% days of the trend+carry style factors:
                    what it loses when the crowd de-levers
They combine into one crowding z per sleeve (mean of the available standardised signals).

THE PROOF (GROWTH_GOVERNANCE Rule 1). Nothing above takes capital authority because it sounds
institutional. `walk_forward` re-estimates every variant on a trailing window at each rebalance,
holds the book out of sample, and compares DAILY LOG GROWTH against the baseline with a paired
Newey-West t: ADOPT only when the 90% lower bound of the mean daily log-growth difference is above
zero, REJECT when the upper bound is below zero, INCONCLUSIVE otherwise, UNMEASURED with too few
out-of-sample days. A risk-reducing variant that does not raise log growth is REJECT, never
"safer".
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

HALFLIFE_D = 126
RIDGE = 1e-3
NW_LAG = 5
#: Heat law (CLAUDE.md, GROWTH GOVERNANCE): 20% floor, 30% ceiling.
HEAT_FLOOR = 0.20
HEAT_CEILING = 0.30
#: Carver's cap on any diversification multiplier.
DM_CAP = 2.5
#: Two-sided crowding tilt strength: weight x exp(-KAPPA x crowd_z). Stated, not fitted.
CROWD_KAPPA = 0.25
#: The proof's acceptance band.
PROOF_Z = 1.645
MIN_OOS_DAYS = 120

# ---------------------------------------------------------------------------- style factors
USD_BASE_LONG = ("USDJPY", "USDCHF", "USDCAD", "USDSEK", "USDNOK", "USDSGD", "USDMXN", "USDZAR")
USD_QUOTE = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")
EQUITY = ("US500", "SPX500", "SP500", "US30", "US100", "NAS100", "USTEC", "GER40", "DE40",
          "UK100", "JP225", "JPN225", "EU50", "STOXX50", "HK50", "AUS200")
GOLD = ("XAUUSD",)
OIL = ("XTIUSD", "USOIL", "WTI", "XBRUSD", "UKOIL", "BRENT")
JPY_CROSSES = ("USDJPY", "EURJPY", "AUDJPY", "GBPJPY", "CADJPY", "NZDJPY", "CHFJPY")
TREND_LOOKBACK = 60
REVERSAL_LOOKBACK = 5


def _pick(closes: pd.DataFrame, names: Sequence[str]) -> list[str]:
    cols = {c.upper(): c for c in closes.columns}
    out = []
    for n in names:
        for k, c in cols.items():
            if k == n or k.startswith(n + ".") or k.startswith(n + "_"):
                out.append(c)
                break
    return out


def style_factors(closes: pd.DataFrame, carry_sign: Mapping[str, int] | None = None
                  ) -> pd.DataFrame:
    """Daily factor returns from daily closes (index = dates, columns = symbols). A factor whose
    inputs are absent is simply not built; nothing is imputed."""
    lr = np.log(closes.astype(float)).diff()
    out: dict[str, pd.Series] = {}
    longs, quotes = _pick(closes, USD_BASE_LONG), _pick(closes, USD_QUOTE)
    if longs or quotes:
        parts = [lr[c] for c in longs] + [-lr[c] for c in quotes]
        out["usd"] = pd.concat(parts, axis=1).mean(axis=1, skipna=True)
    for name, group in (("equity", EQUITY), ("gold", GOLD), ("oil", OIL)):
        cols = _pick(closes, group)
        if cols:
            out[name] = lr[cols].mean(axis=1, skipna=True)
    jpy = _pick(closes, JPY_CROSSES)
    if jpy:
        out["jpy_haven"] = -lr[jpy].mean(axis=1, skipna=True)
    vol = lr.ewm(halflife=20, min_periods=20).std().shift(1)
    z = lr / vol.replace(0.0, np.nan)
    # trend: sign of the trailing 60-day return times today's vol-scaled return, across markets
    mom = lr.rolling(TREND_LOOKBACK, min_periods=TREND_LOOKBACK // 2).sum().shift(1)
    if lr.shape[1] >= 3:
        out["trend"] = (np.sign(mom) * z).mean(axis=1, skipna=True) * 0.01
        rev = lr.rolling(REVERSAL_LOOKBACK, min_periods=REVERSAL_LOOKBACK).sum().shift(1)
        out["reversal"] = (-np.sign(rev) * z).mean(axis=1, skipna=True) * 0.01
    if carry_sign:
        cs = {c: int(carry_sign[k]) for k in carry_sign for c in _pick(closes, (k,))
              if int(carry_sign[k]) != 0}
        if cs:
            out["carry"] = pd.concat([z[c] * s for c, s in cs.items()], axis=1).mean(
                axis=1, skipna=True) * 0.01
    f = pd.DataFrame(out)
    return f.dropna(how="all")


# ---------------------------------------------------------------------------- regression
def _ew_weights(n: int, halflife: float = HALFLIFE_D) -> np.ndarray:
    lam = 0.5 ** (1.0 / max(halflife, 1.0))
    w: np.ndarray = lam ** np.arange(n - 1, -1, -1, dtype=float)
    out: np.ndarray = w / w.sum()
    return out


def newey_west_se(x: np.ndarray, resid: np.ndarray, xtx_inv: np.ndarray, lag: int = NW_LAG
                  ) -> np.ndarray:
    """HAC standard errors (Bartlett kernel) for an OLS fit."""
    u = x * resid[:, None]
    s = u.T @ u
    for k in range(1, lag + 1):
        g = u[k:].T @ u[:-k]
        s += (1.0 - k / (lag + 1.0)) * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv
    return np.sqrt(np.clip(np.diag(cov), 0.0, None))


@dataclass
class Exposure:
    beta: dict[str, float]
    t: dict[str, float]
    alpha: float
    r2: float
    specific_var: float
    n: int


def exposures(sleeves: pd.DataFrame, factors: pd.DataFrame, *, min_obs: int = 120,
              halflife: float = HALFLIFE_D, ridge: float = RIDGE) -> dict[str, Exposure]:
    """EW ridge time-series regression of each sleeve on the factors, per sleeve on its own
    overlapping days; NW t-stats from the unweighted OLS on the same days."""
    out: dict[str, Exposure] = {}
    fac = factors.astype(float)
    names = list(fac.columns)
    for s in sleeves.columns:
        df = pd.concat([sleeves[s].rename("_y"), fac], axis=1, join="inner").dropna()
        if len(df) < min_obs or not names:
            continue
        y = df["_y"].to_numpy(float)
        x = np.column_stack([np.ones(len(df)), df[names].to_numpy(float)])
        w = _ew_weights(len(df), halflife)
        xw = x * w[:, None]
        xtwx = x.T @ xw
        # Ridge scaled to the factors' own weighted second moment, never on the intercept.
        reg = ridge * float(np.mean(np.diag(xtwx)[1:])) * np.eye(x.shape[1])
        reg[0, 0] = 0.0
        b = np.linalg.solve(xtwx + reg, xw.T @ y)
        resid = y - x @ b
        try:
            xtx_inv = np.linalg.inv(x.T @ x + np.eye(x.shape[1]) * 1e-12)
            b_ols = xtx_inv @ (x.T @ y)
            se = newey_west_se(x, y - x @ b_ols, xtx_inv)
            t = np.where(se > 0, b_ols / np.where(se > 0, se, 1.0), 0.0)
        except np.linalg.LinAlgError:
            t = np.zeros(x.shape[1])
        ybar = float((w * y).sum())
        sst = float((w * (y - ybar) ** 2).sum())
        sse = float((w * resid ** 2).sum())
        out[str(s)] = Exposure(
            beta={n: float(b[i + 1]) for i, n in enumerate(names)},
            t={n: float(t[i + 1]) for i, n in enumerate(names)},
            alpha=float(b[0]), r2=float(max(0.0, 1.0 - sse / sst)) if sst > 0 else 0.0,
            specific_var=sse, n=len(df))
    return out


def factor_cov(factors: pd.DataFrame, halflife: float = HALFLIFE_D) -> np.ndarray:
    f = factors.dropna().to_numpy(float)
    if f.shape[0] < 3:
        return np.eye(factors.shape[1]) * 1e-6
    w = _ew_weights(f.shape[0], halflife)
    mu = (w[:, None] * f).sum(axis=0)
    d = f - mu
    c: np.ndarray = (d * w[:, None]).T @ d
    sym: np.ndarray = 0.5 * (c + c.T)
    return sym


def risk_decomposition(book: Mapping[str, float], exp: Mapping[str, Exposure],
                       fcov: np.ndarray, names: Sequence[str]) -> dict[str, Any]:
    """Ex-ante variance of the book split into factor and specific parts, with each factor's
    share by Euler allocation (x_f (F x)_f / var), where x = B'w."""
    held = [k for k in book if k in exp and book[k] > 0]
    if not held:
        return {"status": "UNMEASURED", "why": "no held sleeve has a fitted exposure"}
    w = np.array([book[k] for k in held], dtype=float)
    b = np.array([[exp[k].beta.get(n, 0.0) for n in names] for k in held])
    x = b.T @ w
    fvar = float(x @ fcov @ x)
    svar = float((w ** 2 * np.array([exp[k].specific_var for k in held])).sum())
    tot = fvar + svar
    contrib = x * (fcov @ x)
    return {"status": "MEASURED", "held_with_exposure": len(held), "held_total": len(book),
            "book_exposure": {n: round(float(x[i]), 6) for i, n in enumerate(names)},
            "factor_share": round(fvar / tot, 4) if tot > 0 else None,
            "specific_share": round(svar / tot, 4) if tot > 0 else None,
            "by_factor_share": {n: round(float(contrib[i] / tot), 4) if tot > 0 else None
                                for i, n in enumerate(names)}}


# ---------------------------------------------------------------------------- neutralisation
def neutralise(w: np.ndarray, a: np.ndarray, *, iters: int = 500, tol: float = 1e-10
               ) -> np.ndarray:
    """Euclidean projection of `w` onto {v >= 0, a' v = 0} (a is N x K) by Dykstra's algorithm,
    rescaled to the original total. An infeasible system (no non-negative neutral book with any
    weight) returns `w` unchanged -- a book that cannot be neutralised is reported, not zeroed."""
    w = np.asarray(w, dtype=float)
    a = np.atleast_2d(np.asarray(a, dtype=float))
    if a.shape[0] != w.size:
        a = a.T
    total = float(w.sum())
    if a.size == 0 or total <= 0:
        return w.copy()
    q, _ = np.linalg.qr(a)
    x = w.copy()
    p = np.zeros_like(x)
    r = np.zeros_like(x)
    for _ in range(iters):
        y = x + p
        y_aff = y - q @ (q.T @ y)
        p = y - y_aff
        z = y_aff + r
        x_new = np.clip(z, 0.0, None)
        r = z - x_new
        if np.linalg.norm(x_new - x) < tol:
            x = x_new
            break
        x = x_new
    if x.sum() <= 1e-12 or np.linalg.norm(a.T @ x) > 1e-4 * max(1.0, np.linalg.norm(a.T @ w)):
        return w.copy()
    out: np.ndarray = x * total / x.sum()
    return out


# ---------------------------------------------------------------------------- diversification
def diversification_multiplier(corr: np.ndarray, w: np.ndarray, cap: float = DM_CAP) -> float:
    w = np.clip(np.asarray(w, dtype=float), 0.0, None)
    if w.sum() <= 0:
        return 1.0
    w = w / w.sum()
    d = float(w @ corr @ w)
    return 1.0 if d <= 0 else float(min(cap, max(1.0, 1.0 / math.sqrt(d))))


def idm_heat(corr: np.ndarray, w: np.ndarray, floor: float = HEAT_FLOOR,
             ceiling: float = HEAT_CEILING) -> tuple[float, float]:
    """(dm, heat): the multiplier on the given matrix and the total heat that carries the floor's
    ex-ante risk at that diversification, inside [floor, ceiling]."""
    dm = diversification_multiplier(corr, w)
    return dm, float(min(ceiling, max(floor, floor * dm)))


# ---------------------------------------------------------------------------- crowding
def family_of(name: str) -> str:
    toks = [t for t in str(name).replace(".", "_").split("_") if t]
    return toks[1].lower() if len(toks) > 1 else "unknown"


def symbol_of(name: str) -> str:
    low = str(name).lower()
    if low.startswith(("gold_", "xau_")):
        return "XAUUSD"
    return str(name).replace(".", "_").split("_")[0].upper()


def comomentum(resid: pd.DataFrame, fam: Mapping[str, str], window: int = 63,
               history: int = 252) -> dict[str, dict[str, float | None]]:
    """Per family: average pairwise residual correlation over the last `window` days, and its
    z-score against the same statistic on non-overlapping windows of the trailing `history`."""
    out: dict[str, dict[str, float | None]] = {}
    groups: dict[str, list[str]] = {}
    for s in resid.columns:
        groups.setdefault(fam.get(str(s), "unknown"), []).append(str(s))
    for f, cols in groups.items():
        if len(cols) < 3:
            continue
        sub = resid[cols]

        def avg_corr(block: pd.DataFrame) -> float | None:
            c = block.dropna(axis=1, thresh=max(10, int(0.6 * len(block)))).corr(min_periods=10)
            if c.shape[0] < 3:
                return None
            iu = np.triu_indices(c.shape[0], 1)
            v = c.to_numpy()[iu]
            v = v[np.isfinite(v)]
            return float(v.mean()) if v.size else None

        now = avg_corr(sub.iloc[-window:])
        past = [avg_corr(sub.iloc[e - window:e])
                for e in range(len(sub) - window, max(window, len(sub) - history) - 1, -window)
                if e - window >= 0 and e < len(sub)]
        past_v = [p for p in past if p is not None]
        z = None
        if now is not None and len(past_v) >= 3:
            sd = float(np.std(past_v, ddof=1))
            z = (now - float(np.mean(past_v))) / sd if sd > 0 else None
        out[f] = {"members": len(cols), "avg_resid_corr": None if now is None else round(now, 4),
                  "z": None if z is None else round(z, 3)}
    return out


COT_MAP = {"AUD": "aud", "CAD": "cad", "CHF": "chf", "GBP": "gbp", "JPY": "jpy", "NZD": "nzd",
           "EUR": "eur", "MXN": "mxn", "XAU": "gold", "NAS": "nasdaq100", "USTEC": "nasdaq100",
           "US100": "nasdaq100", "DXY": "dxy", "USDX": "dxy"}


def cot_series(cot: pd.DataFrame) -> pd.Series:
    """Weekly non-commercial net position as a share of open interest."""
    df = cot.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], utc=True)
    net = (df["noncomm_positions_long_all"] - df["noncomm_positions_short_all"]) / \
        df["open_interest_all"].replace(0, np.nan)
    return pd.Series(net.to_numpy(float), index=df["report_date"]).sort_index().dropna()


def cot_pressure(sleeve: pd.Series, net: pd.Series, sign: int = 1,
                 years: int = 3) -> dict[str, Any]:
    """Is the sleeve riding an extended speculative crowd?

    z      latest non-commercial net share of open interest against `years` of history, in
           FUTURES space (positive = speculators unusually long the future)
    align  correlation of the sleeve's weekly R with the weekly CHANGE in that net: positive =
           the sleeve makes money when speculators add to the futures long, i.e. it trades with
           the crowd -- whichever side of the symbol that is
    pressure = z x sign(align): large positive = the sleeve sits with an extended crowd (the
           unwind risk), negative = it sits against one (it is the liquidity provider)

    The mapping does not need the symbol's quote side, because both z and align live in futures
    space; `sign` (-1 when the symbol quotes the COT currency on the base side, e.g. USDJPY for the
    JPY future) only orients the reported `crowd_side_on_symbol`."""
    if net.size < 52:
        return {"z": None, "align": None, "pressure": None, "crowd_side_on_symbol": None}
    hist = net.iloc[-52 * years:]
    sd = float(hist.std(ddof=1))
    z = (float(hist.iloc[-1]) - float(hist.mean())) / sd if sd > 0 else None
    s = sleeve.copy()
    s.index = pd.to_datetime(s.index, utc=True)
    wk = s.resample("W-TUE").sum(min_count=1)
    j = pd.concat([wk.rename("r"), net.diff().rename("d")], axis=1, join="inner").dropna()
    align = float(j["r"].corr(j["d"])) if len(j) >= 26 else None
    if align is not None and not math.isfinite(align):
        align = None
    pressure = None if z is None or align is None else float(z * np.sign(align))
    side = None if z is None else ("long" if sign * z > 0 else "short")
    return {"z": None if z is None else round(z, 3),
            "align": None if align is None else round(align, 3),
            "pressure": None if pressure is None else round(pressure, 3),
            "crowd_side_on_symbol": side}


def unwind_beta(sleeve: pd.Series, style: pd.Series, q: float = 0.05) -> float | None:
    j = pd.concat([sleeve.rename("r"), style.rename("f")], axis=1, join="inner").dropna()
    if len(j) < 100:
        return None
    cut = j["f"].quantile(q)
    tail = j.loc[j["f"] <= cut, "r"]
    sd = float(j["r"].std(ddof=1))
    return None if tail.empty or sd <= 0 else round(float(tail.mean()) / sd, 4)


def crowding_z(rows: Mapping[str, Mapping[str, float | None]]) -> dict[str, float]:
    """Standardise each signal across sleeves and average what each sleeve has. A sleeve with no
    signal reads 0 (no evidence of crowding is not evidence of its absence, and 0 = no tilt)."""
    keys = ("style_r2", "comomentum_z", "cot_pressure", "unwind_loss")
    cols: dict[str, dict[str, float]] = {k: {} for k in keys}
    for s, r in rows.items():
        for k in keys:
            v = r.get(k)
            if v is not None and math.isfinite(float(v)):
                cols[k][s] = float(v)
    zs: dict[str, list[float]] = {s: [] for s in rows}
    for _k, d in cols.items():
        if len(d) < 3:
            continue
        arr = np.array(list(d.values()))
        mu, sd = float(arr.mean()), float(arr.std(ddof=1))
        if sd <= 0:
            continue
        for s, x in d.items():
            zs[s].append((x - mu) / sd)
    return {s: (float(np.mean(v)) if v else 0.0) for s, v in zs.items()}


def crowd_tilt(w: np.ndarray, cz: np.ndarray, kappa: float = CROWD_KAPPA) -> np.ndarray:
    """Two-sided: crowded sleeves lose weight, uncrowded ones gain, total unchanged."""
    w = np.asarray(w, dtype=float)
    t = w * np.exp(-kappa * np.clip(np.asarray(cz, dtype=float), -3.0, 3.0))
    out: np.ndarray = t * (w.sum() / t.sum()) if t.sum() > 0 else w.copy()
    return out


# ---------------------------------------------------------------------------- the proof
def kelly_direction(mu: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Long-only Sigma^-1 mu by projected iteration (clip negatives, re-solve on the support)."""
    n = mu.size
    sup = np.ones(n, dtype=bool)
    w = np.zeros(n)
    for _ in range(n):
        if not sup.any():
            break
        sub = np.linalg.solve(cov[np.ix_(sup, sup)] + 1e-12 * np.eye(int(sup.sum())), mu[sup])
        w = np.zeros(n)
        w[sup] = sub
        if (sub >= -1e-15).all():
            break
        sup &= w > 0
    return np.clip(w, 0.0, None)


def scale_to(w: np.ndarray, total: float) -> np.ndarray:
    s = float(np.clip(w, 0.0, None).sum())
    if s <= 0:
        return np.zeros_like(w)
    out: np.ndarray = np.clip(w, 0.0, None) * total / s
    return out


@dataclass
class Variant:
    name: str
    basis: str
    #: (train T x N with NaN, context) -> (heat vector, total heat)
    build: Callable[[np.ndarray, dict[str, Any]], np.ndarray]


def paired_verdict(d: np.ndarray, z: float = PROOF_Z, lag: int = NW_LAG,
                   min_days: int = MIN_OOS_DAYS) -> dict[str, Any]:
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    if d.size < min_days:
        return {"verdict": "UNMEASURED", "oos_days": int(d.size),
                "why": f"{d.size} out-of-sample days < {min_days}"}
    mu = float(d.mean())
    u = d - mu
    s = float(u @ u) / d.size
    for k in range(1, lag + 1):
        s += 2.0 * (1.0 - k / (lag + 1.0)) * float(u[k:] @ u[:-k]) / d.size
    se = math.sqrt(max(s, 0.0) / d.size)
    lo, hi = mu - z * se, mu + z * se
    verdict = "ADOPT" if lo > 0 else ("REJECT" if hi < 0 else "INCONCLUSIVE")
    return {"verdict": verdict, "oos_days": int(d.size),
            "delta_elog_daily": mu, "delta_elog_annual": mu * 252,
            "se_daily": se, "t": (mu / se) if se > 0 else None,
            "ci90_daily": [lo, hi]}


@dataclass
class ProofResult:
    rebalances: int
    oos_days: int
    by_variant: dict[str, dict[str, Any]] = field(default_factory=dict)
    gmv_oos_var: dict[str, float] = field(default_factory=dict)


def walk_forward(panel: pd.DataFrame, variants: Sequence[Variant], baseline: str, *,
                 train: int = 250, step: int = 21, min_sleeves: int = 5,
                 context: dict[str, Any] | None = None, budget_s: float | None = None,
                 clock: Callable[[], float] | None = None,
                 cov_builders: Mapping[str, Callable[[np.ndarray], np.ndarray]] | None = None,
                 ) -> ProofResult:
    """Out-of-sample daily log growth per variant on `panel` (dates x sleeves, R per unit heat,
    NaN = sleeve not trading that day, counted as 0 out of sample). Each rebalance uses only the
    `train` days before it; the book is held for `step` days.

    `cov_builders` (name -> train -> covariance) adds the covariance-quality test the RMT
    literature uses: the fully-invested minimum-variance book is built on each estimate and its
    REALISED out-of-sample variance recorded. Lower is a better covariance, independent of any
    mean forecast -- the cleanest test of a cleaner, reported beside the growth verdicts."""
    import time as _time
    clk = clock or _time.monotonic
    t0 = clk()
    x = panel.to_numpy(float)
    n_days = x.shape[0]
    logs: dict[str, list[float]] = {v.name: [] for v in variants}
    gmv: dict[str, list[float]] = {}
    rebal = 0
    for start in range(train, n_days - 1, step):
        if budget_s is not None and clk() - t0 > budget_s:
            break
        tr = x[start - train:start]
        live = np.isfinite(tr).sum(axis=0) >= max(60, train // 3)
        if live.sum() < min_sleeves:
            continue
        tr = tr[:, live]
        te = np.nan_to_num(x[start:start + step][:, live], nan=0.0)
        ctx = dict(context or {})
        ctx["columns"] = [str(c) for c, ok in zip(panel.columns, live, strict=True) if ok]
        ctx["train_index"] = panel.index[start - train:start]
        books: dict[str, np.ndarray] = {}
        for v in variants:
            try:
                books[v.name] = v.build(tr, ctx)
            except (np.linalg.LinAlgError, ValueError, FloatingPointError):
                books[v.name] = np.full(int(live.sum()), np.nan)
        if any(not np.isfinite(b).all() for b in books.values()):
            continue
        rebal += 1
        for name, b in books.items():
            r = te @ b
            logs[name].extend(np.log1p(np.clip(r, -0.95, None)).tolist())
        for kind, fn in (cov_builders or {}).items():
            try:
                cov = fn(tr)
                wv = np.linalg.solve(cov + 1e-12 * np.eye(cov.shape[0]), np.ones(cov.shape[0]))
                if wv.sum() == 0 or not np.isfinite(wv).all():
                    continue
                wv = wv / wv.sum()
                gmv.setdefault(kind, []).append(float(np.mean((te @ wv) ** 2)))
            except (np.linalg.LinAlgError, ValueError):
                continue
    res = ProofResult(rebalances=rebal, oos_days=len(logs.get(baseline, [])))
    base = np.array(logs.get(baseline, []))
    for v in variants:
        arr = np.array(logs[v.name])
        row: dict[str, Any] = {"basis": v.basis,
                               "elog_annual": float(arr.mean() * 252) if arr.size else None,
                               "oos_days": int(arr.size)}
        if v.name != baseline and arr.size == base.size:
            row.update(paired_verdict(arr - base))
        elif v.name == baseline:
            row["verdict"] = "BASELINE"
        res.by_variant[v.name] = row
    res.gmv_oos_var = {k: float(np.mean(v)) for k, v in gmv.items() if v}
    return res
