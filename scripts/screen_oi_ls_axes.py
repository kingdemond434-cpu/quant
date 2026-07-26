#!/usr/bin/env python3
"""Stage-A axis screen: oi_ls_daily / binance_metrics / futclose_daily.

MECHANISM-FIRST. Trial grid is PRE-DECLARED below and every cell is executed and logged --
there is no "run more until something prints" loop. Screen verdicts come exclusively from
libs.research.axis_screen.stage_a_screen (angle-20 de-contam gate baked in). Anything computed
here outside the harness is DESCRIPTIVE ONLY and is labelled as such.

ALIGNMENT (verified, not assumed -- see reports/axis_screens/oi_ls_daily.json):
  archive `date`   = UTC calendar day; matches the 1d-kline UTC day and the forward collector.
  `oi_first`/`ls_first` = the 00:00:00 UTC 5-min bucket  -> known at the START of day t.
  `oi`/`ls`/`taker`     = mean of all 288 5-min buckets 00:00..23:55 UTC of day t
                          -> an intra-day AVERAGE spanning day t; complete only at 23:55 UTC.
  futclose `close` for date t = 1d kline close at 23:59:59.999 UTC of day t.
  => pairing `oi[t]` with the day-t return (close t-1 -> close t) is CONTEMPORANEOUS and is
     never done here. Signals dated t are only ever used to predict close(t) -> close(t+h).
     The harness enforces this itself (it predicts target_ret[t+1] from signal[t]).

CROSS-SECTIONAL REDUCTION: these are asset-selection signals over 139 symbols, so the target is
the CROSS-SECTIONALLY DEMEANED (relative) return, and the panel is stacked symbol-major before
being handed to the harness. Then:
    harness ic      = pooled cross-sectional IC (signal -> next-period RELATIVE return)
    harness same_period_corr / residual_ic = de-contam vs the SAME-period relative move
    harness sharpe  = PER-NAME long/short book Sharpe (undiversified, ~sqrt(N_eff) below the
                      diversified book) -- conservative, declared.
Horizons use NON-OVERLAPPING h-day sampling (no overlapping-window t-stat inflation).
"""
from __future__ import annotations

import contextlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from libs.research.axis_screen import stage_a_screen

ROOT = Path("/home/quant/quant-platform")
MET = ROOT / "data/lake/bronze/oi_ls_daily"
PX = ROOT / "data/lake/bronze/futclose_daily"
BM = ROOT / "data/lake/bronze/binance_metrics"
OUTDIR = ROOT / "reports/axis_screens"
MIN_XS = 20          # a cross-section needs breadth on the screening date
MIN_OBS_PER_SYM = 60


