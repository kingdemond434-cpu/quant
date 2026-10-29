"""The implied-vol state as a CONDITIONER: IV percentile, the variance risk premium, the IV
fixed point, the VIX term structure and the SKEW proxy, on the CFD each index is about.

    python desks/mt5/macro/vol_conditioner.py            # build series, contracts, cells
    python desks/mt5/macro/vol_conditioner.py --dry-run  # measure and print, write nothing

QUANT GUILD CARDS (docs/research/quant_guild/cards_world_sensor.json, PR #166):
  QG25-05  implied-vol percentile regime and the IV fixed point IV* = b / (1 - a) (forward mean IV
           regressed on IV, NON-OVERLAPPING 21-day targets, expanding window: the donor's
           overlapping full-sample fit is its stated weakness and is not repeated here)
  QG26-07  term-structure state: VIX9D/VIX/VIX3M/VIX6M slopes per log-tenor, inversion flag, and
           CBOE SKEW as the skew proxy (options never trade here; this is state for US500)
  QG26-08  NOT rebuilt: the CBOE indices ARE the discrete variance-swap strip, so implied variance
           is (index / 100)^2 and that is the only use made of the card
  QG26-09  the variance risk premium IV^2 - RV^2 on matched horizons against THIS BROKER's bars,
           its 252-day rank, the negative-premium crash flag, and the forward-RV regression
           residual (known only once its window has closed)

WHAT ALREADY EXISTED. `recorders/vol_archive.py` (MT5-VolArchive) archives every index against the
broker's realised vol and writes the public 10-year reference history it fetches anyway to
`data/vol_archive/reference/`. `macro/market_state.py` reads the archive for the latest state.
Nothing turned the history into a conditioner: the diff-first verdict was EXISTS_UNWIRED. This is
the consumer. It does not fetch.

POINT IN TIME. An index close of day d is knowable at d+1 01:00 UTC (declared lag), unless the
desk's own archive observed it earlier (bounded by that receipt). The state for broker day D is
the newest index day strictly before D, and the payoff it is judged on is the base cell's return
from D's close to the next close: no bar the state could not have seen.

THE CONTRACT (sensor_engines): per ground,
  vrp_high -> 1-day reversal      (dealers long gamma dampen moves)            QG26-09
  vrp_negative -> 20-day trend    (crash state: moves persist)                 QG26-09
  term_inverted -> 20-day trend, term_contango -> 1-day reversal               QG26-07
  iv_high -> long (equity indices: insurance premium + leverage effect)        QG25-05
  IV* mean-reversion forecast of forward variance vs IV^2 alone (QLIKE)        QG25-05/26-09
each against its ungated base with a circular-shift null and the realised-vol tercile as the
control stratum. The series go to the lake for `family_exogenous_conditioner` cells; the gauntlet
judges them, never this file.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_engines as se  # noqa: E402

REPORT = DESK / "reports" / "VOL_CONDITIONER.json"
#: vol_archive reads the CBOE indices through Yahoo's chart API: the terms gate holds that source
#: (audit #211, J sources). FRED's republication of the same indices is HELD TOO (2026-10-07):
#: each carries CBOE's copyright notice and FRED's ToU FAQ Q3 says FRED cannot license it. A
#: ground still reads FRED first and measures the substitute, but its cells emit only once
#: "fred:<series>" clears the gate; the permitted ground is the broker's own vol CFD and the bar
#: vol state below (BAR_SOURCE).
VOL_SOURCE = "yahoo:cboe_indices"
FRED_IDS: dict[str, str] = {
    "^VIX": "VIXCLS", "^VIX3M": "VXVCLS", "^VXN": "VXNCLS", "^VXD": "VXDCLS",
    "^OVX": "OVXCLS", "^GVZ": "GVZCLS", "^EVZ": "EVZCLS", "^RVX": "RVXCLS",
    "^VXFXI": "VXFXICLS", "^VXEEM": "VXEEMCLS",
}
SUBSTITUTE_MIN_CORR = 0.5
REFERENCE = DESK / "data" / "vol_archive" / "reference"
UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE = UNIVERSE_DIR / "universe.json"
ENGINE = "vol_conditioner"
UNMEASURED = "UNMEASURED"
TRAIL = 252
H = 21
RV_WINDOW = 21
LAG = timedelta(hours=25)          # index close of day d -> knowable d+1 01:00 UTC

#: index -> (MT5 candidates, is an equity index, the term curve, the skew proxy)
GROUNDS: dict[str, tuple[tuple[str, ...], bool, tuple[str, ...], str]] = {
    "^VIX": (("US500", "SPX500", "USA500", "SP500", "US500.cash"), True,
             ("^VIX9D", "^VIX", "^VIX3M", "^VIX6M"), "^SKEW"),
    "^VXN": (("USTEC", "NAS100", "NDX", "USTEC.cash", "NASDAQ"), True, (), ""),
    "^VXD": (("US30", "DJ30", "DOW", "US30.cash"), True, (), ""),
    "^GVZ": (("XAUUSD", "GOLD", "XAUUSD.", "XAUUSDx"), False, (), ""),
    "^OVX": (("USOIL", "WTI", "UKOIL", "BRENT", "CRUDE", "OIL"), False, (), ""),
    "^EVZ": (("EURUSD",), False, (), ""),
    "^RVX": (("US2000", "RUSSELL2000", "RUSSELL", "US2000.cash", "RTY"), True, (), ""),
    "^VXFXI": (("CHINA50", "CN50", "CHINAH", "HK50", "CHINA.A50", "HKIND"), True, (), ""),
}
TENOR = {"^VIX9D": 9, "^VIX": 30, "^VIX3M": 91, "^VIX6M": 182}
SIGNALS = ("iv_pct", "vrp_rank", "vrp_var", "iv_gap", "term_slope_short", "term_slope_long",
           "skew_rank", "rv_resid")

#: THE PERMITTED VOL STATE (coordinator, 2026-10-07). The CBOE indices are HELD on terms whether
#: read through Yahoo or FRED (FRED ToU FAQ Q3: FRED cannot license a series carrying a third
#: party's copyright notice), so their cells went dark. Two grounds need no third party's licence:
#:   1. the broker's OWN vol-index CFD, where this account lists one: its price is our own MT5
#:      data, admitted as "mt5:bars", and it replaces the held index as the IV of its ground;
#:   2. range-based realised-vol state from the desk's own H1 bars (Garman-Klass and Parkinson
#:      estimators, HAR forecast), on every ground's tradeable symbol.
BAR_SOURCE = "mt5:bars"
BROKER_VOL_CFD: dict[str, tuple[str, ...]] = {
    "^VIX": ("VIX", "VIX.f", "VIX.cash", "VIXX", "USVIX", "VOLX", "VIX_Z"),
}
BAR_SIGNALS = ("rv_pct", "rv_term", "volvol_rank", "range_rank", "har_gap")


# ============================================================================== inputs
def load_reference(ticker: str, root: Path = REFERENCE) -> dict[str, float]:
    path = root / (ticker.replace("^", "") + ".json")
    try:
        doc = json.loads(path.read_text("utf-8"))
        return {str(k): float(v) for k, v in (doc.get("series") or {}).items()
                if isinstance(v, int | float) and math.isfinite(float(v))}
    except (OSError, ValueError, AttributeError):
        return {}


def fred_history(ticker: str, series: Mapping[str, Sequence[tuple[str, float]]]
                 ) -> dict[str, float]:
    sid = FRED_IDS.get(ticker)
    return {d: float(v) for d, v in series.get(sid, [])} if sid else {}


def fred_series() -> dict[str, list[tuple[str, float]]]:
    try:
        from macro.market_state import load_series
        return load_series()
    except Exception:
        return {}


def fred_knowable(ticker: str) -> Any:
    """The FRED vintage clock: market_state's declared lag for a non-curve series."""
    from macro.market_state import knowable
    sid = FRED_IDS[ticker]
    return lambda d: knowable(d, sid)


