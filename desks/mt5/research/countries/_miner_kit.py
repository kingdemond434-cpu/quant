"""THE COUNTRY MINER KIT -- the event study, the series lead-lag and the calendar builders every
country pack's OWN miners share, so a pack's `miners.py` is its mechanics and not a copy of the
framework's statistics.

WHAT A PACK MINER IS (LAWS 5n). `country_lab.run_lab` runs the fifteen generic miners on every
pack and then the pack's own `MINERS: {name: callable(pack, ctx)}`. A pack miner knows something
the generic set cannot: WHICH dates are the country's own forced-flow clock (the fortnightly
petrol notification, the moon-sighting Eid, the Poya full moon, the wheat-duty switch, the LNG
cargo tender), WHICH executable symbol its mechanism reaches, and WHICH control tells the
mechanism from the weekday. This module gives those miners the same measurement the generic
miners use -- `country_lab.event_effect` with its matched weekday+hour control, its
randomised-date null and its adjacent-day placebo -- so a pack's finding is comparable with
every other pack's and is never a private statistic.

EVERY OUTCOME IS A RESULT. A missing tape is `ctx.note`d UNMEASURED by symbol; a study with too
few events is POORLY_MEASURED with the counts; a significant matched-control effect is a
DISCOVERY recorded through `ctx.record`, which is the ONE door into the registry (the compiler
reads discoveries; nothing here writes a store beside it). Dry-run contexts record nothing and
the result says so.
"""
from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from typing import Any

import numpy as np

from libs.research import country_lab as CL

OK, UNMEASURED = "ok", "UNMEASURED"
#: Event horizons in H1 bars a pack miner may ask for; a horizon beyond a session is a
#: multi-day question the daily miners own.
HORIZONS: dict[str, int] = {"intraday": 4, "session": 8, "overnight": 24}


# --------------------------------------------------------------------------- calendars
def month_days(start: date, end: date, days: Iterable[int]) -> list[date]:
    """Every (year, month, day) inside [start, end] for the given days of month; a day the
    month does not have (31 in April) lands on the month's last day -- named, not dropped."""
    wanted = sorted({int(d) for d in days if 1 <= int(d) <= 31})
    out: list[date] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        last = calendar.monthrange(y, m)[1]
        for d in wanted:
            day = date(y, m, min(d, last))
            if start <= day <= end:
                out.append(day)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def weekday_dates(start: date, end: date, weekday: int) -> list[date]:
    """Every date with `weekday` (Monday=0) inside [start, end]."""
    first = start + timedelta(days=(weekday - start.weekday()) % 7)
    out: list[date] = []
    d = first
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def next_business_day(day: date, closed: Iterable[int] = (5, 6)) -> date:
    off = set(closed)
    while day.weekday() in off:
        day += timedelta(days=1)
    return day


def shift(dates: Iterable[date], days: int) -> list[date]:
    return [d + timedelta(days=days) for d in dates]


def as_days(dates: Iterable[date]) -> np.ndarray:
    """dates -> datetime64[D], sorted and unique -- the shape `event_effect` reads."""
    vals = sorted({np.datetime64(d.isoformat(), "D") for d in dates})
    return np.asarray(vals, dtype="datetime64[D]")


def tape_span(bars: CL.Bars) -> tuple[date, date]:
    lo = np.datetime_as_string(bars.times[0].astype("datetime64[D]"))
    hi = np.datetime_as_string(bars.times[-1].astype("datetime64[D]"))
    return date.fromisoformat(str(lo)), date.fromisoformat(str(hi))


# --------------------------------------------------------------------------- the studies
def event_study(pack: Any, ctx: Any, *, name: str, symbols: Sequence[str],
                dates: Sequence[date] | np.ndarray, mechanism: str, actor: str,
                constraint: str, rationale: str, falsifier: str, source_id: str,
                required_data: Sequence[str], horizon: str = "intraday",
                hours: tuple[int, int] | None = None, timeframe: str = "H1",
                payload: Mapping[str, Any] | None = None, novelty: float = 0.55,
                confidence: float = 0.5) -> dict[str, Any]:
    """The event study a pack miner runs on ITS OWN dates, with the framework's controls.

    One `event_effect` per symbol; a significant matched-control effect becomes one discovery
    with the reading in its payload. The result carries every reading, measured or not, so a
    pass that found nothing still says which symbol it looked at and why it could not judge.
    """
    days = dates if isinstance(dates, np.ndarray) else as_days(dates)
    if days.size == 0:
        ctx.note(name, "no event dates could be built for this pack")
        return {"outcome": UNMEASURED, "miner": name, "why": "no event dates", "readings": []}
    eras = CL.era_masks
    readings: list[dict[str, Any]] = []
    for sym in symbols:
        if ctx.remaining_s() <= 0:
            ctx.note(name, f"budget spent before {sym}")
            break
        bars = ctx.bars(sym, timeframe)
        if bars is None:
            ctx.note(f"{name}:bars:{sym}", f"no {timeframe} tape on this box")
            continue
        try:
            masks = eras(pack, CL.bar_days(bars))
        except Exception:
            masks = {}
        res = CL.event_effect(bars, days, horizon=HORIZONS.get(horizon, 4), hours=hours,
                              rng=ctx.rng(f"{name}:{sym}"), eras=masks)
        res["symbol"] = sym
        readings.append(res)
    measured = [r for r in readings if r.get("verdict") == "MEASURED"]
    hits = [r for r in measured if r.get("significant")]
    n = 0
    for r in hits:
        did, created = ctx.record(
            mechanism=mechanism, source_id=source_id, source_type="calendar",
            actor=actor, constraint=constraint, economic_rationale=rationale,
            assets=[str(r["symbol"])], horizons=[horizon], sessions=["all"],
            regimes=["unconditional"], required_data=list(required_data),
            pit_requirements=["event date known before the window opens"],
            novelty=novelty, confidence=confidence, falsifier=falsifier,
            payload={"reading": r, "n_events": int(days.size), **dict(payload or {})})
        n += int(created or did != "dry-run")
    return {"outcome": OK if measured else UNMEASURED, "miner": name, "discoveries": n,
            "n_events": int(days.size), "n_symbols": len(readings), "measured": len(measured),
            "significant": len(hits),
            "why": "" if measured else "no instrument carried a measurable study",
            "readings": measured[:12]}


