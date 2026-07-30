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


def test_dust_is_still_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Parity is not permissiveness: below the dust floor, frictions dominate at ANY equity."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web/cashcarry_live.json").write_text(json.dumps({"equity": 100.0}), "utf-8")
    assert V._min_capacity_usd() == pytest.approx(V._CAPACITY_DUST_FLOOR_USD)
    assert V._min_capacity_usd() > 500.0


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
