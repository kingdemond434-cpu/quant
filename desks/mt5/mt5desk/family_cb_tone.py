"""Trade an instrument after its central bank's published speeches lean hawkish or dovish.

    tone_day = (hawk - dove) / (hawk + dove)   over one currency's speeches PUBLISHED that day
    reading  = tone_day                              basis "level"
             = tone_day - mean(previous SURPRISE_OBS published days)   basis "surprise"
    event    = a published day whose reading is on the named side and at least `min_abs` strong
    signal   = `direction`, on the first bar that opens after the market could read the speech

MECHANISM. A central banker's public language moves ahead of the policy it describes: the
reaction function is revealed in speeches before it is revealed in a rate decision. Holders of
the currency's rate expectations, and of the assets discounted on them (gold and silver against
real USD rates, equity indices against the policy path), reprice over the days that follow as
the language is read, translated and absorbed. The claim is falsifiable per cell: it fails when
days of one-sided central-bank language carry no forward return net of cost.

THE EVENT CLOCK IS PUBLICATION, NOT DELIVERY (2026-11-10). The tone corpus stamps each speech
with its DELIVERY date, and `research/cb_tone_screen` read it two trading days later. Measured
on the desk's own corpus, the BIS publishes a speech a median 2 days after delivery, 14 days at
the 90th percentile and 52 at the 99th -- so a fixed two-day lag reads roughly half the corpus
before it existed. Every BIS review URL carries its publication date (`/review/rYYMMDD<x>`), so
each speech is keyed HERE on that date. A row whose URL carries no readable stamp, or a stamp
earlier than the delivery date (the corpus has dated typos), cannot be placed and is dropped --
counted in `LAST_DROPPED`, never guessed.

THE BAR CLOCK. The publication stamp is a DATE with no hour, so the speech is taken as knowable
from 00:00 UTC of the FOLLOWING day. The bar index is broker time, measured at UTC+2 in winter
and UTC+3 in summer; the entry bar must be labelled at or after that instant plus
`BROKER_MAX_OFFSET_H` (3h), which is on or after the knowable instant in BOTH seasons. It is at
most one hour late in winter and never early, so no event is dropped for want of a measured
clock and none is placed on a bar that opened before the news.

TWO BASES, KEPT AS SEPARATE HYPOTHESES. The lexicon counts far more dovish than hawkish hits
(USD: 1,156 dovish published days against 280 hawkish), so the LEVEL's sign mostly says "a
speech happened". The SURPRISE basis reads each day against the same bank's own recent language
-- the mean of its previous `SURPRISE_OBS` published days, each day against its own past only --
which is the part a reader could not already have expected.

THE INPUT IS NAMED ON THE RECIPE (`currency`) and loaded HERE from the tracked per-speech file
(`data/intelligence/central_banks/bis_speech_tone.jsonl`), so the sweep, the sealed gauntlet's
`build_cell` and the forward clock rebuild the same signals from the same identity.

AN ABSENT INPUT IS A NAMED REFUSAL, NOT A CELL THAT NEVER FIRES (L1.28a): no tone file, or no
placeable speech at all for the currency, raises `CbToneUnavailable`. It is also a TypeError on
purpose -- the sealed builder catches only TypeError on its first family call and names the
failure on its retry, so the refusal goes through the builder's own door.

REFUSES (returns []) on an unknown tone side or direction, or too few bars.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from mt5desk.families import Signal
from mt5desk.family_event_reaction import family_event_reaction

DESK = Path(__file__).resolve().parents[1]
SPEECHES = DESK / "data" / "intelligence" / "central_banks" / "bis_speech_tone.jsonl"

DIRECTIONS = {"long": 1, "short": -1}
TONES = ("hawk", "dove")
BASES = ("level", "surprise")
#: Published days of the bank's own prior language a surprise is measured against.
SURPRISE_OBS = 20
#: The largest measured broker-time offset from UTC (summer). Adding it to a UTC instant gives a
#: bar label that is on or after that instant in both seasons.
BROKER_MAX_OFFSET_H = 3
#: `/review/r260624c.htm`, `/review/r970211c.pdf`, `/review/r970819.pdf`: six digits, YYMMDD.
_STAMP = re.compile(r"/review/r(\d{6})(?!\d)")
_EVENT_SYMBOL = "CB_TONE"

#: What the last load could not place, by reason. A shrinking sample is never silent.
LAST_DROPPED: dict[str, int] = {}


class CbToneUnavailable(LookupError, TypeError):
    """The recipe names a currency this host holds no placeable central-bank tone for."""


def published_on(url: str, delivered: str) -> pd.Timestamp | None:
    """The BIS publication DATE in the review URL, or None when it cannot be trusted."""
    m = _STAMP.search(str(url or ""))
    if m is None:
        return None
    try:
        pub = pd.Timestamp(year=int(m.group(1)[:2]) + (1900 if int(m.group(1)[:2]) >= 90 else 2000),
                           month=int(m.group(1)[2:4]), day=int(m.group(1)[4:6]), tz="UTC")
        day = pd.Timestamp(delivered, tz="UTC")
    except (TypeError, ValueError):
        return None
    return pub if pub >= day else None


@lru_cache(maxsize=4)
def _tone_days(path: str, mtime_ns: int) -> tuple[dict[str, pd.Series], dict[str, int]]:
    """{currency: net tone per PUBLICATION day} and what could not be placed."""
    dropped: dict[str, int] = {}
    acc: dict[tuple[str, pd.Timestamp], list[int]] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                dropped["unreadable_row"] = dropped.get("unreadable_row", 0) + 1
                continue
            pub = published_on(row.get("url", ""), row.get("date", ""))
            if pub is None:
                dropped["no_publication_stamp"] = dropped.get("no_publication_stamp", 0) + 1
                continue
            cell = acc.setdefault((str(row.get("currency") or ""), pub), [0, 0])
            cell[0] += int(row.get("hawk") or 0)
            cell[1] += int(row.get("dove") or 0)
    out: dict[str, dict[pd.Timestamp, float]] = {}
    for (ccy, pub), (hawk, dove) in acc.items():
        if hawk + dove == 0:              # no directional language is not neutral language
            dropped["no_directional_language"] = dropped.get("no_directional_language", 0) + 1
            continue
        out.setdefault(ccy, {})[pub] = (hawk - dove) / (hawk + dove)
    return {c: pd.Series(v).sort_index() for c, v in out.items()}, dropped


def tone_days(currency: str) -> pd.Series | None:
    """Net tone per publication day for one currency, or None when this host holds none."""
    global LAST_DROPPED
    try:
        mtime = SPEECHES.stat().st_mtime_ns
    except OSError:
        return None
    series, dropped = _tone_days(str(SPEECHES), mtime)
    LAST_DROPPED = dict(dropped)
    return series.get(str(currency).upper())


def tone_surprise(s: pd.Series, obs: int = SURPRISE_OBS) -> pd.Series:
    """Each published day's tone minus the mean of the `obs` published days BEFORE it."""
    prior = s.shift(1).rolling(int(obs), min_periods=int(obs)).mean()
    return (s - prior).dropna()


