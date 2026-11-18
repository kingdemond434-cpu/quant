"""SINGAPORE BAND STATE -- the inferred S$NEER position inside MAS's policy band, as a USDSGD state.

WHAT IT PUBLISHES. One stamped series, `data/lake/series/sg_neer_band.parquet`, with one signal
column, `band_pos`: where the trade-weighted Singapore dollar sits inside the band MAS manages it
in, in units of the band's half-width (0 = the midpoint, +1 = the top edge, -1 = the floor). The
`exogenous_conditioner` family reads it through the culture-gap recipe `sg_neer_band_state`
(USDSGD), and the scheduled Monetary Policy Statement dates go to
`data/calendars/mas_mps.json` for the `sg_mas_mps_hour` event cells.

THE ESTIMATE, AND EVERY INFERENCE IN IT NAMED. MAS publishes none of the band's three parameters
(see `pack.CENTRAL_BANK`), so each is an estimate and says so:

  * THE LEVEL is a SYNTHETIC S$NEER built only from broker bars (no external fetch): the log value
    of one Singapore dollar in USD, CNY (through USDCNH), EUR, JPY, AUD and GBP, weighted by
    `WEIGHTS`. The weights are an approximation of Singapore's trade shares restricted to
    currencies this broker quotes; MYR, TWD and the rest of ASEAN are absent and their weight is
    not reassigned to anything that pretends to be them.
  * THE CENTRE is anchored at every statement that RE-CENTRED the band "to the prevailing level":
    the midpoint is set to the synthetic NEER at the last broker close BEFORE the statement. The
    series therefore starts at the 2020-03-30 re-centring; before it there is no anchor and no row.
  * THE SLOPE is the market's reading of MAS's adjectives, held as a convention (`SLOPE_STEP`):
    "slight" is 0.5 percentage points a year, "very slight" 0.25, "set to zero" is zero. The
    midpoint crawls at that rate between statements.
  * THE WIDTH is the market convention of +/-2% (`HALF_WIDTH`); MAS has never published it and
    did not change it once in the record below.

NO LOOKAHEAD. A row for broker date d uses the close of d and only statements published at or
before that close; its `available_time` is the true UTC instant the last bar of d closed (broker
stamps are read through `libs/regime/session_clock.server_to_utc`). The conditioner then holds
every value back a further day. A statement re-centres from the close BEFORE it, which was
public when MAS spoke. The calendar holds SCHEDULED statements only: an off-cycle statement was
not knowable before it arrived, so a cell that traded into its hour would be trading on hindsight.

THE RECORD is MAS's own "past monetary policy decisions" table, read by hand on 2026-11-18 (the
MAS website's general terms allow personal non-commercial use only, so the site is never fetched
by this organ; the dates and adjectives are facts transcribed once and kept here as code). Release
time: 08:00 SGT (`pack.CENTRAL_BANK["announce_local"]`).
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[3]
CALENDAR_PATH = DESK / "data" / "calendars" / "mas_mps.json"
SERIES_ID = "sg_neer_band"
MPS_TZ = "Asia/Singapore"
MPS_AT = "08:00"

#: Approximate trade weights over the currencies this broker quotes (an inference, see above).
WEIGHTS: dict[str, float] = {"USD": 0.30, "CNY": 0.28, "EUR": 0.18, "JPY": 0.10, "AUD": 0.08,
                             "GBP": 0.06}
#: The band's half-width in log units: the market convention of +/-2%.
HALF_WIDTH = 0.02
#: MAS's slope adjectives as annual percentage-point changes (the market's reading, not MAS's).
SLOPE_STEP: dict[str, float] = {"slight increase": 0.5, "very slight increase": 0.25,
                                "slight reduction": -0.5, "unchanged": 0.0}
#: Rows below this are UNMEASURED and nothing is written.
MIN_ROWS = 30

#: MAS's decision record, 2016 onward: (date, slope, re-centred, off-cycle). "zero" sets the
#: slope to zero; any other slope is a key of SLOPE_STEP. Source: mas.gov.sg/monetary-policy/
#: past-monetary-policy-decisions, read 2026-11-18. 2015 (incl. the 28 Jan off-cycle move) is not
#: listed: its release time was not verified, and a guessed hour is worse than a missing date.
MPS_RECORD: tuple[tuple[str, str, bool, bool], ...] = (
    ("2016-04-14", "zero", False, False),
    ("2016-10-14", "unchanged", False, False),
    ("2017-04-13", "unchanged", False, False),
    ("2017-10-13", "unchanged", False, False),
    ("2018-04-13", "slight increase", False, False),
    ("2018-10-12", "slight increase", False, False),
    ("2019-04-12", "unchanged", False, False),
    ("2019-10-14", "slight reduction", False, False),
    ("2020-03-30", "zero", True, True),
    ("2020-10-14", "unchanged", False, False),
    ("2021-04-14", "unchanged", False, False),
    ("2021-10-14", "slight increase", False, False),
    ("2022-01-25", "slight increase", False, True),
    ("2022-04-14", "slight increase", True, False),
    ("2022-07-14", "unchanged", True, True),
    ("2022-10-14", "unchanged", True, False),
    ("2023-04-14", "unchanged", False, False),
    ("2023-10-13", "unchanged", False, False),
    ("2024-01-29", "unchanged", False, False),
    ("2024-04-12", "unchanged", False, False),
    ("2024-07-26", "unchanged", False, False),
    ("2024-10-14", "unchanged", False, False),
    ("2025-01-24", "slight reduction", False, False),
    ("2025-04-14", "slight reduction", False, False),
    ("2025-07-30", "unchanged", False, False),
    ("2025-10-14", "unchanged", False, False),
    ("2026-01-29", "unchanged", False, False),
    ("2026-04-14", "slight increase", False, False),
    ("2026-07-27", "very slight increase", False, False),
    ("2026-10-14", "unchanged", False, False),
)


def mps_instant(day: str) -> pd.Timestamp:
    """The statement's UTC instant: 08:00 Singapore time (UTC+8, no daylight saving)."""
    return pd.Timestamp(f"{day} {MPS_AT}").tz_localize(MPS_TZ).tz_convert("UTC")


