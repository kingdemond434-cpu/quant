"""Where a market sits in a scheduled release's life -- per currency, not for the world at once.

A macro release is not "a high-volatility period". It is a sequence of qualitatively different
information processes, and every event sleeve on this desk is really a claim about ONE of them:

    PRE_EVENT        the tape thins and one-sides as inventory is pulled before a known unknown
    SHOCK            price discovery with no reliable mean; spreads gap, stops fill anywhere
    PRICE_DISCOVERY  the range is being found; direction is unreliable but the level is forming
    POST_EVENT_DRIFT the post-release move is EXTENDING -- information is still being absorbed
    POST_EVENT_REVERSAL the move is retracing -- the first print was liquidity, not information
    NORMALIZATION    spreads and ranges returning to their pre-event distribution
    NORMAL           no scheduled release is near

Collapsing those into one label throws away the distinction every one of those sleeves is about.

DRIFT AND REVERSAL ARE MEASURED, NOT ASSUMED. The clock alone cannot tell them apart -- they
occupy the same minutes after the same release. Which one holds is decided by comparing the move
since the release to the move made during the shock window: extending in the same direction is
drift, retracing past `REVERSAL_FRAC` of it is reversal. Naming a phase "REVERSAL" from a
stopwatch would be assuming the answer to the only interesting question.

PER CURRENCY, WHICH IS THE POINT. A Bank of England release is an event for GBP pairs and an
ordinary Tuesday for AUDJPY. The previous version of this classified the whole desk from the
nearest event on the calendar regardless of what it was about, so every instrument was in SHOCK
whenever anything anywhere printed. Each event's own currency scope comes from the calendar row.

IMPACT TIERS BOUND THE CLAIM. A Low-impact release does not create a shock phase; it creates a
footnote. Only Medium and High open the pre/shock windows, and the tier is carried on the state so
a consumer can require High.

SURPRISE IS NOT AVAILABLE AND THAT IS RECORDED, NOT PAPERED OVER. The desk's calendar vintages
carry `event_date`, `impact`, `forecast` and `previous` -- there is no `actual`, so the standard
surprise (actual - forecast) / sigma cannot be computed here. `forecast` versus `previous` gives
the EXPECTED change, which is a weaker and different thing, and it is reported under its own name
rather than passed off as surprise. The missing field is named in `gaps` so the acquisition task
is a task rather than a mystery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

PRE_EVENT = "PRE_EVENT"
SHOCK = "SHOCK"
PRICE_DISCOVERY = "PRICE_DISCOVERY"
POST_EVENT_DRIFT = "POST_EVENT_DRIFT"
POST_EVENT_REVERSAL = "POST_EVENT_REVERSAL"
NORMALIZATION = "NORMALIZATION"
NORMAL = "NORMAL"

PHASES = (PRE_EVENT, SHOCK, PRICE_DISCOVERY, POST_EVENT_DRIFT, POST_EVENT_REVERSAL,
          NORMALIZATION, NORMAL)

#: Window boundaries in minutes either side of the scheduled stamp. Whole minutes, and coarse:
#: a finer grid buys resolution the calendar's own timestamps cannot support (they are scheduled
#: times, not print times) and the admission test would discard it anyway.
PRE_MIN = 120
SHOCK_MIN = 15
DISCOVERY_MIN = 60
POST_MIN = 360
NORMALIZATION_MIN = 720

#: Retracement of the shock move that turns DRIFT into REVERSAL.
REVERSAL_FRAC = 0.5

#: Impact tiers that open a pre/shock window at all. A Low-impact print is a footnote.
TRADED_IMPACT = frozenset({"medium", "high"})


@dataclass(frozen=True)
class EventState:
    """One instrument's position in the nearest RELEVANT release's life."""

    phase: str
    #: Minutes to the next relevant release (positive) -- inf when none is scheduled.
    minutes_to_next: float
    #: Minutes since the last relevant release -- inf when none has happened.
    minutes_since_last: float
    impact: str = ""
    title: str = ""
    currencies: tuple[str, ...] = ()
    #: The release's own expected change, `forecast - previous`, when both parse as numbers.
    #: NOT a surprise: the desk records no `actual`. Named for what it is.
    expected_change: float | None = None
    #: Move during the shock window and since it, in whatever units the caller passed.
    shock_move: float | None = None
    move_since: float | None = None
    n_events_scoped: int = 0
    gaps: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"phase": self.phase,
                "minutes_to_next": (None if self.minutes_to_next == float("inf")
                                    else round(self.minutes_to_next, 2)),
                "minutes_since_last": (None if self.minutes_since_last == float("inf")
                                       else round(self.minutes_since_last, 2)),
                "impact": self.impact, "title": self.title,
                "currencies": list(self.currencies),
                "expected_change": self.expected_change,
                "shock_move": self.shock_move, "move_since": self.move_since,
                "n_events_scoped": self.n_events_scoped, "gaps": self.gaps}


def currencies_of(symbol: str, meta: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Which currencies a release must concern to be an event FOR THIS INSTRUMENT.

    Six-letter FX pairs carry two. Everything else answers to the currency it is quoted in, plus
    USD, because a dollar-quoted metal or index is repriced by a US release whatever else it is.
    """
    sym = str(symbol or "").upper()
    row = (meta or {}).get(sym) if isinstance(meta, dict) else None
    cls = str((row or {}).get("asset_class") or "")
    if cls in {"Forex", "Forex Exotics"} and len(sym) == 6 and sym.isalpha():
        return (sym[:3], sym[3:])
    quote = str((row or {}).get("currency_profit") or "").upper()
    out = {c for c in (quote, "USD") if c}
    return tuple(sorted(out)) if out else ("USD",)


