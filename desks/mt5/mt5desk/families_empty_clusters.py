"""FAMILIES FOR THE SIX EMPTY ALPHA CLUSTERS, each one buildable by the SEALED gauntlet.

WHY THIS FILE (principal's standing order, 2026-09-30): k_eff read 2.53 on 453 nominal sleeves and
six of fifteen declared clusters held nothing -- cross_asset_lead_lag, event_surprise,
execution_entry, news_reaction, options_implied, positioning_flow. Measured on LIVE's own code
and the committed docket (`external_survivors.json`, 2026-09-24), they were empty for ONE reason
wearing three names:

    cross_asset_lead_lag   1,062 `lead_lag` cells, 611 seen by the gauntlet, ZERO with a measured
                           n. `external_gauntlet.build_cell` has no `lead_lag` branch, so every
                           cell was built with driver=None and returned [] -- judged as though
                           the market had said no.
    event_surprise         97 `event_reaction` cells, 210 seen, ZERO with a measured n. The branch
                           exists and hands the family a bare DatetimeIndex, which it skips.
    positioning_flow       18 `cot_positioning` cells. The four `cot_*` families in `families`
                           take a POSITIONAL `cot` frame no branch supplies (TypeError -> build
                           failure), and none of them was even classified into the cluster.
    execution_entry,       NO family classified into them at all. `execution_state` (the one
    news_reaction,         execution family) needs a `surface` no branch loads.
    options_implied

The gauntlet is sealed (IMMUTABLE_MANIFEST) and is not edited. Every family here therefore takes
its external input BY NAME and LOADS IT ITSELF -- the contract `families_cross_sectional` and the
specialist families keep -- so a cell is just (symbol, family, params) and the gauntlet builds it
through its ordinary `fn(h1, side=1, **params)` call. `symbol` is a REQUIRED keyword: a cell that
does not carry it fails to build (a named failure), it never silently returns [].

THE FAMILIES, BY CLUSTER, WITH THE PAYER EACH ONE NAMES (priors written before any data was read):

  options_implied   (CBOE implied-vol indices: VIX, and OVX/GVZ/EVZ/VIX3M when fetched)
    implied_vol_risk_premium    Implied minus the instrument's own realised volatility, z-scored
        on its own trailing history. A rich premium is what option sellers are paid to warehouse
        crash risk; the underlying's risk-on drift is that premium's other face (Bollerslev,
        Tauchen & Zhou 2009). `harvest` holds the risk-on side while it is rich; `stress` holds
        the risk-off side while realised exceeds implied. Payer: the insurance buyer.
    implied_vol_shock_fade      A one-day jump in the implied index against its own trailing
        dispersion. Dealers short gamma hedge INTO the move and over-shoot; the underlying's
        risk-on side recovers as the hedges come off (`fade`), or keeps falling while they are
        still being put on (`follow`). Payer: the short-gamma dealer.
    implied_vol_term_inversion  The front implied index above the back (VIX > VIX3M): hedging
        demand is concentrated at the front. `unwind` trades risk-on on the day the curve
        returns to contango. Refuses without the back-month series.

  positioning_flow  (CFTC COT, desks/mt5/data/cot/<contract>.parquet, lagged to its release)
    positioning_crowding_unwind Speculative net at a multi-year extreme AND price already moving
        against the crowd over `turn_d` days: the unwind has started and the crowd must keep
        selling into it. Not `cot_positioning`'s unconditional extreme fade. Payer: the crowd.
    positioning_hedging_pressure Commercials' net as a share of open interest at an extreme: the
        futures risk premium is paid by hedgers to whoever takes the other side (de Roon, Nijman
        & Veld 2000). Payer: the hedger.
    positioning_flow_momentum   The WEEK'S change in speculative net, z-scored: speculative flow is
        autocorrelated and price-impacting, so a large inflow continues. A flow claim, not a
        level claim. Payer: the late follower.

  execution_entry   (the bars' own spread and tick volume; OPERATORS over a base cell's entries)
    entry_alpha_limit_pullback  A base family's signals re-entered with a LIMIT `pullback_atr`
        ATRs better, resting `wait_bars`. The base cell entered at market is the control arm and
        is already in the docket. Payer: the impatient taker whose overshoot the limit fills.
    entry_alpha_spread_gate     A base family's signals delayed until the bar's spread is at or
        below its own trailing `spread_q` quantile (dropped after `max_wait` bars). Payer: the
        venue's wide-spread hours, which the market entry paid.
    entry_alpha_open_offset     A base family's signals that land in the first `offset_bars` of a
        session open are moved to the first bar after it. Payer: the opening auction's
        liquidity vacuum.

  news_reaction     (unscheduled: central-bank tone and shocks no calendar announced)
    cb_tone_speech_reaction     A Federal Reserve speech or testimony (the Fed's own calendar,
        2017-, ET times): the TONE is unscheduled even when the appearance is not. The market's
        read of it is the move over `read_bars` from the bar containing the start; the family
        trades `continue` or `fade` of that read. Payer: whoever reprices last.
    news_reaction_unscheduled_shock A shock bar (|move| >= jump_k ATR on above-median tick volume)
        that is NOT within `quiet_h` hours of any scheduled Fed calendar event nor a session open:
        a headline nobody scheduled. `jump` trades every discontinuity; this trades only the
        unscheduled ones, after `read_bars`. Payer: the late repricer.

  event_surprise    (scheduled releases, surprise read by consensus or by the tape)
    event_surprise_impact_drift FOMC statements/minutes, Beige Book and testimony at their
        published times: the surprise is read off the impact bar (sign and size in ATRs) and the
        family trades continuation or reversal of it. Payer: the pre-positioned holder.
    event_surprise_consensus    actual - consensus, z-scored on the release's own history
        (`research/event_surprise.py`'s store): side = `side_on_up` x sign(z) for |z| >= z_min,
        entered on the first bar that opens after the release. Refuses without the store.

  cross_asset_lead_lag  (another instrument's bars, loaded by name: `cond_symbol`)
    cross_asset_lead_lag        The driver's `lag`-bar return, z-scored on its own history; trade
        the target `same` or `opposite`. `lead_lag`'s claim, buildable. Payer: the slow updater.
    lead_lag_session_handoff    The driver's return over ITS session (read at `read_hour`)
        predicts the target over the next one; decided at the target's `decision_hour`. The
        transmission crosses a closed market, which is why it can persist. Payer: the session
        whose participants were asleep.

NO LOOKAHEAD, BY CONSTRUCTION. Bars carry BROKER time (New York + 7h, `libs/regime/session_clock`)
under a UTC tzinfo. An ET wall-clock time is placed on the bar clock by adding exactly 7h. A daily
index close (16:15 ET) is usable from the next broker day's 00:00 (= 17:00 ET). A COT report (as of
Tuesday, released Friday 15:30 ET = 22:30 broker) is usable from Friday 23:00 broker, and reports
in the two shutdown windows whose release was delayed are dropped rather than dated wrongly. A
foreign bar is read as of the decision bar's stamp and is ABSENT when older than `max_stale_h`.
Entries are at the next bar's open (`trigger=None`) except the limit operator's resting order.

HONEST LIMITS. Every family returns [] -- never a price-only fallback -- when its input is absent:
no implied series for the symbol, no COT contract, no calendar, a base family it cannot rebuild.
The producer (`research/empty_cluster_breadth.py`) measures firing before minting, so a cell that
cannot fire is held back with the missing artifact named instead of spending a trial.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, bars_per_day

BASE = Path(__file__).resolve().parent.parent            # desks/mt5
OBSERVABLES = BASE / "data" / "observables"
COT_DIR = BASE / "data" / "cot"
CONSENSUS_STORE = BASE / "data" / "macro" / "consensus_actuals.jsonl"

_NS_PER_H = 3_600_000_000_000
_NS_PER_D = 24 * _NS_PER_H
#: Broker = New York + 7h (libs/regime/session_clock.py). ET wall-clock -> bar clock.
ET_TO_BROKER_H = 7

#: The cluster each family is built to fill. `libs.research.alpha_clusters.FAMILY_CLUSTER`
#: declares the same mapping (a test pins them equal), so `classify_family` places a certificate
#: by its registry key.
TARGETS: dict[str, str] = {
    "implied_vol_risk_premium": "options_implied",
    "implied_vol_shock_fade": "options_implied",
    "implied_vol_term_inversion": "options_implied",
    "positioning_crowding_unwind": "positioning_flow",
    "positioning_hedging_pressure": "positioning_flow",
    "positioning_flow_momentum": "positioning_flow",
    "entry_alpha_limit_pullback": "execution_entry",
    "entry_alpha_spread_gate": "execution_entry",
    "entry_alpha_open_offset": "execution_entry",
    "cb_tone_speech_reaction": "news_reaction",
    "news_reaction_unscheduled_shock": "news_reaction",
    "event_surprise_impact_drift": "event_surprise",
    "event_surprise_consensus": "event_surprise",
    "cross_asset_lead_lag": "cross_asset_lead_lag",
    "lead_lag_session_handoff": "cross_asset_lead_lag",
}

#: What each family reads beyond the cell's own bars -- FAMILY_INPUTS' text and source.
INPUTS: dict[str, tuple[str, str]] = {
    **dict.fromkeys(("implied_vol_risk_premium", "implied_vol_shock_fade",
                     "implied_vol_term_inversion"),
                    ("the CBOE implied-vol index mapped to the symbol (VIX/OVX/GVZ/EVZ/VIX3M), "
                     "daily closes lagged to the next broker day",
                     "desks/mt5/data/observables/cboe_<index>_history.json")),
    **dict.fromkeys(("positioning_crowding_unwind", "positioning_hedging_pressure",
                     "positioning_flow_momentum"),
                    ("the CFTC COT contract mapped to the symbol, lagged to its Friday release",
                     "desks/mt5/data/cot/<contract>.parquet")),
    **dict.fromkeys(("entry_alpha_limit_pullback", "entry_alpha_spread_gate",
                     "entry_alpha_open_offset"),
                    ("a price-only base family rebuilt from the same bars, and the bars' own "
                     "spread column", "the cell's own bars")),
    **dict.fromkeys(("cb_tone_speech_reaction", "news_reaction_unscheduled_shock",
                     "event_surprise_impact_drift"),
                    ("the Federal Reserve's published calendar with ET times",
                     "desks/mt5/data/observables/fomc_calendar.json")),
    "event_surprise_consensus": ("actual/consensus pairs with release times",
                                 "desks/mt5/data/macro/consensus_actuals.jsonl"),
    **dict.fromkeys(("cross_asset_lead_lag", "lead_lag_session_handoff"),
                    ("the driver instrument's H1 bars, named on the cell as cond_symbol",
                     "data/universe/<cond_symbol>_H1.parquet")),
}


# ------------------------------------------------------------------------------ shared tools ---
def _signal(d: pd.DataFrame, p: int, side: int, atr: np.ndarray, *, stop_atr: float, rr: float,
            ttl_bars: int, tag: str) -> Signal | None:
    a = float(atr[p])
    px = float(d["close"].iat[p])
    if side == 0 or not (math.isfinite(a) and a > 0 and math.isfinite(px) and px > 0):
        return None
    dist = float(stop_atr) * a
    return Signal(time=d.index[p], side=int(side), stop=px - side * dist,
                  target=px + side * dist * float(rr), ttl_bars=int(ttl_bars), tag=tag,
                  trigger=None, wait_bars=1)


def _daily_decisions(d: pd.DataFrame, decision_hour: int) -> np.ndarray:
    """Position of the LAST bar stamped at or before `decision_hour` on each weekday date."""
    idx = d.index
    ok = (idx.hour <= int(decision_hour)) & (idx.dayofweek < 5)
    pos = np.flatnonzero(ok)
    if pos.size == 0:
        return pos
    day = idx.normalize().asi8[pos]
    last = np.r_[day[1:] != day[:-1], True]
    return pos[last]


def _one_at_a_time(cands: list[tuple[int, int]], hold: int) -> list[tuple[int, int]]:
    """(position, side) candidates thinned so each is at least `hold` bars after the last kept."""
    out: list[tuple[int, int]] = []
    last = -10 ** 9
    for p, s in sorted(cands):
        if p - last >= hold and s != 0:
            out.append((p, s))
            last = p
    return out


def _stamps(d: pd.DataFrame) -> np.ndarray:
    return d.index.as_unit("ns").asi8


def utc_to_bar_ns(t: Any) -> int:
    """A true UTC instant on the bar clock: New York wall time + 7h (the inverse of
    `libs.regime.session_clock.server_to_utc`), so it follows the US daylight-time dates."""
    ts = pd.Timestamp(t)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    wall = ts.tz_convert("America/New_York").tz_localize(None)
    return int((wall + pd.Timedelta(hours=ET_TO_BROKER_H)).tz_localize("UTC").value)


def _broker_ns(et_date: date, hour: int, minute: int) -> int:
    """An ET wall-clock time on the bar clock (broker = ET + 7h), as int64 ns under UTC."""
    ts = pd.Timestamp(datetime(et_date.year, et_date.month, et_date.day, hour, minute),
                      tz="UTC") + pd.Timedelta(hours=ET_TO_BROKER_H)
    return int(ts.value)


# --------------------------------------------------------------------------- implied series ---
#: symbol -> (implied index, risk orientation). +1: the long side is the risk-on side.
IMPLIED_MAP: dict[str, tuple[str, int]] = {
    **{s: ("vix", 1) for s in ("US500", "US30", "NAS100", "US2000", "GER40", "UK100", "FRA40",
                               "EUSTX50", "JPN225", "AUS200", "HK50", "E35", "NETH25", "CA60",
                               "CHINAH", "AUDJPY", "NZDJPY", "CADJPY", "AUDUSD", "NZDUSD",
                               "USDJPY")},
    **{s: ("vix", -1) for s in ("USDCHF",)},
    **{s: ("gvz", 1) for s in ("XAUUSD", "XAUEUR", "XAUAUD", "XAGUSD")},
    **{s: ("ovx", 1) for s in ("XTIUSD", "XBRUSD")},
    **{s: ("evz", 1) for s in ("EURUSD",)},
}


def implied_file(index: str) -> Path:
    return OBSERVABLES / f"cboe_{index.lower()}_history.json"


@lru_cache(maxsize=16)
def _implied_cached(path: str, mtime_ns: int) -> tuple[np.ndarray, np.ndarray] | None:
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("series") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return None
    days: list[int] = []
    vals: list[float] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            dt = datetime.strptime(str(r.get("date")), "%m/%d/%Y")
            v = float(r.get("close"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            # USABLE FROM THE NEXT BROKER DAY'S 00:00 (= 17:00 ET, after the 16:15 ET close).
            days.append(int(pd.Timestamp(dt, tz="UTC").value) + _NS_PER_D)
            vals.append(v)
    if len(days) < 30:
        return None
    order = np.argsort(np.asarray(days, dtype="int64"), kind="stable")
    return (np.asarray(days, dtype="int64")[order], np.asarray(vals, dtype="float64")[order])


def implied_series(index: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(usable-from stamps ns, closes) for a CBOE index, or None when not fetched here."""
    p = implied_file(index)
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        return None
    return _implied_cached(str(p), mtime)


