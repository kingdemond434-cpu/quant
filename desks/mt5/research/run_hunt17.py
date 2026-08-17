"""Hunt #17: H4/D1 swing factory across the whole universe.

Multi-timeframe mechanism sweep on H4 and D1 bars (resampled from H1, no lookahead):
  d1_trend_pullback  - D1 trend (close vs D1 SMA) + H4 pullback-and-resume entry
  d1_swing_break     - H4 break of prior 20/30-day D1 swing extreme with range expansion
  h4_momentum        - H4 close/SMA cross with 2-bar direction persist
  h4_vol_break       - ATR expansion + prior-bar range break
  d1_inside          - inside-day completion: break of outer-day extreme

Every family runs LONG and SHORT with 2 parameterizations. Same battery as the
institution standard (run_hunt12.py): n>60, deflated t>2 (E_MAX 1.5), PF>1.05,
maxDD>-30R, 3-fold WF all>0, 2x cost stress exp>0 & t>1.5. Resumable via
reports/hunt17_partial.json; completion marker reports/DONE_hunt17.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
E_MAX = 1.5
RR = 2.0
ATR_N = 14
ATR_K = 1.2


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=max(5, n // 3)).mean()


def _atr(h4: pd.DataFrame, n: int) -> pd.Series:
    tr = pd.concat([h4["high"] - h4["low"],
                    (h4["high"] - h4["close"].shift()).abs(),
                    (h4["low"] - h4["close"].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=max(3, n // 3)).mean()


def _sig(t: pd.Timestamp, side: int, ref: float, atr_v: float,
         rr: float, ttl: int, tag: str, trigger: float | None = None,
         wait_bars: int = 2) -> Signal:
    risk = atr_v * ATR_K
    if risk <= 0 or risk != risk:
        raise ValueError("no atr")
    return Signal(time=t, side=side, stop=ref - side * risk,
                  target=ref + side * risk * rr, ttl_bars=ttl, tag=tag,
                  trigger=trigger, wait_bars=wait_bars)


def fam_d1_trend_pullback(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                          d1_n: int = 50, h4_n: int = 20, rr: float = 2.0,
                          ttl: int = 12) -> list[Signal]:
    trend = np.sign(d1["close"] - _sma(d1["close"], d1_n))
    trend_s = pd.Series(trend.to_numpy(float), index=d1.index)
    trend_h4 = trend_s.reindex(h4.index, method="ffill")
    sm = _sma(h4["close"], h4_n)
    a = _atr(h4, ATR_N)
    out = []
    cl = h4["close"].to_numpy(float)
    smv = sm.to_numpy(float)
    for i in range(2, len(h4)):
        if side > 0 and cl[i - 2] > smv[i - 2] and cl[i - 1] > smv[i - 1] and cl[i] > smv[i]:
            try:
                out.append(_sig(h4.index[i], 1, float(cl[i]), float(a.iloc[i]),
                                rr, ttl, "h4_momentum"))
            except ValueError:
                pass
        if side < 0 and cl[i - 2] < smv[i - 2] and cl[i - 1] < smv[i - 1] and cl[i] < smv[i]:
            try:
                out.append(_sig(h4.index[i], -1, float(cl[i]), float(a.iloc[i]),
                                rr, ttl, "h4_momentum"))
            except ValueError:
                pass
    return out


def fam_d1_swing_break(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                       d1_win: int = 20, exp_mult: float = 1.15, rr: float = 2.0,
                       ttl: int = 12) -> list[Signal]:
    hi = d1["high"].rolling(d1_win, min_periods=max(5, d1_win // 2)).max().shift(1)
    lo = d1["low"].rolling(d1_win, min_periods=max(5, d1_win // 2)).min().shift(1)
    hi_h4 = hi.reindex(h4.index, method="ffill")
    lo_h4 = lo.reindex(h4.index, method="ffill")
    rng = h4["high"] - h4["low"]
    avg_rng = rng.rolling(50, min_periods=20).mean()
    a = _atr(h4, ATR_N)
    out = []
    cl = h4["close"].to_numpy(float)
    for i in range(1, len(h4)):
        if float(rng.iloc[i]) <= exp_mult * float(avg_rng.iloc[i]):
            continue
        if side > 0 and cl[i] > hi_h4.iloc[i] and hi_h4.iloc[i] == hi_h4.iloc[i]:
            try:
                out.append(_sig(h4.index[i], 1, float(cl[i]), float(a.iloc[i]), rr, ttl,
                                "d1_swing_break", trigger=float(hi_h4.iloc[i])))
            except ValueError:
                pass
        if side < 0 and cl[i] < lo_h4.iloc[i] and lo_h4.iloc[i] == lo_h4.iloc[i]:
            try:
                out.append(_sig(h4.index[i], -1, float(cl[i]), float(a.iloc[i]), rr, ttl,
                                "d1_swing_break", trigger=float(lo_h4.iloc[i])))
            except ValueError:
                pass
    return out


def fam_h4_momentum(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                    n: int = 34, rr: float = 2.0, ttl: int = 12) -> list[Signal]:
    sm = _sma(h4["close"], n)
    a = _atr(h4, ATR_N)
    cl = h4["close"].to_numpy(float)
    smv = sm.to_numpy(float)
    out = []
    for i in range(2, len(h4)):
        if side > 0 and cl[i - 2] > smv[i - 2] and cl[i - 1] > smv[i - 1] and cl[i] > smv[i]:
            if cl[i - 1] <= smv[i - 1] or cl[i] <= smv[i]:
                continue
            try:
                out.append(_sig(h4.index[i], 1, float(cl[i]), float(a.iloc[i]),
                                rr, ttl, "h4_momentum"))
            except ValueError:
                pass
        if side < 0 and cl[i - 2] < smv[i - 2] and cl[i - 1] < smv[i - 1] and cl[i] < smv[i]:
            try:
                out.append(_sig(h4.index[i], -1, float(cl[i]), float(a.iloc[i]),
                                rr, ttl, "h4_momentum"))
            except ValueError:
                pass
    return out


def fam_h4_vol_break(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                     n1: int = 14, n2: int = 50, k: float = 1.2, rr: float = 2.0,
                     ttl: int = 12) -> list[Signal]:
    a1 = _atr(h4, n1)
    a2 = _atr(h4, n2)
    out = []
    cl = h4["close"].to_numpy(float)
    hi = h4["high"].to_numpy(float)
    lo = h4["low"].to_numpy(float)
    for i in range(1, len(h4)):
        if float(a1.iloc[i]) <= k * float(a2.iloc[i]) or a2.iloc[i] != a2.iloc[i]:
            continue
        if side > 0 and cl[i] > hi[i - 1]:
            try:
                out.append(_sig(h4.index[i], 1, float(cl[i]), float(a1.iloc[i]), rr, ttl,
                                "h4_vol_break", trigger=float(hi[i - 1])))
            except ValueError:
                pass
        if side < 0 and cl[i] < lo[i - 1]:
            try:
                out.append(_sig(h4.index[i], -1, float(cl[i]), float(a1.iloc[i]), rr, ttl,
                                "h4_vol_break", trigger=float(lo[i - 1])))
            except ValueError:
                pass
    return out


def fam_d1_inside(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                  rr: float = 2.0, ttl: int = 12) -> list[Signal]:
    d_hi = d1["high"].to_numpy(float)
    d_lo = d1["low"].to_numpy(float)
    n = len(d1)
    inside = np.zeros(n, dtype=bool)
    for i in range(1, n):
        inside[i] = d_hi[i] < d_hi[i - 1] and d_lo[i] > d_lo[i - 1]
    day_of = {d: i for i, d in enumerate(d1.index.date)}
    a = _atr(h4, ATR_N)
    cl = h4["close"].to_numpy(float)
    out = []
    pending = False
    ohi = olo = 0.0
    prev_day = None
    for i in range(1, len(h4)):
        d = h4.index[i].date()
        if d != prev_day:
            prev_day = d
            di = day_of.get(d)
            if di is not None and inside[di]:
                pending = True
                ohi, olo = d_hi[di - 1], d_lo[di - 1]
        if not pending:
            continue
        if side > 0 and cl[i] > ohi:
            try:
                out.append(_sig(h4.index[i], 1, float(cl[i]), float(a.iloc[i]), rr, ttl,
                                "d1_inside", trigger=float(ohi)))
                pending = False
            except ValueError:
                pass
        if side < 0 and cl[i] < olo:
            try:
                out.append(_sig(h4.index[i], -1, float(cl[i]), float(a.iloc[i]), rr, ttl,
                                "d1_inside", trigger=float(olo)))
                pending = False
            except ValueError:
                pass
    return out


_ANC: pd.DataFrame | None = None


def _anchors_df() -> pd.DataFrame:
    global _ANC
    if _ANC is None:
        try:
            _ANC = pd.read_pickle(BASE / "data" / "cross_asset_anchors.pkl")
        except Exception:
            _ANC = pd.DataFrame()
    return _ANC


def fam_macro_gold_yield(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                         n: int = 34, rr: float = 2.0, ttl: int = 12,
                         yield_z: float = 0.0) -> list[Signal]:
    """H4 momentum on gold gated by the REAL-YIELD state (T10YIE from the
    macro anchors desk): LONG only when the 2y rolling z of 10y breakevens is
    <= yield_z, SHORT only when z >= -yield_z. Mechanism: real-yield regime is
    the dominant gold driver; momentum taken with the regime, not against it.
    Non-XAU symbols / missing anchors -> no signals (battery filters by n>60)."""
    anc = _anchors_df()
    if anc.empty or "T10YIE" not in anc.columns:
        return []
    t10 = anc["T10YIE"].dropna()
    roll = t10.rolling(504, min_periods=120)
    z = (t10 - roll.mean()) / roll.std()
    if z.index.tz is not None:
        z = z.tz_localize(None)
    sm = _sma(h4["close"], n)
    a = _atr(h4, ATR_N)
    cl = h4["close"].to_numpy(float)
    smv = sm.to_numpy(float)
    out = []
    for i in range(2, len(h4)):
        zv = z.get(pd.Timestamp(h4.index[i].date()), float("nan"))
        if zv != zv:
            continue
        if side > 0 and zv <= yield_z and cl[i] > smv[i] \
                and cl[i - 1] > smv[i - 1] and cl[i - 2] > smv[i - 2]:
            try:
                out.append(_sig(h4.index[i], 1, float(cl[i]), float(a.iloc[i]),
                                rr, ttl, "macro_gold_yield"))
            except ValueError:
                pass
        if side < 0 and zv >= -yield_z and cl[i] < smv[i] \
                and cl[i - 1] < smv[i - 1] and cl[i - 2] < smv[i - 2]:
            try:
                out.append(_sig(h4.index[i], -1, float(cl[i]), float(a.iloc[i]),
                                rr, ttl, "macro_gold_yield"))
            except ValueError:
                pass
    return out


FAMILIES = {
    "d1_trend_pullback": fam_d1_trend_pullback,
    "d1_swing_break": fam_d1_swing_break,
    "h4_momentum": fam_h4_momentum,
    "h4_vol_break": fam_h4_vol_break,
    "d1_inside": fam_d1_inside,
    "macro_gold_yield": fam_macro_gold_yield,
}
PARAMS = {
    "d1_trend_pullback": [dict(d1_n=50, h4_n=20, rr=2.0, ttl=12),
                          dict(d1_n=100, h4_n=30, rr=2.5, ttl=24)],
    "d1_swing_break": [dict(d1_win=20, exp_mult=1.15, rr=2.0, ttl=12),
                       dict(d1_win=30, exp_mult=1.10, rr=2.5, ttl=24)],
    "h4_momentum": [dict(n=34, rr=2.0, ttl=12),
                    dict(n=55, rr=2.5, ttl=24)],
    "h4_vol_break": [dict(n1=14, n2=50, k=1.2, rr=2.0, ttl=12),
                     dict(n1=10, n2=40, k=1.3, rr=2.5, ttl=24)],
    "d1_inside": [dict(rr=2.0, ttl=12),
                  dict(rr=2.5, ttl=24)],
    "macro_gold_yield": [dict(n=34, rr=2.0, ttl=12, yield_z=0.0),
                         dict(n=55, rr=2.5, ttl=24, yield_z=-0.25)],
}


def wf_oos(h4: pd.DataFrame, sigs: list, costs: Costs) -> list[float]:
    idx_ns = h4.index.to_numpy().astype("datetime64[ns]").astype("int64")
    sig_ns = np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64")
    sig_locs = np.searchsorted(idx_ns, sig_ns)
    n = len(h4)
    fold = n // 3
    out = []
    for k in range(3):
        o0, o1 = k * fold, (k + 1) * fold if k < 2 else n
        sub = [s for s, sl in zip(sigs, sig_locs) if o0 <= sl < o1]
        r = run_backtest(h4.iloc[o0:o1], sub, costs)
        out.append(float(np.mean([t.r_multiple for t in r.trades])) if r.n >= 20 else np.nan)
    return out


def battery(h4: pd.DataFrame, sigs: list, costs: Costs) -> dict:
    r = run_backtest(h4, sigs, costs).stats()
    r2 = run_backtest(h4, sigs, Costs(costs.spread_per_lot * 2,
                                      costs.commission_per_lot * 2,
                                      costs.contract_oz)).stats()
    wf = wf_oos(h4, sigs, costs)
    defl = r["t_stat"] - E_MAX
    gate = (r["n"] > 60 and defl > 2 and r["profit_factor"] > 1.05
            and r["max_dd_r"] > -30
            and len(wf) == 3 and all(w == w and w > 0 for w in wf)
            and r2["expectancy_r"] > 0 and r2["t_stat"] > 1.5)
    return dict(n=r["n"], exp=r["expectancy_r"], t=r["t_stat"], defl=defl,
                pf=r["profit_factor"], maxdd=r["max_dd_r"],
                exp_stress=r2["expectancy_r"], wf=wf, gate=bool(gate))


def resample(h1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    h4 = h1.resample("4h").agg(agg).dropna()
    d1 = h1.resample("D").agg(agg).dropna()
    return h4, d1


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    log = open(BASE / "logs" / "hunt17_console.txt", "w", encoding="utf-8")
    partial = BASE / "reports" / "hunt17_partial.json"
    done, results = [], []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            done = saved.get("done", [])
            results = list(saved.get("all", []))
        except Exception:
            pass

    def tprint(*a) -> None:
        msg = " ".join(str(x) for x in a)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    tprint(f"{'sym':>8} {'fam':<18} {'side':<5} {'p':>3} {'n':>5} {'exp':>7} "
           f"{'t':>5} {'defl':>5} {'PF':>5} {'maxDD':>7} {'GATE':>5}")
    for sym in sorted(meta):
        if sym in done:
            continue
        h1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        h1 = families._h1(h1)
        h4, d1 = resample(h1)
        m = meta[sym]
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05),
            commission_per_lot=3.50, contract_oz=m["contract_size"])
        for fname, fn in FAMILIES.items():
            for pi, params in enumerate(PARAMS[fname]):
                for side in (1, -1):
                    tag = f"{sym}.{fname}.{pi}.{'L' if side > 0 else 'S'}"
                    if tag in done:
                        continue
                    try:
                        sigs = fn(h4, d1, side, **params)
                    except Exception as e:
                        tprint(f"{sym:>8} {fname:<18} {'L' if side > 0 else 'S':<5} "
                               f"{pi:>3}  ERROR {e!r}")
                        continue
                    if len(sigs) < 60:
                        continue
                    b = battery(h4, sigs, costs)
                    wfs = " ".join(f"{x:+.3f}" if x == x else "  nan" for x in b["wf"])
                    tprint(f"{sym:>8} {fname:<18} {'L' if side > 0 else 'S':<5} {pi:>3} "
                           f"{b['n']:5d} {b['exp']:+7.3f} {b['t']:5.2f} {b['defl']:5.2f} "
                           f"{b['pf']:5.2f} {b['maxdd']:7.1f} "
                           f"{'PASS' if b['gate'] else 'fail':>5}  WF[{wfs}]")
                    results.append(dict(sym=sym, fam=fname, side="LONG" if side > 0 else "SHORT",
                                        param=pi, **b))
                    done.append(tag)
                    partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                                  default=str), encoding="utf-8")
        done.append(sym)
        partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                      default=str), encoding="utf-8")
    (BASE / "reports" / "hunt17.json").write_text(
        json.dumps({"survivors": [r for r in results if r["gate"]],
                    "all": results,
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{sum(1 for r in results if r['gate'])} survivors of "
           f"{len(results)} tests across {len(meta)} symbols")
    (BASE / "reports" / "DONE_hunt17").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()