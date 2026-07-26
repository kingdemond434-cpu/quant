"""Re-fire today's quota-killed claude organs once credits are back (cron */30, flock).

Fires at most ONE organ per tick (staggered, so a burst of catch-ups cannot re-exhaust
the fresh quota window), and only after a pageless quota probe succeeds -- a dead pool
costs one failed CLI ping and zero pages. The organ's own brain_auth_check still governs
its real run. See libs/ops/organ_catchup.py for the owed rules.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.ops.organ_catchup import pick_organ  # noqa: E402

LOGDIR = ROOT / "data" / "cro_ai_logs"


def _running(pattern: str) -> bool:
    res = subprocess.run(["pgrep", "-f", pattern], capture_output=True, check=False)
    return res.returncode == 0


def _quota_ok() -> bool:
    # brain_auth_check with paging neutered: walks the model fallback chain, never spams ntfy.
    probe = (
        "cd " + str(ROOT) + " && source ops/brain_env.sh >/dev/null 2>&1 && "
        "_brain_page() { :; } && brain_auth_check >/dev/null 2>&1"
    )
    try:
        return subprocess.run(["bash", "-c", probe], timeout=240, check=False).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def main() -> None:
    now = datetime.now(tz=UTC)
    spec = pick_organ(LOGDIR, now, _running)
    if spec is None:
        # NEVER SILENT (2026-07-26): 'nothing owed' and 'the cron died' used to look
        # identical -- the log just stopped. For a desk whose defining failure is
        # state-looks-healthy/output-is-nothing, silence must never be ambiguous.
        print(f"{datetime.now(tz=UTC).isoformat()} nothing owed -- all organs produced")
        return
    if spec is None:
        return
    if not _quota_ok():
        print(f"{now.isoformat()} owed={spec.name} quota=DEAD -- no fire")
        return
    subprocess.Popen(  # fixed ops script, detached like the cron spawns
        ["setsid", "-f", "bash", str(ROOT / spec.script)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        cwd=str(ROOT), start_new_session=True,
    )
    print(f"{now.isoformat()} re-fired {spec.name} ({spec.script})")


if __name__ == "__main__":
    main()
