"""Hunt #19: RFT Tier-S mechanism sweep (ResponsibleForexTrading/Ryan Brown lineage).

RFT_030  rft_aroon_candle  W1 SMA50 + D1 SMA100 trend -> H1 Aroon state -> inside-bar break
RFT_036  rft_retrack       impulse >= 1 ATR -> 25-66% pullback -> continuation
RFT_001  rft_rmi_inside    RMI(14,3) extreme -> inside bar -> mean reversion
RFT_047  rft_sr_reject     prior-day H/L rejection (wick beyond, close back inside)
RFT_051  rft_candle_break  large candle (1.5 ATR) -> buffered break continuation
RFT_040  rft_fail_seq      2 failed setups -> 3rd counterfactual reversal entry

Same institutional battery (run_hunt17): n>60, defl t>2 (E_MAX 1.5), PF>1.05,
maxDD>-30R, 3-fold WF all>0, 2x cost stress exp>0 & t>1.5. Resumable partial;
completion marker reports/DONE_hunt19.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal  # noqa: E402
from run_hunt17 import _atr, battery, resample  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
E_MAX = 1.5
SYMS = ["AUDCAD", "AUDJPY", "CADJPY", "USDJPY", "EURUSD", "GBPUSD", "XAUUSD", "NZDCAD"]
ATR_K = 1.2


def _sig(t, side, ref, atr_v, rr=2.0, ttl=12, tag="", trigger=None, wait_bars=2):
    risk = atr_v * ATR_K
    if risk <= 0 or risk != risk:
        raise ValueError("no atr")
    return Signal(time=t, side=side, stop=ref - side * risk,
                  target=ref + side * risk * rr, ttl_bars=ttl, tag=tag,
                  trigger=trigger, wait_bars=wait_bars)


def rmi(c: np.ndarray, period: int = 14, mom: int = 3) -> np.ndarray:
    ch = c[mom:] - c[:-mom]
    g = np.maximum(ch, 0.0)
    l = np.maximum(-ch, 0.0)
    alpha = 1.0 / period
    ag = np.zeros(len(ch))
    al = np.zeros(len(ch))
    ag[0], al[0] = g[0], l[0]
    for i in range(1, len(ch)):
        ag[i] = alpha * g[i] + (1 - alpha) * ag[i - 1]
        al[i] = alpha * l[i] + (1 - alpha) * al[i - 1]
    out = np.full(len(c), np.nan)
    rs = ag / np.where(al > 0, al, 1e-12)
    out[mom:] = 100.0 * ag / np.where(ag + al > 0, ag + al, 1e-12)
    return out


def aroon(h: np.ndarray, l: np.ndarray, period: int = 14) -> tuple[np.ndarray, np.ndarray]:
    up = np.full(len(h), np.nan)
    dn = np.full(len(l), np.nan)
    for i in range(period, len(h)):
        seg_h = h[i - period: i + 1]
        seg_l = l[i - period: i + 1]
        up[i] = 100.0 * (period - np.argmax(seg_h)) / period
        dn[i] = 100.0 * (period - np.argmin(seg_l)) / period
    return up, dn


def fam_rft_rmi_inside(h4, d1, side, period=14, mom=3, lo=25, hi=75, rr=2.0, ttl=12):
    c = h4["close"].to_numpy(float)
    a = _atr(h4, 14)
    r = rmi(c, period, mom)
    out = []
    for i in range(period + mom + 2, len(h4) - 1):
        if side > 0 and r[i - 1] < lo and h4["high"].iloc[i] <= h4["high"].iloc[i - 1] \
                and h4["low"].iloc[i] >= h4["low"].iloc[i - 1]:
            try:
                out.append(_sig(h4.index[i], 1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "rft_rmi_inside", trigger=float(h4["high"].iloc[i - 1])))
            except ValueError:
                pass
        if side < 0 and r[i - 1] > hi and h4["high"].iloc[i] <= h4["high"].iloc[i - 1] \
                and h4["low"].iloc[i] >= h4["low"].iloc[i - 1]:
            try:
                out.append(_sig(h4.index[i], -1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "rft_rmi_inside", trigger=float(h4["low"].iloc[i - 1])))
            except ValueError:
                pass
    return out


def fam_rft_aroon_candle(h4, d1, side, aroon_p=14, d1_n=100, w1_n=50, rr=2.0, ttl=12):
    w1 = h4["close"].resample("W").last().dropna()
    d1c = d1["close"]
    w1_tr = np.sign(w1 - w1.rolling(w1_n, min_periods=20).mean())
    d1_tr = np.sign(d1c - d1c.rolling(d1_n, min_periods=40).mean())
    w1_s = pd.Series(w1_tr.to_numpy(float), index=w1.index).reindex(h4.index, method="ffill")
    d1_s = pd.Series(d1_tr.to_numpy(float), index=d1.index).reindex(h4.index, method="ffill")
    up, dn = aroon(h4["high"].to_numpy(float), h4["low"].to_numpy(float), aroon_p)
    a = _atr(h4, 14)
    c = h4["close"].to_numpy(float)
    out = []
    for i in range(aroon_p + 2, len(h4) - 1):
        if up[i - 1] != up[i - 1]:
            continue
        if side > 0 and w1_s.iloc[i] > 0 and d1_s.iloc[i] > 0 and up[i - 1] > 70 \
                and h4["high"].iloc[i] <= h4["high"].iloc[i - 1] \
                and h4["low"].iloc[i] >= h4["low"].iloc[i - 1]:
            try:
                out.append(_sig(h4.index[i], 1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "rft_aroon_candle", trigger=float(h4["high"].iloc[i - 1])))
            except ValueError:
                pass
        if side < 0 and w1_s.iloc[i] < 0 and d1_s.iloc[i] < 0 and dn[i - 1] > 70 \
                and h4["high"].iloc[i] <= h4["high"].iloc[i - 1] \
                and h4["low"].iloc[i] >= h4["low"].iloc[i - 1]:
            try:
                out.append(_sig(h4.index[i], -1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "rft_aroon_candle", trigger=float(h4["low"].iloc[i - 1])))
            except ValueError:
                pass
    return out


def fam_rft_retrack(h4, d1, side, imp_bars=4, min_imp=1.0, ret_lo=0.25, ret_hi=0.66,
                    rr=2.0, ttl=12):
    c = h4["close"].to_numpy(float)
    a = _atr(h4, 14)
    h = h4["high"].to_numpy(float)
    l = h4["low"].to_numpy(float)
    out = []
    i = imp_bars + 2
    while i < len(h4) - 1:
        imp = c[i] - c[i - imp_bars]
        if abs(imp) < min_imp * float(a.iloc[i]):
            i += 1
            continue
        dirn = 1 if imp > 0 else -1
        ext = c[i]
        j = i + 1
        pull_start = j
        while j < len(h4) - 1 and (c[j] - c[j - 1]) * dirn <= 0:
            j += 1
        if j > pull_start:
            ret = (ext - c[j - 1]) * dirn / abs(imp)
            if ret_lo <= ret <= ret_hi and (h4.index[j - 1] - h4.index[i]).total_seconds() / 3600 <= 48:
                try:
                    out.append(_sig(h4.index[j - 1], dirn, float(c[j - 1]), float(a.iloc[j - 1]),
                                    rr, ttl, "rft_retrack"))
                except ValueError:
                    pass
                i = j
                continue
        i = j if j > pull_start else i + 1
    return out


def fam_rft_sr_reject(h4, d1, side, buf=0.1, rr=2.0, ttl=12):
    d_hi = d1["high"].to_numpy(float)
    d_lo = d1["low"].to_numpy(float)
    day_of = {d: i for i, d in enumerate(d1.index.date)}
    a = _atr(h4, 14)
    c = h4["close"].to_numpy(float)
    h = h4["high"].to_numpy(float)
    l = h4["low"].to_numpy(float)
    out = []
    prev_day = None
    ph = pl = 0.0
    for i in range(1, len(h4)):
        d = h4.index[i].date()
        if d != prev_day:
            prev_day = d
            di = day_of.get(d)
            if di is not None and di >= 1:
                ph, pl = d_hi[di - 1], d_lo[di - 1]
        if not ph:
            continue
        at = float(a.iloc[i])
        if side > 0 and l[i] < pl - buf * at and c[i] > pl:
            try:
                out.append(_sig(h4.index[i], 1, float(c[i]), at, rr, ttl, "rft_sr_reject"))
            except ValueError:
                pass
        if side < 0 and h[i] > ph + buf * at and c[i] < ph:
            try:
                out.append(_sig(h4.index[i], -1, float(c[i]), at, rr, ttl, "rft_sr_reject"))
            except ValueError:
                pass
    return out


def fam_rft_candle_break(h4, d1, side, mult=1.5, buf=0.1, rr=2.0, ttl=12):
    a = _atr(h4, 14)
    h = h4["high"].to_numpy(float)
    l = h4["low"].to_numpy(float)
    c = h4["close"].to_numpy(float)
    out = []
    for i in range(2, len(h4) - 1):
        at = float(a.iloc[i - 1])
        if at != at or h[i - 1] - l[i - 1] < mult * at:
            continue
        if side > 0 and c[i] > h[i - 1]:
            try:
                out.append(_sig(h4.index[i], 1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "rft_candle_break", trigger=float(h[i - 1] + buf * at)))
            except ValueError:
                pass
        if side < 0 and c[i] < l[i - 1]:
            try:
                out.append(_sig(h4.index[i], -1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "rft_candle_break", trigger=float(l[i - 1] - buf * at)))
            except ValueError:
                pass
    return out


def fam_rft_fail_seq(h4, d1, side, fail_n=2, rr=2.0, ttl=12):
    """Counterfactual entry: after `fail_n` consecutive setups that failed to reach
    +1R within 10 bars, take the NEXT setup as a reversal (mean reversion after
    repeated failed breakouts)."""
    a = _atr(h4, 14)
    h = h4["high"].to_numpy(float)
    l = h4["low"].to_numpy(float)
    c = h4["close"].to_numpy(float)
    fails = 0
    skip_until = 0
    out = []
    i = 2
    while i < len(h4) - 1:
        at = float(a.iloc[i])
        if at != at:
            i += 1
            continue
        risk = at * ATR_K
        if fails >= fail_n:
            if side > 0 and c[i] > h[i - 1]:
                try:
                    out.append(_sig(h4.index[i], 1, float(c[i]), at, rr, ttl,
                                    "rft_fail_seq", trigger=float(h[i - 1])))
                    fails = 0
                    i += 12
                    continue
                except ValueError:
                    pass
            if side < 0 and c[i] < l[i - 1]:
                try:
                    out.append(_sig(h4.index[i], -1, float(c[i]), at, rr, ttl,
                                    "rft_fail_seq", trigger=float(l[i - 1])))
                    fails = 0
                    i += 12
                    continue
                except ValueError:
                    pass
        hit = False
        for j in range(i + 1, min(i + 11, len(h4))):
            if side > 0 and h[j] >= c[i] + risk:
                hit = True
                break
            if side < 0 and l[j] <= c[i] - risk:
                hit = True
                break
        if not hit:
            fails += 1
        else:
            fails = 0
        i += 1
    return out


FAMILIES = {
    "rft_rmi_inside": fam_rft_rmi_inside,
    "rft_aroon_candle": fam_rft_aroon_candle,
    "rft_retrack": fam_rft_retrack,
    "rft_sr_reject": fam_rft_sr_reject,
    "rft_candle_break": fam_rft_candle_break,
    "rft_fail_seq": fam_rft_fail_seq,
}


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    log = open(BASE / "logs" / "hunt19_console.txt", "w", encoding="utf-8")
    partial = BASE / "reports" / "hunt19_partial.json"
    done, results = [], []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text("utf-8"))
            done = saved.get("done", [])
            results = list(saved.get("all", []))
        except Exception:
            pass

    def tprint(*a) -> None:
        msg = " ".join(str(x) for x in a)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    tprint(f"{'sym':>8} {'fam':<16} {'side':<5} {'n':>5} {'exp':>7} {'t':>5} "
           f"{'defl':>5} {'PF':>5} {'maxDD':>7} {'GATE':>5}")
    for sym in SYMS:
        if sym in done:
            continue
        fp = UNI / f"{sym}_H1.parquet"
        if not fp.exists():
            continue
        h1 = families._h1(pd.read_parquet(fp))
        h4, d1 = resample(h1)
        m = meta.get(sym, {})
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5), 0.05),
            commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
        for fname, fn in FAMILIES.items():
            for side in (1, -1):
                tag = f"{sym}.{fname}.{'L' if side > 0 else 'S'}"
                if tag in done:
                    continue
                try:
                    sigs = fn(h4, d1, side)
                except Exception as e:
                    tprint(f"{sym:>8} {fname:<16} {'L' if side > 0 else 'S':<5}  ERROR {e!r}")
                    continue
                if len(sigs) < 60:
                    done.append(tag)
                    continue
                b = battery(h4, sigs, costs)
                wfs = " ".join(f"{x:+.3f}" if x == x else "  nan" for x in b["wf"])
                tprint(f"{sym:>8} {fname:<16} {'L' if side > 0 else 'S':<5} {b['n']:5d} "
                       f"{b['exp']:+7.3f} {b['t']:5.2f} {b['defl']:5.2f} {b['pf']:5.2f} "
                       f"{b['maxdd']:7.1f} {'PASS' if b['gate'] else 'fail':>5}  WF[{wfs}]")
                results.append(dict(sym=sym, fam=fname, side="LONG" if side > 0 else "SHORT", **b))
                done.append(tag)
                partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                              default=str), encoding="utf-8")
        done.append(sym)
        partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                      default=str), encoding="utf-8")
    (BASE / "reports" / "hunt19.json").write_text(
        json.dumps({"survivors": [r for r in results if r["gate"]],
                    "all": results,
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{sum(1 for r in results if r['gate'])} survivors of {len(results)} tests "
           f"across {len(SYMS)} symbols")
    (BASE / "reports" / "DONE_hunt19").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()