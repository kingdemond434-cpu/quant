"""combined_prop_risk: report-only rule matrix and gold_asia joint worst case (IDEA_QUEUE 207).

Every test runs against files written into tmp_path. Nothing reads the live account files, so a
test can never pass because of today's state.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_spec = importlib.util.spec_from_file_location(
    "combined_prop_risk", DESK / "research" / "combined_prop_risk.py")
cpr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpr)

NOW = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)

GUARD_SRC = '''
START_BALANCE = 100_000.0
PROFIT_TARGET = 0.10
STATIC_DRAWDOWN = 0.10
DAILY_DRAWDOWN = 0.025
DAILY_PROFIT_CAP = 0.02
SERVER_ANCHOR_TZ = "America/New_York"
SERVER_MIDNIGHT_ET_HOUR = 17
'''
DEADMAN_SRC = "DAILY_LOSS_PCT = 0.10\nEQUITY_FLOOR_EUR = 300.0\n"


def _w(p: Path, obj) -> Path:
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return p


@pytest.fixture
def files(tmp_path: Path) -> dict[str, Path]:
    return {
        "guard_src": _w(tmp_path / "e8_guard.py", GUARD_SRC),
        "guard_report": tmp_path / "E8_GUARD.json",
        "guard_state": tmp_path / "e8_guard_state.json",
        "ftmo_manual": tmp_path / "ftmo_manual_state.json",
        "deadman_src": _w(tmp_path / "fusion_deadman.py", DEADMAN_SRC),
        "deadman_state": _w(tmp_path / "dm.json", {"peak_equity": 600.0,
                                                    "checked_at": NOW.isoformat()}),
        "account": _w(tmp_path / "acct.json", {"updated_at": NOW.isoformat(), "equity": 500.0,
                                                "today_pnl": -20.0}),
    }


def test_absent_e8_and_ftmo_state_is_unmeasured_never_zero(files):
    rep = cpr.build(NOW, **files)
    for name in ("E8", "FTMO"):
        blk = rep["accounts"][name]
        assert blk["state"]["status"] == "UNMEASURED"
        assert blk["room"]["room_to_daily_floor_frac"] == "UNMEASURED"
        assert blk["room"]["room_to_static_floor_frac"] == "UNMEASURED"
        h = blk["gold_asia_worst_case"]["scenarios"]["both_legs_plus_1.5R_gap"]
        assert h["breaches_current_daily_room"] == "UNMEASURED"
    assert rep["status"] == "PARTIAL"
    assert "E8 state UNMEASURED" in rep["gaps"]
    assert rep["report_only"] is True


def test_worst_case_numbers_against_daily_limits(files):
    rep = cpr.build(NOW, **files)
    e8 = rep["accounts"]["E8"]["gold_asia_worst_case"]["scenarios"]
    # 0.006 per leg of a 100k initial: 1,200 / 1,800 / 2,100 -- published as fractions only
    assert e8["both_legs_stopped_2R"]["loss_frac"] == pytest.approx(0.012)
    assert e8["each_leg_gapped_to_1.5R"]["loss_frac"] == pytest.approx(0.018)
    assert e8["both_legs_plus_1.5R_gap"]["loss_frac"] == pytest.approx(0.021)
    assert e8["both_legs_plus_1.5R_gap"]["frac_of_daily_limit"] == pytest.approx(0.84)
    ft = rep["accounts"]["FTMO"]["gold_asia_worst_case"]["scenarios"]
    assert ft["both_legs_plus_1.5R_gap"]["loss_frac"] == pytest.approx(0.0315)
    assert ft["both_legs_plus_1.5R_gap"]["frac_of_daily_limit"] == pytest.approx(0.63)
    assert rep["joint_worst_case"]["any_account_breaches_full_daily_limit"] is False


def test_larger_e8_leg_breaches_full_daily_limit(files):
    rep = cpr.build(NOW, e8_leg_risk=0.008, **files)   # 3.5 x 0.8% = 2.8% > 2.5%
    assert rep["joint_worst_case"]["per_account"]["E8"]["breaches_full_daily_limit"] is True
    assert rep["joint_worst_case"]["any_account_breaches_full_daily_limit"] is True


def test_e8_published_state_gives_rooms_and_current_room_breach(files):
    _w(files["guard_report"], {"equity": 99_000.0, "day_start": 100_500.0,
                               "checked_at": (NOW - timedelta(hours=1)).isoformat()})
    rep = cpr.build(NOW, **files)
    e8 = rep["accounts"]["E8"]
    assert e8["state"]["status"] == "MEASURED"
    # daily floor = 100500 - 2500 = 98000; room = 1000. static floor 90000; room 9000.
    # Published as fractions of the 100k initial balance.
    assert e8["room"]["room_to_daily_floor_frac"] == pytest.approx(0.01)
    assert e8["room"]["room_to_static_floor_frac"] == pytest.approx(0.09)
    h = e8["gold_asia_worst_case"]["scenarios"]["both_legs_plus_1.5R_gap"]
    assert h["breaches_current_daily_room"] is True


def test_stale_state_is_not_claimed_against_current_room(files):
    _w(files["guard_report"], {"equity": 99_000.0, "day_start": 100_000.0,
                               "checked_at": (NOW - timedelta(days=2)).isoformat()})
    rep = cpr.build(NOW, **files)
    e8 = rep["accounts"]["E8"]
    assert e8["state"]["status"] == "STALE"
    h = e8["gold_asia_worst_case"]["scenarios"]["both_legs_plus_1.5R_gap"]
    assert h["breaches_current_daily_room"] == "STALE"


def test_ftmo_hand_file_phase_target_and_trading_days(files):
    _w(files["ftmo_manual"], {"entered_at": NOW.isoformat(), "phase": 2,
                              "initial_balance": 100_000, "balance": 103_000,
                              "equity": 102_500, "day_start_balance": 103_000,
                              "trading_days": 3})
    rep = cpr.build(NOW, **files)
    st = rep["accounts"]["FTMO"]["state"]
    assert st["status"] == "MEASURED"
    assert st["profit_target"] == 0.05
    # equity 102,500 on 100k with a 5% target: 2.5% of 5% = half way
    assert st["progress_to_target_frac"] == pytest.approx(0.5)
    assert st["trading_days"] == {"count": 3, "minimum": 4, "remaining": 1}
    room = rep["accounts"]["FTMO"]["room"]
    assert room["room_to_daily_floor_frac"] == pytest.approx((102_500 - 98_000) / 100_000)
    assert room["room_to_static_floor_frac"] == pytest.approx(12_500 / 100_000)


def test_ftmo_file_with_credential_key_is_refused(files):
    _w(files["ftmo_manual"], {"entered_at": NOW.isoformat(), "equity": 100_000,
                              "login": "123", "phase": 1})
    rep = cpr.build(NOW, **files)
    st = rep["accounts"]["FTMO"]["state"]
    assert st["status"] == "REFUSED"
    assert st["equity"] == "UNMEASURED"
    assert "123" not in json.dumps(rep)


def test_reset_clocks(files):
    rep = cpr.build(NOW, **files)
    e8 = rep["accounts"]["E8"]["reset_clock"]
    assert e8["status"] == "MEASURED" and e8["tz"] == "America/New_York"
    # 2026-10-21 is EDT (UTC-4): 17:00 NY = 21:00 UTC.
    assert e8["next_reset_utc"] == "2026-10-21T21:00:00+00:00"
    assert rep["accounts"]["FTMO"]["reset_clock"]["status"] == "UNMEASURED"
    assert "FTMO reset clock UNMEASURED" in rep["gaps"]


def test_e8_reset_follows_dst():
    winter = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)
    assert cpr.next_reset(winter, "America/New_York", 17) == datetime(2026, 12, 1, 22, 0,
                                                                       tzinfo=UTC)


def test_fusion_deadman_rules_from_config_and_leg_risk_optional(files):
    rep = cpr.build(NOW, **files)
    fu = rep["accounts"]["FUSION"]
    assert fu["rules"]["deadman_equity_floor"] == "parsed"
    # equity 500, floor 300 (the test's own deadman file), peak 600, today -20
    assert fu["room"]["room_to_deadman_floor_frac"] == pytest.approx((500 - 300) / 500)
    assert fu["room"]["room_to_daily_rail_frac"] == pytest.approx((0.10 * 600 - 20) / 500)
    assert fu["gold_asia_worst_case"]["status"] == "UNMEASURED"
    rep2 = cpr.build(NOW, fusion_leg_risk=0.03, **files)
    assert rep2["accounts"]["FUSION"]["gold_asia_worst_case"]["status"] == "MEASURED"


def test_missing_deadman_config_is_unmeasured(files, tmp_path):
    files["deadman_src"] = tmp_path / "nope.py"
    rep = cpr.build(NOW, **files)
    fu = rep["accounts"]["FUSION"]
    assert fu["rules"]["deadman_equity_floor"] == "UNMEASURED"
    assert fu["room"]["room_to_deadman_floor_frac"] == "UNMEASURED"


def test_reads_real_e8_guard_constants_by_parsing():
    c = cpr.read_constants(cpr.E8_GUARD_SRC, tuple(cpr.E8_SPEC))
    assert c["DAILY_DRAWDOWN"] == 0.025 and c["STATIC_DRAWDOWN"] == 0.10
    assert c["SERVER_MIDNIGHT_ET_HOUR"] == 17


def test_write_is_atomic_json(files, tmp_path):
    out = cpr.write(cpr.build(NOW, **files), tmp_path / "r" / "COMBINED_PROP_RISK.json")
    assert json.loads(out.read_text())["artifact"] == "COMBINED_PROP_RISK"


def test_published_report_carries_no_money_figure(files):
    _w(files["guard_report"], {"equity": 99_123.0, "day_start": 100_456.0,
                               "checked_at": (NOW - timedelta(hours=1)).isoformat()})
    _w(files["ftmo_manual"], {"entered_at": NOW.isoformat(), "phase": 1, "equity": 101_789,
                              "day_start_balance": 101_000, "trading_days": 2})
    rep = cpr.build(NOW, fusion_leg_risk=0.03, **files)
    blob = json.dumps(rep)
    for amount in ("99123", "100456", "101789", "101000", "100000", "500.0", "600.0", "_usd",
                   "$"):
        assert amount not in blob, amount


@pytest.mark.skipif(shutil.which("git") is None, reason="git unavailable")
def test_the_hand_entered_ftmo_state_and_its_temp_siblings_are_gitignored():
    """MF3: the FTMO balance/equity file is operator money; git must never be able to track it."""
    root = cpr.FTMO_MANUAL.resolve().parents[3]
    rel = cpr.FTMO_MANUAL.resolve().relative_to(root).as_posix()
    assert rel == "desks/mt5/data/ftmo_manual_state.json"
    for path in (rel, rel + ".tmp", "desks/mt5/data/ftmo_manual_state.tmp"):
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", path],
                           capture_output=True, timeout=30, check=False)
        assert r.returncode in (0, 1), r.stderr
        assert r.returncode == 0, f"{path} is not gitignored"
