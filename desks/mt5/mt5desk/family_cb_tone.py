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

THE CORPUS IS THE BANKS' OWN PAGES, AND ONLY WHERE THEIR TERMS ALLOW IT (2026-11-10). The first
version of this family read the BIS speech extract. The BIS offers that extract "for
noncommercial purposes" (its download page, read 2026-11-10), so it may inform research and may
never be a trading input. This family does not open it. It reads
`data/intelligence/central_banks/official_speech_tone.jsonl`: one row per speech, fetched from the
issuing bank's own site, each carrying the `source` it came from and the `terms` verdict someone
read on that site. A row is used only when its `terms` is "permitted" AND its `source` is in
`PERMITTED_SOURCES` below -- two keys, so neither a mislabelled row nor an unregistered source
gets through alone. Everything else is dropped and counted in `LAST_DROPPED`
(`terms_not_permitted`, `source_not_registered`); with nothing left the family refuses by name
(`bis_terms_noncommercial`), it never falls back to the BIS file.

THE EVENT CLOCK IS PUBLICATION, NOT DELIVERY. Each row is keyed on `published_utc`, the day the
bank made the text public; a row without a readable one, or with one earlier than its delivery
date, cannot be placed and is dropped -- counted, never guessed. (Measured on the BIS copy
before it was set aside: publication trailed delivery by a median 2 days, 14 at the 90th
percentile and 52 at the 99th, so a clock keyed on delivery reads speeches before they existed.)

THE BAR CLOCK. Speeches are pooled per publication DAY, so a speech is taken as knowable from
00:00 UTC of the FOLLOWING day whatever hour it was posted. The bar index is broker time,
measured at UTC+2 in winter and UTC+3 in summer; the entry bar must be labelled at or after that
instant plus `BROKER_MAX_OFFSET_H` (3h), which is on or after the knowable instant in BOTH
seasons. It is at most one hour late in winter and never early.

