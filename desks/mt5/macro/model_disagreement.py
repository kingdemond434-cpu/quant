"""THE MODEL-DISAGREEMENT FACTORY (ROMAN-0388..0403, ROMAN-0578, ROMAN-0797..0812; the OU states
of ROMAN-0813..0818 ride along as representation features).

WHAT IT MEASURES. Per MT5 symbol with an implied-vol index (^VIX->US500, ^VXN->NAS100/USTEC,
^GVZ->XAUUSD, ^OVX->USOIL, ^VXD->US30, ^EVZ->EURUSD, resolved through `recorders.vol_archive`)
and per day, every model of `libs.quant_models` is calibrated on what the desk could know at
that day's knowable instant -- the index level (and the VIX term points where they exist) for
the Q models, the broker's own H1 bars for the P models -- and asked the same four questions:

    30-day vol forecast | ATM 30-day straddle | call delta at the market's 25-delta strike |
    P(|r_30d| > 2 x market-IV 30-day move)

The DISPERSION of the answers is the state: when Black-Scholes, Heston, Bates, Merton, local vol,
rough vol, GARCH, EWMA, close-to-close RV, high-frequency RV and the HMM regime model agree, the
world is easy to model; when they split, something the models encode differently (jumps, vol of
vol, memory, regime) is live. Features:

    valuation_disagreement           cross-model CV of the straddle value          (ROMAN-0395)
    vol_disagreement                 cross-model CV of the 30-day vol forecast      (ROMAN-0396)
    hedge_disagreement               cross-model sd of the 25-delta-strike delta    (ROMAN-0397)
    tail_disagreement                cross-model sd of the 2-sigma tail probability (ROMAN-0398)
    model_ensemble_entropy           entropy of softmax(recent out-of-sample log-likelihood of
                                     realised daily returns), / log(M)        (ROMAN-0399, 0812)
    bs_iv_minus_heston_equiv_iv      market IV - BS IV of the Heston straddle       (ROMAN-0807)
    market_iv_minus_garch_rv         market IV - GARCH 30-day forecast              (ROMAN-0808)
    market_iv_minus_rough_forecast   market IV - rough-vol 30-day forecast          (ROMAN-0809)
    heston_minus_bates               Heston - Bates straddle, per unit spot         (ROMAN-0810)
    short_horizon_model_dispersion   cross-model CV of the 5-day vol forecasts      (ROMAN-0811)
    rough_z0..z7                     the rough-vol OU factor states (representation, 0813..0818)

MEASURES ARE MIXED ON PURPOSE AND LABELLED. Q models answer under the risk-neutral measure, P
models under the physical one (QG-ADH-003); the dispersion of the two is partly the variance risk
premium, which is a state too. Sensor rows carry `measure: "P/Q mixed"`.

THE CONTRACT (ROMAN-0400..0403) -- the four predictive tests are the admission law:
    0400  forecast_gain (QLIKE) of next-21-day realised variance: expanding PIT regression on
          log IV^2 + vol/tail disagreement against the same regression on log IV^2 alone
    0401  gated_gain of a long next-day-return cell, gated on valuation disagreement high
    0402  monotone_gain of vol disagreement against next-week change in the daily high-low range
          (and in tick volume where the bars carry it)
    0403  gated_gain of a 1-day reversal cell, gated on vol disagreement high
Each is GAIN / NO_GAIN / UNMEASURED by `libs.research.sensor_engines`; UNMEASURED below min_n.

PIT. A day's row is knowable at d+1 01:00 UTC (the declared lag: the broker daily close and the
CBOE close of day d both precede it). Nothing on day d reads data dated after d, and a test
truncates the inputs after d and requires the identical row.

COMPUTE IS BOUNDED. Cheap models refit daily; GARCH/HMM/rough refit every `--heavy-every` days and
roll their state forward daily in between; Monte-Carlo-priced answers are carried between refits
as a ratio to Black-Scholes at the model's own daily vol forecast. Runs resume from the lake
series; `--budget-s` stops the walk (the report says PARTIAL) rather than overrunning the clock.

NO AUTHORITY: state series, conditioner cells and sensor rows only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.quant_models import (  # noqa: E402
    Bates,
    BlackScholes,
    BSParams,
    Ewma,
    EwmaParams,
    Garch,
    Heston,
    HestonParams,
    HighFrequencyRV,
    HistoricalRV,
    LocalVol,
    MarketData,
    Merton,
    OptionSpec,
    RegimeHMM,
    RoughVol,
    StochasticModel,
    implied_vol,
)
from libs.quant_models.heston import fit_term  # noqa: E402
from libs.quant_models.numerics import norm_cdf  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402

ENGINE = "model_disagreement"
REPORT = DESK / "reports" / "MODEL_DISAGREEMENT.json"
UNIVERSE = DESK / "data" / "universe"
VOL_DIR = DESK / "data" / "vol_archive"
UNMEASURED = "UNMEASURED"
SENSOR_ID = "model_disagreement"

H30 = 30.0
T30 = H30 / 365.0
HISTORY = 750          # daily returns / IV history handed to each calibration
INTRADAY = 60          # days of intraday returns handed to HF-RV and rough vol
ENTROPY_WINDOW = 21
SEED = 20261006
MODEL_NAMES = ("black_scholes", "heston", "merton_jd", "bates", "local_vol", "rough_vol",
               "garch", "ewma", "historical_rv", "hf_rv", "regime_hmm")
#: Models whose straddle / delta / tail come from Monte Carlo: exact on refit days only.
MC_MODELS = frozenset({"rough_vol", "garch", "regime_hmm"})
FEATURES = ("valuation_disagreement", "vol_disagreement", "hedge_disagreement",
            "tail_disagreement", "model_ensemble_entropy", "bs_iv_minus_heston_equiv_iv",
            "market_iv_minus_garch_rv", "market_iv_minus_rough_forecast", "heston_minus_bates",
            "short_horizon_model_dispersion")
N_ROUGH = 8
#: The HMM's EM refit runs every HMM_EVERY heavy refits (its filter rolls forward daily).
HMM_EVERY = 4
CARDS_IMPLEMENTED = {
    "models": ["ROMAN-0388", "ROMAN-0389", "ROMAN-0390", "ROMAN-0391", "ROMAN-0392",
               "ROMAN-0393", "ROMAN-0394", "ROMAN-0797", "ROMAN-0798", "ROMAN-0799",
               "ROMAN-0800", "ROMAN-0801", "ROMAN-0802", "ROMAN-0803", "ROMAN-0804",
               "ROMAN-0805", "ROMAN-0806"],
    "features": ["ROMAN-0395", "ROMAN-0396", "ROMAN-0397", "ROMAN-0398", "ROMAN-0399",
                 "ROMAN-0807", "ROMAN-0808", "ROMAN-0809", "ROMAN-0810", "ROMAN-0811",
                 "ROMAN-0812"],
    "representation": ["ROMAN-0813", "ROMAN-0814", "ROMAN-0815", "ROMAN-0816", "ROMAN-0817",
                       "ROMAN-0818"],
    "delivery": ["ROMAN-0578"],
    "quant_guild": ["QG-QFIN-005", "QG-ADH-003", "QG26-08", "QG25-29"],
}
MECHANISM = ("Eleven stochastic models (BS, Heston, Merton, Bates, local vol, rough vol, GARCH, "
             "EWMA, close-to-close RV, high-frequency RV, HMM regime) calibrated each day on the "
             "implied-vol index and the broker's own bars; their dispersion on vol, value, hedge "
             "and tail marks the days when what the models encode differently (jumps, vol of vol, "
             "memory, regime) is live. State only; options are never traded.")
FALSIFIER = ("disagreement adds no QLIKE reduction over market IV for next-21d realised "
             "variance, no gated Kelly gain on next-day return or 1-day reversal cells beyond "
             "the circular-shift null and within realised-vol terciles, and no rank order with "
             "next-week range change (n >= 250 days per symbol)")


# ============================================================================== PIT stamps
def available_at(day: date) -> datetime:
    """The declared lag: a daily value of day d is knowable at d+1 14:00 UTC -- FRED posts the
    CBOE index closes it republishes by d+1 09:00 ET (13:00 or 14:00 UTC), and the IV leg is
    the binding clock (the broker's close is known earlier)."""
    return datetime(day.year, day.month, day.day, 14, 0, tzinfo=UTC) + timedelta(days=1)


# ============================================================================== data
@dataclass
class Daily:
    """One symbol's daily panel built from H1 bars and the IV index (aligned on broker date)."""

    dates: list[date]
    close: np.ndarray
    ret: np.ndarray            # log close-to-close return INTO day i (nan on the first day)
    log_range: np.ndarray      # ln(high / low) of day i
    tick_volume: np.ndarray    # daily sum (nan when the bars carry none)
    intraday: list[np.ndarray]
    iv: np.ndarray             # market 30-day IV (decimal), nan where absent
    term: list[dict[float, float]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.dates)

    def head(self, n: int) -> Daily:
        """The panel truncated after its first n days (the PIT test's look-ahead probe)."""
        return Daily(self.dates[:n], self.close[:n], self.ret[:n], self.log_range[:n],
                     self.tick_volume[:n], self.intraday[:n], self.iv[:n], self.term[:n])


def daily_from_h1(bars: pd.DataFrame) -> pd.DataFrame:
    """H1 bars (index broker time) -> per broker date: close, high, low, tick volume and the
    intraday log returns (first bar from its open)."""
    idx = pd.DatetimeIndex(bars.index)
    df = bars.assign(_d=idx.date)
    rows = []
    for d, g in df.groupby("_d", sort=True):
        px = np.concatenate([[float(g["open"].iloc[0])], g["close"].to_numpy(dtype=float)])
        px = px[np.isfinite(px) & (px > 0)]
        if px.size < 2:
            continue
        tv = (float(g["tick_volume"].sum()) if "tick_volume" in g.columns else float("nan"))
        rows.append({"date": d, "close": float(px[-1]), "high": float(g["high"].max()),
                     "low": float(g["low"].min()), "tick_volume": tv,
                     "intraday": np.diff(np.log(px))})
    return pd.DataFrame(rows)


def build_daily(day_frame: pd.DataFrame, iv: Mapping[date, float],
                term: Mapping[date, dict[float, float]] | None = None) -> Daily:
    """Join the daily bars with the IV index on the same date. IV in DECIMAL."""
    dates = [d for d in day_frame["date"]]
    close = day_frame["close"].to_numpy(dtype=float)
    ret = np.concatenate([[np.nan], np.diff(np.log(close))])
    hi, lo = day_frame["high"].to_numpy(dtype=float), day_frame["low"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        rng = np.where((hi > 0) & (lo > 0) & (hi >= lo), np.log(hi / lo), np.nan)
    ivs = np.asarray([iv.get(d, np.nan) for d in dates], dtype=float)
    terms = [dict((term or {}).get(d, {})) for d in dates]
    return Daily(dates, close, ret, rng, day_frame["tick_volume"].to_numpy(dtype=float),
                 list(day_frame["intraday"]), ivs, terms)


def _reference(ticker: str, vol_dir: Path) -> dict[str, float]:
    for name in (f"{ticker}.json", f"{ticker.lstrip('^')}.json"):
        path = vol_dir / "reference" / name
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        series = doc.get("series") if isinstance(doc, dict) else None
        if isinstance(series, dict):
            return {str(k)[:10]: float(v) for k, v in series.items()
                    if isinstance(v, int | float) and math.isfinite(float(v))}
    return {}


def load_iv(ticker: str, term_tickers: Sequence[str], vol_dir: Path = VOL_DIR
            ) -> tuple[dict[date, float], dict[date, dict[float, float]]]:
    """(30d IV by date, term points by date) in DECIMAL, from the reference history and the
    desk's own archive vintages (the archive wins on a shared date)."""
    from recorders.vol_archive import TENOR_DAYS, read_archive
    level = {date.fromisoformat(k): v / 100.0 for k, v in _reference(ticker, vol_dir).items()}
    terms: dict[date, dict[float, float]] = {}
    for t in term_tickers:
        tenor = TENOR_DAYS.get(t)
        if not tenor:
            continue
        for k, v in _reference(t, vol_dir).items():
            terms.setdefault(date.fromisoformat(k), {})[tenor / 365.0] = v / 100.0
    for row in read_archive(vol_dir / "observations.jsonl"):
        if row.get("vol_ticker") != ticker or row.get("implied_vol") is None:
            continue
        try:
            d = date.fromisoformat(str(row.get("value_date"))[:10])
        except ValueError:
            continue
        level[d] = float(row["implied_vol"]) / 100.0
        for t, v in (row.get("term") or {}).items():
            if TENOR_DAYS.get(t) and v is not None:
                terms.setdefault(d, {})[TENOR_DAYS[t] / 365.0] = float(v) / 100.0
    return level, terms


def load_iv_sourced(ticker: str, term_tickers: Sequence[str], vol_dir: Path = VOL_DIR,
                    fred: Mapping[str, Sequence[tuple[str, float]]] | None = None
                    ) -> tuple[dict[date, float], dict[date, dict[float, float]], str]:
    """FRED's republished CBOE series first (terms-admitted, coordinator 2026-10-06), with the
    data_source the cells declare; the Yahoo-held reference only where FRED has no series."""
    from macro.vol_conditioner import FRED_IDS, fred_history, fred_series
    from recorders.vol_archive import TENOR_DAYS
    series = fred_series() if fred is None else fred
    lv = fred_history(ticker, series)
    if lv:
        level = {date.fromisoformat(k): v / 100.0 for k, v in lv.items()}
        terms: dict[date, dict[float, float]] = {}
        for t in term_tickers:
            tenor = TENOR_DAYS.get(t)
            if tenor and t in FRED_IDS:
                for k, v in fred_history(t, series).items():
                    terms.setdefault(date.fromisoformat(k), {})[tenor / 365.0] = v / 100.0
        return level, terms, f"fred:{FRED_IDS[ticker]}"
    level, terms = load_iv(ticker, term_tickers, vol_dir)
    return level, terms, DATA_SOURCE


def symbol_map(registry: Mapping[str, Any], universe_dir: Path = UNIVERSE
               ) -> list[tuple[str, str, tuple[str, ...]]]:
    """(vol ticker, MT5 symbol, term tickers) for every ground whose symbol has H1 bars."""
    from recorders.vol_archive import GROUND, resolve_symbol
    out = []
    for g in GROUND:
        sym = resolve_symbol(g.mt5_candidates, dict(registry))
        if sym and (universe_dir / f"{sym}_H1.parquet").exists():
            out.append((g.vol_ticker, sym, tuple(t for t in g.term if t != g.vol_ticker)))
    return out


# ============================================================================== the model bank
def market_data(d: Daily, i: int) -> MarketData:
    """Everything knowable at day i's close (indices <= i), nothing after."""
    lo = max(1, i + 1 - HISTORY)
    r = d.ret[lo:i + 1]
    ivh = d.iv[max(0, i + 1 - HISTORY):i + 1]
    term = {k: v for k, v in d.term[i].items() if v > 0} if d.term else {}
    if math.isfinite(d.iv[i]):
        term[T30] = float(d.iv[i])
    ilo = max(0, i + 1 - INTRADAY)
    return MarketData(as_of=available_at(d.dates[i]), spot=1.0,
                      returns=np.asarray(r[np.isfinite(r)], dtype=np.float64), iv_term=term,
                      iv_history=np.asarray(ivh[np.isfinite(ivh)], dtype=np.float64),
                      intraday_returns=[np.asarray(x, dtype=np.float64)
                                        for x in d.intraday[ilo:i + 1]],
                      daily_ranges=np.asarray(d.log_range[ilo:i + 1], dtype=np.float64))


@dataclass
class Answers:
    vf30: float
    vf5: float
    vf1: float
    straddle: float
    delta25: float
    tail: float


def k25(iv: float) -> float:
    """The strike (spot = 1, r = q = 0) where a BS call at the market IV has delta 0.25."""
    from scipy.special import ndtri
    sd = iv * math.sqrt(T30)
    return math.exp(-sd * float(ndtri(0.25)) + 0.5 * sd * sd)


def _straddle(m: StochasticModel) -> float:
    return (m.price(OptionSpec("call", 1.0, T30, 1.0))
            + m.price(OptionSpec("put", 1.0, T30, 1.0)))


def _delta(m: StochasticModel, strike: float) -> float:
    spec = OptionSpec("call", strike, T30, 1.0)
    if isinstance(m, BlackScholes):
        return m.greeks(spec).delta
    h = 1e-3
    up = m.price(OptionSpec("call", strike, T30, 1.0 + h))
    dn = m.price(OptionSpec("call", strike, T30, 1.0 - h))
    return (up - dn) / (2 * h)


def _gauss_tail(vol: float, a: float) -> float:
    sd = max(vol, 1e-6) * math.sqrt(T30)
    mu = -0.5 * sd * sd
    return (1.0 - norm_cdf((a - mu) / sd)) + norm_cdf((-a - mu) / sd)


def exact_answers(m: StochasticModel, iv: float) -> Answers:
    a = 2.0 * iv * math.sqrt(T30)
    return Answers(m.vol_forecast(H30), m.vol_forecast(5.0), m.vol_forecast(1.0), _straddle(m),
                   _delta(m, k25(iv)), m.tail_prob(a, H30))


@dataclass
class Carry:
    """What an MC model's answers were relative to Black-Scholes at its own vol, last refit."""

    straddle_ratio: float = 1.0
    delta_gap: float = 0.0
    tail_ratio: float = 1.0


def carry_from(ans: Answers, iv: float) -> Carry:
    bs = BlackScholes(BSParams(max(ans.vf30, 1e-4)))
    st = _straddle(bs)
    gt = _gauss_tail(ans.vf30, 2.0 * iv * math.sqrt(T30))
    return Carry(ans.straddle / st if st > 0 else 1.0, ans.delta25 - _delta(bs, k25(iv)),
                 ans.tail / gt if gt > 0 else 1.0)


def carried_answers(m: StochasticModel, iv: float, c: Carry) -> Answers:
    vf30 = m.vol_forecast(H30)
    bs = BlackScholes(BSParams(max(vf30, 1e-4)))
    tail = min(max(_gauss_tail(vf30, 2.0 * iv * math.sqrt(T30)) * c.tail_ratio, 0.0), 1.0)
    return Answers(vf30, m.vol_forecast(5.0), m.vol_forecast(1.0), _straddle(bs) * c.straddle_ratio,
                   _delta(bs, k25(iv)) + c.delta_gap, tail)


class ModelBank:
    """The eleven models, with the refit cadence that keeps a backfill bounded."""

    def __init__(self, heavy_every: int = 5) -> None:
        self.heavy_every = max(1, heavy_every)
        self.garch: Garch | None = None
        self.garch_at = -1
        self.hmm: RegimeHMM | None = None
        self.hmm_at = -1
        self.rough: RoughVol | None = None
        self.heston: Heston | None = None
        self.heston_at = -1
        self.ewma_lam: float | None = None
        self.carry: dict[str, Carry] = {}
        self.carry_at: dict[str, int] = {}

    def _heston(self, md: MarketData, i: int) -> Heston:
        """Full calibration on refit days; in between only v0 is re-solved on today's term."""
        if self.heston is None or i - self.heston_at >= self.heavy_every:
            self.heston = Heston().calibrate(md)
            self.heston_at = i
            return self.heston
        p = self.heston.params
        pts = sorted((t, v * v) for t, v in md.iv_term.items())
        if not pts:
            return self.heston
        v0, kappa, theta = fit_term(pts, p.kappa, p.theta)
        return Heston(HestonParams(v0, kappa, theta, p.sigma, p.rho))

    def calibrate(self, md: MarketData, i: int) -> dict[str, StochasticModel]:
        refit = (i - self.garch_at) >= self.heavy_every or self.garch is None
        out: dict[str, StochasticModel] = {
            "black_scholes": BlackScholes().calibrate(md),
            "local_vol": LocalVol().calibrate(md),
            "historical_rv": HistoricalRV().calibrate(md),
            "hf_rv": HighFrequencyRV().calibrate(md),
            "merton_jd": Merton().calibrate(md),
        }
        heston = self._heston(md, i)
        out["heston"] = heston
        out["bates"] = _bates_from(heston, md)
        fixed = self.ewma_lam is not None and not refit
        ewma = (Ewma(EwmaParams(lam=self.ewma_lam), fit_lambda=False)
                if fixed and self.ewma_lam is not None else Ewma()).calibrate(md)
        self.ewma_lam = ewma.params.lam
        out["ewma"] = ewma
        if refit:
            self.garch, self.garch_at = Garch().calibrate(md), i
        else:
            assert self.garch is not None
            self.garch = Garch(self.garch.params).update(md.returns[-1:])
        if self.hmm is None or i - self.hmm_at >= HMM_EVERY * self.heavy_every:
            self.hmm, self.hmm_at = RegimeHMM().calibrate(md), i
        else:
            self.hmm = self.hmm.refilter(md.returns)
        self.rough = RoughVol().calibrate(md)
        out["garch"], out["regime_hmm"], out["rough_vol"] = self.garch, self.hmm, self.rough
        return out

    def answers(self, models: Mapping[str, StochasticModel], iv: float, i: int
                ) -> dict[str, Answers]:
        res: dict[str, Answers] = {}
        for name, m in models.items():
            stale = (name in MC_MODELS and name in self.carry
                     and i - self.carry_at[name] < self.heavy_every)
            if stale:
                res[name] = carried_answers(m, iv, self.carry[name])
                continue
            res[name] = exact_answers(m, iv)
            if name in MC_MODELS:
                self.carry[name], self.carry_at[name] = carry_from(res[name], iv), i
        return res


def _bates_from(h: Heston, md: MarketData) -> Bates:
    """Bates sharing Heston's variance calibration, plus jumps from the returns."""
    from libs.quant_models.heston import BatesParams
    from libs.quant_models.jumps import estimate_jumps
    j = estimate_jumps(md.returns)
    p = h.params
    jv = j.var_per_year
    return Bates(BatesParams(v0=max(p.v0 - jv, 0.1 * p.v0), kappa=p.kappa,
                             theta=max(p.theta - jv, 0.1 * p.theta), sigma=p.sigma, rho=p.rho,
                             lam=j.lam, mu_j=j.mu_j, delta_j=j.delta_j))


# ============================================================================== features
def _cv(xs: Sequence[float]) -> float:
    a = np.asarray([x for x in xs if math.isfinite(x)], dtype=float)
    if a.size < 3 or a.mean() <= 0:
        return float("nan")
    return float(a.std(ddof=1) / a.mean())


def _sd(xs: Sequence[float]) -> float:
    a = np.asarray([x for x in xs if math.isfinite(x)], dtype=float)
    return float(a.std(ddof=1)) if a.size >= 3 else float("nan")


def features(ans: Mapping[str, Answers], iv: float, rough: RoughVol | None) -> dict[str, float]:
    vals = list(ans.values())
    out = {
        "valuation_disagreement": _cv([a.straddle for a in vals]),
        "vol_disagreement": _cv([a.vf30 for a in vals]),
        "hedge_disagreement": _sd([a.delta25 for a in vals]),
        "tail_disagreement": _sd([a.tail for a in vals]),
        "short_horizon_model_dispersion": _cv([a.vf5 for a in vals]),
        "market_iv": iv,
        "market_iv_minus_garch_rv": iv - ans["garch"].vf30,
        "market_iv_minus_rough_forecast": iv - ans["rough_vol"].vf30,
        "heston_minus_bates": ans["heston"].straddle - ans["bates"].straddle,
    }
    half = 0.5 * ans["heston"].straddle
    heq = implied_vol(half, "call", 1.0, 1.0, T30, 0.0, 0.0)
    out["bs_iv_minus_heston_equiv_iv"] = iv - heq if heq is not None else float("nan")
    z = rough.factor_states() if rough is not None else np.full(N_ROUGH, np.nan)
    for k in range(N_ROUGH):
        out[f"rough_z{k}"] = float(z[k]) if k < z.size else float("nan")
    for name, a in ans.items():
        out[f"vf30_{name}"] = a.vf30
        out[f"vf1_{name}"] = a.vf1
    return out


def ensemble_entropy(rows: list[dict[str, Any]], rets: Sequence[float],
                     window: int = ENTROPY_WINDOW) -> list[float]:
    """Per row i: normalised entropy of softmax(mean log-likelihood of the realised daily
    returns r_{j+1} under each model's 1-day forecast made at j, over the last `window` j < i).
    The forecast made at j is scored on r_{j+1}, knowable at row j+1: no look-ahead."""
    n, out = len(rows), []
    ll = np.full((n, len(MODEL_NAMES)), np.nan)
    for j in range(n - 1):
        r = rets[j + 1]
        if not math.isfinite(r):
            continue
        for k, name in enumerate(MODEL_NAMES):
            v = float(rows[j].get(f"vf1_{name}", float("nan")))
            if math.isfinite(v) and v > 0:
                sd = v / math.sqrt(252.0)
                ll[j, k] = -0.5 * math.log(2 * math.pi * sd * sd) - 0.5 * (r / sd) ** 2
    for i in range(n):
        block = ll[max(0, i - window):i]
        score = np.nanmean(block, axis=0) if block.size and np.isfinite(block).any(
            axis=0).all() else None
        if score is None or block.shape[0] < 5:
            out.append(float("nan"))
            continue
        w = np.exp((score - score.max()) * window)
        p = w / w.sum()
        h = -float(np.sum(p * np.log(np.where(p > 0, p, 1.0))))
        out.append(h / math.log(len(MODEL_NAMES)))
    return out


# ============================================================================== the walk
def build_rows(d: Daily, *, start: int = 0, warmup: int = 120, heavy_every: int = 5,
               deadline: float | None = None, now: datetime | None = None,
               clock: Callable[[], float] = time.monotonic) -> tuple[list[dict[str, Any]], bool]:
    """Rows for days i >= max(start, warmup) with an IV and a knowable instant <= now.
    Returns (rows, complete); complete is False when the deadline stopped the walk."""
    bank = ModelBank(heavy_every)
    rows: list[dict[str, Any]] = []
    for i in range(max(start, warmup), len(d)):
        if now is not None and available_at(d.dates[i]) > now:
            break
        if deadline is not None and clock() > deadline:
            return rows, False
        iv = float(d.iv[i])
        if not (math.isfinite(iv) and iv > 0):
            continue
        md = market_data(d, i)
        models = bank.calibrate(md, i)
        ans = bank.answers(models, iv, i)
        row: dict[str, Any] = {"available_time": available_at(d.dates[i]).isoformat(),
                               "event_time": f"{d.dates[i].isoformat()}T00:00:00+00:00",
                               "day_index": i}
        row.update(features(ans, iv, bank.rough))
        rows.append(row)
    return rows, True


def attach_entropy(rows: list[dict[str, Any]], d: Daily) -> None:
    rets = [float(d.ret[int(r["day_index"])]) for r in rows]
    for k, e in enumerate(ensemble_entropy(rows, rets)):
        rows[k]["model_ensemble_entropy"] = e


# ============================================================================== the contract
def _expanding_flag(x: np.ndarray, q: float = 2 / 3, min_hist: int = 60) -> np.ndarray:
    """x_t above the q-quantile of x_0..x_{t-1} (PIT: only past values set the bar)."""
    out = np.zeros(x.size, dtype=bool)
    for t in range(min_hist, x.size):
        hist = x[:t][np.isfinite(x[:t])]
        if hist.size >= min_hist and math.isfinite(x[t]):
            out[t] = x[t] > float(np.quantile(hist, q))
    return out


def _expanding_tercile(x: np.ndarray, min_hist: int = 60) -> list[int | None]:
    out: list[int | None] = []
    for t in range(x.size):
        hist = x[:t][np.isfinite(x[:t])]
        if hist.size < min_hist or not math.isfinite(x[t]):
            out.append(None)
            continue
        lo, hi = np.quantile(hist, [1 / 3, 2 / 3])
        out.append(0 if x[t] <= lo else (1 if x[t] <= hi else 2))
    return out


def _pit_regression(y: np.ndarray, xs: np.ndarray, lag: int, min_train: int = 250
                    ) -> np.ndarray:
    """Expanding OLS of log y on xs; row t is predicted from rows j <= t - lag - 1 (their
    targets were realised by t). Returns exp(prediction + residual variance / 2)."""
    pred = np.full(y.size, np.nan)
    ly = np.log(np.where(y > 0, y, np.nan))
    x = np.column_stack([np.ones(y.size), xs])
    for t in range(y.size):
        hi = t - lag
        if hi < min_train:
            continue
        xx, yy = x[:hi], ly[:hi]
        ok = np.isfinite(yy) & np.isfinite(xx).all(axis=1)
        if ok.sum() < min_train or not np.isfinite(x[t]).all():
            continue
        beta, *_ = np.linalg.lstsq(xx[ok], yy[ok], rcond=None)
        resid = yy[ok] - xx[ok] @ beta
        pred[t] = math.exp(float(x[t] @ beta) + 0.5 * float(resid.var()))
    return pred


def targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Forward quantities each contract scores, from the daily panel columns ret / log_range /
    tick_volume (all strictly AFTER the row's day)."""
    out = frame.copy()
    r = out["ret"].to_numpy(dtype=float)
    n = r.size
    fwd_rv = np.full(n, np.nan)
    for t in range(n - 21):
        w = r[t + 1:t + 22]
        if np.isfinite(w).all():
            fwd_rv[t] = float(np.mean(w * w)) * 252.0
    out["fwd_rv21"] = fwd_rv
    out["next_ret"] = np.concatenate([r[1:], [np.nan]])
    out["reversal"] = -np.sign(r) * out["next_ret"].to_numpy(dtype=float)
    for col, name in (("log_range", "range_change"), ("tick_volume", "volume_change")):
        x = out[col].to_numpy(dtype=float) if col in out.columns else np.full(n, np.nan)
        ch = np.full(n, np.nan)
        for t in range(5, n - 5):
            past, fut = x[t - 4:t + 1], x[t + 1:t + 6]
            if np.isfinite(past).all() and np.isfinite(fut).all() and past.mean() > 0 \
                    and fut.mean() > 0:
                ch[t] = math.log(fut.mean() / past.mean())
        out[name] = ch
    rv = np.full(n, np.nan)
    for t in range(21, n):
        w = r[t - 20:t + 1]
        if np.isfinite(w).all():
            rv[t] = float(np.std(w, ddof=1))
    out["rv21"] = rv
    return out


def measure_contracts(frame: pd.DataFrame, symbol: str, *, min_n: int = se.MIN_N,
                      min_n_rank: int = 100) -> list[dict[str, Any]]:
    """The four ROMAN-0400..0403 contracts for one symbol's feature frame.

    `frame` columns: the features, market_iv, ret, log_range, tick_volume (daily, row order)."""
    f = targets(frame)
    iv2 = f["market_iv"].to_numpy(dtype=float) ** 2
    vd = f["vol_disagreement"].to_numpy(dtype=float)
    td = f["tail_disagreement"].to_numpy(dtype=float)
    y = f["fwd_rv21"].to_numpy(dtype=float)
    log_iv2 = np.log(np.where(iv2 > 0, iv2, np.nan))
    base = _pit_regression(y, log_iv2[:, None], lag=22)
    model = _pit_regression(y, np.column_stack([log_iv2, vd, td]), lag=22)
    strata = _expanding_tercile(f["rv21"].to_numpy(dtype=float))
    eng = f"{ENGINE}:{symbol}"
    out = [
        {**se.forecast_gain(y.tolist(), model.tolist(), base.tolist(), engine=eng,
                            loss="qlike", min_n=min_n,
                            cards=["ROMAN-0400", "ROMAN-0396", "ROMAN-0398", "ROMAN-0578"],
                            baseline="expanding PIT regression of log RV21 on log market IV^2",
                            falsifier="no QLIKE reduction of next-21d realised variance over "
                                      "market IV alone (block-bootstrap p >= 0.05)"),
         "label": "disagreement -> future realised vol", "roman": "ROMAN-0400"},
        {**se.gated_gain(f["next_ret"].to_numpy(dtype=float).tolist(),
                         _expanding_flag(f["valuation_disagreement"].to_numpy(dtype=float))
                         .tolist(),
                         engine=eng, strata=strata, min_n=min_n,
                         cards=["ROMAN-0401", "ROMAN-0395", "ROMAN-0578"],
                         baseline="long next-day return every day (ungated sign cell)",
                         falsifier="gating on valuation disagreement in its top tercile adds "
                                   "no Kelly growth beyond the circular-shift null and within "
                                   "RV terciles"),
         "label": "disagreement -> direction", "roman": "ROMAN-0401"},
        {**se.monotone_gain(vd, f["range_change"].to_numpy(dtype=float), engine=eng,
                            min_n=min_n_rank,
                            cards=["ROMAN-0402", "ROMAN-0396", "ROMAN-0578"],
                            falsifier="no positive rank order between vol disagreement and the "
                                      "next week's change in daily high-low range"),
         "label": "disagreement -> liquidity (range)", "roman": "ROMAN-0402"},
        {**se.gated_gain(f["reversal"].to_numpy(dtype=float).tolist(),
                         _expanding_flag(vd).tolist(), engine=eng,
                         strata=strata, min_n=min_n,
                         cards=["ROMAN-0403", "ROMAN-0396", "ROMAN-0578"],
                         baseline="1-day reversal cell every day",
                         falsifier="gating the reversal cell on vol disagreement in its top "
                                   "tercile adds no Kelly growth beyond the shift null and "
                                   "within RV terciles"),
         "label": "disagreement -> strategy performance (1-day reversal)",
         "roman": "ROMAN-0403"},
    ]
    vol_ch = f["volume_change"].to_numpy(dtype=float)
    if np.isfinite(vol_ch).sum() >= 3:
        out.append({**se.monotone_gain(vd, vol_ch, engine=eng, min_n=min_n_rank,
                                       cards=["ROMAN-0402", "ROMAN-0396", "ROMAN-0578"],
                                       falsifier="no positive rank order between vol "
                                                 "disagreement and next week's tick-volume "
                                                 "change"),
                    "label": "disagreement -> liquidity (tick volume)", "roman": "ROMAN-0402"})
    for c in out:
        c["symbol"] = symbol
    return out


# ============================================================================== sensor rows
def sensor_rows(rows: Sequence[Mapping[str, Any]], symbol: str, series_id: str,
                now: datetime) -> list[Any]:
    """One state observation per feature for the latest row, with its percentile and z against
    the feature's own history."""
    from libs.research.sensor_contract import make
    if not rows:
        return []
    last = rows[-1]
    obs = []
    for feat in FEATURES:
        v = last.get(feat)
        if v is None or not math.isfinite(float(v)):
            continue
        hist = np.asarray([float(r.get(feat, np.nan)) for r in rows[:-1]], dtype=float)
        hist = hist[np.isfinite(hist)]
        pct = float((hist < v).mean()) if hist.size >= 20 else None
        z = (float((v - hist.mean()) / hist.std(ddof=1)) if hist.size >= 20
             and hist.std(ddof=1) > 0 else None)
        obs.append(make(sensor_id=SENSOR_ID, source_id=series_id, kind="state",
                        sensor_class="model_disagreement", metric=feat, entity=symbol,
                        event_time=last["event_time"], knowable_at=last["available_time"],
                        knowable_basis="declared_lag", received_at=now.isoformat(),
                        value=float(v), percentile=pct, surprise_z=z, unit="ratio",
                        asset_domain="vol", licence="public index + own broker bars",
                        measure="P/Q mixed",
                        declared_lag="daily close of day d knowable at d+1 14:00 UTC (FRED's clock)"))
    return obs


# ============================================================================== orchestration
def load_existing(series_id: str, lake: Path) -> list[dict[str, Any]]:
    path = lake / f"{series_id}.csv"
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
    except (OSError, ValueError):
        return []
    return [dict(r) for r in df.to_dict("records")]


def frame_for_contracts(rows: Sequence[Mapping[str, Any]], d: Daily) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    idx = df["day_index"].astype(int).to_numpy()
    df["ret"] = d.ret[idx]
    df["log_range"] = d.log_range[idx]
    df["tick_volume"] = d.tick_volume[idx]
    return df


#: THE TRUE ORIGIN OF THE NUMBERS. Every feature is a function of the CBOE volatility index
#: level, which the desk reads from the vol_archive reference history (Yahoo chart API, FRED as
#: the fallback), joined to the broker's own bars. The IV leg is the binding licence, so the
#: cells name it: a terms hold on Yahoo/CBOE-derived inputs HOLDS these cells, and that is the
#: correct outcome, never something to route around.
DATA_SOURCE = "yahoo:cboe_vol_index"            # the held fallback; FRED wins when present


def emit_cells(series_id: str, symbol: str, dry_run: bool = False,
               data_source: str = DATA_SOURCE) -> dict[str, Any]:
    """The conditioner cells for one symbol, through the one door. A spine that predates the
    `data_source` argument refuses the call, and the refusal is reported -- never retried
    without the provenance."""
    try:
        return se.emit_conditioner_cells(  # type: ignore[call-arg]
            series_id, list(FEATURES), [symbol], mechanism=MECHANISM, falsifier=FALSIFIER,
            generator=ENGINE, sides=(1, -1), data_source=data_source, dry_run=dry_run)
    except TypeError as exc:
        return {"series_id": series_id, "emitted": 0, "created": 0,
                "data_source": data_source,
                "error": f"cell door refused data_source ({str(exc)[:80]}); no cell emitted"}


def run_symbol(ticker: str, symbol: str, terms: Sequence[str], *, now: datetime,
               deadline: float, heavy_every: int, days: int, dry_run: bool, lake: Path,
               universe_dir: Path = UNIVERSE, vol_dir: Path = VOL_DIR) -> dict[str, Any]:
    series_id = f"ws_model_disagreement_{symbol}"
    out: dict[str, Any] = {"symbol": symbol, "vol_ticker": ticker, "series_id": series_id}
    iv, term, data_source = load_iv_sourced(ticker, terms, vol_dir)
    out["data_source"] = data_source
    if not iv:
        return {**out, "status": UNMEASURED,
                "why": f"no implied-vol history for {ticker} under {vol_dir} (reference or "
                       f"archive): the factory needs the index level"}
    bars = pd.read_parquet(universe_dir / f"{symbol}_H1.parquet")
    d = build_daily(daily_from_h1(bars), iv, term)
    if len(d) < 200:
        return {**out, "status": UNMEASURED, "why": f"{len(d)} daily bars < 200"}
    existing = [] if dry_run else load_existing(series_id, lake)
    start = max(0, len(d) - days)
    done = {str(r.get("event_time", ""))[:10] for r in existing}
    if done:
        pos = [k for k, dd in enumerate(d.dates) if dd.isoformat() in done]
        start = max(start, (max(pos) + 1) if pos else start)
    new, complete = build_rows(d, start=start, heavy_every=heavy_every, deadline=deadline,
                               now=now)
    keep = [r for r in existing if str(r.get("event_time", ""))[:10] in
            {dd.isoformat() for dd in d.dates}]
    for r in keep:
        k = d.dates.index(date.fromisoformat(str(r["event_time"])[:10]))
        r["day_index"] = k
    rows = sorted(keep + new, key=lambda r: str(r["available_time"]))
    if not rows:
        return {**out, "status": UNMEASURED, "why": "no day with an IV and a knowable instant"}
    attach_entropy(rows, d)
    contracts = measure_contracts(frame_for_contracts(rows, d), symbol)
    out.update({"status": "COMPUTED" if complete else "PARTIAL", "rows": len(rows),
                "new_rows": len(new), "first": rows[0]["event_time"][:10],
                "last": rows[-1]["event_time"][:10], "contracts": contracts,
                "latest": {k: rows[-1].get(k) for k in (*FEATURES, "market_iv")}})
    if dry_run:
        return out
    lake_rows = [{k: v for k, v in r.items() if k != "day_index"} for r in rows]
    for r in lake_rows:
        r["source_id"] = series_id
    out["lake"] = se.write_lake_series(series_id, lake_rows, root=lake)
    out["cells"] = emit_cells(series_id, symbol, data_source=data_source)
    from libs.research.sensor_contract import SensorLedger
    out["sensor"] = SensorLedger().append(sensor_rows(rows, symbol, series_id, now), now=now)
    return out


def run(*, now: datetime, budget_s: float = 900.0, heavy_every: int = 5, days: int = 750,
        dry_run: bool = False, symbols: Sequence[str] | None = None, lake: Path = se.LAKE,
        universe_dir: Path = UNIVERSE, vol_dir: Path = VOL_DIR) -> dict[str, Any]:
    try:
        registry = json.loads((universe_dir / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        registry = {}
    grounds = [g for g in symbol_map(registry, universe_dir)
               if not symbols or g[1] in symbols]
    t0 = time.monotonic()
    per: list[dict[str, Any]] = []
    for k, (ticker, sym, terms) in enumerate(grounds):
        share = (budget_s - (time.monotonic() - t0)) / max(1, len(grounds) - k)
        try:
            per.append(run_symbol(ticker, sym, terms, now=now,
                                  deadline=time.monotonic() + max(share, 1.0),
                                  heavy_every=heavy_every, days=days, dry_run=dry_run,
                                  lake=lake, universe_dir=universe_dir, vol_dir=vol_dir))
        except Exception as exc:          # one symbol's failure is reported, never silent
            per.append({"symbol": sym, "vol_ticker": ticker, "status": "ERROR",
                        "why": f"{type(exc).__name__}: {str(exc)[:200]}"})
    contracts = [c for p in per for c in p.get("contracts", [])]
    report = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"), "authority": "NONE",
              "measure": "P/Q mixed (Q: IV-calibrated models; P: bar-fitted models)",
              "symbols": per, "implements": CARDS_IMPLEMENTED,
              "status": (UNMEASURED if not grounds or all(
                  p.get("status") in (UNMEASURED, "ERROR") for p in per) else
                         "PARTIAL" if any(p.get("status") == "PARTIAL" for p in per)
                         else "COMPUTED"),
              "why": "" if grounds else "no vol-index ground resolves to a symbol with H1 bars",
              "elapsed_s": round(time.monotonic() - t0, 1),
              "verdicts": {v: sum(1 for c in contracts if c.get("verdict") == v)
                           for v in (se.GAIN, se.NO_GAIN, se.UNMEASURED)}}
    if not dry_run:
        se.publish(ENGINE, contracts or [se.contract(
            engine=ENGINE, cards=["ROMAN-0400", "ROMAN-0401", "ROMAN-0402", "ROMAN-0403",
                                  "ROMAN-0578"], metric="all", baseline="n/a",
            falsifier=FALSIFIER, value=None, baseline_value=None, n=0,
            why=str(report["why"] or "no symbol produced rows"))],
            extra={"implements": CARDS_IMPLEMENTED, "measure": report["measure"]})
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n",
                          "utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Model-disagreement factory (state only)")
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--heavy-every", type=int, default=5)
    ap.add_argument("--days", type=int, default=750, help="backfill depth on a first run")
    ap.add_argument("--symbols", nargs="*", default=None)
    args = ap.parse_args(argv)
    now = datetime.now(UTC)            # the ENGINE's clock, injected into every model call
    rep = run(now=now, budget_s=args.budget_s, heavy_every=args.heavy_every, days=args.days,
              dry_run=args.dry_run, symbols=args.symbols)
    print(f"model_disagreement: {rep['status']} {rep['verdicts']} in {rep['elapsed_s']}s"
          + (f" -- {rep['why']}" if rep.get("why") else ""))
    for p in rep["symbols"]:
        print(f"  {p.get('symbol')}: {p.get('status')} rows={p.get('rows', 0)} "
              f"{p.get('why', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
