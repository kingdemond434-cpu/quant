"""WHEN A SEAT'S STATE IS PUBLIC, ON THE BROKER'S CLOCK (DATA-46 audit fix, 2026-10-07).

`source_horizons.json` gives every state seat a `release` block: the real publication time and the
timezone it is published in. This module turns that into broker wall time (New York + 7h, so it
moves with US daylight saving exactly as the server does) and answers the one question a
session-transfer cell asks of every signal: was the state it conditions on PUBLIC at the signal's
bar (`available_at <= decision_time`), and which session after the release is this?

RELEASE KINDS
  weekly    a fixed weekday and local time in a named timezone (CFTC COT: Friday 15:30
            America/New_York; AAII: Thursday, unannounced hour, labelled 23:59 New York so a
            label is never earlier than the truth -- the rule #238 applies to unannounced
            releases). `calendar: cftc` reads #238's holiday/shutdown-aware label
            (`mt5desk.cot_frames.release_label`) where that module is present, else the nominal
            weekly instant; the source used is reported, never assumed.
  event     row-dated: each row carries its own release instant (central-bank decisions,
            calendar prints, filings). No schedule exists to gate on, so no transfer cell is
            minted from it until a release series is wired; reported, not approximated.
  observed  available when the desk observed it (swaps, microstructure, snapshots).
  calendar  known in advance (seasonality): nothing to wait for.

THE TRANSFER GATE. A cell `release_gate = "<seat>:<k>"` keeps a family signal at broker time t
only when, for the latest release r <= t of that seat:
  * k == 0: t lies in a broad session window (asia/london/ny) that CONTAINS r;
  * k >= 1: t lies in the k-th session window that STARTS after r (weekend days carry none);
  * the state has not decayed below `DECAY_FLOOR` of its strength:
    0.5 ** ((t - r) / decay_half_life_h) >= DECAY_FLOOR.
A bar before the first release knows nothing and keeps nothing. Nothing here moves a signal.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from libs.mining import source_horizon

#: Broker server time is New York wall time plus this many hours, all year.
BROKER_OFFSET_H = 7
#: A state is still in force while it keeps at least this share of its strength.
DECAY_FLOOR = 0.25
#: The broad sessions, in broker hours (identical to `mt5desk.family_call.SESSIONS`; a test pins
#: the two together so they cannot drift).
SESSION_WINDOWS: tuple[tuple[str, int, int], ...] = (("asia", 0, 8), ("london", 8, 16),
                                                     ("ny", 14, 22))
#: The transfer lags a scheduled seat may mint: its own session and the next three. A lag whose
#: window is empty for the seat's release (COT lands at 22:30 broker, after New York closes, so
#: it has no own-session window) or starts after the state has decayed is not minted.
TRANSFER_LAGS: tuple[int, ...] = (0, 1, 2, 3)
SCHEDULED_KINDS = ("weekly",)
KINDS = ("weekly", "event", "observed", "calendar")


class ReleaseClockUnavailable(RuntimeError):
    """The timezone database cannot convert this zone on this host."""


def wall(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    """A naive broker/local wall time (the bar index's own convention)."""
    return datetime(y, m, d, hh, mm, tzinfo=UTC).replace(tzinfo=None)


def _us_dst(local: datetime) -> bool:
    """US daylight saving (2007 rule) for a New York wall time: second Sunday of March 02:00 to
    first Sunday of November 02:00."""
    y = local.year
    mar = date(y, 3, 1)
    start = datetime.combine(mar + timedelta(days=(6 - mar.weekday()) % 7 + 7), time(2))
    nov = date(y, 11, 1)
    end = datetime.combine(nov + timedelta(days=(6 - nov.weekday()) % 7), time(2))
    return start <= local.replace(tzinfo=None) < end


def _zone(tz: str) -> Any:
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz)
    except Exception:
        return None


def to_utc(local: datetime, tz: str) -> datetime:
    """A wall time in `tz` -> the UTC instant. New York falls back to the US DST rule when the
    host has no timezone database (the Windows box without `tzdata`); any other zone refuses."""
    z = _zone(tz)
    if z is not None:
        return local.replace(tzinfo=z).astimezone(UTC)
    if tz == "UTC":
        return local.replace(tzinfo=UTC)
    if tz == "America/New_York":
        off = 4 if _us_dst(local) else 5
        return (local + timedelta(hours=off)).replace(tzinfo=UTC)
    raise ReleaseClockUnavailable(f"no timezone database entry for {tz!r} on this host")


