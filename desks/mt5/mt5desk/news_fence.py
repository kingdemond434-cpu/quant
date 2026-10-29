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
Absent -> OFF with the defaults. Unreadable or malformed -> OFF, and `why` says so (the RED check
in scripts/check_news_fence_liveness.py reports it). Windows are arguments, not constants fitted
to one afternoon (calendar_us docstring).
"""
from __future__ import annotations

import json
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
#: Families published every month; a month with none of them in the table is a calendar GAP.
#: FOMC and its minutes meet eight times a year, so a month without them is not evidence.
MONTHLY = ("NFP", "CPI", "PPI", "PCE", "GDP")


@dataclass(frozen=True)
class FenceVerdict:
    enabled: bool
    in_window: bool                      # a known tier-1 release is inside the window now
    release: str | None
    why: str
    calendar_ok: bool = True
    uncovered: tuple[str, ...] = field(default_factory=tuple)

    @property
    def blocks(self) -> bool:
        """True when the fence REFUSES (enabled and in a window, or enabled and blind)."""
        return self.enabled and (self.in_window or not self.calendar_ok)

    @property
    def would_block(self) -> bool:
        """What it would refuse if it were on -- the shadow bill when it is off."""
        return self.in_window

    def as_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "in_window": self.in_window, "blocks": self.blocks,
                "release": self.release, "why": self.why, "calendar_ok": self.calendar_ok,
                "uncovered": list(self.uncovered)}


def read_flag(path: Path | None = None) -> tuple[bool, int, int, str]:
    """(enabled, pre_min, post_min, why). Absent or bad -> OFF; never raises."""
    p = FLAG if path is None else path
    try:
        raw = p.read_text("utf-8")
    except FileNotFoundError:
        return False, DEFAULT_PRE_MIN, DEFAULT_POST_MIN, f"no {p.name}: fence OFF (default)"
    except OSError as exc:
        return False, DEFAULT_PRE_MIN, DEFAULT_POST_MIN, f"{p.name} unreadable ({exc}): OFF"
    try:
        doc = json.loads(raw)
        if not isinstance(doc, dict):
            raise ValueError("not an object")
        pre = int(doc.get("pre_min", DEFAULT_PRE_MIN))
        post = int(doc.get("post_min", DEFAULT_POST_MIN))
        if pre < 0 or post < 0:
            raise ValueError("negative window")
        enabled = doc.get("enabled") is True
    except (ValueError, TypeError) as exc:
        return False, DEFAULT_PRE_MIN, DEFAULT_POST_MIN, f"{p.name} malformed ({exc}): OFF"
    return enabled, pre, post, f"{p.name}: enabled={enabled} pre={pre} post={post}"


def uncovered_families(start: date, end: date) -> tuple[str, ...]:
    """MONTHLY families with no release in the table for some month in [start, end], as
    'FAMILY:YYYY-MM'. A gap is a blind spot of the fence, never a quiet month."""
    try:
        rel = releases(start, end)
    except ValueError:
        return tuple(f"ALL:{y}" for y in range(start.year, end.year + 1))
    have = {(r.family, r.when.year, r.when.month) for r in rel}
    out: list[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.extend(f"{f}:{y:04d}-{m:02d}" for f in MONTHLY if (f, y, m) not in have)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return tuple(out)


def verdict(now: datetime, *, flag_path: Path | None = None,
            rel: list[Release] | None = None) -> FenceVerdict:
    """The fence's decision at `now` (UTC). Never raises."""
    enabled, pre, post, fwhy = read_flag(flag_path)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    day = now.astimezone(UTC).date()
    try:
        known = rel if rel is not None else releases(day - timedelta(days=1),
                                                     day + timedelta(days=1))
    except ValueError as exc:
        return FenceVerdict(enabled, False, None,
                            f"{fwhy}; calendar refused ({exc}); "
                            + ("fail closed" if enabled else "UNMEASURED"),
                            calendar_ok=False, uncovered=(f"ALL:{day.year}",))
    hit = blackout(now, known, pre_min=pre, post_min=post, families=TIER1)
    gaps = uncovered_families(day.replace(day=1), day)
    if hit is None:
        why = f"{fwhy}; no known tier-1 release within -{pre}/+{post} min"
        if gaps:
            why += f" (calendar blind to {', '.join(gaps)}: UNMEASURED, not clear)"
        return FenceVerdict(enabled, False, None, why, uncovered=gaps)
    tag = f"{hit.when:%Y-%m-%d %H:%M}Z {hit.family}"
    return FenceVerdict(enabled, True, tag,
                        f"{fwhy}; inside -{pre}/+{post} min of {tag}", uncovered=gaps)


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
