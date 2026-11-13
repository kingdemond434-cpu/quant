"""THE SCHEDULED-RELEASE ENTRY FENCE for the E8 gold lane -- default OFF, behind a data flag.

WHY (2026-10-29). On 2026-10-02 the london_am sell-stop filled at 12:24:52Z with a 19-pt stop,
five minutes before the 12:30Z Employment Situation print. The print gapped the market through
the stop (Fusion tape: ask 4190.28 -> 4216.54 in one tick, spread to 605 pts) and the position
closed at 4219.45 against a 4196.45 stop: +1.23R of slip, a -2.23R trade on a 1R budget.
`calendar_us.blackout` existed and nothing live imported it.

WHAT IT DOES WHEN ON. Inside [release - pre_min, release + post_min] of a TIER1 release:
no new bracket is placed, no dropped leg is re-sent, and any of this lane's RESTING entry legs
is cancelled (a bracket armed at 10:00Z and left resting into 12:30Z is exactly the 10-02 case;
a placement-only fence would not have stopped it). Open positions and their stops are never
touched. Every refusal is billed (rail `e8_news_fence`, RAIL_BLOCKED, with the risk held back).

WHY IT IS OFF. Rule 1: a risk reduction must prove it raises robust forward E[log W]. The
measurement of 2026-10-29 (patch README, e8_news_fence/v1) found ONE E8 trade whose life spanned
a tier-1 release in the calendar, and the calendar holds no CPI, PPI, FOMC, PCE or GDP dates for
Sep/Oct 2026 -- so the comparison is UNMEASURED, not clean. While OFF the fence runs in SHADOW:
each window or resting leg it WOULD have refused is journalled (status SHADOW_FENCE) with its
risk, so the evidence that decides the flag accrues on the lane's own record (two-sided: the bill
shows what it would have held back, the exits show what it would have saved).

THE FLAG. `desks/mt5/data/E8_NEWS_FENCE.json`:
    {"enabled": true, "pre_min": 15, "post_min": 15}
Absent -> OFF with the defaults. Unreadable or malformed (UTF-16, a window outside 0..240 min,
1e999) -> OFF, and `why` says so; the RED check in scripts/check_news_fence_liveness.py reports
it. A blind calendar (a month the table cannot see, any day of an absent year) or an error in the
verdict FAILS OPEN when ON: nothing is blocked, calendar_ok/error are published, and the liveness
check goes RED (v2; v1 failed closed for the whole day out of year and open in year). Windows are arguments, not constants fitted
to one afternoon (calendar_us docstring).
"""
from __future__ import annotations

import calendar
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from mt5desk.calendar_us import TIER1, Release, blackout, releases

DESK = Path(__file__).resolve().parents[1]
FLAG = DESK / "data" / "E8_NEWS_FENCE.json"
RAIL = "e8_news_fence"
SHADOW_STATUS = "SHADOW_FENCE"
DEFAULT_PRE_MIN = 15
DEFAULT_POST_MIN = 15
#: A window wider than this is a typo, not a parameter (and 1e999 / 10**12 must never reach
#: int() or timedelta): the flag is then MALFORMED and reads OFF.
MAX_WINDOW_MIN = 240
#: Families published every month; a month with none of them in the table is a calendar GAP.
#: FOMC and its minutes meet eight times a year, so a month without them is not evidence.
MONTHLY = ("NFP", "CPI", "PPI", "PCE", "GDP")


@dataclass(frozen=True)
class FenceVerdict:
    enabled: bool
    in_window: bool                      # a known tier-1 release is inside the window now
    release: str | None
    why: str
    calendar_ok: bool = True             # False: the table cannot see this month (fails OPEN)
    uncovered: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None             # the flag or the verdict itself failed (fails OPEN)

    @property
    def blocks(self) -> bool:
        """True only when enabled AND a KNOWN release is inside the window. A blind calendar or
        an error never blocks (fail open, v2): it publishes calendar_ok/error and the liveness
        check goes RED, so a gap costs a release, never a whole day of the book."""
        return self.enabled and self.in_window

    @property
    def would_block(self) -> bool:
        """What it would refuse if it were on -- the shadow bill when it is off."""
        return self.in_window

    def as_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "in_window": self.in_window, "blocks": self.blocks,
                "release": self.release, "why": self.why, "calendar_ok": self.calendar_ok,
                "uncovered": list(self.uncovered), "error": self.error}


def _minutes(doc: dict[str, Any], key: str, default: int) -> int:
    v = doc.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{key} is not a number")
    if isinstance(v, float) and not math.isfinite(v):
        raise ValueError(f"{key} is not finite")
    if not 0 <= v <= MAX_WINDOW_MIN:
        raise ValueError(f"{key} outside 0..{MAX_WINDOW_MIN}")
    return int(v)


