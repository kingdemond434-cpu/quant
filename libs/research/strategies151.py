"""KAKUSHADZE & SERUR, "151 TRADING STRATEGIES" (2018, public SSRN paper) -- the desk's catalogue
of it, and its own numpy implementations of the strategies an MT5/Fusion CFD can carry.

WHAT THIS IS. The paper is a survey: options, stocks, ETFs, fixed income, indexes, volatility,
FX, commodities, futures, structured assets, convertibles, tax arbitrage, miscellaneous assets,
distressed assets, real estate, cash, cryptocurrencies, global macro and infrastructure. Every
strategy is a row of `CATALOGUE` with exactly one disposition:

  IMPLEMENTED   price-only on the desk's own bars, written here in desk code (time-series per
                symbol, or cross-sectional within the instrument's peer class from MetaTrader's
                registry), measured by the adapter and donated as a hypothesis for the gates
  UNMEASURED    applicable to an MT5 instrument, but the input it needs (swap/interest-rate
                differentials, a futures curve, COT positioning, years of history, a bond class
                large enough to rank) is not in the research bundle the adapter receives -- named,
                never approximated
  INAPPLICABLE  needs an instrument, market or act the desk cannot hold through MT5 CFDs
                (listed options, cash bonds, single-name fundamentals, OTC credit, real estate,
                tax status ...) or is a sizing / allocation rule, which is the allocator's
                authority and never a hypothesis -- each with its reason

THE CATALOGUE IS RECONSTRUCTED, NOT COPIED. It was written from the paper's section structure as
the desk knows it, without fetching the paper; strategy names are short descriptive labels in the
desk's words, and the row boundaries are the desk's (the paper's own numbering is not claimed).
Its size is whatever `len(CATALOGUE)` says, and the adapter reports the count against 151.

THE TWO-LANE ORDER. A time-series strategy is measured only on symbols `may_hypothesise` admits;
a cross-sectional strategy that maps to a class-book family (`CROSS_SECTIONAL_FAMILIES`) admits
share CFDs too, ranked within the `equity` peer class -- the principal's 2026-09-30 amendment and
nothing wider.

Every operator reads only the bar it is evaluated at and earlier; a test perturbs the future and
checks no past value moved. Nothing here sizes, ranks strategies against each other or approves.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from libs.research import formulaic_alphas as F

IMPLEMENTED = "IMPLEMENTED"
UNMEASURED = "UNMEASURED"
INAPPLICABLE = "INAPPLICABLE"
DISPOSITIONS = (IMPLEMENTED, UNMEASURED, INAPPLICABLE)
PAPER_COUNT = 151
#: Bars in a trading day on the H1 panel (a 24-hour FX day; indices print fewer, and their
#: windows count their OWN bars).
BARS_PER_DAY = 24


@dataclass(frozen=True)
class Row:
    """One strategy of the survey and what the desk does with it."""

    sid: str
    section: str
    name: str
    disposition: str
    why: str = ""
    kind: str = ""                     #: "ts" (per symbol), "xs" (within class), "pair"
    #: Time-series donation: the family + params when the measured association AGREES with the
    #: strategy's stated direction, and the mirror when it opposes it. Never chosen by strength.
    aligned: tuple[str, Mapping[str, Any]] | None = None
    mirror: tuple[str, Mapping[str, Any]] | None = None
    #: Cross-sectional: the desk's class-book family this strategy is an instance of ("" = none).
    desk_family: str = ""
    desk_params: Mapping[str, Any] = field(default_factory=dict)
    only_class: str = ""               #: restrict an xs strategy to one peer class


_OPT = "a listed-option structure: Fusion offers no options on any MT5 instrument"
_FUND = "needs single-name fundamentals (earnings, book value, analyst data) a CFD bar lacks"
_EQEV = "single-name event: the event lane owns it under the two-lane order, not a price hunt"
_SIZE = "a sizing / allocation rule: capital is the allocator's authority, never a hypothesis"
_CASHB = "needs cash bonds along one issuer's curve (coupons, maturities); a bond CFD is one point"
_OTC = "needs OTC credit / swap instruments the MT5 venue does not list"
_VOL = "needs VIX futures, volatility ETNs, variance swaps or options: no term structure on MT5"
_NONMKT = "not a market position the desk can take through MT5 CFDs"

_OPTIONS = (
    "covered call", "covered put", "protective put", "protective call", "bull call spread",
    "bull put spread", "bear call spread", "bear put spread", "long synthetic forward",
    "short synthetic forward", "long combo", "short combo", "bull call ladder",
    "bull put ladder", "bear call ladder", "bear put ladder", "calendar call spread",
    "calendar put spread", "diagonal call spread", "diagonal put spread", "long straddle",
    "long strangle", "long guts", "short straddle", "short strangle", "short guts",
    "long call synthetic straddle", "long put synthetic straddle",
    "short call synthetic straddle", "short put synthetic straddle", "covered short straddle",
    "covered short strangle", "strap", "strip", "call ratio backspread",
    "put ratio backspread", "ratio call spread", "ratio put spread", "long call butterfly",
    "modified call butterfly", "long put butterfly", "modified put butterfly",
    "short call butterfly", "short put butterfly", "long iron butterfly",
    "short iron butterfly", "long call condor", "long put condor", "short call condor",
    "short put condor", "long iron condor", "short iron condor", "long box", "collar",
    "bull call spread collar", "bear put spread collar",
)

_TF = "trend_ma_cross"
_MRB = "mean_reversion_bollinger"
_MRR = "mean_reversion_rsi"
_MOM = "momentum_volgate"
_RR = "range_reversion"
_LB = "level_breakout"
_XM = "cross_sectional_class_momentum"
_XR = "cross_sectional_class_reversal"
_XL = "cross_sectional_class_low_vol"


def _catalogue() -> tuple[Row, ...]:
    rows: list[Row] = [Row(f"opt.{i + 1:02d}", "options", n, INAPPLICABLE, _OPT)
                       for i, n in enumerate(_OPTIONS)]
    IM, U, X = IMPLEMENTED, UNMEASURED, INAPPLICABLE
    rows += [
        # ---- stocks, carried to MT5 classes (the cross-sectional books and per-symbol rules)
        Row("stk.price_momentum", "stocks", "price momentum (cross-sectional)", IM, kind="xs",
            desk_family=_XM, desk_params={"lookback_d": 20, "hold_d": 5, "dispersion": "any"}),
        Row("stk.earnings_momentum", "stocks", "earnings momentum", X, _EQEV),
        Row("stk.value", "stocks", "value (book-to-price)", X, _FUND),
        Row("stk.low_vol", "stocks", "low-volatility anomaly", IM, kind="xs", desk_family=_XL,
            desk_params={"measure": "vol", "window_d": 60, "hold_d": 5}),
        Row("stk.implied_vol", "stocks", "implied volatility", X, _OPT),
        Row("stk.multifactor", "stocks", "multifactor portfolio", X, _FUND),
        Row("stk.residual_momentum", "stocks", "residual momentum", IM, kind="xs",
            desk_family=_XM, desk_params={"lookback_d": 20, "hold_d": 5, "dispersion": "any"}),
        Row("stk.pairs", "stocks", "pairs trading", IM, kind="pair"),
        Row("stk.mr_single_cluster", "stocks", "mean-reversion, single cluster", IM, kind="xs",
            desk_family=_XR, desk_params={"lookback_d": 1, "hold_d": 1, "dispersion": "any"},
            only_class="*"),
        Row("stk.mr_multi_cluster", "stocks", "mean-reversion, multiple clusters", IM, kind="xs",
            desk_family=_XR, desk_params={"lookback_d": 1, "hold_d": 1, "dispersion": "any"}),
        Row("stk.mr_weighted_regression", "stocks", "mean-reversion, weighted regression", IM,
            kind="xs", desk_family=_XR,
            desk_params={"lookback_d": 1, "hold_d": 1, "dispersion": "any"}),
        Row("stk.single_ma", "stocks", "single moving average", IM, kind="ts",
            aligned=(_TF, {"fast_ema": 2, "slow_ema": 20}), mirror=(_MRB, {"bb_n": 20})),
        Row("stk.two_ma", "stocks", "two moving averages", IM, kind="ts",
            aligned=(_TF, {"fast_ema": 10, "slow_ema": 40}), mirror=(_MRB, {"bb_n": 40})),
        Row("stk.three_ma", "stocks", "three moving averages", IM, kind="ts",
            aligned=(_TF, {"fast_ema": 3, "slow_ema": 21}), mirror=(_MRB, {"bb_n": 21})),
        Row("stk.support_resistance", "stocks", "support and resistance (pivot)", IM, kind="ts",
            aligned=(_LB, {}), mirror=(_RR, {"range_n": 24})),
        Row("stk.channel", "stocks", "channel", IM, kind="ts",
            aligned=(_RR, {"range_n": 48}), mirror=(_MOM, {"mom_n": 48})),
        Row("stk.event_ma", "stocks", "event-driven M&A", X, _EQEV),
        Row("stk.knn", "stocks", "machine learning, single-symbol KNN", IM, kind="ts"),
        Row("stk.statarb_optimization", "stocks", "statistical arbitrage optimisation", X,
            _SIZE),
        Row("stk.market_making", "stocks", "market-making", X,
            "needs passive quoting against an order book; MT5 CFD execution takes the "
            "broker's quote"),
        Row("stk.alpha_combos", "stocks", "alpha combos", X,
            "fitting combination weights over many alphas is a selection the gauntlet and the "
            "allocator own; an unfitted combo would re-spend the same charged trials"),
        # ---- ETFs, carried to indices and classes
        Row("etf.sector_momentum", "etfs", "sector momentum rotation", IM, kind="xs",
            desk_family=_XM, desk_params={"lookback_d": 20, "hold_d": 5, "dispersion": "any"},
            only_class="index"),
        Row("etf.sector_momentum_ma", "etfs", "sector rotation with a moving-average filter", IM,
            kind="xs", desk_family=_XM,
            desk_params={"lookback_d": 20, "hold_d": 5, "dispersion": "any"},
            only_class="index"),
        Row("etf.dual_momentum", "etfs", "dual-momentum rotation", IM, kind="xs",
            desk_family=_XM, desk_params={"lookback_d": 20, "hold_d": 5, "dispersion": "any"}),
        Row("etf.alpha_rotation", "etfs", "alpha rotation", IM, kind="xs", desk_family=_XM,
            desk_params={"lookback_d": 20, "hold_d": 5, "dispersion": "any"}),
        Row("etf.r_squared", "etfs", "R-squared trend", IM, kind="ts",
            aligned=(_MOM, {"mom_n": 48}), mirror=(_MRR, {"rsi_n": 14})),
        Row("etf.mean_reversion", "etfs", "mean-reversion (internal bar strength)", IM,
            kind="ts", aligned=(_MRR, {"rsi_n": 2}), mirror=(_MOM, {"mom_n": 6})),
        Row("etf.leveraged", "etfs", "leveraged ETFs", X,
            "a leveraged ETF's daily rebalancing decay has no CFD analogue"),
        Row("etf.multi_asset_trend", "etfs", "multi-asset trend following", IM, kind="ts",
            aligned=(_TF, {"fast_ema": 5, "slow_ema": 100}), mirror=(_MRB, {"bb_n": 100})),
        # ---- fixed income
        Row("fi.bullets", "fixed_income", "bullets", X, _CASHB),
        Row("fi.barbells", "fixed_income", "barbells", X, _CASHB),
        Row("fi.ladders", "fixed_income", "ladders", X, _CASHB),
        Row("fi.immunization", "fixed_income", "bond immunisation", X, _CASHB),
        Row("fi.butterfly_dd", "fixed_income", "dollar-duration-neutral butterfly", X, _CASHB),
        Row("fi.butterfly_5050", "fixed_income", "fifty-fifty butterfly", X, _CASHB),
        Row("fi.butterfly_regression", "fixed_income", "regression-weighted butterfly", X,
            _CASHB),
        Row("fi.low_risk", "fixed_income", "low-risk factor across bonds", U,
            "the bond peer class has fewer members than MIN_CLASS_MEMBERS in the registry"),
        Row("fi.value", "fixed_income", "value factor across bonds", U,
            "needs yields against a fair-value model and a bond class large enough to rank"),
        Row("fi.carry", "fixed_income", "carry factor across bonds", U,
            "needs point-in-time yields/roll-down; the bundle carries prices only"),
        Row("fi.roll_down", "fixed_income", "rolling down the yield curve", X, _CASHB),
        Row("fi.curve_spread", "fixed_income", "yield-curve spread (flattener / steepener)", X,
            "needs two maturities of one issuer's curve; the venue lists single bond CFDs"),
        Row("fi.cds_basis", "fixed_income", "CDS basis arbitrage", X, _OTC),
        Row("fi.swap_spread", "fixed_income", "swap-spread arbitrage", X, _OTC),
        # ---- indexes
        Row("idx.cash_carry", "indexes", "cash-and-carry", X,
            "needs the index's constituent basket against its future; a CFD has neither leg"),
        Row("idx.dispersion", "indexes", "dispersion trading", X, _OPT),
        Row("idx.intraday_etf_arb", "indexes", "intraday arbitrage between index ETFs", X,
            "needs two listed products on one index; Fusion lists one CFD per index"),
        Row("idx.vol_targeting", "indexes", "index volatility targeting with a risk-free asset",
            X, _SIZE),
        # ---- volatility
        Row("vol.vix_basis", "volatility", "VIX futures basis", X, _VOL),
        Row("vol.etn_carry", "volatility", "volatility carry with two ETNs", X, _VOL),
        Row("vol.risk_premium", "volatility", "volatility risk premium", X, _VOL),
        Row("vol.skew", "volatility", "volatility skew (risk reversal)", X, _VOL),
        Row("vol.variance_swaps", "volatility", "variance swaps", X, _VOL),
        # ---- FX
        Row("fx.hp_ma", "fx", "moving averages of a (one-sided) HP-filtered price", IM,
            kind="ts", aligned=(_TF, {"fast_ema": 5, "slow_ema": 20}),
            mirror=(_MRB, {"bb_n": 20})),
        Row("fx.carry", "fx", "carry trade", U,
            "needs point-in-time interest differentials; the bundle carries no swap or rate "
            "series (the desk's cross_sectional_class_carry family reads them itself)"),
        Row("fx.dollar_carry", "fx", "dollar carry trade", U,
            "needs the average forward discount against USD at each date; not in the bundle"),
        Row("fx.momentum_carry", "fx", "momentum and carry combination", U,
            "the carry half needs rate differentials the bundle does not carry"),
        Row("fx.triangular", "fx", "triangular arbitrage", X,
            "needs simultaneous executable quotes on three pairs; H1 closes are not, and the "
            "spread exceeds the mispricing at retail latency"),
        # ---- commodities
        Row("cmd.roll_yield", "commodities", "roll yield", U,
            "needs the futures term structure; a CFD's financing is not its roll yield"),
        Row("cmd.hedging_pressure", "commodities", "hedging pressure", U,
            "needs COT positioning stamped at publication; not an axis of this bundle"),
        Row("cmd.diversification", "commodities", "portfolio diversification with commodities",
            X, _SIZE),
        Row("cmd.value", "commodities", "value (five-year reversal)", U,
            "needs about five years of history; the bundle carries at most 4000 H1 bars"),
        Row("cmd.skewness", "commodities", "skewness premium", IM, kind="xs",
            only_class="commodity"),
        Row("cmd.pricing_models", "commodities", "trading with pricing models", X,
            "needs a fundamental supply/demand model the desk does not have"),
        # ---- futures
        Row("fut.hedging", "futures", "hedging risk with futures", X, _SIZE),
        Row("fut.calendar_spread", "futures", "calendar spread", X,
            "needs two expiries of one contract; a CFD has one rolling price"),
        Row("fut.contrarian", "futures", "contrarian (mean-reversion) across contracts", IM,
            kind="xs", desk_family=_XR,
            desk_params={"lookback_d": 5, "hold_d": 3, "dispersion": "any"}),
        Row("fut.trend", "futures", "trend following (time-series momentum)", IM, kind="ts",
            aligned=(_MOM, {"mom_n": 48}), mirror=(_MRR, {"rsi_n": 14})),
        # ---- the rest of the survey
        Row("str.cdo_carry", "structured", "CDO tranche carry", X, _OTC),
        Row("str.cdo_risk_matched", "structured", "risk-matched CDO tranches", X, _OTC),
        Row("str.mbs", "structured", "mortgage-backed securities trading", X, _OTC),
        Row("cvb.arbitrage", "convertibles", "convertible arbitrage", X, _OTC),
        Row("cvb.oas", "convertibles", "convertible option-adjusted spread", X, _OTC),
        Row("tax.muni", "tax_arbitrage", "municipal bond tax arbitrage", X, _NONMKT),
        Row("tax.cross_border", "tax_arbitrage", "cross-border tax arbitrage", X, _NONMKT),
        Row("misc.inflation_swaps", "misc_assets", "inflation hedging with swaps", X, _OTC),
        Row("misc.tips", "misc_assets", "TIPS-treasury arbitrage", X, _CASHB),
        Row("misc.weather", "misc_assets", "weather risk", X, _OTC),
        Row("misc.energy_spread", "misc_assets", "energy (spark-spread) trading", X,
            "needs power prices against gas; the venue lists no power contract"),
        Row("dst.hold", "distressed", "holding distressed debt", X, _NONMKT),
        Row("dst.active", "distressed", "active distressed investing", X, _NONMKT),
        Row("dst.puzzle", "distressed", "distress-risk puzzle", X, _FUND),
        Row("re.mixed", "real_estate", "mixed-asset diversification with real estate", X,
            _NONMKT),
        Row("re.intra", "real_estate", "intra-asset real-estate diversification", X, _NONMKT),
        Row("cash.laundering", "cash", "money laundering (the survey's illicit example)", X,
            "illegal; listed by the survey as a description, never a strategy"),
        Row("cash.liquidity", "cash", "liquidity management", X, _NONMKT),
        Row("cash.repo", "cash", "repurchase agreements", X, _NONMKT),
        Row("cash.pawnshop", "cash", "pawnshop", X, _NONMKT),
        Row("cash.loan_sharking", "cash", "loan sharking", X,
            "illegal; listed by the survey as a description, never a strategy"),
        Row("cry.ann", "crypto", "artificial neural network on crypto prices", U,
            "applicable to Fusion's crypto CFDs, but no network is trained inside an hourly "
            "numpy budget; the KNN row measures the same price-only learning idea"),
        Row("cry.sentiment", "crypto", "sentiment (naive Bayes on text)", X,
            "needs a text corpus; the news lane, not a price bundle"),
        Row("mac.momentum", "macro", "fundamental macro momentum", U,
            "needs point-in-time macro surprises; not an axis of this bundle"),
        Row("mac.inflation_hedge", "macro", "global macro inflation hedge", X, _SIZE),
        Row("mac.fixed_income", "macro", "global fixed-income strategy", U,
            "needs point-in-time yields across countries; the bundle carries prices only"),
        Row("mac.announcements", "macro", "trading on economic announcements", X,
            "the event lane's event_reaction organ owns it; not a price-only hypothesis"),
        Row("inf.infrastructure", "infrastructure", "infrastructure investment", X, _NONMKT),
    ]
    return tuple(rows)


CATALOGUE: tuple[Row, ...] = _catalogue()
BY_ID: dict[str, Row] = {r.sid: r for r in CATALOGUE}


def counts() -> dict[str, int]:
    out = {d: sum(1 for r in CATALOGUE if r.disposition == d) for d in DISPOSITIONS}
    out["catalogued"] = len(CATALOGUE)
    out["paper_count"] = PAPER_COUNT
    return out


# ============================================================================ kernels
def _sma(s: np.ndarray, n: int) -> np.ndarray:
    return F.k_sum(s, n) / n


def hp_endpoint_weights(window: int, lam: float) -> np.ndarray:
    """The ONE-SIDED Hodrick-Prescott trend: the last row of (I + lam D'D)^-1 over a trailing
    window, so the trend at a bar is a fixed causal filter of the window ending at it. The
    familiar two-sided HP smooths with the future and is a look-ahead; this is not."""
    d2 = np.zeros((window - 2, window))
    for i in range(window - 2):
        d2[i, i:i + 3] = (1.0, -2.0, 1.0)
    inv = np.linalg.inv(np.eye(window) + lam * d2.T @ d2)
    return np.asarray(inv[-1], dtype=float)


_HP_W = 120
_HP_LAMBDA = 14400.0


def _hp_trend(s: np.ndarray) -> np.ndarray:
    w = F._windows(s, _HP_W)
    if w is None:
        return np.full(s.shape[0], np.nan)
    return F._pad(s, _HP_W, w @ hp_endpoint_weights(_HP_W, _HP_LAMBDA))


def _knn(lc: np.ndarray, h: int, k: int = 20, train: int = 500) -> np.ndarray:
    """Predicted h-bar return from the k nearest past states. A state is the 1-, 4- and 24-bar
    log returns scaled by trailing 24-bar volatility; a training row s is used at bar t only when
    its label (s + h) is already closed (s + h <= t)."""
    n = lc.shape[0]
    out = np.full(n, np.nan)
    r1 = lc - F.k_delay(lc, 1)
    vol = F.k_stddev(r1, 24)
    feats = np.column_stack([r1, lc - F.k_delay(lc, 4), lc - F.k_delay(lc, 24)])
    feats = feats / np.where(vol > 0, vol, np.nan)[:, None]
    label = np.full(n, np.nan)
    if n > h:
        label[:-h] = lc[h:] - lc[:-h]
    start = train + h
    if n <= start:
        return out
    win_f = np.lib.stride_tricks.sliding_window_view(feats, train, axis=0)   # (n-train+1, 3, W)
    win_l = np.lib.stride_tricks.sliding_window_view(label, train)            # (n-train+1, W)
    ts = np.arange(start, n)
    i0 = ts - h - train + 1                     # training rows i0 .. t-h
    fx, lx = win_f[i0], win_l[i0]
    dist = ((fx - feats[ts][:, :, None]) ** 2).sum(axis=1)
    dist = np.where(np.isfinite(dist) & np.isfinite(lx), dist, np.inf)
    kk = min(k, train)
    nn = np.argpartition(dist, kk - 1, axis=1)[:, :kk]
    rows = np.arange(ts.size)[:, None]
    picked = np.where(np.isfinite(dist[rows, nn]), lx[rows, nn], np.nan)
    ok = np.isfinite(picked).sum(axis=1) >= kk // 2
    pred = np.where(ok, np.nansum(np.where(np.isfinite(picked), picked, 0.0), axis=1)
                    / np.maximum(np.isfinite(picked).sum(axis=1), 1), np.nan)
    pred[~np.isfinite(feats[ts]).all(axis=1)] = np.nan
    out[ts] = pred
    return out


def _r_squared(lc: np.ndarray, n: int = 48) -> np.ndarray:
    w = F._windows(lc, n)
    if w is None:
        return np.full(lc.shape[0], np.nan)
    t = np.arange(n, dtype=float) - (n - 1) / 2.0
    yc = w - w.mean(axis=-1, keepdims=True)
    slope = (yc * t).sum(axis=-1) / (t * t).sum()
    ss_tot = (yc * yc).sum(axis=-1)
    r2 = np.where(ss_tot > 0, (slope ** 2) * (t * t).sum() / np.where(ss_tot > 0, ss_tot, 1.0),
                  np.nan)
    return F._pad(lc, n, np.sign(slope) * r2)


def _skew(s: np.ndarray, n: int) -> np.ndarray:
    w = F._windows(s, n)
    if w is None:
        return np.full(s.shape[0], np.nan)
    c = w - w.mean(axis=-1, keepdims=True)
    m2 = (c * c).mean(axis=-1)
    m3 = (c * c * c).mean(axis=-1)
    return F._pad(s, n, np.where(m2 > 0, m3 / np.where(m2 > 0, m2, 1.0) ** 1.5, np.nan))


# ============================================================================ time-series signals
#: Positive = the strategy's own long side, per symbol, from its own bars only.
def ts_signal(sid: str, p: F.Panel, h: int = 4) -> Any:
    c, hi, lo = p.c, p.h, p.lo
    with np.errstate(all="ignore"):
        lc = np.log(c)
        if sid == "stk.single_ma":
            return p.ts(c, lambda s: np.sign(s - _sma(s, 20)))
        if sid == "stk.two_ma":
            return p.ts(c, lambda s: np.sign(_sma(s, 10) - _sma(s, 40)))
        if sid == "stk.three_ma":
            def three(s: np.ndarray) -> np.ndarray:
                a, b, d = _sma(s, 3), _sma(s, 10), _sma(s, 21)
                up = (a > b) & (b > d)
                dn = (a < b) & (b < d)
                out = np.where(up, 1.0, np.where(dn, -1.0, 0.0))
                return np.where(np.isfinite(d), out, np.nan)
            return p.ts(c, three)
        if sid == "stk.support_resistance":
            hh = p.ts(hi, lambda s: F.k_delay(F.k_max(s, BARS_PER_DAY), 1))
            ll = p.ts(lo, lambda s: F.k_delay(F.k_min(s, BARS_PER_DAY), 1))
            cc = p.ts(c, lambda s: F.k_delay(s, 1))
            return np.sign(c - (hh + ll + cc) / 3.0)
        if sid == "stk.channel":
            hh = p.ts(hi, lambda s: F.k_delay(F.k_max(s, 48), 1))
            ll = p.ts(lo, lambda s: F.k_delay(F.k_min(s, 48), 1))
            return 0.5 - (c - ll) / np.where(hh > ll, hh - ll, np.nan)
        if sid == "stk.knn":
            return p.ts(lc, lambda s: _knn(s, h))
        if sid == "etf.r_squared":
            return p.ts(lc, _r_squared)
        if sid == "etf.mean_reversion":
            return 0.5 - (c - lo) / np.where(hi > lo, hi - lo, np.nan)
        if sid == "etf.multi_asset_trend":
            return p.ts(c, lambda s: np.sign(s - _sma(s, 100)))
        if sid == "fut.trend":
            return p.ts(lc, lambda s: np.sign(s - F.k_delay(s, 48)))
        if sid == "fx.hp_ma":
            return p.ts(lc, lambda s: np.sign(_sma(_hp_trend(s), 5) - _sma(_hp_trend(s), 20)))
    raise KeyError(sid)


# ============================================================================ class-book signals
def _class_rank(score: np.ndarray, groups: tuple[str, ...], present: np.ndarray,
                min_members: int) -> np.ndarray:
    """Within each class at each bar: rank in [0, 1] minus one half; NaN where the class has
    fewer than `min_members` members carrying a score."""
    out = np.full(score.shape, np.nan)
    sc = np.where(present & np.isfinite(score), score, np.nan)
    for g in sorted(set(groups)):
        if not g:
            continue
        cols = [j for j, gg in enumerate(groups) if gg == g]
        sub = sc[:, cols]
        ok = np.isfinite(sub).sum(axis=1) >= min_members
        r = F.xs_rank(np.where(ok[:, None], sub, np.nan))
        out[:, cols] = r - 0.5
    return out


def _class_mean(x: np.ndarray, groups: tuple[str, ...]) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    for g in sorted(set(groups)):
        if not g:
            continue
        cols = [j for j, gg in enumerate(groups) if gg == g]
        sub = x[:, cols]
        ok = np.isfinite(sub)
        m = np.where(ok, sub, 0.0).sum(axis=1) / np.maximum(ok.sum(axis=1), 1)
        m = np.where(ok.sum(axis=1) > 0, m, np.nan)
        out[:, cols] = m[:, None]
    return out


def xs_signal(sid: str, p: F.Panel, orient: np.ndarray, min_members: int
              ) -> tuple[np.ndarray, tuple[str, ...]]:
    """(signal in the SYMBOL's own direction, the groups it was ranked within). Scores are
    computed on the oriented log price (a USD pair read as its non-USD currency in dollars) and
    the rank is turned back to the symbol's own direction by the same orientation."""
    row = BY_ID[sid]
    groups = p.groups
    if row.only_class == "*":
        groups = tuple("all" if g else "" for g in groups)
    elif row.only_class:
        groups = tuple(g if g == row.only_class else "" for g in groups)
    d = BARS_PER_DAY
    with np.errstate(all="ignore"):
        lp = np.log(p.c) * orient[None, :]
        r1 = p.ts(lp, lambda s: s - F.k_delay(s, 1))
        if sid in ("stk.price_momentum", "etf.sector_momentum", "etf.sector_momentum_ma",
                   "etf.dual_momentum"):
            score = p.ts(lp, lambda s: F.k_delay(s, d) - F.k_delay(s, 21 * d))
        elif sid == "stk.low_vol":
            score = -p.ts(r1, lambda s: F.k_stddev(s, 20 * d))
        elif sid == "stk.residual_momentum":
            resid = r1 - _class_mean(r1, groups)
            score = p.ts(resid, lambda s: F.k_delay(F.k_sum(s, 20 * d), d)
                         / F.k_stddev(s, 20 * d))
        elif sid in ("stk.mr_single_cluster", "stk.mr_multi_cluster"):
            rd = p.ts(lp, lambda s: s - F.k_delay(s, d))
            score = -(rd - _class_mean(rd, groups))
        elif sid == "stk.mr_weighted_regression":
            rd = p.ts(lp, lambda s: s - F.k_delay(s, d))
            var = p.ts(r1, lambda s: F.k_stddev(s, 20 * d)) ** 2
            wt = np.where(var > 0, 1.0 / var, np.nan)
            num = _class_mean(np.where(np.isfinite(wt), rd * wt, np.nan), groups)
            den = _class_mean(wt, groups)
            score = -(rd - num / den) / np.sqrt(var)
        elif sid == "fut.contrarian":
            rd = p.ts(lp, lambda s: s - F.k_delay(s, 5 * d))
            score = -(rd - _class_mean(rd, groups))
        elif sid == "etf.alpha_rotation":
            mkt = _class_mean(r1, groups)
            n = 20 * d
            beta = p.ts2(r1, mkt, lambda a, b: F.k_covariance(a, b, n)
                         / np.where(F.k_stddev(b, n) > 0, F.k_stddev(b, n) ** 2, np.nan))
            score = (p.ts(r1, lambda s: F.k_sum(s, n) / n)
                     - beta * p.ts(mkt, lambda s: F.k_sum(s, n) / n))
        elif sid == "cmd.skewness":
            score = -p.ts(r1, lambda s: _skew(s, 20 * d))
        else:
            raise KeyError(sid)
        sig = _class_rank(score, groups, p.present, min_members)
        if sid == "etf.sector_momentum_ma":
            above = p.ts(lp, lambda s: s - _sma(s, 20 * d)) > 0
            sig = np.where((sig > 0) & ~above, 0.0, sig)
        elif sid == "etf.dual_momentum":
            sig = np.where((sig > 0) & ~(score > 0), 0.0, sig)
    return sig * orient[None, :], groups


def pair_signals(p: F.Panel, max_pairs: int = 30, window: int = 240
                 ) -> list[tuple[int, int, np.ndarray, np.ndarray]]:
    """Pairs within a peer class, in symbol order, at most `max_pairs`. For each: the signal on
    the spread (minus its trailing z-score: long the spread when it is cheap) and the spread's
    one-bar log change, both on the bars where BOTH legs printed. The hedge ratio is the trailing
    OLS slope -- known at the bar, never fitted on the bars after it."""
    out: list[tuple[int, int, np.ndarray, np.ndarray]] = []
    n_sym = len(p.symbols)
    with np.errstate(all="ignore"):
        lc = np.log(p.c)
        for i in range(n_sym):
            for j in range(i + 1, n_sym):
                if len(out) >= max_pairs:
                    return out
                if not p.groups[i] or p.groups[i] != p.groups[j]:
                    continue
                both = np.flatnonzero(p.present[:, i] & p.present[:, j])
                if both.size <= window + 2:
                    continue
                a, b = lc[both, i], lc[both, j]
                beta = F.k_covariance(a, b, window) / np.where(
                    F.k_stddev(b, window) > 0, F.k_stddev(b, window) ** 2, np.nan)
                spread = a - beta * b
                z = (spread - F.k_sum(spread, window) / window) / F.k_stddev(spread, window)
                sig = np.full(p.shape[0], np.nan)
                chg = np.full(p.shape[0], np.nan)
                sig[both] = -z
                # the spread held at THIS bar's hedge ratio, over the next bar
                nxt = np.full(both.size, np.nan)
                nxt[:-1] = (a[1:] - a[:-1]) - beta[:-1] * (b[1:] - b[:-1])
                chg[both] = nxt
                out.append((i, j, sig, chg))
    return out


TS_IDS: tuple[str, ...] = tuple(r.sid for r in CATALOGUE
                                if r.disposition == IMPLEMENTED and r.kind == "ts")
XS_IDS: tuple[str, ...] = tuple(r.sid for r in CATALOGUE
                                if r.disposition == IMPLEMENTED and r.kind == "xs")
PAIR_IDS: tuple[str, ...] = tuple(r.sid for r in CATALOGUE
                                  if r.disposition == IMPLEMENTED and r.kind == "pair")
SIGNALS: dict[str, Callable[..., Any]] = {**dict.fromkeys(TS_IDS, ts_signal),
                                          **dict.fromkeys(XS_IDS, xs_signal)}
