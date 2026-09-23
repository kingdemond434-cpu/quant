#!/usr/bin/env python
"""THE PROBABILITY AND FAIR-VALUE DISLOCATION LAB (RESEARCH 11; LAWS 5m).

Six independent probability engines, each with a reliability curve per regime, against what the
MT5 instrument itself prices. A cell fires only when the CALIBRATED ensemble materially disagrees
with the market-implied state net of costs, model uncertainty and a regime buffer
(`libs/research/probability_engines.py` is the arithmetic; this file is the organ). It CONSUMES
the desk's existing organs by their reports and re-implements none of them:

  P1 macro/statistical     the instrument's own bar statistics (replayable on history) plus the
                           macro tilt from MACRO_INTELLIGENCE.json / MACRO_VIEW.json, which
                           enters only from the report's own `at`
  P2 options-implied       VIXCLS from data/axes/fred.json for the US indices;
                           SHADOW_INSTITUTIONAL.json names the other surfaces (deribit_*,
                           cboe REFUSED by terms) -- UNMEASURED BY NAME where none exists
  P3 prediction market     PREDICTION_MARKETS.json + data/prediction_forecasts.jsonl, as changes
                           in a resolving event probability mapped onto the instruments it reprices
  P4 cross-asset           the driver instruments' own bars (USDX, UST10Y, US500, XTIUSD ...)
                           plus TRANSMISSION_GRAPH.json measured edges when it names symbols
  P5 LLM/news              NEWS_EVENT_STREAM.json reaction cells (hit_rate with n)
  P6 physical/fundamental  data/axes/cot.json (knowable_at-stamped positioning), cot_gold.parquet,
                           reports/sge_premium.json; weather: no plane in the tree -> UNMEASURED

CALIBRATION IS MEASURED ON HISTORY WITH THE ANTI-LOOKAHEAD RULE: every replayed forecast carries
the available_time of its newest input (a COT row's knowable_at, a report's `at`) and is usable
only from then; `resolved_pairs` withholds and counts the rest. The snapshot engines (P2, P3, P5)
accumulate a forward record in data/dislocation_lab_forecasts.jsonl, resolved on later passes
against the bars, so an engine that cannot be replayed earns its curve the slow way or reads
UNMEASURED -- it is never handed p = 0.5.

CELLS are RESEARCH 11's eleven families, each cross-bred with regime x session x volatility x
liquidity x trend x event proximity x cross-asset confirmation x horizon, scheduled by V(a)
(`probability_engines.value_of_cell`) rather than enumerated; a fired cell is donated to the
compiler as an EXACT recipe (a registered family with its parameters, the dislocation state as
the conditioner, a named falsifier) and recorded in the registry as a `dislocation_cell`
discovery. NOTHING HERE SIZES CAPITAL.

    python desks/mt5/research/dislocation_lab.py --once --budget-s 900 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import probability_engines as PE  # noqa: E402

try:
    import universe_policy as up
except ImportError:  # pragma: no cover
    from research import universe_policy as up  # type: ignore[no-redef]

UNMEASURED = PE.UNMEASURED
MEASURED = PE.MEASURED
HORIZONS = PE.HORIZONS
HB = PE.HORIZON_BARS
ENGINES = PE.ENGINES
P1, P2, P3, P4, P5, P6 = ENGINES

CORE_TARGETS: tuple[str, ...] = ("XAUUSD", "USDJPY", "EURUSD", "US500", "NAS100", "XTIUSD",
                                 "XBRUSD", "USDX", "UST10Y")
MAX_BARS = 20_000
MIN_BARS = 400
MARKET_WINDOW = 720
MAX_PAIRS = 3_000
MAX_TARGETS_PER_PASS = 24
MAX_CELLS_PER_PASS = 80
MAX_DONATIONS = 40
DISPERSION_FIRE = 0.15
LEDGER_KEEP = 50_000
VOL_WINDOW = 120
RANK_WINDOW = 500
EVENT_NEAR_H = 4.0
EXCEED_1SD = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(1.0 / math.sqrt(2.0))))   # 0.3173

RULE = ("six independent probability engines, each with a reliability curve per regime measured "
        "on history under the anti-lookahead rule; a cell fires only when the CALIBRATED ensemble "
        "disagrees with the instrument's own market-implied state by more than costs + model "
        "uncertainty + a regime buffer; UNMEASURED is a value and is named per engine per target; "
        "fired cells are donated as exact recipes and nothing here sizes capital")

#: Static cross-asset drivers (sign = the direction the driver's up-move implies for the target).
#: UST10Y is a note PRICE: price up = yield down = USDJPY down, gold up.
DRIVERS: dict[str, tuple[tuple[str, float], ...]] = {
    "EURUSD": (("USDX", -1.0),), "GBPUSD": (("USDX", -1.0),),
    "AUDUSD": (("USDX", -1.0), ("XAUUSD", 1.0)), "NZDUSD": (("USDX", -1.0),),
    "USDCAD": (("USDX", 1.0), ("XTIUSD", -1.0)), "USDCHF": (("USDX", 1.0),),
    "USDJPY": (("UST10Y", -1.0), ("USDX", 1.0)),
    "XAUUSD": (("USDX", -1.0), ("UST10Y", 1.0)), "XAGUSD": (("XAUUSD", 1.0), ("USDX", -1.0)),
    "NAS100": (("US500", 1.0),), "US500": (("NAS100", 1.0),), "US30": (("US500", 1.0),),
    "XTIUSD": (("XBRUSD", 1.0),), "XBRUSD": (("XTIUSD", 1.0),),
    "USDX": (("EURUSD", -1.0),), "UST10Y": (("USDJPY", -1.0),),
}
RATES_DRIVER = "UST10Y"

#: Prediction-market categories -> the instruments a RISING probability reprices, with sign.
P3_MAP: dict[str, dict[str, float]] = {
    "rates": {"USDJPY": 1.0, "USDX": 1.0, "XAUUSD": -1.0, "UST10Y": -1.0, "EURUSD": -1.0},
    "fed": {"USDJPY": 1.0, "USDX": 1.0, "XAUUSD": -1.0, "UST10Y": -1.0},
    "inflation": {"XAUUSD": 1.0, "UST10Y": -1.0, "USDX": 1.0},
    "recession": {"US500": -1.0, "NAS100": -1.0, "XTIUSD": -1.0, "UST10Y": 1.0},
    "oil": {"XTIUSD": 1.0, "XBRUSD": 1.0},
    "geopolitics": {"XAUUSD": 1.0, "XTIUSD": 1.0, "XBRUSD": 1.0},
}

#: RESEARCH 11's cell families, exactly as listed, with the engines each one crosses.
CELL_FAMILIES: dict[str, dict[str, Any]] = {
    "macro_surprise": {"engines": (P1,), "expression": "continuation", "scope": "all"},
    "cross_asset_disagreement": {"engines": (P4, P1), "expression": "continuation",
                                 "scope": "all"},
    "options_vs_spot": {"engines": (P2,), "expression": "exceed", "scope": "all"},
    "rates_vs_fx": {"engines": (P4,), "expression": "continuation", "scope": "fx_gold",
                    "driver": RATES_DRIVER},
    "commodity_fundamentals_vs_cfd": {"engines": (P6,), "expression": "positioning",
                                      "scope": "commodity"},
    "event_probability_vs_gold": {"engines": (P3,), "expression": "event", "scope": "gold"},
    "weather_vs_energy_agriculture": {"engines": (P6,), "expression": "event",
                                      "scope": "energy_agri", "needs": "weather data plane"},
    "prediction_market_vs_index_fx": {"engines": (P3,), "expression": "event",
                                      "scope": "index_fx"},
    "news_ensemble_vs_reaction": {"engines": (P5,), "expression": "event", "scope": "all"},
    "consensus_dispersion": {"engines": ENGINES, "expression": "reversal", "scope": "all"},
    "under_over_reaction_after_probability_shock": {"engines": ENGINES, "expression": "shock",
                                                    "scope": "all"},
}

FX_CCYS = ("USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "SGD", "NOK", "SEK", "DKK",
           "HKD", "MXN", "ZAR", "HUF", "PLN", "CZK", "TRY", "CNH")


# --------------------------------------------------------------------------- paths and io
@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe"

    @property
    def registry(self) -> Path:
        return self.universe / "universe.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "DISLOCATION_LAB.json"

    @property
    def intel(self) -> Path:
        return self.desk / "data" / "intelligence" / "dislocation_lab"

    @property
    def conformal(self) -> Path:
        """The sandbox conformal cell's calibration feed (sandboxes/conformal_calibration)."""
        return self.desk / "reports" / "SANDBOX_CONFORMAL.json"

    @property
    def state(self) -> Path:
        return self.desk / "data" / "dislocation_lab_state.json"

    @property
    def ledger(self) -> Path:
        return self.desk / "data" / "dislocation_lab_forecasts.jsonl"

    @property
    def macro_intel(self) -> Path:
        return self.desk / "reports" / "MACRO_INTELLIGENCE.json"

    @property
    def macro_view(self) -> Path:
        return self.desk / "reports" / "MACRO_VIEW.json"

    @property
    def fred(self) -> Path:
        return self.desk / "data" / "axes" / "fred.json"

    @property
    def shadow(self) -> Path:
        return self.desk / "reports" / "SHADOW_INSTITUTIONAL.json"

    @property
    def prediction(self) -> Path:
        return self.desk / "reports" / "PREDICTION_MARKETS.json"

    @property
    def prediction_forecasts(self) -> Path:
        return self.desk / "data" / "prediction_forecasts.jsonl"

    @property
    def transmission(self) -> Path:
        return self.desk / "reports" / "TRANSMISSION_GRAPH.json"

    @property
    def news(self) -> Path:
        return self.desk / "reports" / "NEWS_EVENT_STREAM.json"

    @property
    def cot(self) -> Path:
        return self.desk / "data" / "axes" / "cot.json"

    @property
    def cot_gold(self) -> Path:
        return self.desk / "data" / "cot_gold.parquet"

    @property
    def sge(self) -> Path:
        return self.desk / "reports" / "sge_premium.json"

    @property
    def calendar(self) -> Path:
        return self.desk / "data" / "forced_flow_calendar.json"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.isoformat(timespec="seconds")


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _parse_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError):
        return None
    if ts is pd.NaT:
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").to_pydatetime()


