#!/usr/bin/env python3
"""P0 liveness watch (principal calibration 2026-08-25): critical failures invoke the repair
organ IMMEDIATELY instead of waiting for its weekly slot -- the same gap-wirer serves both
roles; this watcher only decides WHEN it fires early.

P0 conditions (any one triggers): a failed user unit; a production heartbeat/state artifact
stale beyond twice its cadence; a fence alarm artifact present. Cooldown: at most one
event-triggered invocation per 6 hours (shared via libs.ops.repair_invoke), so a persistent failure gets one
deep repair run, not a thrash loop -- the weekly slot still runs regardless.

    python3 scripts/check_p0_liveness.py       # exit 0 quiet / triggers wirer and exits 1
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.repair_invoke import request_repair

ROOT = Path(__file__).resolve().parent.parent
# The cooldown and its stamp moved to libs/ops/repair_invoke.py (2026-08-26) so all five
# gap-wirer invokers share ONE rate limit. They are deliberately NOT restated here: a stale
# `STAMP = data/p0_last_fired` would tell the next reader that this fence still owns its own
# window, which is exactly the belief that let four other fences fire without one.
LOG = ROOT / "data" / "p0_watch.log"

#: artifact -> max age in minutes (2x its producer's cadence)
STALE_WATCH = {
    "logs_hourly": ("/home/quant/logs/hourly_user.log", 150),
    "qquant_proxy": ("desks/mt5/reports/shadow/qquant_shadow_state.json", 90),
    "x_signals": ("web/x_signals.json", 180),
    "moneypath_fence_log_write": ("data/moneypath_fence.log", None),  # presence-only info
}
ALARMS = ["data/FENCE_ALARM.txt", "data/AUTHORITY_ALARM.txt"]


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
    for h in hard:
        log(f"P0: {h}")
    # SHARED DOOR (2026-08-26). This fence was the ONLY one of five gap-wirer invokers with a
    # cooldown; the other four fired on every breaching run, at cadences as fast as 10 minutes,
    # so a persistent breach re-spawned a multi-hour Claude seat continuously -- three OOM kills
    # and a 1.6GB peak in one night, each run holding the desk-wide brain mutex and starving the
    # miners behind it. libs.ops.repair_invoke now owns the rate limit for everyone, using this
    # fence's own 6h value and this fence's own semantics, so nothing here changes behaviour --
    # it just stops being the only place that behaves.
    log("P0 TRIGGER: requesting gap-wirer (event-driven repair)")
    request_repair("p0-liveness: " + "; ".join(hard[:3]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
