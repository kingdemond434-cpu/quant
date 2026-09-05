"""A symbol the desk does not have cannot produce a survivor (L1.49).

MEASURED 2026-09-02: eight certificates -- six on AFG, two on AFL -- had passed all ten gates on
symbols absent from universe.json with no H1 parquet on the box. They can never enrol a forward
clock, so the ten gates were spent producing rows indistinguishable from tradeable survivors in
every artifact that counts them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet as eg  # noqa: E402

META = {"EURUSD": {"contract_size": 1e5}, "AFG": {"contract_size": 1e5}}


@pytest.fixture
def bars(tmp_path, monkeypatch):
    """A universe directory holding EURUSD bars and nothing else."""
    (tmp_path / "EURUSD_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(eg, "UNI", tmp_path)
    return tmp_path


def _spec(sym: str, family: str = "session_range_breakout", **kw):
    return {"sym": sym, "family": family, "params": {}, "mechanism_status": "NAMED", **kw}


def test_a_symbol_with_registry_and_bars_is_tradeable(bars) -> None:
    ok, why = eg.symbol_is_tradeable("EURUSD", META)
    assert ok and why == ""


def test_a_symbol_missing_from_the_registry_is_not(bars) -> None:
    ok, why = eg.symbol_is_tradeable("NOSUCH", META)
    assert not ok and "absent from the universe registry" in why


def test_a_registered_symbol_with_no_bars_is_not(bars) -> None:
    """THE AFG CASE. Registry membership answers "will the broker quote it"; the parquet answers
    "can a clock replay it". Both are required and they are different questions."""
    ok, why = eg.symbol_is_tradeable("AFG", META)
    assert not ok and "no AFG_H1.parquet" in why


def test_untradeable_specs_are_partitioned_out_before_any_other_gate(bars) -> None:
    eligible, rejected = eg.partition_at_economic_prior(
        [_spec("EURUSD"), _spec("AFG"), _spec("NOSUCH")], META)
    assert [s["sym"] for s in eligible] == ["EURUSD"]
    assert {r["sym"] for r in rejected} == {"AFG", "NOSUCH"}
    assert all(r["terminal_gate"] == "symbol_eligibility" for r in rejected)
    assert all(r["downstream_status"] == "NOT_RUN_UNTRADEABLE_SYMBOL" for r in rejected)


def test_untradeable_is_named_not_silently_failed(bars) -> None:
    """It is not a bad edge -- it is an edge on an instrument this desk does not have, and the
    artifact has to say which."""
    _e, rejected = eg.partition_at_economic_prior([_spec("AFG")], META)
    stage = rejected[0]["stages"]["symbol_eligibility"]
    assert stage["passed"] is False
    assert "AFG" in stage["message"]


def test_tradeability_is_checked_before_the_mechanism(bars) -> None:
    """An untradeable cell must not be reported as an economic-prior failure: running the other
    nine gates on it is the waste, and mislabelling it hides the real reason."""
    _e, rejected = eg.partition_at_economic_prior(
        [_spec("AFG", family="discovered", mechanism_status="STATISTICAL_ONLY")], META)
    assert rejected[0]["terminal_gate"] == "symbol_eligibility"


def test_the_mechanism_limb_still_works(bars) -> None:
    eligible, rejected = eg.partition_at_economic_prior(
        [_spec("EURUSD", family="discovered", mechanism_status="STATISTICAL_ONLY")], META)
    assert eligible == []
    assert rejected[0]["terminal_gate"] == "economic_prior"


def test_no_meta_runs_the_mechanism_limb_alone(bars) -> None:
    """Backwards compatible on purpose: an existing caller that passes no registry keeps its
    behaviour exactly, rather than having every cell silently declared untradeable."""
    eligible, rejected = eg.partition_at_economic_prior([_spec("AFG"), _spec("NOSUCH")])
    assert len(eligible) == 2 and rejected == []