TWO BASES, KEPT AS SEPARATE HYPOTHESES. The lexicon counts far more dovish than hawkish hits
(USD: 1,156 dovish published days against 280 hawkish), so the LEVEL's sign mostly says "a
speech happened". The SURPRISE basis reads each day against the same bank's own recent language
-- the mean of its previous `SURPRISE_OBS` published days, each day against its own past only --
which is the part a reader could not already have expected. (The USD counts quoted are from the
research copy; the permitted corpus is re-measured by the proposer's report on every pass.)

THE INPUT IS NAMED ON THE RECIPE (`currency`) and loaded HERE from the per-speech file
(`data/intelligence/central_banks/official_speech_tone.jsonl`), so the sweep, the sealed gauntlet's
`build_cell` and the forward clock rebuild the same signals from the same identity.

AN ABSENT INPUT IS A NAMED REFUSAL, NOT A CELL THAT NEVER FIRES (L1.28a): no tone file, or no
permitted, placeable speech at all for the currency, raises `CbToneUnavailable`. It is also a
TypeError on purpose -- the sealed builder catches only TypeError on its first family call and names the
failure on its retry, so the refusal goes through the builder's own door.

REFUSES (returns []) on an unknown tone side or direction, or too few bars.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from mt5desk.families import Signal
from mt5desk.family_event_reaction import family_event_reaction

DESK = Path(__file__).resolve().parents[1]
SPEECHES = DESK / "data" / "intelligence" / "central_banks" / "official_speech_tone.jsonl"

#: Sources whose OWN terms were read and allow reuse, with the clause. A source is added here by
#: a person who read its terms page, in a diff; a row's own `terms` label is necessary and not
#: sufficient. Read 2026-11-10 (Global data). NOT here, on purpose: the BIS extract, the SNB and
#: the BoE's general pages (noncommercial); the ECB and the BoJ (unverified); the RBA (its CC-BY
#: sentence does not name speeches).
PERMITTED_SOURCES: dict[str, str] = {
    "fed_board": "federalreserve.gov: \"information on Board's website is in the public domain "
                 "and may be copied and distributed without permission\" (citation requested)",
    "boc": "bankofcanada.ca: \"the Bank permits you to freely use, copy, distribute and "
           "transmit its website content\", with attribution and its request-rate limits",
}
TERMS_PERMITTED = "permitted"
#: The reason a host with no permitted corpus is parked under, by name.
NO_PERMITTED_CORPUS = "bis_terms_noncommercial"

DIRECTIONS = {"long": 1, "short": -1}
TONES = ("hawk", "dove")
BASES = ("level", "surprise")
#: Published days of the bank's own prior language a surprise is measured against.
SURPRISE_OBS = 20
#: The largest measured broker-time offset from UTC (summer). Adding it to a UTC instant gives a
#: bar label that is on or after that instant in both seasons.
BROKER_MAX_OFFSET_H = 3
_EVENT_SYMBOL = "CB_TONE"

#: What the last load could not use, by reason. A shrinking sample is never silent.
LAST_DROPPED: dict[str, int] = {}


class CbToneUnavailable(LookupError, TypeError):
    """The recipe names a currency this host holds no permitted, placeable tone for."""


def published_day(row: dict[str, Any]) -> pd.Timestamp | None:
    """The UTC day the bank made the speech public, or None when it cannot be trusted."""
    raw = str(row.get("published_utc") or "").strip()
    if not raw:
        return None
    try:
        pub = pd.Timestamp(raw)
        pub = (pub.tz_localize("UTC") if pub.tzinfo is None else pub.tz_convert("UTC")).normalize()
    except (TypeError, ValueError):
        return None
    delivered = str(row.get("delivered") or "").strip()
    if delivered:
        try:
            if pub < pd.Timestamp(delivered[:10], tz="UTC"):
                return None                   # public before it was spoken: a typo, not a clock
        except (TypeError, ValueError):
            return None
    return pub


def refusal(row: dict[str, Any]) -> str | None:
    """Why this row may not be a trading input; None when both keys turn."""
    if str(row.get("terms") or "") != TERMS_PERMITTED:
        return "terms_not_permitted"
    if str(row.get("source") or "") not in PERMITTED_SOURCES:
        return "source_not_registered"
    return None


@lru_cache(maxsize=4)
def _tone_days(path: str, mtime_ns: int) -> tuple[dict[str, pd.Series], dict[str, int]]:
    """{currency: net tone per PUBLICATION day} over permitted rows, and what was dropped."""
    dropped: dict[str, int] = {}

    def drop(why: str) -> None:
        dropped[why] = dropped.get(why, 0) + 1

    acc: dict[tuple[str, pd.Timestamp], list[int]] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                drop("unreadable_row")
                continue
            if not isinstance(row, dict):
                drop("unreadable_row")
                continue
            why = refusal(row)
            if why is not None:
                drop(why)
                continue
            pub = published_day(row)
            if pub is None:
                drop("no_publication_stamp")
                continue
            try:
                hawk, dove = int(row.get("hawk") or 0), int(row.get("dove") or 0)
            except (TypeError, ValueError):
                drop("unreadable_row")
                continue
            cell = acc.setdefault((str(row.get("currency") or "").upper(), pub), [0, 0])
            cell[0] += hawk
            cell[1] += dove
    out: dict[str, dict[pd.Timestamp, float]] = {}
    for (ccy, pub), (hawk, dove) in acc.items():
        if hawk + dove == 0:              # no directional language is not neutral language
            drop("no_directional_language")
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
            f"{NO_PERMITTED_CORPUS}: no permitted central-bank tone for {currency} on this host "
            f"({SPEECHES.name} absent, or it holds no speech of that currency from a source "
            "whose terms allow trading use); the BIS extract is noncommercial and is never "
            "read here, so the input is missing and the cell is unjudged")
    events: list[dict[str, Any]] = [{"symbol": _EVENT_SYMBOL, "at": ts} for ts in times]
    out = family_event_reaction(
        df, events=events, symbol=_EVENT_SYMBOL, mode="drift", side=flip,
        hold_bars=int(hold_bars), atr_n=int(atr_n), stop_atr=float(stop_atr), rr=float(rr),
        ttl_bars=int(hold_bars), cooldown_bars=int(hold_bars), clock="bars")
    return [Signal(time=s.time, side=s.side, stop=s.stop, target=s.target, ttl_bars=s.ttl_bars,
                   tag=f"cb_tone_event:{str(currency).upper()}:{basis}:{tone}:{direction}",
                   trigger=s.trigger, wait_bars=s.wait_bars) for s in out]