def _row_currencies(row: dict) -> tuple[str, ...]:
    vals = row.get("symbols") or row.get("currency") or row.get("currencies") or ()
    if isinstance(vals, str):
        vals = [vals]
    out = {str(v).upper() for v in vals if v}
    return tuple(sorted(out))


def _num(v: Any) -> float | None:
    """Parse a calendar figure, tolerating the units the source writes them in."""
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    mult = 1.0
    if s.endswith("%"):
        s = s[:-1]
    elif s[-1:].upper() in {"K", "M", "B", "T"}:
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[s[-1].upper()]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def relevant(rows: Iterable[dict], symbol: str,
             meta: dict[str, Any] | None = None) -> list[dict]:
    """Calendar rows whose currency scope touches this instrument, and whose impact is traded.

    A row scoped "All" is kept: a G20 meeting is everyone's event. A row with no parseable stamp
    is dropped rather than guessed at.
    """
    want = set(currencies_of(symbol, meta))
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("impact") or "").strip().lower() not in TRADED_IMPACT:
            continue
        ccy = set(_row_currencies(row))
        if ccy and "ALL" not in ccy and not (ccy & want):
            continue
        out.append(row)
    return out


def classify(now: datetime, stamps: Sequence[datetime], symbol: str = "",
             rows: Sequence[dict] | None = None,
             shock_move: float | None = None, move_since: float | None = None,
             ) -> EventState:
    """Which phase `now` is in, given the release stamps already scoped to this instrument.

    `shock_move` and `move_since` are the instrument's own move during the shock window and since
    it. Without them the post-event phase cannot be split, and the state says POST_EVENT_DRIFT
    only when it has measured drift -- otherwise it reports PRICE_DISCOVERY, which is the honest
    description of "after the print, direction not yet established".
    """
    gaps: dict[str, str] = {}
    if rows is not None and rows and all("actual" not in r for r in rows):
        gaps["surprise"] = ("calendar vintages carry forecast and previous but no `actual`, so "
                            "(actual - forecast) cannot be computed; only the EXPECTED change is "
                            "available and it is reported under that name")
    if not stamps:
        return EventState(NORMAL, float("inf"), float("inf"), n_events_scoped=0, gaps=gaps)

    ahead = [s for s in stamps if s > now]
    behind = [s for s in stamps if s <= now]
    to_next = ((min(ahead) - now).total_seconds() / 60.0) if ahead else float("inf")
    since_last = ((now - max(behind)).total_seconds() / 60.0) if behind else float("inf")

    nearest = max(behind) if behind else (min(ahead) if ahead else None)
    row = None
    if rows and nearest is not None:
        for r in rows:
            st = r.get("_stamp")
            if isinstance(st, datetime) and st == nearest:
                row = r
                break
    impact = str((row or {}).get("impact") or "")
    title = str((row or {}).get("title") or "")[:120]
    ccy = _row_currencies(row) if row else ()
    fcast, prev = _num((row or {}).get("forecast")), _num((row or {}).get("previous"))
    expected = (fcast - prev) if (fcast is not None and prev is not None) else None

    common = dict(minutes_to_next=to_next, minutes_since_last=since_last, impact=impact,
                  title=title, currencies=ccy, expected_change=expected,
                  shock_move=shock_move, move_since=move_since,
                  n_events_scoped=len(stamps), gaps=gaps)

    if since_last <= SHOCK_MIN:
        return EventState(SHOCK, **common)
    if since_last <= DISCOVERY_MIN:
        return EventState(PRICE_DISCOVERY, **common)
    if since_last <= POST_MIN:
        # DRIFT vs REVERSAL, decided by the tape rather than by the clock.
        if shock_move is None or move_since is None or shock_move == 0.0:
            return EventState(PRICE_DISCOVERY, **common)
        ratio = move_since / shock_move
        if ratio <= -REVERSAL_FRAC:
            return EventState(POST_EVENT_REVERSAL, **common)
        if ratio > 0:
            return EventState(POST_EVENT_DRIFT, **common)
        return EventState(NORMALIZATION, **common)
    if since_last <= NORMALIZATION_MIN:
        return EventState(NORMALIZATION, **common)
    if to_next <= PRE_MIN:
        return EventState(PRE_EVENT, **common)
    return EventState(NORMAL, **common)


def parse_rows(rows: Iterable[dict]) -> list[dict]:
    """Attach a parsed UTC `_stamp` to each row, dropping any the calendar timestamps badly."""
    import pandas as pd

    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = next((row.get(k) for k in ("event_date", "date", "datetime", "timestamp")
                    if row.get(k)), None)
        if raw is None:
            continue
        try:
            ts = pd.to_datetime(raw, utc=True, errors="coerce")
        except (TypeError, ValueError):
            continue
        if ts is None or pd.isna(ts):
            continue
        out.append({**row, "_stamp": ts.to_pydatetime()})
    return out
