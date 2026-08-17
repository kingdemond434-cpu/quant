"""Free-data supremacy: derived proprietary state lake (v1).

Builds data/states/*.parquet - self-made information states from the free
lakes (CFTC legacy/TFF/disaggregated + FRED + H1 universe). Every state is
POINT-IN-TIME safe:
  - COT/TFF states activate at report_date + 6 days (Monday-open publication
    convention, same as the COT signal families)
  - FRED daily states activate at the next H1 bar after the FRED value date
  - percentiles are TRAILING (min 2y of history) - never full-sample
No state ever uses information unavailable at its own timestamp.

States (v1): jpy_tff_dealer_net_pct, jpy_tff_am_net_pct, jpy_tff_lm_net_pct,
jpy_tff_am_minus_lm_pct, jpy_legacy_net_pct, jpy_rates_z, jpy_cross_breadth,
gold_legacy_am_net_pct, gold_legacy_lm_net_pct, gold_disagg_mm_net_pct,
gold_disagg_swap_net_pct, gold_physical_paper, gold_macro_stress,
gold_real_yield_z, gold_usd_z, gold_ratio_z, gold_risk_off_z,
usd_liquidity_z, cc_physical_z, session_range_z, session_volume_z.
"""

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "states"
OUT.mkdir(parents=True, exist_ok=True)

LAKE = BASE / "data" / "lake"
UNI = BASE / "data" / "universe"


def load_fred(name: str) -> pd.DataFrame:
    p = LAKE / f"fred_{name}.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["value"])
    df = pd.read_parquet(p)
    col = name if name in df.columns else df.columns[0]
    df = df[[col]].rename(columns={col: "value"})
    df = df.sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    if getattr(df.index, "dtype", None) != "datetime64[ms, UTC]":
        df.index = df.index.as_unit("ms")
    return df


