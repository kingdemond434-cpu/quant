"""A deposit re-arms Fusion at once; a withdrawn-to-zero account stays halted, quietly.

Principal 2026-11-24: "fusion is 0 balance rn i withdrawed" / "make it so it immedeately ttrades
when i depo". The 30-minute-and-doubling backoff stops a flap across the floor; a flat, halted
account cannot earn its way up, so a fresh reading far above the floor is new money.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture
def fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(
        "_fd_deposit", _DESK / "proposals" / "fusion_deadman.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    paused = tmp_path / "GATEWAY_PAUSED"
    paused.write_text("Fusion ruin rail halt", "utf-8")
    monkeypatch.setattr(mod, "PAUSED", paused)
    lines: list[str] = []
    monkeypatch.setattr(mod, "log", lines.append)
    mod.lines = lines
    return mod


def _stamp(codes=("EQUITY_FLOOR",), cleared_at=None, history=None) -> dict:
    return {"halt_codes": list(codes), "cleared_at": cleared_at,
            "rearm_history": history or {}}


def _line(fd) -> float:
    return fd.EQUITY_FLOOR_EUR * fd.EQUITY_REARM_HYSTERESIS


def test_a_measured_deposit_on_a_flat_book_re_arms_on_the_same_pass(fd) -> None:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    st = _stamp(history={"EQUITY_FLOOR": [now, now, now]})        # backoff would be 240 min
    dep = {"equity": _line(fd) * 2.5, "measured": True, "open_positions": 0}
    assert fd.try_rearm(st, dry_run=False, reading=dep) is True
    assert not fd.PAUSED.exists() and st["halt_codes"] == []
    assert st["rearm_verdict"].startswith("RE-ARMED") and "DEPOSIT" in st["rearm_verdict"]


def test_a_deposit_in_dry_run_states_it_would_re_arm_and_touches_nothing(fd) -> None:
    dep = {"equity": _line(fd) * 3, "measured": True, "open_positions": 0}
    assert fd.try_rearm(_stamp(), dry_run=True, reading=dep) is False
    assert fd.PAUSED.exists()


@pytest.mark.parametrize("reading", [
    {"measured": False, "open_positions": 0},                 # stale reading is no deposit
    {"measured": True, "open_positions": 1},                  # an open book can earn its way up
])
def test_no_fast_path_without_a_fresh_reading_on_a_flat_book(fd, reading) -> None:
    st = _stamp()
    assert fd.try_rearm(st, dry_run=False,
                        reading={**reading, "equity": _line(fd) * 3}) is False
    assert fd.PAUSED.exists()


def test_a_small_recovery_keeps_the_ordinary_backoff(fd) -> None:
    st = _stamp()
    rec = {"equity": _line(fd) * 1.2, "measured": True, "open_positions": 0}
    assert fd.try_rearm(st, dry_run=False, reading=rec) is False
    assert st["cleared_at"] and st["rearm_verdict"].startswith("cleared; backoff")
    st["cleared_at"] = (datetime.now(tz=UTC) - timedelta(minutes=31)).isoformat()
    assert fd.try_rearm(st, dry_run=False, reading=rec) is True


def test_other_halt_codes_never_take_the_deposit_path(fd) -> None:
    st = _stamp(codes=("EQUITY_FLOOR", "DAILY_LOSS"))
    dep = {"equity": _line(fd) * 5, "measured": True, "open_positions": 0}
    assert fd.deposit_detected(st["halt_codes"], dep) is None
    assert fd.try_rearm(st, dry_run=False, reading=dep) is False
    assert fd.PAUSED.exists()


def test_withdrawn_to_zero_stays_halted_and_logs_once(fd) -> None:
    zero = {"equity": 0.0, "measured": True, "open_positions": 0}
    st = _stamp()
    for _ in range(5):
        st["rearm_verdict_prev"] = st.pop("rearm_verdict", None)
        assert fd.try_rearm(st, dry_run=False, reading=zero) is False
        assert st["rearm_verdict"].startswith("HELD awaiting deposit")
    assert fd.PAUSED.exists()
    assert sum("HELD awaiting deposit" in ln for ln in fd.lines) == 1