# ----------------------------------------------------------------- panel loading
def load_panel(dirp: Path, field: str) -> pd.DataFrame:
    cols = {}
    for f in sorted(dirp.glob("*.jsonl")):
        rows = []
        for ln in f.read_text("utf-8").splitlines():
            with contextlib.suppress(Exception):
                r = json.loads(ln)
                rows.append((r["date"], float(r[field])))
        if len(rows) >= MIN_OBS_PER_SYM:
            s = pd.Series(dict(rows), name=f.stem)
            cols[f.stem] = s[~s.index.duplicated()]
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def xs_rank_z(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional normal-scores (van der Waerden) per date: robust, parameter-free,
    and exactly the 'rank the symbols' normalisation the cross-sectional mandate calls for."""
    r = df.rank(axis=1, method="average")
    n = df.notna().sum(axis=1)
    u = r.div(n + 1, axis=0)
    return pd.DataFrame(norm.ppf(u.to_numpy()), index=df.index, columns=df.columns)


def stack(sig: pd.DataFrame, tgt: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict]:
    """Symbol-major stack for the harness. Reports the block-boundary bleed explicitly."""
    ss, tt, blocks = [], [], 0
    for c in sig.columns:
        j = pd.concat([sig[c].rename("s"), tgt[c].rename("t")], axis=1).dropna()
        if len(j) < MIN_OBS_PER_SYM:
            continue
        ss.append(j["s"].to_numpy("float64"))
        tt.append(j["t"].to_numpy("float64"))
        blocks += 1
    if not ss:
        return np.array([]), np.array([]), {"blocks": 0}
    s, t = np.concatenate(ss), np.concatenate(tt)
    bleed = (blocks * 21) / max(len(s), 1)   # 20 z-window rows + 1 wrapped fwd row per block
    return s, t, {"blocks": blocks, "rows": int(len(s)), "boundary_bleed_frac": round(bleed, 5)}


def decile_spread(sig: pd.DataFrame, fwd_rel: pd.DataFrame) -> dict:
    """DESCRIPTIVE ONLY (not a screen): diversified top-vs-bottom-decile spread, equal weight."""
    ok = sig.notna() & fwd_rel.notna()
    sig, fwd_rel = sig.where(ok), fwd_rel.where(ok)
    n = sig.notna().sum(axis=1)
    keep = n >= MIN_XS
    sig, fwd_rel, n = sig[keep], fwd_rel[keep], n[keep]
    if len(sig) < 30:
        return {"note": "insufficient dates"}
    r = sig.rank(axis=1, method="average")
    q = r.div(n + 1, axis=0)
    top = fwd_rel.where(q >= 0.9).mean(axis=1)
    bot = fwd_rel.where(q <= 0.1).mean(axis=1)
    sp = (top - bot).dropna()
    if len(sp) < 30 or sp.std() == 0:
        return {"note": "insufficient spread obs"}
    return {"dates": int(len(sp)), "mean_per_period": round(float(sp.mean()), 6),
            "spread_sharpe_per_period": round(float(sp.mean() / sp.std()), 4)}


TRIALS: list[dict] = []


def run(name: str, sig: pd.DataFrame, tgt: pd.DataFrame, meta: dict) -> dict:
    s, t, info = stack(sig, tgt)
    if len(s) < 100:
        out = {"name": name, "verdict": "INSUFFICIENT-DATA", "n": int(len(s))}
    else:
        out = stage_a_screen(s, t, name=name)
    out.update(meta)
    out.update(info)
    TRIALS.append(out)
    print(f"  {name:52s} n={out.get('n',0):>7} ic={out.get('ic',0):+.4f} "
          f"shR={out.get('sharpe_reversal',0):+6.2f} same={out.get('same_period_corr',0):+.3f} "
          f"resIC={out.get('residual_ic',0):+.4f}  {out['verdict']}", flush=True)
    return out


# ----------------------------------------------------------------- oi_ls_daily
def screen_oi_ls() -> dict:
    print("loading oi_ls_daily panels ...", flush=True)
    P = {f: load_panel(MET, f) for f in ("oi", "ls", "taker", "oi_first", "ls_first")}
    px = load_panel(PX, "close")
    common = px.columns
    for v in P.values():
        common = common.intersection(v.columns)
    common = sorted(common)
    px = px[common].reindex(sorted(set(px.index) | set(P["oi"].index)))
    for k in P:
        P[k] = P[k][common].reindex(px.index)
    print(f"panel: {len(common)} symbols x {len(px)} dates "
          f"[{px.index.min().date()} .. {px.index.max().date()}]", flush=True)

    # PRE-DECLARED CONSTRUCTION GRID (built per horizon on the non-overlapping h-grid)
    def build(h: int) -> dict[str, pd.DataFrame]:
        g = px.index[::h]                       # non-overlapping h-day sampling grid
        p, oi, ls, tk = px.loc[g], P["oi"].loc[g], P["ls"].loc[g], P["taker"].loc[g]
        oif, lsf = P["oi_first"].loc[g], P["ls_first"].loc[g]
        dp = np.log(p).diff()
        doi = np.log(oi.where(oi > 0)).diff()
        dls = np.log(ls.where(ls > 0)).diff()
        return {
            # M1 crowded positioning -> liquidation cascade
            "M1_ls_level": ls,
            "M1_ls_change": dls,
            "M1_lsfirst_level": lsf,                                    # alignment robustness
            # M2 OI build without price confirmation -> fragile leverage
            "M2_oi_growth": doi,
            "M2_oi_divergence_signxsign": np.sign(dp) * np.sign(doi),   # pre-registered sleeve
            "M2_oi_minus_price": doi - dp,
            "M2_oi_build_against_move": doi * -np.sign(dp),
            "M2_oifirst_growth": np.log(oif.where(oif > 0)).diff(),     # alignment robustness
            # M3 taker-flow imbalance -> informed aggression
            "M3_taker_level": tk,
            "M3_taker_change": tk.diff(),
        }, p

    res: dict = {}
    for h in (1, 5, 20):
        cons, p = build(h)
        ret = p.pct_change()
        rel = ret.sub(ret.mean(axis=1), axis=0)          # cross-sectional RELATIVE return
        enough = ret.notna().sum(axis=1) >= MIN_XS
        rel = rel.where(enough)
        print(f"\n--- horizon {h}d (non-overlapping): {int(enough.sum())} usable dates ---")
        for cname, raw in cons.items():
            meta = {"horizon_days": h, "target": "cross-sectional relative return",
                    "normalisation": "cross-sectional rank->normal-scores, then harness z20"}
            o = run(f"{cname}|xsrank|rel|{h}d", xs_rank_z(raw).where(enough), rel, meta)
            o["descriptive_decile_spread"] = decile_spread(
                xs_rank_z(raw).where(enough), rel.shift(-1))
        res[h] = None

    # -- declared secondary normalisation: RAW level (harness z20 is the only normalisation),
    #    target still cross-sectionally relative. Run for the M1/M3 LEVEL constructions where
    #    "extreme vs own history" is the mechanism-faithful reading of crowding.
    print("\n--- secondary normalisation: raw level, harness-z20 only ---")
    for h in (1, 5, 20):
        cons, p = build(h)
        ret = p.pct_change()
        rel = ret.sub(ret.mean(axis=1), axis=0)
        enough = ret.notna().sum(axis=1) >= MIN_XS
        rel = rel.where(enough)
        for cname in ("M1_ls_level", "M3_taker_level", "M2_oi_growth"):
            run(f"{cname}|rawz20|rel|{h}d", cons[cname].where(enough), rel,
                {"horizon_days": h, "target": "cross-sectional relative return",
                 "normalisation": "raw level, harness z20 only"})

    # -- declared target control: ABSOLUTE (non-demeaned) return instead of relative, h=1.
    #    Documents the relative-vs-absolute distinction the mandate calls the key lever.
    print("\n--- target control: ABSOLUTE return (mandate's rejected default) ---")
    cons, p = build(1)
    ret = p.pct_change()
    enough = ret.notna().sum(axis=1) >= MIN_XS
    for cname in ("M1_ls_level", "M2_oi_divergence_signxsign", "M3_taker_level"):
        run(f"{cname}|xsrank|ABS|1d", xs_rank_z(cons[cname]).where(enough),
            ret.where(enough),
            {"horizon_days": 1, "target": "ABSOLUTE return (control)",
             "normalisation": "cross-sectional rank->normal-scores, then harness z20"})
    return {"symbols": len(common), "dates": len(px),
            "range": [str(px.index.min().date()), str(px.index.max().date())]}


# ----------------------------------------------------------------- binance_metrics
def screen_binance_metrics() -> dict:
    """BTCUSDT-only 5-min metrics archive. Adds two fields absent from oi_ls_daily:
    count_toptrader_long_short_ratio and sum_toptrader_long_short_ratio (top 20% of accounts by
    margin balance) -- i.e. SMART-MONEY vs RETAIL. Single asset => no cross-section is possible,
    so the only available target is BTC's own absolute return: the construction shape the
    mandate explicitly flags as the low-prior one. Screened anyway, honestly, and declared."""
    d = BM / "BTCUSDT"
    rows = []
    for z in sorted(d.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                lines = zf.read(zf.namelist()[0]).decode().splitlines()
        except Exception:
            continue
        hdr = lines[0].split(",")
        ix = {c: hdr.index(c) for c in hdr}
        vals = []
        for ln in lines[1:]:
            p = ln.split(",")
            with contextlib.suppress(Exception):
                vals.append((float(p[ix["sum_open_interest"]]),
                             float(p[ix["count_toptrader_long_short_ratio"]]),
                             float(p[ix["sum_toptrader_long_short_ratio"]]),
                             float(p[ix["count_long_short_ratio"]])))
        if len(vals) < 100:
            continue
        a = np.array(vals)
        rows.append({"date": z.stem.split("-metrics-")[1],
                     "oi_intraday_drift": a[-1, 0] / a[0, 0] - 1.0,   # 23:55 vs 00:00 OI
                     "tt_count_ls": a[:, 1].mean(),
                     "tt_pos_ls": a[:, 2].mean(),
                     "retail_ls": a[:, 3].mean()})
    df = pd.DataFrame(rows).set_index("date").sort_index()
    df.index = pd.to_datetime(df.index)
    print(f"\nbinance_metrics BTCUSDT: {len(df)} days "
          f"[{df.index.min().date()} .. {df.index.max().date()}]", flush=True)

    pxb = load_panel(PX, "close")["BTCUSDT"].reindex(df.index)
    ret = pxb.pct_change()
    cons = {
        "M4_smart_minus_retail_count": df["tt_count_ls"] - df["retail_ls"],
        "M4_toptrader_position_ls": df["tt_pos_ls"],
        "M5_oi_intraday_drift": df["oi_intraday_drift"],
    }
    for h in (1, 5):
        g = df.index[::h]
        r = pxb.loc[g].pct_change()
        for cname, s in cons.items():
            j = pd.concat([s.loc[g].rename("s"), r.rename("t")], axis=1).dropna()
            if len(j) < 60:
                TRIALS.append({"name": f"{cname}|BTC_abs|{h}d", "verdict": "INSUFFICIENT-DATA",
                               "n": int(len(j)), "horizon_days": h})
                continue
            o = stage_a_screen(j["s"].to_numpy("float64"), j["t"].to_numpy("float64"),
                               name=f"{cname}|BTC_abs|{h}d")
            o.update({"horizon_days": h, "target": "BTCUSDT absolute return (single asset -- "
                      "no cross-section available in this axis)",
                      "normalisation": "harness z20 only"})
            TRIALS.append(o)
            print(f"  {o['name']:52s} n={o['n']:>7} ic={o['ic']:+.4f} "
                  f"shR={o['sharpe_reversal']:+6.2f} same={o['same_period_corr']:+.3f} "
                  f"resIC={o['residual_ic']:+.4f}  {o['verdict']}", flush=True)
    return {"symbols": 1, "days": int(len(df)),
            "range": [str(df.index.min().date()), str(df.index.max().date())]}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    OUTDIR.mkdir(parents=True, exist_ok=True)
    meta = {}
    if which in ("all", "oi_ls"):
        meta["oi_ls_daily"] = screen_oi_ls()
    if which in ("all", "bm"):
        meta["binance_metrics"] = screen_binance_metrics()
    (OUTDIR / "_raw_trials.json").write_text(json.dumps(
        {"generated": datetime.now(tz=UTC).isoformat(), "panel": meta,
         "n_trials": len(TRIALS), "trials": TRIALS}, indent=1), encoding="utf-8")
    print(f"\nTOTAL TRIALS RUN AND LOGGED: {len(TRIALS)}")