def calendar_doc(record: Sequence[tuple[str, str, bool, bool]] = MPS_RECORD) -> dict[str, Any]:
    """The `mt5desk/local_clock` calendar of SCHEDULED statements (off-cycle ones excluded)."""
    return {
        "name": "mas_mps",
        "tz": MPS_TZ,
        "note": ("MAS Monetary Policy Statement dates at MAS's own local time (08:00 SGT). "
                 "SCHEDULED statements only: the off-cycle statements of 2020-03-30, 2022-01-25 "
                 "and 2022-07-14 were not knowable in advance and are excluded so no cell trades "
                 "into an hour nobody could have known was an event. Generated from "
                 "desks/mt5/research/countries/sg/band_state.py MPS_RECORD; regenerate, never "
                 "hand-edit (a test pins the two equal). Append each statement from MAS's past "
                 "decisions page once it is published."),
        "sources": ["https://www.mas.gov.sg/monetary-policy/past-monetary-policy-decisions",
                    "https://www.mas.gov.sg/monetary-policy/advance-release-calendar"],
        "verified_at": "2026-11-18",
        "dates": {d: MPS_AT for d, _s, _r, off in record if not off},
    }


def write_calendar(path: Path = CALENDAR_PATH) -> bool:
    """Write the calendar when it differs from the record. True when the file changed."""
    doc = calendar_doc()
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    try:
        if path.read_text("utf-8") == text:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, "utf-8")
    tmp.replace(path)
    return True


# ------------------------------------------------------------------------------ the level

def _closes(load: Callable[[str], pd.DataFrame | None], symbol: str) -> pd.Series | None:
    """Last H1 close per BROKER date, indexed by the true UTC instant that bar closed."""
    df = load(symbol)
    if df is None or len(df) == 0 or "close" not in df.columns:
        return None
    from libs.regime.session_clock import server_to_utc
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    s = pd.Series(pd.to_numeric(df["close"], errors="coerce").to_numpy(), index=idx).dropna()
    s = s[s > 0].sort_index()
    if s.empty:
        return None
    last = s.groupby(s.index.normalize()).tail(1)
    closed = server_to_utc(last.index) + pd.Timedelta(hours=1)
    out = pd.Series(last.to_numpy(), index=pd.DatetimeIndex(last.index.normalize()))
    out.attrs["closed_utc"] = pd.Series(closed, index=out.index)
    return out


