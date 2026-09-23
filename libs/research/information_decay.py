"""INFORMATION DECAY -- every input to the state vector carries its true age, and a weight
that says how much of it is still information.

THE ORDER THIS ANSWERS (principal, 2026-09-05): "every minute X_t = {market, macro, flows,
positioning, cross-asset, news, liquidity, execution, tail, regime}, but every input carries its
true age. Don't pretend weekly COT becomes new every minute. Information_j(t) = Value_j x
Decay_j(age_j) ... Then the allocator sees the freshest valid state every cycle."

WHAT WAS WRONG BEFORE. `state_vector_build` writes one `at` stamp for the whole vector, and
`pf_allocator` refuses the vector when THAT stamp is older than two hours. Inside the vector a
COT z-score read on Friday evening, a daily regime fit and a spread read from a tape that stopped
an hour ago all wear the same age -- the age of the file. The consumer cannot tell a fresh state
from a stale one because nothing on the input says when it was last true.

THE REGISTRY. One `InformationClass` per kind of input, each with the age at which half its
information is gone, the fastest interval at which recomputing it could see anything NEW, the
structural lag between the thing happening and the desk being able to know it, and the reason
those numbers are what they are. The reasons are the point: a half-life nobody can argue with is
a half-life nobody can correct.

THE SHAPES. Most classes decay exponentially in age (`0.5 ** (age / half_life)`): a bar's close
is half as informative one span later because a new bar has arrived and told the desk what the
old one could only forecast. Two classes are EPISODIC: a central-bank decision is fully in force
until the next meeting supersedes it, and a macro print is the state of that series until the
next print, after which it is a vintage rather than a reading. Those step to zero when superseded
and only fade between.

AGE IS MEASURED FROM AVAILABILITY, NEVER FROM THE EVENT. A COT report dated Tuesday is public on
Friday evening; its age on Saturday is one day, not four, and its age on Wednesday afternoon is
NEGATIVE -- it does not exist yet. A negative age is refused as a point-in-time violation rather
than clipped to zero, because clipping is exactly how a backtest reads Friday's report on
Wednesday and reports an edge. The convention is `libs.data.feature_store`'s: report_date +
`COT_RELEASE_LAG`, unless the row carries its own `available_time`.

TRUTHFUL CADENCE. `truthful_cadence(cls)` is the fastest interval at which a recompute can see
new information of that class. A minute solve over hourly bars is a minute solve over the SAME
HOUR, and this module says so rather than letting a 60-second timer look like 60 fresh readings.

Pure stdlib except for one constant borrowed from the feature store. No I/O, no network.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from libs.data.feature_store import COT_RELEASE_LAG
from libs.data.pit import revise as _pit_revise
from libs.data.pit import stamp as _pit_stamp

__all__ = [
    "REGISTRY",
    "STALE_WEIGHT",
    "InformationClass",
    "PITViolation",
    "age_of",
    "available_time_of",
    "decay",
    "information",
    "is_new_information",
    "stamp",
    "state_freshness",
    "truthful_cadence",
]

_MIN = 60.0
_HOUR = 3_600.0
_DAY = 86_400.0

#: Below this weight an input is STALE for the consumer's purposes: two half-lives gone for an
#: exponential class, or superseded for an episodic one. A quarter, because a state built from
#: inputs that are three-quarters forgotten is describing the past, and the consumer should be
#: told that rather than left to infer it from a file mtime.
STALE_WEIGHT = 0.25

EXPONENTIAL = "exponential"
#: A bar's information is dated from its CLOSE -- an open bar is a forecast, not a reading -- and
#: halves every span because the next close supersedes it. Same formula as exponential; the
#: separate name records the convention.
BAR = "bar"
#: In force until the next episode, then superseded: weight 1 before the expiry, 0 after.
STEP = "step"
#: The current reading of a series until the next print; fades in between (a month-old CPI is
#: half as informative because the next print will say whether it was the start of something),
#: and goes to zero once the next print exists -- at which point the old one is a vintage.
RELEASE = "release"


class PITViolation(ValueError):
    """Information dated after the moment it is being used at. Never clipped, always refused."""


@dataclass(frozen=True)
class InformationClass:
    """One kind of input and the honest arithmetic of its ageing."""

    name: str
    #: EXPONENTIAL/BAR: the age at which weight = 0.5. STEP/RELEASE: the typical interval to
    #: the next episode, used as the expiry when the caller does not know the real one.
    half_life_s: float
    #: The fastest interval at which recomputing could see NEW information of this class.
    cadence_s: float
    shape: str
    #: Structural lag between the thing happening (event_time) and the desk being able to know
    #: it. Zero for anything published at its own stamp.
    publication_lag_s: float
    #: WHY the half-life is what it is. Required, because a number without a reason is a number
    #: nobody can correct.
    why: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cls(name: str, half_life_s: float, cadence_s: float, shape: str, why: str,
         publication_lag_s: float = 0.0) -> InformationClass:
    return InformationClass(name, float(half_life_s), float(cadence_s), shape,
                            float(publication_lag_s), why)


#: THE REGISTRY. Every class states why. Ordered fastest to slowest so a reader sees the clock.
REGISTRY: dict[str, InformationClass] = {c.name: c for c in (
    _cls("tick", 10.0, 1.0, EXPONENTIAL,
         "a tick is the market's last word until the next one, and on a liquid Fusion feed the "
         "next one is seconds away; ten seconds without a print is already a thin market"),
    _cls("quote_spread", 60.0, 1.0, EXPONENTIAL,
         "the quoted spread is an execution condition; the venue re-quotes within seconds and a "
         "minute-old spread is the previous liquidity state, not this one"),
    _cls("tick_flow", 5.0 * _MIN, 60.0, EXPONENTIAL,
         "signed tick-volume imbalance is a flow READ over a window; what the last five minutes "
         "showed is half-gone five minutes later because the window has rolled past it"),
    _cls("bar_M1", 60.0, 60.0, BAR, "one span: the next close supersedes this one"),
    _cls("bar_M5", 5.0 * _MIN, 5.0 * _MIN, BAR, "one span: the next close supersedes this one"),
    _cls("bar_M15", 15.0 * _MIN, 15.0 * _MIN, BAR, "one span: the next close supersedes it"),
    _cls("bar_H1", _HOUR, _HOUR, BAR,
         "one span: the desk's own lake is hourly, so an hourly close is the finest reading it "
         "has and the next hour's close is the only thing that can replace it"),
    _cls("bar_H4", 4.0 * _HOUR, 4.0 * _HOUR, BAR, "one span: the next close supersedes it"),
    _cls("bar_D1", _DAY, _DAY, BAR, "one span: a daily regime fit is a daily object"),
    _cls("bar_W1", 7.0 * _DAY, 7.0 * _DAY, BAR, "one span: the next weekly close supersedes it"),
    _cls("yield", 15.0 * _MIN, 60.0, EXPONENTIAL,
         "a yield quote moves in seconds on the print and drifts in minutes between; the desk "
         "reads it as a level that feeds the dollar and gold, and fifteen minutes is how long a "
         "rates-driven move takes to be fully reflected in the FX and metals it drives"),
    _cls("liquidity_tape", 15.0 * _MIN, 60.0, EXPONENTIAL,
         "spread and activity percentiles from the tape describe the current session's "
         "execution conditions; rollover, news windows and session opens change them on a "
         "quarter-hour clock"),
    _cls("regime_fit", _HOUR, _HOUR, EXPONENTIAL,
         "the state-vector fits are refreshed on the hourly cycle and see one new bar an hour; "
         "a fit older than that is describing the previous bar's world"),
    _cls("news", 4.0 * _HOUR, 5.0 * _MIN, EXPONENTIAL,
         "a headline's surprise is priced within the session it lands in; four hours on, half "
         "of what it told the desk is already in the price and the rest is a narrative"),
    _cls("calendar_event", 6.0 * _HOUR, _HOUR, EXPONENTIAL,
         "where an instrument sits in a release's life (PRE_EVENT, SHOCK, DRIFT ...) is an "
         "hourly question; the phases themselves last hours"),
    _cls("swap", _DAY, _DAY, EXPONENTIAL,
         "the broker's overnight financing is re-quoted once a day at rollover, and the desk "
         "pays exactly one day of it per day held"),
    _cls("etf_flow", _DAY, _DAY, EXPONENTIAL,
         "GLD and its peers publish holdings once a day after the close; the flow the desk sees "
         "is yesterday's and tomorrow's file replaces it"),
    _cls("cot", 7.0 * _DAY, 7.0 * _DAY, EXPONENTIAL,
         "the CFTC reports positioning weekly; a report dated Tuesday is public Friday evening "
         "(the feature store's COT_RELEASE_LAG) and the next report is the only thing that can "
         "tell the desk whether the positioning it read has since unwound",
         publication_lag_s=COT_RELEASE_LAG.total_seconds()),
    _cls("macro_monthly", 30.0 * _DAY, 30.0 * _DAY, RELEASE,
         "a monthly print (CPI, NFP, PMI) is the state of its series until the next print; the "
         "value used at any moment is the VINTAGE available then -- a revision is a new row with "
         "its own available_time (libs.data.pit.revise), never an edit of the row the desk "
         "decided on"),
    _cls("macro_quarterly", 91.0 * _DAY, 91.0 * _DAY, RELEASE,
         "GDP and the quarterly national accounts print once a quarter and are revised for "
         "years; the same vintage rule as the monthly class, on a quarterly clock"),
    _cls("cb_decision", 42.0 * _DAY, 42.0 * _DAY, STEP,
         "a policy decision is fully in force until the next scheduled meeting supersedes it; "
         "six weeks is the modal FOMC/ECB/BoE interval, and the caller passes the real next "
         "meeting when the calendar knows it"),
)}


# ---------------------------------------------------------------------------- time handling
def _as_utc(t: datetime | str | float | int) -> datetime:
    """An aware UTC datetime from a datetime, an ISO string or epoch seconds. Naive is UTC, the
    parquet convention the rest of the desk follows."""
    if isinstance(t, datetime):
        dt = t
    elif isinstance(t, int | float):
        dt = datetime.fromtimestamp(float(t), tz=UTC)
    else:
        try:
            dt = datetime.fromisoformat(str(t))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"not a time: {t!r}") from exc
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def age_of(when: datetime | str | float | int, now: datetime | str | float | int | None = None
           ) -> float:
    """Seconds between `when` -- the AVAILABLE time of the information, or its publication time
    when nothing better is known -- and `now`. Refuses a negative age.

    Refused rather than clipped because a clipped negative age is the quiet form of lookahead:
    the row exists, it is dated in the future, and a consumer that reads it at weight 1.0 has
    used Friday's report on Wednesday.
    """
    t0 = _as_utc(when)
    t1 = _as_utc(now) if now is not None else datetime.now(tz=UTC)
    age = (t1 - t0).total_seconds()
    if age < 0:
        raise PITViolation(f"information available at {t0.isoformat()} used at "
                           f"{t1.isoformat()}: {-age:.0f}s before it existed")
    return age


def available_time_of(cls: str, event_time: datetime | str | float | int) -> datetime:
    """When information of this class about `event_time` became knowable, by the class's
    structural publication lag. COT: report date + Friday-evening release lag."""
    return datetime.fromtimestamp(
        _as_utc(event_time).timestamp() + _class(cls).publication_lag_s, tz=UTC)


def _class(cls: str) -> InformationClass:
    try:
        return REGISTRY[cls]
    except KeyError:
        raise KeyError(f"unknown information class {cls!r}; known: {sorted(REGISTRY)}") from None


# ----------------------------------------------------------------------------------- decay
def decay(cls: str, age_s: float, *, expiry_s: float | None = None) -> float:
    """Weight in [0, 1] of information of class `cls` at `age_s` seconds after it became
    available.

    `expiry_s` is the age at which the next episode arrived (the next meeting, the next print)
    for the STEP and RELEASE shapes; when the caller does not know it the class's typical
    interval stands in. Negative age is a PIT violation and is refused.
    """
    c = _class(cls)
    age = float(age_s)
    if age != age:                                             # NaN: no stamp, no weight
        return 0.0
    if age < 0:
        raise PITViolation(f"{cls}: age {age:.0f}s is negative -- information from the future")
    if c.shape in (EXPONENTIAL, BAR):
        return float(0.5 ** (age / c.half_life_s))
    expiry = float(expiry_s) if expiry_s is not None else c.half_life_s
    if age >= expiry:
        return 0.0                                             # superseded by the next episode
    if c.shape == STEP:
        return 1.0
    return float(0.5 ** (age / c.half_life_s))                 # RELEASE: fades, then vintage


def information(value: float, cls: str, age_s: float, *, expiry_s: float | None = None) -> float:
    """Information_j(t) = Value_j x Decay_j(age_j). A NaN value stays NaN: no reading is not a
    reading of zero."""
    v = float(value)
    if v != v:
        return v
    return v * decay(cls, age_s, expiry_s=expiry_s)


def truthful_cadence(cls: str) -> float:
    """The fastest interval, in seconds, at which recomputing this class can see anything new.

    A minute solve over hourly bars is a minute solve over the SAME HOUR: the bars class answers
    3600 here, so a consumer solving every 60s knows that 59 of its 60 solves read the same
    information, and the report says so instead of counting them as fresh.
    """
    return _class(cls).cadence_s


def is_new_information(cls: str, age_s: float, last_solve_age_s: float) -> bool:
    """Could a recompute now see information of this class that the previous solve could not?

    True when the two ages fall in different cadence intervals -- a new bar closed, a new
    report was published -- and False when both solves are reading the same interval.
    """
    cad = _class(cls).cadence_s
    return int(float(age_s) // cad) != int(float(last_solve_age_s) // cad)


def state_freshness(entries: Mapping[str, float | tuple[str, float]],
                    *, expiry_s: Mapping[str, float] | None = None) -> dict[str, dict[str, Any]]:
    """Per input: its class, age, weight, whether it is stale, and the cadence at which it can
    honestly be re-read.

    `entries` maps a name to `(class, age_s)`, or a class name straight to an age when the name
    IS the class. An age of NaN (an input with no stamp) is reported at weight 0 and stale --
    absence is not freshness.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, ent in entries.items():
        if isinstance(ent, tuple):
            cls, age = str(ent[0]), float(ent[1])
        else:
            cls, age = str(name), float(ent)
        c = _class(cls)
        exp = float(expiry_s[name]) if expiry_s and name in expiry_s else None
        w = decay(cls, age, expiry_s=exp)
        out[str(name)] = {
            "cls": cls, "age_s": age, "weight": round(w, 6), "stale": bool(w < STALE_WEIGHT),
            "half_life_s": c.half_life_s, "cadence_s": c.cadence_s, "shape": c.shape,
        }
    return out


