"""WALCL reserve-impulse forward clock -- R0031, pre-registered 2026-07-31.

STAGE A EVIDENCE (data/fred_macro_screen.json, trial fred_macro::reserve_quantity_impulse::h1b):
IC +0.1106 on n=815 weekly obs, mechanism-consistent momentum sign (Sharpe 0.82), de-contamination
PASSED (residual IC +0.0964), verdict SCREEN-UNDERPOWERED. The power wall cannot be closed
retroactively; the honest path is forward accrual under the Two-Stage law.

PRE-REGISTERED CONSTRUCTION (changing any of it is a NEW trial):
  signal    = 4-week log change in WALCL
  lag       = +2 calendar days from the Wednesday as-of date
  z         = trailing 20-observation z-score, past-only
  direction = +1, target BTCUSDT next-day close-to-close

The deriver never back-writes dates. Reads data/fred_macro.json; no network.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_ARCHIVE = _ROOT / "data" / "fred_macro.json"
_CLOCK = _ROOT / "data" / "walcl_impulse.jsonl"

# Constants for the life of the registered clock. A second window is a second trial.
_IMPULSE_WEEKS = 4
_ZWIN = 20
_RELEASE_LAG_DAYS = 2
_MIN_OBS = _IMPULSE_WEEKS + _ZWIN


def _series() -> list[tuple[str, float]]:
    """Return WALCL rows oldest-first; unreadable input refuses rather than fabricating zero."""
    try:
        doc = json.loads(_ARCHIVE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(doc, dict):
        return []
    series = doc.get("series", {})
    if not isinstance(series, dict):
        return []
    raw_rows = series.get("WALCL", [])
    if not isinstance(raw_rows, list):
        return []
    out: list[tuple[str, float]] = []
    for row in raw_rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2 or not row[1]:
            continue
        try:
            value = float(row[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            out.append((str(row[0]), value))
    out.sort()
    return out


def signal_for(today: str, rows: list[tuple[str, float]]) -> dict[str, Any] | None:
    """Return the registered z-score from observations available by ``today``."""
    avail = [
        (date, value)
        for date, value in rows
        if (datetime.fromisoformat(date) + timedelta(days=_RELEASE_LAG_DAYS)).date().isoformat()
        <= today
    ]
    if len(avail) < _MIN_OBS:
        return None
    impulses = [
        math.log(avail[i][1]) - math.log(avail[i - _IMPULSE_WEEKS][1])
        for i in range(_IMPULSE_WEEKS, len(avail))
    ]
    window = impulses[-_ZWIN:]
    mean = sum(window) / len(window)
    variance = sum((value - mean) ** 2 for value in window) / len(window)
    sd = math.sqrt(variance)
    if sd < 1e-12:
        return None
    return {
        "date": today,
        "z20": round((impulses[-1] - mean) / sd, 4),
        "asof": avail[-1][0],
        "impulse": round(impulses[-1], 6),
    }


def main() -> int:
    _law_guard()
    today = datetime.now(tz=UTC).date().isoformat()
    rows = _series()
    if not rows:
        print(f"walcl-clock: CANNOT MEASURE -- {_ARCHIVE} missing/unreadable/empty; no row written")
        return 1
    signal = signal_for(today, rows)
    if signal is None:
        print(
            f"walcl-clock: CANNOT MEASURE -- {len(rows)} obs available, need {_MIN_OBS} "
            "with release lag; no row written"
        )
        return 1
    if _CLOCK.exists():
        for line in _CLOCK.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("date") == today:
                print(f"walcl-clock: {today} already recorded (idempotent) -- z {signal['z20']}")
                return 0
    with _CLOCK.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(signal) + "\n")
    print(
        f"walcl-clock: {today} z {signal['z20']} (asof {signal['asof']}, "
        f"impulse {signal['impulse']}) -> {_CLOCK.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
