"""The halt-rail fence must name the two things that hid an 11.7-day halt in plain sight.

THE DETECTOR IS TESTED, NOT JUST THE DEFECT (constitution 23: "fix the defect, determine why it
escaped, improve detection, TEST the detector"). Each case here is one of the readings that was
wrong on the box on 2026-11-11:

  * the halt's age taken from a marker its own writer rewrites every five minutes -> 0.0 days;
  * a rail judging a `gateway_state.json` the halt itself froze -> five of seven rails unreachable;
  * the loop wrapper's process-recycle line read as a live gateway pass -> 11.7 days dated as 2.0.
"""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "check_halt_rail_integrity", ROOT / "scripts" / "check_halt_rail_integrity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tree(tmp_path: Path, *, paused: bool, state: dict | None, stamp: dict | None,
          log_lines: list[str] | None = None) -> Path:
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    (desk / "logs").mkdir(parents=True)
    (desk / "reports").mkdir(parents=True)
    if paused:
        (desk / "data" / "GATEWAY_PAUSED").write_text(
            "AUTO-HALTED 2026-11-11T12:00:39+00:00 by the Fusion ruin rail.\n", encoding="utf-8")
    if state is not None:
        (desk / "data" / "gateway_state.json").write_text(json.dumps(state), encoding="utf-8")
    if stamp is not None:
        (desk / "data" / "fusion_deadman_state.json").write_text(json.dumps(stamp),
                                                                 encoding="utf-8")
    if log_lines:
        (desk / "logs" / "gateway.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return tmp_path


def _paused_log(start: datetime, n: int, *, every_min: int = 1,
                recycle_at: int | None = None) -> list[str]:
    """`n` paused passes from `start`, with the wrapper's recycle line among them if asked."""
    out = [f"{(start - timedelta(minutes=5)).isoformat()} state: armed=True pos=0 pending=0"]
    for i in range(n):
        at = start + timedelta(minutes=i * every_min)
        if recycle_at is not None and i == recycle_at:
            out.append(f"{at.isoformat()} RESIDENT: started pid 14904; loop wrapper recycle")
        out.append(f"{at.isoformat()} gateway paused (data/GATEWAY_PAUSED present); "
                   f"no trading this pass")
    return out


def test_halt_age_comes_from_the_log_not_the_marker_mtime(tmp_path):
    """The marker is minutes old and the halt is days old. Both are reported, and they differ."""
    mod = _module()
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    start = now - timedelta(days=11, hours=16)
    root = _tree(tmp_path, paused=True,
                 state={"equity": 266.01, "last_reconcile": "2026-10-30T19:50:13+00:00",
                        "position": None, "day_start_equity": {"date": "2026-10-30"}},
                 stamp={"mode": "LIVE", "halt_codes": ["EQUITY_FLOOR"],
                        "readings": {"equity": 266.01}},
                 log_lines=_paused_log(start, 400, every_min=42))
    mod._rebind(root)
    rep = mod.measure(now=now, write_origin=False)

    assert rep["halt"]["halted"] is True
    assert rep["halt"]["halt_days"] > 10, rep["halt"]
    # The marker was written by the test seconds ago; the halt is eleven days old. The old fence
    # reported the first number as the second.
    assert rep["halt"]["marker_age_min"] < 60
    assert rep["halt"]["marker_age_is_not_halt_age"] is True
    assert any("MARKER AGE IS NOT HALT AGE" in b for b in rep["breaches"])


def test_the_loop_wrappers_recycle_line_does_not_end_the_halt(tmp_path):
    """RESIDENT: started is the wrapper recycling, never a pass that traded."""
    mod = _module()
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    start = now - timedelta(days=11)
    root = _tree(tmp_path, paused=True, state={"equity": 266.01}, stamp=None,
                 log_lines=_paused_log(start, 300, every_min=52, recycle_at=290))
    mod._rebind(root)
    rep = mod.measure(now=now, write_origin=False)
    # Without the TRANSPARENT rule the recycle at pass 290 would date the halt at ~9 hours.
    assert rep["halt"]["halt_days"] > 10, rep["halt"]
    assert rep["halt"]["paused_passes"] == 300


def test_every_rail_the_frozen_input_cannot_reach_is_named(tmp_path):
    """Five of seven, exactly as measured on the box: the census names each one and its key."""
    mod = _module()
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    root = _tree(tmp_path, paused=True,
                 state={"equity": 266.01, "last_reconcile": "2026-10-30T19:50:13+00:00",
                        "position": None, "day_start_equity": {"date": "2026-10-30",
                                                               "equity": 457.74}},
                 stamp={"mode": "LIVE", "readings": {"equity": 266.01}},
                 log_lines=_paused_log(now - timedelta(days=11), 50, every_min=300))
    mod._rebind(root)
    rep = mod.measure(now=now, write_origin=False)

    assert set(rep["rails_unreachable"]) == {"DAILY_LOSS", "MARGIN", "POSITION_COUNT",
                                             "SIZE_GUARD", "STALE_HEARTBEAT"}
    assert rep["rails_reachable"] == 2
    by = {r["rail"]: r for r in rep["rails"]}
    assert "margin_free" in by["MARGIN"]["why"]
    assert "day_start_equity" in by["DAILY_LOSS"]["why"]
    # WEEKLY_LOSS reads the live ledger, so a frozen gateway_state.json never silences it.
    assert by["WEEKLY_LOSS"]["verdict"] == "REACHABLE"
    # The input names no account at all -- the rail judges an equity with nothing attached.
    assert rep["rail_input"]["carries_account_identity"] is False


def test_the_latch_is_named_when_the_halt_outlives_its_own_input(tmp_path):
    mod = _module()
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    root = _tree(tmp_path, paused=True, state={"equity": 266.01},
                 stamp={"mode": "LIVE", "readings": {"equity": 266.01}},
                 log_lines=_paused_log(now - timedelta(days=11), 20, every_min=700))
    mod._rebind(root)
    # The state file was written by the test just now, so it is NOT older than the halt.
    rep = mod.measure(now=now, write_origin=False)
    assert rep["latched"] is False, "a fresh input is not a latch, however long the halt"

    # Age it past the halt: now the clear condition cannot be observed any more.
    old = (now - timedelta(days=12)).timestamp()
    os.utime(root / "desks" / "mt5" / "data" / "gateway_state.json", (old, old))
    rep = mod.measure(now=now, write_origin=False)
    assert rep["latched"] is True
    assert rep["verdict"] == "RED"
    assert any("HALT LATCHED" in b for b in rep["breaches"])
    assert rep["rail_stamp"]["quotes_frozen_input"] is True


def test_a_healthy_unhalted_desk_is_clean_and_drops_the_origin(tmp_path):
    mod = _module()
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    root = _tree(tmp_path, paused=False,
                 state={"equity": 99578.18, "margin_free": 98693.75,
                        "position": [{"ticket": 1, "volume": 0.12}],
                        "day_start_equity": {"date": "PLACEHOLDER", "equity": 99666.0},
                        "last_reconcile": now.isoformat()},
                 stamp={"mode": "LIVE", "readings": {"equity": 99578.18}})
    mod._rebind(root)
    # The opening-balance anchor must be dated to the rail's own broker day to be reachable.
    state_path = root / "desks" / "mt5" / "data" / "gateway_state.json"
    doc = json.loads(state_path.read_text(encoding="utf-8"))
    doc["day_start_equity"]["date"] = mod._broker_day(now)
    state_path.write_text(json.dumps(doc), encoding="utf-8")

    origin = root / "desks" / "mt5" / "data" / "halt_origin.json"
    origin.write_text(json.dumps({"halt_since": "2026-10-30T19:51:04+00:00"}), encoding="utf-8")
    rep = mod.measure(now=now, write_origin=True)

    assert rep["halt"]["halted"] is False
    assert rep["halt"]["halt_since"] is None
    assert not origin.exists(), "a cleared halt must not leave its origin behind to be re-read"
    assert rep["rails_unreachable"] == []
    assert rep["verdict"] == "OK"
    assert rep["breaches"] == []


def test_an_unreadable_input_is_unmeasured_never_ok(tmp_path):
    """L1.28a: the rail judging nothing is a verdict of its own, not a quiet pass."""
    mod = _module()
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    root = _tree(tmp_path, paused=True, state=None, stamp=None)
    mod._rebind(root)
    rep = mod.measure(now=now, write_origin=False)
    assert rep["verdict"] == "UNMEASURED"
    assert any("RAIL INPUT UNMEASURED" in b for b in rep["breaches"])
    assert all(r["verdict"] == "UNMEASURED" for r in rep["rails"] if r["rail"] != "WEEKLY_LOSS")


def test_the_fence_never_touches_the_halt(tmp_path):
    """It measures and names. Clearing a halt places live orders and is the principal's act."""
    mod = _module()
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    root = _tree(tmp_path, paused=True, state={"equity": 266.01}, stamp=None,
                 log_lines=_paused_log(now - timedelta(days=11), 10, every_min=1400))
    mod._rebind(root)
    marker = root / "desks" / "mt5" / "data" / "GATEWAY_PAUSED"
    before = marker.read_bytes()
    stamp = root / "desks" / "mt5" / "data" / "fusion_deadman_state.json"
    mod.measure(now=now, write_origin=True)
    assert marker.exists() and marker.read_bytes() == before
    assert not stamp.exists(), "the fence must never create or write the rail's stamp"
