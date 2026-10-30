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

import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

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


def _row_currencies(row: dict[str, Any]) -> tuple[str, ...]:
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


def relevant(rows: Iterable[dict[str, Any]], symbol: str,
             meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Calendar rows whose currency scope touches this instrument, and whose impact is traded.

    A row scoped "All" is kept: a G20 meeting is everyone's event. A row with no parseable stamp
    is dropped rather than guessed at.

    AN ASSET-SCOPED ROW IS NEVER GLOBAL. A row carrying `instruments` (the Asia-native rows from
    `asia_schedule`) touches exactly those instruments, plus any instrument sharing one of its
    declared currencies -- and nothing else. Without this, a SHFE inventory release, which names
    copper and no currency, would have fallen through the "no currency means everyone" branch
    and put the whole book in SHOCK every Friday: the defect PART XVIII names ("a BOJ release is
    not automatically a EURUSD event").
    """
    want = set(currencies_of(symbol, meta))
    sym = str(symbol or "").upper()
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("impact") or "").strip().lower() not in TRADED_IMPACT:
            continue
        ccy = set(_row_currencies(row))
        inst = row.get("instruments")
        if isinstance(inst, (list, tuple)) and inst:
            if sym in {str(x).upper() for x in inst} or (ccy & want):
                out.append(row)
            continue
        if ccy and "ALL" not in ccy and not (ccy & want):
            continue
        out.append(row)
    return out


def classify(now: datetime, stamps: Sequence[datetime], symbol: str = "",
             rows: Sequence[dict[str, Any]] | None = None,
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

    common: dict[str, Any] = {
        "minutes_to_next": to_next, "minutes_since_last": since_last, "impact": impact,
        "title": title, "currencies": ccy, "expected_change": expected,
        "shock_move": shock_move, "move_since": move_since,
        "n_events_scoped": len(stamps), "gaps": gaps}

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


def parse_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
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


# =============================================================================================
# ASIA-NATIVE EVENT OBJECTS (directive PART XVIII; audit 2026-10-06 row 42, package P5)
# =============================================================================================
#
# WHY THESE ARE HERE AND NOT IN A SECOND EVENT ENGINE. The lifecycle above (PRE_EVENT -> SHOCK ->
# PRICE_DISCOVERY -> DRIFT/REVERSAL -> NORMALIZATION) was fed ONLY by ForexFactory calendar
# vintages, and that calendar does not carry the releases an Asian book is actually moved by:
# the CFETS central parity at 01:15 UTC, the Korean 10- and 20-day export prints, the KOSPI200
# second-Thursday expiry and its quadruple-witching months, the Tokyo gotobi fix, the SHFE
# Friday warehouse report, the NBS PMI, the LPR. Each of those is RULE-DERIVED here, so it enters
# the SAME lifecycle through the same `relevant` / `classify` door -- one event machine, more
# events.
#
# THE OBJECT IS MORE THAN A STAMP. Every Asia event also carries the information lifecycle the
# directive asks for: ANNOUNCED (the schedule is knowable) -> EXPECTATION (an expectation exists
# from the sensor's own history) -> RELEASED (the print is knowable) -> SURPRISE_MEASURED ->
# REVISED (a later vintage of the same period changed the value) -> DECAYING -> DECAYED. The
# market-phase lifecycle says where the TAPE is; this one says where the INFORMATION is.
#
# NOTHING IS INVENTED TO FILL A STAGE. A rule whose sensor is not collected yet carries
# `sensor_status: UNMEASURED: <who will deliver it>`, its expectation and surprise stay None,
# and consensus is UNMEASURED on every row because the desk holds no licensed consensus feed.
#
# FIELD NAMES ARE THE UNIVERSAL SENSOR CONTRACT'S (mandate 2026-10-06 section 2.5): dataset_id,
# observation_id, entity, geography, metric, value, unit, event_time, scheduled_time,
# publication_time, knowable_at, expected_value, consensus, raw_surprise, surprise_z,
# revision_of, revision_delta, measurement_uncertainty, provenance_hash -- so the adapter the
# world-sensor thread is building is a pure mapping, not a re-derivation.

ASIA_DATASET_ID = "asia_events"

ANNOUNCED = "ANNOUNCED"
EXPECTATION = "EXPECTATION"
RELEASED = "RELEASED"
SURPRISE_MEASURED = "SURPRISE_MEASURED"
REVISED = "REVISED"
DECAYING = "DECAYING"
DECAYED = "DECAYED"
INFO_STAGES = (ANNOUNCED, EXPECTATION, RELEASED, SURPRISE_MEASURED, REVISED, DECAYING, DECAYED)

#: A print counts as THIS event's release when it became knowable within this window of the
#: scheduled time. Wide at the back because a customs press page is often parsed hours late; a
#: point outside it belongs to another event and is never pulled in to fill this one.
RELEASE_MATCH_BEFORE = timedelta(hours=2)
RELEASE_MATCH_AFTER = timedelta(days=3)
#: Prior prints the own-history expectation averages, and prior surprises the z needs.
EXPECTATION_N = 6
SURPRISE_MIN_N = 5
#: Below this share of its information left, a released event is DECAYED.
DECAYED_WEIGHT = 0.1

UNMEASURED_CONSENSUS = ("UNMEASURED: the desk holds no licensed consensus feed for Asian "
                        "releases; the expectation is the sensor's own trailing mean, labelled")


@dataclass(frozen=True)
class AsiaEventRule:
    """One rule-derived Asian release: when it happens, what it is about, and its sensor."""

    rule: str
    kind: str
    title: str
    country: str
    calendar: str
    hour_utc: int
    minute_utc: int
    impact: str
    currencies: tuple[str, ...]
    instruments: tuple[str, ...]
    commodities: tuple[str, ...]
    #: `<axis doc stem>:<series key>` of the hard series that carries the print, or "".
    sensor: str
    #: "BOUND" when `sensor` names a collected series, else "UNMEASURED: <who delivers it>".
    sensor_status: str
    unit: str
    decay_halflife_h: float
    schedule_note: str


ASIA_EVENT_RULES: tuple[AsiaEventRule, ...] = (
    AsiaEventRule(
        "cn_cfets_fix", "fixing", "CFETS USDCNY central parity", "CN", "cn_open", 1, 15,
        "medium", ("CNH", "CNY"), ("USDCNH",), (), "", (
            "UNMEASURED: the fix history and its model-implied surprise are package P3 "
            "(asia_parser / cn_official_tables); the generic parser keeps one day"),
        "CNY per USD", 6.0,
        "09:15 Beijing = 01:15 UTC on every mainland open day (countries.cn.pack closures)"),
    AsiaEventRule(
        "cn_lpr", "policy", "PBOC loan prime rate", "CN", "cn_lpr", 1, 15, "high",
        ("CNH", "CNY"), ("USDCNH", "CHINAH", "HK50"), (), "", (
            "UNMEASURED: LPR values are not parsed (pboc pages are landing pages, package P3)"),
        "percent", 48.0, "the 20th at 01:15 UTC, rolled forward off mainland closures"),
    AsiaEventRule(
        "cn_nbs_pmi", "pmi", "NBS official manufacturing PMI", "CN", "month_last", 1, 30,
        "high", ("CNH", "CNY"),
        ("USDCNH", "AUDUSD", "NZDUSD", "XCUUSD", "CHINAH", "HK50", "AUS200"),
        ("copper", "iron_ore"), "", (
            "UNMEASURED: NBS easyquery PMI internals are package P3 (cn_official_tables)"),
        "index", 72.0,
        "09:30 Beijing = 01:30 UTC on the last calendar day of the month (NBS publishes on "
        "weekends too); holiday shifts announced by NBS are not modelled"),
    AsiaEventRule(
        "shfe_weekly_inventory", "inventory", "SHFE weekly warehouse stocks", "CN", "shfe_friday",
        7, 30, "medium", (), ("XCUUSD",), ("copper", "aluminium", "zinc", "nickel"), "", (
            "UNMEASURED: SHFE weekly warehouse parser is package P2 (free_stack); the vault "
            "holds the dataview.html JavaScript shell only"),
        "tonnes", 72.0, "Friday after the 15:00 Beijing close (~07:30 UTC) on mainland open days"),
    AsiaEventRule(
        "kr_exports_10d", "trade", "Korea customs 1-10 day exports", "KR", "kr_day11", 0, 0,
        "medium", ("KRW",), ("USDKRW",), ("semiconductors",),
        "alt_kr_exports_early:daily_avg_yoy.value", "BOUND", "percent y/y", 96.0,
        "the 11th (next Korean business day if closed), 09:00 KST = 00:00 UTC"),
    AsiaEventRule(
        "kr_exports_20d", "trade", "Korea customs 1-20 day exports", "KR", "kr_day21", 0, 0,
        "medium", ("KRW",), ("USDKRW",), ("semiconductors",),
        "alt_kr_exports_early:daily_avg_yoy.value", "BOUND", "percent y/y", 96.0,
        "the 21st (next Korean business day if closed), 09:00 KST = 00:00 UTC"),
    AsiaEventRule(
        "kr_kospi200_expiry", "expiry", "KOSPI200 futures/options expiry", "KR", "kr_expiry",
        6, 20, "medium", ("KRW",), ("USDKRW",), (), "", (
            "UNMEASURED: KRX derivatives OI is package P6 (countries/kr data plane)"),
        "contracts", 24.0,
        "second Thursday 15:20 KST = 06:20 UTC, preceding business day on a holiday; "
        "March/June/September/December are quadruple witching (impact high)"),
    AsiaEventRule(
        "jp_gotobi_fix", "fixing", "Tokyo gotobi 09:55 fix", "JP", "jp_gotobi", 0, 55,
        "medium", (), ("USDJPY",), (), "", (
            "UNMEASURED: no fix-flow sensor exists; the event is a mechanical-flow clock"),
        "JPY per USD", 6.0,
        "09:55 JST = 00:55 UTC on effective gotobi days (mt5desk.flowcal when available)"),
)
ASIA_RULES_BY_ID: dict[str, AsiaEventRule] = {r.rule: r for r in ASIA_EVENT_RULES}


def _weekend(day: date) -> bool:
    return day.weekday() >= 5


def _default_gotobi(day: date) -> bool:
    """5/10/15/20/25/30 or month end, brought back to the prior weekday. Holidays unknown."""
    if _weekend(day):
        return False
    probe = day
    for _ in range(5):
        nxt = probe + timedelta(days=1)
        if probe.day % 5 == 0 or nxt.month != probe.month:
            return True
        probe = nxt
        if not _weekend(probe):
            break
    return False


def _roll_forward(day: date, closed: Callable[[date], bool]) -> date:
    for _ in range(14):
        if not closed(day):
            return day
        day += timedelta(days=1)
    return day


def _roll_back(day: date, closed: Callable[[date], bool]) -> date:
    for _ in range(14):
        if not closed(day):
            return day
        day -= timedelta(days=1)
    return day


def _second_thursday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(3 - first.weekday()) % 7 + 7)


def _dates_for(rule: AsiaEventRule, start: date, end: date,
               cal: Mapping[str, Callable[[date], bool]]) -> list[tuple[date, dict[str, Any]]]:
    """Every scheduled day of `rule` inside [start, end], with per-row extras."""
    cn_closed = cal.get("cn_closed", _weekend)
    kr_closed = cal.get("kr_closed", _weekend)
    gotobi = cal.get("jp_gotobi", _default_gotobi)
    out: list[tuple[date, dict[str, Any]]] = []
    months: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        y, m = (y + (m == 12), 1 if m == 12 else m + 1)
    if rule.calendar in ("cn_open", "shfe_friday", "jp_gotobi"):
        d = start
        while d <= end:
            hit = ((rule.calendar == "cn_open" and not cn_closed(d))
                   or (rule.calendar == "shfe_friday" and d.weekday() == 4 and not cn_closed(d))
                   or (rule.calendar == "jp_gotobi" and gotobi(d)))
            if hit:
                out.append((d, {}))
            d += timedelta(days=1)
        return out
    for y, m in months:
        if rule.calendar == "cn_lpr":
            d = _roll_forward(date(y, m, 20), cn_closed)
            extra: dict[str, Any] = {}
        elif rule.calendar == "month_last":
            d = date(y + (m == 12), 1 if m == 12 else m + 1, 1) - timedelta(days=1)
            extra = {}
        elif rule.calendar in ("kr_day11", "kr_day21"):
            d = _roll_forward(date(y, m, 11 if rule.calendar == "kr_day11" else 21), kr_closed)
            extra = {}
        elif rule.calendar == "kr_expiry":
            nominal = _second_thursday(y, m)
            d = _roll_back(nominal, kr_closed)
            qw = m in (3, 6, 9, 12)
            extra = {"quadruple_witching": qw, "nominal_date": nominal.isoformat(),
                     "holiday_collision": d != nominal}
            if qw:
                extra["impact"] = "high"
        else:
            continue
        if start <= d <= end:
            out.append((d, extra))
    return out


def asia_schedule(start: date, end: date,
                  calendars: Mapping[str, Callable[[date], bool]] | None = None,
                  rules: Sequence[AsiaEventRule] = ASIA_EVENT_RULES) -> list[dict[str, Any]]:
    """Calendar-shaped rows for every rule-derived Asian release in [start, end].

    `calendars` supplies the desk's own closure tables (`cn_closed`, `kr_closed`, `jp_gotobi`);
    without them weekends are the only closures, and every row says so in `calendar_quality`
    rather than passing a weekend-only calendar off as the exchange's.
    """
    cal = dict(calendars or {})
    out: list[dict[str, Any]] = []
    for rule in rules:
        quality = ("desk_tables" if any(k in cal for k in ("cn_closed", "kr_closed", "jp_gotobi"))
                   else "weekends_only")
        for d, extra in _dates_for(rule, start, end, cal):
            at = datetime(d.year, d.month, d.day, rule.hour_utc, rule.minute_utc, tzinfo=UTC)
            row: dict[str, Any] = {
                "event_id": f"{rule.rule}:{d.isoformat()}", "rule": rule.rule,
                "kind": rule.kind, "title": rule.title, "country": rule.country,
                "event_date": at.isoformat(), "scheduled_time": at.isoformat(),
                "impact": rule.impact, "currency": list(rule.currencies),
                "instruments": list(rule.instruments), "commodities": list(rule.commodities),
                "sensor": rule.sensor, "sensor_status": rule.sensor_status, "unit": rule.unit,
                "decay_halflife_h": rule.decay_halflife_h, "schedule_basis": "rule-derived",
                "schedule_note": rule.schedule_note, "calendar_quality": quality,
                "asia_native": True}
            row.update(extra)
            out.append(row)
    out.sort(key=lambda r: (r["event_date"], r["rule"]))
    return out


def _ts(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _arrival(p: Mapping[str, Any]) -> datetime | None:
    """When a sensor point became knowable: a revision arrives at its own revision time."""
    a = _ts(p.get("available_time"))
    r = _ts(p.get("revision_time"))
    if a is None:
        return r
    return max(a, r) if r is not None else a


def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def event_lifecycle(row: Mapping[str, Any], now: datetime,
                    sensor_points: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """The information lifecycle of one Asian release AS KNOWABLE AT `now`.

    `sensor_points` is the bound series' points (`d`, `v`, `available_time`, optional
    `revision_time` / `vintage_id`), exactly as the axis door publishes them. Only points
    knowable at `now` are read, so the object at `now` never uses a later vintage.
    """
    sched = _ts(row.get("scheduled_time") or row.get("event_date"))
    halflife = float(row.get("decay_halflife_h") or 24.0)
    known: list[tuple[datetime, Mapping[str, Any]]] = []
    for p in sensor_points or ():
        t = _arrival(p)
        v = p.get("v", p.get("value"))
        if t is None or t > now or not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if not math.isfinite(float(v)):
            continue
        known.append((t, p))
    known.sort(key=lambda x: x[0])
    first_print: dict[str, tuple[datetime, Mapping[str, Any]]] = {}
    for t, p in known:
        first_print.setdefault(str(p.get("d") or t.date().isoformat()), (t, p))
    firsts = sorted(first_print.values(), key=lambda x: x[0])

    release: tuple[datetime, Mapping[str, Any]] | None = None
    if sched is not None:
        for t, p in firsts:
            if sched - RELEASE_MATCH_BEFORE <= t <= sched + RELEASE_MATCH_AFTER:
                release = (t, p)
                break
    cut = release[0] if release is not None else (sched or now)
    prior = [float(p.get("v", p.get("value"))) for t, p in firsts if t < cut]
    expected = (sum(prior[-EXPECTATION_N:]) / len(prior[-EXPECTATION_N:])
                if len(prior) >= 2 else None)
    past_surprises: list[float] = []
    for k in range(2, len(prior)):
        base = prior[max(0, k - EXPECTATION_N):k]
        past_surprises.append(prior[k] - sum(base) / len(base))

    value = None if release is None else float(release[1].get("v", release[1].get("value")))
    raw = (value - expected) if (value is not None and expected is not None) else None
    sd = None
    if len(past_surprises) >= SURPRISE_MIN_N:
        mu = sum(past_surprises) / len(past_surprises)
        var = sum((x - mu) ** 2 for x in past_surprises) / (len(past_surprises) - 1)
        sd = math.sqrt(var) if var > 0 else None
    z = (raw / sd) if (raw is not None and sd) else None

    revision_of = revision_delta = None
    latest_value = value
    if release is not None:
        period = str(release[1].get("d") or "")
        later = [(t, p) for t, p in known if str(p.get("d") or "") == period and t > release[0]]
        if later:
            lv = float(later[-1][1].get("v", later[-1][1].get("value")))
            if value is not None and lv != value:
                revision_of = str(release[1].get("vintage_id") or f"{row.get('event_id')}:first")
                revision_delta = lv - value
                latest_value = lv

    pub = release[0] if release is not None else None
    anchor = pub or sched
    age_h = ((now - anchor).total_seconds() / 3600.0) if anchor is not None else None
    weight = (0.5 ** (age_h / halflife)) if (age_h is not None and age_h >= 0) else None
    if sched is not None and now < sched:
        stage = EXPECTATION if expected is not None else ANNOUNCED
    elif weight is not None and weight < DECAYED_WEIGHT:
        stage = DECAYED
    elif revision_of is not None:
        stage = REVISED
    elif age_h is not None and age_h > halflife:
        stage = DECAYING
    elif raw is not None:
        stage = SURPRISE_MEASURED
    else:
        stage = RELEASED

    knowable = pub or sched
    vintage_ids = [str(p.get("vintage_id") or "") for _t, p in known]
    obs_id = _hash([row.get("event_id"), stage, latest_value, revision_delta])[:24]
    return {
        "dataset_id": ASIA_DATASET_ID, "observation_id": obs_id,
        "event_id": row.get("event_id"), "rule": row.get("rule"), "kind": row.get("kind"),
        "entity": row.get("title"), "geography": row.get("country"),
        "asset_domain": "fx" if row.get("currency") else "commodity",
        "metric": row.get("sensor") or row.get("rule"), "unit": row.get("unit"),
        "value": latest_value, "first_value": value,
        "event_time": (str(release[1].get("d")) if release is not None else None),
        "scheduled_time": sched.isoformat() if sched else None,
        "publication_time": pub.isoformat() if pub else None,
        "knowable_at": knowable.isoformat() if knowable is not None else None,
        "expected_value": expected,
        "expectation_basis": (f"own trailing mean of {min(len(prior), EXPECTATION_N)} prior "
                              "first prints" if expected is not None else
                              "UNMEASURED: fewer than 2 prior prints of the bound sensor"),
        "consensus": None, "consensus_status": UNMEASURED_CONSENSUS,
        "raw_surprise": raw, "surprise_z": z,
        "surprise_basis": (f"raw / sd of {len(past_surprises)} prior own-history surprises"
                           if z is not None else "UNMEASURED: no release matched or fewer than "
                           f"{SURPRISE_MIN_N} prior surprises"),
        "revision_of": revision_of, "revision_delta": revision_delta,
        "measurement_uncertainty": sd,
        "provenance_hash": _hash([row.get("event_id"), row.get("sensor"), vintage_ids]),
        "stage": stage, "decay_halflife_h": halflife,
        "decay_weight": None if weight is None else round(weight, 6),
        "age_h": None if age_h is None else round(age_h, 3),
        "sensor": row.get("sensor") or None, "sensor_status": row.get("sensor_status"),
        "scope": {"currencies": list(row.get("currency") or []),
                  "instruments": list(row.get("instruments") or []),
                  "commodities": list(row.get("commodities") or [])},
        "impact": row.get("impact"),
        **({"quadruple_witching": row["quadruple_witching"]}
           if "quadruple_witching" in row else {}),
        "calendar_quality": row.get("calendar_quality"),
        "schedule_note": row.get("schedule_note"),
    }


def asia_event_objects(now: datetime, rows: Sequence[Mapping[str, Any]],
                       sensors: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
                       ) -> list[dict[str, Any]]:
    """One lifecycle object per scheduled row; `sensors` maps a rule's `sensor` to its points."""
    sensors = sensors or {}
    return [event_lifecycle(r, now, sensors.get(str(r.get("sensor") or "")) or ())
            for r in rows]
