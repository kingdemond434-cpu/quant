"""Cross-asset factor returns and per-sleeve loadings: a covariance that exists on day one.

THE DEFECT, MEASURED 2026-09-16 ON THE LIVE BOOK. The gateway logged `k_eff UNMEASURED: no
sleeve pair has 20 overlapping trading days yet (16 sleeves)` on every pass, and the allocator's
`_corr_abs` -- the redundancy charge that stops a heat budget being filled with five copies of
one dollar bet -- was ZERO for every pair of sleeves whose histories do not overlap. A scalp
clock born a fortnight ago and a certified sleeve born in 2018 have no common days, so the
optimiser was told they were independent, and `leg_balance` had to catch the resulting pile-up
one order at a time at the venue. A covariance that needs OVERLAP is blind for the first month
of every new sleeve, which is exactly the month the desk most needs it to see.

A FACTOR MODEL NEEDS NO OVERLAP. Each sleeve's returns are regressed, on its OWN days only,
against a factor history that exists for every day since 2018: the currency legs (`libs.risk.
fx_factors` decomposition, so a long-EURCHF sleeve loads on +EUR and -CHF), the metals, and two
cross-asset macro factors (the daily change in VIX and in the 10-year). Two sleeves are then
correlated through the factors they share -- `cov(i, j) = b_i' F b_j` -- whether or not they
ever traded on the same day. This is the Barra/APT construction every institutional risk model
uses (`libs.portfolio.factor_model.FactorRiskModel` already carries the algebra); what was
missing was the FACTOR RETURNS for this universe and the LOADINGS for these sleeves, and this
module is those two things.

RIDGE, RESTRICTED TO THE SLEEVE'S OWN LEGS. A fortnight of returns cannot identify loadings on
thirty factors, so the regression sees only the factors the sleeve can structurally carry -- its
two currency legs (or metal plus quote currency) and the two macro factors -- and shrinks them
toward zero with `K_PRIOR` pseudo-observations. At n=13 days about 40% of the least-squares
loading survives; at n=250 nearly all of it. The whitened loading `u = L' b` (with `F = L L'`)
is what `SleeveEvidence.factor_load` carries, so a dot product of two sleeves' loadings IS their
factor covariance and `robust_elog._corr_abs` needs no factor matrix at all.

WHAT THIS IS NOT. It is not a return forecast and it sizes nothing by itself. It supplies the
STRUCTURE of the covariance that the redundancy charge and the growth objective already consume;
where realised co-movement is measured on enough common days, `_corr_abs` still prefers it.
"""
from __future__ import annotations

import math
import os
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
UNIVERSE = ROOT / "desks" / "mt5" / "data" / "universe"
CACHE = ROOT / "desks" / "mt5" / "data" / "pf_allocator_cache" / "factor_returns.parquet"
CACHE_MAX_AGE_S = float(os.environ.get("LEG_FACTORS_CACHE_S", str(6 * 3600)))

#: Pseudo-observations of the zero-loading prior in the ridge. 20 days: a sleeve needs about
#: three weeks of its own history before its loadings are mostly its own.
K_PRIOR = float(os.environ.get("LEG_FACTORS_K_PRIOR", "20"))
#: A currency needs this many quoted pairs before its leg return is a factor rather than one
#: pair's noise. ILS/INR/THB have one pair each and are dropped; the sleeve on them keeps only
#: its other leg and the macro factors.
MIN_PAIRS = 3
#: The cross-asset macro factors, as daily CHANGES of the FRED series (the state module uses the
#: LEVELS; a factor return must be a return).
MACRO_FACTORS: dict[str, tuple[str, str]] = {"d_vix": ("VIXCLS", "dlog"),
                                             "d_r10": ("DGS10", "diff")}


@dataclass(frozen=True)
class FactorSet:
    """The factor history, standardised, with the Cholesky root of its correlation."""

    names: tuple[str, ...]
    #: date string -> row index into `values`
    index: dict[str, int]
    #: (T, K) standardised factor returns (unit variance over the full history)
    values: np.ndarray
    #: (K, K) lower-triangular L with L L' = corr(values) + jitter
    chol: np.ndarray
    sd: np.ndarray
    note: str = ""

    @property
    def n_days(self) -> int:
        return int(self.values.shape[0])


@dataclass(frozen=True)
class Loadings:
    """One sleeve's whitened loadings and what is left over."""

    load: np.ndarray
    resid_var: float
    n: int
    used: tuple[str, ...]
    betas: dict[str, float] = field(default_factory=dict)
    explained: float = 0.0
    why: str = ""


