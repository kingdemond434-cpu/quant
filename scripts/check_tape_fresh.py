"""Is the tick tape still moving? RED when its newest tick is over 2 h old while FX trades.

WHY (2026-10-14). MT5-TickRecorder returned 1 at 2026-10-12 19:56 box time and was never run
again: its only triggers were boot and logon, and the scheduler's restart-on-failure does not
fire on a non-zero exit. process_health named it FAILING for two days and nothing acted, because
no contract tied it to an artifact. Origin's `tape_state.json` reads 2026-09-04, but that file
was never on the box's publish allowlist, so its date says nothing about the box. This fence
reads each tape's OWN newest-tick stamp on the box that writes it, and publishes the verdict.

THE TWO TAPES, both judged:

    bronze  reports/TAPE_RECORDER.json  `last_tick_ms`  recorders/tick_recorder.py (MT5-TickRecorder)
    silver  data/tape/tape_state.json   per-symbol `last_tick_ms`, newest taken (hourly `tape` leg)

THE STAMP IS THE VENUE'S CLOCK. `time_msc` is New York + 7 h under an epoch label (two or three
hours ahead of UTC), so it is converted by `libs.regime.session_clock.server_to_utc`, the desk's
one conversion. Read raw, a live tape would sit in the future.

VERDICTS, per tape:
    FRESH          newest tick within 2 h of now, or of the week's open if that is later
    STALE          over 2 h during FX hours (Sunday 22:00 UTC to Friday 22:00 UTC) -- RED
    MARKET_CLOSED  outside FX hours; the age is still published
    UNMEASURED     absent, unreadable, unstamped, or stamped in the future -- RED (L1.28a)

The age during FX hours is measured from the LATER of the newest tick and the week's open, so
Sunday's first two hours are not red for a Friday tick the market could not have improved on.

    python scripts/check_tape_fresh.py      # writes the report; exit 1 when RED
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "TAPE_FRESHNESS.json"

MAX_AGE_H = 2.0
#: A stamp more than this far past now is a clock defect, never a fresh tape.
FUTURE_SLACK = timedelta(minutes=5)

#: (name, artifact under desks/mt5, producer)
TAPES: tuple[tuple[str, str, str], ...] = (
    ("bronze", "reports/TAPE_RECORDER.json", "MT5-TickRecorder: recorders/tick_recorder.py"),
    ("silver", "data/tape/tape_state.json", "hourly_cycle `tape` leg: mt5desk/tape.py"),
)


def fx_open(now: datetime) -> bool:
    """The FX week: Sunday 22:00 UTC to Friday 22:00 UTC."""
    wd, h = now.weekday(), now.hour + now.minute / 60.0
    if wd == 5:
        return False
    if wd == 6:
        return h >= 22.0
    if wd == 4:
        return h < 22.0
    return True


def week_open(now: datetime) -> datetime:
    """The most recent Sunday 22:00 UTC at or before `now`."""
    days_back = (now.weekday() + 1) % 7            # Sunday -> 0, Monday -> 1, ...
    sunday = (now - timedelta(days=days_back)).replace(hour=22, minute=0, second=0,
                                                       microsecond=0)
    return sunday if sunday <= now else sunday - timedelta(days=7)


def broker_ms_to_utc(ms: int) -> datetime:
    """A venue `time_msc` as the true UTC instant (New York wall time + 7 h)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import pandas as pd

    from libs.regime.session_clock import server_to_utc
    return server_to_utc(pd.to_datetime([int(ms)], unit="ms"))[0].to_pydatetime()


def newest_ms(doc: Any) -> int | None:
    """The newest broker-clock tick stamp in either tape's shape, or None."""
    if not isinstance(doc, dict):
        return None
    vals: list[int] = []
    if "last_tick_ms" in doc:                       # bronze status: one top-level stamp
        vals.append(doc.get("last_tick_ms"))  # type: ignore[arg-type]
    else:                                           # silver state: one row per symbol
        vals.extend(r.get("last_tick_ms") for r in doc.values() if isinstance(r, dict))
    good = []
    for v in vals:
        try:
            iv = int(v)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            continue
        if iv > 0:
            good.append(iv)
    return max(good) if good else None


def judge(path: Path, now: datetime) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "UNMEASURED", "why": "tape artifact absent"}
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "why": f"unreadable ({type(exc).__name__})"}
    ms = newest_ms(doc)
    if ms is None:
        return {"status": "UNMEASURED", "why": "no tick stamp (`last_tick_ms`) in the tape"}
    try:
        at = broker_ms_to_utc(ms)
    except Exception as exc:                        # conversion unavailable is not freshness
        return {"status": "UNMEASURED", "why": f"stamp not convertible ({type(exc).__name__})"}
    row: dict[str, Any] = {"last_tick_ms": ms, "last_tick_utc": at.isoformat(),
                           "age_h": round((now - at).total_seconds() / 3600, 2)}
    if at > now + FUTURE_SLACK:
        return {**row, "status": "UNMEASURED",
                "why": "newest tick is stamped in the future -- a clock defect, not a fresh tape"}
    if not fx_open(now):
        return {**row, "status": "MARKET_CLOSED", "why": "outside FX hours"}
    since = max(at, week_open(now))
    open_age = round((now - since).total_seconds() / 3600, 2)
    row["open_age_h"] = open_age
    if open_age > MAX_AGE_H:
        return {**row, "status": "STALE",
                "why": f"no tick for {open_age:g} h of open market against {MAX_AGE_H:g} h"}
    return {**row, "status": "FRESH", "why": ""}


def build(desk: Path = DESK, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    rows = [{"tape": name, "artifact": f"desks/mt5/{rel}", "producer": producer,
             **judge(desk / rel, now)} for name, rel, producer in TAPES]
    red = [r["tape"] for r in rows if r["status"] in ("STALE", "UNMEASURED")]
    return {"schema": "tape_freshness/1", "generated_at": now.isoformat(timespec="seconds"),
            "fx_open": fx_open(now), "max_age_h": MAX_AGE_H,
            "status": "RED" if red else "GREEN", "red": red, "n_red": len(red),
            "n_unmeasured": sum(1 for r in rows if r["status"] == "UNMEASURED"), "tapes": rows}


def main(argv: list[str] | None = None) -> int:
    rep = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    for r in rep["tapes"]:
        print(f"  {r['status']:<14} {r['tape']:<7} {r.get('last_tick_utc', '-')}  {r['why']}")
    print(f"tape: {rep['status']} -> {OUT}")
    return 1 if rep["red"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