def read_flag(path: Path | None = None) -> tuple[bool, int, int, str]:
    """(enabled, pre_min, post_min, why). Absent or bad -> OFF; NEVER raises (any exception,
    a UTF-16 file or a 1e999 window included, reads OFF with its reason)."""
    p = FLAG if path is None else path
    try:
        if not p.exists():
            return False, DEFAULT_PRE_MIN, DEFAULT_POST_MIN, f"no {p.name}: fence OFF (default)"
        doc = json.loads(p.read_text("utf-8-sig"))
        if not isinstance(doc, dict):
            raise ValueError("not an object")
        pre = _minutes(doc, "pre_min", DEFAULT_PRE_MIN)
        post = _minutes(doc, "post_min", DEFAULT_POST_MIN)
        enabled = doc.get("enabled") is True
    except Exception as exc:                                    # by contract: never raises
        return (False, DEFAULT_PRE_MIN, DEFAULT_POST_MIN,
                f"{getattr(p, 'name', p)} malformed ({type(exc).__name__}: {exc})"[:200]
                + ": OFF")
    return enabled, pre, post, f"{p.name}: enabled={enabled} pre={pre} post={post}"


def uncovered_families(start: date, end: date) -> tuple[str, ...]:
    """MONTHLY families with no release in the table for some month touched by [start, end]
    (each WHOLE month, never month-to-date), as 'FAMILY:YYYY-MM'; 'ALL:YYYY' for a year the
    table refuses. A gap is a blind spot of the fence, never a quiet month."""
    lo = start.replace(day=1)
    hi = end.replace(day=calendar.monthrange(end.year, end.month)[1])
    out: list[str] = []
    for y in range(lo.year, hi.year + 1):
        a = lo if y == lo.year else date(y, 1, 1)
        b = hi if y == hi.year else date(y, 12, 31)
        try:
            rel = releases(a, b)
        except ValueError:
            out.append(f"ALL:{y}")
            continue
        have = {(r.family, r.when.month) for r in rel}
        for m in range(a.month, b.month + 1):
            out.extend(f"{f}:{y:04d}-{m:02d}" for f in MONTHLY if (f, m) not in have)
    return tuple(out)


def verdict(now: datetime, *, flag_path: Path | None = None,
            rel: list[Release] | None = None) -> FenceVerdict:
    """The fence's decision at `now` (UTC). NEVER raises: any failure is a fail-OPEN verdict
    carrying `error`, which the liveness check reports RED."""
    enabled, pre, post, fwhy = read_flag(flag_path)
    try:
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        day = now.astimezone(UTC).date()
        gaps = uncovered_families(day, day)
        blind = bool(gaps)
        try:
            known = rel if rel is not None else releases(day - timedelta(days=1),
                                                         day + timedelta(days=1))
        except ValueError as exc:
            known, blind = [], True
            fwhy += f"; calendar refused ({exc})"
        hit = blackout(now, known, pre_min=pre, post_min=post, families=TIER1)
    except Exception as exc:                                    # by contract: never raises
        return FenceVerdict(enabled, False, None, f"{fwhy}; verdict failed: fail OPEN",
                            calendar_ok=False,
                            error=f"{type(exc).__name__}: {exc}"[:200])
    note = (f" (calendar blind to {', '.join(gaps)}: UNMEASURED, fail OPEN)" if blind else "")
    if hit is None:
        return FenceVerdict(enabled, False, None,
                            f"{fwhy}; no known tier-1 release within -{pre}/+{post} min{note}",
                            calendar_ok=not blind, uncovered=gaps)
    tag = f"{hit.when:%Y-%m-%d %H:%M}Z {hit.family}"
    return FenceVerdict(enabled, True, tag, f"{fwhy}; inside -{pre}/+{post} min of {tag}{note}",
                        calendar_ok=not blind, uncovered=gaps)


def resting_entry_legs(state: dict[str, Any], open_ids: set[int],
                       filled: dict[int, int]) -> list[tuple[str, str, int]]:
    """(window, side, order_id) of this lane's resting ENTRY legs on windows with no position.
    Protective stop/target orders are never window legs, so they are never returned."""
    out: list[tuple[str, str, int]] = []
    for name, w in (state.get("windows") or {}).items():
        if w.get("position_id") is not None:
            continue
        for side, o in (w.get("orders") or {}).items():
            oid = o.get("id") if isinstance(o, dict) else None
            if oid is None:
                continue
            if int(oid) in open_ids and int(oid) not in filled:
                out.append((str(name), str(side), int(oid)))
    return out
