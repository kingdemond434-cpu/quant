"""Cash-and-carry tracker daemon -- the spot book running 24/7 as its OWN process.

Separate from the perp executor (they can't share one futures account), this keeps the cash-and-
carry book live: each loop it advances the forward shadow, refreshes the live carry candidates
(positive-funding perps tradeable on both testnets), and writes a heartbeat the watchdog monitors.
No orders -- it is the tracked/paper spot book, so it never collides with the perp executor. With
this running, both books are alive as distinct Python processes.

    python scripts/run_cashcarry_tracker.py --interval 1800
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from libs.data.crypto_source import current_funding

_ROOT = Path(__file__).resolve().parent.parent
_HB = _ROOT / "data" / "cashcarry_heartbeat"
_STATUS = _ROOT / "web" / "cashcarry_tracker.json"
_HB_TICK = 60                                  # heartbeat cadence (decoupled from book update)


def _loop_once() -> None:
    # advance the forward shadow + refresh the molded live account (best-effort; survive failures)
    for script in ("run_cashcarry_shadow.py", "run_live_combined.py"):
        with contextlib.suppress(Exception):
            subprocess.run([sys.executable, f"scripts/{script}"], cwd=str(_ROOT),
                           timeout=600, capture_output=True, text=True, check=False)
    pos: list[tuple[str, float]] = []
    with contextlib.suppress(Exception):
        f = current_funding()
        pos = sorted(((s, v) for s, v in f.items() if v > 0 and s.endswith("USDT")),
                     key=lambda x: -x[1])[:8]
    _STATUS.parent.mkdir(parents=True, exist_ok=True)
    _STATUS.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(),
        "tracking": "delta-neutral cash-and-carry (long spot + short perp), positive funding",
        "top_carries": [{"symbol": s, "funding_8h": round(v, 6)} for s, v in pos],
        "note": "Runs 24/7 as its own process, separate from the perp executor. Paper / tracked.",
    }, indent=2), "utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=1800, help="seconds between book updates")
    ap.add_argument("--once", action="store_true", help="single pass then exit")
    args = ap.parse_args()
    # heartbeat ticks every _HB_TICK so a dead process goes stale fast (no false single-instance
    # lock); the heavy book update only runs every --interval.
    if not args.once and _HB.exists() and (time.time() - _HB.stat().st_mtime) < _HB_TICK * 2.5:
        print("another cash-carry tracker is already running (fresh heartbeat) -- exiting")
        return
    print(f"cash-carry tracker | book update {args.interval}s | hb {_HB_TICK}s | no orders")
    last_work = 0.0
    while True:
        _HB.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")
        if time.time() - last_work >= args.interval:
            _loop_once()
            last_work = time.time()
        if args.once:
            break
        time.sleep(_HB_TICK)


if __name__ == "__main__":
    main()
