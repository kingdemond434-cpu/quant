from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.run_conversion_control import build, weakest_transition

from libs.research.alpha_state import AlphaStateLedger


def test_weakest_transition_is_dynamic_and_unknown_is_not_zero() -> None:
    stages = [
        {"stage": "A", "count": 100},
        {"stage": "B", "count": None},
        {"stage": "C", "count": 20},
        {"stage": "D", "count": 1},
    ]
    assert weakest_transition(stages) == {
        "from": "C", "to": "D", "upstream": 20, "downstream": 1,
        "conversion": 0.05, "stranded": 19,
    }


def test_build_uses_canonical_store_and_defaults_to_fifty_fifty(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    db = sqlite3.connect(tmp_path / "data/sor_crypto.sqlite")
    db.execute("CREATE TABLE research_candidates (survived INT, status TEXT, capacity_usd REAL, "
               "rejection_reason TEXT)")
    db.executemany("INSERT INTO research_candidates VALUES (?, ?, ?, ?)", [
        (0, "rejected", 0, "failed:x"), (1, "registry", 10, ""),
    ])
    db.commit()
    db.close()
    report = build(tmp_path)
    assert report["legacy_inventory_not_conversion"]["candidate_store"]["tested"] == 2
    assert report["legacy_inventory_not_conversion"]["candidate_store"][
        "fully_measured_survivors"
    ] == 1
    assert report["stages"][0]["count"] == 0
    assert report["research_portfolios"]["weights"] == {
        "exploitation": 0.5, "exploration": 0.5,
    }
    assert report["research_portfolios"]["evidence_used"] is False


def test_build_computes_rates_only_inside_the_canonical_identity_ledger(tmp_path: Path) -> None:
    path = tmp_path / "data/alpha_state_ledger.jsonl"
    ledger = AlphaStateLedger(path)
    ledger.advance("a", "IMPLEMENTED", {"expression": "x", "data_source": "d"})
    report = build(tmp_path)
    assert report["stages"][0]["count"] == 1
    assert report["stages"][1]["count"] == 1
    assert report["stages"][2]["count"] == 0
    assert report["binding_transition"]["from"] == "IMPLEMENTED"
    assert report["binding_transition"]["to"] == "TESTED"


def test_build_moves_only_from_realised_two_sided_outcomes(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/research_portfolio_outcomes.json").write_text(json.dumps({
        "exploitation": {"validated_economic_value": 9, "measured_cost": 3},
        "exploration": {"validated_economic_value": 1, "measured_cost": 3},
    }), "utf-8")
    report = build(tmp_path)
    assert report["research_portfolios"]["evidence_used"] is True
    assert report["research_portfolios"]["weights"]["exploitation"] == 0.6
