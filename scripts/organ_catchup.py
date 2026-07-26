"""Re-fire today's quota-killed claude organs once credits are back (cron */30, flock).

Fires at most ONE organ per tick (staggered, so a burst of catch-ups cannot re-exhaust
the fresh quota window), and only after a pageless quota probe succeeds -- a dead pool
costs one failed CLI ping and zero pages. The organ's own brain_auth_check still governs
its real run. See libs/ops/organ_catchup.py for the owed rules.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.ops.organ_catchup import pick_organ  # noqa: E402

# A 5xx/overloaded is a SERVER hiccup, not an exhausted pool: no reset time will appear in
# the log and waiting for one would strand the organ. Retry these immediately.
_TRANSIENT = ("529", "overloaded", "502", "503", "504", "timed out", "connection reset")

_RESET_RE = re.compile(r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)


def _reset_time_from_log(path: Path, now: datetime) -> datetime | None:
    """Parse the reset stamp the CLI itself prints into a UTC datetime.

    The death logs state it verbatim -- "session limit - resets 11:40pm (UTC)", "out of usage
    credits - resets 4am" -- so the desk never has to guess when it may resume. Returns None when
    no stamp is present (e.g. an auth or model failure, which no reset will fix).
    """
    try:
        txt = path.read_text("utf-8", errors="ignore")
    except OSError:
        return None
    m = _RESET_RE.search(txt)
    if not m:
        return None
    hh, mm, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ap == "pm" and hh != 12:
        hh += 12
    elif ap == "am" and hh == 12:
        hh = 0
    if hh > 23:
        return None
    # ANCHOR TO THE LOG, NOT TO NOW. The stated reset is the first such clock time AFTER the
    # death, so it is computed from the death's own timestamp. Anchoring to `now` pushed an
    # ALREADY-PASSED reset a full day forward and would have blocked resume for ~23h.
    try:
        died = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        died = now.astimezone(UTC)
    cand = died.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cand < died:
        cand += timedelta(days=1)          # reset falls after midnight relative to the death
    return cand


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
    # RESET-AWARE (2026-07-26): if the organ's own death log states when the window
    # reopens, do not burn a probe before that minute -- and fire on the FIRST tick
    # at/after it, so resume lands ~1 minute after reset instead of up to a poll late.
    _logs = sorted(LOGDIR.glob(spec.pattern), key=lambda p: p.stat().st_mtime)
    _reset = _reset_time_from_log(_logs[-1], now) if _logs else None
    if _logs:
        _tail = _logs[-1].read_text('utf-8', errors='ignore').lower()
        if any(k in _tail for k in _TRANSIENT):
            _reset = None            # transient server error -> retry now, do not wait
    if _reset is not None and now.astimezone(UTC) < _reset:
        print(f"{now.isoformat()} owed={spec.name} waiting for stated reset "
              f"{_reset.isoformat()} -- no probe")
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
