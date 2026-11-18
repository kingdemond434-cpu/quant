"""Dukascopy tick backfill: REFUSED ON TERMS, every pass writes a refusal and fetches nothing.

This used to download a few complete UTC symbol-days an hour and advance a per-symbol cursor.
Dukascopy's terms refuse automated access and commercial use of its data (the desk's own verdict,
data/data_universe_map.json dukascopy_bi5_datafeed_VERDICT, grade excluded-illegitimate), so the
download path is REMOVED rather than switched off. The hourly leg still runs and leaves an
artifact: a BLOCKED_ON_TERMS report with its missed-growth line and a count of the files already
held, which stay on disk exactly as they are and are never refreshed. The cursor file is left
untouched so the record of what was held is not rewritten.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:  # package import in tests; direct import when invoked as a script by the supervisor
    from .fetch_dukascopy import BLOCKED_ON_TERMS, MISSED_GROWTH, POINT
except ImportError:  # pragma: no cover - exercised by the real script entry point
    from fetch_dukascopy import BLOCKED_ON_TERMS, MISSED_GROWTH, POINT


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


def held_files(root: Path = DATA) -> dict[str, int]:
    """Day files already on disk per symbol, read without opening any of them."""
    held: dict[str, int] = {}
    for symbol in SYMBOLS:
        n = sum(1 for _ in (root / symbol).glob("*/*/*.parquet")) if (root / symbol).is_dir() else 0
        if n:
            held[symbol] = n
    return held


def run(*, root: Path = DATA, report_path: Path = REPORT,
        now: datetime | None = None) -> dict[str, Any]:
    """Write the refusal record. Opens no socket and changes no held file or cursor."""
    now = now or datetime.now(UTC)
    held = held_files(root)
    report = {
        "schema_version": 2,
        "generated_at": now.isoformat(),
        "status": "BLOCKED_ON_TERMS",
        "why": BLOCKED_ON_TERMS,
        "missed_growth": MISSED_GROWTH,
        "authority": "RESEARCH_DEPTH_ONLY",
        "venue_cost_authority": "Fusion-native quotes and fills",
        "supported_symbols": len(SYMBOLS),
        "attempted_symbol_days": 0,
        "written": 0,
        "retry": 0,
        "held_day_files": held,
        "held_day_files_total": sum(held.values()),
        "held_data": "labelled Dukascopy-sourced, kept as is, never refreshed",
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
    # Kept so the hourly leg's existing command line still parses; none of them fetches anything.
    parser.add_argument("--symbol-days", type=int, default=0)
    parser.add_argument("--pause", type=float, default=0.0)
    parser.add_argument("--out", type=Path, default=DATA)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    now = datetime.now(UTC)
    if not _claim(LOCK, now=now):
        print("Dukascopy backfill already running; this pass is a measured no-op")
        return 0
    try:
        report = run(root=args.out, report_path=args.report, now=now)
    finally:
        LOCK.unlink(missing_ok=True)
    print(f"Dukascopy: {report['status']}; {report['held_day_files_total']} held day files kept, "
          "nothing fetched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
