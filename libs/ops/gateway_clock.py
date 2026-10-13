"""WHEN DID THE GATEWAY LAST PASS, IN UTC -- read from a stamp that was written in broker time.

THE DEFECT (ledger row L3, 2026-10-13). `gateway.main` stamps `st["placement_pass"]` from
`pd.Timestamp(tick.time, unit="s", tz="UTC")`. MetaTrader's `tick.time` is the BROKER's wall clock
counted as seconds, not a UTC epoch, so the stamp carries broker time under a `+00:00` label: at
15:20 UTC it read 18:20 "UTC" (Fusion runs EET/EEST, +3 in summer, +2 in winter). Every reader
that subtracted it from `datetime.now(UTC)` got an age three hours too YOUNG -- a gateway that had
stopped two hours ago still read as passing "in the future" -- and a role check that took the
newest stamp kept calling a cold host the trading host for three hours longer.

THE CURE IS AT THE SOURCE and is a money-path change (desktop spec
`docs/desktop_pass/recovery_drills/gateway_broker_clock_stamp.md`): the gateway writes real UTC and
marks it `placement_pass_clock: "utc"`. Until that lands, and for every legacy file after it, this
is the one place a reader turns the stamp into UTC:

  * `placement_pass_clock == "utc"`  -> the stamp is UTC already, taken as written;
  * otherwise (legacy, broker time)  -> minus the broker's UTC offset from
    `session_phase.broker_utc_offset_h()` (live terminal, recorded measurement, then the bars);
  * offset unknown                   -> None. UNMEASURED, never a guessed zero: a zero offset is
    exactly the three-hour error this module exists to remove.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_RESEARCH = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
UTC_MARK = "utc"


def broker_offset_h() -> int | None:
    """The broker's UTC offset in hours, from the desk's one resolver; None when unknown."""
    try:
        if str(_RESEARCH) not in sys.path:
            sys.path.insert(0, str(_RESEARCH))
        import session_phase  # type: ignore[import-not-found]
        off, _src = session_phase.broker_utc_offset_h()
    except Exception:
        return None
    return None if off is None else int(off)


def _parse(value: Any) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def placement_pass_utc(state: Any,
                       offset: Callable[[], int | None] = broker_offset_h) -> datetime | None:
    """`gateway_state.json`'s last placement pass as a real UTC instant, or None (UNMEASURED)."""
    if not isinstance(state, dict):
        return None
    ts = _parse(state.get("placement_pass"))
    if ts is None:
        return None
    if str(state.get("placement_pass_clock") or "").lower() == UTC_MARK:
        return ts.astimezone(UTC)
    off = offset()
    if off is None:
        return None
    return (ts - timedelta(hours=off)).astimezone(UTC)
