"""Gate items 14/26/27: the research-capital auction as behavior plus committed evidence.

The two directions matter equally: item 26 (existing data wins) and item 27 (a new free source
wins) are the same arithmetic pointing different ways, and the fence tests at the bottom read the
COMMITTED ledger to prove the desk holds one real decision each way -- assembled from artifacts,
dated, and marked retroactive where recording lagged deciding.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.research.research_auction import AuctionError, compare, decisions, record_decision

_REPO = Path(__file__).resolve().parents[2]


def _cand(side: str, value: float, cost: float) -> dict:
    return {"side": side, "marginal_value": value, "cost": cost,
            "evidence": "declared for test arithmetic"}


# ------------------------------------------------------------------ item 14: the comparison
def test_item14_comparison_is_total_cost_arithmetic_not_class_preference() -> None:
    # Identical value: the cheaper TOTAL cost wins regardless of class...
    v = compare(_cand("EXISTING_DATA", 10, 4), _cand("NEW_SOURCE", 10, 2))
    assert v["winner"] == "NEW_SOURCE"
    # ...and flipping the costs flips the winner. The class is an outcome, never an input.
    v2 = compare(_cand("EXISTING_DATA", 10, 2), _cand("NEW_SOURCE", 10, 4))
    assert v2["winner"] == "EXISTING_DATA"


def test_item14_unpriced_side_is_refused() -> None:
    with pytest.raises(AuctionError, match="unpriced"):
        compare({"side": "EXISTING_DATA", "marginal_value": 10, "evidence": "e"},
                _cand("NEW_SOURCE", 1, 1))


def test_item14_ungrounded_estimate_is_refused() -> None:
    bad = {"side": "NEW_SOURCE", "marginal_value": 99, "cost": 0, "evidence": "  "}
    with pytest.raises(AuctionError, match="ungrounded"):
        compare(bad, _cand("EXISTING_DATA", 1, 1))


def test_item14_ledger_refuses_a_choice_that_loses_its_own_arithmetic(tmp_path: Path) -> None:
    with pytest.raises(AuctionError, match="LOSES its own comparison"):
        record_decision(question="q", chosen=_cand("EXISTING_DATA", 1, 5),
                        rejected=_cand("NEW_SOURCE", 10, 1),
                        decided_utc="2026-08-11T00:00:00+00:00", artifacts=["x"], root=tmp_path)


# ------------------------------------------------------------------ items 26/27: the record
def test_item26_existing_data_defeated_a_new_source_in_the_committed_ledger() -> None:
    rows = [r for r in decisions(_REPO) if r["verdict"]["winner"] == "EXISTING_DATA"
            and r["rejected"]["side"] == "NEW_SOURCE"]
    assert rows, "no recorded decision where existing-data exploitation won the auction"
    row = rows[0]
    assert row["decided_utc"] and row["artifacts"]
    assert any("screen_conversion" in a for a in row["artifacts"])


def test_item27_a_new_free_source_defeated_existing_data_in_the_committed_ledger() -> None:
    rows = [r for r in decisions(_REPO) if r["verdict"]["winner"] == "NEW_SOURCE"
            and r["rejected"]["side"] == "EXISTING_DATA"]
    assert rows, "no recorded decision where a new free source won the auction"
    assert any("collect_circulating_supply" in a for a in rows[0]["artifacts"])


def test_retroactive_rows_declare_themselves() -> None:
    for row in decisions(_REPO):
        if row["decided_utc"][:10] != row["recorded_utc"][:10]:
            assert row.get("retroactive_basis"), (
                "a row recorded after its decision must cite the artifacts that prove the "
                "decision -- history is assembled, never invented")
