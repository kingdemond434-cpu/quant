"""Gateway watchdog unit: ONE gateway pass per invocation.

Windows Task Scheduler runs this every minute (task MT5-Gateway). A file lock
prevents overlapping passes (double-bracket race at window hours).

Never trade a weekend/holiday: gateway.main() itself idles on stale ticks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import gateway  # noqa: E402

LOCK = Path(r"C:\Users\dell\mt5-research\data\gateway.lock")


def main() -> None:
    if LOCK.exists():
        age_min = (__import__("time").time() - LOCK.stat().st_mtime) / 60
        if age_min < 5:
            return  # another pass is running (or crashed <5 min ago)
        LOCK.unlink(missing_ok=True)  # stale lock: steal it
    LOCK.write_text("locked", encoding="utf-8")
    try:
        gateway.main()
        import shadow_forward  # noqa: PLC0415
        from datetime import datetime, timezone  # noqa: PLC0415
        if datetime.now(timezone.utc).hour == 22:  # once per UTC day
            shadow_forward.main()
    except Exception as e:  # noqa: BLE001 - watchdog must never die
        gateway.log(f"LOOP ERROR: {e!r}")
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()