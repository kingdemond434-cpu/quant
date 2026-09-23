"""Collection must start where coverage is missing, not where the broker's list starts.

THE BUDGET DIED AT THE SAME PREFIX EVERY RUN. `expand_universe` walked `mt5.symbols_get()` in
terminal order and asked every symbol for every chart -- M1's 200,000 bars included, four chunked
calls each. The leg budget expired partway down that list, and the next run began at the same
place, so the prefix was re-collected hourly and the tail was never reached. Measured on the
trading box 2026-09-14: M5, M15, M30 and H4 each hold 248 symbols and D1 250, while M1 holds 25
of 299. M1 is not expensive relative to the others; it was last.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

eu = pytest.importorskip("research.expand_universe")


def _sym(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, trade_mode=1)


def _cover(tmp_path: Path, monkeypatch, coverage: dict[str, list[str]]) -> None:
    monkeypatch.setattr(eu, "UNIVERSE", tmp_path)
    for name, tfs in coverage.items():
        for tf in tfs:
            (tmp_path / f"{name}_{tf}.parquet").write_bytes(b"x")


def test_a_symbol_the_desk_trades_and_is_missing_charts_goes_first(tmp_path, monkeypatch):
    full = list(eu.TIMEFRAMES)
    _cover(tmp_path, monkeypatch, {"AAAUSD": full, "ZZZUSD": full[:-1], "XAUUSD": full[:-1]})
    order = [s.name for s in eu._collection_order(
        [_sym("AAAUSD"), _sym("ZZZUSD"), _sym("XAUUSD")], {"XAUUSD"})]
    assert order[0] == "XAUUSD", "a traded symbol missing a chart must be collected first"
    assert order[-1] == "AAAUSD", "a fully covered symbol is refreshed last"


def test_the_least_covered_symbol_outranks_a_nearly_complete_one(tmp_path, monkeypatch):
    full = list(eu.TIMEFRAMES)
    _cover(tmp_path, monkeypatch, {"BARE": [], "NEARLY": full[:-1]})
    order = [s.name for s in eu._collection_order([_sym("NEARLY"), _sym("BARE")], set())]
    assert order == ["BARE", "NEARLY"]


def test_an_unreadable_sleeve_registry_degrades_it_does_not_refuse(tmp_path, monkeypatch):
    """Absence of the priority set must order by coverage, never stop collection."""
    monkeypatch.setattr(eu, "SLEEVES", tmp_path / "nope.json")
    assert eu._traded_symbols() == set()
    full = list(eu.TIMEFRAMES)
    _cover(tmp_path, monkeypatch, {"DONE": full, "GAP": full[:-2]})
    order = [s.name for s in eu._collection_order([_sym("DONE"), _sym("GAP")],
                                                  eu._traded_symbols())]
    assert order == ["GAP", "DONE"]


def test_the_order_is_a_permutation_and_drops_nothing(tmp_path, monkeypatch):
    """Reprioritising must never collect LESS -- every tradable symbol still appears once."""
    _cover(tmp_path, monkeypatch, {})
    syms = [_sym(n) for n in ("A", "B", "C", "D")]
    out = eu._collection_order(syms, {"C"})
    assert sorted(s.name for s in out) == ["A", "B", "C", "D"]
    assert len(out) == len(syms)
