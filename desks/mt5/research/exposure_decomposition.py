"""HIERARCHICAL EXPOSURE DECOMPOSITION -- what the book is actually betting on, by name.

Forty LIVE sleeves is not forty bets. Eight of them are EURCHF, four are AUDUSD, and every short
cross in the list is the same long-dollar trade wearing a different ticker. That duplication is
not free and it is not in the sleeve list: correlated bets share their drawdowns, so the book's
GEOMETRIC growth falls with the crowding while its arithmetic mean sits still. A desk that
believes it holds forty independent bets and holds four sizes its heat for forty and compounds
like four. The duplication lives BETWEEN the rows, which is why no per-sleeve report shows it.

So this reads every LIVE sleeve and every open position, regresses its instrument's daily returns
on factors built from THE DESK'S OWN BARS (a dollar basket of the six majors, gold, oil, an
equity index, a realised-vol state, a bond CFD, a commodity basket, a 12-week momentum factor of
the instrument's own asset class, FRED's daily series) plus two characteristics the desk holds as
data rather than as a tape (carry from the broker's swap table, liquidity from the measured
spread surface), and reports the book's NET loading on each. Then the part that earns the module:
pairs pointing the same way (cosine >= 0.8) are named as ONE bet with the heat they share, and
the effective number of independent factor bets is reported as (sum|e|)^2 / sum e^2 -- the
concentration arithmetic the desk uses everywhere else. Both are taken on loadings divided by the
book's RMS loading per factor, because an angle between mixed units is a UNIT CHOICE and not a
finding: carry sits on a +-3 clip and an FX beta near 0.2, so the raw angle is decided by the
swap table alone. Measured here first: 235 raw pairs, every one shared via carry and liquidity;
scaled, 155, and they name trend, usd and rates instead.

WHAT IS MEASURED AND WHAT IS ASSUMED, kept apart. A factor with no data on this box is
`unmeasured: true` and named in `unmeasured` -- never a zero loading, because a zero loading is a
claim and an absent series is not (L1.28a). A sleeve whose registry row carries no `side` cannot
be signed: it is computed at +1 and listed as `sleeve_side:`, so every NET number is conditional
on that and the ABSOLUTE ones are not. Betas are univariate by design -- the factors are
collinear (gold IS most of the commodity basket here) and a ten-column joint fit on 120 days
returns coefficients that flip sign on a week of new data; that fit runs once, for `r2` alone.

NOTHING HERE SIZES, CAPS, VETOES, SHRINKS OR GATES ANYTHING. Duplicate heat NAMED is not
duplicate heat FORBIDDEN: a risk reduction must first prove it raises robust forward E[log W],
and this proves nothing of the kind -- it makes the shared bet visible so the allocator's own
arithmetic can see what it is buying. A map, never a limit.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _entry in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

SOURCE = "exposure_decomposition"
LOOKBACK_DAYS = 250           # the tape each factor is built from
WINDOW = 120                  # the rolling OLS window, in common daily observations
MIN_OBS = 30                  # below this an instrument is UNMEASURED, never a zero beta
RV_WINDOW = 20                # the realised-vol state
TREND_WINDOW = 60             # 12 weeks of trading days
COSINE_DUP = 0.8              # same direction in factor space, therefore one bet
MAX_PAIRS = 200               # the report LISTS the worst; the count is always exact
CARRY_CLIP = 3.0
STALE_DAYS = 30               # a factor whose tape stopped this far behind the rest is named
TIMEFRAMES = ("H1", "D1", "H4", "M15")

#: The dollar basket, signed so + is a STRONGER dollar. EURUSD up is the dollar down.
USD_LEGS: tuple[tuple[str, float], ...] = (
    ("EURUSD", -1.0), ("GBPUSD", -1.0), ("AUDUSD", -1.0),
    ("USDJPY", 1.0), ("USDCAD", 1.0), ("USDCHF", 1.0))
GOLD_SYMBOLS = ("XAUUSD",)
OIL_SYMBOLS = ("XTIUSD", "XBRUSD", "USOIL", "UKOIL", "WTI", "BRENT")
EQUITY_SYMBOLS = ("US500", "SPX500", "NAS100", "US30", "GER40")
VOL_SYMBOLS = ("VIX", "VIXUSD", "VOLX")
RATES_SYMBOLS = ("UST10Y", "US10Y", "UST05Y", "UKGILT", "BUND")
COMMODITY_LEGS = ("XAUUSD", "XAGUSD", "XTIUSD", "XBRUSD")
GROWTH_SERIES = ("T10Y2Y", "DGS10", "DGS2")
INFLATION_SERIES = ("T10YIE", "T5YIE")
RETURN_FACTORS = ("usd", "gold", "oil", "equity_beta", "vol", "rates",
                  "growth", "inflation", "commodities", "trend")
CHARACTERISTIC_FACTORS = ("carry", "liquidity")
FACTORS = RETURN_FACTORS + CHARACTERISTIC_FACTORS
#: Which basket a class's momentum factor is built on. DECLARED, never inferred: FX has no market
#: portfolio, and the dollar is the closest thing to one this desk trades.
TREND_BASE = {"Forex": "usd", "Forex Exotics": "usd", "Commodities": "commodities",
              "Soft Commodity": "commodities", "Energy": "oil", "Indices": "equity_beta",
              "Equities": "equity_beta", "Bonds": "rates", "Crypto": "equity_beta"}
RULE = (f"Univariate OLS betas on the last {WINDOW} common daily observations of the last "
        f"{LOOKBACK_DAYS} days; r2 from one joint fit of the same return factors. Sleeve exposure "
        "= sign(side) x beta x risk_frac; position exposure = signed stop-risk/equity x beta. "
        "carry and liquidity are CHARACTERISTICS (broker swap table, measured spread surface), "
        "not regressions; liquidity is unsigned because an illiquid short is as exposed as an "
        "illiquid long. An absent factor is UNMEASURED, never a zero loading; a sleeve with no "
        "declared side is computed at +1 and named in unmeasured, so net numbers are conditional "
        "on that and absolute ones are not. The duplicate cosine and n_eff_factor_bets divide by "
        "factor_scale (the book's RMS loading per factor) because an angle between mixed units is "
        "a unit choice; n_eff_factor_bets_unscaled is the raw one. r2 is fitted over r2_factors, "
        f"the factors covering that instrument's own window; a factor more than {STALE_DAYS} days "
        "behind the freshest tape is listed in stale_factors and its beta is that old. NOTHING "
        "HERE CAPS OR SIZES.")

_BARS: dict[tuple[str, str], pd.Series | None] = {}


def _at(*parts: str) -> Path:
    """Every path hangs off DESK and is resolved at CALL time: one monkeypatch moves the organ."""
    return DESK.joinpath(*parts)


def report_path() -> Path:
    return _at("reports", "EXPOSURE_DECOMPOSITION.json")


def _json(path: Path) -> dict[str, Any]:
    """Tolerant reader: a BOM, a half-written file or an absent one all read as {}."""
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:        # a read-only destination is WinError 5 here, not EACCES
        with contextlib.suppress(OSError):
            path.chmod(0o644)
        os.replace(tmp, path)


# Bars -> daily returns

def _frame_to_close(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        col = next((c for c in ("time", "date", "timestamp", "Time", "Date") if c in df), None)
        if col is None:
            return None
        df = df.set_index(pd.DatetimeIndex(pd.to_datetime(df[col], utc=True, errors="coerce")))
    if not isinstance(df.index, pd.DatetimeIndex):
        return None
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    close = next((c for c in ("close", "Close", "CLOSE") if c in df.columns), None)
    if close is None:
        return None
    ser = pd.to_numeric(df[close], errors="coerce").dropna()
    daily = ser[ser > 0].resample("1D").last().dropna()
    return daily if not daily.empty else None


def load_bars(symbol: str) -> pd.Series | None:
    """Daily closes from the highest-resolution file on disk, cached per (desk root, symbol)."""
    key = (str(DESK), str(symbol))
    if key in _BARS:
        return _BARS[key]
    out: pd.Series | None = None
    for tf, suffix in ((t, x) for t in TIMEFRAMES for x in (".parquet", ".csv")):
        path = _at("data", "universe", f"{symbol}_{tf}{suffix}")
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path) if suffix == ".parquet" else pd.read_csv(path)
        except Exception:                          # a corrupt bar file is data, not a crash
            continue
        out = _frame_to_close(frame)
        if out is not None and len(out) > 3:
            break
        out = None
    _BARS[key] = out
    return out


def daily_returns(symbol: str) -> pd.Series | None:
    """Log daily returns, or None when the instrument has too little tape to measure."""
    close = load_bars(symbol)
    ret = None if close is None else np.log(close).diff().dropna()
    return ret if ret is not None and len(ret) >= MIN_OBS else None


def _basket(legs: Sequence[tuple[str, float]]) -> tuple[pd.Series | None, list[str]]:
    """Equal-weight signed average of whichever legs have bars. A partial basket is honest."""
    frames = {sym: ret * sign for sym, sign in legs
              if (ret := daily_returns(sym)) is not None}
    if not frames:
        return None, []
    out = pd.concat(frames.values(), axis=1).mean(axis=1).dropna()
    return (out if len(out) >= MIN_OBS else None), sorted(frames)


def _first_with_bars(symbols: Sequence[str]) -> tuple[pd.Series | None, str | None]:
    hits = ((daily_returns(s), s) for s in symbols)
    return next(((r, s) for r, s in hits if r is not None), (None, None))


def _pairs_of(points: Any) -> list[tuple[Any, Any]]:
    """Every dated shape the desk's FRED writers use: {date: v}, [{date, value}], [[d, v]]."""
    if isinstance(points, dict):
        return list(points.items())
    out: list[tuple[Any, Any]] = []
    for item in points if isinstance(points, list) else []:
        if isinstance(item, dict):
            out.append((next((item[k] for k in ("date", "d", "t", "time") if k in item), None),
                        next((item[k] for k in ("value", "v", "x") if k in item), None)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append((item[0], item[1]))
    return out


def _fred_points(names: Sequence[str]) -> tuple[pd.Series | None, str | None]:
    """A daily FRED state series, first-differenced so a return regression can read it."""
    for path in (_at("data", "fred_macro.json"), _at("data", "axes", "fred.json")):
        series = _json(path).get("series")
        for name in names if isinstance(series, dict) else ():
            row = series.get(name)
            pairs = _pairs_of(row.get("points") if isinstance(row, dict) else row)
            if len(pairs) < MIN_OBS + 1:
                continue
            idx = pd.DatetimeIndex(pd.to_datetime([q[0] for q in pairs], utc=True,
                                                  errors="coerce"))
            vals = pd.to_numeric(pd.Series([q[1] for q in pairs]), errors="coerce")
            ser = pd.Series(vals.to_numpy(), index=idx).dropna().sort_index()
            diff = ser.resample("1D").last().dropna().diff().dropna()
            if len(diff) >= MIN_OBS:
                return diff, f"{path.name}:{name}"
    return None, None


def _vol_state(equity: pd.Series | None) -> pd.Series | None:
    """Change in log realised vol -- a state, differenced so it reads as a factor return."""
    if equity is None or len(equity) < RV_WINDOW + MIN_OBS:
        return None
    rv = equity.rolling(RV_WINDOW).std().dropna()
    rv = rv[rv > 0]
    out = np.log(rv).diff().dropna() if len(rv) > MIN_OBS else None
    return out if out is not None and len(out) >= MIN_OBS else None


def _trend(base: pd.Series | None) -> pd.Series | None:
    """12-week time-series momentum of a basket: yesterday's sign times today's return."""
    if base is None or len(base) < TREND_WINDOW + MIN_OBS:
        return None
    out = (np.sign(base.rolling(TREND_WINDOW).sum()).shift(1) * base).dropna()
    return out if len(out) >= MIN_OBS else None


# The factor panel

def _characteristics(symbols: Sequence[str]) -> tuple[dict[str, float], dict[str, float],
                                                      dict[str, Any]]:
    """carry (swap long minus short, robust-scaled) and liquidity (relative-spread percentile).

    Both are scored against THIS BOOK, not the universe: the question is which of the desk's own
    holdings is the expensive one, and a percentile against 196 symbols it never trades answers
    a different one.
    """
    universe = _json(_at("data", "universe", "universe.json"))
    surface = _json(_at("data", "cost_surface.json")).get("symbols")
    surface = surface if isinstance(surface, dict) else {}
    raw_carry: dict[str, float] = {}
    rel_spread: dict[str, float] = {}
    for symbol in symbols:
        row = universe.get(symbol) if isinstance(universe.get(symbol), dict) else {}
        cost = surface.get(symbol) if isinstance(surface.get(symbol), dict) else {}
        lng, shrt = row.get("swap_long"), row.get("swap_short")
        if isinstance(lng, (int, float)) and isinstance(shrt, (int, float)):
            raw_carry[symbol] = float(lng) - float(shrt)
        pts = cost.get("pooled_median_spread_pts", row.get("median_spread_pts"))
        tick = cost.get("tick_size", row.get("tick_size"))
        close = load_bars(symbol)
        if (isinstance(pts, (int, float)) and isinstance(tick, (int, float))
                and close is not None and float(close.iloc[-1]) > 0):
            rel_spread[symbol] = abs(float(pts) * float(tick)) / float(close.iloc[-1])
    scale = float(np.median(np.abs(list(raw_carry.values())))) if raw_carry else 0.0
    carry = ({s: float(np.clip(v / scale, -CARRY_CLIP, CARRY_CLIP))
              for s, v in raw_carry.items()} if scale > 0 else {})
    order = sorted(rel_spread, key=lambda s: rel_spread[s])
    liquidity = ({s: round(i / (len(order) - 1), 6) for i, s in enumerate(order)}
                 if len(order) > 1 else dict.fromkeys(order, 0.5))
    meta = {n: {"kind": "characteristic", "signed_by_side": n == "carry", "n_days": 0,
                "n_symbols": len(d), "unmeasured": not d, "basis": b}
            for n, d, b in (
                ("carry", carry, "broker swap_long - swap_short from universe.json, over the "
                                 f"median absolute carry in the book, clipped to +-{CARRY_CLIP}"),
                ("liquidity", liquidity, "percentile of spread_pts x tick_size / last close "
                                         "WITHIN THE BOOK, from cost_surface.json where measured "
                                         "else universe.json"))}
    return carry, liquidity, meta


def build_factors(symbols: Sequence[str]) -> dict[str, Any]:
    """Every named factor the desk can build from its own data today, and what it cannot."""
    series: dict[str, pd.Series] = {}
    meta: dict[str, Any] = {}

    def put(name: str, data: pd.Series | None, basis: str, used: Any = None) -> None:
        ok = data is not None and len(data) >= MIN_OBS
        if ok:
            series[name] = data.iloc[-LOOKBACK_DAYS:]
        meta[name] = {"kind": "return", "signed_by_side": True, "basis": basis, "symbols": used,
                      "n_days": len(series[name]) if ok else 0,
                      "last": str(series[name].index[-1].date()) if ok else None,
                      **({} if ok else {"unmeasured": True})}

    usd, usd_legs = _basket(USD_LEGS)
    put("usd", usd, "dollar basket of the six majors; + is a STRONGER dollar", usd_legs)
    for name, pool, basis in (
            ("gold", GOLD_SYMBOLS, "gold spot daily log returns"),
            ("oil", OIL_SYMBOLS, "first crude CFD with bars"),
            ("equity_beta", EQUITY_SYMBOLS, "first equity index CFD with bars"),
            ("rates", RATES_SYMBOLS, "first bond CFD with bars; a PRICE, so + is a lower yield")):
        data, sym = _first_with_bars(pool)
        put(name, data, f"{basis}, from {tuple(pool)}", sym)
    equity, eq_sym = _first_with_bars(EQUITY_SYMBOLS)
    vix, vix_sym = _first_with_bars(VOL_SYMBOLS)
    if vix is not None:
        put("vol", vix, "volatility index daily returns", vix_sym)
    else:
        put("vol", _vol_state(equity),
            f"change in log {RV_WINDOW}-day realised vol of {eq_sym or 'the equity index'}", eq_sym)
    for name, pool, basis in (("growth", GROWTH_SERIES, "curve"),
                              ("inflation", INFLATION_SERIES, "breakeven")):
        data, sid = _fred_points(pool)
        put(name, data, f"daily change in a FRED {basis} series {tuple(pool)}", sid)
    comm, comm_legs = _basket([(s, 1.0) for s in COMMODITY_LEGS])
    put("commodities", comm, "equal-weight commodity basket", comm_legs)

    trend = {cls: built.iloc[-LOOKBACK_DAYS:] for cls, base in TREND_BASE.items()
             if (built := _trend(series.get(base))) is not None}
    meta["trend"] = {
        "kind": "return", "signed_by_side": True,
        "basis": f"{TREND_WINDOW}-day time-series momentum of the instrument's OWN asset-class "
                 "basket; the class-to-basket map is declared, never inferred",
        "n_days": int(min((len(v) for v in trend.values()), default=0)),
        "last": str(max(v.index[-1] for v in trend.values()).date()) if trend else None,
        "symbols": {c: TREND_BASE[c] for c in sorted(trend)},
        **({} if trend else {"unmeasured": True})}

    carry, liquidity, char_meta = _characteristics(symbols)
    meta.update(char_meta)
    fresh = max((s.index[-1] for s in series.values()), default=None)
    for name, ser in series.items():         # a factor left behind is measured, and STALE with it
        behind = int((fresh - ser.index[-1]).days) if fresh is not None else 0
        if behind > STALE_DAYS:
            meta[name]["stale_days"] = behind
    ordered = {name: meta[name] for name in FACTORS if name in meta}   # declared order, always
    return {"series": series, "trend": trend, "carry": carry, "liquidity": liquidity,
            "meta": ordered}


# Betas

def _beta(y: np.ndarray, x: np.ndarray) -> float | None:
    xc, yc = x - x.mean(), y - y.mean()
    var = float(xc @ xc)
    return None if var <= 0 else float(xc @ yc / var)


def _joint_r2(frame: pd.DataFrame) -> float | None:
    """One multivariate fit, for r2 only -- the per-factor betas above stay univariate."""
    if len(frame) <= frame.shape[1] + 2 or frame.shape[1] < 2:
        return None
    y = frame.iloc[:, 0].to_numpy(dtype=float)
    design = np.column_stack([frame.iloc[:, 1:].to_numpy(dtype=float), np.ones(len(frame))])
    tot = float(((y - y.mean()) ** 2).sum())
    try:
        coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    resid = y - design @ coef
    return None if tot <= 0 else round(
        float(np.clip(1.0 - float(resid @ resid) / tot, 0.0, 1.0)), 4)


def instrument_exposures(symbol: str, factors: dict[str, Any], asset_class: str | None) -> dict:
    """Univariate betas of one instrument on every measured return factor, plus a joint r2."""
    ret = daily_returns(symbol)
    if ret is None:
        return {"exposures": {}, "r2": None, "n_obs": 0, "unmeasured": "no bars"}
    ret = ret.iloc[-LOOKBACK_DAYS:]
    panel = dict(factors["series"])
    trend = factors["trend"].get(str(asset_class))
    if trend is not None:
        panel["trend"] = trend
    betas: dict[str, float] = {}
    n_obs = 0
    for name, ser in panel.items():
        joined = pd.concat([ret, ser], axis=1, join="inner").dropna().iloc[-WINDOW:]
        if len(joined) < MIN_OBS:
            continue
        beta = _beta(joined.iloc[:, 0].to_numpy(dtype=float),
                     joined.iloc[:, 1].to_numpy(dtype=float))
        if beta is not None:
            betas[name] = round(beta, 6)
            n_obs = max(n_obs, len(joined))
    # The joint fit runs over the factors that COVER this instrument's own last window, not over
    # the intersection of every factor on the box: measured 2026-09-16, the UST10Y tape stopped on
    # 2025-12-31, and an all-factor inner join left SIX common days, so every r2 in the report read
    # null. One stale series must cost its own column, never the whole fit.
    window = ret.iloc[-WINDOW:]
    cover = {n: v for n, v in ((k, x.reindex(window.index)) for k, x in panel.items())
             if v.notna().sum() >= MIN_OBS}
    aligned = (pd.concat([window, *cover.values()], axis=1).dropna() if cover
               else pd.DataFrame())
    out: dict[str, Any] = {
        "exposures": betas, "n_obs": int(n_obs), "r2_factors": sorted(cover),
        "r2": _joint_r2(aligned) if len(aligned) >= MIN_OBS else None}
    if not betas:
        out["unmeasured"] = "no measured factor overlapped this instrument's tape"
    return out


def _asset_class(symbol: str, universe: dict[str, Any]) -> str | None:
    row = universe.get(symbol)
    return row.get("asset_class") if isinstance(row, dict) else None


def _cluster(name: str, family: Any) -> str:
    """The mechanism cluster from the desk's declared taxonomy; the family is the fallback."""
    try:
        from libs.research.alpha_clusters import UNCLASSIFIED, classify_family, classify_sleeve
    except Exception:                                 # the taxonomy is optional here
        return str(family) if family else "UNCLASSIFIED"
    label = classify_sleeve(name)
    if label == UNCLASSIFIED and family:
        label = classify_family(str(family))
        if label == UNCLASSIFIED:
            return str(family)
    return label


# Rows: sleeves and positions

def _sign(side: Any) -> tuple[float, bool]:
    text = str(side or "").strip().upper()
    if text in ("LONG", "BUY", "1", "+1"):
        return 1.0, True
    if text in ("SHORT", "SELL", "-1"):
        return -1.0, True
    return 1.0, False


def _apply(base: dict[str, Any], weight: float, factors: dict[str, Any],
           symbol: str) -> dict[str, float]:
    """Betas -> book exposures: signed by side and scaled by the row's weight."""
    out = {name: round(beta * weight, 8) for name, beta in base["exposures"].items()}
    carry = factors["carry"].get(symbol)
    if carry is not None:
        out["carry"] = round(carry * weight, 8)
    liq = factors["liquidity"].get(symbol)
    if liq is not None:
        out["liquidity"] = round(liq * abs(weight), 8)   # unsigned: a short is as illiquid
    return out


def live_sleeves() -> list[dict[str, Any]]:
    doc = _json(_at("data", "sleeves.json"))
    rows = doc.get("sleeves") if isinstance(doc.get("sleeves"), list) else []
    return [s for s in rows if isinstance(s, dict) and str(s.get("status", "")).upper() == "LIVE"]


def _row(kind: str, name: str, symbol: str, weight: float, basis: str, factors: dict[str, Any],
         universe: dict[str, Any], unmeasured: list[str], **extra: Any) -> dict[str, Any]:
    base = instrument_exposures(symbol, factors, _asset_class(symbol, universe))
    if base.get("unmeasured"):
        unmeasured.append(f"instrument:{symbol} ({base['unmeasured']})")
    return {"kind": kind, "name": name, "symbol": symbol, "weight": round(weight, 8),
            "weight_basis": basis, "risk_frac": round(abs(weight), 8), "n_obs": base["n_obs"],
            "r2": base["r2"], "r2_factors": base.get("r2_factors", []),
            "exposures": _apply(base, weight, factors, symbol), **extra}


def open_positions() -> tuple[list[dict[str, Any]], float | None]:
    state = _json(_at("data", "gateway_state.json"))
    raw = state.get("positions") or state.get("position") or []
    if isinstance(raw, dict):
        raw = list(raw.values())
    equity = state.get("equity")
    return ([p for p in raw if isinstance(p, dict)] if isinstance(raw, list) else [],
            float(equity) if isinstance(equity, (int, float)) and equity else None)


def sleeve_rows(sleeves: list[dict[str, Any]], factors: dict[str, Any],
                universe: dict[str, Any], unmeasured: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sleeve in sleeves:
        name, symbol = str(sleeve.get("name") or "?"), str(sleeve.get("symbol") or "")
        sign, declared = _sign(sleeve.get("side") or sleeve.get("direction"))
        if not declared:
            unmeasured.append(f"sleeve_side:{name}")
        risk = sleeve.get("risk_frac")
        risk = float(risk) if isinstance(risk, (int, float)) else 0.0
        rows.append(_row("sleeve", name, symbol, sign * risk, "risk_frac", factors, universe,
                         unmeasured, family=sleeve.get("family"), lot=sleeve.get("lot"),
                         cluster=_cluster(name, sleeve.get("family")), side=sleeve.get("side"),
                         side_declared=declared))
    return rows


def position_rows(positions: list[dict[str, Any]], equity: float | None,
                  factors: dict[str, Any], universe: dict[str, Any],
                  unmeasured: list[str]) -> list[dict[str, Any]]:
    """A position's weight is its STOP RISK over equity -- the same unit a sleeve's risk_frac is
    in. Without a stop or an equity there is no such number, so the row keeps its lots, says so,
    and is left out of the book sum rather than being summed in a unit it is not in."""
    rows: list[dict[str, Any]] = []
    for pos in positions:
        symbol, ticket = str(pos.get("symbol") or ""), pos.get("ticket")
        volume = pos.get("volume")
        volume = float(volume) if isinstance(volume, (int, float)) else 0.0
        sign = -1.0 if str(pos.get("type")).upper() in ("1", "SELL", "SHORT") else 1.0
        row_u = universe.get(symbol) if isinstance(universe.get(symbol), dict) else {}
        stop, open_px = pos.get("sl"), pos.get("price_open")
        tick_v, tick_s = row_u.get("tick_value"), row_u.get("tick_size")
        weight, basis = sign * volume, "lots_unconverted"
        if (equity and all(isinstance(v, (int, float)) for v in (stop, open_px, tick_v, tick_s))
                and float(stop) > 0 and float(tick_s) > 0):
            money = volume * abs(float(open_px) - float(stop)) * float(tick_v) / float(tick_s)
            weight, basis = sign * money / equity, "risk_frac_from_stop"
        else:
            unmeasured.append(f"position_weight:{ticket} (no stop or no equity; lots, not heat)")
        rows.append(_row("position", f"pos:{ticket}:{symbol}", symbol, weight, basis, factors,
                         universe, unmeasured, ticket=ticket, family=None,
                         cluster="open_position", volume=round(sign * volume, 4),
                         side="SELL" if sign < 0 else "BUY", side_declared=True))
    return rows


# Book, duplicate heat, concentration

def factor_scales(rows: list[dict[str, Any]]) -> dict[str, float]:
    """The book's own RMS loading per factor. An angle between mixed-unit vectors is a UNIT
    CHOICE: carry is clipped at +-3 and an FX beta lives near 0.2, so an unscaled cosine is
    decided by the swap table and every pair looks identical. Dividing by these makes the
    comparison about DIRECTION, which is the only thing the duplicate question asks."""
    scales: dict[str, float] = {}
    for name in FACTORS:
        vals = np.array([abs(float(r["exposures"][name])) for r in rows
                         if name in r["exposures"]], dtype=float)
        rms = float(np.sqrt((vals ** 2).mean())) if vals.size else 0.0
        scales[name] = rms if rms > 0 else 1.0
    return scales


def _scaled(exposures: dict[str, float], scales: dict[str, float]) -> dict[str, float]:
    return {k: v / scales.get(k, 1.0) for k, v in exposures.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float | None:
    keys = sorted(set(a) & set(b))
    if not keys:
        return None
    va = np.array([a[k] for k in keys], dtype=float)
    vb = np.array([b[k] for k in keys], dtype=float)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    return None if na <= 0 or nb <= 0 else float(va @ vb / (na * nb))


def duplicate_heat(rows: list[dict[str, Any]],
                   scales: dict[str, float]) -> tuple[list[dict[str, Any]], int]:
    """Pairs pointing the same way in scaled factor space: five long-dollar trades are ONE bet."""
    vecs = [_scaled(r["exposures"], scales) for r in rows]
    pairs: list[dict[str, Any]] = []
    for i, left in enumerate(rows):
        for j in range(i + 1, len(rows)):
            cos = _cosine(vecs[i], vecs[j])
            if cos is None or cos < COSINE_DUP:
                continue
            ea, eb = vecs[i], vecs[j]
            shared = sorted((k for k in set(ea) & set(eb) if ea[k] * eb[k] > 0),
                            key=lambda k: -abs(ea[k] * eb[k]))
            pairs.append({"a": left["name"], "b": rows[j]["name"], "cosine": round(cos, 4),
                          "shared_factors": shared[:3],
                          "shared_heat": round(abs(left["weight"]) + abs(rows[j]["weight"]), 8)})
    total = len(pairs)
    pairs.sort(key=lambda p: (-p["shared_heat"], -p["cosine"]))
    return pairs[:MAX_PAIRS], total


def n_eff_bets(book: dict[str, float]) -> float | None:
    """(sum|e|)^2 / sum e^2 -- how many independent factor bets the loadings amount to."""
    vals = np.array([v for v in book.values() if isinstance(v, (int, float))], dtype=float)
    if vals.size == 0:
        return None
    s1, s2 = float(np.abs(vals).sum()), float((vals ** 2).sum())
    return None if s2 <= 0 else round(s1 * s1 / s2, 4)


# The organ

def run(write: bool = True) -> dict[str, Any]:
    _BARS.clear()
    universe = _json(_at("data", "universe", "universe.json"))
    unmeasured: list[str] = []
    registry = live_sleeves()
    open_pos, equity = open_positions()
    symbols = sorted({str(s.get("symbol") or "") for s in registry}
                     | {str(p.get("symbol") or "") for p in open_pos})
    factors = build_factors([s for s in symbols if s])
    unmeasured += [f"factor:{n}" for n, m in factors["meta"].items() if m.get("unmeasured")]
    sleeves = sleeve_rows(registry, factors, universe, unmeasured)
    position_table = position_rows(open_pos, equity, factors, universe, unmeasured)
    rows = sleeves + position_table
    scales = factor_scales(rows)
    book: dict[str, float] = {}
    clusters: dict[str, float] = {}
    for row in rows:
        key = row["cluster"]
        clusters[key] = round(clusters.get(key, 0.0) + abs(float(row["weight"])), 8)
        if row["weight_basis"] == "lots_unconverted":
            continue        # lots are not heat; the row is reported, never summed into the book
        for name, value in row["exposures"].items():
            book[name] = round(book.get(name, 0.0) + value, 8)
    dupes, n_pairs = duplicate_heat(rows, scales)
    report = {
        "at": datetime.now(tz=UTC).isoformat(), "source": SOURCE, "factors": factors["meta"],
        "n_live_sleeves": len(sleeves), "n_positions": len(position_table),
        "sleeves": sleeves, "positions": position_table,
        "book": dict(sorted(book.items())),
        "factor_scale": {k: round(v, 8) for k, v in scales.items() if k in book},
        "stale_factors": {n: m["stale_days"] for n, m in factors["meta"].items()
                          if m.get("stale_days")},
        "clusters": dict(sorted(clusters.items(), key=lambda kv: -kv[1])),
        "duplicate_heat": dupes, "n_duplicate_pairs": n_pairs,
        "duplicate_heat_truncated": n_pairs > len(dupes),
        "n_eff_factor_bets": n_eff_bets(_scaled(book, scales)),
        "n_eff_factor_bets_unscaled": n_eff_bets(book),
        "n_factors_measured": sum(1 for m in factors["meta"].values() if not m.get("unmeasured")),
        "unmeasured": sorted(set(unmeasured)), "rule": RULE}
    if write:
        _write_atomic(report_path(), report)
    return report


def _print(report: dict[str, Any]) -> None:
    meta, names = report["factors"], [n for n in FACTORS if n in report["book"]]
    print(f"EXPOSURE DECOMPOSITION  {report['n_live_sleeves']} live sleeves, "
          f"{report['n_positions']} positions, "
          f"{report['n_factors_measured']}/{len(FACTORS)} factors measured")
    print("  measured  : " + (", ".join(
        f"{n}({m['n_days']}d)" if m["kind"] == "return" else f"{n}({m['n_symbols']} symbols)"
        for n, m in meta.items() if not m.get("unmeasured")) or "NONE"))
    print("  UNMEASURED: " + (", ".join(n for n, m in meta.items()
                                        if m.get("unmeasured")) or "none"))
    if report["stale_factors"]:
        print("  STALE     : " + ", ".join(f"{n} {d}d behind (last {meta[n]['last']})"
                                           for n, d in report["stale_factors"].items()))
    print("  " + "BOOK net exposure".ljust(26) + "".join(f"{n[:9]:>10s}" for n in names))
    print("  " + " " * 26 + "".join(f"{report['book'][n]:>10.4f}" for n in names))
    for row in sorted(report["sleeves"] + report["positions"],
                      key=lambda r: -abs(float(r["weight"])))[:12]:
        print(f"  {row['name'][:24]:<24s}{row['weight']:+.4f}"
              + "".join(f"{row['exposures'].get(n, float('nan')):>10.3f}" for n in names))
    for cluster, heat in list(report["clusters"].items())[:8]:
        print(f"  cluster {cluster[:32]:<32s} heat={heat:.4f}")
    print(f"  duplicate pairs (cosine >= {COSINE_DUP}): {report['n_duplicate_pairs']}"
          + (f", listing {len(report['duplicate_heat'])}"
             if report["duplicate_heat_truncated"] else ""))
    for pair in report["duplicate_heat"][:8]:
        print(f"    {pair['a'][:26]:<26s} ~ {pair['b'][:26]:<26s} cos={pair['cosine']:.3f} "
              f"heat={pair['shared_heat']:.4f} via {','.join(pair['shared_factors'])}")
    print(f"  effective independent factor bets: {report['n_eff_factor_bets']}")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print the table, write nothing")
    args = ap.parse_args(argv)
    report = run(write=not args.dry_run)
    _print(report)
    print("dry run: nothing written" if args.dry_run else f"written: {report_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