def event_times(currency: str, tone: str, min_abs: float,
                basis: str = "level") -> list[pd.Timestamp] | None:
    """Bar-frame instants from which each qualifying day is knowable; None = no input."""
    s = tone_days(currency)
    if s is None or s.empty:
        return None
    if basis == "surprise":
        s = tone_surprise(s)
    hit = s[s >= float(min_abs)] if tone == "hawk" else s[s <= -float(min_abs)]
    hit = hit[hit != 0.0]
    step = pd.Timedelta(days=1) + pd.Timedelta(hours=BROKER_MAX_OFFSET_H)
    return [ts + step for ts in hit.index]


def family_cb_tone_event(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    currency: str = "",
    tone: str = "hawk",
    min_abs: float = 0.0,
    basis: str = "level",
    direction: str = "long",
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    # THE RECIPE'S `direction` IS THE SIDE (as in `world_macro_state`): the sealed gauntlet
    # always passes side=1 and the forward clock passes the cell's own side, so honouring `side`
    # would make the two callers build different trades from one identity.
    del side
    flip = DIRECTIONS.get(str(direction))
    if (not currency or flip is None or tone not in TONES or basis not in BASES
            or float(min_abs) < 0):
        return []
    times = event_times(str(currency), str(tone), float(min_abs), str(basis))
    if times is None:
        raise CbToneUnavailable(
            f"no placeable central-bank tone for {currency} on this host "
            f"({SPEECHES.name} absent, or no speech of that currency carries a publication "
            "stamp); the input is missing, the cell is unjudged")
    events: list[dict[str, Any]] = [{"symbol": _EVENT_SYMBOL, "at": ts} for ts in times]
    out = family_event_reaction(
        df, events=events, symbol=_EVENT_SYMBOL, mode="drift", side=flip,
        hold_bars=int(hold_bars), atr_n=int(atr_n), stop_atr=float(stop_atr), rr=float(rr),
        ttl_bars=int(hold_bars), cooldown_bars=int(hold_bars), clock="bars")
    return [Signal(time=s.time, side=s.side, stop=s.stop, target=s.target, ttl_bars=s.ttl_bars,
                   tag=f"cb_tone_event:{str(currency).upper()}:{basis}:{tone}:{direction}",
                   trigger=s.trigger, wait_bars=s.wait_bars) for s in out]