def _num(value: Any, *keys: str) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None
    if isinstance(value, dict):
        for k in keys or ("tilt", "value", "p", "v"):
            v = value.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
    return None


# --------------------------------------------------------------------------- the pass context
class Context:
    """Everything a pass reads, read once, with the bars cached per symbol."""

    def __init__(self, paths: Paths, now: datetime) -> None:
        self.paths = paths
        self.now = now
        self._bars: dict[str, pd.DataFrame | None] = {}
        self.registry = _read_json(paths.registry)
        self.macro_intel = _read_json(paths.macro_intel)
        self.macro_view = _read_json(paths.macro_view)
        self.fred = _read_json(paths.fred)
        self.shadow = _read_json(paths.shadow)
        self.prediction = _read_json(paths.prediction)
        self.pred_rows = _read_jsonl(paths.prediction_forecasts)
        self.transmission = _read_json(paths.transmission)
        self.news = _read_json(paths.news)
        self.cot = _read_json(paths.cot)
        self.sge = _read_json(paths.sge)
        self.calendar = _read_json(paths.calendar)
        self.ledger_rows = _read_jsonl(paths.ledger)
        self.cot_gold: pd.DataFrame | None = None
        if paths.cot_gold.exists():
            try:
                self.cot_gold = pd.read_parquet(paths.cot_gold)
            except Exception:
                self.cot_gold = None
        self.sources: dict[str, str] = {
            str(p.relative_to(paths.desk)): ("present" if p.exists() else "absent")
            for p in (paths.macro_intel, paths.macro_view, paths.fred, paths.shadow,
                      paths.prediction, paths.prediction_forecasts, paths.transmission,
                      paths.news, paths.cot, paths.cot_gold, paths.sge, paths.calendar)}

    def bars(self, sym: str) -> pd.DataFrame | None:
        if sym not in self._bars:
            self._bars[sym] = _load_bars(self.paths, sym)
        return self._bars[sym]

    def has_bars(self, sym: str) -> bool:
        return (self.paths.universe / f"{sym}_H1.parquet").exists()

    def digits(self, sym: str) -> int | None:
        row = (self.registry or {}).get(sym) if isinstance(self.registry, dict) else None
        d = row.get("digits") if isinstance(row, dict) else None
        return int(d) if isinstance(d, (int, float)) and not isinstance(d, bool) else None


def _load_bars(paths: Paths, sym: str) -> pd.DataFrame | None:
    p = paths.universe / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if "close" not in df.columns or len(df) < MIN_BARS:
        return None
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True))
    df = df.set_axis(idx).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df[df["close"] > 0].tail(MAX_BARS)
    return None if len(df) < MIN_BARS else df


# --------------------------------------------------------------------------- bar arithmetic
def _close_times(df: pd.DataFrame) -> np.ndarray:
    """A bar labelled t is KNOWN at t + 1h: every forecast is stamped at the close."""
    return (df.index + pd.Timedelta(hours=1)).to_numpy(dtype="datetime64[ns]")


def _fwd_return(lc: np.ndarray, hb: int) -> np.ndarray:
    out = np.full(len(lc), np.nan)
    if len(lc) > hb:
        out[:-hb] = lc[hb:] - lc[:-hb]
    return out


