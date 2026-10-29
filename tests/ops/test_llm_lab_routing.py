"""LLM lab routing: novelty, freeze, typed routing, requests and coverage debt.

Every test runs in a temporary root; nothing here writes the repository's own state."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from libs.ops import llm_lab_core as core
from libs.ops import llm_lab_routing as routing

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


# ------------------------------------------------------------- novelty / genealogy (15)

def test_duplicates_collapse_and_neighbours_share_a_trial_family(root: Path) -> None:
    ctx = _ctx(root)
    o = core.validate(dict(EXACT), ctx)["object"]
    n1 = routing.novelty(o, [])
    assert n1["class"] == "GENUINELY_NOVEL"
    f = routing.freeze(root, o, n1, {"model": "m"})
    assert f["status"] == "FROZEN_PRE_EVALUATION"
    mem = core.load_memory(root)
    assert routing.novelty(o, mem)["class"] == "EXACT_DUPLICATE"
    p2 = core.validate({**EXACT, "params": {**EXACT["params"], "entry_z": 2.0}}, ctx)["object"]
    n2 = routing.novelty(p2, mem)
    assert n2["class"] == "PARAMETER_NEIGHBOUR"
    assert n2["trial_family_id"] == f["trial_family_id"]
    x = core.validate({**EXACT, "symbols": ["GBPUSD"]}, ctx)["object"]
    assert routing.novelty(x, mem)["class"] == "CROSS_ASSET_TRANSLATION"


def test_a_frozen_id_changes_when_any_rule_changes(root: Path) -> None:
    ctx = _ctx(root)
    a = core.validate(dict(EXACT), ctx)["object"]
    b = core.validate({**EXACT, "stop_rule": "2.5 ATR(20)"}, ctx)["object"]
    fa = routing.freeze(root, a, routing.novelty(a, []), {})
    fb = routing.freeze(root, b, routing.novelty(b, []), {})
    assert fa["hypothesis_id"] != fb["hypothesis_id"]


# --------------------------------------------------------------------- routing (21)

def _route(root: Path, objs: list[dict[str, Any]]) -> dict[str, Any]:
    ctx = _ctx(root)
    recs = [core.validate(o, ctx) for o in objs]
    return routing.route(root, recs, lab="B", prov={"model": "deepseek/x"}, ctx=ctx,
                     memory=ctx["memory"])


def test_exact_candidates_reach_the_compiler_as_exact_recipes(root: Path) -> None:
    out = _route(root, [dict(EXACT)])
    assert out["counts"]["exact"] == 1
    doc = json.loads(Path(out["donated_to"]).read_text("utf-8"))
    row = doc["discoveries"][0]
    assert row["params"]["expr"] == EXACT["params"]["expr"]
    assert row["params"]["session"] == "ny"
    assert row["url"].startswith("deepseek://B/dsh_")
    # The SAME compiler door every miner uses: EXACT_RECIPE, no DeepSeek lane.
    sys.path.insert(0, str(REPO / "desks/mt5/research"))
    sys.path.insert(0, str(REPO / "desks/mt5"))
    import miner_candidate_compiler as mcc
    cands, why = mcc.compile_row("deepseek", row, {"EURUSD", "GBPUSD"})
    assert why == "EXACT_RECIPE"
    assert cands[0]["family"] == "formula" and cands[0]["source_url"] == row["url"]


def test_duplicate_output_is_collapsed_not_donated_twice(root: Path) -> None:
    _route(root, [dict(EXACT)])
    out = _route(root, [dict(EXACT)])
    assert out["counts"] == {"duplicate": 1} and out["donated_to"] is None


def test_incomplete_output_enters_deepening_and_invalid_is_named(root: Path) -> None:
    out = _route(root, [{"object_type": "MECHANISM_HYPOTHESIS", "title": "pension rebalancing",
                         "mechanism": "month-end rebalancing sells winners"},
                        {"object_type": "NEGATIVE_KNOWLEDGE", "title": "x"}])
    assert out["counts"].get("deepening") == 1
    row = json.loads(Path(out["donated_to"]).read_text("utf-8"))["discoveries"][0]
    assert row["kind"] == "hypothesis" and "params" not in row
    assert any(r["route"] == "NEGATIVE_MEMORY" for r in out["receipts"])


def test_data_request_lifecycle_reaches_the_frontier_and_resumes(root: Path) -> None:
    _route(root, [{**EXACT, "data_inputs": [{"series_id": "lme_warrants"}]}])
    reqs = json.loads((root / core.REQUESTS).read_text("utf-8"))
    (rid, r), = reqs["open"].items()
    assert r["object_type"] == "DATA_REQUEST" and r["parent_hypothesis"].startswith("dsh_")
    frontier = json.loads((root / core.FRONTIER).read_text("utf-8"))
    assert frontier["vectors"]["deepseek data request: lme_warrants"]["outcome"] == "NAMED_ONLY"
    q: dict[str, Any] = {"jobs": {}}
    assert routing.recheck_requests(root, {"eurusd"}, q) == []
    assert routing.recheck_requests(root, {"lme_warrants"}, q) == [rid]
    (job,) = q["jobs"].values()
    assert job["lab"] == "CONV" and job["trigger"].startswith("resume:dsh_")


def test_representation_with_a_valid_expr_becomes_a_formula_candidate(root: Path) -> None:
    out = _route(root, [{"object_type": "REPRESENTATION_REQUEST", "title": "usd persistence",
                         "symbols": ["USDJPY"], "expr": "ts_rank(usd, 48)"}])
    assert out["counts"].get("exact") == 1


def test_coverage_debt_waits_for_the_parent_verdict_then_drains_by_cursor(root: Path) -> None:
    out = _route(root, [dict(EXACT)])
    hid = out["receipts"][0]["hypothesis_id"]
    d0 = routing.drain_debt(root, 10)
    assert d0["donated"] == 0 and d0["awaiting_parent_verdict"] == 2   # owed, not dropped
    (root / core.ATTRIBUTION).write_text(json.dumps(
        {"gauntlet": {"verdicts": {hid: {"judged": 1, "passed": 0}}}}), "utf-8")
    d1 = routing.drain_debt(root, 1)
    assert d1["donated"] == 1 and d1["owed"] == 1      # GBPUSD, USDJPY: one now, one owed
    d2 = routing.drain_debt(root, 10)
    assert d2["donated"] == 1 and d2["owed"] == 0
    assert routing.drain_debt(root, 10)["donated"] == 0
