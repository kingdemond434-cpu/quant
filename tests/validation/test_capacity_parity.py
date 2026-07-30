"""CAPACITY PARITY (principal order 2026-07-30) -- small edges are exploited, never deprioritised.

The gauntlet carried a FIXED $100,000 capacity floor on a desk deploying ~$4,500. That rejected
edges the desk could fill completely (measured: capacity blocked part of 182/420 campaign
candidates), which is capacity PICKINESS and it costs exactly the compounding the desk exists to
maximise. The bar is now relative to the desk's OWN size, and these tests pin that it can never
silently drift back to an institutional assumption.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.autodiscovery import validation as V


def test_bar_is_relative_to_desk_equity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web/cashcarry_live.json").write_text(json.dumps({"equity": 4500.0}), "utf-8")
    assert V._desk_equity_usd() == 4500.0
    assert V._min_capacity_usd() == pytest.approx(9000.0)


def test_a_small_edge_the_desk_can_fill_is_ADMITTED(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """THE DEFECT ITSELF: a $20k-capacity edge at $4.5k equity is 100% usable and used to fail."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web/cashcarry_live.json").write_text(json.dumps({"equity": 4500.0}), "utf-8")
    assert V._min_capacity_usd() <= 20_000.0          # admitted now
    assert 20_000.0 < 1.0e5                            # would have been rejected before


def test_tiny_capital_admits_tiny_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PRINCIPAL 2026-07-30: capital may start ~$100. A $300-capacity edge is then FULLY usable
    and must be exploited -- the floor is execution physics, not a capital-size opinion."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web/cashcarry_live.json").write_text(json.dumps({"equity": 100.0}), "utf-8")
    assert V._min_capacity_usd() == pytest.approx(V._EXEC_VIABILITY_FLOOR_USD)
    assert V.capacity_status(300.0, equity_usd=100.0) == "ADMIT"


def test_sub_viable_is_the_only_capacity_kill() -> None:
    """Below a handful of economic round-trips at venue minimums, L1.5 kills it at ANY equity."""
    assert V.capacity_status(50.0, equity_usd=100.0) == "SUB-VIABLE"
    assert V.capacity_status(50.0, equity_usd=1.0e6) == "SUB-VIABLE"


def test_outgrown_is_distinct_from_sub_viable() -> None:
    """The lifecycle the principal specified: a real edge harvested to exhaustion retires by
    OUTGROWTH as capital compounds past it -- success, not failure, and never a graveyard entry."""
    assert V.capacity_status(300.0, equity_usd=50_000.0) == "OUTGROWN"
    assert V.capacity_status(300.0, equity_usd=1000.0) == "ADMIT"     # same edge, smaller book
    src = Path(V.__file__).read_text("utf-8")
    assert "NEVER graveyarded" in src        # the rule is written where the code lives


