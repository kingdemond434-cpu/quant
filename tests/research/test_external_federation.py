"""The open-source research federation's rules: one disposition per system, no fake breadth, no
verdict out of a sandbox, no frontier switched off, and no seed list treated as the universe."""
from __future__ import annotations

import json

import pytest

from libs.research import external_federation as fed


def test_every_seed_is_vocabulary_clean_and_uniquely_named() -> None:
    ids = [s.system_id for s in fed.SEEDS]
    assert len(set(ids)) == len(ids)
    for s in fed.SEEDS:
        assert not s.unknown_capabilities(), (s.system_id, s.unknown_capabilities())
        assert not s.unknown_axes(), (s.system_id, s.unknown_axes())
        assert s.integration in fed.DISPOSITIONS
        assert s.licence == "UNVERIFIED", (
            f"{s.system_id}: a licence nobody has read at the pinned commit is UNVERIFIED, never "
            f"a guess about somebody else's terms")


def test_the_roster_covers_the_principals_named_systems() -> None:
    must = {"rd_agent", "qlib", "agonalpha", "quantaalpha", "alphaagent", "alphacrafter",
            "hubble", "finrl", "lean", "nautilus", "hummingbot", "tradingagents",
            "tradingagents_kr", "tradingagents_cn", "openfr", "quanti", "quantmind",
            "akshare", "tushare", "openbb", "rohonchain", "l1vsun", "bl888m"}
    assert must <= set(fed.SEED_BY_ID)


def test_a_capability_twin_collapses_into_one_lineage() -> None:
    parent = fed.SEED_BY_ID["tradingagents"]
    twin = fed.ExternalSystem("ta_fork_17", "yet another fork", "github:someone/TradingAgents-X",
                              "same agents, new repo name", "DIRECT",
                              parent.capabilities, parent.axes)
    decision = fed.admit(twin, list(fed.SEEDS))
    assert decision.disposition == "DUPLICATE"
    assert decision.duplicate_of == "tradingagents"


def test_a_regional_data_stack_over_a_known_topology_is_a_real_addition() -> None:
    parent = fed.SEED_BY_ID["tradingagents"]
    thai = fed.ExternalSystem("tradingagents_th", "TradingAgents-TH", "public:ta-th",
                              "Thai filings, SET data, local news", "WRAPPED",
                              (*parent.capabilities, "data_source"),
                              ("data", "region_language"), region="th", languages=("th",),
                              lineage_parent="tradingagents")
    decision = fed.admit(thai, list(fed.SEEDS))
    assert decision.disposition in fed.RUNNING_DISPOSITIONS
    assert "region_language" in decision.novel_axes or "data" in decision.novel_axes


def test_admission_refuses_when_the_cost_eats_the_gain() -> None:
    # A genuinely new axis (a Thai-language ecosystem nothing on the roster reaches) with an
    # integration cost that eats the gain: refused WITH EVIDENCE and a reopening condition, which
    # is a decision the desk can revisit -- never a silent drop.
    cand = fed.ExternalSystem("expensive_th", "Expensive", "public:x", "new maths", "DIRECT",
                              ("causal_discovery",), ("region_language",),
                              region="th", languages=("th",))
    assert fed.admit(cand, list(fed.SEEDS)).disposition in fed.RUNNING_DISPOSITIONS
    d = fed.admit(cand, list(fed.SEEDS), ev_capability=1.0, ev_duplication=0.5,
                  integration_cost=2.0)
    assert d.disposition == "REJECTED_WITH_EVIDENCE" and "reopens" in d.why


def test_an_unknown_vocabulary_is_undisposed_not_admitted() -> None:
    cand = fed.ExternalSystem("weird", "Weird", "public:w", "?", "DIRECT",
                              ("telepathy",), ("vibes",))
    assert fed.admit(cand, list(fed.SEEDS)).disposition == "UNDISPOSED"


def test_a_packet_may_never_carry_a_verdict() -> None:
    for row in ({"survivor": True}, {"promote": "yes"}, {"position_size": 0.5},
                {"certified": 1}, {"VERDICT": "pass"}):
        with pytest.raises(ValueError, match="researcher, never a validator"):
            fed.ExternalResearchPacket(system_id="s", run_id="r", commit="c",
                                       candidates=(row,))
    ok = fed.ExternalResearchPacket(system_id="s", run_id="r", commit="c",
                                    candidates=({"family": "carry", "symbol": "XAUUSD"},),
                                    trials_charged=1200)
    assert ok.counts()["candidates"] == 1 and ok.counts()["trials_charged"] == 1200
    assert not ok.empty()


def test_a_packet_cannot_be_built_under_a_loosened_policy() -> None:
    bad = fed.SandboxPolicy(broker_credentials=True)
    assert bad.violations()
    with pytest.raises(ValueError, match="sandbox policy violated"):
        fed.ExternalResearchPacket(system_id="s", run_id="r", commit="c", policy=bad)


def test_operational_names_the_missing_terms() -> None:
    ok, missing = fed.operational(dict.fromkeys(fed.OPERATIONAL_TERMS, True))
    assert ok and missing == ()
    ok2, missing2 = fed.operational({"registered": True, "sandboxed": True, "scheduled": True,
                                     "executed": True, "progressed": False, "produced": True,
                                     "consumed": False})
    assert not ok2 and missing2 == ("progressed", "consumed")


def test_no_frontier_is_ever_switched_off_and_roi_is_two_sided() -> None:
    rows = [{"system_id": "rich", "live_delta_elog": 10.0, "compute_spent": 1.0},
            {"system_id": "poor", "live_delta_elog": 0.1, "compute_spent": 10.0},
            {"system_id": "unmeasured"}]
    alloc = fed.allocation(rows, 3600, floor_s=60)
    assert alloc["rich"] > alloc["poor"] >= 60
    assert alloc["unmeasured"] >= 60, "an unmeasured system draws the exploration prior"
    assert fed.roi(rows[2]) is None and fed.roi({"live_delta_elog": 1.0}) is None


def test_exhaustion_requires_all_twelve_conditions() -> None:
    conds = dict.fromkeys(fed.EXHAUSTION_CONDITIONS, True)
    done, open_ones = fed.exhausted(conds)
    assert done and open_ones == ()
    conds["delta_watch_active"] = False
    done2, open2 = fed.exhausted(conds)
    assert not done2 and open2 == ("delta_watch_active",)


def test_the_ledger_row_carries_every_field_the_law_names() -> None:
    row = fed.ledger_row(fed.SEED_BY_ID["rd_agent"])
    assert set(fed.LEDGER_FIELDS) <= set(row)
    assert row["disposition"] == "UNDISPOSED" and row["sandbox_status"] == "NOT_PROVISIONED"
    assert row["capabilities"] and row["upstream_repo"].startswith("github:")


def test_lineage_collapse_reports_the_branches() -> None:
    lin = fed.collapse_lineage(list(fed.SEEDS))
    assert set(lin["tradingagents"]) >= {"tradingagents_kr", "tradingagents_cn"}


def test_the_roster_round_trips_through_json() -> None:
    back = fed.from_json(fed.to_json(list(fed.SEEDS)))
    assert [s.system_id for s in back] == [s.system_id for s in fed.SEEDS]
    assert json.loads(fed.to_json(list(fed.SEEDS)))[0]["licence"] == "UNVERIFIED"
