"""`--apply` conflated two decisions whose directions of error are opposite.

WIDENING a spread can only make the desk charge itself more. Every certificate priced against the
old number was too generous, so re-pricing can only retire claims -- it can never mint one.
Measured 2026-09-14: 74 of 191 re-measured symbols carry a registry spread of ZERO (USDRUB
0 -> 2582.5, EURRUB 0 -> 250, NOKSEK 0 -> 39), and 26.3% of the judged docket -- 1,803 of 6,854
cells -- was evaluated at no spread cost at all because of it.

NARROWING one is the opposite act: it makes previously-uneconomic cells look tradeable, which is
the shape of a desk talking itself into an edge. Those are the rows whose medians are
zero-inflated -- GBPCHF prices 46% of its full-session bars, so its median falls in the near-zero
cluster while its p75 is 150.

So the conservative half can be taken without the half that needs a person to read each row. This
pins the property that makes that safe: widening-only NEVER lowers a charge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

rus = pytest.importorskip("repair_universe_spreads")


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    doc = {"WIDENS": {"median_spread_pts": 10.0},
           "NARROWS": {"median_spread_pts": 500.0},
           "ZEROED": {"median_spread_pts": 0.0}}
    p = tmp_path / "universe.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(rus, "REGISTRY", p)
    monkeypatch.setattr(rus, "REPORT", tmp_path / "SPREAD_PROVENANCE.json")
    measured = {"WIDENS": 200.0, "NARROWS": 7.0, "ZEROED": 39.0}
    monkeypatch.setattr(rus, "measured_spread",
                        lambda sym: (measured[sym], "measured", {"n_priced": 10_000}))
    return p


def test_widening_only_never_lowers_a_charge(registry):
    rus.run(apply=True, write=True, widening_only=True)
    doc = json.loads(registry.read_text("utf-8"))
    assert doc["WIDENS"]["median_spread_pts"] == 200.0, "a wider measurement must be taken"
    assert doc["ZEROED"]["median_spread_pts"] == 39.0, "a zero-priced symbol must be repaired"
    assert doc["NARROWS"]["median_spread_pts"] == 500.0, (
        "widening-only must NOT narrow a spread: that mints claims rather than retiring them")


def test_full_apply_still_takes_both_directions(registry):
    rus.run(apply=True, write=True, widening_only=False)
    doc = json.loads(registry.read_text("utf-8"))
    assert doc["NARROWS"]["median_spread_pts"] == 7.0
    assert doc["WIDENS"]["median_spread_pts"] == 200.0


def test_report_only_writes_nothing(registry):
    before = registry.read_text("utf-8")
    r = rus.run(apply=False, write=True)
    assert registry.read_text("utf-8") == before
    assert r["apply_mode"] == "report_only"
    assert r["n_applied"] == 0


def test_the_zero_spread_count_is_published(registry):
    """74 symbols priced at zero is the number that justifies the whole change; publish it."""
    r = rus.run(apply=False, write=True)
    assert r["n_zero_registry_spread"] >= 1
    assert r["apply_mode"] == "report_only"


def test_the_mode_is_recorded_in_provenance(registry):
    rus.run(apply=True, write=True, widening_only=True)
    doc = json.loads(registry.read_text("utf-8"))
    assert doc["WIDENS"]["_provenance"]["median_spread_pts"]["mode"] == "widening_only"
    assert doc["WIDENS"]["_provenance"]["median_spread_pts"]["was"] == 10.0