def _asof(stamps: np.ndarray, series: tuple[np.ndarray, np.ndarray], *,
          max_stale_d: float = 5.0) -> np.ndarray:
    t, v = series
    j = np.searchsorted(t, stamps, side="right") - 1
    out = np.full(stamps.size, np.nan)
    has = j >= 0
    jj = np.where(has, j, 0)
    fresh = has & ((stamps - t[jj]) <= max_stale_d * _NS_PER_D)
    out[fresh] = v[jj[fresh]]
    return out


def _decision_frame(df: pd.DataFrame, decision_hour: int) -> tuple[pd.DataFrame, np.ndarray]:
    d = _h1(df)
    return d, _daily_decisions(d, decision_hour)


def family_implied_vol_risk_premium(
    df: pd.DataFrame, *, symbol: str, mode: str = "harvest", z_thr: float = 1.0,
    rv_days: int = 20, z_days: int = 252, hold_d: int = 5, decision_hour: int = 10,
    atr_n: int = 20, stop_atr: float = 2.5, rr: float = 1.5,
) -> list[Signal]:
    """`harvest`: risk-on side while VRP z >= z_thr. `stress`: risk-off side while VRP z <= -z_thr."""
    spec = IMPLIED_MAP.get(str(symbol))
    if spec is None or mode not in ("harvest", "stress") or float(z_thr) <= 0:
        return []
    series = implied_series(spec[0])
    if series is None:
        return []
    d, pos = _decision_frame(df, decision_hour)
    if pos.size < int(z_days) + int(rv_days) + 5:
        return []
    close = d["close"].to_numpy(dtype=float)[pos]
    lr = np.r_[np.nan, np.diff(np.log(close))]
    rv = pd.Series(lr).rolling(int(rv_days), min_periods=int(rv_days)).std().to_numpy()
    rv = rv * math.sqrt(252.0) * 100.0
    iv = _asof(_stamps(d)[pos], series)
    vrp = pd.Series(iv - rv)
    r = vrp.rolling(int(z_days), min_periods=int(z_days) // 2)
    # the yardstick is yesterday's, so today's premium cannot inflate its own normaliser
    z = ((vrp - r.mean().shift(1)) / r.std().shift(1)).to_numpy()
    risk = spec[1]
    want = z >= float(z_thr) if mode == "harvest" else z <= -float(z_thr)
    side = risk if mode == "harvest" else -risk
    hold = int(hold_d) * bars_per_day(d)
    atr = _atr(d, int(atr_n)).to_numpy()
    out: list[Signal] = []
    for p, s in _one_at_a_time([(int(pos[k]), side) for k in np.flatnonzero(want)], hold):
        sig = _signal(d, p, s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=hold,
                      tag=f"implied_vol_risk_premium:{spec[0]}:{mode}")
        if sig is not None:
            out.append(sig)
    return out


def family_implied_vol_shock_fade(
    df: pd.DataFrame, *, symbol: str, mode: str = "fade", z_thr: float = 2.0,
    sd_days: int = 60, hold_d: int = 2, decision_hour: int = 10,
    atr_n: int = 20, stop_atr: float = 2.5, rr: float = 1.5,
) -> list[Signal]:
    """A one-day implied jump: `fade` trades the risk-on side, `follow` the risk-off side."""
    spec = IMPLIED_MAP.get(str(symbol))
    if spec is None or mode not in ("fade", "follow") or float(z_thr) <= 0:
        return []
    series = implied_series(spec[0])
    if series is None:
        return []
    d, pos = _decision_frame(df, decision_hour)
    if pos.size < int(sd_days) + 5:
        return []
    iv = pd.Series(_asof(_stamps(d)[pos], series))
    chg = np.log(iv).diff()
    sd = chg.rolling(int(sd_days), min_periods=int(sd_days) // 2).std().shift(1)
    z = (chg / sd).to_numpy()
    fire = np.flatnonzero(z >= float(z_thr))
    side = spec[1] if mode == "fade" else -spec[1]
    hold = int(hold_d) * bars_per_day(d)
    atr = _atr(d, int(atr_n)).to_numpy()
    out: list[Signal] = []
    for p, s in _one_at_a_time([(int(pos[k]), side) for k in fire], hold):
        sig = _signal(d, p, s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=hold,
                      tag=f"implied_vol_shock_fade:{spec[0]}:{mode}")
        if sig is not None:
            out.append(sig)
    return out


def family_implied_vol_term_inversion(
    df: pd.DataFrame, *, symbol: str, front: str = "vix", back: str = "vix3m",
    mode: str = "unwind", hold_d: int = 5, decision_hour: int = 10,
    atr_n: int = 20, stop_atr: float = 2.5, rr: float = 1.5,
) -> list[Signal]:
    """`unwind`: risk-on on the first day the curve is back in contango after an inversion.
    `stress`: risk-off on the first inverted day. Refuses without the back-month series."""
    spec = IMPLIED_MAP.get(str(symbol))
    if spec is None or spec[0] != "vix" or mode not in ("unwind", "stress"):
        return []
    fs, bs = implied_series(front), implied_series(back)
    if fs is None or bs is None:
        return []
    d, pos = _decision_frame(df, decision_hour)
    if pos.size < 30:
        return []
    st = _stamps(d)[pos]
    ratio = _asof(st, fs) / _asof(st, bs)
    inv = ratio > 1.0
    prev = np.r_[False, inv[:-1]]
    fire = (inv & ~prev) if mode == "stress" else (~inv & prev & np.isfinite(ratio))
    side = -spec[1] if mode == "stress" else spec[1]
    hold = int(hold_d) * bars_per_day(d)
    atr = _atr(d, int(atr_n)).to_numpy()
    out: list[Signal] = []
    for p, s in _one_at_a_time([(int(pos[k]), side) for k in np.flatnonzero(fire)], hold):
        sig = _signal(d, p, s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=hold,
                      tag=f"implied_vol_term_inversion:{mode}")
        if sig is not None:
            out.append(sig)
    return out


# ------------------------------------------------------------------------------------- COT ---
#: COT contract files present in desks/mt5/data/cot, keyed by the currency or asset they price.
COT_CONTRACTS: dict[str, str] = {
    "JPY": "jpy", "EUR": "eur", "GBP": "gbp", "CAD": "cad", "AUD": "aud", "NZD": "nzd",
    "CHF": "chf", "XAU": "gold", "XAG": "silver",
}
COT_INDEX: dict[str, str] = {"US500": "sp500", "US30": "sp500", "NAS100": "nasdaq100",
                             "USDX": "dxy"}
#: Report dates whose release the 2013 and 2018-19 US government shutdowns DELAYED by weeks. A
#: fixed Friday lag would date them before they existed, so they are dropped, not mis-dated.
COT_DELAYED: tuple[tuple[str, str], ...] = (("2013-09-30", "2013-11-01"),
                                            ("2018-12-18", "2019-03-08"))


def cot_contract(symbol: str) -> tuple[str, int] | None:
    """(contract slug, orientation): +1 when a long futures position is long the symbol."""
    s = str(symbol).upper()
    if s in COT_INDEX:
        return COT_INDEX[s], 1
    if len(s) == 6 and s.isalpha():
        base, quote = s[:3], s[3:]
        if base in COT_CONTRACTS:
            return COT_CONTRACTS[base], 1
        if quote in COT_CONTRACTS:
            return COT_CONTRACTS[quote], -1
    return None


@lru_cache(maxsize=32)
def _cot_cached(path: str, mtime_ns: int) -> pd.DataFrame | None:
    try:
        f = pd.read_parquet(path)
    except Exception:
        return None
    need = {"report_date", "open_interest_all", "noncomm_positions_long_all",
            "noncomm_positions_short_all", "comm_positions_long_all", "comm_positions_short_all"}
    if not need.issubset(f.columns) or len(f) < 60:
        return None
    f = f.copy()
    f["report_date"] = pd.to_datetime(f["report_date"], utc=True, errors="coerce")
    f = f.dropna(subset=["report_date"]).sort_values("report_date")
    f = f.drop_duplicates("report_date", keep="last")
    for lo, hi in COT_DELAYED:
        f = f[~((f["report_date"] >= pd.Timestamp(lo, tz="UTC"))
                & (f["report_date"] <= pd.Timestamp(hi, tz="UTC")))]
    oi = f["open_interest_all"].astype(float).replace(0.0, np.nan)
    out = pd.DataFrame({
        "spec": (f["noncomm_positions_long_all"].astype(float)
                 - f["noncomm_positions_short_all"].astype(float)) / oi,
        "comm": (f["comm_positions_long_all"].astype(float)
                 - f["comm_positions_short_all"].astype(float)) / oi,
    })
    # Tuesday as-of -> Friday 15:30 ET release = 22:30 broker -> usable from Friday 23:00 broker.
    out.index = pd.DatetimeIndex(f["report_date"].dt.normalize()
                                 + pd.Timedelta(days=3, hours=23))
    return out.dropna()


def cot_frame(symbol: str) -> tuple[pd.DataFrame, int] | None:
    """(weekly frame with `spec` and `comm` net shares of OI, indexed by usable-from, orientation)."""
    got = cot_contract(symbol)
    if got is None:
        return None
    p = COT_DIR / f"{got[0]}.parquet"
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        return None
    f = _cot_cached(str(p), mtime)
    return None if f is None else (f, got[1])


def _cot_signals(d: pd.DataFrame, usable: pd.DatetimeIndex, sides: np.ndarray, *, hold_d: int,
                 atr_n: int, stop_atr: float, rr: float, tag: str) -> list[Signal]:
    """One entry per report: the first bar stamped at or after the report became usable."""
    st = _stamps(d)
    locs = np.searchsorted(st, usable.as_unit("ns").asi8, side="left")
    hold = int(hold_d) * bars_per_day(d)
    atr = _atr(d, int(atr_n)).to_numpy()
    use_ns = usable.as_unit("ns").asi8
    # a report whose first usable bar is more than four days later fell into a gap in the bars;
    # entering then would trade a stale print as though it were fresh
    cands = [(int(p), int(s)) for p, s, u in zip(locs, sides, use_ns, strict=True)
             if s != 0 and 0 < p < len(d) - 1 and st[p] - u <= 4 * _NS_PER_D]
    out: list[Signal] = []
    for p, s in _one_at_a_time(cands, hold):
        sig = _signal(d, p, s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=hold, tag=tag)
        if sig is not None:
            out.append(sig)
    return out


def family_positioning_crowding_unwind(
    df: pd.DataFrame, *, symbol: str, lookback_w: int = 156, extreme_q: float = 0.85,
    turn_d: int = 20, hold_d: int = 10, atr_n: int = 20, stop_atr: float = 3.0, rr: float = 1.5,
) -> list[Signal]:
    """Against the crowd, only once price is already moving against it."""
    got = cot_frame(symbol)
    if got is None or not 0.5 < float(extreme_q) < 1.0:
        return []
    cot, orient = got
    d = _h1(df)
    if len(d) < 500 or len(cot) < int(lookback_w) // 2:
        return []
    pct = cot["spec"].rolling(int(lookback_w), min_periods=int(lookback_w) // 2).rank(pct=True)
    crowd = np.where(pct >= float(extreme_q), 1, np.where(pct <= 1 - float(extreme_q), -1, 0))
    # the crowd's side in SYMBOL terms; the price turn is read on the symbol's own bars at the
    # usable-from stamp, over `turn_d` days that end before it
    st = _stamps(d)
    close = d["close"].to_numpy(dtype=float)
    at = np.searchsorted(st, cot.index.as_unit("ns").asi8, side="left") - 1
    back = np.searchsorted(st, cot.index.as_unit("ns").asi8 - int(turn_d) * _NS_PER_D,
                           side="left") - 1
    sides = np.zeros(len(cot), dtype=int)
    for k in range(len(cot)):
        c = int(crowd[k]) * orient
        if c == 0 or at[k] < 1 or back[k] < 0 or at[k] <= back[k]:
            continue
        move = close[at[k]] - close[back[k]]
        if np.sign(move) == -c:
            sides[k] = -c
    return _cot_signals(d, cot.index, sides, hold_d=hold_d, atr_n=atr_n, stop_atr=stop_atr,
                        rr=rr, tag="positioning_crowding_unwind")


def family_positioning_hedging_pressure(
    df: pd.DataFrame, *, symbol: str, lookback_w: int = 156, extreme_q: float = 0.85,
    hold_d: int = 10, atr_n: int = 20, stop_atr: float = 3.0, rr: float = 1.5,
) -> list[Signal]:
    """Take the other side of hedgers at an extreme of their net share of open interest."""
    got = cot_frame(symbol)
    if got is None or not 0.5 < float(extreme_q) < 1.0:
        return []
    cot, orient = got
    d = _h1(df)
    if len(d) < 500:
        return []
    pct = cot["comm"].rolling(int(lookback_w), min_periods=int(lookback_w) // 2).rank(pct=True)
    # hedgers heavily net SHORT -> the premium is earned LONG, and vice versa
    s = np.where(pct <= 1 - float(extreme_q), 1, np.where(pct >= float(extreme_q), -1, 0))
    return _cot_signals(d, cot.index, s * orient, hold_d=hold_d, atr_n=atr_n, stop_atr=stop_atr,
                        rr=rr, tag="positioning_hedging_pressure")


def family_positioning_flow_momentum(
    df: pd.DataFrame, *, symbol: str, z_w: int = 52, z_thr: float = 1.5, hold_d: int = 5,
    atr_n: int = 20, stop_atr: float = 3.0, rr: float = 1.5,
) -> list[Signal]:
    """With the week's speculative flow when it is large against its own history."""
    got = cot_frame(symbol)
    if got is None or float(z_thr) <= 0:
        return []
    cot, orient = got
    d = _h1(df)
    if len(d) < 500:
        return []
    flow = cot["spec"].diff()
    r = flow.rolling(int(z_w), min_periods=int(z_w) // 2)
    z = ((flow - r.mean().shift(1)) / r.std().shift(1)).to_numpy()
    s = np.where(z >= float(z_thr), 1, np.where(z <= -float(z_thr), -1, 0))
    return _cot_signals(d, cot.index, s * orient, hold_d=hold_d, atr_n=atr_n, stop_atr=stop_atr,
                        rr=rr, tag="positioning_flow_momentum")


# ----------------------------------------------------------------------- execution operators ---
#: Price-only base families an entry operator may wrap. Declared, not discovered: a base that
#: needs an input the operator cannot rebuild would return [] and read as a mechanism that never
#: fires. Every one is registered, price-only, gauntlet-buildable and enters AT MARKET -- the
#: breakout families (`session_range_breakout`, `level_breakout`) rest STOP orders, so a pullback
#: limit or a spread delay has no market entry to operate on (measured on EURUSD: 0 of 4,518).
ENTRY_BASES: tuple[str, ...] = (
    "overnight_gap_decay", "failed_breakout", "asia_momentum", "london_close_momentum",
    "vol_transition", "turn_of_month", "monday_gap", "opening_range", "jump")

#: Server-hour session opens (the same clock `family_call.SESSIONS` uses).
SESSION_OPENS: tuple[int, ...] = (0, 8, 14)


def _memo() -> Any:
    from mt5desk.build_memo import Memo, copy_signals
    return Memo(copier=copy_signals)


_BASE_MEMO = _memo()


def _base_signals(d: pd.DataFrame, base_family: str, base_params: dict | None) -> list[Signal]:
    if base_family not in ENTRY_BASES:
        return []
    from mt5desk.families import get_family_func
    fn = get_family_func(base_family)
    if fn is None:
        return []
    params = {k: v for k, v in dict(base_params or {}).items()
              if k not in ("timeframe", "session", "symbol")}

    def _build() -> list[Signal]:
        try:
            raw = fn(d, side=1, **params)
        except TypeError:
            try:
                raw = fn(d, **params)
            except Exception:
                return []
        except Exception:
            return []
        return [s for s in (raw or []) if isinstance(s, Signal)]

    # ONE BASE BUILD PER (bars, base, base params) across the operator variants of a pass --
    # `family_exit_operated`'s memo, keyed on a content hash of the bars, copied on the way out
    from mt5desk.build_memo import args_key, frame_fingerprint
    return list(_BASE_MEMO.get_or_compute((frame_fingerprint(d), args_key(base_family, params)),
                                          _build) or [])


def _rebased(s: Signal, t: Any, entry_ref: float, *, trigger: float | None, wait: int,
             tag: str) -> Signal:
    """`s` moved to time `t` with its stop and target kept at the same distance from the new
    reference price, so the operator changes the ENTRY and nothing else."""
    ref0 = s.trigger if s.trigger is not None else None
    dist_stop = abs((ref0 if ref0 is not None else entry_ref) - s.stop)
    dist_tgt = abs(s.target - (ref0 if ref0 is not None else entry_ref))
    ref = trigger if trigger is not None else entry_ref
    return Signal(time=t, side=s.side, stop=ref - s.side * dist_stop,
                  target=ref + s.side * dist_tgt, ttl_bars=s.ttl_bars,
                  tag=f"{tag}<{s.tag}", trigger=trigger, wait_bars=int(wait))


def family_entry_alpha_limit_pullback(
    df: pd.DataFrame, *, symbol: str, base_family: str, base_params: dict | None = None,
    pullback_atr: float = 0.3, wait_bars: int = 4, atr_n: int = 20,
) -> list[Signal]:
    """The base's signals entered with a resting LIMIT `pullback_atr` ATRs better."""
    if not symbol or float(pullback_atr) <= 0 or int(wait_bars) < 1:
        return []
    d = _h1(df)
    base = _base_signals(d, base_family, base_params)
    if not base:
        return []
    atr = _atr(d, int(atr_n)).to_numpy()
    close = d["close"].to_numpy(dtype=float)
    st = _stamps(d)
    out: list[Signal] = []
    for s in base:
        if s.trigger is not None:            # a stop-entry base is already an order, not market
            continue
        p = int(np.searchsorted(st, pd.Timestamp(s.time).value, side="left"))
        if p >= len(d) - 1 or not (math.isfinite(atr[p]) and atr[p] > 0):
            continue
        ref = float(close[p])
        lim = ref - s.side * float(pullback_atr) * float(atr[p])
        out.append(_rebased(s, s.time, ref, trigger=lim, wait=int(wait_bars),
                            tag="entry_alpha_limit_pullback"))
    return out


def family_entry_alpha_spread_gate(
    df: pd.DataFrame, *, symbol: str, base_family: str, base_params: dict | None = None,
    spread_q: float = 0.5, window: int = 240, max_wait: int = 3,
) -> list[Signal]:
    """The base's signals delayed to the first bar whose spread is at or under its trailing
    `spread_q` quantile; dropped when no such bar arrives within `max_wait` bars."""
    if not symbol or "spread" not in df.columns or not 0 < float(spread_q) < 1:
        return []
    d = _h1(df)
    base = _base_signals(d, base_family, base_params)
    if not base:
        return []
    raw = df["spread"].astype(float)
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.index, utc=True, errors="coerce"))
    sp = raw[~raw.index.duplicated(keep="last")].reindex(d.index).ffill()
    thr = sp.rolling(int(window), min_periods=int(window) // 2).quantile(float(spread_q)).shift(1)
    ok = (sp <= thr).to_numpy()
    close = d["close"].to_numpy(dtype=float)
    st = _stamps(d)
    out: list[Signal] = []
    for s in base:
        if s.trigger is not None:
            continue
        p = int(np.searchsorted(st, pd.Timestamp(s.time).value, side="left"))
        # the base decided at bar p and would fill at p+1; the gate may hold the fill to p+1+k
        for q in range(p + 1, min(p + 1 + int(max_wait), len(d) - 1)):
            if bool(ok[q]):
                if q == p + 1:
                    break                 # no delay: identical to the base, not a new question
                out.append(_rebased(s, d.index[q - 1], float(close[q - 1]), trigger=None,
                                    wait=1, tag="entry_alpha_spread_gate"))
                break
    return out


def family_entry_alpha_open_offset(
    df: pd.DataFrame, *, symbol: str, base_family: str, base_params: dict | None = None,
    offset_bars: int = 1,
) -> list[Signal]:
    """The base's signals that would fill in the first `offset_bars` bars of a session open are
    moved to fill on the first bar after them. Signals elsewhere are dropped: they are the base
    cell unchanged, and re-testing them would charge a second trial for no new question."""
    if not symbol or int(offset_bars) < 1:
        return []
    d = _h1(df)
    base = _base_signals(d, base_family, base_params)
    if not base:
        return []
    close = d["close"].to_numpy(dtype=float)
    hours = d.index.hour.to_numpy()
    st = _stamps(d)
    out: list[Signal] = []
    for s in base:
        if s.trigger is not None:
            continue
        p = int(np.searchsorted(st, pd.Timestamp(s.time).value, side="left"))
        f = p + 1
        if f >= len(d) - 1:
            continue
        opened = next((h for h in SESSION_OPENS if 0 <= hours[f] - h < int(offset_bars)), None)
        if opened is None:
            continue
        q = f + (int(offset_bars) - (int(hours[f]) - opened))
        if q >= len(d) - 1:
            continue
        out.append(_rebased(s, d.index[q - 1], float(close[q - 1]), trigger=None, wait=1,
                            tag="entry_alpha_open_offset"))
    return out


# ------------------------------------------------------------------------- the Fed calendar ---
FED_CALENDAR = OBSERVABLES / "fomc_calendar.json"

#: Calendar rows by kind. A speech or testimony's CONTENT is unscheduled (news_reaction); an
#: FOMC statement, minutes or the Beige Book is a scheduled release (event_surprise).
SPEECH_KINDS = frozenset({"speeches", "testimony"})
RELEASE_KINDS = frozenset({"fomc", "beige"})


def _parse_et(month: str, day: str, clock: str) -> tuple[date, int, int] | None:
    try:
        y, m = (int(x) for x in str(month).split("-")[:2])
        dd = int(str(day).split("-")[0].split(",")[0].strip())
        txt = str(clock).strip().lower().replace(".", "")
        hm, _, ampm = txt.partition(" ")
        h, _, mi = hm.partition(":")
        hour, minute = int(h), int(mi or 0)
        if ampm.startswith("p") and hour != 12:
            hour += 12
        if ampm.startswith("a") and hour == 12:
            hour = 0
        return date(y, m, dd), hour, minute
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=4)
def _calendar_cached(path: str, mtime_ns: int) -> tuple[tuple[int, str, str], ...]:
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return ()
    rows = doc.get("raw") if isinstance(doc, dict) else None
    out: set[tuple[int, str, str]] = set()
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        got = _parse_et(r.get("month", ""), r.get("days", ""), r.get("time", ""))
        if got is None:
            continue
        kind = str(r.get("type") or "").strip().lower()
        title = str(r.get("title") or "")
        out.add((_broker_ns(*got), kind, title))
    return tuple(sorted(out))


def fed_calendar() -> tuple[tuple[int, str, str], ...]:
    """(bar-clock ns, kind, title) for every dated Fed calendar row, sorted; () when absent."""
    try:
        mtime = FED_CALENDAR.stat().st_mtime_ns
    except OSError:
        return ()
    return _calendar_cached(str(FED_CALENDAR), mtime)


def _is_policy_speaker(title: str) -> bool:
    t = title.lower()
    return any(w in t for w in ("chair", "governor", "vice chair", "president"))


def _read_and_trade(d: pd.DataFrame, event_ns: list[int], *, read_bars: int, react_atr: float,
                    mode: str, hold_bars: int, atr_n: int, stop_atr: float, rr: float,
                    tag: str) -> list[Signal]:
    """The shared reaction-function core: the move from the OPEN of the bar containing the event
    through the close `read_bars` later, in ATRs measured BEFORE the event; `continue` trades its
    sign, `fade` the opposite, entered at the next bar's open."""
    if mode not in ("continue", "fade") or int(read_bars) < 1 or float(react_atr) <= 0:
        return []
    st = _stamps(d)
    o = d["open"].to_numpy(dtype=float)
    c = d["close"].to_numpy(dtype=float)
    atr = _atr(d, int(atr_n)).to_numpy()
    cands: list[tuple[int, int]] = []
    for t in event_ns:
        p0 = int(np.searchsorted(st, t, side="right")) - 1       # the bar containing t
        if p0 < 1 or st[p0] + _NS_PER_H <= t:                    # no bar spans the event
            continue
        p = p0 + int(read_bars) - 1
        if p >= len(d) - 1:
            continue
        a = float(atr[p0 - 1])                                   # measured before the event
        mv = float(c[p] - o[p0])
        if not (math.isfinite(a) and a > 0 and math.isfinite(mv)) or abs(mv) < react_atr * a:
            continue
        s = int(np.sign(mv)) * (1 if mode == "continue" else -1)
        cands.append((p, s))
    out: list[Signal] = []
    for p, s in _one_at_a_time(cands, int(hold_bars)):
        sig = _signal(d, p, s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=int(hold_bars), tag=tag)
        if sig is not None:
            out.append(sig)
    return out


def family_cb_tone_speech_reaction(
    df: pd.DataFrame, *, symbol: str, mode: str = "continue", read_bars: int = 2,
    react_atr: float = 0.75, hold_bars: int = 12, speakers: str = "policy",
    atr_n: int = 20, stop_atr: float = 2.0, rr: float = 1.5,
) -> list[Signal]:
    """The market's read of a Fed speech or testimony, continued or faded."""
    if not symbol:
        return []
    cal = fed_calendar()
    if not cal:
        return []
    ev = [t for t, k, title in cal if k in SPEECH_KINDS
          and (speakers != "policy" or _is_policy_speaker(title))]
    return _read_and_trade(_h1(df), ev, read_bars=read_bars, react_atr=react_atr, mode=mode,
                           hold_bars=hold_bars, atr_n=atr_n, stop_atr=stop_atr, rr=rr,
                           tag=f"cb_tone_speech_reaction:{mode}")


def family_news_reaction_unscheduled_shock(
    df: pd.DataFrame, *, symbol: str, mode: str = "continue", jump_k: float = 3.0,
    quiet_h: float = 2.0, read_bars: int = 1, hold_bars: int = 8, atr_n: int = 20,
    vol_window: int = 240, stop_atr: float = 2.0, rr: float = 1.5,
) -> list[Signal]:
    """A shock no calendar announced: |bar move| >= jump_k ATR (measured on the bars before it),
    tick volume above its trailing median, not within `quiet_h` hours of any Fed calendar row,
    not the first bar of a session and not the week's first bar."""
    if not symbol or mode not in ("continue", "fade") or float(jump_k) <= 0:
        return []
    cal = fed_calendar()
    if not cal:
        return []
    d = _h1(df)
    if len(d) < int(vol_window) + 10:
        return []
    st = _stamps(d)
    o = d["open"].to_numpy(dtype=float)
    c = d["close"].to_numpy(dtype=float)
    atr_prev = _atr(d, int(atr_n)).shift(1).to_numpy()
    if "tick_volume" in df.columns:
        tv = df["tick_volume"].astype(float)
        tv.index = pd.DatetimeIndex(pd.to_datetime(tv.index, utc=True, errors="coerce"))
        tv = tv[~tv.index.duplicated(keep="last")].reindex(d.index)
        med = tv.rolling(int(vol_window), min_periods=int(vol_window) // 2).median().shift(1)
        loud = (tv > med).to_numpy()
    else:
        loud = np.ones(len(d), dtype=bool)
    cal_ns = np.asarray([t for t, _k, _ti in cal], dtype="int64")
    quiet = int(float(quiet_h) * _NS_PER_H)
    hours = d.index.hour.to_numpy()
    gap = np.r_[np.inf, np.diff(st) / _NS_PER_H]
    events: list[int] = []
    for i in range(1, len(d) - 1):
        a = atr_prev[i]
        if not (math.isfinite(a) and a > 0) or abs(c[i] - o[i]) < float(jump_k) * a:
            continue
        if not bool(loud[i]) or hours[i] in SESSION_OPENS or gap[i] > 6:
            continue
        j = int(np.searchsorted(cal_ns, st[i]))
        near = any(0 <= k < cal_ns.size and abs(int(cal_ns[k]) - int(st[i])) <= quiet + _NS_PER_H
                   for k in (j - 1, j))
        if near:
            continue
        events.append(int(st[i]))
    return _read_and_trade(d, events, read_bars=read_bars, react_atr=float(jump_k) * 0.5,
                           mode=mode, hold_bars=hold_bars, atr_n=atr_n, stop_atr=stop_atr, rr=rr,
                           tag=f"news_reaction_unscheduled_shock:{mode}")


def family_event_surprise_impact_drift(
    df: pd.DataFrame, *, symbol: str, mode: str = "continue", kinds: str = "fomc",
    read_bars: int = 1, react_atr: float = 0.75, hold_bars: int = 12, atr_n: int = 20,
    stop_atr: float = 2.0, rr: float = 1.5,
) -> list[Signal]:
    """A scheduled Fed release, the surprise read off its impact bar, continued or reversed."""
    if not symbol:
        return []
    cal = fed_calendar()
    if not cal:
        return []
    want = {"fomc": {"fomc"}, "beige": {"beige"}, "all": set(RELEASE_KINDS)}.get(str(kinds))
    if not want:
        return []
    ev = [t for t, k, _ti in cal if k in want]
    return _read_and_trade(_h1(df), ev, read_bars=read_bars, react_atr=react_atr, mode=mode,
                           hold_bars=hold_bars, atr_n=atr_n, stop_atr=stop_atr, rr=rr,
                           tag=f"event_surprise_impact_drift:{kinds}:{mode}")


#: Currency -> the instruments a release in it is traded on, and the side a POSITIVE surprise in
#: that currency's own data maps to on each (+1: long the instrument). Only the mapping's SIGN
#: convention is declared here; whether up-surprises are bought or sold is `side_on_up`.
CURRENCY_LEGS: dict[str, int] = {"USD": -1, "EUR": 1, "GBP": 1, "JPY": -1, "AUD": 1, "NZD": 1,
                                 "CAD": -1, "CHF": -1}


@lru_cache(maxsize=4)
def _consensus_cached(path: str, mtime_ns: int) -> tuple[tuple[int, str, float], ...]:
    out: list[tuple[int, str, float]] = []
    try:
        fh = Path(path).open(encoding="utf-8")
    except OSError:
        return ()
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict):
                continue
            z = r.get("z") if r.get("z") is not None else r.get("surprise_z")
            at = r.get("release_utc") or r.get("at") or r.get("released_at")
            cur = str(r.get("currency") or "").upper()
            try:
                zf = float(z)
                t = pd.Timestamp(at)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(zf) or cur not in CURRENCY_LEGS or pd.isna(t):
                continue
            out.append((utc_to_bar_ns(t), cur, zf))
    return tuple(sorted(out))


def family_event_surprise_consensus(
    df: pd.DataFrame, *, symbol: str, side_on_up: int = 1, z_min: float = 1.0,
    hold_bars: int = 8, atr_n: int = 20, stop_atr: float = 2.0, rr: float = 1.5,
) -> list[Signal]:
    """side = side_on_up x sign(z) x the symbol's leg sign, for |z| >= z_min, entered on the
    first bar that OPENS after the release. Refuses without the consensus store."""
    s = str(symbol).upper()
    if len(s) != 6 or int(side_on_up) not in (1, -1) or float(z_min) <= 0:
        return []
    try:
        mtime = CONSENSUS_STORE.stat().st_mtime_ns
    except OSError:
        return []
    rows = _consensus_cached(str(CONSENSUS_STORE), mtime)
    legs = {s[:3]: 1, s[3:]: -1}
    d = _h1(df)
    st = _stamps(d)
    atr = _atr(d, int(atr_n)).to_numpy()
    cands: list[tuple[int, int]] = []
    for t, cur, z in rows:
        if cur not in legs or abs(z) < float(z_min):
            continue
        p = int(np.searchsorted(st, t, side="left"))        # first bar opening at/after release
        if p < 1 or p >= len(d) - 1:
            continue
        side = int(side_on_up) * int(np.sign(z)) * legs[cur]
        cands.append((p - 1, side))                          # decided on p-1, filled at p's open
    out: list[Signal] = []
    for p, sd in _one_at_a_time(cands, int(hold_bars)):
        sig = _signal(d, p, sd, atr, stop_atr=stop_atr, rr=rr, ttl_bars=int(hold_bars),
                      tag="event_surprise_consensus")
        if sig is not None:
            out.append(sig)
    return out


# ------------------------------------------------------------------------ cross-asset lead ---
def _driver_close(d: pd.DataFrame, cond_symbol: str, *, max_stale_h: float) -> np.ndarray | None:
    from mt5desk import families_cross_sectional as xs
    series = xs._load_series(str(cond_symbol))
    if series is None:
        return None
    t, c = series
    st = _stamps(d)
    j = np.searchsorted(t, st, side="right") - 1
    out = np.full(st.size, np.nan)
    has = j >= 0
    jj = np.where(has, j, 0)
    fresh = has & ((st - t[jj]) <= float(max_stale_h) * _NS_PER_H)
    out[fresh] = c[jj[fresh]]
    return out


def family_cross_asset_lead_lag(
    df: pd.DataFrame, *, symbol: str, cond_symbol: str, lag: int = 2, direction: str = "same",
    entry_z: float = 1.5, norm: int = 240, hold_bars: int = 6, atr_n: int = 20,
    stop_atr: float = 2.0, rr: float = 1.5, max_stale_h: float = 2.0,
) -> list[Signal]:
    """`lead_lag`'s claim with the driver loaded here: z of the driver's `lag`-bar log return."""
    if (not symbol or not cond_symbol or str(cond_symbol) == str(symbol)
            or direction not in ("same", "opposite") or int(lag) < 1):
        return []
    d = _h1(df)
    if len(d) < max(2 * int(norm), 300):
        return []
    dc = _driver_close(d, cond_symbol, max_stale_h=max_stale_h)
    if dc is None or not np.isfinite(dc).any():
        return []
    x = pd.Series(np.log(dc)).diff()
    sig = x.rolling(int(lag), min_periods=int(lag)).sum()
    r = sig.rolling(int(norm), min_periods=int(norm))
    z = ((sig - r.mean()) / r.std()).to_numpy()
    flip = 1 if direction == "same" else -1
    atr = _atr(d, int(atr_n)).to_numpy()
    cands = [(i, int(np.sign(z[i])) * flip) for i in range(int(norm), len(d) - 1)
             if math.isfinite(z[i]) and abs(z[i]) >= float(entry_z)]
    out: list[Signal] = []
    for p, s in _one_at_a_time(cands, int(hold_bars)):
        sgl = _signal(d, p, s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=int(hold_bars),
                      tag=f"cross_asset_lead_lag:{cond_symbol}:{direction}")
        if sgl is not None:
            out.append(sgl)
    return out


def family_lead_lag_session_handoff(
    df: pd.DataFrame, *, symbol: str, cond_symbol: str, read_hour: int = 22,
    session_h: int = 8, decision_hour: int = 1, direction: str = "same", z_thr: float = 1.0,
    z_days: int = 120, hold_bars: int = 7, atr_n: int = 20, stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """The driver's return over the `session_h` hours ending at `read_hour` (broker), z-scored on
    its own trailing days, traded on the target at its first bar at/after `decision_hour` on the
    next broker day."""
    if (not symbol or not cond_symbol or str(cond_symbol) == str(symbol)
            or direction not in ("same", "opposite") or not 1 <= int(session_h) <= 16):
        return []
    from mt5desk import families_cross_sectional as xs
    series = xs._load_series(str(cond_symbol))
    if series is None:
        return []
    t, c = series
    d = _h1(df)
    pos = _daily_decisions(d, int(decision_hour))
    if pos.size < int(z_days) + 5:
        return []
    st = _stamps(d)[pos]
    day0 = (st // _NS_PER_D) * _NS_PER_D
    end = day0 - _NS_PER_D + int(read_hour) * _NS_PER_H + _NS_PER_H   # yesterday's read bar close
    start = end - int(session_h) * _NS_PER_H

    def _at(x: np.ndarray) -> np.ndarray:
        j = np.searchsorted(t, x - _NS_PER_H, side="right") - 1     # bar STAMPED before x closes
        v = np.full(x.size, np.nan)
        ok = (j >= 0) & (x - t[np.where(j >= 0, j, 0)] <= 3 * _NS_PER_H)
        v[ok] = c[j[ok]]
        return v

    with np.errstate(divide="ignore", invalid="ignore"):
        ret = pd.Series(np.log(_at(end) / _at(start)))
    ok_time = end <= st                                               # read closed before decision
    sd = ret.rolling(int(z_days), min_periods=int(z_days) // 2).std().shift(1)
    z = (ret / sd).to_numpy()
    flip = 1 if direction == "same" else -1
    atr = _atr(d, int(atr_n)).to_numpy()
    cands = [(int(pos[k]), int(np.sign(z[k])) * flip) for k in range(pos.size)
             if ok_time[k] and math.isfinite(z[k]) and abs(z[k]) >= float(z_thr)]
    out: list[Signal] = []
    for p, s in _one_at_a_time(cands, int(hold_bars)):
        sgl = _signal(d, p, s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=int(hold_bars),
                      tag=f"lead_lag_session_handoff:{cond_symbol}:{direction}")
        if sgl is not None:
            out.append(sgl)
    return out


# ------------------------------------------------------------------------------ registry ------
EMPTY_CLUSTER_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "implied_vol_risk_premium": family_implied_vol_risk_premium,
    "implied_vol_shock_fade": family_implied_vol_shock_fade,
    "implied_vol_term_inversion": family_implied_vol_term_inversion,
    "positioning_crowding_unwind": family_positioning_crowding_unwind,
    "positioning_hedging_pressure": family_positioning_hedging_pressure,
    "positioning_flow_momentum": family_positioning_flow_momentum,
    "entry_alpha_limit_pullback": family_entry_alpha_limit_pullback,
    "entry_alpha_spread_gate": family_entry_alpha_spread_gate,
    "entry_alpha_open_offset": family_entry_alpha_open_offset,
    "cb_tone_speech_reaction": family_cb_tone_speech_reaction,
    "news_reaction_unscheduled_shock": family_news_reaction_unscheduled_shock,
    "event_surprise_impact_drift": family_event_surprise_impact_drift,
    "event_surprise_consensus": family_event_surprise_consensus,
    "cross_asset_lead_lag": family_cross_asset_lead_lag,
    "lead_lag_session_handoff": family_lead_lag_session_handoff,
}

#: What makes a cell of each family, the grid the producer sweeps (its trial count is charged in
#: the producer's census row). Instrument-dependent keys (cond_symbol, base_family) come from the
#: producer's declared maps, not from this grid.
PARAM_GRID: dict[str, dict[str, list]] = {
    "implied_vol_risk_premium": {"mode": ["harvest", "stress"], "z_thr": [1.0, 1.5],
                                 "hold_d": [1, 5]},
    "implied_vol_shock_fade": {"mode": ["fade", "follow"], "z_thr": [2.0, 3.0],
                               "hold_d": [1, 3]},
    "implied_vol_term_inversion": {"mode": ["unwind", "stress"], "hold_d": [3, 10]},
    "positioning_crowding_unwind": {"extreme_q": [0.8, 0.9], "turn_d": [10, 20],
                                    "hold_d": [5, 15]},
    "positioning_hedging_pressure": {"extreme_q": [0.8, 0.9], "hold_d": [5, 15]},
    "positioning_flow_momentum": {"z_thr": [1.0, 1.5, 2.0], "hold_d": [3, 5]},
    "entry_alpha_limit_pullback": {"pullback_atr": [0.25, 0.5], "wait_bars": [2, 6]},
    "entry_alpha_spread_gate": {"spread_q": [0.3, 0.5], "max_wait": [3]},
    "entry_alpha_open_offset": {"offset_bars": [1, 2]},
    "cb_tone_speech_reaction": {"mode": ["continue", "fade"], "read_bars": [1, 2],
                                "react_atr": [0.5, 1.0]},
    "news_reaction_unscheduled_shock": {"mode": ["continue", "fade"], "jump_k": [2.5, 3.5],
                                        "hold_bars": [4, 12]},
    "event_surprise_impact_drift": {"mode": ["continue", "fade"], "kinds": ["fomc", "all"],
                                    "react_atr": [0.5, 1.0]},
    "event_surprise_consensus": {"side_on_up": [1, -1], "z_min": [1.0, 1.5]},
    "cross_asset_lead_lag": {"lag": [1, 3], "direction": ["same", "opposite"],
                             "entry_z": [1.5, 2.0]},
    "lead_lag_session_handoff": {"direction": ["same", "opposite"], "z_thr": [0.75, 1.5]},
}