def series_lead(pack: Any, ctx: Any, *, name: str, series_name: str, symbols: Sequence[str],
                mechanism: str, actor: str, constraint: str, rationale: str, falsifier: str,
                source_id: str, horizon_days: int = 5,
                payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """A dated series against forward returns: the lead-lag reading with the framework's
    circular-shift null. UNMEASURED by name when the series is not on this box."""
    series = ctx.series(series_name)
    if series is None:
        ctx.note(f"{name}:series", f"{series_name}: not on this box")
        return {"outcome": UNMEASURED, "miner": name, "why": f"{series_name} absent",
                "readings": []}
    readings: list[dict[str, Any]] = []
    for sym in symbols:
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "D1") or ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"{name}:bars:{sym}", "no tape on this box")
            continue
        try:
            x, y = CL.align_daily(series, bars, horizon=horizon_days)
            res = CL.corr_with_null(x, y, rng=ctx.rng(f"{name}:{sym}"))
        except Exception as exc:
            ctx.note(f"{name}:{sym}", f"{type(exc).__name__}: {exc}")
            continue
        res = dict(res)
        res["symbol"] = sym
        readings.append(res)
    hits = [r for r in readings if r.get("significant")]
    n = 0
    for r in hits:
        did, created = ctx.record(
            mechanism=mechanism, source_id=source_id, source_type="dataset",
            actor=actor, constraint=constraint, economic_rationale=rationale,
            assets=[str(r["symbol"])], horizons=["multi_day"], sessions=["all"],
            regimes=["unconditional"], required_data=[series_name],
            pit_requirements=[f"{series_name} publication stamp"], novelty=0.6,
            confidence=0.45, falsifier=falsifier,
            payload={"reading": r, **dict(payload or {})})
        n += int(created or did != "dry-run")
    return {"outcome": OK if readings else UNMEASURED, "miner": name, "discoveries": n,
            "n_symbols": len(readings), "significant": len(hits), "readings": readings[:12],
            "why": "" if readings else "no tape carried the series"}


def seed_edges(pack: Any, ctx: Any, *, name: str, edges: Iterable[Mapping[str, Any]],
               mechanism_prefix: str, source_id: str) -> dict[str, Any]:
    """The pack's own transmission edges as HYPOTHESIS discoveries -- the map the law grants a
    region before any tape has been read (LAWS 5n: 'discovery rights and a transmission map
    into executable assets'). One discovery per edge, deduplicated by the registry."""
    n = 0
    rows: list[str] = []
    for edge in edges:
        if ctx.remaining_s() <= 0:
            break
        target = str(edge.get("target") or edge.get("asset") or "")
        if not target:
            continue
        rows.append(target)
        did, created = ctx.record(
            mechanism=f"{mechanism_prefix}:{CL._tok(edge.get('source') or target)}",
            source_id=source_id, source_type="transmission_seed",
            actor=str(edge.get("actor") or pack.name), constraint=str(edge.get("condition") or ""),
            economic_rationale=str(edge.get("mechanism") or ""), assets=[target],
            horizons=[str(edge.get("horizon_class") or "multi_day")], sessions=["all"],
            regimes=["unconditional"], required_data=[str(edge.get("source") or "")],
            pit_requirements=["source publication stamp"], novelty=0.4, confidence=0.3,
            falsifier=str(edge.get("falsifier") or ""),
            payload={"edge": dict(edge), "evidence": str(edge.get("evidence") or "HYPOTHESIS"),
                     "control": str(edge.get("control") or "")})
        n += int(created or did != "dry-run")
        ctx.seed_transmission(target=target, mechanism=str(edge.get("mechanism") or ""),
                              sign=str(edge.get("sign") or ""), horizon=str(edge.get("horizon")
                                                                            or ""))
    return {"outcome": OK if rows else UNMEASURED, "miner": name, "discoveries": n,
            "n_edges": len(rows), "targets": sorted(set(rows)),
            "why": "" if rows else "the pack declares no transmission edges"}
