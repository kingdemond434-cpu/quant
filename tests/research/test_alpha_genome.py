"""One strategy, four records, one id. The join AP3 needs is a key, not a matcher."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import alpha_genome as ag  # noqa: E402
from libs.research.hypothesis_graph import node_id  # noqa: E402
from libs.research.strategy_artifact import from_certificate as artifact_from_cert  # noqa: E402

PARAMS = {"lookback": 20, "rr": 1.5}
CAND = {"symbol": "xauusd", "family": "session_range_breakout", "params": PARAMS,
        "source": "miner:reddit", "source_url": "u", "source_title": "t",
        "mechanism_status": "NAMED", "mechanism_note": "asia range"}
NODE = {"id": "x", "region": "r", "symbol": "XAUUSD", "family": "session_range_breakout",
        "params": PARAMS, "source": "reddit", "parent": "", "fate": "CERTIFIED", "why": "",
        "gates": {"dsr": True}, "at": "2026-09-08T00:00:00+00:00"}
CERT = {"hunt": "external_discoveries", "cell": "XAUUSD.session_range_breakout.rr1.5",
        "sym": "XAUUSD", "days": 400, "gates": ["economic_prior", "dsr"],
        "gated_at": "2026-09-08T00:00:00+00:00",
        "shadow_spec": {"symbol": "XAUUSD", "selector": "asia", "family": "session_range_breakout",
                        "is_universe": True, "hunt": "external_discoveries", "condition": None,
                        "params": PARAMS}}


def test_the_four_shapes_are_recognised() -> None:
    art = artifact_from_cert("external.x", CERT).to_dict()
    assert [ag.shape_of(r) for r in (CAND, NODE, CERT, art)] == list(ag.STAGES)
    assert ag.shape_of({"foo": 1}) is None and ag.from_any({"foo": 1}) is None


def test_one_strategy_has_one_id_across_all_four_records() -> None:
    art = artifact_from_cert("external.x", CERT).to_dict()
    ids = {ag.from_any(r).genome_id for r in (CAND, NODE, CERT, art)}
    assert len(ids) == 1, ids
    assert ids == {node_id("XAUUSD", "session_range_breakout", PARAMS)}, \
        "the genome id IS the graph's node id -- one function, never re-spelled"


def test_different_params_are_a_different_genome() -> None:
    other = dict(CAND, params={"lookback": 20, "rr": 2.0})
    assert ag.from_candidate(other).genome_id != ag.from_candidate(CAND).genome_id


def test_stamp_writes_the_id_in_place_and_leaves_strangers_alone() -> None:
    rec = dict(CAND)
    assert ag.stamp(rec) is rec and rec["genome_id"] == ag.from_candidate(CAND).genome_id
    stranger = {"foo": 1}
    assert ag.stamp(stranger) == {"foo": 1}


def test_chain_lists_the_stages_each_genome_reached() -> None:
    art = artifact_from_cert("external.x", CERT).to_dict()
    lonely = {"symbol": "EURUSD", "family": "overnight_gap_decay", "params": {}}
    ch = ag.chain([CAND, NODE, CERT, art, lonely])
    gid = ag.from_candidate(CAND).genome_id
    assert ch[gid] == list(ag.STAGES)
    assert ch[ag.from_candidate(lonely).genome_id] == ["CANDIDATE"]


def test_an_unrunnable_certificate_is_named_not_hidden() -> None:
    cert = dict(CERT, shadow_spec={"symbol": "XAUUSD", "selector": "asia",
                                   "family": "session_range_breakout", "params": None})
    g = ag.from_certificate(cert)
    assert g.certificate["unrunnable"] is True and g.params == {}
    defaults = ag.from_candidate({"symbol": "XAUUSD", "family": "session_range_breakout",
                                  "params": {}})
    assert g.genome_id != defaults.genome_id, \
        "unknown params must not join onto the 'family defaults' genome"
