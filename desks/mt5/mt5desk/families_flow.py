"""FLOW FAMILIES: reported positioning (all three CFTC reports), the equity-options expiry
calendar, and the tick tape's signed-tick imbalance -- each loaded by the family itself.

WHY A NEW MODULE (2026-11-13). The hourly research pass measured three producers at 0 cells in
24h, and in each case the family existed in name while its input never reached it:

  COT        `cot_positioning` reads `data/cot_zcache.parquet` at the REPO root, which only the
             VPS's `quant-cot-zcache` timer writes (gitignored, and the refresher refuses to
             bootstrap an absent cache) -- so on the box that runs the gauntlet it is always
             `cot=None`. The four raw `cot_*` families were set aside as INPUT_NOT_SUPPLIED by
             `gauntlet_buildability`, whose source scan read `family in {...}` literals but not
             `family in RAW_COT_FAMILIES`. And neither path could read the TFF or disaggregated
             reports the desk already holds in-tree (`data/cot_tff/`, `data/cot_disagg/`), so
             indices -- which the legacy file stops covering in 2021 -- had no COT family at all.
  ORDERFLOW  `orderflow_imbalance` is handed `flow` by the sealed gauntlet only from the last 30
             silver files, as a mid-change sum forward-filled over gaps. Thirty days cannot clear
             a 66-trade-day floor however the family fires. `tape_flow` reads the WHOLE silver
             tape the tick moat has written (`data/tape/ticks/<SYM>/<DAY>.parquet`) as a
             normalised signed-tick imbalance per bar; the family selects it with
             `flow_source="tape_signed_ticks"` and the cell's own `symbol`.
  GAMMA      `us:custom:expiry_gamma_calendar` is an unwired event study (`countries/us/pack.py`,
             `wired: False`) and `forced_flow`'s `option_expiry` kind is a minutes-wide window
             around one settlement print; nothing could say "the opex week" or "the week after the
             quad witch" as a family. `expiry_gamma` does, from the date alone.

THE CONTRACT IS `families_specialist`'s: every foreign input is loaded HERE from what the cell
carries (`report`/`market`, `symbol`), because the sealed `build_cell` is never edited. The
gauntlet, the forward clock and the live executor therefore build identical signals.

NO LOOKAHEAD, BY CONSTRUCTION.
  * A CFTC report is as-of TUESDAY and released the following FRIDAY 15:30 ET. A report is
    usable from `report_date + COT_USABLE_AFTER_D` (the Monday after release, 00:00 bar clock),
    the same lag `families._cot_entries` and `orthogonal_sweep._cot_frame` apply. Percentiles and
    z-scores are trailing, over reports already usable. A report the CFTC published LATE (the
    2013 and 2025 shutdowns) is not marked in the in-tree files; the lag is the rule, and that
    limit is written here rather than hidden.
  * The expiry calendar is the third Friday of the month, computed from the date alone; whether
    the market turned out to be open plays no part. An exchange holiday on the third Friday
    (expiry moves to Thursday) is not modelled -- stated, not hidden.
  * The tape imbalance of a bar uses only ticks inside that bar; the signal enters at the next
    open (`wait_bars=1`). A bar with too few ticks is ABSENT (NaN), never forward-filled.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, bar_minutes, bars_per_day

BASE = Path(__file__).resolve().parent.parent            # desks/mt5
DATA = BASE / "data"
#: Where each CFTC report lives in-tree (one parquet per market slug, `report_date` column).
COT_DIRS: dict[str, str] = {"legacy": "cot", "tff": "cot_tff", "disagg": "cot_disagg"}
#: (long column, short column, open-interest column) per trader group, per report.
COT_GROUPS: dict[str, dict[str, tuple[str, str, str]]] = {
    "legacy": {"noncomm": ("noncomm_positions_long_all", "noncomm_positions_short_all",
                           "open_interest_all"),
               "comm": ("comm_positions_long_all", "comm_positions_short_all",
                        "open_interest_all")},
    "tff": {"lev_money": ("lm_l", "lm_s", "oi"), "asset_mgr": ("am_l", "am_s", "oi"),
            "dealer": ("dealer_l", "dealer_s", "oi")},
    "disagg": {"managed_money": ("m_money_positions_long_all", "m_money_positions_short_all",
                                 "open_interest_all"),
               "swap": ("swap_positions_long_all", "swap__positions_short_all",
                        "open_interest_all")},
}
COT_MODES = ("extreme_fade", "extreme_follow", "change_follow", "change_fade")
#: Tuesday as-of + 3 days to the Friday release + 3 days to the Monday after it.
COT_USABLE_AFTER_D = 6
#: A usable report whose first bar is further away than this is a data hole, not an entry.
COT_MAX_ENTRY_GAP_D = 4

#: The silver tape `recorders/tape_features` writes: `ts, bid, ask` (+ extras) per broker day.
TAPE_SILVER = DATA / "tape" / "ticks"
TAPE_FLOW_SOURCE = "tape_signed_ticks"
#: Fewer signed ticks than this in a bar and its imbalance is not a measurement.
MIN_TICKS_PER_BAR = 20

EXPIRY_SETS = ("all", "monthly", "quad")
EXPIRY_DIRECTIONS = ("long", "short", "follow", "fade")
QUAD_MONTHS = (3, 6, 9, 12)
#: The daily-expiry ladder reached every weekday from here (`countries/us/miners.py`): the era
#: is a parameter so the two halves are never pooled by accident.
ERA_SPLIT = date(2022, 5, 1)
ERAS = ("all", "pre_2022", "post_2022")


def _signal(d: pd.DataFrame, p: int, side: int, atr: np.ndarray, *, stop_atr: float, rr: float,
            ttl_bars: int, tag: str) -> Signal | None:
    a = float(atr[p])
    px = float(d["close"].iat[p])
    if not (math.isfinite(a) and a > 0 and math.isfinite(px) and px > 0) or side == 0:
        return None
    dist = float(stop_atr) * a
    return Signal(time=d.index[p], side=int(side), stop=px - side * dist,
                  target=px + side * dist * float(rr), ttl_bars=int(ttl_bars), tag=tag,
                  trigger=None, wait_bars=1)


# ------------------------------------------------------------------------------- COT reports ---
@lru_cache(maxsize=64)
def _cot_cached(path: str, mtime_ns: int) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if "report_date" not in df.columns:
        return None
    df = df.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], utc=True, errors="coerce")
    df = df.dropna(subset=["report_date"]).sort_values("report_date")
    return df.drop_duplicates("report_date", keep="last").reset_index(drop=True)


def cot_table(report: str, market: str) -> pd.DataFrame | None:
    """One CFTC report's rows for one market slug, sorted by report date, or None."""
    sub = COT_DIRS.get(str(report))
    if not sub or not market or not str(market).replace("_", "").isalnum():
        return None
    path = DATA / sub / f"{market}.parquet"
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    return _cot_cached(str(path), mtime)


