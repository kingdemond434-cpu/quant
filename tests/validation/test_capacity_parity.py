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
    assert V.capacity_status(300.0, equity_usd=1000.0) == "OUTGROWN"
    assert V.capacity_status(300.0, equity_usd=100.0) == "ADMIT"      # same edge, smaller book
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