def substitute_corr(fred: Mapping[str, float], held: Mapping[str, float]) -> dict[str, Any]:
    common = sorted(set(fred) & set(held))
    if len(common) < 60:
        return {"status": UNMEASURED, "n": len(common),
                "why": "fewer than 60 common days with the held source"}
    a = np.asarray([fred[d] for d in common])
    b = np.asarray([held[d] for d in common])
    if a.std() == 0 or b.std() == 0:
        return {"status": UNMEASURED, "n": len(common), "why": "a constant series"}
    c = float(np.corrcoef(a, b)[0, 1])
    return {"status": "MEASURED", "n": len(common), "corr": round(c, 4),
            "covered": c >= SUBSTITUTE_MIN_CORR, "min_corr": SUBSTITUTE_MIN_CORR}


def vintage_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], tuple[float, str]]:
    """(ticker, value_date) -> (value, earliest observed_at) from the desk's own archive."""
    out: dict[tuple[str, str], tuple[float, str]] = {}
    for r in rows:
        iv, d, seen = r.get("implied_vol"), r.get("value_date"), r.get("observed_at")
        if not isinstance(iv, int | float) or not d or not seen:
            continue
        key = (str(r.get("vol_ticker")), str(d))
        if key not in out or str(seen) < out[key][1]:
            out[key] = (float(iv), str(seen))
        for t, v in (r.get("term") or {}).items():
            if isinstance(v, int | float):
                k2 = (str(t), str(d))
                if k2 not in out or str(seen) < out[k2][1]:
                    out[k2] = (float(v), str(seen))
    return out


def read_vintages() -> list[dict[str, Any]]:
    try:
        from recorders import vol_archive as va
        return list(va.read_archive())
    except Exception:
        return []


def resolve_symbol(candidates: Sequence[str], universe_dir: Path = UNIVERSE_DIR) -> str | None:
    try:
        reg = json.loads((universe_dir / "universe.json").read_text("utf-8"))
        from recorders.vol_archive import resolve_symbol as rs
        got = rs(tuple(candidates), reg)
        if got:
            return str(got)
    except Exception:
        pass
    for c in candidates:
        if (universe_dir / f"{c}_H1.parquet").exists():
            return c
    return None


def daily_closes(symbol: str, universe_dir: Path = UNIVERSE_DIR) -> dict[str, float]:
    """Broker-day closes from the desk's own H1 bars, {iso date: close}."""
    path = universe_dir / f"{symbol}_H1.parquet"
    if not path.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_parquet(path, columns=["close"])
    except Exception:
        return {}
    if df.empty:
        return {}
    idx = pd.DatetimeIndex(df.index)
    s = df["close"].groupby(idx.date).last()
    return {d.isoformat(): float(v) for d, v in s.items() if v and math.isfinite(float(v))}