def cot_net_share(report: str, market: str, group: str) -> pd.Series | None:
    """(long - short) / open interest of `group`, indexed by the instant it became USABLE."""
    cols = COT_GROUPS.get(str(report), {}).get(str(group))
    table = cot_table(report, market)
    if cols is None or table is None or any(c not in table.columns for c in cols):
        return None
    lo, sh, oi = (pd.to_numeric(table[c], errors="coerce").to_numpy(dtype="float64")
                  for c in cols)
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(oi > 0, (lo - sh) / oi, np.nan)
    usable = table["report_date"] + pd.Timedelta(days=COT_USABLE_AFTER_D)
    s = pd.Series(share, index=pd.DatetimeIndex(usable)).dropna()
    return s if not s.empty else None


def family_cot_report(
    df: pd.DataFrame,
    *,
    report: str = "legacy",
    market: str = "",
    group: str = "noncomm",
    mode: str = "extreme_fade",
    sign: int = 1,
    lookback_w: int = 104,
    q: float = 0.10,
    z_thr: float = 1.5,
    hold_d: int = 5,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Trade one trader group's weekly positioning in one CFTC report, from the Monday after it
    is published. `extreme_*` reads the trailing percentile of the group's net share of open
    interest (fade or follow the crowd at a `q` tail); `change_*` reads the week's change as a
    trailing z-score. `sign` maps the future onto the instrument: -1 where the future is the
    QUOTE currency (a long JPY future is a short USDJPY). One entry per usable report, held
    `hold_d` days."""
    if mode not in COT_MODES or int(sign) not in (1, -1) or int(lookback_w) < 26:
        return []
    if not 0.0 < float(q) < 0.5 or float(z_thr) <= 0 or int(hold_d) < 1:
        return []
    if df is None or len(df) == 0:
        return []
    net = cot_net_share(report, market, group)
    if net is None or len(net) < int(lookback_w) + 2:
        return []
    lb = int(lookback_w)
    if mode.startswith("extreme"):
        pct = net.rolling(lb, min_periods=lb).rank(pct=True).to_numpy()
        raw = np.where(pct >= 1.0 - float(q), 1, np.where(pct <= float(q), -1, 0))
        raw = np.where(np.isfinite(pct), raw, 0)
        side = -raw if mode == "extreme_fade" else raw
    else:
        delta = net.diff()
        mu = delta.rolling(lb, min_periods=lb).mean()
        sd = delta.rolling(lb, min_periods=lb).std(ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            z = ((delta - mu) / sd).to_numpy()
        hit = np.isfinite(z) & (np.abs(z) >= float(z_thr))
        raw = np.where(hit, np.sign(delta.to_numpy()), 0).astype(int)
        side = raw if mode == "change_follow" else -raw
    d = _h1(df)
    idx_ns = d.index.as_unit("ns").asi8
    atr = _atr(d, int(atr_n)).to_numpy()
    ttl = int(hold_d) * bars_per_day(d)
    gap_ns = COT_MAX_ENTRY_GAP_D * 86_400_000_000_000
    out: list[Signal] = []
    last = -1
    for at, s in zip(net.index.as_unit("ns").asi8, side, strict=True):
        if s == 0:
            continue
        p = int(np.searchsorted(idx_ns, at, side="left"))
        if p >= len(d) - 1 or p <= last or idx_ns[p] - at > gap_ns:
            continue
        sig = _signal(d, p, int(s) * int(sign), atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl,
                      tag=f"cot_report.{report}.{group}.{mode}")
        if sig is not None:
            out.append(sig)
            last = p
    return out


# --------------------------------------------------------------------------- expiry calendar ---
def third_friday(year: int, month: int) -> date:
    """The monthly equity-option expiry: `forced_flow_calendar.nth_weekday(y, m, FRIDAY, 3)`,
    computed here from the date alone so the family needs no research import."""
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


def add_weekdays(day: date, n: int) -> date:
    """`day` moved `n` weekdays (Mon-Fri; no holiday table, as the family's docstring says)."""
    step = 1 if n >= 0 else -1
    out = day
    for _ in range(abs(int(n))):
        out += timedelta(days=step)
        while out.weekday() >= 5:
            out += timedelta(days=step)
    return out


def expiry_days(lo: date, hi: date, expiry: str, day_from: int, day_to: int) -> set[date]:
    """Every weekday in [lo, hi] that sits `day_from..day_to` weekdays from a third Friday of the
    requested set (`all`, `monthly` = non-quarterly only, `quad` = Mar/Jun/Sep/Dec)."""
    out: set[date] = set()
    # a window can reach a month either side of the span, so the scan starts and ends one over
    y, m = (lo.year - 1, 12) if lo.month == 1 else (lo.year, lo.month - 1)
    end = (hi.year + 1, 1) if hi.month == 12 else (hi.year, hi.month + 1)
    while (y, m) <= end:
        quad = m in QUAD_MONTHS
        if expiry == "all" or (expiry == "quad") == quad:
            f = third_friday(y, m)
            for k in range(int(day_from), int(day_to) + 1):
                day = add_weekdays(f, k)
                if lo <= day <= hi:
                    out.add(day)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _daily_decisions(d: pd.DataFrame, decision_hour: int) -> np.ndarray:
    """Position of the LAST bar stamped at or before `decision_hour` on each weekday date."""
    idx = d.index
    ok = (idx.hour <= int(decision_hour)) & (idx.dayofweek < 5)
    pos = np.flatnonzero(ok)
    if pos.size == 0:
        return pos
    day = idx.normalize().asi8[pos]
    keep = np.r_[day[1:] != day[:-1], True]
    return pos[keep]


def family_expiry_gamma(
    df: pd.DataFrame,
    *,
    expiry: str = "all",
    day_from: int = -4,
    day_to: int = 0,
    decision_hour: int = 16,
    direction: str = "follow",
    lookback_d: int = 5,
    era: str = "all",
    hold_d: int = 1,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.5,
) -> list[Signal]:
    """Dealer gamma around the equity-option expiry: a daily decision at `decision_hour` on each
    weekday `day_from..day_to` weekdays from the third Friday (0 = the expiry itself, -4 = the
    Monday of opex week, +1 = the Monday after). `long`/`short` bet the calendar; `follow`/`fade`
    bet the hedge flow's direction against the trailing `lookback_d`-day move (the pin damps a
    move into expiry, the release lets it run after). Held `hold_d` days."""
    if expiry not in EXPIRY_SETS or direction not in EXPIRY_DIRECTIONS or era not in ERAS:
        return []
    if int(day_from) > int(day_to) or abs(int(day_from)) > 15 or abs(int(day_to)) > 15:
        return []
    if not 0 <= int(decision_hour) <= 23 or int(lookback_d) < 1 or int(hold_d) < 1:
        return []
    if df is None or len(df) == 0:
        return []
    d = _h1(df)
    pos = _daily_decisions(d, int(decision_hour))
    if pos.size <= int(lookback_d):
        return []
    days = d.index[pos].date
    targets = expiry_days(days[0], days[-1], expiry, int(day_from), int(day_to))
    close = d["close"].astype(float).to_numpy()
    atr = _atr(d, int(atr_n)).to_numpy()
    ttl = int(hold_d) * bars_per_day(d)
    out: list[Signal] = []
    for j, p in enumerate(pos):
        day = days[j]
        if day not in targets:
            continue
        if (era == "pre_2022" and day >= ERA_SPLIT) or (era == "post_2022" and day < ERA_SPLIT):
            continue
        if direction in ("long", "short"):
            s = 1 if direction == "long" else -1
        else:
            if j < int(lookback_d):
                continue
            move = close[p] - close[pos[j - int(lookback_d)]]
            if not math.isfinite(move) or move == 0.0:
                continue
            s = (1 if move > 0 else -1) * (1 if direction == "follow" else -1)
        sig = _signal(d, int(p), s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl,
                      tag=f"expiry_gamma.{expiry}.{direction}")
        if sig is not None:
            out.append(sig)
    return out


# -------------------------------------------------------------------------------- tick tape ---
def _day_imbalance(path: Path, rule: str, min_ticks: int) -> pd.Series | None:
    try:
        t = pd.read_parquet(path, columns=["ts", "bid", "ask"])
    except Exception:
        return None
    if t.empty:
        return None
    ts = pd.to_datetime(t["ts"], utc=True, errors="coerce")
    mid = (pd.to_numeric(t["bid"], errors="coerce").to_numpy(dtype="float64")
           + pd.to_numeric(t["ask"], errors="coerce").to_numpy(dtype="float64")) / 2.0
    order = np.argsort(ts.to_numpy(), kind="stable")
    mid = mid[order]
    stamps = pd.DatetimeIndex(ts.to_numpy()[order])
    step = np.sign(np.diff(mid, prepend=np.nan))         # first tick of the day: no sign
    frame = pd.DataFrame({"up": (step > 0).astype("int64"), "dn": (step < 0).astype("int64")},
                         index=stamps)
    frame = frame[stamps.notna()]
    if frame.empty:
        return None
    agg = frame.resample(rule, label="left", closed="left").sum()
    n = agg["up"] + agg["dn"]
    imb = (agg["up"] - agg["dn"]) / n.where(n >= int(min_ticks))
    return imb.dropna()


@lru_cache(maxsize=4)
def _tape_flow_cached(symbol: str, minutes: int, root: str, stamp: tuple[str, ...],
                      min_ticks: int) -> pd.Series | None:
    rule = f"{int(minutes)}min"
    parts = [s for s in (_day_imbalance(Path(root) / symbol / name, rule, min_ticks)
                         for name in stamp) if s is not None and not s.empty]
    if not parts:
        return None
    flow = pd.concat(parts).sort_index()
    return flow[~flow.index.duplicated(keep="last")]


def tape_days(symbol: str) -> list[str]:
    """The silver tape's day files for `symbol`, oldest first ([] when it has none here)."""
    if not symbol or "/" in symbol or "\\" in symbol or symbol.startswith("."):
        return []
    d = TAPE_SILVER / symbol
    try:
        return sorted(p.name for p in d.glob("*.parquet") if not p.name.startswith("."))
    except OSError:
        return []


def tape_flow(symbol: str, index: pd.DatetimeIndex, minutes: int | None = None,
              *, min_ticks: int = MIN_TICKS_PER_BAR) -> pd.Series | None:
    """Signed-tick imbalance (upticks - downticks) / signed ticks of `symbol`'s mid, per bar of
    `index`'s chart, from EVERY silver day on disk. NaN where the bar is absent from the tape or
    holds fewer than `min_ticks` signed ticks -- never forward-filled. None with no tape."""
    days = tape_days(symbol)
    if not days or len(index) == 0:
        return None
    mins = int(minutes or 60)
    flow = _tape_flow_cached(str(symbol), mins, str(TAPE_SILVER), tuple(days), int(min_ticks))
    if flow is None:
        return None
    idx = pd.DatetimeIndex(index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return flow.reindex(idx)


def tape_flow_for(df: pd.DataFrame, symbol: str) -> pd.Series | None:
    """`tape_flow` on `df`'s own index and chart -- what `orderflow_imbalance` reads."""
    d = _h1(df)
    return tape_flow(symbol, d.index, bar_minutes(d) or 60)


FLOW_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "cot_report": family_cot_report,
    "expiry_gamma": family_expiry_gamma,
}

#: `cot_report` reads a dataset the bars do not carry; `expiry_gamma` reads its own bars and
#: the calendar only.
INFORMATION_CLASS: dict[str, str] = {"cot_report": "exogenous", "expiry_gamma": "price_only"}
FOREIGN_SERIES: dict[str, tuple[tuple[str | None, str], ...]] = {
    "cot_report": (("market", "data/cot{,_tff,_disagg}/<market>.parquet (CFTC legacy, TFF, "
                              "disaggregated; usable from the Monday after release)"),),
    "expiry_gamma": (),
}
INPUTS: dict[str, tuple[str, str]] = {
    "cot_report": ("EXOGENOUS: one trader group's net share of open interest in the CFTC report "
                   "named by `report`/`market`, read from the in-tree parquet and usable from "
                   "the Monday after its Friday release -- not price-only",
                   "data/cot_tff/<market>.parquet"),
    "expiry_gamma": ("price only + the third-Friday equity-option expiry calendar, computed from "
                     "the date alone", "data/universe/*_H1.parquet"),
}
TIMEFRAMES: dict[str, tuple[tuple[str, ...], str]] = {
    "expiry_gamma": (("H1",), "decides once a day at a broker decision HOUR; on a four-hour or "
                              "daily chart the decision hour does not exist"),
}


def information_class(family: str) -> str | None:
    return INFORMATION_CLASS.get(str(family or ""))


__all__ = [
    "FLOW_FAMILIES",
    "FOREIGN_SERIES",
    "INFORMATION_CLASS",
    "INPUTS",
    "TIMEFRAMES",
    "cot_net_share",
    "cot_table",
    "expiry_days",
    "family_cot_report",
    "family_expiry_gamma",
    "tape_days",
    "tape_flow",
    "tape_flow_for",
    "third_friday",
]
