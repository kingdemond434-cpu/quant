"""Bounded, resumable Dukascopy tick-history acquisition for the MT5 research desk.

This is a depth source, never execution-cost authority.  Fusion-native quotes and fills remain
the only source allowed to price the live venue.  Each invocation downloads a small number of
complete UTC symbol-days, writes them atomically, and advances a durable per-symbol cursor.
The hourly data department can therefore compound history without a multi-hour monolith or a
restart that begins again at the newest date.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

try:  # package import in tests; direct import when invoked as a script by the supervisor
    from .fetch_dukascopy import POINT, fetch_hour
except ImportError:  # pragma: no cover - exercised by the real script entry point
    from fetch_dukascopy import POINT, fetch_hour


BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "dukascopy"
REPORT = BASE / "reports" / "DUKASCOPY_BACKFILL.json"
STATE = DATA / "backfill_state.json"
LOCK = DATA / ".backfill.lock"

# Rotate across unlike exposures first.  The remainder of the supported vendor universe follows,
# so the source never collapses into another gold/FX-only dataset.
PRIORITY = (
    "XAUUSD", "XTIUSD", "USDJPY", "EURUSD", "XAGUSD", "XBRUSD", "AUDNZD", "GBPUSD",
    "XNGUSD", "EURCHF", "XPTUSD", "USDCAD", "XPDUSD",
)
SYMBOLS = PRIORITY + tuple(sorted(set(POINT) - set(PRIORITY)))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _load_state(path: Path, *, newest: date) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        raw = {}
    cursors = raw.get("next_date") if isinstance(raw.get("next_date"), dict) else {}
    clean: dict[str, str] = {}
    for symbol in SYMBOLS:
        value = str(cursors.get(symbol, newest.isoformat()))
        try:
            clean[symbol] = date.fromisoformat(value).isoformat()
        except ValueError:
            clean[symbol] = newest.isoformat()
    return {"schema_version": 1, "next_date": clean,
            "rotation": int(raw.get("rotation", 0) or 0)}


def _day_path(root: Path, symbol: str, day: date) -> Path:
    return root / symbol / f"{day:%Y}" / f"{day:%m}" / f"{symbol}_ticks_{day:%Y%m%d}.parquet"


def fetch_day(symbol: str, day: date, root: Path, *, pause: float = 0.05) -> dict[str, Any]:
    """Fetch one complete UTC day.  A partial download is never published as complete."""
    import pandas as pd

    target = _day_path(root, symbol, day)
    if target.exists():
        return {"symbol": symbol, "day": day.isoformat(), "status": "EXISTS",
                "ticks": None, "file": str(target)}
    rows: list[tuple[Any, ...]] = []
    failures: list[str] = []
    missing = 0
    start = datetime.combine(day, time.min, tzinfo=UTC)
    for hour in range(24):
        values, status = fetch_hour(symbol, start + timedelta(hours=hour), pause=pause)
        if status == "ok":
            rows.extend(values)
        elif status in {"missing", "empty"}:
            missing += 1
        else:
            failures.append(f"{hour:02d}:{status}")
    if failures:
        return {"symbol": symbol, "day": day.isoformat(), "status": "RETRY",
                "ticks": len(rows), "missing_hours": missing, "failures": failures}

    target.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=["ms", "bid", "ask", "bidvol", "askvol"])
    if not frame.empty:
        frame["utc"] = pd.to_datetime(frame.pop("ms"), unit="ms", utc=True)
        frame = frame.set_index("utc").sort_index()
    else:
        frame.index = pd.DatetimeIndex([], name="utc", tz="UTC")
    partial = target.with_suffix(target.suffix + ".partial")
    frame.to_parquet(partial)
    os.replace(partial, target)
    return {"symbol": symbol, "day": day.isoformat(), "status": "WRITTEN",
            "ticks": len(frame), "missing_hours": missing, "file": str(target)}


def run(*, root: Path = DATA, state_path: Path = STATE, report_path: Path = REPORT,
        symbol_days: int = 8, pause: float = 0.05, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    newest = now.date() - timedelta(days=1)  # never publish the still-forming UTC day
    state = _load_state(state_path, newest=newest)
    start_rotation = state["rotation"] % len(SYMBOLS)
    results: list[dict[str, Any]] = []
    for offset in range(max(0, symbol_days)):
        symbol = SYMBOLS[(start_rotation + offset) % len(SYMBOLS)]
        day = date.fromisoformat(state["next_date"][symbol])
        result = fetch_day(symbol, day, root, pause=pause)
        results.append(result)
        # Only a complete artifact (new or pre-existing) advances the cursor. Transient failures
        # remain on the same day and are retried on the next rotation.
        if result["status"] in {"WRITTEN", "EXISTS"}:
            state["next_date"][symbol] = (day - timedelta(days=1)).isoformat()
    state["rotation"] = (start_rotation + max(0, symbol_days)) % len(SYMBOLS)
    state["updated_at"] = now.isoformat()
    _atomic_json(state_path, state)
    report = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "authority": "RESEARCH_DEPTH_ONLY",
        "venue_cost_authority": "Fusion-native quotes and fills",
        "supported_symbols": len(SYMBOLS),
        "attempted_symbol_days": len(results),
        "written": sum(r["status"] == "WRITTEN" for r in results),
        "retry": sum(r["status"] == "RETRY" for r in results),
        "results": results,
        "next_date": state["next_date"],
    }
    _atomic_json(report_path, report)
    return report


def _claim(lock: Path, *, now: datetime) -> bool:
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = now.timestamp() - lock.stat().st_mtime
        except OSError:
            return False
        if age <= 2 * 3600:
            return False
        lock.unlink(missing_ok=True)
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"pid={os.getpid()} at={now.isoformat()}\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol-days", type=int, default=8)
    parser.add_argument("--pause", type=float, default=0.05)
    parser.add_argument("--out", type=Path, default=DATA)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    now = datetime.now(UTC)
    if not _claim(LOCK, now=now):
        print("Dukascopy backfill already running; this pass is a measured no-op")
        return 0
    try:
        report = run(root=args.out, state_path=args.state, report_path=args.report,
                     symbol_days=args.symbol_days, pause=max(0.0, args.pause), now=now)
    finally:
        LOCK.unlink(missing_ok=True)
    print(f"Dukascopy: {report['written']}/{report['attempted_symbol_days']} symbol-days written; "
          f"{report['retry']} held for retry")
    return 1 if report["retry"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
