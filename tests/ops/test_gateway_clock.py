"""L3 (2026-10-13): gateway_state.json's placement_pass is broker time under a UTC label.

At 15:20 UTC it read 18:20 "+00:00". Every reader now goes through one converter: a stamp marked
`placement_pass_clock: "utc"` is taken as written, a legacy stamp loses the broker offset, and an
unknown offset is UNMEASURED (None), never a guessed zero.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import gateway_clock as gc

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "desks" / "mt5" / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

UTC_NOW = datetime(2026, 10, 13, 15, 20, tzinfo=UTC)
BROKER_STAMP = "2026-10-13T18:20:00+00:00"   # what the gateway writes at 15:20 UTC, EEST


def test_a_legacy_broker_stamp_loses_the_offset() -> None:
    got = gc.placement_pass_utc({"placement_pass": BROKER_STAMP}, offset=lambda: 3)
    assert got == UTC_NOW


def test_a_stamp_marked_utc_is_taken_as_written() -> None:
    doc = {"placement_pass": "2026-10-13T15:20:00+00:00", "placement_pass_clock": "utc"}
    assert gc.placement_pass_utc(doc, offset=lambda: 3) == UTC_NOW


def test_an_unknown_offset_is_unmeasured_never_zero() -> None:
    assert gc.placement_pass_utc({"placement_pass": BROKER_STAMP}, offset=lambda: None) is None


@pytest.mark.parametrize("doc", [None, {}, {"placement_pass": "not a time"}, []])
def test_absent_or_unreadable_is_none(doc: object) -> None:
    assert gc.placement_pass_utc(doc, offset=lambda: 3) is None


def test_live_system_state_reports_the_utc_age(monkeypatch: pytest.MonkeyPatch) -> None:
    import live_system_state as lss  # type: ignore[import-not-found]
    monkeypatch.setattr(gc, "broker_offset_h", lambda: 3)
    monkeypatch.setattr(gc.placement_pass_utc, "__defaults__", (lambda: 3,))
    out = lss._execution_section({"placement_pass": BROKER_STAMP}, None,
                                 UTC_NOW + timedelta(hours=2))
    assert out["last_pass_at"] == "2026-10-13T15:20:00+00:00"
    assert out["last_pass_age_h"] == 2.0          # was -1.0: three hours too young


def test_the_host_role_check_no_longer_sees_a_future_pass(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    import os
    import time

    sys.path.insert(0, str(ROOT / "scripts"))
    import check_self_repair as csr  # type: ignore[import-not-found]
    monkeypatch.setattr(gc.placement_pass_utc, "__defaults__", (lambda: 3,))
    gw = tmp_path / "desks" / "mt5" / "data" / "gateway_state.json"
    gw.parent.mkdir(parents=True)
    # a pass that really happened 2h ago, stamped in broker time (+3): it reads 1h in the FUTURE
    real = datetime.now(UTC) - timedelta(hours=2)
    gw.write_text(json.dumps({"placement_pass": (real + timedelta(hours=3)).isoformat()}), "utf-8")
    os.utime(gw, (time.time(), time.time()))
    assert csr._trading_host(tmp_path) is True        # 2h < 3h: still the trading host
    real = datetime.now(UTC) - timedelta(hours=4)
    gw.write_text(json.dumps({"placement_pass": (real + timedelta(hours=3)).isoformat()}), "utf-8")
    assert csr._trading_host(tmp_path) is False       # was True: a 4h-cold host read as live
