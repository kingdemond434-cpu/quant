"""Hunt #20: SALEH Tier-S mechanism sweep (Mir Saleh / Jesse lineage).

Direction families (H1 entries, H4 anchor):
  saleh_squeeze    H4 BB(20,2)-inside-KC(EMA20+/-2ATR) persistence >=3 -> release ->
                   linreg(20) direction -> ADX(14)>=20 -> first H1 bar of new H4
  saleh_ema_bank   EMA21/50 trend + EMA50 touch -> stop 3ATR -> prev-20-bar target ->
                   bank 0.5 at target, BE, runner trail 1.5R
  saleh_turtle     Donchian(20) breakout, stop 2ATR, ATR target (crisis/convexity sleeve)
  saleh_kama_dir   KAMA(10,2,30) direction + slope
  saleh_kama_er    efficiency-ratio regime (ER>=0.15) continuation
  saleh_gator_dir  Alligator lips>teeth>jaw (+ inverses for SHORT)
  saleh_gator_adx  gator + ADX(14)>=20            (ablation)
  saleh_gator_cmo  gator + CMO(14)>0              (ablation)
  saleh_gator_rs   gator + StochRSI K<20 pullback (ablation)
  saleh_gator_htf  gator + D1 EMA100              (ablation)

Pairs / residual RV (rolling-OLS hedge, z-score MR both sides, spread ATR risk):
  (AUDCAD,NZDCAD) (AUDNZD,NZDCAD) (EURGBP,GBPUSD) (AUDJPY,CADJPY) (EURJPY,GBPJPY)
  (XAUUSD,XAGUSD log)

Same institutional battery. Resumable partial; marker reports/DONE_hunt20.
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
SYMS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "EURJPY", "GBPJPY", "AUDUSD",
        "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURCHF", "AUDJPY", "CADJPY",
        "NZDJPY", "CHFJPY", "BTCUSD", "ETHUSD", "AUDCAD", "AUDNZD", "NZDCAD", "XAGUSD"]
PAIRS = [("AUDCAD", "NZDCAD", False), ("AUDNZD", "NZDCAD", False),
         ("EURGBP", "GBPUSD", False), ("AUDJPY", "CADJPY", False),
         ("EURJPY", "GBPJPY", False), ("XAUUSD", "XAGUSD", True)]


def _sig(t, side, ref, atr_v, rr=2.0, ttl=12, tag="", bank_frac=0.0,
         bank_protect_k=0.0, runner_trail_k=0.0):
    risk = atr_v * 1.2
    if risk <= 0 or risk != risk:
        raise ValueError("no atr")
    return Signal(time=t, side=side, stop=ref - side * risk,
                  target=ref + side * risk * rr, ttl_bars=ttl, tag=tag,
                  bank_frac=bank_frac, bank_protect_k=bank_protect_k,
                  runner_trail_k=runner_trail_k)


def adx(h, l, c, period=14):
    up = np.maximum(h[1:] - h[:-1], 0.0)
    dn = np.maximum(l[:-1] - l[1:], 0.0)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    a = 1.0 / period
    su = np.zeros(len(up)); sd = np.zeros(len(dn)); st = np.zeros(len(tr))
    su[0], sd[0], st[0] = up[0], dn[0], tr[0]
    for i in range(1, len(up)):
        su[i] = a * up[i] + (1 - a) * su[i - 1]
        sd[i] = a * dn[i] + (1 - a) * sd[i - 1]
        st[i] = a * tr[i] + (1 - a) * st[i - 1]
    pdi = 100 * su / np.where(st > 0, st, 1e-12)
    mdi = 100 * sd / np.where(st > 0, st, 1e-12)
    dx = 100 * np.abs(pdi - mdi) / np.where(pdi + mdi > 0, pdi + mdi, 1e-12)
    out = np.full(len(c), np.nan)
    for i in range(period * 2 - 1, len(dx)):
        out[i + 1] = dx[i - period + 1: i + 1].mean()
    return out


def cmo(c, period=14):
    d = c[1:] - c[:-1]
    g = np.where(d > 0, d, 0.0)
    l = np.where(d < 0, -d, 0.0)
    a = 1.0 / period
    ag = np.zeros(len(d)); al = np.zeros(len(d))
    ag[0], al[0] = g[0], l[0]
    for i in range(1, len(d)):
        ag[i] = a * g[i] + (1 - a) * ag[i - 1]
        al[i] = a * l[i] + (1 - a) * al[i - 1]
    out = np.full(len(c), np.nan)
    out[1:] = 100 * (ag - al) / np.where(ag + al > 0, ag + al, 1e-12)
    return out


def rsi(c, period=14):
    d = c[1:] - c[:-1]
    g = np.where(d > 0, d, 0.0)
    l = np.where(d < 0, -d, 0.0)
    a = 1.0 / period
    ag = np.zeros(len(d)); al = np.zeros(len(d))
    ag[0], al[0] = g[0], l[0]
    for i in range(1, len(d)):
        ag[i] = a * g[i] + (1 - a) * ag[i - 1]
        al[i] = a * l[i] + (1 - a) * al[i - 1]
    out = np.full(len(c), np.nan)
    out[1:] = 100 - 100 / (1 + ag / np.where(al > 0, al, 1e-12))
    return out


def stoch_rsi(c, period=14, k_n=3):
    r = rsi(c, period)
    st = np.full(len(c), np.nan)
    for i in range(period + k_n, len(c)):
        lo = np.nanmin(r[i - period + 1: i + 1])
        hi = np.nanmax(r[i - period + 1: i + 1])
        if hi - lo > 0 and not np.isnan(hi):
            st[i] = (r[i] - lo) / (hi - lo) * 100
    k = np.full(len(c), np.nan)
    for i in range(k_n - 1, len(c)):
        seg = st[i - k_n + 1: i + 1]
        if not np.isnan(seg).all():
            k[i] = np.nanmean(seg)
    return k


def kama(c, n=10, fast=2, slow=30):
    fast_a = 2.0 / (fast + 1)
    slow_a = 2.0 / (slow + 1)
    er = np.full(len(c), np.nan)
    k = np.full(len(c), np.nan)
    for i in range(n, len(c)):
        ch = c[i] - c[i - n]
        vol = np.abs(np.diff(c[i - n: i + 1])).sum()
        er[i] = abs(ch) / vol if vol > 0 else 0.0
        sc = (er[i] * (fast_a - slow_a) + slow_a) ** 2
        k[i] = k[i - 1] + sc * (c[i] - k[i - 1]) if not np.isnan(k[i - 1]) else c[i]
    return k, er


def smma(c, n):
    out = np.full(len(c), np.nan)
    if len(c) < n:
        return out
    out[n - 1] = c[:n].mean()
    for i in range(n, len(c)):
        out[i] = (out[i - 1] * (n - 1) + c[i]) / n
    return out


def fam_saleh_squeeze(h4, d1, side, bb_n=20, bb_k=2.0, kc_k=2.0, persist=3, adx_n=14, adx_min=20.0,
                      rr=2.0, ttl=12):
    hc = h4["close"].to_numpy(float)
    hh = h4["high"].to_numpy(float)
    hl = h4["low"].to_numpy(float)
    a4 = _atr(h4, 14).to_numpy(float)
    bb_m = pd.Series(hc).rolling(bb_n).mean().to_numpy()
    bb_s = pd.Series(hc).rolling(bb_n).std(ddof=0).to_numpy()
    kc_m = pd.Series(hc).ewm(span=bb_n, adjust=False).mean().to_numpy()
    squeeze = np.zeros(len(h4))
    for i in range(bb_n, len(h4)):
        squeeze[i] = 1.0 if (bb_m[i] - bb_k * bb_s[i]) >= (kc_m[i] - kc_k * a4[i]) \
            and (bb_m[i] + bb_k * bb_s[i]) <= (kc_m[i] + kc_k * a4[i]) else 0.0
    ax = adx(hh, hl, hc, adx_n)
    slope = np.full(len(h4), np.nan)
    for i in range(bb_n - 1, len(h4)):
        x = np.arange(bb_n)
        slope[i] = np.polyfit(x, hc[i - bb_n + 1: i + 1], 1)[0]
    out = []
    run = 0
    for i in range(bb_n, len(h4) - 1):
        released = squeeze[i - 1] == 1 and squeeze[i] == 0
        if released and run >= persist:
            if side > 0 and slope[i] > 0 and ax[i] >= adx_min:
                try:
                    out.append(_sig(h4.index[i], 1, float(hc[i]), float(a4[i]), rr, ttl, "saleh_squeeze"))
                except ValueError:
                    pass
            if side < 0 and slope[i] < 0 and ax[i] >= adx_min:
                try:
                    out.append(_sig(h4.index[i], -1, float(hc[i]), float(a4[i]), rr, ttl, "saleh_squeeze"))
                except ValueError:
                    pass
        run = run + 1 if squeeze[i] else 0
    return out


def fam_saleh_ema_bank(h4, d1, side, f=21, s=50, tgt=20, stop_k=3.0, rr=2.0, ttl=24,
                       bank_frac=0.5, bank_protect_k=0.0, runner_trail_k=1.5):
    hc = h4["close"].to_numpy(float)
    hh = h4["high"].to_numpy(float)
    hl = h4["low"].to_numpy(float)
    ema_f = pd.Series(hc).ewm(span=f, adjust=False).mean().to_numpy()
    ema_s = pd.Series(hc).ewm(span=s, adjust=False).mean().to_numpy()
    prev20_hi = pd.Series(hh).rolling(tgt).max().shift(1).to_numpy()
    prev20_lo = pd.Series(hl).rolling(tgt).min().shift(1).to_numpy()
    a = _atr(h4, 14).to_numpy(float)
    out = []
    for i in range(s + tgt, len(h4) - 1):
        if side > 0 and ema_f[i - 1] > ema_s[i - 1] and hl[i] <= ema_s[i] <= hh[i]:
            try:
                out.append(_sig(h4.index[i], 1, float(hc[i]), float(a[i]), rr, ttl,
                                "saleh_ema_bank", bank_frac=bank_frac,
                                bank_protect_k=bank_protect_k, runner_trail_k=runner_trail_k))
            except ValueError:
                pass
        if side < 0 and ema_f[i - 1] < ema_s[i - 1] and hl[i] <= ema_s[i] <= hh[i]:
            try:
                out.append(_sig(h4.index[i], -1, float(hc[i]), float(a[i]), rr, ttl,
                                "saleh_ema_bank", bank_frac=bank_frac,
                                bank_protect_k=bank_protect_k, runner_trail_k=runner_trail_k))
            except ValueError:
                pass
    return out


def fam_saleh_turtle(h4, d1, side, chan=20, exit_n=10, stop_k=2.0, rr=2.0, ttl=48):
    hc = h4["close"].to_numpy(float)
    hh = h4["high"].to_numpy(float)
    hl = h4["low"].to_numpy(float)
    hi20 = pd.Series(hh).rolling(chan).max().shift(1).to_numpy()
    lo20 = pd.Series(hl).rolling(chan).min().shift(1).to_numpy()
    a = _atr(h4, 14).to_numpy(float)
    out = []
    for i in range(chan + 2, len(h4) - 1):
        if side > 0 and hc[i] > hi20[i]:
            try:
                out.append(_sig(h4.index[i], 1, float(hc[i]), float(a[i]), rr, ttl, "saleh_turtle"))
            except ValueError:
                pass
        if side < 0 and hc[i] < lo20[i]:
            try:
                out.append(_sig(h4.index[i], -1, float(hc[i]), float(a[i]), rr, ttl, "saleh_turtle"))
            except ValueError:
                pass
    return out


def fam_saleh_kama_dir(h4, d1, side, n=10, rr=2.0, ttl=12):
    hc = h4["close"].to_numpy(float)
    k, er = kama(hc, n, 2, 30)
    a = _atr(h4, 14).to_numpy(float)
    out = []
    for i in range(n + 3, len(h4) - 1):
        if side > 0 and hc[i - 1] > k[i - 1] and k[i - 1] > k[i - 2]:
            try:
                out.append(_sig(h4.index[i], 1, float(hc[i]), float(a[i]), rr, ttl, "saleh_kama_dir"))
            except ValueError:
                pass
        if side < 0 and hc[i - 1] < k[i - 1] and k[i - 1] < k[i - 2]:
            try:
                out.append(_sig(h4.index[i], -1, float(hc[i]), float(a[i]), rr, ttl, "saleh_kama_dir"))
            except ValueError:
                pass
    return out


def fam_saleh_kama_er(h4, d1, side, n=10, er_min=0.15, rr=2.0, ttl=12):
    hc = h4["close"].to_numpy(float)
    k, er = kama(hc, n, 2, 30)
    a = _atr(h4, 14).to_numpy(float)
    out = []
    for i in range(n + 3, len(h4) - 1):
        if side > 0 and hc[i - 1] > k[i - 1] and er[i - 1] >= er_min:
            try:
                out.append(_sig(h4.index[i], 1, float(hc[i]), float(a[i]), rr, ttl, "saleh_kama_er"))
            except ValueError:
                pass
        if side < 0 and hc[i - 1] < k[i - 1] and er[i - 1] >= er_min:
            try:
                out.append(_sig(h4.index[i], -1, float(hc[i]), float(a[i]), rr, ttl, "saleh_kama_er"))
            except ValueError:
                pass
    return out


def _gator_state(h4):
    hc = h4["close"].to_numpy(float)
    lips = smma(hc, 5)
    teeth = smma(hc, 8)
    jaw = smma(hc, 13)
    n = len(hc)
    lips_s = np.full(n, np.nan); teeth_s = np.full(n, np.nan); jaw_s = np.full(n, np.nan)
    lips_s[3:] = lips[:n - 3]
    teeth_s[5:] = teeth[:n - 5]
    jaw_s[8:] = jaw[:n - 8]
    return lips_s, teeth_s, jaw_s


def fam_saleh_gator(h4, d1, side, use_adx=False, use_cmo=False, use_rs=False, use_htf=False,
                    rr=2.0, ttl=12, adx_min=20.0, rs_lo=20.0):
    hc = h4["close"].to_numpy(float)
    hh = h4["high"].to_numpy(float)
    hl = h4["low"].to_numpy(float)
    lips_s, teeth_s, jaw_s = _gator_state(h4)
    ax = adx(hh, hl, hc, 14) if use_adx else None
    cm = cmo(hc, 14) if use_cmo else None
    k = stoch_rsi(hc, 14, 3) if use_rs else None
    d1c = d1["close"]
    d1e = d1c.ewm(span=100, adjust=False).mean()
    htf = pd.Series(d1e.to_numpy(float), index=d1c.index).reindex(h4.index, method="ffill").to_numpy() \
        if use_htf else None
    a = _atr(h4, 14).to_numpy(float)
    out = []
    for i in range(20, len(h4) - 1):
        if np.isnan(lips_s[i]) or np.isnan(teeth_s[i]) or np.isnan(jaw_s[i]):
            continue
        up = lips_s[i] > teeth_s[i] > jaw_s[i]
        dn = lips_s[i] < teeth_s[i] < jaw_s[i]
        if use_adx and (ax is None or np.isnan(ax[i]) or ax[i] < adx_min):
            up = dn = False
        if use_cmo and (cm is None or np.isnan(cm[i])):
            up = dn = False
        if use_cmo and cm[i] <= 0:
            up = False
        if use_cmo and cm[i] >= 0:
            dn = False
        if use_rs and (k is None or np.isnan(k[i])):
            up = dn = False
        if use_rs:
            if k[i] >= rs_lo:
                up = False
            if k[i] <= 100 - rs_lo:
                dn = False
        if use_htf and (htf is None or np.isnan(htf[i])):
            up = dn = False
        if use_htf:
            if hc[i] <= htf[i]:
                up = False
            if hc[i] >= htf[i]:
                dn = False
        if side > 0 and up:
            try:
                out.append(_sig(h4.index[i], 1, float(hc[i]), float(a[i]), rr, ttl, "saleh_gator"))
            except ValueError:
                pass
        if side < 0 and dn:
            try:
                out.append(_sig(h4.index[i], -1, float(hc[i]), float(a[i]), rr, ttl, "saleh_gator"))
            except ValueError:
                pass
    return out


def build_pair_spread(a: pd.DataFrame, b: pd.DataFrame, log_mode: bool, beta_win=120):
    idx = a.index.intersection(b.index)
    ca = a.loc[idx, "close"].to_numpy(float)
    cb = b.loc[idx, "close"].to_numpy(float)
    if log_mode:
        ca = np.log(ca)
        cb = np.log(cb)
    beta = np.full(len(ca), np.nan)
    for i in range(beta_win, len(ca)):
        x = cb[i - beta_win: i]
        y = ca[i - beta_win: i]
        xm = x.mean(); ym = y.mean()
        d = ((x - xm) ** 2).sum()
        if d > 0:
            beta[i] = ((x - xm) * (y - ym)).sum() / d
    beta = np.where(np.isnan(beta), 1.0, beta)
    oa = a.loc[idx, "open"].to_numpy(float)
    ha = a.loc[idx, "high"].to_numpy(float)
    la = a.loc[idx, "low"].to_numpy(float)
    ob = b.loc[idx, "open"].to_numpy(float)
    hb = b.loc[idx, "high"].to_numpy(float)
    lb = b.loc[idx, "low"].to_numpy(float)
    if log_mode:
        oa, ha, la = np.log(oa), np.log(ha), np.log(la)
        ob, hb, lb = np.log(ob), np.log(hb), np.log(lb)
    frame = pd.DataFrame({
        "open": oa - beta * ob, "high": ha - beta * lb,
        "low": la - beta * hb, "close": ca - beta * cb},
        index=idx)
    return frame, beta


def fam_saleh_pairs(spread: pd.DataFrame, z_n=20, z_thr=2.0, rr=2.0, ttl=24, tag="saleh_pairs"):
    s = spread["close"].to_numpy(float)
    z = (s - pd.Series(s).rolling(z_n).mean()) / pd.Series(s).rolling(z_n).std()
    z = z.to_numpy(float)
    a = _atr(spread, 14)
    out = []
    for i in range(z_n + 2, len(spread) - 1):
        if z[i - 1] < -z_thr:
            try:
                out.append(_sig(spread.index[i], 1, float(s[i]), float(a.iloc[i]), rr, ttl, tag))
            except ValueError:
                pass
        elif z[i - 1] > z_thr:
            try:
                out.append(_sig(spread.index[i], -1, float(s[i]), float(a.iloc[i]), rr, ttl, tag))
            except ValueError:
                pass
    return out


DIR_FAMILIES = {
    "saleh_squeeze": fam_saleh_squeeze,
    "saleh_ema_bank": fam_saleh_ema_bank,
    "saleh_turtle": fam_saleh_turtle,
    "saleh_kama_dir": fam_saleh_kama_dir,
    "saleh_kama_er": fam_saleh_kama_er,
    "saleh_gator_dir": lambda h4, d1, side: fam_saleh_gator(h4, d1, side),
    "saleh_gator_adx": lambda h4, d1, side: fam_saleh_gator(h4, d1, side, use_adx=True),
    "saleh_gator_cmo": lambda h4, d1, side: fam_saleh_gator(h4, d1, side, use_cmo=True),
    "saleh_gator_rs": lambda h4, d1, side: fam_saleh_gator(h4, d1, side, use_rs=True),
    "saleh_gator_htf": lambda h4, d1, side: fam_saleh_gator(h4, d1, side, use_htf=True),
}


def base_costs(sym: str, meta: dict) -> Costs:
    if sym == "XAUUSD":
        return Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
    m = meta.get(sym, {})
    return Costs(spread_per_lot=max(
        m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5), 0.05),
        commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    log = open(BASE / "logs" / "hunt20_console.txt", "w", encoding="utf-8")
    partial = BASE / "reports" / "hunt20_partial.json"
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

    tprint(f"{'cell':<36} {'n':>5} {'exp':>7} {'t':>5} {'defl':>5} {'PF':>5} {'maxDD':>7} {'GATE':>5}")
    pair_cache: dict[str, pd.DataFrame] = {}

    for sym in SYMS:
        fp = UNI / f"{sym}_H1.parquet"
        if not fp.exists():
            continue
        h1 = families._h1(pd.read_parquet(fp))
        h4, d1 = resample(h1)
        costs = base_costs(sym, meta)
        for fname, fn in DIR_FAMILIES.items():
            for side in (1, -1):
                tag = f"{sym}.{fname}.{'L' if side > 0 else 'S'}"
                if tag in done:
                    continue
                try:
                    sigs = fn(h4, d1, side)
                except Exception as e:
                    tprint(f"{tag:<36} ERROR {e!r}")
                    continue
                if len(sigs) < 60:
                    done.append(tag)
                    continue
                b = battery(h4, sigs, costs)
                tprint(f"{tag:<36} {b['n']:5d} {b['exp']:+7.3f} {b['t']:5.2f} "
                       f"{b['defl']:5.2f} {b['pf']:5.2f} {b['maxdd']:7.1f} "
                       f"{'PASS' if b['gate'] else 'fail':>5}")
                results.append(dict(sym=sym, fam=fname, side="LONG" if side > 0 else "SHORT", **b))
                done.append(tag)
                partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                              default=str), encoding="utf-8")

    frames = {}
    for sym in SYMS:
        fp = UNI / f"{sym}_H1.parquet"
        if fp.exists():
            frames[sym] = families._h1(pd.read_parquet(fp))
    for a, b, log_mode in PAIRS:
        if a not in frames or b not in frames:
            continue
        spread, _ = build_pair_spread(frames[a], frames[b], log_mode)
        ca = base_costs(a, meta)
        cb = base_costs(b, meta)
        beta_mean = None
        tagp = f"PAIR.{a}-{b}"
        if tagp in done:
            continue
        sigs = fam_saleh_pairs(spread)
        if len(sigs) < 60:
            done.append(tagp)
            continue
        per_a = ca.per_oz_roundtrip()
        per_b = cb.per_oz_roundtrip() * (cb.contract_oz / ca.contract_oz)
        avg_beta = 1.0
        c_pair = Costs(spread_per_lot=(per_a + avg_beta * per_b) - 2 * ca.commission_per_lot,
                        commission_per_lot=ca.commission_per_lot, contract_oz=ca.contract_oz)
        b = battery(spread, sigs, c_pair)
        tprint(f"{tagp:<36} {b['n']:5d} {b['exp']:+7.3f} {b['t']:5.2f} "
               f"{b['defl']:5.2f} {b['pf']:5.2f} {b['maxdd']:7.1f} "
               f"{'PASS' if b['gate'] else 'fail':>5}")
        results.append(dict(sym=tagp, fam="saleh_pairs", side="BOTH", **b))
        done.append(tagp)
        partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                      default=str), encoding="utf-8")

    (BASE / "reports" / "hunt20.json").write_text(
        json.dumps({"survivors": [r for r in results if r["gate"]],
                    "all": results,
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{sum(1 for r in results if r['gate'])} survivors of {len(results)} tests")
    (BASE / "reports" / "DONE_hunt20").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()