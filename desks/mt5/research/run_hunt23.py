"""Hunt #23: CROSS-ASSET ANCHOR + REACTION-FAILURE DESK (SALEH_017 unblocked).

Anchors come from data/cross_asset_anchors.pkl (built by macro_desk from
KEYLESS free sources: FRED fredgraph.csv + ALFRED vintages + Yahoo Finance):
DXY/DTWEXBGS, 10y (DGS10/TNX), breakeven (T10YIE), gold (GOLDAMGBD228NLBM/GC),
WTI (DCOILWTICO/CL), VIX (VIXCLS/^VIX), SPX.

Direction cells (standard FAMILIES, rebuilt by universal_gate):
  anc_gold_dxy_resid   XAU daily return vs (DXY, 10y) rolling regression
                       residual z; z < -1.5 -> LONG (gold cheap vs anchors),
                       z > +1.5 -> SHORT (mean reversion of the residual)
  anc_gold_yield_lag   10y yield z > 1.5 with gold NOT falling >= 30% of the
                       expected move -> SHORT gold (lagged reaction arrives)
                       symmetric long on yield z < -1.5 with gold not rising
  anc_cad_oil_lag      WTI z > 1.5 with AUDCAD NOT falling >= 30% of expected
                       -> SHORT AUDCAD (CAD strengthens late); symmetric long
  anc_usdcad_oil_lag   same mechanism on USDCAD (oil up -> USDCAD up late)
  anc_jpy_risk_lag     VIX z > 1.5 with USDJPY NOT falling -> SHORT USDJPY
                       (risk-off lag); symmetric long on VIX z < -1.5

Anchor days are STRICTLY the last completed anchor day BEFORE the signal H4
bar (no same-day lookahead). Entry = next H4 bar open (engine semantics).

SURVIVOR CLAIMS: universal_gate.py 10-gate pass ONLY. Battery stats are
descriptive only. Marker reports/DONE_hunt23.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))
sys.path.insert(0, str(BASE.parent / "quant-platform"))

from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402
from mt5desk.families import _h1  # noqa: E402
from run_hunt17 import resample  # noqa: E402

UNI = BASE / "data" / "universe"
ANCHORS_F = BASE / "data" / "cross_asset_anchors.pkl"
Z_THR = 1.5
W = 60
RR = 2.0
TTL = 8

_anchor_cache: pd.DataFrame | None = None
_ANCHOR_TRIES = 0


def _load(sym: str) -> pd.DataFrame:
    return _h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))


def _atr(h4: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = h4["high"], h4["low"], h4["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


ATR_K = 1.0


def _sig(ts, side, close, a, rr: float, ttl: int, fam: str) -> Signal:
    risk = float(a) * ATR_K
    if risk <= 0 or risk != risk:
        raise ValueError("no atr")
    return Signal(time=ts, side=side, stop=float(close) - side * risk,
                  target=float(close) + side * risk * rr, ttl_bars=ttl, tag=fam)


def _anchors() -> pd.DataFrame | None:
    global _anchor_cache, _ANCHOR_TRIES
    if _anchor_cache is not None:
        return _anchor_cache
    if not ANCHORS_F.exists():
        if _ANCHOR_TRIES == 0:
            print("anchors pkl missing - run macro_desk first", flush=True)
        _ANCHOR_TRIES += 1
        return None
    _anchor_cache = pd.read_pickle(ANCHORS_F)
    _anchor_cache.index = pd.to_datetime(_anchor_cache.index)
    return _anchor_cache


def _pick(anch: pd.DataFrame, *names: str) -> pd.Series:
    for n in names:
        if n in anch.columns:
            s = anch[n].dropna()
            if len(s) > W + 20:
                return s
    return pd.Series(dtype=float)


def _z_of(s: pd.Series, w: int = W) -> pd.Series:
    s = s.dropna()
    m = s.rolling(w, min_periods=w // 2).mean()
    sd = s.rolling(w, min_periods=w // 2).std(ddof=0)
    return ((s - m) / sd).dropna()


def _daily_ret_of(h4: pd.DataFrame) -> pd.Series:
    d = h4["close"].resample("D").last().dropna()
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d.pct_change().dropna()


def _first_bar_next_day(h4: pd.DataFrame, day: pd.Timestamp) -> pd.Timestamp | None:
    for t in h4.index:
        if t.date() > day.date():
            return t
    return None


def _reactfail_days(xr: pd.Series, az: pd.Series, w: int = W) -> dict:
    """Days where the anchor moved >1.5 sigma but the traded asset moved
    <30% of its OWN typical daily move (reaction failure). Returns
    {day: anchor_z}."""
    sd = xr.rolling(w, min_periods=w // 2).std()
    conds = {}
    for day, z in az.items():
        if day not in xr.index or day not in sd.index:
            continue
        s = sd.loc[day]
        if s != s or s <= 0:
            continue
        xm = float(xr.loc[:day].iloc[-1])
        if abs(z) > Z_THR and abs(xm) < 0.3 * s:
            conds[day] = z
    return conds


def _lag_signals(h4: pd.DataFrame, side: int, fam: str,
                 conds: dict) -> list[Signal]:
    """One signal per extreme anchor day (entry = first H4 bar next day).
    LONG fires on anchor z < -1.5 (anchor fell -> asset lags up); SHORT fires
    on anchor z > +1.5 (anchor rose -> asset lags down)."""
    a = _atr(h4, 14)
    c = h4["close"].to_numpy(float)
    idx = h4.index
    out = []
    prev = None
    for day, z in conds.items():
        if prev is not None and day.date() <= prev.date():
            continue
        hit = (side > 0 and z < -Z_THR) or (side < 0 and z > Z_THR)
        if not hit:
            continue
        t = _first_bar_next_day(h4, day)
        if t is None:
            continue
        i = h4.index.get_loc(t)
        if not np.isfinite(c[i]):
            continue
        try:
            out.append(_sig(t, side, float(c[i]), float(a.iloc[i]), RR, TTL, fam))
        except ValueError:
            pass
        prev = day
    return out


def fam_anc_gold_dxy_resid(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                           w: int = W, rr: float = RR, ttl: int = TTL) -> list[Signal]:
    """Gold vs (DXY, 10y) rolling regression residual; MR on the residual."""
    anch = _anchors()
    if anch is None:
        return []
    xau = _pick(anch, "GC", "GOLDAMGBD228NLBM")
    dxy = _pick(anch, "DXY", "DTWEXBGS")
    y10 = _pick(anch, "DGS10", "TNX")
    if not len(xau) or not len(dxy) or not len(y10):
        return []
    xau_r = xau.pct_change().dropna()
    dxy_r = dxy.pct_change().dropna()
    y10_d = y10.diff().dropna()
    df = pd.concat([xau_r, dxy_r, y10_d], axis=1, join="inner").dropna()
    df.columns = ["x", "d", "y"]
    resid = pd.Series(index=df.index, dtype=float)
    for i in range(w, len(df)):
        seg = df.iloc[i - w: i]
        if len(seg) < w // 2:
            continue
        try:
            X = np.column_stack([np.ones(len(seg)), seg["d"], seg["y"]])
            b, *_ = np.linalg.lstsq(X, seg["x"], rcond=None)
            pred = b[0] + b[1] * df["d"].iloc[i] + b[2] * df["y"].iloc[i]
            resid.iloc[i] = df["x"].iloc[i] - pred
        except Exception:
            pass
    z = _z_of(resid, w)
    a = _atr(h4, 14)
    c = h4["close"].to_numpy(float)
    out = []
    prev = None
    for day, zv in z.items():
        if prev is not None and day.date() <= prev.date():
            continue
        if (side > 0 and zv < -Z_THR) or (side < 0 and zv > Z_THR):
            t = _first_bar_next_day(h4, day)
            if t is None:
                continue
            i = h4.index.get_loc(t)
            if not np.isfinite(c[i]):
                continue
            try:
                out.append(_sig(t, side, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "anc_gold_dxy_resid"))
            except ValueError:
                pass
            prev = day
    return out


def fam_anc_gold_yield_lag(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                           w: int = W, rr: float = RR, ttl: int = TTL) -> list[Signal]:
    anch = _anchors()
    if anch is None:
        return []
    y10 = _pick(anch, "DGS10", "TNX")
    xau = _pick(anch, "GC", "GOLDAMGBD228NLBM")
    if not len(y10) or not len(xau):
        return []
    yz = _z_of(y10, w)
    xr = xau.pct_change().dropna()
    conds = _reactfail_days(xr, yz, w)
    if not conds:
        return []
    return _lag_signals(h4, side, "anc_gold_yield_lag", conds)


def _oil_series(anch: pd.DataFrame) -> pd.Series:
    return _pick(anch, "CL", "DCOILWTICO")


def fam_anc_cad_oil_lag(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                        w: int = W, rr: float = RR, ttl: int = TTL) -> list[Signal]:
    """WTI z > 1.5 and AUDCAD failed to fall -> SHORT AUDCAD (CAD late); symmetric."""
    anch = _anchors()
    if anch is None:
        return []
    oil = _oil_series(anch)
    if not len(oil):
        return []
    oz = _z_of(oil, w)
    xr = _daily_ret_of(h4)
    conds = _reactfail_days(xr, oz, w)
    if not conds:
        return []
    return _lag_signals(h4, side, "anc_cad_oil_lag", conds)


def fam_anc_usdcad_oil_lag(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                           w: int = W, rr: float = RR, ttl: int = TTL) -> list[Signal]:
    anch = _anchors()
    if anch is None:
        return []
    oil = _oil_series(anch)
    if not len(oil):
        return []
    oz = _z_of(oil, w)
    xr = _daily_ret_of(h4)
    conds = _reactfail_days(xr, oz, w)
    if not conds:
        return []
    return _lag_signals(h4, side, "anc_usdcad_oil_lag", conds)


def fam_anc_jpy_risk_lag(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                         w: int = W, rr: float = RR, ttl: int = TTL) -> list[Signal]:
    """VIX z > 1.5 and USDJPY failed to fall -> SHORT USDJPY; symmetric long."""
    anch = _anchors()
    if anch is None:
        return []
    vix = _pick(anch, "VIX", "VIXCLS")
    if not len(vix):
        return []
    vz = _z_of(vix, w)
    xr = _daily_ret_of(h4)
    conds = _reactfail_days(xr, vz, w)
    if not conds:
        return []
    return _lag_signals(h4, side, "anc_jpy_risk_lag", conds)


FAMILIES = {
    "anc_gold_dxy_resid": fam_anc_gold_dxy_resid,
    "anc_gold_yield_lag": fam_anc_gold_yield_lag,
    "anc_cad_oil_lag": fam_anc_cad_oil_lag,
    "anc_usdcad_oil_lag": fam_anc_usdcad_oil_lag,
    "anc_jpy_risk_lag": fam_anc_jpy_risk_lag,
}
FAM_SYMS = {
    "anc_gold_dxy_resid": ["XAUUSD"],
    "anc_gold_yield_lag": ["XAUUSD"],
    "anc_cad_oil_lag": ["AUDCAD"],
    "anc_usdcad_oil_lag": ["USDCAD"],
    "anc_jpy_risk_lag": ["USDJPY"],
}
SYMS = ["XAUUSD", "AUDCAD", "USDCAD", "USDJPY"]


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    log = open(BASE / "logs" / "hunt23_console.txt", "w", encoding="utf-8")
    partial = BASE / "reports" / "hunt23_partial.json"
    done, results = [], []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text("utf-8"))
            done, results = saved.get("done", []), list(saved.get("all", []))
        except Exception:
            pass

    def tprint(*a) -> None:
        msg = " ".join(str(x) for x in a)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    tprint(f"{'cell':<32} {'n':>5} {'exp':>7} {'t':>5} {'PF':>5} {'maxDD':>7}")
    if _anchors() is None:
        tprint("anchors missing - waiting for macro_desk to produce pkl ...")
        for _ in range(60):
            time.sleep(30)
            if _anchors() is not None:
                break
    if _anchors() is None:
        tprint("anchors still missing after 30 min; writing DONE (rerun after macro_desk)")
        (BASE / "reports" / "hunt23.json").write_text(
            json.dumps({"survivors": [], "all": [],
                        "note": "no anchors; rerun after macro_desk produces pkl",
                        "swept_at": datetime.now(timezone.utc).isoformat()},
                       indent=2), encoding="utf-8")
        (BASE / "reports" / "DONE_hunt23").write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        return
    for fname, fn in FAMILIES.items():
        for sym in FAM_SYMS.get(fname, []):
            h4, d1 = resample(_load(sym))
            for side in (1, -1):
                tag = f"{sym}.{fname}.{'L' if side > 0 else 'S'}"
                if tag in done:
                    continue
                sigs = fn(h4, d1, side)
                if len(sigs) < 60:
                    done.append(tag)
                    continue
                m = meta.get(sym, {})
                costs = Costs(
                    spread_per_lot=0.48 if sym == "XAUUSD" else max(
                        m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5)
                        * m.get("contract_size", 1e5), 0.05),
                    commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
                r = run_backtest(h4, sigs, costs).stats()
                tprint(f"{tag:<32} {r['n']:5d} {r['expectancy_r']:+7.3f} {r['t_stat']:5.2f} "
                       f"{r['profit_factor']:5.2f} {r['max_dd_r']:7.1f}")
                results.append(dict(sym=sym, fam=fname,
                                    side="LONG" if side > 0 else "SHORT",
                                    n=r["n"], exp=r["expectancy_r"], t=r["t_stat"],
                                    pf=r["profit_factor"], maxdd=r["max_dd_r"]))
                done.append(tag)
                partial.write_text(json.dumps({"done": done, "all": results}, indent=2),
                                   encoding="utf-8")
    (BASE / "reports" / "hunt23.json").write_text(
        json.dumps({"survivors": [], "all": results,
                    "note": "SURVIVOR CLAIMS ONLY via universal_gate.py 10-gate pass",
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{len(results)} cells swept. Survivor claims pending universal 10-gate pass.")
    (BASE / "reports" / "DONE_hunt23").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()