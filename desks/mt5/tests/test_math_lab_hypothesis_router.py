"""The math lab as a PhD team: hypotheses in, the fitting mathematics per hypothesis, and compute
earned on yield (2026-11-13).

Pins: routing by mechanism, the 90/10 exotic cap at panel selection, newest-first hypothesis
intake that never reads the lab's own output, the yield ladder (survivors > judged > cells >
donated), the zero-yield exploration floor, and MATH_LAB.json in the box publish list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.mathlab import hypothesis_router as HR  # noqa: E402
from research.mathlab import scientists as S  # noqa: E402

from research import math_lab as ML  # noqa: E402

ROOT = DESK.parents[1]


def test_a_regime_hypothesis_goes_to_state_space_and_change_point():
    tools = HR.route({"mechanism": "a volatility regime switch after the London fix"}, S.REGISTRY)
    names = [t["tradition"] for t in tools]
    assert names[0] == "dynamical_systems" and "change_point" in names
    assert len(names) >= 4 and all(t["why"] for t in tools)
    assert len(names) == len(set(names))


def test_routing_takes_every_fitting_tradition_ranked_by_yield_and_drops_the_non_earner():
    hyp = {"mechanism": "a volatility regime switch after the London fix"}
    every = [t["tradition"] for t in HR.route(hyp, S.REGISTRY)]
    yields = {"koopman_dmd": 3.0, "change_point": 1.0, "dynamical_systems": 0.0}
    ranked = HR.route(hyp, S.REGISTRY, yields, zero_yield={"dynamical_systems"})
    names = [t["tradition"] for t in ranked]
    assert names[:2] == ["koopman_dmd", "change_point"]
    assert "dynamical_systems" not in names
    assert set(names) == set(every) - {"dynamical_systems"}
    assert ranked[0]["tier"] == "earning" and ranked[-1]["tier"] == "unpriced"
    lone = HR.route({"mechanism": "zzz"}, S.REGISTRY, {}, zero_yield={"symbolic_regression",
                                                                      "information_theory"})
    assert len(lone) == 1, "a hypothesis is never left with no tradition at all"


def test_every_toolkit_tradition_is_a_live_scientist():
    named = {t for _, _, tools in HR.TOOLKIT for t, _ in tools} | {t for t, _ in HR.DEFAULT_TOOLS}
    assert named <= set(S.REGISTRY), sorted(named - set(S.REGISTRY))


def test_a_lead_lag_hypothesis_goes_to_graph_and_transfer_entropy():
    tools = HR.route({"mechanism": "gold leads the yen cross by an hour"}, S.REGISTRY)
    assert {t["tradition"] for t in tools} >= {"graph_theory"}
    assert tools[0]["class"] == "lead_lag"


def test_an_unclassified_hypothesis_still_gets_a_tool_and_a_reason():
    tools = HR.route({"mechanism": "zzz qqq"}, S.REGISTRY)
    assert tools and tools[0]["class"] == "unclassified" and tools[0]["why"]


def test_exotic_and_gap_classification():
    assert HR.is_exotic("USDTRY") and HR.is_exotic("EURZAR")
    assert not HR.is_exotic("EURUSD") and not HR.is_exotic("XAUUSD")
    assert not HR.is_exotic("US500")
    assert HR.gap_weight("XAUUSD") == 2 and HR.gap_weight("US500") == 2
    assert HR.gap_weight("EURJPY") == 1 and HR.gap_weight("AUDNZD") == 0


def test_exotics_are_held_to_ten_percent_of_slots_but_never_leave_the_lab_empty():
    assert HR.cap_exotics(["USDTRY", "EURUSD", "USDZAR", "XAUUSD"], 4) == ["EURUSD", "XAUUSD"]
    assert HR.cap_exotics(["USDTRY"], 4) == ["USDTRY"]
    ten = [f"X{i}" for i in range(9)]
    assert "USDTRY" in HR.cap_exotics(["USDTRY", *ten], 10)


def _hyp(hid: str, target: str, mechanism: str, *, original: bool = False) -> dict[str, Any]:
    return {"hypothesis_id": hid, "generator": "llm_lab", "origin": "DESK" if original else "",
            "target": target, "mechanism": mechanism, "created_at": "2026-11-13",
            "original": original, "gap_weight": HR.gap_weight(target),
            "exotic": HR.is_exotic(target)}


def test_plan_ranks_gaps_and_originals_and_logs_every_route():
    hyps = [_hyp("h1", "AUDNZD", "mean reversion of the spread"),
            _hyp("h2", "XAUUSD", "regime switch at the Asia open"),
            _hyp("h3", "USDTRY", "carry trade flow"),
            _hyp("h4", "EURJPY", "momentum after the fix", original=True)]
    targets, by_tradition, log, status = HR.plan(hyps, S.REGISTRY, 2)
    assert targets == ["EURJPY", "XAUUSD"]
    assert len(log) == 4 and all(entry["tools"] for entry in log)
    assert "USDTRY" in status["exotic_held_back"]
    assert all(set(v) <= set(targets) for v in by_tradition.values())


def test_hypotheses_are_read_newest_first_and_never_from_the_lab_itself(tmp_path):
    from libs.moat import registry as R
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        conn = R.connect()
        for i, (gen, asset, mech) in enumerate([
                ("llm_lab", "EURUSD", "old regime idea"),
                ("math:spectral", "EURUSD", "the lab's own object"),
                ("residual_hunt", "GBPUSD", "residual question"),
                ("idea_proposer", "BTCUSD", "not a huntable symbol here"),
                ("idea_proposer", "XAUUSD", "new lead-lag idea")]):
            R.record_discovery(source_id=f"s{i}", source_type="t", mechanism=mech,
                               origin="DESK", generator=gen, assets=[asset], conn=conn)
            conn.execute("UPDATE discoveries SET created_at=? WHERE source_id=?",
                         (f"2026-11-13T0{i}:00:00Z", f"s{i}"))
        conn.commit()
        hyps, status = HR.load_hypotheses(["EURUSD", "GBPUSD", "XAUUSD"], conn=conn)
        conn.close()
    finally:
        R.set_path(None)
    assert status["status"] == "MEASURED"
    assert [h["mechanism"] for h in hyps] == ["new lead-lag idea", "old regime idea"]
    assert status["set_aside_no_huntable_symbol"] == 1
    assert hyps[0]["original"] is True


def test_zero_yield_keeps_only_the_floor_unless_a_hypothesis_was_routed():
    names = ("spectral", "topology", "causal", "geometry")
    roi = {"spectral": 2.0, "topology": 0.0, "causal": 0.0, "geometry": None}
    plan = ML.allocation(roi, None, names, zero_yield={"topology", "causal"},
                         demand={"causal": 3.0})
    t = plan["traditions"]
    assert t["topology"]["share"] == pytest.approx(ML.FLOOR_SHARE)
    assert t["causal"]["share"] > t["topology"]["share"]
    assert t["spectral"]["share"] > t["causal"]["share"]
    assert plan["sum"] == pytest.approx(1.0, abs=1e-4)
    assert "exploration floor" in t["topology"]["why"]
    assert t["causal"]["hypotheses_routed"] == 3


def test_when_everything_is_zero_yield_and_unrouted_the_rest_is_released_not_spent():
    names = ("spectral", "topology")
    plan = ML.allocation(dict.fromkeys(names, 0.0), None, names, zero_yield=set(names))
    assert all(v["share"] == pytest.approx(ML.FLOOR_SHARE) for v in plan["traditions"].values())
    assert plan["released_share"] == pytest.approx(1.0 - 2 * ML.FLOOR_SHARE)


def test_the_yield_ladder_prices_every_tradition_on_the_same_highest_rung(tmp_path):
    from libs.moat import registry as R
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        for name, hours in (("spectral", 3.0), ("topology", 3.0), ("causal", 1.0)):
            R.generator_yield_update(f"math:{name}", compute_s=hours * 3600, generated=10)
        roi, detail = ML.tradition_roi(("spectral", "topology", "causal"),
                                       cells={"spectral": {"cells": 6, "judged": 3,
                                                           "survived": 0}})
    finally:
        R.set_path(None)
    assert detail["rung"] == "judged"
    assert roi["spectral"] == pytest.approx(1.0)
    assert roi["topology"] == 0.0
    assert detail["zero_yield"] == ["topology"]          # causal has under MIN_EVIDENCE_H
    assert detail["rows"]["spectral"]["cells_to_judge_per_compute_hour"] == pytest.approx(1.0)
    assert detail["rows"]["spectral"]["cells_per_compute_hour"] == pytest.approx(2.0)


def test_each_tradition_works_its_routed_panel_and_the_rest_take_the_scout():
    class P:
        def __init__(self, target: str) -> None:
            self.target = target
    panels = [P("XAUUSD"), P("EURJPY"), P("GBPUSD")]
    routing = {"targets": ["XAUUSD", "EURJPY"],
               "by_tradition": {"dynamical_systems": ["XAUUSD"], "graph_theory": ["EURJPY"]}}
    out = ML.route_panels(["dynamical_systems", "graph_theory", "topology"], panels, routing)
    assert [p.target for p in out["dynamical_systems"]] == ["XAUUSD"]
    assert [p.target for p in out["graph_theory"]] == ["EURJPY"]
    assert [p.target for p in out["topology"]] == ["GBPUSD"]
    legacy = ML.route_panels(["topology"], panels, {})
    assert len(legacy["topology"]) == 3


def test_math_lab_json_is_published_from_the_box():
    sync = (ROOT / "desks/mt5/scripts/sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/MATH_LAB.json"' in sync
    ignore = (ROOT / ".gitignore").read_text("utf-8")
    assert "!desks/mt5/reports/MATH_LAB.json" in ignore.splitlines()


def test_llm_lab_orig_and_gap_tags_and_the_idea_queue_mirror_are_read_original_first(tmp_path):
    ideas = tmp_path / "orig_ideas.json"
    ideas.write_text(json.dumps({"ideas": [
        {"id": "IQ-1", "symbols": ["XAUUSD"], "mechanism": "fix imbalance leads the index",
         "breadth_gap": ["gold_metals"]}]}), "utf-8")
    lab = tmp_path / "llm_lab"
    lab.mkdir()
    (lab / "discoveries_20261113T2100.json").write_text(json.dumps({"discoveries": [
        {"symbol": "EURUSD", "mechanism": "plain idea", "cell_id": "c1"},
        {"symbols": ["USDJPY"], "mechanism": "regime switch", "orig": True,
         "breadth_gap": "usd_jpy_eur_cross", "cell_id": "c2"},
        {"symbols": ["BTCUSD"], "mechanism": "not huntable here", "orig": True}]}), "utf-8")
    out, status = HR.load_file_ideas(["XAUUSD", "EURUSD", "USDJPY"], idea_files=[ideas],
                                     donation_dirs=[lab, tmp_path / "missing"])
    assert [h["hypothesis_id"] for h in out] == ["IQ-1", "c2", "c1"]
    assert out[0]["generator"] == "idea_queue" and out[0]["original"] is True
    assert out[1]["generator"] == "llm_lab" and out[1]["breadth_gap"] == ["usd_jpy_eur_cross"]
    assert out[1]["gap_weight"] == HR.gap_weight("USDJPY") + 1
    assert out[2]["original"] is False
    assert status["set_aside_no_huntable_symbol"] == 1 and status["original"] == 2


def test_the_orig_ideas_mirror_names_only_registry_symbols_and_routes_every_idea():
    doc = json.loads(ML.ORIG_IDEAS.read_text("utf-8"))
    universe = (DESK / "data" / "universe" / "universe.json").read_text("utf-8")
    assert doc["ideas"]
    for idea in doc["ideas"]:
        assert idea["orig"] is True and idea["mechanism"] and idea["falsifier"]
        assert all(f'"{s}"' in universe for s in idea["symbols"]), idea["id"]
        tools = HR.route(idea, S.REGISTRY)
        assert tools and tools[0]["class"] != "unclassified", idea["id"]


def test_option_pricing_ideas_keep_stochastic_calculus_even_when_it_has_earned_nothing_yet():
    doc = json.loads(ML.ORIG_IDEAS.read_text("utf-8"))
    options = [i for i in doc["ideas"] if i["id"].startswith("IQ-OPT-")]
    assert {i["id"] for i in options} == {"IQ-OPT-VRP", "IQ-OPT-HESTON", "IQ-OPT-JUMP"}
    for idea in options:
        tools = HR.route(idea, S.REGISTRY, {"spectral": 5.0},
                         zero_yield={"stochastic_processes", "extreme_value"})
        names = [t["tradition"] for t in tools]
        assert names[0] == "stochastic_processes", idea["id"]
        assert tools[0]["tier"] == "pinned"
        assert any(t["class"] == "option_pricing" for t in tools), idea["id"]


def test_quant_guild_cards_are_intake_with_orig_where_the_mechanism_is_new():
    doc = json.loads(ML.QUANT_GUILD_CARDS.read_text("utf-8"))
    universe = (DESK / "data" / "universe" / "universe.json").read_text("utf-8")
    assert doc["ideas"] and any(i["orig"] for i in doc["ideas"])
    assert any(not i["orig"] for i in doc["ideas"])
    for card in doc["ideas"]:
        assert card["route_kind"] != "method_only"
        assert card["symbols"] and all(f'"{s}"' in universe for s in card["symbols"])
        assert card["orig"] == (card["route_kind"] == "new_family_needed" or card["diff_first"] in
                                ("MISSING", "EXISTS_UNWIRED", "EXISTS_INCOMPLETE"))
    allowed = sorted({s for c in doc["ideas"] for s in c["symbols"]})
    out, _status = HR.load_file_ideas(allowed, idea_files=[("quant_guild", ML.QUANT_GUILD_CARDS)],
                                     donation_dirs=[])
    assert out and all(h["generator"] == "quant_guild" for h in out)
    assert sum(h["original"] for h in out) > 0 and not out[-1]["original"]


def test_llm_lab_revisions_rank_with_originals_and_the_separating_test_is_the_first_test(tmp_path):
    lab = tmp_path / "llm_lab"
    lab.mkdir()
    (lab / "discoveries_20261113T2200.json").write_text(json.dumps({"discoveries": [
        {"symbol": "EURUSD", "mechanism": "plain idea", "cell_id": "p1"},
        {"symbol": "EURUSD", "mechanism": "hardened idea", "lab": "REVISION", "cell_id": "r1",
         "competing_explanations": ["flow", "common dollar shock"],
         "separating_test": "lead-lag controlling the dollar index"}]}), "utf-8")
    queue = tmp_path / "orig_ideas.json"
    queue.write_text(json.dumps({"ideas": [
        {"id": "q-false", "orig": False, "symbols": ["EURUSD"], "mechanism": "a crowded idea"},
        {"id": "q-unsaid", "symbols": ["EURUSD"], "mechanism": "an [ORIG] row"}]}), "utf-8")
    out, _ = HR.load_file_ideas(["EURUSD"], idea_files=[queue], donation_dirs=[lab])
    by_id = {h["hypothesis_id"]: h for h in out}
    assert by_id["q-false"]["original"] is False, "an explicit orig=false is honoured"
    assert by_id["q-unsaid"]["original"] is True
    assert by_id["r1"]["refereed_revision"] is True
    assert by_id["r1"]["first_test"] == "lead-lag controlling the dollar index"
    assert "common dollar shock" in by_id["r1"]["mechanism"]
    order = [h["hypothesis_id"] for h in out]
    assert order.index("r1") < order.index("p1") and order.index("r1") < order.index("q-false")