def pct_trailing(s: pd.Series, win: int) -> pd.Series:
    return s.rolling(win, min_periods=win // 2).rank(pct=True)


def reindex_ff(s: pd.Series, idx: pd.DatetimeIndex, ffill: bool = True) -> pd.Series:
    out = pd.Series(np.nan, index=idx, dtype=float)
    locs = idx.searchsorted(s.index)
    vals = s.to_numpy()
    avail = locs < len(idx)
    locs = locs[avail]
    out.iloc[locs] = vals[avail]
    if ffill:
        out = out.ffill()
    return out


def ff_daily(sr: pd.Series, idx: pd.DatetimeIndex) -> pd.Series:
    """Daily series -> H1 index, PIT-safe: the value dated D applies to the
    first bar strictly AFTER D (no exact-match reindex, which silently fails
    when bar timestamps never equal midnight)."""
    src = sr.dropna()
    if src.empty:
        return pd.Series(np.nan, index=idx, dtype=float)
    pos = idx.searchsorted(src.index, side="right")
    out = pd.Series(np.nan, index=idx, dtype=float)
    valid = pos < len(idx)
    out.iloc[pos[valid]] = src.to_numpy()[valid]
    return out.ffill()


def cot_net_pct(legacy_df: pd.DataFrame, col: str, idx: pd.DatetimeIndex,
                min_years: int = 2) -> pd.Series:
    df = legacy_df[["report_date", col]].dropna()
    df = df[df[col] != 0].sort_values("report_date").set_index("report_date")
    net = df[col].replace(0, np.nan).ffill()
    pct = pct_trailing(net, min_years * 52)
    ts = pct.index + timedelta(days=6)
    return reindex_ff(pd.Series(pct.to_numpy(), index=ts), idx)


def main() -> None:
    xau = pd.read_parquet(UNI / "XAUUSD_H1.parquet")
    xau = xau.sort_index()
    xidx = xau.index
    jpy_usd = pd.read_parquet(UNI / "USDJPY_H1.parquet").sort_index()
    jidx = jpy_usd.index

    legacy = {s: pd.read_parquet(BASE / "data" / "cot" / f"{s}.parquet")
              for s in ["jpy", "gold", "silver"]}
    tff = pd.read_parquet(BASE / "data" / "cot_tff" / "jpy.parquet")
    disagg = {s: pd.read_parquet(BASE / "data" / "cot_disagg" / f"{s}.parquet")
              for s in ["gold", "silver"]}
    fr = {n: load_fred(n) for n in
          ["DGS2", "DFII10", "T10YIE", "VIXCLS", "BAMLH0A0HYM2", "DTWEXBGS",
           "DEXUSAL", "DEXCAUS", "DEXUSNZ", "PCOPPUSDM", "WALCL",
           "IR3TIB01JPM156N", "DEXJPUS"]}

    s = {}

    # ---- JPY states (USDJPY H1 index) ----
    def tff_net_pct(col_l: str, col_s: str, oi: str) -> pd.Series:
        df = tff[["report_date", col_l, col_s, oi]].dropna()
        df = df[(df[oi] > 0)].sort_values("report_date").set_index("report_date")
        net = (df[col_l] - df[col_s]) / df[oi]
        pct = pct_trailing(net, 156)
        ts = pct.index + timedelta(days=6)
        return reindex_ff(pd.Series(pct.to_numpy(), index=ts), jidx)

    s["jpy_tff_dealer_net_pct"] = tff_net_pct("dealer_l", "dealer_s", "oi")
    s["jpy_tff_am_net_pct"] = tff_net_pct("am_l", "am_s", "oi")
    s["jpy_tff_lm_net_pct"] = tff_net_pct("lm_l", "lm_s", "oi")
    am_lm = s["jpy_tff_am_net_pct"] - s["jpy_tff_lm_net_pct"]
    s["jpy_tff_am_minus_lm_pct"] = am_lm

    leg_jpy = legacy["jpy"].copy()
    leg_jpy = leg_jpy[leg_jpy["open_interest_all"] > 0]
    leg_jpy["net"] = (leg_jpy["noncomm_positions_long_all"]
                      - leg_jpy["noncomm_positions_short_all"])
    s["jpy_legacy_net_pct"] = cot_net_pct(leg_jpy, "net", jidx)

    jpy_3m = ff_daily(fr["IR3TIB01JPM156N"]["value"], jidx)
    us2y = ff_daily(fr["DGS2"]["value"], jidx)
    diff = (us2y - jpy_3m).dropna()
    s["jpy_rates_z"] = ((diff - diff.rolling(365 * 24, min_periods=52 * 24).mean())
                        / diff.rolling(365 * 24, min_periods=52 * 24).std())

    crosses = ["USDJPY", "EURJPY", "GBPJPY", "CADJPY", "AUDJPY", "NZDJPY", "CHFJPY"]
    ema20s = []
    for c in crosses:
        h = pd.read_parquet(UNI / f"{c}_H1.parquet").sort_index()
        above = (h["close"] > h["close"].ewm(span=20, min_periods=10).mean()).astype(float)
        ema20s.append(above.reindex(jidx).ffill())
    breadth = pd.concat(ema20s, axis=1).mean(axis=1)
    s["jpy_cross_breadth"] = breadth

    # ---- Gold states (XAUUSD H1 index) ----
    def cot_net_abs(legacy_df: pd.DataFrame, col_l: str, col_s: str,
                    oi: str, idx) -> pd.Series:
        df = legacy_df[[ "report_date", col_l, col_s, oi]].dropna()
        df = df[(df[oi] > 0)].sort_values("report_date").set_index("report_date")
        net = (df[col_l] - df[col_s]) / df[oi]
        pct = pct_trailing(net, 156)
        ts = pct.index + timedelta(days=6)
        return reindex_ff(pd.Series(pct.to_numpy(), index=ts), idx)

    leg_gold = legacy["gold"]
    s["gold_legacy_am_net_pct"] = cot_net_abs(
        leg_gold, "noncomm_positions_long_all", "noncomm_positions_short_all",
        "open_interest_all", xidx)
    s["gold_legacy_lm_net_pct"] = cot_net_abs(
        leg_gold, "comm_positions_long_all", "comm_positions_short_all",
        "open_interest_all", xidx)

    for tag, cl, cs in [("gold_disagg_mm_net_pct", "m_money_positions_long_all",
                         "m_money_positions_short_all"),
                        ("gold_disagg_swap_net_pct", "swap_positions_long_all",
                         "swap__positions_short_all")]:
        d = disagg["gold"]
        cols = [c for c in d.columns if c in (cl, cs, "open_interest_all", "report_date")]
        sub = d[cols].dropna()
        sub = sub[sub["open_interest_all"] > 0].sort_values("report_date").set_index("report_date")
        net = (sub[cl] - sub[cs]) / sub["open_interest_all"]
        pct = pct_trailing(net, 156)
        ts = pct.index + timedelta(days=6)
        s[tag] = reindex_ff(pd.Series(pct.to_numpy(), index=ts), xidx)

    s["gold_physical_paper"] = (
        s["gold_legacy_am_net_pct"].fillna(0.5) * 0.5
        + s["gold_disagg_swap_net_pct"].fillna(0.5) * 0.3
        + (1 - s["gold_legacy_lm_net_pct"].fillna(0.5)) * 0.2)

    vix = ff_daily(fr["VIXCLS"]["value"], xidx)
    credit = ff_daily(fr["BAMLH0A0HYM2"]["value"], xidx)
    real_y = ff_daily(fr["DFII10"]["value"], xidx)
    usd = ff_daily(fr["DTWEXBGS"]["value"], xidx)
    ratio = (xau["close"] / ff_daily(pd.read_parquet(UNI / "XAGUSD_H1.parquet").sort_index()["close"], xidx))

    def z(sr: pd.Series, win: int = 365 * 24) -> pd.Series:
        return ((sr - sr.rolling(win, min_periods=win // 2).mean())
                / sr.rolling(win, min_periods=win // 2).std())

    s["gold_real_yield_z"] = z(real_y)
    s["gold_usd_z"] = z(usd)
    s["gold_ratio_z"] = z(ratio)
    s["gold_risk_off_z"] = (z(vix) + z(credit)).fillna(0.0)
    s["gold_macro_stress"] = (z(vix).fillna(0) * 0.4 + z(credit).fillna(0) * 0.25
                              - z(real_y).fillna(0) * 0.2 + z(usd).fillna(0) * 0.15)
    s["usd_liquidity_z"] = z(ff_daily(fr["WALCL"]["value"], xidx))

    aud = ff_daily(fr["DEXUSAL"]["value"], xidx)
    cad = ff_daily(fr["DEXCAUS"]["value"], xidx)
    nzd = ff_daily(fr["DEXUSNZ"]["value"], xidx)
    copper = ff_daily(fr["PCOPPUSDM"]["value"], xidx)
    cc = (z(aud) + z(cad) + z(nzd) + z(copper)) / 4
    s["cc_physical_z"] = cc

    # ---- Session states (XAUUSD): per-hour profile normalization ----
    hh = xau.index.hour
    rng = (xau["high"] - xau["low"]).astype(float)
    keep = ((hh >= 7) & (hh < 10)) | ((hh >= 14) & (hh < 17))
    rng = rng.where(keep, np.nan)
    hour_med = rng.groupby(hh).transform(
        lambda g: g.rolling(24 * 20, min_periods=24).median())
    s["session_range_z"] = (rng - hour_med) / hour_med.replace(0, np.nan)

    tv = xau["tick_volume"].astype(float).replace(0, np.nan)
    tv_med = tv.groupby(hh).transform(
        lambda g: g.rolling(24 * 20, min_periods=24).median())
    s["session_volume_z"] = (tv - tv_med) / tv_med.replace(0, np.nan)

    frame = pd.DataFrame(s).reindex(xau.index)
    frame.index.name = "ts"
    frame.to_parquet(OUT / "free_states.parquet")
    n_syms = len(crosses) + 2
    print(f"states: {len(frame.columns)} series x {len(frame)} bars  "
          f"(inputs: cot legacy+disagg+tff, fred {len(fr)} series, "
          f"{n_syms} H1 instruments)")
    print("columns:", ", ".join(frame.columns))


if __name__ == "__main__":
    main()