# ------------------------------------------------------------------------------ factor returns
def _pair_daily_logret(path: Path) -> Any:
    import pandas as pd

    df = pd.read_parquet(path, columns=["close"])
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    s = pd.Series(df["close"].to_numpy(dtype=float), index=idx).dropna()
    s = s[~s.index.isna()].sort_index()
    if s.empty:
        return None
    daily = s.groupby(s.index.date).last()
    daily = daily[daily > 0]
    if daily.size < 3:
        return None
    r = np.log(daily).diff().dropna()
    r.index = [d.isoformat() for d in r.index]
    return r


def _macro_changes(archive: Path | None) -> dict[str, Any]:
    import pandas as pd

    from libs.portfolio.macro_state import _load_archive
    series, _newest = _load_archive(archive)         # None -> the long archive when present
    out: dict[str, Any] = {}
    for name, (sid, how) in MACRO_FACTORS.items():
        rows = series.get(sid)
        if not rows:
            continue
        s = pd.Series([v for _, v in rows], index=[d for d, _ in rows], dtype=float)
        s = s[~s.index.duplicated(keep="last")]
        if how == "dlog":
            s = s[s > 0]
            ch = np.log(s).diff()
        else:
            ch = s.diff()
        ch = ch.dropna()
        if ch.size:
            out[name] = ch
    return out


def daily_factor_returns(universe: Path = UNIVERSE, archive: Path | None = None, *,
                         cache: Path | None = CACHE, max_age_s: float = CACHE_MAX_AGE_S) -> Any:
    """(T, K) DataFrame of daily factor returns indexed by 'YYYY-MM-DD', or None.

    Currency legs are the MEAN signed daily log return of every quoted pair containing the
    currency (+ when it is the base, - when the quote): a basket return, which is what "the
    euro went up today" means once it is not measured against one counterparty. Metals are
    booked the way `fx_factors.decompose` books them. The result is cached for `max_age_s`
    because 120 parquet reads are a few seconds the five-minute clock should not pay twice.
    """
    import pandas as pd

    if cache is not None and cache.exists() and time.time() - cache.stat().st_mtime < max_age_s:
        try:
            return pd.read_parquet(cache)
        except (OSError, ValueError):
            pass
    try:
        from libs.risk.fx_factors import _NON_CURRENCY, split_pair
    except ImportError:
        return None
    if not universe.is_dir():
        return None
    legs: dict[str, list[Any]] = {}
    for path in sorted(universe.glob("*_H1.parquet")):
        sym = path.name[: -len("_H1.parquet")]
        pair = split_pair(sym)
        if pair is None:
            continue
        try:
            r = _pair_daily_logret(path)
        except (OSError, ValueError, KeyError):
            continue
        if r is None:
            continue
        base, quote = pair
        legs.setdefault(base, []).append(r)
        legs.setdefault(quote, []).append(-r)
    cols: dict[str, Any] = {}
    for ccy, parts in legs.items():
        if len(parts) < MIN_PAIRS and ccy not in _NON_CURRENCY:
            continue
        cols[ccy] = pd.concat(parts, axis=1).mean(axis=1)
    if not cols:
        return None
    frame = pd.DataFrame(cols).sort_index()
    for name, ch in _macro_changes(archive).items():
        # A day with no print is a day the factor did not move, for a CHANGE series: 0.0 is the
        # honest fill at portfolio level. Outside the archive's span the column is NaN and the
        # regression drops those days for the macro factors only (see `fit_loadings`).
        frame[name] = ch.reindex(frame.index)
        first, last = ch.index.min(), ch.index.max()
        inside = (frame.index >= first) & (frame.index <= last)
        frame.loc[inside, name] = frame.loc[inside, name].fillna(0.0)
    frame = frame.dropna(how="all")
    if cache is not None:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(cache)
        except (OSError, ValueError):
            pass
    return frame


def factor_set(frame: Any) -> FactorSet | None:
    """Standardise the factor history and take the Cholesky root of its correlation."""
    if frame is None or len(frame) < 30:
        return None
    names = tuple(str(c) for c in frame.columns)
    raw = frame.to_numpy(dtype=float)
    filled = np.where(np.isfinite(raw), raw, 0.0)
    sd = np.nanstd(raw, axis=0, ddof=1)
    sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)
    z = filled / sd[None, :]
    corr = np.corrcoef(z, rowvar=False)
    corr = np.asarray(np.nan_to_num(corr, nan=0.0), dtype=float)
    np.fill_diagonal(corr, 1.0)
    try:
        chol = np.linalg.cholesky(corr + 1e-6 * np.eye(len(names)))
    except np.linalg.LinAlgError:
        # Repair a non-PD estimate the standard way: clip eigenvalues and re-root.
        w, v = np.linalg.eigh(corr)
        corr = (v * np.maximum(w, 1e-6)) @ v.T
        chol = np.linalg.cholesky(corr + 1e-6 * np.eye(len(names)))
    index = {str(d)[:10]: i for i, d in enumerate(frame.index)}
    return FactorSet(names=names, index=index, values=z, chol=chol, sd=sd,
                     note=f"{len(names)} factors over {len(index)} days")