def test_bar_scales_up_with_the_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """As the desk grows the bar grows with it -- no retrofit needed at $1m."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web/cashcarry_live.json").write_text(json.dumps({"equity": 1.0e6}), "utf-8")
    assert V._min_capacity_usd() == pytest.approx(2.0e6)


def test_missing_state_falls_back_without_crashing(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert V._desk_equity_usd() == V._DESK_EQUITY_FALLBACK_USD
    assert V._min_capacity_usd() > 0


def test_no_fixed_institutional_floor_remains() -> None:
    """A regression fence: the day someone reintroduces a hardcoded 1e5 capacity bar, this fails."""
    src = Path(V.__file__).read_text("utf-8")
    assert "_MIN_CAPACITY_USD = 1.0e5" not in src
    assert "_min_capacity_usd()" in src


class TestAdmissionBandSlides:
    """PRINCIPAL 2026-07-30: the band slides up with equity and stays INCLUSIVE at the small end.
    A multiple-of-book rule failed this and was replaced by a minimum-SLICE rule."""

    def test_at_1k_everything_from_the_floor_up_is_admitted(self) -> None:
        for cap in (300.0, 800.0, 1500.0, 2000.0, 5000.0):
            assert V.capacity_status(cap, equity_usd=1000.0) == "ADMIT", cap

    def test_the_old_multiple_rule_would_have_rejected_most_of_those(self) -> None:
        # Regression fence on the reasoning, not just the number: a 2x-of-book bar at $1k equity
        # marked $300/$800/$1500 OUTGROWN -- edges holding 30%/80%/150% of the entire book.
        assert 1000.0 * V._CAPACITY_MULTIPLE_OF_EQUITY > 1500.0
        assert V.capacity_status(1500.0, equity_usd=1000.0) == "ADMIT"

    def test_the_same_edge_retires_only_when_it_becomes_a_rounding_error(self) -> None:
        assert V.capacity_status(300.0, equity_usd=1000.0) == "ADMIT"
        assert V.capacity_status(300.0, equity_usd=50_000.0) == "OUTGROWN"
        assert V.capacity_status(20_000.0, equity_usd=50_000.0) == "ADMIT"

    def test_min_slice_is_the_documented_fraction(self) -> None:
        # Use an equity high enough that the slice boundary sits clear of the execution floor,
        # so the two rules are tested separately rather than colliding.
        eq = 50_000.0
        boundary = eq * V._MIN_SLICE_FRACTION            # $5,000
        assert boundary > V._EXEC_VIABILITY_FLOOR_USD
        assert V.capacity_status(boundary * 1.01, equity_usd=eq) == "ADMIT"
        assert V.capacity_status(boundary * 0.99, equity_usd=eq) == "OUTGROWN"


class TestCapacityRace:
    """The pipeline-latency race: an edge that lands after the book outgrew it is a zero."""

    def test_runway_is_zero_when_already_outgrown(self) -> None:
        assert V.capacity_runway_days(50.0, equity_usd=1000.0) == 0.0

    def test_runway_shrinks_as_growth_accelerates(self) -> None:
        slow = V.capacity_runway_days(300.0, equity_usd=1000.0, growth_rate_annual=1.0)
        fast = V.capacity_runway_days(300.0, equity_usd=1000.0, growth_rate_annual=4.6)
        assert fast < slow

    def test_verdicts_span_the_regimes(self) -> None:
        # Measured 2026-07-30: at the desk's mandated ~100%/yr a $300 edge comfortably outruns a
        # 90-day clock; the race only bites in aggressive-growth regimes. That is the honest
        # finding -- pipeline latency is NOT currently the binding constraint on small edges.
        assert V.capacity_race(300.0, validation_days=90, equity_usd=1000.0,
                               growth_rate_annual=1.0)["verdict"] == "REACHES-LIVE"
        assert V.capacity_race(300.0, validation_days=90, equity_usd=1000.0,
                               growth_rate_annual=2.3)["verdict"] == "TIGHT"
        assert V.capacity_race(300.0, validation_days=90, equity_usd=1000.0,
                               growth_rate_annual=4.6)["verdict"] == "DOA"

    def test_remedy_never_proposes_a_shorter_clock(self) -> None:
        """L1.6: the confirmation bar never loosens. The only honest accelerants are more
        observations per day and not queueing."""
        r = V.capacity_race(300.0, validation_days=90, equity_usd=1000.0, growth_rate_annual=4.6)
        assert "never a shorter clock or a lower bar" in r["remedy"]
        assert "higher-frequency" in r["remedy"]

    def test_slot_priority_orders_by_expiry(self) -> None:
        """Shortest runway is served FIRST: a long-runway edge loses nothing by waiting, a
        short-runway one loses everything."""
        edges = [V.capacity_race(c, validation_days=90, equity_usd=1000.0) for c in
                 (20_000.0, 300.0, 2000.0)]
        order = [e["capacity_usd"] for e in sorted(edges, key=lambda e: e["slot_priority"])]
        assert order == [300.0, 2000.0, 20_000.0]