# ----------------------------------------------------------------------------------- stamp
def stamp(row: Mapping[str, Any], cls: str, *, event_time: datetime | str | float | int | None,
          published_time: datetime | str | float | int | None,
          available_time: datetime | str | float | int | None = None,
          ingested_time: datetime | str | float | int | None = None,
          source: str | None = None, revision_of: str | None = None,
          revision_reason: str = "") -> dict[str, Any]:
    """A point-in-time-complete COPY of `row` for information class `cls`.

        event_time      when the thing happened (the class's clock: the report date, the print)
        published_time  when the producer made it public (None when the producer has no stamp)
        available_time  when THIS DESK could know it -- defaults to `ingested_time`, and is
                        REFUSED when earlier than `published_time`: nothing is knowable before
                        it is published, and a row that says otherwise is a backfill wearing a
                        live stamp
        ingested_time   when the desk took it in (now, by default)

    Delegates the base fields (source_version, payload_hash) to `libs.data.pit.stamp` so the
    census in `scripts/check_pit.py` counts these rows as stamped, and to `libs.data.pit.revise`
    when `revision_of` names the payload hash of the row this corrects -- the vintage rule: a
    revision is a new row whose availability is floored at the revision time.
    """
    c = _class(cls)
    now = _as_utc(ingested_time) if ingested_time is not None else datetime.now(tz=UTC)
    pub = _as_utc(published_time) if published_time is not None else None
    avail = _as_utc(available_time) if available_time is not None else now
    if pub is not None and avail < pub:
        raise PITViolation(f"{cls}: available_time {avail.isoformat()} is before published_time "
                           f"{pub.isoformat()} -- nothing is knowable before it is published")
    ev = _as_utc(event_time) if event_time is not None else None
    if ev is not None and pub is not None and pub < ev and c.publication_lag_s > 0:
        raise PITViolation(f"{cls}: published_time {pub.isoformat()} precedes event_time "
                           f"{ev.isoformat()} for a class with a publication lag")
    body: dict[str, Any] = {k: v for k, v in row.items()
                            if k not in ("available_time", "ingested_time", "source_version",
                                         "payload_hash")}
    body["information_class"] = cls
    body["half_life_s"] = c.half_life_s
    body["cadence_s"] = c.cadence_s
    body["event_time"] = ev.isoformat() if ev is not None else body.get("event_time")
    body["published_time"] = pub.isoformat() if pub is not None else None
    body["available_time"] = avail.isoformat()
    body["ingested_time"] = now.isoformat()
    src = source or str(row.get("source") or cls)
    if revision_of:
        return _pit_revise(body, revision_of=revision_of, reason=revision_reason or "revised",
                           source=src, now=now)
    return _pit_stamp(body, src, now=now)
