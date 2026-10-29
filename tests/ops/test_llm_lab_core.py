"""LLM lab core: the ds-2 output contract (addendum sections 10, 16).

Every test runs in a temporary root; nothing here writes the repository's own state."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from libs.ops import llm_lab_core as core

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def families() -> dict[str, list[str]]:
    fams = core.family_specs(REPO)
    assert "formula" in fams, "the registered formula family is the exact-candidate IR"
    return fams


@pytest.fixture
def root(tmp_path: Path, families, monkeypatch) -> Path:
    uni = tmp_path / "desks/mt5/data/universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps({
        "EURUSD": {"asset_class": "Forex"}, "GBPUSD": {"asset_class": "Forex"},
        "USDJPY": {"asset_class": "Forex"}, "XAUUSD": {"asset_class": "Commodities"},
    }), "utf-8")
    (tmp_path / "desks/mt5/data/data_registry.json").write_text(
        json.dumps({"datasets": {"cot_tff": {}}}), "utf-8")
    monkeypatch.setattr(core, "family_specs", lambda _root: families)
    return tmp_path


def _ctx(root: Path) -> dict[str, Any]:
    return core.context(root)


EXACT = {
    "object_type": "EXACT_CANDIDATE", "title": "USD driver impulse fades on EURUSD in NY",
    "symbols": ["eurusd"], "family": "formula",
    "params": {"expr": "mul(sign(delta(usd, 5)), ts_rank(vol, 48))", "norm": 240,
               "entry_z": 1.5, "side_mode": "fade", "hold_bars": 8, "stop_atr": 2.0, "rr": 1.5},
    "timeframe": "H1", "session": "ny", "direction": "both",
    "entry_rule": "enter at next open when |z| of expr over 240 bars >= 1.5, against its sign",
    "exit_rule": "exit after 8 bars or at target/stop", "stop_rule": "2.0 ATR(20)",
    "target_rule": "1.5 R", "holding_horizon": "8 H1 bars",
    "falsifier": "fade return <= 0 net of costs over the dev sample",
    "economic_mechanism": "dealers hedge USD index moves late in NY and over-shoot EURUSD",
    "forced_actor": "USD index hedgers", "mechanism_class": "inventory_hedging",
    "data_inputs": [{"series_id": "usd", "source": "desk driver"}],
}


def _packet(**sections: Any) -> dict[str, Any]:
    base = {"universe": {"symbols": 4}, "data_and_features": {"dirs": 1},
            "research_frontier": {"docket_rows": 1}, "conversion_inventory": {"queue": 1},
            "empirical_memory": {"rows": 1}, "portfolio_opportunity_state": {"sleeves": 1},
            "point_in_time_metadata": {"a": 1}, "resource_state": {"cpu": 4}}
    base.update(sections)
    return {"status": "MEASURED", "packet_hash": "p" * 64, "sections": base}


# ------------------------------------------------------------------- contract (10, 16)

def test_an_exact_formula_candidate_is_testable_now(root: Path) -> None:
    rec = core.validate(dict(EXACT), _ctx(root))
    o = rec["object"]
    assert o["disposition"] == "TESTABLE_NOW", o["reasons"]
    assert o["symbols"] == ["EURUSD"]            # registry spelling
    assert o["schema_version"] == core.SCHEMA_VERSION


def test_vague_rules_are_refused_not_repaired(root: Path) -> None:
    o = core.validate({**EXACT, "entry_rule": "enter on a strong trend"}, _ctx(root))["object"]
    assert o["disposition"] == "NEEDS_RULE_EXTRACTION"
    assert o["object_type"] == "MECHANISM_HYPOTHESIS"
    assert any(r.startswith("VAGUE_RULE") for r in o["reasons"])


def test_an_unknown_series_becomes_a_data_request(root: Path) -> None:
    rec = core.validate({**EXACT, "data_inputs": [{"series_id": "lme_cancelled_warrants"}]},
                       _ctx(root))
    assert rec["object"]["disposition"] == "NEEDS_DATA"
    assert rec["data_requests"][0]["variable"] == "lme_cancelled_warrants"


def test_an_invalid_expression_or_unregistered_family_is_named(root: Path) -> None:
    bad = core.validate({**EXACT, "params": {**EXACT["params"], "expr": "mean(close, 20)"}},
                       _ctx(root))["object"]
    assert bad["disposition"] == "NEEDS_RULE_EXTRACTION"
    assert any("EXPR" in r for r in bad["reasons"])
    new = core.validate({**EXACT, "family": "gamma_flip_sniper"}, _ctx(root))["object"]
    assert new["disposition"] == "NEEDS_NEW_EXECUTABLE_FAMILY"


def test_banal_indicator_rules_are_not_discoveries(root: Path) -> None:
    o = core.validate({**EXACT, "title": "RSI 30 oversold bounce",
                      "data_inputs": [{"series_id": "close"}]}, _ctx(root))["object"]
    assert o["disposition"] == "INVALID" and "BANAL_INDICATOR_VARIANT" in o["reasons"]


def test_simple_but_new_is_accepted(root: Path) -> None:
    o = core.validate({**EXACT, "params": {"expr": "sign(delta(oil, 24))", "side_mode": "follow"},
                      "title": "oil 24-bar impulse leads CAD-free USD"}, _ctx(root))["object"]
    assert o["disposition"] == "TESTABLE_NOW", o["reasons"]


def test_unparseable_reply_is_schema_invalid_not_a_crash() -> None:
    assert core.parse_objects("I think gold goes up") == ([], "SCHEMA_INVALID")
    objs, st = core.parse_objects('Sure:\n```json\n{"objects": [{"title": "x"}]}\n```')
    assert st == "OK" and objs == [{"title": "x"}]
