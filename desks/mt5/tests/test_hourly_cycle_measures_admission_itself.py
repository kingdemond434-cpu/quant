"""The hourly roster measures the admission scan when the supervisor has not.

MEASURED 2026-09-08 (trace of the promoted-scalp money path): only `pf_allocator --mode heavy`
runs `marginal_admission`; `fast` and `normal` carry the last heavy scan forward. The scan is
what lets a PROMOTION_CANDIDATE leave STANDBY (`promoter.reconcile_capital` reads it), and heavy
had exactly one scheduler -- the persistent MT5-ResearchSupervisor worker (cadence 3600s). If
that worker is dead or stalled, no scalp sleeve can ever go LIVE, and every artifact reads
healthy because `normal` keeps re-stamping the old scan as carried.

The hourly roster is on a clock the box owns (MT5-Hourly). It now asks for `heavy` whenever the
last MEASURED scan is missing or older than twice the supervisor's cadence. A scheduling
redundancy: no admission rule, threshold or budget changes.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle  # noqa: E402

NOW = datetime(2026, 9, 8, 18, 0, tzinfo=UTC)


def _art(tmp_path: Path, admission: dict | None) -> Path:
    p = tmp_path / "pf_allocation.json"
    p.write_text(json.dumps({"admission": admission} if admission is not None else {}), "utf-8")
    return p


def test_no_artifact_means_heavy(tmp_path: Path) -> None:
    assert hourly_cycle._allocator_mode_for_the_hour(tmp_path / "missing.json", NOW) == "heavy"


def test_an_unmeasured_scan_means_heavy(tmp_path: Path) -> None:
    art = _art(tmp_path, {"status": "not measured on this clock", "candidates": {}})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "heavy"


def test_a_fresh_measured_scan_keeps_the_hourly_normal(tmp_path: Path) -> None:
    art = _art(tmp_path, {"status": "MEASURED",
                          "measured_utc": (NOW - timedelta(minutes=50)).isoformat()})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "normal"


def test_a_scan_older_than_two_supervisor_passes_means_heavy(tmp_path: Path) -> None:
    art = _art(tmp_path, {"status": "MEASURED",
                          "measured_utc": (NOW - timedelta(hours=2, minutes=1)).isoformat()})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "heavy"


def test_a_carried_scan_ages_from_its_real_measurement(tmp_path: Path) -> None:
    """`normal` re-stamps measured_utc? No -- it copies the old doc and adds carried_from, so
    the honest age is carried_from's. A carried scan must not read as fresh forever."""
    art = _art(tmp_path, {"status": "MEASURED",
                          "measured_utc": (NOW - timedelta(hours=5)).isoformat(),
                          "carried_from": (NOW - timedelta(hours=5)).isoformat(),
                          "carried_by": "normal"})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "heavy"


def test_the_window_is_twice_the_supervisor_cadence() -> None:
    assert hourly_cycle.ADMISSION_SCAN_MAX_AGE_S == 2 * 3600.0


# ----------------------------------------- a scan that never priced a rostered sleeve is stale
def _fresh(tmp_path: Path, universe: dict) -> Path:
    return _art(tmp_path, {"status": "MEASURED",
                           "measured_utc": (NOW - timedelta(minutes=30)).isoformat(),
                           "universe": universe, "candidates": {}})


def _roster(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "sleeves.json"
    p.write_text(json.dumps({"sleeves": rows}), "utf-8")
    return p


_SCALP = {"name": "xau_m15_anti_breakout", "symbol": "XAUUSD", "family": "anti_donchian_breakout",
          "exec": "scalp_market", "status": "STANDBY"}


def test_a_fresh_scan_that_never_priced_a_rostered_sleeve_means_heavy(tmp_path: Path) -> None:
    """MEASURED 2026-09-08: until scalp_evidence read closed_at/opened_at, no scalp clock was in
    the priced universe, and `normal` carried that scan forward as MEASURED and fresh -- so the
    promoter read UNMEASURED for the three candidates, which by design moves nothing."""
    art = _fresh(tmp_path, {"XAUUSD_session_range_breakout_asia": {
        "symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia"}})
    roster = _roster(tmp_path, [dict(_SCALP)])
    assert hourly_cycle._rostered_but_unpriced(art, roster) == ["xau_m15_anti_breakout"]
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW, roster) == "heavy"


def test_the_same_scan_with_the_sleeve_priced_keeps_normal(tmp_path: Path) -> None:
    art = _fresh(tmp_path, {"xau_m15_anti_breakout": {
        "symbol": "XAUUSD", "family": "anti_donchian_breakout", "selector": ""}})
    roster = _roster(tmp_path, [dict(_SCALP)])
    assert hourly_cycle._rostered_but_unpriced(art, roster) == []
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW, roster) == "normal"


def test_the_join_is_the_promoter_s_own(tmp_path: Path) -> None:
    """The allocator names a sleeve SYM_family_selector and publishes the parts; the roster
    names it by its clock key. Joining on the parts is `promoter._join_keys`' rule, reused."""
    art = _fresh(tmp_path, {"CADJPY_session_range_breakout_asia": {
        "symbol": "CADJPY", "family": "session_range_breakout", "selector": "asia"}})
    roster = _roster(tmp_path, [{"name": "CADJPY.asia", "symbol": "CADJPY", "window": "asia",
                                 "family": "session_range_breakout", "status": "LIVE"}])
    assert hourly_cycle._rostered_but_unpriced(art, roster) == []


def test_only_live_and_standby_rows_count_and_an_empty_roster_defers_to_the_age_rule(
        tmp_path: Path) -> None:
    art = _fresh(tmp_path, {})
    assert hourly_cycle._rostered_but_unpriced(
        art, _roster(tmp_path, [{**_SCALP, "status": "RETIRED"}])) == []
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW, _roster(tmp_path, [])) == "normal"
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW, tmp_path / "absent.json") == "normal"


def test_a_stale_scan_is_heavy_before_the_roster_is_even_read(tmp_path: Path) -> None:
    art = _art(tmp_path, {"status": "MEASURED",
                          "measured_utc": (NOW - timedelta(hours=3)).isoformat(),
                          "universe": {"xau_m15_anti_breakout": {}}})
    roster = _roster(tmp_path, [_SCALP])
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW, roster) == "heavy"


def test_the_roster_leg_uses_the_chooser() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/pf_allocator.py", "--mode", _allocator_mode_for_the_hour()' in src
    # the executable call that pinned the mode is gone; the docstring that quotes it may stay
    assert '"research/pf_allocator.py", "--mode", "normal"))' not in src
