#!/usr/bin/env python3
"""PLAYER FOOTPRINT -- where three named participant classes must trade, as judged cells.

Three producers, one organ, one hourly leg (`player_footprint`). Each turns a PUBLIC footprint
of a participant class into a point-in-time series under `data/lake/series/`, and each series
into a handful of pre-registered `exogenous_conditioner` hypotheses on MT5 instruments, donated
through `proposer_common.donate` -- the miner-discovery contract `miner_candidate_compiler`
admits as EXACT_RECIPE -- so the sealed gauntlet judges them like any other cell.

  1. CTA / TREND FOLLOWERS (`pf_cta_<SYMBOL>`). A trend-replication model in the SG-CTA style:
     the sign of the past 20/60/120/250-day log return per horizon, averaged into a position in
     risk units, then vol-scaled to a 10%-annual target (`cta_notional`). Its one-day change is
     the implied FORCED FLOW (`cta_flow_1d`): what a replicating book had to trade yesterday.
     The levels that flip each horizon's sign are the closes 20/60/120/250 days back, so a
     one-sigma move up or down tomorrow implies a known flow (`flip_up`, `flip_dn`) and its
     asymmetry (`flip_asym`). CFTC TFF leveraged funds (CFTC disaggregated managed money for
     metals and energy), read from `futures_state`'s own stamped series, joins it as a
     crowding composite (`crowd_z`).
     Per speed it also publishes the position (`trend_<h>`), the trigger price that flips it
     (`flip_level_<h>`), the distance to it in daily ATRs (`flip_dist_atr_<h>`) and an
     ESTIMATED dollar flow if it is crossed (`est_flow_usd_<h>`: the position delta times an
     assumed industry AUM and vol target, constants `CTA_AUM_USD_ESTIMATE` /
     `CTA_INSTRUMENT_SHARE_ESTIMATE`), summed proximity-weighted into `pending_flow`.

  2. GOLD ETF HOLDINGS (`pf_gold_etf`). SPDR Gold Shares' public historical archive (GLD:
     tonnes and ounces in trust per day), turned into daily, five- and twenty-day flows in
     tonnes and a z-scored flow, plus two cells that read the flow against the market:
     `flow_px_resid`, the five-day GLD flow's residual on XAUUSD's five-day log return over the
     same window (a rolling 250-row OLS, past and current rows only: creations the price has
     NOT yet answered), and `flow_streak`, the signed count of consecutive creation (+) or
     redemption (-) days, reset by a no-change day. The XAUUSD close each GLD row sees is the
     newest broker-day close whose own `available_time` is at or before the row's, so the
     return never reaches past the flow's 09:00 New York stamp. Extends `GOLD_ETF_creation_redemption_flow`
     (data/hypotheses/compiled_proposals.json, a HEURISTIC_PROXY that measured distance from a
     20-bar mean) and `GLD_IAU_Gold_ETF_Rebalance` (side_channels/operational_calendar_miner.py)
     with the issuer's own measured flow. IAU is NOT fetched: iShares publishes a current
     holdings snapshot, not a public history, and a snapshot accumulated from today cannot be
     backtested; it is named in the report as a gap.
     SUPERSEDES `research/fetch_gld.py`, the legacy GLD fetcher: it writes to a hard-coded Dell
     path and reads the old `GLD_US_holdings.xlsx` URL, which 404s. It is left in place on
     purpose -- removing it is the owner's call -- and nothing here reads what it writes.

  3. ASSET MANAGERS / REAL MONEY (`pf_realmoney_<SYMBOL>`). CFTC TFF asset-manager net/OI
     against leveraged-funds net/OI (`am_vs_lev`: real money leaning one way while fast money
     leans the other), and a month-/quarter-end REBALANCE estimate (`rebal_pressure`): a
     balanced fund that let equities outrun bonds over the quarter must sell equities into its
     last days, and a foreign holder whose US equities outran home equities over the month
     sells dollars at month-end. The pressure is non-zero only in the last five NY business
     days of a month (full weight at quarter-end, half otherwise).

WHAT IS REUSED, NOT REWRITTEN. The CFTC data is `research/futures_state.py`'s: it already
collects TFF / disaggregated / legacy through the CFTC public-reporting API on its own hourly
leg, by EXACT market-name rename chains, signed into each market's primary MT5 target, with its
release calendar (federal holidays, CFTC closures, the 2018-19 and 2025 shutdown catch-up
dates). No second fetcher. When that organ has not yet written a series, the producer falls
back to `mt5desk/fetch_tff.py`'s parquets under `data/cot_tff/`, filtered to the exact market
names -- those files were built by a substring match plus `drop_duplicates("report_date")`, so
`eur.parquet` is one third EUR/GBP and EUR/JPY cross-rate rows, and they are never read
unfiltered.

POINT IN TIME, STATED BECAUSE IT IS WHERE THIS GOES WRONG SILENTLY.
  * A CFTC report is as of TUESDAY and public at 15:30 New York on its release day: the Friday
    after, the next business day when a federal holiday or a CFTC closure falls between the
    two, and CFTC's own catch-up dates after a shutdown (`cot_usable_from`, built on
    `futures_state.cftc_release_day`). Every row's `available_time` is that instant in UTC.
    When `futures_state`'s stamp names a LATER day, the later one wins: a later label is never
    a look-ahead; an earlier one is.
  * The bars are BROKER stamps under a UTC label, New York + 7 h (`libs/regime/session_clock`):
    UTC+3 while New York is on daylight time, UTC+2 otherwise. So 15:30 New York is 22:30 on
    the bar clock in both seasons. `exogenous_conditioner` treats `available_time` as UTC and
    holds it back `lag_hours` before aligning it to bars; every hypothesis here carries
    `lag_hours = 3`, the larger of the two offsets, so the value lands on the bar clock at
    exactly its release in summer and one hour after it in winter -- never before.
  * Price-derived series (the CTA model and the rebalance estimate) are known at the CLOSE of
    the broker day they use (stamp `D+1 00:00` on the bar clock); that stamp is converted to
    true UTC with `session_clock.server_to_utc`, and the same 3-hour hold applies.
  * GLD holdings for day D are stamped 09:00 New York on the next business day: SPDR posts the
    file after the 16:15 NAV strike, and nothing here assumes it is up the same evening.

TRIALS ARE CHARGED ONCE PER HYPOTHESIS. Every hypothesis is identified by
`proposer_common.identity(symbol, family, params)`. `state.json["charged"]` holds every identity
ever donated; a pass donates only identities not in it, and `tests_run` is exactly the number of
new identities in that donation. A pass with nothing new writes no contract file and charges
nothing. A hypothesis whose series is absent or too short is HELD -- not donated, not charged --
and named in the report until its data arrives.

PUBLIC DATA ONLY. CFTC and the SPDR archive are public pages read with one honest User-Agent
through `libs.data.polite_fetch`, retries off; a 401/403/429/451 is a HARD STOP recorded in
state and never retried until `--release-hard-stops`. No login, no key, no paid feed, no
crypto-exchange universe; single-name equities are never targeted (the donation door refuses
them anyway).

    python desks/mt5/research/player_footprint.py --once
    python desks/mt5/research/player_footprint.py --once --dry-run   # build; write, donate nothing
    python desks/mt5/research/player_footprint.py --once --offline   # no network: held data only
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "player_footprint"
SERIES = DESK / "data" / "lake" / "series"
STATE = DESK / "data" / "player_footprint" / "state.json"
GLD_RAW = DESK / "data" / "player_footprint" / "gld_archive.csv"
OUT = DESK / "reports" / "PLAYER_FOOTPRINT.json"
FS_REGISTRY = DESK / "research" / "futures_state_sources.json"
COT_TFF = DESK / "data" / "cot_tff"

UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; player_footprint)"
HARD_STOP = frozenset({401, 403, 429, 451})
#: SPDR Gold Shares' public historical archive (the one `world_dataset_hunter.LEGACY_PROBES`
#: already names for `spdr_gld_holdings`). The older `GLD_US_holdings.xlsx` URL 404s.
GLD_URL = "https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv"
GLD_REFETCH_H = 20.0
TROY_OZ_PER_TONNE = 32150.7466

NY = ZoneInfo("America/New_York")
COT_RELEASE_ET = dtime(15, 30)
GLD_AVAILABLE_ET = dtime(9, 0)
#: Hours every hypothesis holds its series back before it may touch a bar: the larger of the
#: broker clock's two UTC offsets (New York + 7 h is UTC+3 in US summer time, UTC+2 otherwise).
LAG_HOURS = 3
FAMILY = "exogenous_conditioner"
MIN_SERIES_ROWS = 30          # family_exogenous_conditioner.MIN_OBSERVATIONS

#: SG-CTA-style trend horizons, in trading days, equally weighted.
HORIZONS: tuple[int, ...] = (20, 60, 120, 250)
VOL_SPAN = 60
TARGET_VOL_ANNUAL = 0.10
ATR_N = 20
#: THE FLOW SIZE IS AN ESTIMATE, AND THESE TWO NUMBERS ARE ITS ENTIRE ASSUMPTION. Trend-following
#: CTA assets are put at roughly USD 350bn (order of magnitude of the public BarclayHedge /
#: SG Trend index-manager figures; not measured here), spread over ~60 liquid futures markets.
#: A horizon's flip moves its 1/len(HORIZONS) share of a vol-targeted position from +1 to -1
#: (or back), so the dollar flow is 2 * share * leverage * AUM * INSTRUMENT_SHARE. Only the
#: SIGN and the relative SIZE across days carry information into a z-scored cell; the level
#: is a documented guess and is never read as a measured flow.
CTA_AUM_USD_ESTIMATE = 3.5e11
CTA_INSTRUMENT_SHARE_ESTIMATE = 1.0 / 60.0
MIN_FLIP_DIST_ATR = 0.25
Z_WEEKS = 156

#: MT5 symbol -> futures_state market id. The futures_state series is already signed into the
#: market's primary target (`sign: -1` for JPY, CAD, CHF), and each symbol here IS that target.
CTA_TARGETS: dict[str, str | None] = {
    "EURUSD": "eur", "GBPUSD": "gbp", "USDJPY": "jpy", "AUDUSD": "aud", "USDCAD": "cad",
    "USDCHF": "chf", "NZDUSD": "nzd", "XAUUSD": "gold", "XAGUSD": "silver",
    "US500": "sp500", "NAS100": "nasdaq", "US30": "djia", "US2000": "russell",
    "JPN225": "nikkei", "GER40": None, "UK100": None, "XTIUSD": "wti", "XBRUSD": "brent",
}
#: The leveraged-money column per market, in preference order: TFF leveraged funds for
#: financials, disaggregated managed money for metals and energy (TFF does not carry them).
LEV_COLUMNS: tuple[str, ...] = ("tff_lev_money_net_oi", "disagg_m_money_net_oi")
AM_COLUMN = "tff_asset_mgr_net_oi"
#: fetch_tff slug -> futures_state market id, for the fallback read.
TFF_SLUGS: dict[str, str] = {"eur": "eur", "gbp": "gbp", "jpy": "jpy", "aud": "aud",
                             "cad": "cad", "chf": "chf", "nzd": "nzd", "sp500": "sp500",
                             "nasdaq100": "nasdaq"}
REALMONEY_TFF: dict[str, str] = {
    "EURUSD": "eur", "GBPUSD": "gbp", "USDJPY": "jpy", "AUDUSD": "aud", "USDCAD": "cad",
    "USDCHF": "chf", "NZDUSD": "nzd", "US500": "sp500", "NAS100": "nasdaq", "US30": "djia",
    "US2000": "russell", "JPN225": "nikkei",
}
#: Rebalance targets. Indices: the index against the US 10-year CFD (a balanced fund's two
#: sleeves). FX: the US index against the home index of the currency, signed so a positive
#: value means the month-end flow BUYS the symbol.
BOND = "UST10Y"
US_EQUITY = "US500"
REBAL_INDEX: tuple[str, ...] = ("US500", "NAS100", "US30", "US2000", "GER40", "UK100",
                                "JPN225", "EUSTX50")
REBAL_FX: dict[str, tuple[str, int]] = {
    # symbol: (home index, sign of "US outran home" on the symbol)
    "EURUSD": ("GER40", +1), "GBPUSD": ("UK100", +1), "AUDUSD": ("AUS200", +1),
    "USDJPY": ("JPN225", -1),
}
REBAL_WINDOW_BDAYS = 5


# ============================================================================ point in time

def _calendar() -> dict[str, Any]:
    doc = _read(FS_REGISTRY, {}) or {}
    cal = doc.get("cftc_release_calendar") if isinstance(doc, dict) else None
    return cal if isinstance(cal, dict) else {}


@lru_cache(maxsize=8)
def _holidays(closures: tuple[str, ...] = ()) -> frozenset[pd.Timestamp]:
    """US federal holidays (observed) plus named CFTC closures, built once per closure set."""
    from research.futures_state import _us_holidays
    return _us_holidays(closures)


def cot_release_day(report_day: Any, calendar: Mapping[str, Any] | None = None) -> pd.Timestamp:
    """The New York calendar day a COT report dated `report_day` became public."""
    from research.futures_state import cftc_release_day
    closures = tuple(str(c) for c in ((calendar or {}).get("closures") or ()))
    return pd.Timestamp(cftc_release_day(pd.Timestamp(report_day), calendar,
                                         _holidays(closures))).normalize()


def cot_usable_from(report_day: Any, calendar: Mapping[str, Any] | None = None) -> pd.Timestamp:
    """The UTC instant a COT report dated `report_day` was public: 15:30 New York on its
    release day (the Friday after; the next business day when a federal holiday or a CFTC
    closure falls in between; CFTC's own catch-up dates after a shutdown)."""
    day = cot_release_day(report_day, calendar)
    local = datetime.combine(day.date(), COT_RELEASE_ET, tzinfo=NY)
    return pd.Timestamp(local).tz_convert("UTC")


def to_broker(ts_utc: Any) -> pd.Timestamp:
    """A true UTC instant as the bar clock stamps it: New York wall time + 7 h, UTC-labelled."""
    t = pd.Timestamp(ts_utc)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    wall = t.tz_convert(NY).tz_localize(None) + pd.Timedelta(hours=7)
    return wall.tz_localize("UTC")


def bar_label_after_lag(available_utc: Any, lag_hours: int = LAG_HOURS) -> pd.Timestamp:
    """Where `exogenous_conditioner` places a value on the bar clock: UTC plus the lag."""
    t = pd.Timestamp(available_utc)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t + pd.Timedelta(hours=int(lag_hours))


def _naive_day(day: Any) -> pd.Timestamp:
    t = pd.Timestamp(day)
    return (t.tz_convert("UTC").tz_localize(None) if t.tzinfo is not None else t).normalize()


def _next_ny_business_day(day: pd.Timestamp) -> pd.Timestamp:
    hol = _holidays()
    d = _naive_day(day) + pd.Timedelta(days=1)
    while d.weekday() >= 5 or d in hol:
        d += pd.Timedelta(days=1)
    return d


def gld_available(day: Any) -> pd.Timestamp:
    """GLD holdings dated `day`: 09:00 New York on the next business day, in UTC."""
    nxt = _next_ny_business_day(pd.Timestamp(day))
    return pd.Timestamp(datetime.combine(nxt.date(), GLD_AVAILABLE_ET, tzinfo=NY)).tz_convert(
        "UTC")


def daily_closes(h1: pd.DataFrame | None) -> pd.DataFrame:
    """Broker-day closes from H1 bars, each with the true UTC instant it was known (the close
    of the broker day: stamp D+1 00:00 on the bar clock, converted by session_clock)."""
    if h1 is None or h1.empty or "close" not in h1.columns:
        return pd.DataFrame(columns=["close", "available_time"])
    from libs.regime.session_clock import server_to_utc
    idx = pd.DatetimeIndex(pd.to_datetime(h1.index, utc=True))
    s = pd.Series(pd.to_numeric(h1["close"], errors="coerce").to_numpy(), index=idx).dropna()
    s = s[s > 0]
    if s.empty:
        return pd.DataFrame(columns=["close", "available_time"])
    d = s.resample("1D").last().dropna()
    # A TRAILING PARTIAL DAY is not a close: the live tail's last bar is mid-session and its
    # value would change next pass. A day is complete once it reaches the hour this
    # instrument's days usually end on (the modal last-bar hour, so gold and indices with an
    # earlier daily break are judged on their own session, not FX's 23:00).
    last_hour = pd.Series(s.index.hour, index=s.index).resample("1D").max().dropna()
    if len(d) > 1 and len(last_hour) and last_hour.iloc[-1] < last_hour.mode().iloc[0]:
        d = d.iloc[:-1]
    known_broker = pd.DatetimeIndex(d.index + pd.Timedelta(days=1))
    out = pd.DataFrame({"close": d.to_numpy()}, index=d.index)
    for col, how in (("high", "max"), ("low", "min")):
        if col in h1.columns:
            x = pd.Series(pd.to_numeric(h1[col], errors="coerce").to_numpy(), index=idx)
            out[col] = x.resample("1D").agg(how).reindex(d.index).to_numpy()
    out["available_time"] = server_to_utc(known_broker).to_numpy()
    return out


# ============================================================================ 1. CTA model (pure)

def cta_replication(close: pd.Series, horizons: Sequence[int] = HORIZONS,
                    vol_span: int = VOL_SPAN, target_vol: float = TARGET_VOL_ANNUAL,
                    high: pd.Series | None = None, low: pd.Series | None = None
                    ) -> pd.DataFrame:
    """The replicated trend book on one instrument's daily closes. Strictly causal: row t uses
    closes up to and including t only.

    cta_pos       mean over horizons of sign(ln P_t - ln P_{t-h}), in [-1, 1] (risk units)
    cta_notional  cta_pos * target daily vol / realised daily vol (EWMA, span `vol_span`)
    cta_flow_1d   cta_notional_t - cta_notional_{t-1}: the flow the book had to trade
    cta_flow_5d   the same over five days
    flip_up       the change in cta_notional if tomorrow closes one daily sigma higher
    flip_dn       the same for one sigma lower (each horizon's flip level is the close it is
                  measured against tomorrow, P_{t+1-h}, known today)
    flip_asym     flip_up + flip_dn: > 0 when a rally would force more buying than a decline
                  would force selling
    flip_dist     the nearest flip level in daily sigmas (|ln P_t - ln P_{t+1-h}| / sigma)

    Per speed h (multi-speed positions, trigger levels, distance, estimated flow):
    trend_<h>          that speed's position today, sign(ln P_t - ln P_{t-h})
    flip_level_<h>     the price that flips that speed tomorrow (P_{t+1-h}, known today)
    flip_dist_atr_<h>  (P_t - flip_level_<h>) / ATR(20): signed, in daily ATRs
    est_flow_usd_<h>   ESTIMATED USD flow if that level is crossed: the speed's position delta
                       (-2 * its sign * 1/len(horizons)) times the vol-target leverage times
                       CTA_AUM_USD_ESTIMATE * CTA_INSTRUMENT_SHARE_ESTIMATE (an assumption,
                       documented at those constants -- never a measurement)
    pending_flow       sum over speeds of est_flow_usd_<h> / max(|flip_dist_atr_<h>|, 0.25):
                       the estimated flow weighted by how close its trigger sits; < 0 when the
                       nearby triggers would force selling
    ATR uses the daily high/low when given, else |close-to-close| (true range of a close-only
    series)."""
    p = pd.to_numeric(close, errors="coerce").astype(float)
    p = p.where(p > 0)
    lp = np.log(p)
    r = lp.diff()
    sigma = r.ewm(span=vol_span, min_periods=max(10, vol_span // 3)).std()
    sigma = sigma.where(sigma > 0)
    scale = (target_vol / math.sqrt(252.0)) / sigma
    w = 1.0 / len(horizons)
    signs = pd.DataFrame({h: np.sign(lp - lp.shift(h)) for h in horizons}, index=p.index)
    complete = signs.notna().all(axis=1)
    pos = (signs.sum(axis=1) * w).where(complete)
    notional = pos * scale
    out = pd.DataFrame(index=p.index)
    out["cta_pos"] = pos
    out["cta_notional"] = notional
    out["cta_flow_1d"] = notional.diff()
    out["cta_flow_5d"] = notional.diff(5)
    # Tomorrow's horizon-h signal compares P_{t+1} with P_{t+1-h}: that reference is known now.
    dist = pd.DataFrame({h: (lp - lp.shift(h - 1)) / sigma for h in horizons}, index=p.index)
    now_sign = np.sign(dist)
    up = (np.sign(dist + 1.0) - now_sign).sum(axis=1) * w
    dn = (np.sign(dist - 1.0) - now_sign).sum(axis=1) * w
    ok = complete & dist.notna().all(axis=1)
    out["flip_up"] = (up * scale).where(ok)
    out["flip_dn"] = (dn * scale).where(ok)
    out["flip_asym"] = out["flip_up"] + out["flip_dn"]
    out["flip_dist"] = dist.abs().min(axis=1).where(ok)
    prev = p.shift(1)
    if high is not None and low is not None:
        hi = pd.to_numeric(high, errors="coerce").reindex(p.index)
        lo = pd.to_numeric(low, errors="coerce").reindex(p.index)
        tr = pd.concat([hi - lo, (hi - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    else:
        tr = (p - prev).abs()
    atr = tr.rolling(ATR_N, min_periods=ATR_N).mean()
    atr = atr.where(atr > 0)
    usd_unit = 2.0 * w * CTA_AUM_USD_ESTIMATE * CTA_INSTRUMENT_SHARE_ESTIMATE
    pending = pd.Series(0.0, index=p.index)
    for h in horizons:
        level = p.shift(h - 1)
        s_now = np.sign(p - level)
        d_atr = (p - level) / atr
        flow = -s_now * usd_unit * scale
        out[f"trend_{h}"] = signs[h]
        out[f"flip_level_{h}"] = level
        out[f"flip_dist_atr_{h}"] = d_atr
        out[f"est_flow_usd_{h}"] = flow
        pending = pending + flow / d_atr.abs().clip(lower=MIN_FLIP_DIST_ATR)
    out["pending_flow"] = pending.where(ok & atr.notna())
    return out


def zscore(s: pd.Series, window: int) -> pd.Series:
    mu = s.rolling(window, min_periods=max(10, window // 6)).mean()
    sd = s.rolling(window, min_periods=max(10, window // 6)).std(ddof=0)
    return ((s - mu) / sd.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)


def asof_join(daily: pd.DataFrame, weekly: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    """Attach to each daily row the newest weekly value PUBLISHED at or before it, on the two
    frames' own `available_time` clocks; the joined row's stamp is the later of the two."""
    left = daily.reset_index(drop=True).copy()
    left["_t"] = pd.to_datetime(left["available_time"], utc=True).astype("datetime64[ns, UTC]")
    right = weekly[["available_time", *cols]].copy()
    right["_t"] = pd.to_datetime(right["available_time"], utc=True).astype("datetime64[ns, UTC]")
    right = right.dropna(subset=["_t"]).sort_values("_t").rename(
        columns={"available_time": "_w_available"})
    left = left.dropna(subset=["_t"]).sort_values("_t")
    joined = pd.merge_asof(left, right, on="_t", direction="backward")
    w_av = pd.to_datetime(joined["_w_available"], utc=True)
    joined["available_time"] = pd.concat(
        [pd.to_datetime(joined["available_time"], utc=True), w_av], axis=1).max(axis=1)
    return joined.drop(columns=["_t", "_w_available"])


# ============================================================================ CFTC (reused)

def cot_series(market: str, calendar: Mapping[str, Any] | None = None,
               series_dir: Path | None = None, tff_dir: Path | None = None,
               registry: Mapping[str, Any] | None = None) -> tuple[pd.DataFrame | None, str]:
    """One market's stamped positioning, re-stamped at its exact release instant.

    `futures_state`'s `cot_<market>` series first (its own collector, exact-name chains,
    already signed). Else `fetch_tff.py`'s parquet filtered to the exact market names. The
    frame carries `event_time` (the as-of Tuesday), `available_time` (UTC release) and the
    `*_net_oi` columns present."""
    cal = calendar if calendar is not None else _calendar()
    base = series_dir or SERIES
    p = base / f"cot_{market}.parquet"
    if p.exists():
        try:
            df = pd.read_parquet(p)
        except Exception as exc:
            return None, f"cot_{market}.parquet unreadable ({type(exc).__name__})"
        if "event_time" not in df.columns:
            return None, f"cot_{market}.parquet has no event_time"
        df = df.copy()
        ev = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
        exact = pd.Series([cot_usable_from(x, cal) if pd.notna(x) else pd.NaT for x in ev],
                          index=df.index)
        held = pd.to_datetime(df.get("available_time"), utc=True, errors="coerce")
        # A LATER DAY from the collector wins; same day -> the exact 15:30 New York instant.
        later_day = held.notna() & (held.dt.normalize() > exact.dt.normalize())
        df["available_time"] = exact.where(~later_day, held)
        df["event_time"] = ev
        return df.dropna(subset=["available_time"]).sort_values("event_time").reset_index(
            drop=True), f"futures_state:cot_{market}"
    slug = next((k for k, v in TFF_SLUGS.items() if v == market), None)
    q = (tff_dir or COT_TFF) / f"{slug}.parquet" if slug else None
    if q is None or not q.exists():
        return None, f"no cot_{market} series (futures_state) and no fetch_tff parquet"
    try:
        raw = pd.read_parquet(q)
    except Exception as exc:
        return None, f"{q.name} unreadable ({type(exc).__name__})"
    return tff_fallback(raw, market, cal, registry), f"fetch_tff:{q.name} (exact names)"


def tff_fallback(raw: pd.DataFrame, market: str, calendar: Mapping[str, Any] | None,
                 registry: Mapping[str, Any] | None = None) -> pd.DataFrame | None:
    """`fetch_tff.py` rows -> the futures_state column shape, keeping ONLY the exact market
    names of futures_state's rename chain (never the cross-rates a substring caught)."""
    reg = registry if registry is not None else (_read(FS_REGISTRY, {}) or {})
    m = next((x for x in reg.get("cftc_markets") or [] if x.get("id") == market), None)
    if m is None or "market" not in raw.columns:
        return None
    names = {str(n).upper() for n in m.get("names") or []}
    df = raw[raw["market"].astype(str).str.upper().isin(names)].copy()
    if df.empty or "oi" not in df.columns:
        return None
    sign = float(m.get("sign", 1))
    oi = pd.to_numeric(df["oi"], errors="coerce").replace(0, np.nan)
    out = pd.DataFrame({"event_time": pd.to_datetime(df["report_date"], utc=True)})
    for stem, name in (("lm", "tff_lev_money"), ("am", "tff_asset_mgr"),
                       ("dealer", "tff_dealer")):
        lc, sc = f"{stem}_l", f"{stem}_s"
        if lc in df.columns and sc in df.columns:
            net = pd.to_numeric(df[lc], errors="coerce") - pd.to_numeric(df[sc], errors="coerce")
            out[f"{name}_net_oi"] = (net / oi * sign).to_numpy()
    out["available_time"] = [cot_usable_from(x, calendar) for x in out["event_time"]]
    return out.sort_values("event_time").drop_duplicates("event_time").reset_index(drop=True)


# ============================================================================ 2. GLD (parser)

def _num(v: Any) -> float | None:
    try:
        x = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def parse_gld_archive(text: str) -> pd.DataFrame:
    """SPDR's GLD archive CSV -> `date`, `tonnes`, `ounces` (one row per dated day).

    Schema-robust on purpose: the archive has carried preamble lines, `HOLIDAY` rows and both
    `18-Nov-2004` and `11/18/2004` dates. The header row is the first that names a date column
    and a tonnes or ounces column; a row whose holdings do not parse is dropped, never zeroed.
    """
    lines = [ln for ln in str(text or "").splitlines() if ln.strip()]
    hdr_i = next((i for i, ln in enumerate(lines)
                  if "date" in ln.lower() and ("tonnes" in ln.lower() or "ounces" in ln.lower())),
                 None)
    if hdr_i is None:
        return pd.DataFrame(columns=["date", "tonnes", "ounces"])
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr_i:])), dtype=str, skipinitialspace=True)
    cols = {c: str(c).strip().lower() for c in df.columns}
    date_c = next((c for c, n in cols.items() if n.startswith("date")), None)
    ton_c = next((c for c, n in cols.items() if "tonnes" in n), None)
    oz_c = next((c for c, n in cols.items() if "ounces" in n), None)
    if date_c is None or (ton_c is None and oz_c is None):
        return pd.DataFrame(columns=["date", "tonnes", "ounces"])
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        raw_d = str(r.get(date_c) or "").strip()
        d = None
        for fmt in ("%d-%b-%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%y", "%d/%m/%Y"):
            try:
                d = datetime.strptime(raw_d, fmt).replace(tzinfo=UTC).date()
                break
            except ValueError:
                continue
        if d is None:
            continue
        t = _num(r.get(ton_c)) if ton_c else None
        oz = _num(r.get(oz_c)) if oz_c else None
        if t is None and oz is not None:
            t = oz / TROY_OZ_PER_TONNE
        if oz is None and t is not None:
            oz = t * TROY_OZ_PER_TONNE
        if t is None or t <= 0:
            continue
        rows.append({"date": pd.Timestamp(d), "tonnes": float(t), "ounces": float(oz or 0.0)})
    if not rows:
        return pd.DataFrame(columns=["date", "tonnes", "ounces"])
    return (pd.DataFrame(rows).sort_values("date").drop_duplicates("date", keep="last")
            .reset_index(drop=True))


FLOW_PX_WINDOW = 5
FLOW_PX_BETA_ROWS = 250


def signed_streak(flow: pd.Series) -> pd.Series:
    """Consecutive same-sign days, signed: +3 is a third creation day running, -2 a second
    redemption day. A no-change day is 0 and resets the run; an unknown (NaN) day is NaN and
    resets it too, so a gap never extends a streak it cannot see."""
    out = np.full(len(flow), np.nan)
    run = 0
    for i, v in enumerate(pd.to_numeric(flow, errors="coerce").to_numpy(dtype=float)):
        if not math.isfinite(v):
            run = 0
            continue
        sgn = 1 if v > 0 else -1 if v < 0 else 0
        run = 0 if sgn == 0 else (run + sgn if run * sgn > 0 else sgn)
        out[i] = float(run)
    return pd.Series(out, index=flow.index)


def known_close(available: pd.Series, xau: pd.DataFrame | None,
                day: pd.Series | None = None) -> pd.Series:
    """For each GLD row, the XAUUSD daily close of its own day -- or the newest before it --
    that was PUBLIC by the row's stamp: the newest close whose broker day is at or before
    `day` (when given) AND whose own `available_time` is at or before `available`. Both
    constraints bind: without the day one, a Friday row stamped on the Tuesday after a holiday
    Monday would compare Friday's flow with Monday's price. NaN where no close qualifies."""
    if xau is None or xau.empty or "close" not in xau.columns:
        return pd.Series(np.nan, index=available.index)
    r = pd.DataFrame({
        "_a": pd.to_datetime(xau["available_time"], utc=True).astype(
            "datetime64[ns, UTC]").to_numpy(),
        "_d": pd.to_datetime(xau.index, utc=True).normalize().astype(
            "datetime64[ns, UTC]").to_numpy(),
        "close": pd.to_numeric(xau["close"], errors="coerce").to_numpy()}
    ).dropna().sort_values("_d").reset_index(drop=True)
    if r.empty:
        return pd.Series(np.nan, index=available.index)
    a = pd.to_datetime(available, utc=True).astype("datetime64[ns, UTC]").to_numpy()
    # publication is monotone in the broker day, so "newest satisfying both" is the smaller of
    # the two backward positions
    pos = np.searchsorted(np.maximum.accumulate(r["_a"].to_numpy()), a, side="right") - 1
    if day is not None:
        d = pd.to_datetime(day, utc=True).dt.normalize().astype(
            "datetime64[ns, UTC]").to_numpy()
        pos = np.minimum(pos, np.searchsorted(r["_d"].to_numpy(), d, side="right") - 1)
    vals = r["close"].to_numpy(dtype=float)
    return pd.Series(np.where(pos >= 0, vals[np.clip(pos, 0, None)], np.nan),
                     index=available.index)


def flow_price_residual(flow: pd.Series, ret: pd.Series,
                        rows: int = FLOW_PX_BETA_ROWS) -> pd.Series:
    """`flow` minus its rolling OLS fit on `ret` (past and current rows only)."""
    mp = max(30, rows // 4)
    both = pd.concat([flow, ret], axis=1, keys=["f", "r"]).dropna()
    mf = both["f"].rolling(rows, min_periods=mp).mean()
    mr = both["r"].rolling(rows, min_periods=mp).mean()
    cov = both["f"].rolling(rows, min_periods=mp).cov(both["r"], ddof=0)
    var = both["r"].rolling(rows, min_periods=mp).var(ddof=0)
    beta = (cov / var.replace(0.0, np.nan)).fillna(0.0).where(mf.notna())
    resid = both["f"] - (mf - beta * mr) - beta * both["r"]
    return resid.replace([np.inf, -np.inf], np.nan).reindex(flow.index)


def gold_etf_features(h: pd.DataFrame, xau: pd.DataFrame | None = None) -> pd.DataFrame:
    """Holdings -> flows in tonnes, stamped at their next-business-day availability; with
    XAUUSD daily closes (`daily_closes`), the flow's residual on the same-window return."""
    if h.empty:
        return pd.DataFrame()
    t = h["tonnes"].astype(float).reset_index(drop=True)
    out = pd.DataFrame({"event_time": pd.to_datetime(h["date"].to_numpy(), utc=True)})
    out["tonnes"] = t.to_numpy()
    out["flow_1d_t"] = t.diff().to_numpy()
    out["flow_5d_t"] = t.diff(5).to_numpy()
    out["flow_20d_t"] = t.diff(20).to_numpy()
    out["flow_z"] = zscore(t.diff(), 250).to_numpy()
    out["available_time"] = [gld_available(x) for x in h["date"]]
    out["flow_streak"] = signed_streak(t.diff()).to_numpy()
    if xau is not None and not xau.empty:
        px = known_close(out["available_time"], xau, out["event_time"])
        ret = pd.Series(np.log(px.to_numpy()), index=out.index).diff(FLOW_PX_WINDOW)
        out["xau_ret_5d"] = ret.to_numpy()
        f5 = out["flow_5d_t"].astype(float)
        out["flow_px_resid"] = flow_price_residual(f5, ret).to_numpy()
        sf, sr = np.sign(f5), np.sign(ret)
        out["flow_px_disagree"] = np.where(sf.notna() & sr.notna(),
                                           np.where(sf * sr < 0, sf, 0.0), np.nan)
    return out


# ============================================================================ 3. rebalance (pure)

def _ny_bdays_left_in_month(day: pd.Timestamp) -> int:
    """NY business days strictly after `day` and inside its month."""
    hol = _holidays()
    d = _naive_day(day)
    end = (d + pd.offsets.MonthEnd(0)).normalize()
    n = 0
    x = d + pd.Timedelta(days=1)
    while x <= end:
        if x.weekday() < 5 and x not in hol:
            n += 1
        x += pd.Timedelta(days=1)
    return n


def rebalance_pressure(lead: pd.Series, lag: pd.Series, *,
                       window_bdays: int = REBAL_WINDOW_BDAYS) -> pd.Series:
    """Signed month-/quarter-end rebalance flow on `lead` from its run against `lag`.

    `lead` and `lag` are daily closes on one broker-day index. On day t the period-to-date
    log return of each runs from the last close of the previous period (quarter in the last
    month of a quarter, month otherwise). The pressure is -(lead - lag): a sleeve that outran
    the other is sold into the period end. It is non-zero only when at most `window_bdays` NY
    business days of the month remain (counting today), and half weight outside quarter-ends.
    """
    both = pd.concat([lead.rename("a"), lag.rename("b")], axis=1).dropna()
    both = both[(both["a"] > 0) & (both["b"] > 0)]
    if both.empty:
        return pd.Series(dtype=float)
    la, lb = np.log(both["a"]), np.log(both["b"])
    idx = pd.DatetimeIndex(both.index)
    naive = idx.tz_localize(None) if idx.tz is not None else idx
    month = pd.Series(naive.to_period("M"), index=both.index)
    quarter = pd.Series(naive.to_period("Q"), index=both.index)
    # the last close BEFORE each period: shift(1) of the period's grouped first-day close
    prev_a, prev_b = la.shift(1), lb.shift(1)
    m_base_a = prev_a.groupby(month.to_numpy()).transform("first")
    m_base_b = prev_b.groupby(month.to_numpy()).transform("first")
    q_base_a = prev_a.groupby(quarter.to_numpy()).transform("first")
    q_base_b = prev_b.groupby(quarter.to_numpy()).transform("first")
    is_q_end = pd.Series(naive.month % 3 == 0, index=both.index)
    rel_m = (la - m_base_a) - (lb - m_base_b)
    rel_q = (la - q_base_a) - (lb - q_base_b)
    rel = rel_q.where(is_q_end, rel_m)
    weight = is_q_end.map({True: 1.0, False: 0.5})
    left = pd.Series([_ny_bdays_left_in_month(x) + 1 for x in naive], index=both.index)
    inside = left <= int(window_bdays)
    return (-rel * weight).where(inside, 0.0).where(rel.notna())


# ============================================================================ build

def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    _replace(tmp, p)


def _replace(tmp: Path, p: Path) -> None:
    """os.replace with the Windows fallback (a destination another process holds open)."""
    try:
        os.replace(tmp, p)
    except PermissionError:
        p.unlink(missing_ok=True)
        os.replace(tmp, p)


def write_series(sid: str, frame: pd.DataFrame, series_dir: Path | None = None) -> Path:
    """Parquet when pyarrow is importable (the box), CSV otherwise; the other format's stale
    file is removed so `family_exogenous_conditioner.series_path` can never read old data."""
    base = series_dir or SERIES
    base.mkdir(parents=True, exist_ok=True)
    f = frame.copy()
    f["available_time"] = pd.to_datetime(f["available_time"], utc=True).astype(str)
    if "event_time" in f.columns:
        f["event_time"] = pd.to_datetime(f["event_time"], utc=True).astype(str)
    f["source_id"] = sid
    try:
        import pyarrow  # noqa: F401
        p, other = base / f"{sid}.parquet", base / f"{sid}.csv"
        tmp = p.with_suffix(".parquet.tmp")
        f.to_parquet(tmp, index=False)
    except ImportError:
        p, other = base / f"{sid}.csv", base / f"{sid}.parquet"
        tmp = p.with_suffix(".csv.tmp")
        f.to_csv(tmp, index=False)
    _replace(tmp, p)
    if other.exists():
        other.unlink(missing_ok=True)
    return p


def _hyp(symbol: str, sid: str, signal: str, threshold: float, side: int, *, producer: str,
         mechanism: str, falsifier: str, extends: Sequence[str] = ()) -> dict[str, Any]:
    params = {"source": sid, "signal": signal, "transform": "level_z",
              "threshold": float(threshold), "side_when_high": int(side),
              "lag_hours": LAG_HOURS}
    return {"symbol": symbol, "family": FAMILY, "params": params, "producer": producer,
            "mechanism": mechanism, "falsifier": falsifier, "extends": list(extends),
            "title": f"{producer}: {symbol} {signal} level_z {'>=' if side > 0 else 'fade'} "
                     f"{threshold:g}"}


def cta_producer(bars: Callable[[str], pd.DataFrame | None], calendar: Mapping[str, Any],
                 *, series_dir: Path | None = None, tff_dir: Path | None = None,
                 registry: Mapping[str, Any] | None = None
                 ) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], dict[str, Any]]:
    frames: dict[str, pd.DataFrame] = {}
    hyps: list[dict[str, Any]] = []
    report: dict[str, Any] = {}
    for sym, market in CTA_TARGETS.items():
        dc = daily_closes(bars(sym))
        if len(dc) < max(HORIZONS) + MIN_SERIES_ROWS:
            report[sym] = {"status": "UNMEASURED", "why": f"{len(dc)} daily closes on this box"}
            continue
        feat = cta_replication(dc["close"], high=dc.get("high"), low=dc.get("low"))
        feat["available_time"] = dc["available_time"].to_numpy()
        feat["event_time"] = pd.DatetimeIndex(dc.index).to_numpy()
        feat = feat.dropna(subset=["cta_pos"])
        row: dict[str, Any] = {"status": "OK", "rows": len(feat), "cot": None}
        if market:
            cot, why = cot_series(market, calendar, series_dir, tff_dir, registry)
            lev = next((c for c in LEV_COLUMNS if cot is not None and c in cot.columns
                        and pd.to_numeric(cot[c], errors="coerce").notna().sum()
                        >= MIN_SERIES_ROWS), None)
            row["cot"] = why if lev is None else f"{why}:{lev}"
            if cot is not None and lev is not None:
                w = cot[["available_time", lev]].copy()
                w["lev_z"] = zscore(pd.to_numeric(w[lev], errors="coerce"), Z_WEEKS)
                joined = asof_join(feat.reset_index(drop=True), w, ["lev_z"])
                joined["cta_z"] = zscore(joined["cta_notional"], 250)
                joined["crowd_z"] = 0.5 * (joined["cta_z"] + joined["lev_z"])
                feat = joined
        sid = f"pf_cta_{sym}"
        frames[sid] = feat.reset_index(drop=True)
        mech = ("a trend-following book replicating SG-CTA horizons must trade its signal "
                "changes; the replicated flow is public arithmetic on public prices")
        hyps.append(_hyp(sym, sid, "cta_flow_1d", 1.5, +1, producer="cta", mechanism=mech,
                         falsifier=f"{sym} shows no continuation after an extreme replicated "
                                   "CTA flow day out of sample"))
        hyps.append(_hyp(sym, sid, "cta_notional", 1.5, -1, producer="cta", mechanism=(
            "a maximally positioned trend book has no buyers left inside it; extremes unwind"),
            falsifier=f"{sym} does not mean-revert from extreme replicated CTA length"))
        hyps.append(_hyp(sym, sid, "flip_asym", 1.0, +1, producer="cta", mechanism=(
            "when the levels that flip the trend signals sit closer above than below, a rally "
            "forces more systematic buying than a decline forces selling (convex flow)"),
            falsifier=f"{sym}'s next move is unrelated to the replicated flip asymmetry"))
        hyps.append(_hyp(sym, sid, "pending_flow", 1.5, +1, producer="cta", mechanism=(
            "the estimated systematic flow waiting at the nearest signal-flip levels, weighted "
            "by how few ATRs away they sit, is convex: a move toward a large trigger is "
            "accelerated by the book that must trade through it"),
            falsifier=f"{sym}'s next move is unrelated to the proximity-weighted estimated "
                      "CTA flip flow"))
        if "crowd_z" in feat.columns:
            hyps.append(_hyp(sym, sid, "crowd_z", 1.5, -1, producer="cta", mechanism=(
                "replicated CTA length confirmed by CFTC leveraged-money positioning is a "
                "crowded systematic trade that unwinds"),
                falsifier=f"{sym} does not fade when the CTA model and CFTC leveraged money "
                          "are jointly extreme"))
        report[sym] = row
    return frames, hyps, report


def gold_etf_producer(text: str | None, xau_h1: pd.DataFrame | None = None
                      ) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], dict[str, Any]]:
    if not text:
        return {}, [], {"status": "UNMEASURED", "why": "no GLD archive held on this box yet"}
    h = parse_gld_archive(text)
    if len(h) < MIN_SERIES_ROWS:
        return {}, [], {"status": "UNMEASURED", "why": f"{len(h)} parsable GLD rows"}
    xau = daily_closes(xau_h1)
    feat = gold_etf_features(h, xau)
    sid = "pf_gold_etf"
    ext = ("GOLD_ETF_creation_redemption_flow", "GLD_IAU_Gold_ETF_Rebalance")
    mech = ("authorised participants create GLD shares by delivering physical gold: a "
            "sustained creation flow is measured physical demand that the spot price follows")
    hyps = [_hyp("XAUUSD", sid, col, thr, +1, producer="gold_etf", mechanism=mech, extends=ext,
                 falsifier=f"XAUUSD shows no continuation after an extreme GLD {col} out of "
                           "sample")
            for col, thr in (("flow_z", 2.0), ("flow_5d_t", 1.5), ("flow_20d_t", 1.5))]
    # Two more cells, defined whether or not their inputs are here yet: one whose column is
    # absent or short (no XAUUSD bars on this box) is HELD by plan_donation, never charged.
    hyps.append(_hyp("XAUUSD", sid, "flow_px_resid", 1.5, +1, producer="gold_etf", mechanism=(
        "GLD creations the gold price has not yet answered over the same five days are "
        "physical demand still to be priced: the residual of the flow on the return leads "
        "the return"), extends=ext,
        falsifier="XAUUSD shows no continuation after an extreme GLD flow residual on its own "
                  "same-window return out of sample"))
    hyps.append(_hyp("XAUUSD", sid, "flow_streak", 1.5, +1, producer="gold_etf", mechanism=(
        "an unbroken run of creation (redemption) days is a persistent allocator buying "
        "(selling) through authorised participants, not one block: persistence continues"),
        extends=ext,
        falsifier="XAUUSD shows no continuation after an extreme signed GLD creation/"
                  "redemption streak out of sample"))
    return {sid: feat}, hyps, {"status": "OK", "rows": len(feat),
                               "first": str(h["date"].min().date()),
                               "last": str(h["date"].max().date()),
                               "latest_tonnes": round(float(h["tonnes"].iloc[-1]), 2),
                               "xauusd_closes": len(xau),
                               "divergence": ("OK" if "flow_px_resid" in feat.columns else
                                              "UNMEASURED: no XAUUSD daily closes on this box"),
                               "iau": ("NOT_FETCHED: iShares publishes a current holdings "
                                       "snapshot, not a public history")}


def realmoney_producer(bars: Callable[[str], pd.DataFrame | None], calendar: Mapping[str, Any],
                       *, series_dir: Path | None = None, tff_dir: Path | None = None,
                       registry: Mapping[str, Any] | None = None
                       ) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], dict[str, Any]]:
    frames: dict[str, pd.DataFrame] = {}
    hyps: list[dict[str, Any]] = []
    report: dict[str, Any] = {}
    closes: dict[str, pd.DataFrame] = {}

    def dc(sym: str) -> pd.DataFrame:
        if sym not in closes:
            closes[sym] = daily_closes(bars(sym))
        return closes[sym]

    targets = sorted(set(REALMONEY_TFF) | set(REBAL_INDEX) | set(REBAL_FX))
    for sym in targets:
        parts: list[pd.DataFrame] = []
        row: dict[str, Any] = {}
        market = REALMONEY_TFF.get(sym)
        if market:
            cot, why = cot_series(market, calendar, series_dir, tff_dir, registry)
            lev = next((c for c in LEV_COLUMNS if cot is not None and c in cot.columns), None)
            if cot is not None and lev and AM_COLUMN in cot.columns:
                w = cot[["event_time", "available_time"]].copy()
                w["am_net_oi"] = pd.to_numeric(cot[AM_COLUMN], errors="coerce")
                w["am_vs_lev"] = (zscore(w["am_net_oi"], Z_WEEKS)
                                  - zscore(pd.to_numeric(cot[lev], errors="coerce"), Z_WEEKS))
                w = w.dropna(subset=["am_vs_lev"])
                if len(w) >= MIN_SERIES_ROWS:
                    parts.append(w)
                row["am"] = f"{why}:{AM_COLUMN}"
            else:
                row["am"] = f"UNMEASURED: {why}" if cot is None else (
                    f"UNMEASURED: {why} carries no {AM_COLUMN}")
        lead_lag: tuple[str, str, int] | None = None
        if sym in REBAL_INDEX:
            lead_lag = (sym, BOND, +1)
        elif sym in REBAL_FX:
            home, sgn = REBAL_FX[sym]
            lead_lag = (US_EQUITY, home, sgn)
        if lead_lag:
            a, b, sgn = lead_lag
            da, db = dc(a), dc(b)
            if len(da) >= MIN_SERIES_ROWS and len(db) >= MIN_SERIES_ROWS:
                rp = rebalance_pressure(da["close"], db["close"])
                if sym in REBAL_FX:
                    # FX: -(US - home) is the flow on the dollar's other side; a USD-quote
                    # symbol (EURUSD) is bought, a USD-base symbol (USDJPY) is sold.
                    rp = -rp * sgn
                av = pd.concat([da["available_time"], db["available_time"]], axis=1).max(axis=1)
                r = pd.DataFrame({"event_time": pd.DatetimeIndex(rp.index).to_numpy(),
                                  "rebal_pressure": rp.to_numpy(),
                                  "available_time": pd.to_datetime(
                                      av.reindex(rp.index), utc=True).to_numpy()}).dropna()
                if len(r) >= MIN_SERIES_ROWS:
                    parts.append(r)
                row["rebalance"] = f"{a} vs {b}: {len(r)} rows"
            else:
                row["rebalance"] = (f"UNMEASURED: {a} {len(da)} / {b} {len(db)} daily closes "
                                    "on this box")
        if not parts:
            report[sym] = {"status": "UNMEASURED", **row}
            continue
        merged = pd.concat(parts, ignore_index=True, sort=False)
        merged["available_time"] = pd.to_datetime(merged["available_time"], utc=True)
        merged = merged.sort_values("available_time").reset_index(drop=True)
        sid = f"pf_realmoney_{sym}"
        frames[sid] = merged
        if "am_vs_lev" in merged.columns:
            hyps.append(_hyp(sym, sid, "am_vs_lev", 1.0, +1, producer="real_money", mechanism=(
                "asset managers rebalance slowly against benchmarks; when real money leans "
                "against leveraged money the slow book's direction persists"),
                falsifier=f"{sym} does not follow CFTC asset-manager positioning when it "
                          "diverges from leveraged funds"))
        if "rebal_pressure" in merged.columns:
            hyps.append(_hyp(sym, sid, "rebal_pressure", 1.0, +1, producer="real_money",
                             mechanism=(
                "balanced mandates restore fixed weights at month- and quarter-end, selling "
                "the sleeve that outran the other into the period's last days"),
                falsifier=f"{sym} shows no period-end move in the direction of the estimated "
                          "rebalance flow"))
        report[sym] = {"status": "OK", "rows": len(merged), **row}
    return frames, hyps, report


def fetch_gld(state: dict[str, Any], now: datetime, *, offline: bool,
              get: Callable[..., Any] | None = None) -> tuple[str | None, str]:
    """The held archive, refreshed at most once per GLD_REFETCH_H through polite_fetch."""
    held = GLD_RAW.read_text(encoding="utf-8") if GLD_RAW.exists() else None
    if offline:
        return held, "offline: held archive only"
    if "gld" in (state.get("hard_stops") or {}):
        return held, f"HARD_STOP {state['hard_stops']['gld']}"
    last = state.get("gld_fetched_utc")
    if held and last:
        try:
            if now - datetime.fromisoformat(str(last)) < timedelta(hours=GLD_REFETCH_H):
                return held, "held (fetched within the refetch window)"
        except ValueError:
            pass
    if get is None:
        from libs.data import polite_fetch
        get = polite_fetch.get
    r = get(GLD_URL, headers={"User-Agent": UA, "Accept": "text/csv,*/*"}, timeout=40.0,
            retries=0, leg=SEAT)
    status = getattr(r, "status", None)
    if status in HARD_STOP:
        state.setdefault("hard_stops", {})["gld"] = {"code": status, "at": now.isoformat()}
        return held, f"HARD_STOP {status}"
    if not getattr(r, "ok", False):
        return held, f"fetch failed: {getattr(r, 'error', '') or status}"
    text = str(getattr(r, "text", "") or "")
    if len(parse_gld_archive(text)) < MIN_SERIES_ROWS:
        return held, "fetched a body with no parsable GLD rows; held archive kept"
    GLD_RAW.parent.mkdir(parents=True, exist_ok=True)
    tmp = GLD_RAW.with_suffix(".csv.tmp")
    tmp.write_text(text, encoding="utf-8")
    _replace(tmp, GLD_RAW)
    state["gld_fetched_utc"] = now.isoformat()
    return text, "fetched"


def plan_donation(hyps: Sequence[dict[str, Any]], frames: Mapping[str, pd.DataFrame],
                  charged: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(new hypotheses to donate, held ones). A hypothesis is donated ONCE in its life: an
    identity already charged is skipped, and one whose series column is too short is held
    (not charged) until its data arrives."""
    from research.proposer_common import identity
    new: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    seen: set[str] = set()
    for h in hyps:
        ident = identity(h["symbol"], h["family"], h["params"])
        if ident in charged or ident in seen:
            continue
        f = frames.get(h["params"]["source"])
        col = h["params"]["signal"]
        n = int(pd.to_numeric(f[col], errors="coerce").notna().sum()) if (
            f is not None and col in f.columns) else 0
        if n < MIN_SERIES_ROWS:
            held.append({"symbol": h["symbol"], "signal": col, "rows": n})
            continue
        seen.add(ident)
        new.append({**h, "identity": ident})
    return new, held


def donate(new: Sequence[dict[str, Any]], state: dict[str, Any], now: datetime,
           donate_fn: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Donate this pass's NEW hypotheses; `tests_run` is their count, charged exactly once."""
    if not new:
        return {"donated": 0, "tests_run": 0, "path": None}
    from research import proposer_common as PC
    rows = []
    for h in new:
        c = PC.candidate(SEAT, h["symbol"], h["family"], dict(h["params"]), h["mechanism"],
                         h["title"], {"producer": h["producer"], "lag_hours": LAG_HOURS,
                                      "series": f"data/lake/series/{h['params']['source']}"})
        c.update({"falsifier": h["falsifier"], "extends": h["extends"],
                  "identity": h["identity"], "horizon": "H1",
                  "required_data": [f"desks/mt5/data/lake/series/{h['params']['source']}"]})
        rows.append(c)
    fn = donate_fn or PC.donate
    path = fn(SEAT, rows, tests_run=len(rows))
    if path is None:
        return {"donated": 0, "tests_run": 0, "path": None,
                "why": "the donation door wrote nothing", **PC.donation_counts()}
    charged = state.setdefault("charged", {})
    for h in new:
        charged[h["identity"]] = now.isoformat(timespec="seconds")
    return {"donated": len(rows), "tests_run": len(rows), "path": str(path)}


def build(*, dry_run: bool = False, offline: bool = False,
          bars: Callable[[str], pd.DataFrame | None] | None = None,
          priority: Mapping[str, Any] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(UTC)
    state = _read(STATE, {}) or {}
    calendar = _calendar()
    if bars is None:
        try:
            from research.proposer_common import bars as _pc_bars
            bars = _pc_bars
        except Exception:
            def bars(sym: str) -> pd.DataFrame | None:
                return None
    frames: dict[str, pd.DataFrame] = {}
    hyps: list[dict[str, Any]] = []
    producers: dict[str, Any] = {}
    f, h, r = cta_producer(bars, calendar)
    frames.update(f)
    hyps.extend(h)
    producers["cta"] = {"symbols": r, "hypotheses": len(h)}
    text, how = fetch_gld(state, now, offline=offline or dry_run)
    f, h, r = gold_etf_producer(text, bars("XAUUSD"))
    frames.update(f)
    hyps.extend(h)
    producers["gold_etf"] = {**r, "fetch": how, "source": GLD_URL, "hypotheses": len(h)}
    f, h, r = realmoney_producer(bars, calendar)
    frames.update(f)
    hyps.extend(h)
    producers["real_money"] = {"symbols": r, "hypotheses": len(h)}
    new, held = plan_donation(hyps, frames, state.get("charged") or {})
    if not dry_run:
        for sid, frame in frames.items():
            write_series(sid, frame)
        donation = donate(new, state, now)
    else:
        donation = {"donated": 0, "tests_run": 0, "would_donate": len(new)}
    doc = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "rule": ("Every hypothesis is donated once in its life and charged once (tests_run = "
                 "new identities this pass). COT rows are usable from 15:30 New York on their "
                 "release day; every cell holds its series back lag_hours=3 so the bar clock "
                 "(New York + 7 h) can never see a value before it was public."),
        "producers": producers,
        "series": {sid: {"rows": len(fr), "columns": [c for c in fr.columns if c not in (
            "available_time", "event_time", "source_id")]} for sid, fr in frames.items()},
        "hypotheses_defined": len(hyps),
        "hypotheses_charged_total": len(state.get("charged") or {}),
        "new_this_pass": len(new),
        "held_for_data": held,
        "donation": donation,
        "hard_stops": state.get("hard_stops", {}),
        "priority": dict(priority or {"applied": False, "how": "not requested (library call)"}),
        "seconds": round(time.monotonic() - t0, 1),
    }
    if not dry_run:
        _write(STATE, state)
        _write(OUT, doc)
    return doc


def below_normal() -> dict[str, Any]:
    """RELEASE AND RISK WIN THE CPU. Lower this leg's own priority before any work (BELOW_NORMAL
    on Windows, nice 10 elsewhere) -- the same self-demotion `judge_prescreen._below_normal`
    uses, and the class `department_resident` gives its children -- and SAY whether it took.
    No new process and no resident: one hourly subprocess that yields to everything else."""
    try:
        import psutil

        me = psutil.Process()
        want = psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10
        if os.name != "nt" and me.nice() >= want:
            return {"applied": True, "observed": str(me.nice()), "how": "already lower"}
        me.nice(want)
        got = me.nice()
        return {"applied": bool(got == want), "requested": str(want), "observed": str(got),
                "how": "psutil"}
    except Exception as exc:
        return {"applied": False, "how": "none", "why": type(exc).__name__}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "player footprint").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--release-hard-stops", action="store_true",
                    help="clear recorded 401/403/429/451 hard stops (a human decision)")
    a = ap.parse_args(argv)
    prio = below_normal()
    if a.release_hard_stops:
        st = _read(STATE, {}) or {}
        st.pop("hard_stops", None)
        _write(STATE, st)
    doc = build(dry_run=a.dry_run, offline=a.offline, priority=prio)
    p = doc["producers"]
    print(f"player footprint: {len(doc['series'])} series, {doc['hypotheses_defined']} "
          f"hypotheses defined, {doc['new_this_pass']} new this pass, "
          f"{doc['hypotheses_charged_total']} charged in total, "
          f"{len(doc['held_for_data'])} held for data; cta {p['cta']['hypotheses']}, "
          f"gold_etf {p['gold_etf']['hypotheses']} ({p['gold_etf']['status']}: "
          f"{p['gold_etf'].get('fetch')}), real_money {p['real_money']['hypotheses']}; "
          f"{doc['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