def broker_wall(utc: datetime) -> datetime:
    """A UTC instant -> broker server wall time (naive), DST-aware through New York."""
    u = utc if utc.tzinfo else utc.replace(tzinfo=UTC)
    z = _zone("America/New_York")
    if z is not None:
        ny = u.astimezone(z).replace(tzinfo=None)
    else:
        naive = u.astimezone(UTC).replace(tzinfo=None)
        ny = naive - timedelta(hours=4)
        if not _us_dst(ny):
            ny = naive - timedelta(hours=5)
    return ny + timedelta(hours=BROKER_OFFSET_H)


def spec(seat: str) -> dict[str, Any] | None:
    decl = source_horizon.declared(seat)
    rel = (decl or {}).get("release")
    return dict(rel) if isinstance(rel, dict) else None


def scheduled(seat: str) -> bool:
    return str((spec(seat) or {}).get("kind") or "") in SCHEDULED_KINDS


def _cftc_label(friday: date) -> datetime | None:
    """#238's holiday/shutdown-aware COT label for the report week ending `friday`, in UTC."""
    try:
        from mt5desk.cot_frames import release_label
    except Exception:
        return None
    try:
        lab = release_label(datetime(friday.year, friday.month, friday.day, tzinfo=UTC))
        out: datetime = lab.to_pydatetime().astimezone(UTC)
        return out
    except Exception:
        return None


def calendar_source(seat: str) -> str:
    rel = spec(seat) or {}
    if rel.get("calendar") == "cftc":
        return "mt5desk.cot_frames" if _cftc_label(date(2026, 1, 2)) else "nominal_weekly"
    return "nominal_weekly" if rel.get("kind") == "weekly" else str(rel.get("kind") or "none")


def release_instants(seat: str, start: datetime, end: datetime) -> list[datetime]:
    """Every release of a scheduled seat whose broker wall time lies in [start, end], sorted."""
    rel = spec(seat) or {}
    if rel.get("kind") not in SCHEDULED_KINDS:
        return []
    tz = str(rel.get("tz") or "UTC")
    wd = int(rel["weekday"])
    hh, mm = (int(x) for x in str(rel.get("local") or "00:00").split(":"))
    d = (start - timedelta(days=9)).date()
    d += timedelta(days=(wd - d.weekday()) % 7)
    out: list[datetime] = []
    while d <= (end + timedelta(days=2)).date():
        utc = _cftc_label(d) if rel.get("calendar") == "cftc" else None
        if utc is None:
            utc = to_utc(datetime.combine(d, time(hh, mm)), tz)
        b = broker_wall(utc)
        if start - timedelta(days=9) <= b <= end:
            out.append(b)
        d += timedelta(days=7)
    return sorted(set(out))


def describe(seat: str) -> dict[str, Any]:
    """The seat's release, as declared and as the broker clock sees it (summer and winter)."""
    rel = spec(seat)
    if not rel:
        return {"kind": "UNDECLARED"}
    out: dict[str, Any] = {k: rel.get(k) for k in ("kind", "tz", "weekday", "local", "calendar")
                           if rel.get(k) is not None}
    if rel.get("kind") in SCHEDULED_KINDS:
        try:
            for label, probe in (("broker_summer", wall(2026, 7, 1)),
                                 ("broker_winter", wall(2026, 1, 5))):
                got = release_instants(seat, probe, probe + timedelta(days=7))
                out[label] = got[-1].strftime("%a %H:%M") if got else None
        except ReleaseClockUnavailable as exc:
            out["broker"] = f"UNMEASURED: {exc}"
        out["calendar_source"] = calendar_source(seat)
    return out


def _windows_from(day: date, n_days: int) -> list[tuple[datetime, datetime]]:
    out = []
    for i in range(n_days):
        d = day + timedelta(days=i)
        if d.weekday() >= 5:              # no broker session on Saturday or Sunday
            continue
        for _, lo, hi in SESSION_WINDOWS:
            base = datetime.combine(d, time(0))
            out.append((base + timedelta(hours=lo), base + timedelta(hours=hi)))
    return sorted(out)


