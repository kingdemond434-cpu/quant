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
        from datetime import datetime, timezone  # noqa: PLC0415
        if datetime.now(timezone.utc).hour == 22:  # once per UTC day
            import shadow_forward  # noqa: PLC0415
            shadow_forward.main()
            import promoter  # noqa: PLC0415
            promoter.main()
            import regime_monitor  # noqa: PLC0415
            regime_monitor.main()
        if datetime.now(timezone.utc).weekday() == 0 and datetime.now(timezone.utc).hour == 23:
            import json as _json  # noqa: PLC0415
            from pathlib import Path as _Path  # noqa: PLC0415
            stfile = _Path(r"C:\Users\dell\mt5-research\data\hunt7_state.json")
            last = 0
            if stfile.exists():
                try:
                    last = _json.loads(stfile.read_text(encoding="utf-8")).get("last_sweep", 0)
                except Exception:
                    pass
            now_ts = datetime.now(timezone.utc).timestamp()
            if now_ts - last > 6 * 86400:  # weekly standing sweep
                try:
                    import fetch_universe  # noqa: PLC0415
                    fetch_universe.main()
                    import run_hunt7  # noqa: PLC0415
                    run_hunt7.main()
                    import run_hunt8  # noqa: PLC0415
                    run_hunt8.main()
                    import run_hunt9  # noqa: PLC0415
                    run_hunt9.main()
                    stfile.write_text(_json.dumps({"last_sweep": now_ts}),
                                      encoding="utf-8")
                    gateway.log("weekly hunt7/8/9 sweep completed")
                except Exception as e2:  # noqa: BLE001
                    gateway.log(f"HUNT7/8/9 ERROR: {e2!r}")
    except Exception as e:  # noqa: BLE001 - watchdog must never die
        gateway.log(f"LOOP ERROR: {e!r}")
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()