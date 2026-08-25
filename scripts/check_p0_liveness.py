#!/usr/bin/env python3
"""P0 liveness watch (principal calibration 2026-08-25): critical failures invoke the repair
organ IMMEDIATELY instead of waiting for its weekly slot -- the same gap-wirer serves both
roles; this watcher only decides WHEN it fires early.

P0 conditions (any one triggers): a failed user unit; a production heartbeat/state artifact
stale beyond twice its cadence; a fence alarm artifact present. Cooldown: at most one
event-triggered invocation per 6 hours (data/p0_last_fired), so a persistent failure gets one
deep repair run, not a thrash loop -- the weekly slot still runs regardless.

    python3 scripts/check_p0_liveness.py       # exit 0 quiet / triggers wirer and exits 1
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COOLDOWN_S = 6 * 3600
STAMP = ROOT / "data" / "p0_last_fired"
LOG = ROOT / "data" / "p0_watch.log"

#: artifact -> max age in minutes (2x its producer's cadence)
STALE_WATCH = {
    "logs_hourly": ("/home/quant/logs/hourly_user.log", 150),
    "qquant_proxy": ("desks/mt5/reports/shadow/qquant_shadow_state.json", 90),
    "x_signals": ("web/x_signals.json", 180),
    "moneypath_fence_log_write": ("data/moneypath_fence.log", None),  # presence-only info
}
ALARMS = ["data/FENCE_ALARM.txt"]


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def failed_user_units() -> list[str]:
    r = subprocess.run(["systemctl", "--user", "--failed", "--no-legend", "--plain"],
                       capture_output=True, text=True, timeout=30, check=False)
    return [ln.split()[0] for ln in r.stdout.splitlines() if ln.strip()]


def main() -> int:
    problems: list[str] = []
    for u in failed_user_units():
        # memecoin OOM recurrences are a known root-console item (swap); still reported,
        # but alone they do not spend the 6h cooldown on a repair run that cannot add swap.
        problems.append(f"failed unit: {u}")
    hard = [p for p in problems if "memecoin" not in p]
    now = time.time()
    for name, (rel, max_min) in STALE_WATCH.items():
        if max_min is None:
            continue
        p = Path(rel) if rel.startswith("/") else ROOT / rel
        if not p.exists():
            hard.append(f"stale: {name} missing ({rel})")
        elif now - p.stat().st_mtime > max_min * 60:
            age = int((now - p.stat().st_mtime) / 60)
            hard.append(f"stale: {name} {age}min old (floor {max_min}min)")
    for rel in ALARMS:
        if (ROOT / rel).exists():
            hard.append(f"alarm artifact present: {rel}")

    if not hard:
        return 0
    last = 0.0
    with suppress(OSError, ValueError):
        last = float(STAMP.read_text().strip())
    for h in hard:
        log(f"P0: {h}")
    if now - last < COOLDOWN_S:
        log(f"P0 present but cooldown active ({int((now - last) / 60)}min ago); weekly slot "
            f"or next cooldown window will take it")
        return 1
    STAMP.write_text(json.dumps(now), "utf-8")
    log("P0 TRIGGER: invoking gap-wirer early (event-driven repair)")
    subprocess.Popen(["systemctl", "--user", "start", "--no-block",
                      "quant-gap-wirer.service"])
    return 1


if __name__ == "__main__":
    sys.exit(main())
