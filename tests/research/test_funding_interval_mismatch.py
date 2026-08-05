"""The settlement-calendar screen must tell NESTED grids from OFFSET ones.

That distinction is the screen's whole content: "the calendars differ" supports the trade only when
the grids are displaced in PHASE. If one venue simply settles more often on the same anchor, every
sparse stamp coincides with a dense one and no capture window exists at any funding level.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def screen():
    spec = importlib.util.spec_from_file_location(
        "screen_funding_interval_mismatch",
        _ROOT / "scripts/screen_funding_interval_mismatch.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stamps(start: str, interval_h: float, n: int) -> pd.Series:
    return pd.Series(pd.date_range(start, periods=n, freq=f"{int(interval_h * 60)}min", tz="UTC"))


def test_interval_is_measured_from_stamps_not_configured(screen) -> None:
    """A CONFIGURED CONSTANT IS NOT EVIDENCE OF A CADENCE (L1.46)."""
    p = screen._phase_profile(_stamps("2024-01-01T00:00:00Z", 4.0, 300))
    assert p["usable"] and p["interval_h"] == 4.0
    p8 = screen._phase_profile(_stamps("2024-01-01T00:00:00Z", 8.0, 300))
    assert p8["interval_h"] == 8.0


def test_an_offset_venue_is_usable_not_discarded(screen) -> None:
    """THE BUG THIS PINS. The first version tested for phase 0, which by construction excludes
    every OFFSET venue -- the only case the screen exists to find. BitMEX (04/12/20 UTC) is 100%
    consistent on its own grid and was dropped as NO-DATA."""
    p = screen._phase_profile(_stamps("2024-01-01T04:00:00Z", 8.0, 300))
    assert p["dominant_phase_h"] == 4.0
    assert p["share_at_dominant_phase"] == 1.0
    assert p["usable"], "a venue consistently on an OFFSET grid must be usable"
    assert p["share_on_utc_midnight_grid"] == 0.0     # and reported, not used as the gate


def test_a_series_that_changed_interval_is_excluded(screen) -> None:
    """The case the usability bar is actually for: no single interval describes the series."""
    mixed = pd.concat([_stamps("2024-01-01T00:00:00Z", 8.0, 200),
                       _stamps("2024-04-01T02:00:00Z", 3.0, 200)], ignore_index=True)
    p = screen._phase_profile(mixed)
    assert not p["usable"]
    assert "CHANGED" in p["why"]


def test_too_few_stamps_refuses_a_phase_claim(screen) -> None:
    p = screen._phase_profile(_stamps("2024-01-01T00:00:00Z", 8.0, 10))
    assert not p["usable"] and "too few" in p["why"]


def test_offset_is_measured_against_the_reference_grid_not_midnight(screen) -> None:
    """THE BUG THIS PINS. `offset = bm_phase - 0.0` is an offset only while the reference venue
    sits at phase 0; it reads an ABSOLUTE phase as a DIFFERENCE. The day Binance re-anchors -- the
    event this weekly screen exists to catch -- the headline would keep quoting BitMEX's own phase
    and claim an offset that no longer exists."""
    assert screen._phase_offset(4.0, {0.0}) == 4.0            # today's real corpus
    # Reference venue re-anchored to 04/12/20 and BitMEX unchanged: the offset is now ZERO, and
    # the pre-fix arithmetic would still have reported 4.0.
    assert screen._phase_offset(4.0, {4.0}) == 0.0
    # Nearest reference phase wins -- a window has to avoid every reference stamp.
    assert screen._phase_offset(4.0, {0.0, 3.0}) == 1.0
    assert screen._phase_offset(4.0, set()) == 0.0            # no reference: no claimed offset


def test_grid_stamps_are_derived_from_the_measured_interval(screen) -> None:
    """The report writes out the actual UTC hours; hardcoding '+8/+16' asserted an 8h BitMEX."""
    assert screen._grid_stamps(4.0, 8.0) == "04/12/20"
    assert screen._grid_stamps(0.0, 4.0) == "00/04/08/12/16/20"
    assert screen._grid_stamps(23.0, 8.0) == "23/07/15"       # wraps, never prints hour 31
    assert screen._grid_stamps(0.0, None) == "?"              # refuses rather than inventing


def test_cost_lookup_refuses_rather_than_defaults(screen) -> None:
    """A screen that invents a cost it never measured is how a dead mechanism gets a slot."""
    assert screen._roundtrip_bps("DEFINITELY_NOT_A_SYMBOL") is None


def test_the_live_report_states_a_breakeven_not_an_invented_cost(screen) -> None:
    rep = screen.build_report()
    assert rep["stage"].startswith("A ")                       # zero promotion authority
    assert rep["status"] in ("SCREEN-CONDITIONAL", "REFUTED-STRUCTURAL", "NO-DATA", "REDUNDANT")
    assert "forward clock" in rep["next_action"].lower()
    # Every construction tried is reported, never only the survivor.
    assert rep["trial_accounting"]["constructions_tried"] == len(rep["trials"]) >= 2
    assert rep["timestamp_alignment"]
    cross = next(t for t in rep["trials"] if t["trial"].startswith("cross_venue"))
    if cross.get("verdict") == "GEOMETRICALLY-FEASIBLE":
        econ = cross["economics_btcusdt"]
        assert econ["bitmex_leg_roundtrip_bps"] is None       # never invented
        assert econ["breakeven_second_leg_roundtrip_bps"] > 0
        assert cross["unpriced_risks"]                        # dominance + convexity + n=1


def test_intra_venue_nesting_is_detected_on_the_real_corpus(screen) -> None:
    """Binance's 4h grid is a strict superset of its 8h grid -- geometrically impossible."""
    if not (_ROOT / "data/funding_settlements").exists():
        pytest.skip("settlement corpus absent on this box")
    artifact = _ROOT / "reports/screen_funding_interval_mismatch.json"
    rep = (json.loads(artifact.read_text("utf-8")) if artifact.exists()
           else screen.build_report())
    intra = next(t for t in rep["trials"] if t["trial"].startswith("intra_venue"))
    assert intra["verdict"] == "IMPOSSIBLE-NESTED"
    assert intra["distinct_grid_phases"] == [0.0]
    assert set(intra["intervals_seen"]) == {"8.0h", "4.0h"}
