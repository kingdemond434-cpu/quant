"""The allocator's HEAVY admission scan runs every 4th hour (2026-10-21), and nothing that
reads the scan's stamp expires it before the next heavy pass lands."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "research"))
sys.path.insert(0, str(HERE.parent))

import hourly_cycle  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 5, tzinfo=UTC)
#: The slack a consumer's expiry must clear above the cadence: one missed hourly pass plus margin.
SLACK_S = 1800.0


def _art(tmp_path: Path, age: timedelta) -> Path:
    p = tmp_path / "pf_allocation.json"
    p.write_text(json.dumps({"admission": {"status": "MEASURED",
                                           "measured_utc": (NOW - age).isoformat()}}), "utf-8")
    return p


def test_heavy_runs_once_every_four_hourly_passes(tmp_path: Path) -> None:
    # A scan stamped ~5 min into the 08:00 pass; the cycle then wakes at 09, 10, 11, 12.
    modes = [hourly_cycle._allocator_mode_for_the_hour(
        _art(tmp_path, timedelta(hours=h, minutes=-3)), NOW) for h in (1, 2, 3, 4)]
    assert modes == ["normal", "normal", "normal", "heavy"]


def test_cadence_is_four_hours() -> None:
    assert hourly_cycle.ADMISSION_SCAN_HEAVY_CADENCE_S == 4 * 3600.0
    assert 3 * 3600.0 < hourly_cycle.ADMISSION_SCAN_MAX_AGE_S <= 4 * 3600.0


def test_every_consumer_expiry_exceeds_the_heavy_cadence() -> None:
    import pf_allocator
    import promoter

    floor = hourly_cycle.ADMISSION_SCAN_HEAVY_CADENCE_S + SLACK_S
    assert pf_allocator.ADMISSION_MAX_AGE_S > floor
    assert promoter.ADMISSION_MAX_AGE_H * 3600.0 > floor


def test_a_3h29m_old_scan_stays_normal_and_3h31m_goes_heavy(tmp_path: Path) -> None:
    assert hourly_cycle._allocator_mode_for_the_hour(
        _art(tmp_path, timedelta(hours=3, minutes=29)), NOW) == "normal"
    assert hourly_cycle._allocator_mode_for_the_hour(
        _art(tmp_path, timedelta(hours=3, minutes=31)), NOW) == "heavy"


def _run_hourly(tmp_path: Path, leg_offset_min: list[int], hours: int = 24) -> list[int]:
    """Simulate hourly passes starting on the hour, the allocator leg finishing `offset` minutes
    in (varying per pass). Returns the hours at which heavy ran."""
    art = tmp_path / "pf_allocation.json"
    hp = tmp_path / "admission_heavy_pass.json"
    t0 = datetime(2026, 10, 21, 0, 0, tzinfo=UTC)
    heavy_at: list[int] = []
    for h in range(hours):
        start = t0 + timedelta(hours=h)
        if hourly_cycle._allocator_mode_for_the_hour(art, start, heavy_pass=hp) == "heavy":
            done = start + timedelta(minutes=leg_offset_min[h % len(leg_offset_min)])
            art.write_text(json.dumps({"admission": {"status": "MEASURED",
                                                     "measured_utc": done.isoformat()}}), "utf-8")
            assert hourly_cycle._stamp_heavy_pass({"exit_code": 0}, art, hp, start)
            heavy_at.append(h)
    return heavy_at


def test_age_is_anchored_on_the_pass_start_so_heavy_is_exactly_every_4th_pass(
        tmp_path: Path) -> None:
    # The leg lands anywhere from 5 to 59 minutes into the pass; the cadence must not drift.
    heavy = _run_hourly(tmp_path, [5, 59, 45, 12, 33, 58, 7])
    gaps = {b - a for a, b in zip(heavy, heavy[1:], strict=False)}
    assert gaps == {4}, heavy


def test_without_the_start_stamp_a_late_leg_would_slip(tmp_path: Path) -> None:
    # The audit's failure mode, kept visible: aged off measured_utc, a scan finished 59 min into
    # its pass reads 3h01m at the 4th pass and slips heavy to the 5th.
    assert hourly_cycle._allocator_mode_for_the_hour(
        _art(tmp_path, timedelta(hours=3, minutes=1)), NOW) == "normal"


def test_a_failed_or_carried_heavy_leg_writes_no_stamp(tmp_path: Path) -> None:
    hp = tmp_path / "admission_heavy_pass.json"
    start = NOW - timedelta(minutes=30)
    art = _art(tmp_path, timedelta(minutes=10))
    assert not hourly_cycle._stamp_heavy_pass({"exit_code": 1}, art, hp, start)
    assert not hourly_cycle._stamp_heavy_pass({"exit_code": None}, art, hp, start)
    old = _art(tmp_path, timedelta(hours=2))            # scan predates the pass: not this one
    assert not hourly_cycle._stamp_heavy_pass({"exit_code": 0}, old, hp, start)
    assert not hp.exists()


def test_a_stamp_for_another_scan_is_ignored(tmp_path: Path) -> None:
    art = _art(tmp_path, timedelta(minutes=10))
    hp = tmp_path / "admission_heavy_pass.json"
    hp.write_text(json.dumps({"pass_started_utc": (NOW - timedelta(hours=9)).isoformat(),
                              "measured_utc": "2026-01-01T00:00:00+00:00"}), "utf-8")
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW, heavy_pass=hp) == "normal"


def test_the_supervisor_shares_the_cadence_and_defers_to_a_fresh_scan(tmp_path: Path) -> None:
    import research_supervisor as rs

    pa = next(p for p in rs.PERIODIC if p["name"] == "pf_allocator")
    assert pa["cadence_s"]["heavy"] == hourly_cycle.ADMISSION_SCAN_HEAVY_CADENCE_S
    assert rs.ADMISSION_SCAN_MAX_AGE_S == hourly_cycle.ADMISSION_SCAN_MAX_AGE_S
    art = _art(tmp_path, timedelta(hours=1))
    assert rs._scan_is_fresh(NOW.timestamp(), art)
    assert not rs._scan_is_fresh(NOW.timestamp(), _art(tmp_path, timedelta(hours=4)))
    assert not rs._scan_is_fresh(NOW.timestamp(), tmp_path / "missing.json")


def test_the_cadence_is_billed_as_a_published_line(tmp_path: Path, monkeypatch) -> None:
    from research import missed_growth as mg

    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [{"name": "a", "status": "LIVE"},
                                               {"name": "b", "status": "STANDBY"}]}), "utf-8")
    monkeypatch.setattr(mg, "SLEEVES", sleeves)
    alloc = {"admission": {"status": "MEASURED", "admitted": ["a", "b"],
                           "candidates": {"a": {"delta_elogw_per_day": 0.002},
                                          "b": {"delta_elogw_per_day": 0.0024}}}}
    m = mg.admission_cadence_line(alloc)
    assert m["verdict"] == mg.COSTS and m["waiting"] == ["b"]
    # billed at 2.1/6.1 of the waiting candidates' growth for as long as they wait, which
    # integrates to sum(delta) x 2.1 h per promotion
    assert m["value_logw_per_day"] == round(-0.0024 * 2.1 / 6.1, 12)
    assert mg.admission_cadence_line({})["verdict"] == mg.UNMEASURED
    sleeves.write_text("{torn", "utf-8")
    assert mg.admission_cadence_line(alloc)["verdict"] == mg.UNMEASURED


def test_the_line_rides_missed_growth_and_the_sealed_register_is_untouched() -> None:
    from libs.portfolio.rails import RAILS

    src = (HERE.parent / "research" / "missed_growth.py").read_text("utf-8")
    assert '"admission_scan_cadence": admission_cadence_line(alloc)' in src
    assert "admission_scan_cadence" not in {r.name for r in RAILS}


def test_a_future_or_post_scan_start_stamp_is_ignored(tmp_path: Path) -> None:
    art = _art(tmp_path, timedelta(hours=5))
    scan = json.loads(art.read_text("utf-8"))["admission"]["measured_utc"]
    hp = tmp_path / "admission_heavy_pass.json"
    for start in (NOW + timedelta(days=365), NOW - timedelta(hours=1)):
        hp.write_text(json.dumps({"pass_started_utc": start.isoformat(),
                                  "measured_utc": scan}), "utf-8")
        assert hourly_cycle._allocator_mode_for_the_hour(art, NOW, heavy_pass=hp) == "heavy"


def test_a_fresh_scan_does_not_make_the_supervisor_spin_normal(tmp_path: Path,
                                                                monkeypatch) -> None:
    import research_supervisor as rs

    monkeypatch.setattr(rs, "BASE", tmp_path)
    monkeypatch.setattr(rs, "is_running", lambda match: False)
    monkeypatch.setattr(rs, "_scan_is_fresh", lambda now, art=None: True)
    (tmp_path / "data").mkdir()
    cad = next(p for p in rs.PERIODIC if p["name"] == "pf_allocator")["cadence_s"]
    state: dict = {}
    launched: list[str] = []
    t0 = 1_000_000.0
    for i in range(3 * 3600 // 5):                       # 3 h of 5 s ticks, heavy overdue
        launched += rs.tick_periodic(state, t0 + 5.0 * i, lambda name, args: 1)
    normals = sum(x.endswith(":normal") for x in launched)
    assert "pf_allocator:heavy" not in launched
    assert normals <= 3 * 3600 // cad["normal"] + 1
