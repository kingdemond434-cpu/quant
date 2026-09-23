"""The compounding term: what a sleeve added to GEOMETRIC growth given WHEN its heat was held.

AUDIT P19 (2026-09-08): the edge term was signed per sleeve, but no term priced timing -- the
allocator re-weights every pass, and nothing said whether the re-weighting put heat on a sleeve
on the days it paid -- and nothing priced the geometric cost of variance at the heat held.

What is pinned:

  * constant heat and constant R: timing is exactly zero and the value is exactly the drag,
    ln(1 + h r) - h r, so the arithmetic can be checked by hand;
  * heat that rises on winning days and falls on losing days is POSITIVE timing, and the number
    is the covariance the docstring names;
  * the last allocator pass of a day speaks for it;
  * UNMEASURED names the EXACT missing input (a realised daily R) and the day count, never zero;
  * the nine-term contract and the ten-term weekly table are byte-for-byte what they were: the
    term rides beside them and stays out of the identity.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import allocator_attribution as attr  # noqa: E402

UNMEASURED = attr.UNMEASURED
DAYS = [(datetime.now(UTC).date() - timedelta(days=i)).isoformat() for i in range(10, 0, -1)]
BOOK = {"A": 0.10, "B": 0.05}
REALISED_R = {"A": 0.5, "B": -0.2}


def _forecasts(desk: Path, books: dict[str, dict[str, float]] | None = None,
               passes_per_day: int = 1) -> None:
    rows = []
    for d in DAYS:
        for h in range(passes_per_day):
            rows.append(json.dumps({"t": f"{d}T{6 + 6 * h:02d}:00:00+00:00",
                                    "book": (books or {}).get(d, BOOK),
                                    "expected_log_per_day": 0.002, "total_heat": 0.15}))
    (desk / "data" / "pf_forecast_log.jsonl").write_text("\n".join(rows), "utf-8")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(attr, "BASE", tmp_path)
    monkeypatch.setattr(attr, "FORECASTS", tmp_path / "data" / "pf_forecast_log.jsonl")
    monkeypatch.setattr(attr, "LIVE", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(attr, "OUT", tmp_path / "reports" / "allocator_attribution.json")
    monkeypatch.setattr(attr, "WEEKLY_OUT",
                        tmp_path / "reports" / "GROWTH_ATTRIBUTION_WEEKLY.json")
    monkeypatch.setattr(attr, "_heat_bars", lambda: (0.20, 0.30, "test"))
    monkeypatch.setattr(attr, "realized_daily",
                        lambda: ({s: dict.fromkeys(DAYS, r) for s, r in REALISED_R.items()},
                                 "shadow_forward"))
    _forecasts(tmp_path)
    return tmp_path


def test_constant_heat_has_zero_timing_and_the_value_is_exactly_the_drag(desk: Path) -> None:
    t = attr._compounding_term(attr.load_forecasts(30), attr.realized_daily()[0],
                               "shadow_forward")
    assert isinstance(t["value"], float) and t["unit"] == attr.LOGW
    assert t["in_identity"] is False and "pinned nine-term" in t["out_of_identity_why"]
    assert t["scored_days"] == len(DAYS) and t["n_sleeves"] == 2
    for name, h in BOOK.items():
        row = t["sleeves"][name]
        r = REALISED_R[name]
        assert row["timing"] == pytest.approx(0.0, abs=1e-9)
        assert row["drag"] == pytest.approx(math.log1p(h * r) - h * r, abs=1e-9)
        assert row["value"] == pytest.approx(row["drag"], abs=1e-9)
        assert row["n_days"] == len(DAYS) and row["mean_heat"] == pytest.approx(h)
        assert row["heat_sd"] == 0.0 and "did not move" in row["reading"]
    assert t["value"] == pytest.approx(sum(r["value"] for r in t["sleeves"].values()))
    assert t["timing_total"] == pytest.approx(0.0, abs=1e-9) and t["drag_total"] < 0
    dlogw = 0.10 * 0.5 + 0.05 * -0.2
    assert t["book_geometric_gap"] == pytest.approx(math.log1p(dlogw) - dlogw, abs=1e-9)
    # with zero timing the ranking IS the drag, and B's |h r| = 0.01 costs less than A's 0.05
    assert t["best_timed"][0] == "B" and t["worst_timed"][-1] == "A"
    assert t["skipped_sleeves"] == []


def test_heat_that_rises_on_winning_days_is_positive_timing_by_the_covariance(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """h = 0.10 on winning days (r=+1) and 0.02 on losing days (r=-1): mean h 0.06, mean r 0,
    mean(h r) = 0.04, so timing = 0.04 - 0.06 x 0 = 0.04 exactly. Reversed, it is -0.04."""
    wins = {d: {"A": 0.10 if i % 2 == 0 else 0.02} for i, d in enumerate(DAYS)}
    _forecasts(desk, wins)
    rs = {d: (1.0 if i % 2 == 0 else -1.0) for i, d in enumerate(DAYS)}
    monkeypatch.setattr(attr, "realized_daily", lambda: ({"A": rs}, "shadow_forward"))
    t = attr._compounding_term(attr.load_forecasts(30), attr.realized_daily()[0], "x")
    a = t["sleeves"]["A"]
    assert a["timing"] == pytest.approx(0.04, abs=1e-9)
    assert "days this sleeve paid" in a["reading"]
    expected_drag = sum(math.log1p(h * r) - h * r for h, r in
                        ((0.10, 1.0), (0.02, -1.0)) * 5) / 10
    assert a["drag"] == pytest.approx(expected_drag, abs=1e-9)
    assert a["value"] == pytest.approx(0.04 + expected_drag, abs=1e-9)
    # the same heat path against the opposite results is the mirror image
    monkeypatch.setattr(attr, "realized_daily",
                        lambda: ({"A": {d: -v for d, v in rs.items()}}, "shadow_forward"))
    t2 = attr._compounding_term(attr.load_forecasts(30), attr.realized_daily()[0], "x")
    assert t2["sleeves"]["A"]["timing"] == pytest.approx(-0.04, abs=1e-9)
    assert "days this sleeve lost" in t2["sleeves"]["A"]["reading"]


def test_the_last_allocator_pass_of_a_day_speaks_for_it(desk: Path) -> None:
    rows = []
    for d in DAYS:
        rows.append(json.dumps({"t": f"{d}T06:00:00+00:00", "book": {"A": 1.0}}))
        rows.append(json.dumps({"t": f"{d}T18:00:00+00:00", "book": BOOK}))
    (desk / "data" / "pf_forecast_log.jsonl").write_text("\n".join(rows), "utf-8")
    t = attr._compounding_term(attr.load_forecasts(30), attr.realized_daily()[0], "x")
    assert t["sleeves"]["A"]["mean_heat"] == pytest.approx(0.10)
    assert t["sleeves"]["A"]["n_days"] == len(DAYS)


def test_unmeasured_names_the_exact_missing_input_and_never_reads_zero(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attr, "realized_daily", lambda: ({}, UNMEASURED))
    t = attr._compounding_term(attr.load_forecasts(30), {}, UNMEASURED)
    assert t["value"] == UNMEASURED and t["scored_days"] == 0 and t["sleeves"] == {}
    assert f"needs {attr.MIN_DAYS} scored day" in t["why"]
    assert "live_ledger.jsonl" in t["why"] and "forward clocks" in t["why"]
    assert f"over {len(DAYS)} forecast pass(es)" in t["why"]
    # realised series exist but under other names: a join defect, named as such
    t = attr._compounding_term(attr.load_forecasts(30), {"Z": dict.fromkeys(DAYS, 0.1)}, "x")
    assert t["value"] == UNMEASURED and "share no sleeve name" in t["why"]
    # too few scored days
    short = {"A": dict.fromkeys(DAYS[-3:], 0.5)}
    t = attr._compounding_term(attr.load_forecasts(30), short, "x")
    assert t["value"] == UNMEASURED and t["scored_days"] == 3 and "3 today" in t["why"]


def test_a_day_that_wiped_the_sleeve_is_skipped_by_name_not_logged_as_minus_infinity(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _forecasts(desk, {d: {"A": 1.0} for d in DAYS})
    monkeypatch.setattr(attr, "realized_daily",
                        lambda: ({"A": dict.fromkeys(DAYS, -1.0)}, "x"))
    t = attr._compounding_term(attr.load_forecasts(30), attr.realized_daily()[0], "x")
    assert t["skipped_sleeves"] == ["A"] and t["n_sleeves"] == 0
    assert t["value"] == 0.0 and t["book_geometric_gap"] is None


def test_the_term_rides_beside_the_pinned_contracts_and_stays_out_of_the_identity(
        desk: Path) -> None:
    doc = attr.build(30)
    assert tuple(doc["growth_decomposition"]["terms"]) == (
        "alpha", "selection", "state", "sizing", "diversification", "execution", "exit",
        "cost", "veto")
    assert isinstance(doc["compounding"]["value"], float)
    w = attr.weekly_table(days=30)
    assert tuple(w["terms"]) == ("alpha", "selection", "state", "sizing", "diversification",
                                 "entry", "execution", "exit", "cost", "veto")
    assert "compounding" not in w["terms"] and isinstance(w["compounding"]["value"], float)
    assert "compounding" not in w["identity"]["terms_in_identity"]
    assert w["compounding"]["in_identity"] is False
    out = attr.run(days=30, week_days=7)
    assert out["compounding"] == out["weekly"]["compounding"]["value"]
    daily = json.loads((desk / "reports" / "allocator_attribution.json").read_text("utf-8"))
    weekly = json.loads((desk / "reports" / "GROWTH_ATTRIBUTION_WEEKLY.json").read_text("utf-8"))
    assert daily["compounding"]["n_sleeves"] == 2 and weekly["compounding"]["n_sleeves"] == 2