def lag_window(release: datetime, lag: int) -> list[tuple[datetime, datetime]]:
    """The broker windows a transfer cell of `lag` sessions trades after `release`."""
    wins = _windows_from(release.date(), 10)
    if lag == 0:
        return [(max(lo, release), hi) for lo, hi in wins if lo <= release < hi]
    after = [w for w in wins if w[0] > release]
    return [after[lag - 1]] if len(after) >= lag else []


def mintable_lags(seat: str) -> tuple[int, ...]:
    """The lags worth a cell for this seat: non-empty in summer AND winter, and starting while the
    state still keeps DECAY_FLOOR of its strength. Deterministic: the table alone decides."""
    if not scheduled(seat) or max_age_h(seat) is None:
        return ()
    cap = float(max_age_h(seat) or 0.0)
    keep = []
    try:
        probes = [release_instants(seat, p, p + timedelta(days=7))
                  for p in (wall(2026, 7, 1), wall(2026, 1, 5))]
    except ReleaseClockUnavailable:
        return ()
    for lag in TRANSFER_LAGS:
        ok = True
        for got in probes:
            win = lag_window(got[-1], lag) if got else []
            if not win or (win[0][0] - got[-1]).total_seconds() / 3600.0 > cap:
                ok = False
        if ok:
            keep.append(lag)
    return tuple(keep)


def parse_gate(value: Any) -> tuple[str, int] | None:
    text = str(value if value is not None else "").strip()
    seat, _, k = text.rpartition(":")
    if not seat or not k.isdigit():
        return None
    return seat, int(k)


def max_age_h(seat: str) -> float | None:
    hl = (source_horizon.declared(seat) or {}).get("decay_half_life_h")
    if hl is None or float(hl) <= 0:
        return None
    return float(hl) * math.log(1.0 / DECAY_FLOOR, 2)


def decay_weight(seat: str, age_h: float) -> float | None:
    hl = (source_horizon.declared(seat) or {}).get("decay_half_life_h")
    if hl is None or float(hl) <= 0:
        return None
    return float(0.5 ** (max(age_h, 0.0) / float(hl)))


def refusal(value: Any) -> str | None:
    """Why a `release_gate` value cannot be applied honestly, or None."""
    got = parse_gate(value)
    if got is None:
        return f"release_gate={value!r}: expected '<seat>:<sessions after release>'"
    seat, lag = got
    if not scheduled(seat):
        return (f"release_gate={value!r}: seat {seat!r} has no scheduled release clock "
                f"(kind {(spec(seat) or {}).get('kind') or 'UNDECLARED'!r}); a transfer test "
                "needs the instant the state became public")
    if lag not in TRANSFER_LAGS:
        return f"release_gate={value!r}: lag {lag} is not one of {TRANSFER_LAGS}"
    if max_age_h(seat) is None:
        return f"release_gate={value!r}: seat {seat!r} declares no decay_half_life_h"
    return None


def _wall(t: Any) -> datetime | None:
    if t is None:
        return None
    try:
        import pandas as pd
        ts = pd.Timestamp(t)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)       # the bar index holds broker wall time
        out: datetime = ts.to_pydatetime()
        return out
    except Exception:
        return None


def gate(times: list[Any], value: Any) -> list[bool]:
    """For each broker-time stamp: does a `release_gate` cell keep a signal there?"""
    got = parse_gate(value)
    if got is None or refusal(value):
        return [False] * len(times)
    seat, lag = got
    walls = [_wall(t) for t in times]
    known = [w for w in walls if w is not None]
    if not known:
        return [False] * len(times)
    age_cap = float(max_age_h(seat) or 0.0)
    rel = release_instants(seat, min(known) - timedelta(hours=age_cap), max(known))
    out: list[bool] = []
    for w in walls:
        i = bisect_right(rel, w) if w is not None else 0
        if w is None or i == 0:
            out.append(False)
            continue
        r = rel[i - 1]
        if (w - r).total_seconds() / 3600.0 > age_cap:
            out.append(False)
            continue
        out.append(any(lo <= w < hi for lo, hi in lag_window(r, lag)))
    return out