def _own_factors(symbol: str, names: Sequence[str]) -> list[str]:
    """The factors this symbol can structurally carry: its legs plus the macro factors."""
    try:
        from libs.risk.fx_factors import split_pair
        pair = split_pair(symbol)
    except ImportError:
        pair = None
    out: list[str] = []
    if pair is not None:
        out.extend(c for c in pair if c in names)
    out.extend(m for m in MACRO_FACTORS if m in names and m not in out)
    return out


def fit_loadings(r: np.ndarray, dates: Iterable[Any], fs: FactorSet, symbol: str, *,
                 k_prior: float = K_PRIOR) -> Loadings:
    """Ridge loadings of one sleeve on the factors it can carry, on its own days only.

    NaN days of `r` (the sleeve did not exist) are dropped, never zero-filled -- the same rule
    `SleeveEvidence.own_r` enforces. A day the factor history does not cover is dropped too.
    """
    a = np.asarray(r, dtype=float)
    days = [str(d)[:10] for d in dates]
    k = len(fs.names)
    empty = Loadings(load=np.zeros(k), resid_var=float(np.nanvar(a)) if a.size else 0.0, n=0,
                     used=(), why="")
    if a.size != len(days):
        return Loadings(**{**empty.__dict__, "why": f"{a.size} returns vs {len(days)} dates"})
    use = _own_factors(symbol, fs.names)
    if not use:
        return Loadings(**{**empty.__dict__, "why": f"{symbol}: no factor it can carry"})
    cols = [fs.names.index(c) for c in use]
    rows: list[int] = []
    ys: list[float] = []
    for v, d in zip(a, days, strict=True):
        if not math.isfinite(v):
            continue
        j = fs.index.get(d)
        if j is None:
            continue
        if not np.all(np.isfinite(fs.values[j, cols])):
            continue
        rows.append(j)
        ys.append(float(v))
    n = len(rows)
    if n < 3:
        return Loadings(**{**empty.__dict__, "n": n, "used": tuple(use),
                           "why": f"{n} usable day(s) on the factor calendar"})
    x = fs.values[np.asarray(rows), :][:, cols]                     # (n, p)
    y = np.asarray(ys, dtype=float)
    y_c = y - y.mean()
    p = len(cols)
    beta = np.linalg.solve(x.T @ x + float(k_prior) * np.eye(p), x.T @ y_c)
    resid = y_c - x @ beta
    resid_var = float(resid.var(ddof=1)) if n > 2 else float(resid.var())
    resid_var = max(resid_var, 1e-12)
    b_full = np.zeros(k)
    b_full[cols] = beta
    load = fs.chol.T @ b_full                                        # u'u = b' corr b
    fvar = float(load @ load)
    return Loadings(load=load, resid_var=resid_var, n=n, used=tuple(use),
                    betas={c: round(float(b), 6) for c, b in zip(use, beta, strict=True)},
                    explained=round(fvar / (fvar + resid_var), 4) if fvar + resid_var > 0 else 0.0,
                    why=f"{n} days on {len(use)} factor(s), k_prior={k_prior:g}")


def factor_corr_abs(loads: Sequence[np.ndarray | None],
                    resid_var: Sequence[float]) -> np.ndarray:
    """|corr| implied by the loadings alone, 0 wherever either side has none."""
    n = len(loads)
    out = np.zeros((n, n))
    ok = [i for i, u in enumerate(loads) if u is not None and np.asarray(u).size]
    if not ok:
        np.fill_diagonal(out, 1.0)
        return out
    k = max(np.asarray(loads[i]).size for i in ok)
    m = np.zeros((len(ok), k))
    for row, i in enumerate(ok):
        u = np.asarray(loads[i], dtype=float)
        m[row, : u.size] = u
    g = m @ m.T
    d = np.diag(g) + np.array([max(0.0, float(resid_var[i])) for i in ok])
    den = np.sqrt(np.outer(d, d))
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(den > 0, np.abs(g) / den, 0.0)
    for row, i in enumerate(ok):
        for col, j in enumerate(ok):
            out[i, j] = min(1.0, float(c[row, col]))
    np.fill_diagonal(out, 1.0)
    return out
