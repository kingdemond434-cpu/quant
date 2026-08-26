"""The brain quota memo must skip probes inside a measured wall and NEVER outlive it.

WHY THIS TEST EXISTS. On 2026-08-26 `scripts/check_seat_launch_yield.py --days 7` measured 94
billable seat launches for 26 real digs (27.7%), with AUTH_UNAVAILABLE alone accounting for 55.
Every one of those walked the full model chain probe-by-probe into a wall a previous organ had
already measured precisely -- `brain_reset_wait_s` computed the reset stamp, slept on it once,
and discarded it. The memo persists that stamp. The properties below are the ones that make it a
memo rather than a rail: it must expire, it must be capped so a bad parse cannot silence the
desk, it must clear on success, and a human must be able to override it.

Shelling out to bash is the point -- these functions live in ops/brain_env.sh and the desk has
been bitten before by "tests kept, code dropped": a python re-implementation would pass while the
shell the organs actually source was broken.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / "ops" / "brain_env.sh"


def _run(script: str, memo: Path, log: Path, **env: str) -> subprocess.CompletedProcess[str]:
    pre = (
        f'_BRAIN_QUOTA_MEMO="{memo}"; _BRAIN_QUOTA_LOG="{log}"; '
        f'_BRAIN_NO_DOCTRINE=1; source "{ENV}" >/dev/null 2>&1 || true; '
    )
    out = subprocess.run(
        ["bash", "-c", pre + script],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
        env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), **env},
    )
    # POSITIVE CONTROL, and it is not decorative: while writing these tests a concurrent pytest
    # run reverted ops/brain_env.sh underneath them, the functions vanished, and every
    # `... && echo BLOCKED || echo GO` assertion went on PASSING -- because an undefined function
    # exits 127, which the `||` reads as "not blocked". The vacuous green is the failure mode
    # this harness is most exposed to, so it is checked on every single invocation.
    assert "command not found" not in out.stderr, (
        f"brain_env.sh did not define the function under test -- a GO result here would be "
        f"vacuous, not a pass:\n{out.stderr[:400]}"
    )
    return out


@pytest.fixture()
def memo(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "quota.json", tmp_path / "windows.jsonl"


def test_no_memo_means_go(memo: tuple[Path, Path]) -> None:
    """Absence is never a wall -- an unwritten memo must not gate a single probe."""
    m, lg = memo
    assert _run("brain_quota_blocked && echo BLOCKED || echo GO", m, lg).stdout.strip() == "GO"


def test_recorded_block_gates_the_probe_and_expires(memo: tuple[Path, Path]) -> None:
    m, lg = memo
    until = int(time.time()) + 900
    out = _run(f"brain_quota_record blocked {until} testorgan 'session limit'; "
               "brain_quota_blocked && echo BLOCKED || echo GO", m, lg)
    assert out.stdout.strip() == "BLOCKED", out
    row = json.loads(m.read_text())
    assert row["state"] == "blocked" and row["blocked_until_epoch"] == until
    assert row["organ"] == "testorgan"

    past = int(time.time()) - 60
    out = _run(f"brain_quota_record blocked {past} testorgan x; "
               "brain_quota_blocked && echo BLOCKED || echo GO", m, lg)
    assert out.stdout.strip() == "GO", "an elapsed wall must not keep gating probes"


def test_memo_further_out_than_any_real_window_is_distrusted(memo: tuple[Path, Path]) -> None:
    """A parse fault must cost a probe, never a day of digs (over-blocking is the worse error)."""
    m, lg = memo
    until = int(time.time()) + 60 * 60 * 24
    out = _run(f"brain_quota_record blocked {until} testorgan x; "
               "brain_quota_blocked && echo BLOCKED || echo GO", m, lg)
    assert out.stdout.strip() == "GO"


def test_open_observation_clears_the_wall(memo: tuple[Path, Path]) -> None:
    m, lg = memo
    until = int(time.time()) + 900
    out = _run(f"brain_quota_record blocked {until} o1 x; brain_quota_record open 0 o1 PING-OK; "
               "brain_quota_blocked && echo BLOCKED || echo GO", m, lg)
    assert out.stdout.strip() == "GO"


def test_human_override_always_wins(memo: tuple[Path, Path]) -> None:
    m, lg = memo
    until = int(time.time()) + 900
    out = _run(f"brain_quota_record blocked {until} o1 x; "
               "brain_quota_blocked && echo BLOCKED || echo GO", m, lg,
               BRAIN_IGNORE_QUOTA_MEMO="1")
    assert out.stdout.strip() == "GO"


def test_window_log_records_transitions_not_every_probe(memo: tuple[Path, Path]) -> None:
    """The jsonl is for a future scheduler: it needs when the wall moved, not how often we asked."""
    m, lg = memo
    until = int(time.time()) + 900
    _run(f"brain_quota_record blocked {until} o1 x; brain_quota_record blocked {until} o2 x; "
         f"brain_quota_record blocked {until} o3 x; brain_quota_record open 0 o4 PING-OK", m, lg)
    rows = [json.loads(x) for x in lg.read_text().splitlines() if x.strip()]
    assert [r["state"] for r in rows] == ["blocked", "open"], rows


def test_functions_are_actually_defined(memo: tuple[Path, Path]) -> None:
    """The harness's own falsifier: if the shell stops defining these, say so loudly."""
    m, lg = memo
    out = _run("type -t brain_quota_record; type -t brain_quota_blocked", m, lg)
    assert out.stdout.split() == ["function", "function"], out


# --- the CONSUMER half: scripts/check_seat_launch_yield.quota_walls -------------------------
# A memo nothing reads is an opinion (III.16). These pin the two properties that make the
# fence's reading honest: absence must report UNMEASURED rather than a comfortable zero, and a
# wall straddling the window edge must be clipped rather than double counted.

def test_quota_walls_reports_unmeasured_when_nothing_recorded(monkeypatch, tmp_path) -> None:
    import scripts.check_seat_launch_yield as slj
    monkeypatch.setattr(slj, "QUOTA_LOG", tmp_path / "absent.jsonl")
    out = slj.quota_walls(time.time() - 3600, time.time())
    assert out["recorded"] is False
    assert "blocked_hours" not in out, "absence must not be reported as zero hours (L1.28a)"


def test_quota_walls_clips_to_the_measurement_window(monkeypatch, tmp_path) -> None:
    import scripts.check_seat_launch_yield as slj
    now = time.time()
    since = now - 3600.0
    lg = tmp_path / "w.jsonl"
    # a 2h wall that opened an hour BEFORE the window: only the in-window hour may be counted
    lg.write_text(json.dumps({
        "state": "blocked",
        "observed_at_epoch": since - 3600,
        "blocked_until_epoch": since + 3600,
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(slj, "QUOTA_LOG", lg)
    out = slj.quota_walls(since, now)
    assert out["recorded"] is True and out["walls_in_window"] == 1
    assert abs(float(out["blocked_hours"]) - 1.0) < 0.05, out