# ============================================================================== the features
def _pct_rank(hist: Sequence[float], x: float) -> float | None:
    h = [v for v in hist if math.isfinite(v)]
    if len(h) < 20:
        return None
    return round(sum(1 for v in h if v <= x) / len(h), 6)


def _ols(x: Sequence[float], y: Sequence[float]) -> tuple[float, float] | None:
    if len(x) < 8:
        return None
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    vx = float(((xa - xa.mean()) ** 2).sum())
    if vx <= 0:
        return None
    b = float(((xa - xa.mean()) * (ya - ya.mean())).sum() / vx)
    return float(ya.mean() - b * xa.mean()), b


def rv_series(closes: Mapping[str, float], window: int = RV_WINDOW) -> dict[str, float]:
    """Annualised close-to-close realised vol in PERCENT ending on each broker day."""
    days = sorted(closes)
    out: dict[str, float] = {}
    rets: list[float] = []
    for i in range(1, len(days)):
        a, b = closes[days[i - 1]], closes[days[i]]
        rets.append(math.log(b / a) if a > 0 and b > 0 else float("nan"))
        w = [r for r in rets[-window:] if math.isfinite(r)]
        if len(w) >= max(5, window // 2):
            out[days[i]] = float(np.std(w, ddof=1)) * math.sqrt(252.0) * 100.0
    return out


def forward_rv(closes: Mapping[str, float], window: int = H) -> dict[str, tuple[float, str]]:
    """day -> (realised vol over the NEXT `window` broker days, the day that window ends)."""
    days = sorted(closes)
    out: dict[str, tuple[float, str]] = {}
    for i in range(len(days) - window):
        seg = [closes[days[j]] for j in range(i, i + window + 1)]
        r = [math.log(seg[k + 1] / seg[k]) for k in range(window) if seg[k] > 0 and seg[k + 1] > 0]
        if len(r) >= window // 2:
            out[days[i]] = (float(np.std(r, ddof=1)) * math.sqrt(252.0) * 100.0,
                            days[i + window])
    return out


def term_slopes(points: Mapping[str, float]) -> tuple[float | None, float | None]:
    pts = sorted((TENOR[k], v) for k, v in points.items() if k in TENOR)
    if len(pts) < 2:
        return None, None

    def slope(a: tuple[int, float], b: tuple[int, float]) -> float:
        return (b[1] - a[1]) / (math.log(b[0]) - math.log(a[0]))

    return slope(pts[0], pts[1]), (slope(pts[-2], pts[-1]) if len(pts) >= 3 else None)


def build_ground(ticker: str, *, iv: Mapping[str, float], closes: Mapping[str, float],
                 term: Mapping[str, Mapping[str, float]] | None = None,
                 skew: Mapping[str, float] | None = None,
                 vintages: Mapping[tuple[str, str], tuple[float, str]] | None = None,
                 knowable_fn: Any = None) -> list[dict[str, Any]]:
    """One PIT row per index day: every feature computed from data held by its available_time."""
    days = sorted(iv)
    rv = rv_series(closes)
    rv_days = sorted(rv)
    fwd = forward_rv(closes)
    term = term or {}
    skew = skew or {}
    vint = vintages or {}
    rows: list[dict[str, Any]] = []
    ivs: list[float] = []
    vrps: list[float] = []
    skews: list[float] = []
    # completed (non-overlapping) training pairs, accrued in calendar order of completion
    pending: list[tuple[str, float, float, float, str]] = []   # day, iv, iv_fwd_mean, rv_fwd, end
    done: list[tuple[float, float, float]] = []
    last_taken = ""
    for i, d in enumerate(days):
        x = float(iv[d])
        avail = (knowable_fn(d) if knowable_fn is not None else
                 datetime.fromisoformat(d).replace(tzinfo=UTC) + LAG)
        basis = "declared_lag"
        seen = vint.get((ticker, d))
        if seen is not None:
            t = datetime.fromisoformat(seen[1].replace("Z", "+00:00"))
            t = t if t.tzinfo else t.replace(tzinfo=UTC)
            if t < avail:
                avail, basis = t, "bounded_by_receipt"
        # the broker's realised vol as of the index day (bars up to and including d)
        j = int(np.searchsorted(rv_days, d, side="right")) - 1
        rv_now = rv[rv_days[j]] if j >= 0 else None
        # admit training pairs whose target window has ended by this day
        while pending and pending[0][4] < d:
            p = pending.pop(0)
            done.append((p[1], p[2], p[3]))
        row: dict[str, Any] = {"event_time": d, "available_time": avail.isoformat(),
                               "knowable_basis": basis, "iv": x,
                               "implied_var": (x / 100.0) ** 2,
                               "iv_pct": _pct_rank(ivs[-TRAIL:], x)}
        if rv_now is not None:
            vrp = (x / 100.0) ** 2 - (rv_now / 100.0) ** 2
            row.update({"rv21": rv_now, "vrp_var": vrp, "iv_rv_ratio": x / rv_now if rv_now
                        else None, "vrp_rank": _pct_rank(vrps[-TRAIL:], vrp),
                        "vrp_negative": 1.0 if vrp < 0 else 0.0})
            vrps.append(vrp)
        fit_iv = _ols([a for a, _, _ in done], [b for _, b, _ in done])
        if fit_iv is not None and 0 < fit_iv[1] < 1:
            star = fit_iv[0] / (1 - fit_iv[1])
            row.update({"iv_star": star, "iv_gap": x - star,
                        "iv_half_life_21d": math.log(0.5) / math.log(fit_iv[1])})
            row["iv_fwd_hat"] = fit_iv[0] + fit_iv[1] * x
        fit_rv = _ols([(a / 100) ** 2 for a, _, _ in done], [(c / 100) ** 2 for _, _, c in done])
        if fit_rv is not None:
            row["rv_fwd_var_hat"] = fit_rv[0] + fit_rv[1] * (x / 100.0) ** 2
            # the last COMPLETED residual: forward RV^2 minus its prediction, known by now
            a, _, c = done[-1]
            row["rv_resid"] = (c / 100) ** 2 - (fit_rv[0] + fit_rv[1] * (a / 100) ** 2)
        pts = {t: float(series[d]) for t, series in term.items() if d in series}
        if len(pts) >= 2:
            s1, s2 = term_slopes(pts)
            row.update({"term_slope_short": s1, "term_slope_long": s2,
                        "term_inverted": 1.0 if (s1 is not None and s1 < 0) else 0.0})
        if d in skew:
            sk = float(skew[d])
            row.update({"skew": sk, "skew_rank": _pct_rank(skews[-TRAIL:], sk)})
            skews.append(sk)
        rows.append(row)
        ivs.append(x)
        # queue this day as a training pair if its forward window is complete in the data and
        # it does not overlap the previous pair (non-overlapping targets)
        f = fwd.get(d)
        if f is not None and (not last_taken or d >= last_taken) and i + H < len(days):
            iv_fwd = float(np.mean([iv[days[k]] for k in range(i + 1, i + H + 1)]))
            end = max(f[1], days[i + H])
            pending.append((d, x, iv_fwd, f[0], end))
            pending.sort(key=lambda p: p[4])
            last_taken = end
    return rows


# ============================================================================== bar vol state
def daily_bars(symbol: str, universe_dir: Path = UNIVERSE_DIR
               ) -> dict[str, tuple[float, float, float, float, str]]:
    """{iso date: (open, high, low, close, available_time)} from the desk's own H1 bars. A bar is
    stamped at its OPEN, so a day's state is knowable when its last bar closes (+1h)."""
    path = universe_dir / f"{symbol}_H1.parquet"
    if not path.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_parquet(path, columns=["open", "high", "low", "close"])
    except Exception:
        return {}
    if df.empty:
        return {}
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is None:
        idx = idx.tz_localize(UTC)
    df = df.set_axis(idx)
    g = df.groupby(idx.date)
    agg = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last()})
    last = pd.Series(idx, index=idx).groupby(idx.date).max()
    out: dict[str, tuple[float, float, float, float, str]] = {}
    for d, r in agg.iterrows():
        o, h, lo, c = (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
        if min(o, h, lo, c) <= 0 or not all(map(math.isfinite, (o, h, lo, c))) or h < lo:
            continue
        avail = (last[d].to_pydatetime() + timedelta(hours=1)).astimezone(UTC)
        out[d.isoformat()] = (o, h, lo, c, avail.isoformat())
    return out


def _gk(o: float, h: float, lo: float, c: float) -> float:
    """Garman-Klass one-day variance (log units)."""
    return 0.5 * math.log(h / lo) ** 2 - (2.0 * math.log(2.0) - 1.0) * math.log(c / o) ** 2


def _ann(var_mean: float) -> float:
    return math.sqrt(max(var_mean, 0.0) * 252.0) * 100.0


def build_bar_ground(bars: Mapping[str, tuple[float, float, float, float, str]]
                     ) -> list[dict[str, Any]]:
    """One PIT row per broker day from that day's bars and earlier ones only.

    rv5/rv21/rv63  annualised Garman-Klass vol (%) over 5/21/63 days
    rv_pct         rv21's rank in the trailing year           (the IV-percentile analogue)
    rv_term        log(rv5 / rv63): > 0 is the short end above the long (an "inverted" curve)
    volvol_rank    rank of the 63-day std of log rv5 changes  (vol of vol)
    range_rank     the day's Parkinson range against the trailing year
    har_gap        HAR forecast of next-21-day variance minus rv21^2, fitted only on windows that
                   had CLOSED by the day (non-overlapping targets, expanding window)"""
    days = sorted(bars)
    gk: list[float] = []
    park: list[float] = []
    rv21s: list[float] = []
    lrv5: list[float] = []
    vv: list[float] = []
    rows: list[dict[str, Any]] = []
    pending: list[tuple[int, list[float], float]] = []      # (end index, x, y)
    train_x: list[list[float]] = []
    train_y: list[float] = []
    last_end = -1
    for i, d in enumerate(days):
        o, h, lo, c, avail = bars[d]
        gk.append(max(_gk(o, h, lo, c), 0.0))
        park.append(math.log(h / lo) ** 2 / (4.0 * math.log(2.0)))
        while pending and pending[0][0] <= i:
            _e, x, y = pending.pop(0)
            train_x.append(x)
            train_y.append(y)
        if len(gk) < 63:
            continue
        v5, v21, v63 = (float(np.mean(gk[-5:])), float(np.mean(gk[-21:])),
                        float(np.mean(gk[-63:])))
        rv5, rv21, rv63 = _ann(v5), _ann(v21), _ann(v63)
        row: dict[str, Any] = {"event_time": d, "available_time": avail,
                               "knowable_basis": "bar_close", "rv5": rv5, "rv21": rv21,
                               "rv63": rv63, "rv_pct": _pct_rank(rv21s[-TRAIL:], rv21),
                               "range_rank": _pct_rank(park[-TRAIL - 1:-1], park[-1])}
        if rv5 > 0 and rv63 > 0:
            row["rv_term"] = math.log(rv5 / rv63)
            row["rv_term_inverted"] = 1.0 if rv5 > rv63 else 0.0
            lrv5.append(math.log(rv5))
        if len(lrv5) >= 64:
            vol_of_vol = float(np.std(np.diff(lrv5[-64:]), ddof=1))
            row["volvol_rank"] = _pct_rank(vv[-TRAIL:], vol_of_vol)
            vv.append(vol_of_vol)
        x = [1.0, v5, v21, v63]
        if len(train_y) >= 12:
            beta, *_ = np.linalg.lstsq(np.asarray(train_x), np.asarray(train_y), rcond=None)
            har = float(np.dot(beta, x))
            if har > 0:
                row["har_var_hat"] = har
                row["har_gap"] = har - v21
        row["gk_var21"] = v21
        rows.append(row)
        rv21s.append(rv21)
        # this day becomes a training pair once its next-21-day window has closed
        if i + H < len(days) and i > last_end:
            y = float(np.mean([max(_gk(*bars[days[k]][:4]), 0.0)
                               for k in range(i + 1, i + H + 1)]))
            pending.append((i + H + 1, x, y))
            last_end = i + H
    return rows


def bar_contracts(symbol: str, equity: bool, rows: Sequence[Mapping[str, Any]],
                  closes: Mapping[str, float],
                  bars: Mapping[str, tuple[float, float, float, float, str]]
                  ) -> list[dict[str, Any]]:
    al = _align(rows, closes)
    rev = [-math.copysign(1.0, r0) * r1 if r0 else 0.0 for _, r0, r1, _ in al]
    mom = [math.copysign(1.0, m) * r1 if m else 0.0 for _, _, r1, m in al]
    lng = [r1 for _, _, r1, _ in al]
    strata = _terciles([s.get("rv63") for s, _, _, _ in al])

    def g(key: str, test: Any) -> list[bool]:
        return [bool(isinstance(s.get(key), int | float) and test(float(s[key])))
                for s, _, _, _ in al]

    fals = ("bucket expectancy difference not significant after the multiplicity charge, or "
            "vanishes once the 63-day realised-vol tercile is controlled")
    out = [
        se.gated_gain(mom, g("rv_term_inverted", lambda v: v > 0.5), engine=ENGINE,
                      cards=["QG26-07", "QG26-09"], falsifier=fals,
                      baseline="20-day trend, ungated", strata=strata),
        se.gated_gain(rev, g("rv_term_inverted", lambda v: v < 0.5), engine=ENGINE,
                      cards=["QG26-07", "QG26-09"], falsifier=fals,
                      baseline="1-day reversal, ungated", strata=strata),
        se.gated_gain(rev, g("range_rank", lambda v: v >= 0.9), engine=ENGINE,
                      cards=["QG26-09"], falsifier=fals, baseline="1-day reversal, ungated",
                      strata=strata),
        se.gated_gain(mom, g("volvol_rank", lambda v: v >= 0.8), engine=ENGINE,
                      cards=["QG26-09"], falsifier=fals, baseline="20-day trend, ungated",
                      strata=strata),
    ]
    labels = ["rv_term_inverted->trend", "rv_term_contango->reversal",
              "range_extreme->reversal", "volvol_high->trend"]
    if equity:
        out.append(se.gated_gain(lng, g("rv_pct", lambda v: v >= 0.8), engine=ENGINE,
                                 cards=["QG25-05"], falsifier=fals, baseline="long, ungated",
                                 strata=strata))
        labels.append("rv_high->long")
    days = sorted(bars)
    pos = {d: i for i, d in enumerate(days)}
    y, model, base = [], [], []
    for r in rows:
        i = pos.get(str(r["event_time"]))
        if i is None or i + H >= len(days) or not isinstance(r.get("har_var_hat"), float):
            continue
        y.append(float(np.mean([max(_gk(*bars[days[k]][:4]), 0.0)
                                for k in range(i + 1, i + H + 1)])))
        model.append(max(float(r["har_var_hat"]), 1e-12))
        base.append(max(float(r["gk_var21"]), 1e-12))
    out.append(se.forecast_gain(y, model, base, engine=ENGINE, cards=["QG25-05", "QG26-09"],
                                falsifier="the HAR forecast of forward variance is no better "
                                          "than the last 21 days' variance",
                                baseline="trailing 21-day Garman-Klass variance", loss="qlike"))
    labels.append("har->forward_variance")
    for c, lbl in zip(out, labels, strict=True):
        c.update({"label": lbl, "ground": f"bars:{symbol}", "symbol": symbol,
                  "data_source": BAR_SOURCE})
    return out


def broker_vol_cfd(ticker: str, universe_dir: Path = UNIVERSE_DIR
                   ) -> tuple[str, dict[str, float]] | None:
    """(symbol, daily closes) of this broker's own vol-index CFD for `ticker`, if it lists one."""
    cands = BROKER_VOL_CFD.get(ticker)
    if not cands:
        return None
    sym = resolve_symbol(cands, universe_dir)
    if sym is None:
        return None
    closes = daily_closes(sym, universe_dir)
    return (sym, closes) if closes else None


def _admitted(source: str) -> bool:
    try:
        from libs.data.terms_hold import gauntlet_terms
        return bool(gauntlet_terms(source)[0])
    except Exception:
        return False


# ============================================================================== the contract
def _align(rows: Sequence[Mapping[str, Any]], closes: Mapping[str, float]
           ) -> list[tuple[Mapping[str, Any], float, float, float]]:
    """(state, r_today, r_next, mom20) per broker day, state = newest index day BEFORE it."""
    days = sorted(closes)
    states = sorted(rows, key=lambda r: str(r["event_time"]))
    keys = [str(r["event_time"]) for r in states]
    out = []
    for i in range(20, len(days) - 1):
        k = int(np.searchsorted(keys, days[i], side="left")) - 1
        if k < 0:
            continue
        c0, c1, c2, c20 = closes[days[i - 1]], closes[days[i]], closes[days[i + 1]], \
            closes[days[i - 20]]
        if min(c0, c1, c2, c20) <= 0:
            continue
        out.append((states[k], c1 / c0 - 1.0, c2 / c1 - 1.0, c1 / c20 - 1.0))
    return out


def _terciles(vals: Sequence[float | None]) -> list[int | None]:
    good = sorted(v for v in vals if v is not None)
    if len(good) < 3:
        return [None] * len(vals)
    lo, hi = good[len(good) // 3], good[2 * len(good) // 3]
    return [None if v is None else (0 if v < lo else 2 if v > hi else 1) for v in vals]


def contracts(ticker: str, symbol: str, equity: bool, rows: Sequence[Mapping[str, Any]],
              closes: Mapping[str, float]) -> list[dict[str, Any]]:
    al = _align(rows, closes)
    rev = [-math.copysign(1.0, r0) * r1 if r0 else 0.0 for _, r0, r1, _ in al]
    mom = [math.copysign(1.0, m) * r1 if m else 0.0 for _, _, r1, m in al]
    lng = [r1 for _, _, r1, _ in al]
    strata = _terciles([s.get("rv21") for s, _, _, _ in al])

    def g(key: str, test: Any) -> list[bool]:
        return [bool(isinstance(s.get(key), int | float) and test(float(s[key])))
                for s, _, _, _ in al]

    out = [
        se.gated_gain(rev, g("vrp_rank", lambda v: v >= 0.8), engine=ENGINE, cards=["QG26-09"],
                      falsifier="bucket expectancy difference not significant after the "
                                "multiplicity charge, or vanishes once realised-vol tercile is "
                                "controlled", baseline="1-day reversal, ungated",
                      strata=strata),
        se.gated_gain(mom, g("vrp_negative", lambda v: v > 0.5), engine=ENGINE,
                      cards=["QG26-09"], falsifier="crash-state trend no better than ungated",
                      baseline="20-day trend, ungated", strata=strata),
        se.gated_gain(mom, g("term_inverted", lambda v: v > 0.5), engine=ENGINE,
                      cards=["QG26-07"], falsifier="no expectancy difference between term-shape "
                                                   "buckets in walk-forward",
                      baseline="20-day trend, ungated", strata=strata),
        se.gated_gain(rev, g("term_inverted", lambda v: v < 0.5) if any(
            isinstance(s.get("term_inverted"), float) for s, _, _, _ in al) else [False] * len(al),
            engine=ENGINE, cards=["QG26-07"],
            falsifier="no expectancy difference between term-shape buckets in walk-forward",
            baseline="1-day reversal, ungated", strata=strata),
    ]
    labels = ["vrp_high->reversal", "vrp_negative->trend", "term_inverted->trend",
              "term_contango->reversal"]
    if equity:
        out.append(se.gated_gain(lng, g("iv_pct", lambda v: v >= 0.8), engine=ENGINE,
                                 cards=["QG25-05"], falsifier="gate effect indistinguishable "
                                 "from the shuffled-IV gate across the judged cells",
                                 baseline="long, ungated", strata=strata))
        labels.append("iv_high->long")
    # the forecast half: IV* mean reversion of forward variance vs implied variance alone
    fwd = forward_rv(closes)
    y, model, base = [], [], []
    for r in rows:
        f = fwd.get(str(r["event_time"]))
        if f is None or not isinstance(r.get("rv_fwd_var_hat"), float):
            continue
        y.append((f[0] / 100.0) ** 2)
        model.append(max(float(r["rv_fwd_var_hat"]), 1e-8))
        base.append(float(r["implied_var"]))
    out.append(se.forecast_gain(y, model, base, engine=ENGINE, cards=["QG25-05", "QG26-09"],
                                falsifier="the IV fixed-point forecast of forward variance is no "
                                          "better than implied variance itself",
                                baseline="implied variance (IV/100)^2", loss="qlike"))
    labels.append("iv_star->forward_variance")
    for c, lbl in zip(out, labels, strict=True):
        c.update({"label": lbl, "ground": ticker, "symbol": symbol})
    return out


# ============================================================================== the organ
def observations(ticker: str, symbol: str, last: Mapping[str, Any], received_at: datetime,
                 data_source: str | None = None) -> list[Any]:
    from libs.research import sensor_contract as sc
    out = []
    basis = str(last.get("knowable_basis") or "declared_lag")
    know = last["available_time"]
    rx = know if basis == "bounded_by_receipt" else max(
        received_at.isoformat(), str(know))
    for metric in ("iv_pct", "vrp_var", "vrp_rank", "iv_gap", "term_slope_short", "skew_rank",
                   "rv_resid"):
        v = last.get(metric)
        if not isinstance(v, int | float):
            continue
        out.append(sc.make(sensor_id="market:vol_conditioner", source_id=data_source or f"{VOL_SOURCE}:{ticker}",
                           metric=f"{ticker}_{metric}", entity=symbol, kind="state",
                           sensor_class="market_state", asset_domain="vol", value=float(v),
                           event_time=last["event_time"], knowable_at=know,
                           knowable_basis=basis, received_at=rx, parse_complete_at=rx,
                           licence=("own data: this account's vol-index CFD bars"
                                    if data_source == BAR_SOURCE else
                                    "CBOE index values republished by FRED: held (FAQ Q3)"
                                    if str(data_source).startswith("fred:") else
                                    "CBOE index values via Yahoo: terms UNCLEARED, held"),
                           commercial_rights=UNMEASURED))
    return out


def bar_observations(symbol: str, last: Mapping[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    know = str(last["available_time"])
    rx = max(received_at.isoformat(), know)
    return [sc.make(sensor_id="market:vol_conditioner", source_id=f"{BAR_SOURCE}:{symbol}",
                    metric=f"bars_{symbol}_{m}", entity=symbol, kind="state",
                    sensor_class="market_state", asset_domain="vol", value=float(last[m]),
                    event_time=last["event_time"], knowable_at=know, knowable_basis="bar_close",
                    received_at=rx, parse_complete_at=rx,
                    licence="own data: this account's MT5 bars", commercial_rights="own data")
            for m in (*BAR_SIGNALS, "rv21") if isinstance(last.get(m), int | float)]


def run_bars(*, dry_run: bool, universe_dir: Path, when: datetime,
             contracts_out: list[dict[str, Any]], obs_out: list[Any]) -> dict[str, Any]:
    """Range-based realised-vol state on every ground's tradeable symbol, from our own bars."""
    out: dict[str, Any] = {}
    for _ticker, (cands, equity, _t, _s) in GROUNDS.items():
        sym = resolve_symbol(cands, universe_dir)
        if sym is None or sym in out:
            continue
        bars = daily_bars(sym, universe_dir)
        if len(bars) < 63 + 20:
            out[sym] = {"status": UNMEASURED, "why": f"{len(bars)} broker days < 83"}
            continue
        rows = [r for r in build_bar_ground(bars)
                if datetime.fromisoformat(str(r["available_time"])) <= when]
        closes = {d: v[3] for d, v in bars.items()}
        cs = bar_contracts(sym, equity, rows, closes, bars)
        contracts_out.extend(cs)
        sid = f"ws_bar_vol_state_{sym.lower()}"
        info: dict[str, Any] = {"status": "MEASURED", "rows": len(rows), "series_id": sid,
                                "data_source": BAR_SOURCE, "last": rows[-1] if rows else None}
        if not dry_run and rows:
            info["lake"] = se.write_lake_series(sid, [{k: v for k, v in r.items()
                                                       if k != "knowable_basis"} for r in rows])
            info["cells"] = se.emit_conditioner_cells(
                sid, [s for s in BAR_SIGNALS if any(isinstance(r.get(s), float) for r in rows)],
                [sym], mechanism=(f"{sym}'s own range-based vol state (Garman-Klass level and "
                                  "term, vol of vol, range extremes, HAR forecast gap) conditions "
                                  "it: vol clusters, and the short end above the long marks "
                                  "trending stress while a calm curve marks mean reversion"),
                falsifier="gate effect indistinguishable from the shuffled-state gate across "
                          "the judged cells", generator=ENGINE,
                sides=(1,) if equity else (1, -1), data_source=BAR_SOURCE)
            obs_out.extend(bar_observations(sym, rows[-1], when))
        out[sym] = info
    return out


def run(*, dry_run: bool = False, reference: Path = REFERENCE,
        universe_dir: Path = UNIVERSE_DIR, now: datetime | None = None,
        series: Mapping[str, Sequence[tuple[str, float]]] | None = None) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    fred = fred_series() if series is None else series
    vint = vintage_index(read_vintages())
    grounds: dict[str, Any] = {}
    all_contracts: list[dict[str, Any]] = []
    obs: list[Any] = []
    for ticker, (cands, equity, term_t, skew_t) in GROUNDS.items():
        held = load_reference(ticker, reference)
        for (t, d), (v, _) in vint.items():
            if t == ticker:
                held.setdefault(d, v)
        fiv = fred_history(ticker, fred)
        substitute = (substitute_corr(fiv, held) if fiv and held else
                      {"status": UNMEASURED, "why": "one side absent here"})
        cfd = broker_vol_cfd(ticker, universe_dir)
        fred_src = f"fred:{FRED_IDS[ticker]}" if ticker in FRED_IDS else ""
        if fiv and _admitted(fred_src):
            iv, data_source, knowable_fn, vintages = (fiv, fred_src, fred_knowable(ticker), None)
        elif cfd is not None:
            # the broker's own vol-index CFD: our data, its close known at the next day's start
            iv, data_source, knowable_fn, vintages = cfd[1], BAR_SOURCE, None, None
            fiv = {}
        elif fiv:
            iv, data_source, knowable_fn, vintages = (fiv, fred_src, fred_knowable(ticker), None)
        else:
            iv, data_source, knowable_fn, vintages = held, f"{VOL_SOURCE}:{ticker}", None, vint
        sym = resolve_symbol(cands, universe_dir)
        if not iv:
            grounds[ticker] = {"status": UNMEASURED, "why": "no reference history and no "
                               "archive vintage (MT5-VolArchive has not written one here)"}
            continue
        if sym is None:
            grounds[ticker] = {"status": "NOT_TRADEABLE_HERE", "tried": list(cands)}
            continue
        closes = daily_closes(sym, universe_dir)
        if fiv:
            # FRED carries VIX and VIX3M only: the term slope is that pair, no skew proxy
            term = {t: fred_history(t, fred) for t in term_t if t != ticker and t in FRED_IDS}
            skew: dict[str, float] = {}
        else:
            term = {t: load_reference(t, reference) for t in term_t if t != ticker}
            skew = load_reference(skew_t, reference) if skew_t else {}
        term = {t: v for t, v in term.items() if v}
        if term:
            term[ticker] = iv
        rows = [r for r in build_ground(ticker, iv=iv, closes=closes, term=term, skew=skew,
                                        vintages=vintages, knowable_fn=knowable_fn)
                if datetime.fromisoformat(str(r["available_time"])) <= when]
        cs = contracts(ticker, sym, equity, rows, closes) if closes else []
        all_contracts.extend(cs)
        sid = f"ws_vol_state_{sym.lower()}"
        info: dict[str, Any] = {"status": "MEASURED", "symbol": sym, "rows": len(rows),
                                "data_source": data_source, "substitute": substitute,
                                "broker_days": len(closes), "series_id": sid,
                                "last": rows[-1] if rows else None}
        if not closes:
            info["why_no_contract"] = f"no {sym}_H1.parquet bars here"
        if not dry_run and rows:
            info["lake"] = se.write_lake_series(sid, [{k: v for k, v in r.items()
                                                       if k != "knowable_basis"} for r in rows])
            sides = (1,) if equity else (1, -1)
            info["cells"] = se.emit_conditioner_cells(
                sid, [s for s in SIGNALS if any(isinstance(r.get(s), float) for r in rows)],
                [sym], mechanism=(f"{ticker} implied-vol state (percentile, variance risk premium "
                                  f"vs this broker's realised vol, IV fixed-point gap, term and "
                                  f"skew) conditions {sym}: the insurance premium is richest "
                                  f"when fear is high and vol mean-reverts"),
                falsifier="gate effect indistinguishable from the shuffled-state gate across "
                          "the judged cells", generator=ENGINE, sides=sides,
                data_source=data_source)
            info["terms"] = {"data_source": data_source,
                             "gauntlet": ("HELD" if info["cells"].get("status") == "HELD_TERMS"
                                          else "admitted"),
                             "why": info["cells"].get("why", "")}
            obs.extend(observations(ticker, sym, rows[-1], when, data_source))
        if cfd is not None:
            info["broker_cfd"] = cfd[0]
        grounds[ticker] = info
    bar_grounds = run_bars(dry_run=dry_run, universe_dir=universe_dir, when=when,
                           contracts_out=all_contracts, obs_out=obs)
    report: dict[str, Any] = {"at": when.isoformat(timespec="seconds"), "engine": ENGINE,
                              "grounds": grounds, "bar_grounds": bar_grounds,
                              "contracts": all_contracts,
                              "cards": ["QG25-05", "QG26-07", "QG26-08", "QG26-09"],
                              "qg26_08": "implied variance = (index/100)^2; the strip is not "
                                         "rebuilt (NOT_WORTH_IT)",
                              "authority": "NONE"}
    if not dry_run:
        se.publish(ENGINE, all_contracts)
        if obs:
            try:
                from libs.research import sensor_contract as sc
                report["ledger"] = sc.SensorLedger().append(obs)
            except Exception as exc:
                report["ledger"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="implied-vol state conditioner (QG25-05/26-07/09)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    rep = run(dry_run=args.dry_run)
    text = json.dumps(rep, indent=1, sort_keys=True, default=str)
    if args.dry_run:
        print(text[:4000])
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(text + "\n", "utf-8")
    tmp.replace(REPORT)
    v = [c.get("verdict") for c in rep["contracts"]]
    print(f"vol_conditioner: grounds={len(rep['grounds'])} contracts={len(v)} "
          f"GAIN={v.count('GAIN')} NO_GAIN={v.count('NO_GAIN')} UNMEASURED={v.count('UNMEASURED')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_ground", "contracts", "date", "run"]
