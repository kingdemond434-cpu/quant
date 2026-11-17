"""The gateway lifts ONLY its own placement auto-pause, only after a passed probe and a backoff."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import pause_rearm as pr

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def _setup(tmp: Path, body: str, paused_at: datetime, probe_at: datetime | None,
           rearms: list[datetime] | None = None) -> tuple[Path, Path, Path]:
    paused, ok, hist = tmp / "GATEWAY_PAUSED", tmp / "terminal_boot_ok.json", tmp / "h.json"
    paused.write_text(body, encoding="utf-8")
    os.utime(paused, (paused_at.timestamp(), paused_at.timestamp()))
    if probe_at is not None:
        ok.write_text(json.dumps({"at": probe_at.isoformat()}), encoding="utf-8")
    if rearms:
        hist.write_text(json.dumps({"rearms": [t.isoformat() for t in rearms]}), encoding="utf-8")
    return paused, ok, hist


AUTO = "AUTO-PAUSED 2026-11-17 12:00: 2 consecutive placement passes with ZERO accepted orders.\n"


def test_own_pause_lifts_after_probe_and_backoff(tmp_path: Path) -> None:
    paused, ok, hist = _setup(tmp_path, AUTO, T0, T0 + timedelta(minutes=20))
    v = pr.maybe_rearm(paused, ok, hist, now=T0 + timedelta(minutes=31))
    assert v["rearm"] is True and not paused.exists()
    assert len(json.loads(hist.read_text())["rearms"]) == 1


def test_a_person_s_pause_is_never_touched(tmp_path: Path) -> None:
    for body in ("paused by hand for the NFP\n", "Fusion ruin rail: daily loss breach\n", ""):
        paused, ok, hist = _setup(tmp_path, body, T0, T0 + timedelta(minutes=20))
        v = pr.maybe_rearm(paused, ok, hist, now=T0 + timedelta(hours=10))
        assert v["rearm"] is False and paused.exists(), body


def test_no_probe_pass_since_the_pause_holds(tmp_path: Path) -> None:
    paused, ok, hist = _setup(tmp_path, AUTO, T0, T0 - timedelta(minutes=5))
    assert pr.maybe_rearm(paused, ok, hist, now=T0 + timedelta(hours=2))["rearm"] is False
    paused, ok, hist = _setup(tmp_path, AUTO, T0, None)
    ok.unlink(missing_ok=True)
    v = pr.maybe_rearm(paused, ok, hist, now=T0 + timedelta(hours=2))
    assert v["rearm"] is False and "UNMEASURED" in v["why"] and paused.exists()


def test_a_stale_probe_pass_holds(tmp_path: Path) -> None:
    paused, ok, hist = _setup(tmp_path, AUTO, T0, T0 + timedelta(minutes=1))
    v = pr.maybe_rearm(paused, ok, hist, now=T0 + timedelta(minutes=1 + pr.BOOT_OK_MAX_AGE_MIN + 1))
    assert v["rearm"] is False and paused.exists()


def test_backoff_doubles_per_rearm_in_24h_and_caps(tmp_path: Path) -> None:
    probe = T0 + timedelta(minutes=5)
    paused, ok, hist = _setup(tmp_path, AUTO, T0, probe, rearms=[T0 - timedelta(hours=3)] * 2)
    v = pr.decide(paused, ok, hist, now=T0 + timedelta(minutes=60))
    assert v["rearm"] is False and v["backoff_min"] == 120.0
    paused, ok, hist = _setup(tmp_path, AUTO, T0, T0 + timedelta(minutes=479),
                              rearms=[T0 - timedelta(hours=1)] * 9)
    v = pr.decide(paused, ok, hist, now=T0 + timedelta(minutes=481))
    assert v["backoff_min"] == pr.REARM_CAP_MIN and v["rearm"] is True
    # re-arms older than a day no longer count
    paused, ok, hist = _setup(tmp_path, AUTO, T0, probe, rearms=[T0 - timedelta(days=2)] * 5)
    assert pr.decide(paused, ok, hist, now=T0 + timedelta(minutes=31))["backoff_min"] == 30.0


def test_the_loop_lifts_before_the_gateway_reads_the_pause() -> None:
    desk = Path(__file__).resolve().parent.parent
    loop = (desk / "research" / "run_gateway_loop.py").read_text("utf-8")
    body = loop[loop.index("def main() -> None:"):]
    assert body.index('getattr(gateway, "_lift_own_auto_pause", None)') < body.index(
        "lift()") < body.index("gateway.main()")
    src = (desk / "mt5desk" / "gateway.py").read_text("utf-8")
    lift = src[src.index("def _lift_own_auto_pause"):src.index("def main() -> None:")]
    assert "JOURNAL GATEWAY AUTO RE-ARMED" in lift and "GATEWAY_AUTO_REARMED" in lift
    # main() itself is unchanged: its first statement is still the pause read (audit E13)
    main = src[src.index("def main() -> None:"):]
    assert main.split("\n")[1].strip() == "if gateway_paused():"
    # the writer's tag is the reader's tag
    assert f'f"{pr.PAUSE_TAG} {{now()}}' in src