def _zscore_move(lc: np.ndarray, n: int) -> np.ndarray:
    """(log move over n bars) / (trailing 1-bar vol * sqrt(n)); NaN before enough history."""
    s = pd.Series(lc)
    r1 = s.diff()
    vol = r1.rolling(VOL_WINDOW, min_periods=VOL_WINDOW // 2).std()
    move = s - s.shift(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (move / (vol * math.sqrt(n))).to_numpy(dtype=float)
    z[~np.isfinite(z)] = np.nan
    return np.clip(z, -4.0, 4.0)


def _regime_axes(df: pd.DataFrame) -> dict[str, np.ndarray]:
    lc = np.log(df["close"].to_numpy(dtype=float))
    s = pd.Series(lc)
    ma = s.rolling(120, min_periods=60).mean()
    trend = np.where(s > ma, "up", "down").astype(object)
    trend[ma.isna().to_numpy()] = "UNMEASURED"
    vol = s.diff().rolling(24, min_periods=12).std()
    rank = vol.rolling(RANK_WINDOW, min_periods=100).rank(pct=True)
    volb = np.full(len(lc), "UNMEASURED", dtype=object)
    rk = rank.to_numpy(dtype=float)
    ok = np.isfinite(rk)
    volb[ok & (rk < 1 / 3)] = "lo"
    volb[ok & (rk >= 1 / 3) & (rk < 2 / 3)] = "mid"
    volb[ok & (rk >= 2 / 3)] = "hi"
    hours = (df.index.hour.to_numpy() + 1) % 24
    session = np.full(len(lc), "late", dtype=object)
    session[(hours >= 0) & (hours < 7)] = "asia"
    session[(hours >= 7) & (hours < 13)] = "london"
    session[(hours >= 13) & (hours < 21)] = "ny"
    liq = np.full(len(lc), "UNMEASURED", dtype=object)
    if "spread" in df.columns:
        sp = pd.to_numeric(df["spread"], errors="coerce")
        med = sp.rolling(RANK_WINDOW, min_periods=100).median()
        both = sp.notna() & med.notna()
        liq[both.to_numpy() & (sp <= med).to_numpy()] = "tight"
        liq[both.to_numpy() & (sp > med).to_numpy()] = "wide"
    regime = np.array([f"{t}_{v}" for t, v in zip(trend, volb, strict=False)], dtype=object)
    return {"trend": trend, "vol": volb, "session": session, "liquidity": liq, "regime": regime}


def _round_trip_cost(ctx: Context, sym: str, df: pd.DataFrame) -> float:
    """Round trip in log-return units from the bars' own spread column and the registry's
    digits (inferred from the price's decimals when the registry has no row)."""
    close = df["close"].to_numpy(dtype=float)
    mid = float(np.median(close[-MARKET_WINDOW:]))
    if "spread" not in df.columns:
        return 2e-4
    sp = pd.to_numeric(df["spread"], errors="coerce").tail(MARKET_WINDOW)
    if sp.notna().sum() == 0:
        return 2e-4
    digits = ctx.digits(sym)
    if digits is None:
        digits = 0
        for v in close[-50:]:
            txt = f"{v:.6f}".rstrip("0")
            digits = max(digits, len(txt.split(".")[1]) if "." in txt else 0)
        digits = min(5, digits)
    point = 10.0 ** (-digits)
    return max(1e-6, 2.0 * float(sp.median()) * point / mid)


# --------------------------------------------------------------------------- engine readings
@dataclass
class Reading:
    engine: str
    status: str
    why: str = ""
    p: np.ndarray | None = None
    available: np.ndarray | None = None
    band: np.ndarray | None = None
    source: str = ""
    claim: str = PE.CLAIM_UP
    quantiles: dict[str, float] = field(default_factory=dict)
    n_basis: int = 0


def _unmeasured(engine: str, why: str, source: str = "") -> Reading:
    return Reading(engine=engine, status=UNMEASURED, why=why, source=source)


def _sigmoid_arr(x: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore"):
        return 1.0 / (1.0 + np.exp(-x))


def _asset_class(ctx: Context, sym: str) -> str:
    try:
        return str(up.asset_class_of(sym) or "")
    except Exception:
        return ""


def _macro_tilt(ctx: Context, sym: str) -> tuple[float, datetime | None, str]:
    """The macro component of P1: the fusion's asset-class tilt and the view's currency lean,
    each usable only from its own `at`."""
    tilt = 0.0
    at: datetime | None = None
    parts: list[str] = []
    mi = ctx.macro_intel
    if isinstance(mi, dict):
        tilts = (mi.get("suggestions") or {}).get("asset_classes") or {}
        cls = up._norm(_asset_class(ctx, sym))
        for k, v in tilts.items():
            if up._norm(k) == cls:
                t = _num(v)
                if t is not None:
                    tilt += max(-1.0, min(1.0, t)) * 0.5
                    parts.append(f"MACRO_INTELLIGENCE asset_classes[{k}]={t:.3f}")
                    at = _parse_time(mi.get("at"))
    mv = ctx.macro_view
    if isinstance(mv, dict) and isinstance(mv.get("lean"), dict):
        lean = {str(k).upper(): _num(v) for k, v in mv["lean"].items()}
        base, quote = sym[:3].upper(), sym[3:6].upper()
        if base in lean and quote in lean and lean[base] is not None and lean[quote] is not None:
            d = math.tanh((lean[base] - lean[quote]) / 2.0)
            tilt += 0.5 * d
            parts.append(f"MACRO_VIEW lean[{base}]-lean[{quote}]={lean[base] - lean[quote]:.3f}")
        elif sym.upper() in ("XAUUSD", "USDX") and lean.get("USD") is not None:
            d = math.tanh(float(lean["USD"] or 0.0) / 2.0) * (1.0 if sym == "USDX" else -1.0)
            tilt += 0.5 * d
            parts.append(f"MACRO_VIEW lean[USD]={lean['USD']:.3f}")
        mv_at = _parse_time(mv.get("at"))
        if parts and mv_at is not None:
            at = mv_at if at is None else max(at, mv_at)
    return tilt, at, "; ".join(parts) if parts else "no macro component (reports absent)"


def engine_p1(ctx: Context, sym: str, h: str, df: pd.DataFrame, close_t: np.ndarray) -> Reading:
    lc = np.log(df["close"].to_numpy(dtype=float))
    z24, z120 = _zscore_move(lc, 24), _zscore_move(lc, 120)
    x = 0.2 * np.nan_to_num(z24, nan=0.0) + 0.3 * np.nan_to_num(z120, nan=0.0)
    p = _sigmoid_arr(x)
    p[np.isnan(z120)] = np.nan
    avail = close_t.copy()
    tilt, at, src = _macro_tilt(ctx, sym)
    if at is not None and tilt != 0.0:
        stamp = np.datetime64(at.replace(tzinfo=None), "ns")
        after = close_t >= stamp
        p[after] = _sigmoid_arr(x[after] + tilt)
        avail[after] = np.maximum(avail[after], stamp)
    n = int(np.isfinite(p).sum())
    if n == 0:
        return _unmeasured(P1, f"{sym}: fewer than {VOL_WINDOW + 120} bars of history")
    return Reading(engine=P1, status=MEASURED, p=p, available=avail,
                   source=f"bars(z24,z120) + {src}", n_basis=n,
                   why="statistical component replayed on history; macro tilt from the "
                       "reports' own `at` only")


def _vix_points(ctx: Context) -> list[tuple[datetime, float]]:
    fred = ctx.fred
    series = fred.get("series") if isinstance(fred, dict) else None
    raw = series.get("VIXCLS") if isinstance(series, dict) else None
    pts: list[tuple[datetime, float]] = []
    if isinstance(raw, dict):
        items: list[Any] = raw.get("points") or raw.get("rows") or raw.get("values") or []
        if not items:
            items = [{"date": k, "value": v} for k, v in raw.items()
                     if isinstance(v, (int, float))]
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    for it in items:
        if isinstance(it, dict):
            t = _parse_time(it.get("date") or it.get("at") or it.get("t"))
            v = _num(it, "value", "v", "close")
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            t, v = _parse_time(it[0]), _num(it[1])
        else:
            continue
        if t is not None and v is not None and v > 0:
            pts.append((t, float(v)))
    return sorted(pts)


def _sensor_state(ctx: Context, sensor: str) -> str:
    sh = ctx.shadow
    for row in (sh.get("sensors") or []) if isinstance(sh, dict) else []:
        if isinstance(row, dict) and row.get("sensor") == sensor:
            return str(row.get("state") or UNMEASURED)
    return "SHADOW_INSTITUTIONAL.json absent"


def engine_p2(ctx: Context, sym: str, h: str, df: pd.DataFrame, close_t: np.ndarray) -> Reading:
    """Options-implied: the surface's own claim is P(|r| > 1 sigma) = 0.317 and its width. Only
    the US indices have a lawful surface in this tree (VIXCLS); everything else is UNMEASURED
    BY NAME, with the surfaces the shadow organ checked and why they hold nothing."""
    pts = _vix_points(ctx) if sym in ("US500", "NAS100") else []
    if not pts:
        why = (f"no options surface for {sym}: VIXCLS in data/axes/fred.json holds "
               f"{len(_vix_points(ctx))} point(s) and maps to US500/NAS100 only; "
               f"deribit_atm_iv {_sensor_state(ctx, 'deribit_atm_iv')}; "
               f"cboe_delayed_surface {_sensor_state(ctx, 'cboe_delayed_surface')}")
        return _unmeasured(P2, why, source="fred.json VIXCLS; SHADOW_INSTITUTIONAL sensors")
    hb = HB[h]
    stamps = np.array([np.datetime64(t.replace(tzinfo=None) + timedelta(days=1), "ns")
                       for t, _ in pts])
    values = np.array([v for _, v in pts], dtype=float)
    pos = np.searchsorted(stamps, close_t, side="right") - 1
    ok = pos >= 0
    iv = np.full(len(close_t), np.nan)
    avail = close_t.copy()
    iv[ok] = values[pos[ok]] / 100.0
    avail[ok] = np.maximum(close_t[ok], stamps[pos[ok]])
    band = iv * math.sqrt(hb / (252.0 * 24.0))
    p = np.where(np.isfinite(band), EXCEED_1SD, np.nan)
    last = float(band[-1]) if np.isfinite(band[-1]) else None
    q = ({"q05": -1.645 * last, "q25": -0.674 * last, "q50": 0.0, "q75": 0.674 * last,
          "q95": 1.645 * last} if last is not None else {})
    return Reading(engine=P2, status=MEASURED, p=p, available=avail, band=band,
                   source="fred.json VIXCLS (S&P surface)", claim=PE.CLAIM_EXCEED,
                   quantiles=q, n_basis=int(ok.sum()),
                   why="implied one-sigma move vs realised exceedance; the calibration table IS "
                       "the variance risk premium by regime")


def engine_p3(ctx: Context, sym: str, h: str, df: pd.DataFrame, close_t: np.ndarray) -> Reading:
    rows = ctx.pred_rows
    if not rows:
        return _unmeasured(P3, f"{sym}: PREDICTION_MARKETS.json "
                               f"{ctx.sources.get('reports/PREDICTION_MARKETS.json', 'absent')} "
                               "and data/prediction_forecasts.jsonl holds no forecast rows",
                           source="prediction_markets.py forecasts")
    p = np.full(len(close_t), np.nan)
    avail = close_t.copy()
    last_by_id: dict[str, float] = {}
    n = 0
    for row in sorted(rows, key=lambda r: str(r.get("at") or r.get("recorded_at") or "")):
        cat = str(row.get("category") or "").lower()
        sign = next((m[sym] for k, m in P3_MAP.items() if k in cat and sym in m), None)
        pv = _num(row.get("p"))
        t = _parse_time(row.get("at") or row.get("recorded_at") or row.get("t"))
        fid = str(row.get("forecast_id") or "")
        if sign is None or pv is None or t is None or not fid:
            continue
        prev = last_by_id.get(fid)
        last_by_id[fid] = pv
        if prev is None:
            continue
        stamp = np.datetime64(t.replace(tzinfo=None), "ns")
        i = int(np.searchsorted(close_t, stamp, side="left"))
        if i >= len(close_t):
            continue
        p[i] = PE.sigmoid(sign * (PE.logit(pv) - PE.logit(prev)))
        avail[i] = max(avail[i], stamp)
        n += 1
    if n == 0:
        return _unmeasured(P3, f"{sym}: no prediction-market contract in a category that "
                               "reprices it has two readings", source="prediction_forecasts")
    return Reading(engine=P3, status=MEASURED, p=p, available=avail,
                   source="data/prediction_forecasts.jsonl (changes in a resolving probability)",
                   n_basis=n, why="a change in a resolving event probability mapped onto the "
                                  "instrument that event reprices")


def _drivers(ctx: Context, sym: str) -> list[tuple[str, float, str]]:
    out: list[tuple[str, float, str]] = [(d, s, "static map") for d, s in DRIVERS.get(sym, ())]
    if not out:
        base, quote = sym[:3].upper(), sym[3:6].upper()
        if quote == "USD" and base in FX_CCYS and sym != "USDX":
            out.append(("USDX", -1.0, "quote currency"))
        elif base == "USD" and quote in FX_CCYS:
            out.append(("USDX", 1.0, "base currency"))
        elif base == "XAU":
            out.append(("XAUUSD", 1.0, "gold cross"))
    tg = ctx.transmission
    edges = (tg.get("edges") or []) if isinstance(tg, dict) else []
    for e in edges:
        if not isinstance(e, dict) or not e.get("measured"):
            continue
        dst = str(e.get("to") or e.get("target") or e.get("dst") or "")
        src = str(e.get("from") or e.get("source") or e.get("src") or "")
        corr = _num(e.get("corr"))
        if dst == sym and src and corr and ctx.has_bars(src) and src != sym:
            out.append((src, 1.0 if corr > 0 else -1.0, "TRANSMISSION_GRAPH edge"))
    seen: set[str] = set()
    uniq = []
    for d, s, src in out:
        if d not in seen and d != sym:
            seen.add(d)
            uniq.append((d, s, src))
    return uniq


def engine_p4(ctx: Context, sym: str, h: str, df: pd.DataFrame, close_t: np.ndarray,
              *, only: str | None = None) -> Reading:
    hb = HB[h]
    drivers = [(d, s, src) for d, s, src in _drivers(ctx, sym) if only is None or d == only]
    x = np.zeros(len(df))
    used: list[str] = []
    for d, sign, src in drivers:
        ddf = ctx.bars(d)
        if ddf is None:
            continue
        dl = pd.Series(np.log(ddf["close"].to_numpy(dtype=float)), index=ddf.index)
        aligned = dl.reindex(df.index, method="ffill").to_numpy(dtype=float)
        z = _zscore_move(aligned, hb)
        x = x + sign * np.nan_to_num(z, nan=0.0)
        used.append(f"{d}({'+' if sign > 0 else '-'}, {src})")
    if not used:
        return _unmeasured(P4, f"{sym}: no cross-asset driver with bars"
                               + (f" (wanted {only})" if only else ""),
                           source="driver bars; TRANSMISSION_GRAPH.json "
                                  + ctx.sources.get("reports/TRANSMISSION_GRAPH.json", "absent"))
    p = _sigmoid_arr(0.4 * x / math.sqrt(len(used)))
    p[: VOL_WINDOW + hb] = np.nan
    return Reading(engine=P4, status=MEASURED, p=p, available=close_t.copy(),
                   source="drivers: " + ", ".join(used), n_basis=int(np.isfinite(p).sum()),
                   why="the drivers' own horizon moves, standardised, on the shared bar clock")


def engine_p5(ctx: Context, sym: str, h: str, df: pd.DataFrame, close_t: np.ndarray) -> Reading:
    news = ctx.news
    if not isinstance(news, dict):
        return _unmeasured(P5, f"{sym}: NEWS_EVENT_STREAM.json absent; news_captures.jsonl "
                               "carries headlines without a probability",
                           source="news_event_stream.py")
    at = _parse_time(news.get("at"))
    hits: list[tuple[float, float]] = []
    for ev in news.get("events") or []:
        rx = ev.get("reaction") if isinstance(ev, dict) else None
        if not isinstance(rx, dict) or rx.get("symbol") != sym or rx.get("horizon") != h:
            continue
        n = _num(rx.get("n"))
        hr = _num(rx.get("hit_rate"))
        if n and hr is not None and n >= PE.MIN_N_BIN:
            hits.append((hr, n))
    if not hits or at is None:
        return _unmeasured(P5, f"{sym}/{h}: NEWS_EVENT_STREAM.json holds no reaction cell with "
                               f"n >= {PE.MIN_N_BIN} for it", source="NEWS_EVENT_STREAM.json")
    pv = sum(hr * n for hr, n in hits) / sum(n for _, n in hits)
    p = np.full(len(close_t), np.nan)
    avail = close_t.copy()
    stamp = np.datetime64(at.replace(tzinfo=None), "ns")
    i = int(np.searchsorted(close_t, stamp, side="left"))
    if i >= len(close_t):
        i = len(close_t) - 1
    p[i:] = pv
    avail[i:] = np.maximum(avail[i:], stamp)
    return Reading(engine=P5, status=MEASURED, p=p, available=avail,
                   source=f"NEWS_EVENT_STREAM.json reactions (n={int(sum(n for _, n in hits))})",
                   n_basis=len(hits), why="the news ensemble's measured hit rate for this "
                                          "symbol and horizon, usable from the stream's `at`")


def _cot_series(ctx: Context, sym: str) -> tuple[list[tuple[datetime, float]], str]:
    rows = (ctx.cot.get("rows") or []) if isinstance(ctx.cot, dict) else []
    pts = []
    for r in rows:
        if isinstance(r, dict) and r.get("symbol") == sym:
            t = _parse_time(r.get("knowable_at"))
            v = _num(r.get("net_pct_oi"))
            if t is not None and v is not None:
                pts.append((t + timedelta(hours=23, minutes=59), v))
    if pts:
        return sorted(pts), "data/axes/cot.json (knowable_at-stamped)"
    if sym == "XAUUSD" and ctx.cot_gold is not None and len(ctx.cot_gold):
        g = ctx.cot_gold
        try:
            for _, r in g.iterrows():
                t = _parse_time(r.get("report_date"))
                oi = float(r.get("open_interest_all") or 0.0)
                if t is None or oi <= 0:
                    continue
                net = (float(r.get("noncomm_positions_long_all") or 0.0)
                       - float(r.get("noncomm_positions_short_all") or 0.0)) / oi
                pts.append((t + timedelta(days=3, hours=21), net))
        except (TypeError, ValueError):
            pts = []
        if pts:
            return sorted(pts), "data/cot_gold.parquet (report_date + 3d 21:00 UTC release pad)"
    return [], ""


def engine_p6(ctx: Context, sym: str, h: str, df: pd.DataFrame, close_t: np.ndarray) -> Reading:
    pts, src = _cot_series(ctx, sym)
    sge_n = 0
    if sym == "XAUUSD" and isinstance(ctx.sge, dict):
        sge_n = int(_num(ctx.sge.get("rows")) or 0)
    if len(pts) < 30:
        syms = sorted({str(r.get("symbol")) for r in ((ctx.cot or {}).get("rows") or [])
                       if isinstance(r, dict)}) if isinstance(ctx.cot, dict) else []
        why = (f"{sym}: no positioning series with >= 30 knowable_at-stamped rows "
               f"(cot.json covers {len(syms)} symbols; cot_gold.parquet "
               f"{'present' if ctx.cot_gold is not None else 'absent'}"
               + (f"; sge_premium {sge_n} rows < {PE.MIN_N_TABLE}" if sym == "XAUUSD" else "")
               + "; weather: no data plane in the tree)")
        return _unmeasured(P6, why, source="cot.json; cot_gold.parquet; sge_premium.json")
    stamps = np.array([np.datetime64(t.replace(tzinfo=None), "ns") for t, _ in pts])
    vals = pd.Series([v for _, v in pts], dtype=float)
    mu = vals.rolling(156, min_periods=26).mean()
    sd = vals.rolling(156, min_periods=26).std()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = ((vals - mu) / sd).to_numpy(dtype=float)
    z[~np.isfinite(z)] = np.nan
    pv = _sigmoid_arr(-0.5 * np.clip(z, -4, 4))
    pv[np.isnan(z)] = np.nan
    pos = np.searchsorted(stamps, close_t, side="right") - 1
    ok = pos >= 0
    p = np.full(len(close_t), np.nan)
    avail = close_t.copy()
    p[ok] = pv[pos[ok]]
    avail[ok] = np.maximum(close_t[ok], stamps[pos[ok]])
    n = int(np.isfinite(p).sum())
    if n == 0:
        return _unmeasured(P6, f"{sym}: positioning rows never overlap the bars", source=src)
    return Reading(engine=P6, status=MEASURED, p=p, available=avail, source=src, n_basis=n,
                   why="fade of a positioning extreme (z of net spec % of OI vs 156 weeks), "
                       "usable only from each row's knowable_at"
                       + (f"; sge_premium {sge_n} rows < {PE.MIN_N_TABLE}: UNMEASURED"
                          if sym == "XAUUSD" else ""))


ENGINE_FNS = {P1: engine_p1, P2: engine_p2, P3: engine_p3, P4: engine_p4, P5: engine_p5,
              P6: engine_p6}


# --------------------------------------------------------------------------- resolution
def _to_dt(ns: np.datetime64) -> datetime:
    return pd.Timestamp(ns).tz_localize("UTC").to_pydatetime()


def _replay(reading: Reading, sym: str, h: str, r_fwd: np.ndarray, close_t: np.ndarray,
            regime: np.ndarray) -> PE.Record:
    """Every bar the engine spoke on, stride-sampled to non-overlapping windows, paired with its
    outcome under the anti-lookahead rule."""
    if reading.p is None or reading.available is None:
        return PE.Record((), 0, 0)
    hb = HB[h]
    valid = np.isfinite(reading.p) & np.isfinite(r_fwd)
    idx = np.flatnonzero(valid)
    if len(idx) == 0:
        return PE.Record((), 0, 0)
    stride = max(hb, math.ceil(len(idx) / MAX_PAIRS))
    idx = idx[::stride]
    band = reading.band
    forecasts = [PE.ProbabilityForecast(engine=reading.engine, target=sym, horizon=h,
                                        at=_to_dt(close_t[i]),
                                        available_time=_to_dt(reading.available[i]),
                                        p=float(reading.p[i]), claim=reading.claim,
                                        regime=str(regime[i]))
                 for i in idx]
    outcomes: dict[datetime, float] = {}
    for i in idx:
        if reading.claim == PE.CLAIM_EXCEED:
            b = float(band[i]) if band is not None and np.isfinite(band[i]) else None
            outcomes[_to_dt(close_t[i])] = (1.0 if b is not None and abs(r_fwd[i]) > b
                                            else 0.0)
        else:
            outcomes[_to_dt(close_t[i])] = 1.0 if r_fwd[i] > 0 else 0.0
    return PE.resolved_pairs(forecasts, lambda f: outcomes.get(f.at))


def _ledger_pairs(ctx: Context, engine: str, sym: str, h: str, lc: np.ndarray,
                  close_t: np.ndarray) -> tuple[list[PE.Resolved], int]:
    """The lab's own forward record for engines that cannot be replayed: forecasts written on
    earlier passes, resolved against the bars once their horizon has elapsed."""
    hb = HB[h]
    out: list[PE.Resolved] = []
    pending = 0
    for row in ctx.ledger_rows:
        if (row.get("engine") != engine or row.get("target") != sym
                or row.get("horizon") != h):
            continue
        at = _parse_time(row.get("at"))
        avail = _parse_time(row.get("available_time"))
        pv = _num(row.get("p"))
        if at is None or avail is None or pv is None or avail > at:
            continue
        stamp = np.datetime64(at.replace(tzinfo=None), "ns")
        i = int(np.searchsorted(close_t, stamp, side="left"))
        if i >= len(close_t) or close_t[i] != stamp or i + hb >= len(close_t):
            pending += 1
            continue
        r = lc[i + hb] - lc[i]
        band = _num(row.get("band"))
        if row.get("claim") == PE.CLAIM_EXCEED:
            y = 1.0 if band is not None and abs(r) > band else 0.0
        else:
            y = 1.0 if r > 0 else 0.0
        out.append(PE.Resolved(p=PE.clip(pv), y=y, regime=str(row.get("regime") or ""), at=at))
    return out, pending


# --------------------------------------------------------------------------- per target
@dataclass
class EngineResult:
    reading: Reading
    record: PE.Record
    tables: dict[str, PE.CalibrationTable]
    p_now: float | None
    usable_now: bool
    available_now: datetime | None
    ledger_n: int = 0
    ledger_pending: int = 0

    def table_for(self, regime: str) -> tuple[PE.CalibrationTable | None, str]:
        t = self.tables.get(regime)
        if t is not None and t.status == MEASURED:
            return t, "regime"
        o = self.tables.get("overall")
        if o is not None and o.status == MEASURED:
            return o, "overall_fallback"
        return None, "none"


def _event_proximity(ctx: Context, sym: str, now: datetime) -> str:
    cal = ctx.calendar
    events = (cal.get("events") or []) if isinstance(cal, dict) else []
    if not events:
        return UNMEASURED
    best: float | None = None
    for ev in events:
        if not isinstance(ev, dict) or sym not in (ev.get("instruments") or []):
            continue
        t = _parse_time(ev.get("window_start_utc"))
        if t is None:
            continue
        dh = (t - now).total_seconds() / 3600.0
        if dh >= -1.0 and (best is None or dh < best):
            best = dh
    if best is None:
        return "none_scheduled"
    return "near" if best <= EVENT_NEAR_H else "far"


def _expression(expression: str, side: int, hb: int) -> tuple[str, dict[str, Any]]:
    ttl = max(12, 2 * hb)
    if expression == "continuation" or (expression == "exceed" and side > 0):
        return "momentum_volgate", {"mom_n": max(6, hb), "atr_n": 20, "vol_gate_q": 0.4,
                                    "ttl_bars": ttl, "rr": 1.8, "mom_thresh": 0.0012}
    if expression in ("reversal", "exceed"):
        return "mean_reversion_bollinger", {"bb_n": 20, "bb_k": 2.0, "atr_n": 20,
                                            "ttl_bars": ttl, "rr": 1.8}
    if expression == "positioning":
        return "cot_positioning", {"lookback_weeks": 156, "extreme_pct": 0.9, "atr_n": 20,
                                   "stop_atr": 3.0, "rr": 2.0, "ttl_bars": max(240, 2 * hb)}
    return "event_reaction", {"react_bars": 1, "atr_n": 20, "stop_atr": 1.5, "rr": 1.5,
                              "ttl_bars": max(6, hb), "fade": side < 0}


def _in_scope(ctx: Context, fam: str, sym: str) -> bool:
    scope = CELL_FAMILIES[fam]["scope"]
    cls = up._norm(_asset_class(ctx, sym))
    is_fx = sym[:3].upper() in FX_CCYS and sym[3:6].upper() in FX_CCYS and len(sym) == 6
    if scope == "all":
        return True
    if scope == "gold":
        return sym.upper().startswith("XAU")
    if scope == "fx_gold":
        return is_fx or sym.upper().startswith("XAU") or sym == "USDX"
    if scope == "commodity":
        return (any(k in cls for k in ("commod", "energ", "metal", "soft", "agri"))
                or sym.upper()[:3] in ("XAU", "XAG", "XTI", "XBR", "XNG"))
    if scope == "energy_agri":
        return (any(k in cls for k in ("energ", "soft", "agri"))
                or sym.upper()[:3] in ("XTI", "XBR", "XNG"))
    if scope == "index_fx":
        return is_fx or any(k in cls for k in ("index", "indice"))
    return True


CONFORMAL_MAX_AGE_H = 48.0
CONFORMAL_MIN_N = 50


def _conformal_gap(paths: Paths, sym: str, h: str, now: datetime) -> dict[str, Any]:
    """The sandbox conformal cell's measured coverage gap for (sym, h) -- a GUARDED hook: the
    file may be absent, stale, unreadable or thin, and each of those is UNMEASURED by name and
    changes nothing. Read-only; the cell (research/sandboxes/conformal_calibration.py) writes it
    on the sandbox_runner leg."""
    try:
        doc = _read_json(paths.conformal)
        if not isinstance(doc, dict):
            return {"status": UNMEASURED, "gap": None, "why": "no calibration file"}
        at = _parse_time(doc.get("at"))
        if at is None or (now - at) > timedelta(hours=CONFORMAL_MAX_AGE_H):
            return {"status": UNMEASURED, "gap": None,
                    "why": f"calibration older than {CONFORMAL_MAX_AGE_H:.0f}h"}
        row = ((doc.get("by_symbol") or {}).get(sym) or {}).get(h)
        if not isinstance(row, dict):
            return {"status": UNMEASURED, "gap": None, "why": f"no calibration for {sym}/{h}"}
        gap, n = _num(row, "coverage_gap"), _num(row, "n_test")
        if gap is None or n is None or n < CONFORMAL_MIN_N or not np.isfinite(gap):
            return {"status": UNMEASURED, "gap": None,
                    "why": f"gap {gap} on n {n} (need n >= {CONFORMAL_MIN_N})"}
        return {"status": MEASURED, "gap": round(float(gap), 6), "n_test": int(n),
                "coverage_measured": _num(row, "coverage_measured"),
                "engine": str(row.get("engine") or ""), "at": _iso(at), "why": ""}
    except Exception as exc:
        return {"status": UNMEASURED, "gap": None, "why": f"{type(exc).__name__}: {exc}"[:120]}


def _blend_uncertainty(ensemble_uncertainty: float | None, gap: float | None) -> float | None:
    """TWO-SIDED: the ensemble's pooled uncertainty moved halfway (in quadrature) toward the
    conformal cell's measured coverage gap. A gap below the ensemble's own term TIGHTENS the
    threshold, a gap above it WIDENS it; with no measured gap the ensemble's term stands, so
    the hook can never add a cap the evidence did not measure (GROWTH_GOVERNANCE Rule 1)."""
    if gap is None:
        return None
    if ensemble_uncertainty is None:
        return float(gap)
    return float(math.sqrt(0.5 * ensemble_uncertainty ** 2 + 0.5 * gap ** 2))


def _conformal_direction(before: float | None, after: float | None) -> str:
    if after is None or before is None:
        return UNMEASURED
    if abs(after - before) < 1e-9:
        return "unchanged"
    return "tightened" if after < before else "widened"


def _study_target(ctx: Context, sym: str, state: dict[str, Any], horizons: tuple[str, ...],
                  ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Every engine, every horizon, for one target: readings, curves, the ensemble against the
    market-implied state, and the cells the families produce. Returns (target report, cells,
    forecasts to ledger)."""
    df = ctx.bars(sym)
    now = ctx.now
    if df is None:
        return ({"status": UNMEASURED, "why": f"no H1 bars for {sym} (>= {MIN_BARS} needed)"},
                [], [])
    lc = np.log(df["close"].to_numpy(dtype=float))
    close_t = _close_times(df)
    axes = _regime_axes(df)
    regime_now = str(axes["regime"][-1])
    cost = _round_trip_cost(ctx, sym, df)
    prev_readings = ((state.get("last_readings") or {}).get(sym) or {})
    target: dict[str, Any] = {
        "status": MEASURED, "asset_class": _asset_class(ctx, sym), "lane": up.lane(sym),
        "n_bars": len(df), "last_bar_close": _iso(_to_dt(close_t[-1])),
        "regime_now": regime_now, "round_trip_cost": round(cost, 8),
        "axes_now": {"trend": str(axes["trend"][-1]), "vol": str(axes["vol"][-1]),
                     "session": str(axes["session"][-1]),
                     "liquidity": str(axes["liquidity"][-1]),
                     "event_proximity": _event_proximity(ctx, sym, now)},
        "drivers": [f"{d}({'+' if s > 0 else '-'})" for d, s, _ in _drivers(ctx, sym)],
        "horizons": {},
    }
    cells: list[dict[str, Any]] = []
    to_ledger: list[dict[str, Any]] = []
    for h in horizons:
        hb = HB[h]
        r_fwd = _fwd_return(lc, hb)
        results: dict[str, EngineResult] = {}
        for name, fn in ENGINE_FNS.items():
            reading = fn(ctx, sym, h, df, close_t)
            record = _replay(reading, sym, h, r_fwd, close_t, axes["regime"])
            pairs = list(record.pairs)
            ledger_n = ledger_pending = 0
            if len(pairs) < PE.MIN_N_TABLE:
                extra, ledger_pending = _ledger_pairs(ctx, name, sym, h, lc, close_t)
                pairs.extend(extra)
                ledger_n = len(extra)
            tables = PE.curves_by_regime(pairs) if pairs else {}
            p_now: float | None = None
            avail_now: datetime | None = None
            usable_now = False
            if reading.p is not None and reading.available is not None \
                    and np.isfinite(reading.p[-1]):
                p_now = float(reading.p[-1])
                avail_now = _to_dt(reading.available[-1])
                usable_now = avail_now <= now
            results[name] = EngineResult(reading, record, tables, p_now, usable_now, avail_now,
                                         ledger_n, ledger_pending)
            if p_now is not None and usable_now:
                band = reading.band
                to_ledger.append({"engine": name, "target": sym, "horizon": h,
                                  "at": _iso(_to_dt(close_t[-1])),
                                  "available_time": _iso(avail_now),
                                  "p": round(p_now, 6), "claim": reading.claim,
                                  "regime": regime_now,
                                  "band": (round(float(band[-1]), 8) if band is not None
                                           and np.isfinite(band[-1]) else None),
                                  "written_at": _iso(now)})
        # the market-implied state: the instrument's own recent distribution at this horizon
        recent = r_fwd[-(MARKET_WINDOW + hb):-hb] if len(r_fwd) > MARKET_WINDOW + hb \
            else r_fwd[np.isfinite(r_fwd)]
        market = PE.market_implied([float(x) for x in recent if np.isfinite(x)], cost=cost)
        readings_up = {n: r.p_now for n, r in results.items()
                       if r.p_now is not None and r.usable_now
                       and r.reading.claim == PE.CLAIM_UP}
        tables_now: dict[str, PE.CalibrationTable | None] = {}
        table_basis: dict[str, str] = {}
        for n, r in results.items():
            t, basis = r.table_for(regime_now)
            tables_now[n] = t
            table_basis[n] = basis
        ens = PE.ensemble(readings_up, tables_now)
        member_regime_tables = [results[m].tables.get(regime_now) for m in ens.members]
        if ens.members and all(t is not None and t.status == MEASURED
                               for t in member_regime_tables):
            buffer = PE.REGIME_BUFFER_BASE + sum(float(t.ece or 0.0)
                                                 for t in member_regime_tables
                                                 if t is not None) / len(member_regime_tables)
        else:
            buffer = PE.regime_buffer(None)
        conf = _conformal_gap(ctx.paths, sym, h, now)
        unc = _blend_uncertainty(ens.uncertainty, conf.get("gap"))
        dis = PE.dislocation(ens, market, uncertainty=unc, regime_buffer=buffer)
        con = PE.consensus(dict(readings_up))
        # cross-asset confirmation: does the driver reading agree with the ensemble's side?
        p4 = results[P4].p_now if results[P4].usable_now else None
        if dis.side == 0 or p4 is None:
            confirmation = UNMEASURED if p4 is None else "no_side"
        else:
            confirmation = "confirmed" if (p4 - 0.5) * dis.side > 0 else "contradicted"
        # who leads whom, P4 against P1, on the replayed series
        lead_doc: dict[str, Any] = {"status": UNMEASURED}
        p1r, p4r = results[P1].reading.p, results[P4].reading.p
        if p1r is not None and p4r is not None:
            both = np.isfinite(p1r) & np.isfinite(p4r)
            ii = np.flatnonzero(both)[-500:]
            if len(ii) >= PE.MIN_N_LEAD:
                ld = PE.lead([float(p1r[i]) for i in ii], [float(p4r[i]) for i in ii],
                             max_lag=max(1, hb))
                lead_doc = {**ld.as_dict(), "a": P1, "b": P4}
        hdoc: dict[str, Any] = {
            "market_implied": market.as_dict(),
            "ensemble": ens.as_dict(), "table_basis": table_basis,
            "regime_buffer": round(buffer, 6),
            "dislocation": dis.as_dict(), "fired": dis.fired, "why": dis.why,
            "consensus": con.as_dict(), "cross_asset_confirmation": confirmation,
            "lead_P1_vs_P4": lead_doc,
            "conformal": {**conf, "uncertainty_used": None if unc is None else round(unc, 6),
                          "ensemble_uncertainty": (None if ens.uncertainty is None
                                                   else round(ens.uncertainty, 6)),
                          "direction": _conformal_direction(ens.uncertainty, unc)},
            "engines": {},
        }
        for n, r in results.items():
            ov = r.tables.get("overall")
            reg = r.tables.get(regime_now)
            hdoc["engines"][n] = {
                "status": r.reading.status, "why": r.reading.why, "source": r.reading.source,
                "claim": r.reading.claim, "p_now": None if r.p_now is None else round(r.p_now, 6),
                "available_now": _iso(r.available_now), "usable_now": r.usable_now,
                "quantiles_now": r.reading.quantiles,
                "record": {**r.record.as_dict(), "ledger_resolved": r.ledger_n,
                           "ledger_pending": r.ledger_pending},
                "calibration_overall": ov.as_dict() if ov is not None else {"status": UNMEASURED},
                "calibration_regime": ({"regime": regime_now, "n": reg.n, "status": reg.status,
                                        "ece": None if reg.ece is None else round(reg.ece, 5),
                                        "brier": (None if reg.brier is None
                                                  else round(reg.brier, 5))}
                                       if reg is not None else {"regime": regime_now,
                                                                "status": UNMEASURED}),
                "regimes_measured": sorted(k for k, t in r.tables.items()
                                           if t.status == MEASURED and k != "overall"),
            }
        target["horizons"][h] = hdoc
        # ---- the cell families, cross-bred with the axes, at this horizon
        axes_now = {**target["axes_now"], "regime": regime_now,
                    "cross_asset_confirmation": confirmation, "horizon": h}
        prev_h = (prev_readings.get(h) or {})
        for fam, spec in CELL_FAMILIES.items():
            if not _in_scope(ctx, fam, sym):
                continue
            key = f"{fam}|{sym}|{h}|{regime_now}|{axes_now['session']}"
            cell: dict[str, Any] = {"cell": key, "family": fam, "symbol": sym, "horizon": h,
                                    "axes": axes_now, "status": UNMEASURED, "fired": False,
                                    "why": "", "value": 0.0}
            if spec.get("needs") == "weather data plane":
                cell["why"] = ("weather-vs-energy/agriculture needs a weather data plane; none "
                               "exists in this tree (Multimodal Physical-World Perception Swarm "
                               "not present) -- UNMEASURED by name")
                cells.append(cell)
                continue
            if fam == "rates_vs_fx":
                rd = engine_p4(ctx, sym, h, df, close_t, only=RATES_DRIVER)
                if rd.status != MEASURED or rd.p is None or not np.isfinite(rd.p[-1]):
                    cell["why"] = rd.why
                    cells.append(cell)
                    continue
                sub_read = {P4: float(rd.p[-1])}
            elif fam == "options_vs_spot":
                r2 = results[P2]
                if r2.reading.status != MEASURED or r2.p_now is None:
                    cell["why"] = r2.reading.why
                    cells.append(cell)
                    continue
                t2, _ = r2.table_for(regime_now)
                ens2 = PE.ensemble({P2: r2.p_now}, {P2: t2})
                implied = PE.MarketImplied(p=EXCEED_1SD, quantiles=r2.reading.quantiles,
                                           cost_probability=market.cost_probability,
                                           n=market.n, status=market.status, why=market.why)
                d2 = PE.dislocation(ens2, implied, regime_buffer=buffer)
                _finish_cell(cell, d2, ens2, spec["expression"], hb, state, {P2: r2.p_now},
                             EXCEED_1SD)
                cells.append(cell)
                continue
            elif fam == "under_over_reaction_after_probability_shock":
                shocked = {n: (prev_h.get(n), v) for n, v in readings_up.items()
                           if PE.shock(_num(prev_h.get(n)), v)}
                if not shocked:
                    cell["status"] = "NO_SHOCK"
                    cell["why"] = (f"no engine moved > {PE.SHOCK_THRESHOLD} since the last "
                                   "reading" if prev_h else "no previous reading in the state "
                                   "file: the first pass cannot see a shock")
                    cells.append(cell)
                    continue
                sub_read = {n: v for n, (_, v) in shocked.items()}
                cell["shock"] = {n: {"from": pv, "to": round(v, 6)}
                                 for n, (pv, v) in shocked.items()}
            elif fam == "consensus_dispersion":
                sub_read = dict(readings_up)
            else:
                sub_read = {e: readings_up[e] for e in spec["engines"] if e in readings_up}
            if not sub_read:
                cell["why"] = "; ".join(
                    f"{e}: {results[e].reading.why}" for e in spec["engines"]
                    if e in results and results[e].reading.status != MEASURED) \
                    or "no engine of this family has a usable reading now"
                cells.append(cell)
                continue
            sub_tables = {e: tables_now.get(e) for e in sub_read}
            sub_ens = PE.ensemble(sub_read, sub_tables)
            sub_dis = PE.dislocation(sub_ens, market, regime_buffer=buffer)
            expression = spec["expression"]
            if fam == "consensus_dispersion":
                disp = PE.dispersion(list(sub_ens.members.values())) if sub_ens.members else None
                cell["dispersion"] = None if disp is None else round(disp, 6)
                if disp is None or disp <= DISPERSION_FIRE:
                    sub_dis = PE.Dislocation(sub_dis.edge, sub_dis.threshold, False, 0,
                                             sub_dis.costs, sub_dis.uncertainty, buffer,
                                             sub_dis.status,
                                             f"dispersion {disp} <= {DISPERSION_FIRE}: the "
                                             "engines agree, there is no dispersion cell")
            if fam == "under_over_reaction_after_probability_shock" and sub_dis.fired:
                moved = float(lc[-1] - lc[-2]) if len(lc) > 1 else 0.0
                expression = "reversal" if moved * sub_dis.side > 0 and abs(moved) > cost \
                    else "continuation"
                cell["reaction"] = ("over" if expression == "reversal" else "under")
            _finish_cell(cell, sub_dis, sub_ens, expression, hb, state, sub_read, market.p)
            cells.append(cell)
    return target, cells, to_ledger


def _finish_cell(cell: dict[str, Any], dis: PE.Dislocation, ens: PE.Ensemble, expression: str,
                 hb: int, state: dict[str, Any], readings: dict[str, float],
                 market_p: float | None) -> None:
    cell["status"] = dis.status
    cell["fired"] = dis.fired
    cell["why"] = dis.why
    cell["dislocation"] = dis.as_dict()
    cell["ensemble"] = ens.as_dict()
    cell["market_p"] = None if market_p is None else round(market_p, 6)
    donated_at = (state.get("donated") or {}).get(cell["cell"])
    novelty = 0.25 if donated_at else 1.0
    cell["value"] = PE.value_of_cell(edge=dis.edge, threshold=dis.threshold,
                                     dispersion=PE.dispersion(list(readings.values())),
                                     n_engines=ens.n, novelty=novelty)
    if dis.fired:
        family, params = _expression(expression, dis.side, hb)
        cell["expression"] = {"family": family, "params": params, "mode": expression}


# --------------------------------------------------------------------------- donations
def _donation_row(cell: dict[str, Any], now: datetime) -> dict[str, Any]:
    sym, h, fam = cell["symbol"], cell["horizon"], cell["family"]
    ex = cell["expression"]
    dis = cell["dislocation"]
    members = list((cell.get("ensemble") or {}).get("members") or {})
    regime = cell["axes"]["regime"]
    exact_rule = (
        f"at the close of an H1 bar on {sym} when the calibrated ensemble {members} says "
        f"P(up over {h}) = {(cell.get('ensemble') or {}).get('p')} against the instrument's own "
        f"trailing-{MARKET_WINDOW}-bar frequency {cell.get('market_p')} -- an edge of "
        f"{dis['edge']} beyond costs + uncertainty + regime buffer = {dis['threshold']} -- in "
        f"regime {regime}, session {cell['axes']['session']}, run "
        f"{ex['family']}({json.dumps(ex['params'], sort_keys=True)}) for {HB[h]} bars, "
        f"side {dis['side']}")
    falsifier = (
        f"over >= {PE.MIN_N_TABLE} fired instances {sym}'s forward {h} return conditioned on the "
        "fired state does not separate from its unconditional distribution after costs "
        "(t < 2), or the members' reliability curve in this regime drifts to ECE > 0.10, or "
        "the market-implied p moves to within the threshold of the ensemble before the "
        "horizon elapses (the market was right and the ensemble late)")
    return {
        "kind": "dislocation_cell", "source": "dislocation_lab", "cell": cell["cell"],
        "cell_family": fam, "symbol": sym, "symbols": [sym], "family": ex["family"],
        "params": ex["params"], "horizon": h, "side": dis["side"],
        "title": f"{fam} dislocation on {sym} at {h} ({ex['mode']})",
        "mechanism": (f"{fam}: the calibrated {members} ensemble disagrees with {sym}'s "
                      f"market-implied state by {dis['edge']} (threshold {dis['threshold']}); "
                      f"expressed as {ex['mode']} through {ex['family']}"),
        "conditioner": f"{fam}: ensemble p {(cell.get('ensemble') or {}).get('p')} vs market p "
                       f"{cell.get('market_p')} in {regime}",
        "exact_rule": exact_rule, "falsifier": falsifier,
        "edge": dis["edge"], "threshold": dis["threshold"], "engines": members,
        "axes": cell["axes"], "value": cell["value"], "at": _iso(now),
    }


def _record_discovery(row: dict[str, Any], conn: Any) -> str:
    did, _ = R.record_discovery(
        source_id=f"dislocation_lab:{row['cell_family']}", source_type="dislocation_cell",
        mechanism=str(row["mechanism"])[:400], origin="DESK", generator="dislocation_lab",
        assets=[row["symbol"]], sessions=[row["axes"]["session"]], horizons=[row["horizon"]],
        regimes=[row["axes"]["regime"]], information="probability",
        economic_rationale=("several independently calibrated probability engines disagree with "
                            "what the instrument prices; net of costs, model uncertainty and a "
                            "regime buffer, one side holds information the other has not priced"),
        exact_rule_if_known=str(row["exact_rule"])[:1000],
        required_data=[f"{row['symbol']}_H1.parquet", "reports/DISLOCATION_LAB.json"],
        falsifier=str(row["falsifier"])[:600], novelty=0.6,
        confidence=min(0.9, 0.3 + 2.0 * abs(float(row["edge"] or 0.0))),
        payload=dict(row), conn=conn)
    return str(did)


# --------------------------------------------------------------------------- the pass
def _hunt_universe(ctx: Context) -> list[str]:
    syms = sorted(p.stem.removesuffix("_H1") for p in ctx.paths.universe.glob("*_H1.parquet"))
    return [s for s in syms if s not in CORE_TARGETS and up.lane(s) == up.HYPOTHESIS]


def run_pass(*, budget_s: float = 900.0, dry_run: bool = False, desk: Path | None = None,
             now: datetime | None = None, horizons: tuple[str, ...] = HORIZONS,
             max_targets: int = MAX_TARGETS_PER_PASS) -> dict[str, Any]:
    started = time.monotonic()
    paths = Paths(desk or DESK)
    ctx = Context(paths, now or _now())
    state = _read_json(paths.state) if paths.state.exists() else None
    state = state if isinstance(state, dict) else {}
    core = [s for s in CORE_TARGETS if ctx.has_bars(s)]
    hunt = _hunt_universe(ctx)
    offset = int(state.get("cursor") or 0) % max(1, len(hunt)) if hunt else 0
    rotated = hunt[offset:] + hunt[:offset]
    queue = core + [s for s in rotated if s not in core]
    queue = queue[:max(1, max_targets)]
    targets: dict[str, Any] = {}
    cells: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    reached: list[str] = []
    stopped = False
    for sym in queue:
        if time.monotonic() - started > budget_s:
            stopped = True
            break
        tdoc, tcells, tledger = _study_target(ctx, sym, state, horizons)
        targets[sym] = tdoc
        cells.extend(tcells)
        ledger_rows.extend(tledger)
        reached.append(sym)
    hunt_reached = [s for s in reached if s in hunt]
    new_cursor = ((hunt.index(hunt_reached[-1]) + 1) % len(hunt)) if hunt_reached else offset
    # ---- V(a) schedule and donations
    values = {c["cell"]: float(c.get("value") or 0.0) for c in cells
              if c["status"] == MEASURED}
    scheduled = PE.schedule(values, capacity=MAX_CELLS_PER_PASS)
    sched_set = set(scheduled)
    fired = [c for c in cells if c["cell"] in sched_set and c.get("fired")]
    fired.sort(key=lambda c: -float(c.get("value") or 0.0))
    donations = [_donation_row(c, ctx.now) for c in fired[:MAX_DONATIONS]]
    donation_path: Path | None = None
    discovery_ids: list[str] = []
    if donations and not dry_run:
        donation_path = paths.intel / f"discoveries_{ctx.now.strftime('%Y%m%d_%H%M%S')}.json"
        _atomic(donation_path, {"source": "dislocation_lab", "generated_at": _iso(ctx.now),
                                "rule": RULE, "discoveries": donations})
        conn = R.connect()
        try:
            for row in donations:
                try:
                    discovery_ids.append(_record_discovery(row, conn))
                except Exception as exc:
                    discovery_ids.append(f"ERROR:{type(exc).__name__}")
        finally:
            conn.close()
    # ---- per-engine roll-up
    engines: dict[str, Any] = {}
    for name in ENGINES:
        measured_targets: list[str] = []
        unmeasured_targets: dict[str, str] = {}
        n_forecasts = withheld = ledger_n = pending = 0
        calib: dict[str, Any] = {}
        anomalies: dict[str, Any] = {}
        leads: dict[str, Any] = {}
        for sym, tdoc in targets.items():
            for h, hdoc in (tdoc.get("horizons") or {}).items():
                e = hdoc["engines"][name]
                rec = e["record"]
                n_forecasts += int(rec["n"])
                withheld += int(rec["withheld_lookahead"])
                ledger_n += int(rec["ledger_resolved"])
                pending += int(rec["ledger_pending"])
                if e["status"] == MEASURED:
                    if sym not in measured_targets:
                        measured_targets.append(sym)
                    calib.setdefault(sym, {})[h] = {
                        "overall": {k: e["calibration_overall"].get(k)
                                    for k in ("n", "status", "ece", "brier", "base_rate")},
                        "bins": e["calibration_overall"].get("bins"),
                        "regime_now": e["calibration_regime"],
                        "regimes_measured": e["regimes_measured"]}
                elif sym not in unmeasured_targets:
                    unmeasured_targets[sym] = e["why"]
                z = (hdoc["consensus"].get("anomalies") or {}).get(name)
                if z is not None:
                    anomalies.setdefault(sym, {})[h] = z
                if name in (P1, P4) and hdoc["lead_P1_vs_P4"].get("status") == MEASURED:
                    leads.setdefault(sym, {})[h] = hdoc["lead_P1_vs_P4"]
        engines[name] = {
            "status": MEASURED if measured_targets else UNMEASURED,
            "n_forecasts": n_forecasts, "withheld_lookahead": withheld,
            "forward_ledger": {"resolved": ledger_n, "pending": pending},
            "targets_measured": measured_targets, "targets_unmeasured": unmeasured_targets,
            "calibration": calib, "leads": leads, "anomalies": anomalies,
        }
    families: dict[str, Any] = {}
    for fam in CELL_FAMILIES:
        fc = [c for c in cells if c["family"] == fam]
        why = next((c["why"] for c in fc if c["status"] != MEASURED and c["why"]), "")
        needs = CELL_FAMILIES[fam].get("needs")
        if not why and needs:
            why = (f"needs a {needs}; none exists in this tree (Multimodal Physical-World "
                   f"Perception Swarm not present) -- UNMEASURED by name")
        families[fam] = {"n_cells": len(fc),
                         "n_measured": sum(1 for c in fc if c["status"] == MEASURED),
                         "n_unmeasured": sum(1 for c in fc if c["status"] == UNMEASURED),
                         "n_scheduled": sum(1 for c in fc if c["cell"] in sched_set),
                         "n_fired": sum(1 for c in fc if c.get("fired")),
                         "why_sample": why[:300]}
    report: dict[str, Any] = {
        "at": _iso(ctx.now), "rule": RULE, "dry_run": bool(dry_run),
        "budget": {"budget_s": float(budget_s),
                   "elapsed_s": round(time.monotonic() - started, 2), "stopped": stopped,
                   "targets_reached": reached,
                   "targets_not_reached": [s for s in queue if s not in reached],
                   "hunt_universe": len(hunt), "cursor": new_cursor},
        "sources": ctx.sources,
        "engines": engines,
        "unmeasured_engines": [n for n in ENGINES if engines[n]["status"] != MEASURED],
        "targets": targets,
        "cell_families": families,
        "value_schedule": [{"cell": k, "value": values[k]} for k in scheduled[:40]],
        "cells": [c for c in cells if c["cell"] in sched_set] + [
            {k: c[k] for k in ("cell", "family", "symbol", "horizon", "status", "why")}
            for c in cells if c["cell"] not in sched_set][:400],
        "n_cells": len(cells),
        "donated": {"n": len(donations), "path": str(donation_path) if donation_path else None,
                    "cells": [d["cell"] for d in donations]},
        "discoveries": len([d for d in discovery_ids if not d.startswith("ERROR")]),
        "discovery_errors": [d for d in discovery_ids if d.startswith("ERROR")],
        "forward_ledger": {"rows_written": 0 if dry_run else len(ledger_rows),
                           "path": str(paths.ledger)},
        "allocates_capital": False,
    }
    if not dry_run:
        _atomic(paths.report, report)
        last_readings: dict[str, Any] = {}
        for sym, tdoc in targets.items():
            for h, hdoc in (tdoc.get("horizons") or {}).items():
                last_readings.setdefault(sym, {})[h] = {
                    n: e["p_now"] for n, e in hdoc["engines"].items()
                    if e["p_now"] is not None and e["usable_now"]
                    and e["claim"] == PE.CLAIM_UP}
        donated = dict(state.get("donated") or {})
        for d in donations:
            donated[d["cell"]] = _iso(ctx.now)
        _atomic(paths.state, {"at": _iso(ctx.now), "cursor": new_cursor,
                              "last_readings": {**(state.get("last_readings") or {}),
                                                **last_readings},
                              "donated": donated})
        _append_ledger(paths.ledger, ledger_rows)
    return report


def _append_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
    try:
        lines = path.read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return
    if len(lines) > LEDGER_KEEP + 10_000:
        tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
        tmp.write_text("\n".join(lines[-LEDGER_KEEP:]) + "\n", encoding="utf-8")
        os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the probability and fair-value dislocation lab")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    ap.add_argument("--max-targets", type=int, default=MAX_TARGETS_PER_PASS)
    a = ap.parse_args(argv)
    rep = run_pass(budget_s=float(a.budget_s), dry_run=bool(a.dry_run),
                   max_targets=int(a.max_targets))
    eng = {k: v["status"] for k, v in rep["engines"].items()}
    fired = sum(f["n_fired"] for f in rep["cell_families"].values())
    print(f"dislocation_lab: targets={len(rep['targets'])} cells={rep['n_cells']} "
          f"fired={fired} donated={rep['donated']['n']} discoveries={rep['discoveries']} "
          f"engines={eng} elapsed={rep['budget']['elapsed_s']}s"
          f"{' (dry run: nothing written)' if a.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