def synthetic_neer(load: Callable[[str], pd.DataFrame | None]
                   ) -> tuple[pd.DataFrame, list[str]]:
    """(frame of broker-date rows with `log_neer` and `closed_utc`, notes on the legs used).

    Each currency leg is the log value of one SGD in that currency, from the direct SGD cross
    where the broker has it and through USD otherwise. A date missing any leg has no row."""
    notes: list[str] = []
    cache: dict[str, pd.Series | None] = {}

    def c(sym: str) -> pd.Series | None:
        if sym not in cache:
            cache[sym] = _closes(load, sym)
        return cache[sym]

    usdsgd = c("USDSGD")
    if usdsgd is None:
        return pd.DataFrame(), ["USDSGD: no H1 tape -- the state is UNMEASURED"]
    lu = np.log(usdsgd)

    def via(direct: str, invert: bool, usd_pair: str, usd_quoted_first: bool) -> pd.Series | None:
        d = c(direct)
        if d is not None:
            notes.append(f"{direct} direct")
            return -np.log(d) if invert else np.log(d)
        u = c(usd_pair)
        if u is None:
            notes.append(f"{direct}: no tape, and no {usd_pair} to cross through")
            return None
        notes.append(f"{direct} crossed through {usd_pair}")
        # SGD in X = (X per USD) / (SGD per USD)
        x_per_usd = np.log(u) if usd_quoted_first else -np.log(u)
        return x_per_usd - lu

    legs = {
        "USD": -lu,
        "CNY": (np.log(c("USDCNH")) - lu) if c("USDCNH") is not None else None,
        "EUR": via("EURSGD", True, "EURUSD", False),
        "JPY": via("SGDJPY", False, "USDJPY", True),
        "AUD": via("AUDSGD", True, "AUDUSD", False),
        "GBP": via("GBPSGD", True, "GBPUSD", False),
    }
    missing = [k for k, v in legs.items() if v is None]
    if missing:
        return pd.DataFrame(), [*notes, f"legs absent: {missing} -- the state is UNMEASURED"]
    frame = pd.concat({k: v for k, v in legs.items() if v is not None}, axis=1).dropna()
    frame["log_neer"] = sum(WEIGHTS[k] * frame[k] for k in WEIGHTS)
    closed = pd.concat([s.attrs["closed_utc"] for s in cache.values() if s is not None],
                       axis=1).max(axis=1)
    frame["closed_utc"] = closed.reindex(frame.index)
    return frame[["log_neer", "closed_utc"]].dropna(), notes


# ------------------------------------------------------------------------------ the band

def band_path(neer: pd.DataFrame,
              record: Sequence[tuple[str, str, bool, bool]] = MPS_RECORD) -> pd.DataFrame:
    """`band_pos` per broker date from the first re-centring the tape covers.

    A statement applies from the first close AFTER its 08:00 SGT instant. A re-centring anchors
    the midpoint at the last close BEFORE that instant."""
    if neer.empty:
        return pd.DataFrame()
    closed = pd.to_datetime(neer["closed_utc"], utc=True)
    log_neer = neer["log_neer"].astype(float)
    events = sorted((mps_instant(d), s, r) for d, s, r, _off in record)
    slope = 0.0
    mid: float | None = None
    mid_at: pd.Timestamp | None = None
    out_pos: list[float] = []
    out_idx: list[pd.Timestamp] = []
    out_at: list[pd.Timestamp] = []
    ei = 0
    for day, at, ln in zip(neer.index, closed, log_neer, strict=True):
        while ei < len(events) and events[ei][0] < at:
            t, s, recentre = events[ei]
            if mid is not None and mid_at is not None:     # crawl to the statement first
                mid += slope / 100.0 * (t - mid_at).total_seconds() / (365.25 * 86400)
                mid_at = t
            slope = 0.0 if s == "zero" else slope + SLOPE_STEP.get(s, 0.0)
            if recentre:
                prior = log_neer[closed < t]
                if len(prior):
                    mid, mid_at = float(prior.iloc[-1]), t
            ei += 1
        if mid is None or mid_at is None:
            continue
        m = mid + slope / 100.0 * (at - mid_at).total_seconds() / (365.25 * 86400)
        out_pos.append((ln - m) / HALF_WIDTH)
        out_idx.append(day)
        out_at.append(at)
    if not out_pos:
        return pd.DataFrame()
    return pd.DataFrame({"band_pos": out_pos, "event_time": out_idx,
                         "available_time": out_at})


def slope_now(record: Sequence[tuple[str, str, bool, bool]] = MPS_RECORD) -> float:
    s = 0.0
    for _d, step, _r, _o in record:
        s = 0.0 if step == "zero" else s + SLOPE_STEP.get(step, 0.0)
    return s


def build(load: Callable[[str], pd.DataFrame | None]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """(stamped frame or empty, report block)."""
    neer, notes = synthetic_neer(load)
    band = band_path(neer)
    info: dict[str, Any] = {
        "series": SERIES_ID, "targets": ["USDSGD"], "legs": notes, "weights": WEIGHTS,
        "half_width": HALF_WIDTH, "slope_now_pa": slope_now(), "rows": len(band)}
    if len(band) < MIN_ROWS:
        info["status"] = f"UNMEASURED: {len(band)} rows (< {MIN_ROWS})"
        return pd.DataFrame(), info
    last = band.iloc[-1]
    info.update(status="BUILT", last_event=str(pd.Timestamp(last["event_time"]).date()),
                last_band_pos=round(float(last["band_pos"]), 4))
    return band, info


def record_summary(record: Sequence[tuple[str, str, bool, bool]] = MPS_RECORD
                   ) -> Mapping[str, Any]:
    return {"statements": len(record), "scheduled": sum(not o for *_x, o in record),
            "off_cycle": [d for d, _s, _r, o in record if o],
            "recentred": [d for d, _s, r, _o in record if r]}
