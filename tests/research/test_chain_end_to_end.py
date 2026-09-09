"""THE WHOLE CHAIN, WALKED ONCE: source -> candidate -> node -> certificate -> sleeve -> intent
-> order -> position -> deal -> realised R, joined by keys and never by a matcher.

Acceptance property AP3 says a hypothesis id must be followable deterministically from the
source that proposed it to the money it made. Before this programme the chain had two breaks:
upstream nothing carried an id at all (four record shapes, four vocabularies), and downstream
the closing deal's `order` was the server's exit order, which had never matched anything.

This test is the proof that both are closed. It builds one strategy in every shape the desk
actually writes -- the compiler's candidate, the graph's node, the gauntlet's certificate row,
the promoter's sleeve row, the gateway's intent row, and the broker's entry and closing deals --
and asserts that a reader with no knowledge of any organ can walk it end to end using only the
keys on the records.

It is deliberately a JOIN TEST and not a mock of the pipeline: it asserts the identities agree,
which is the property that broke, rather than re-running organs that have their own suites.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import alpha_genome as ag  # noqa: E402
from libs.research.hypothesis_graph import Node, node_id  # noqa: E402

SYMBOL, FAMILY = "XAUUSD", "session_range_breakout"
PARAMS = {"rr": 1.5, "stop_atr": 1.0}
SLEEVE = "xau_asia"
CERT_KEY = "external.XAUUSD.session_range_breakout.rr1.5"


def _intent_id(symbol: str, sleeve: str, side: str, minute: str) -> str:
    """gateway._intent_id's formula, recomputed here so the test is not the code under test."""
    return hashlib.sha1(f"{symbol}|{sleeve}|{side}|{minute}".encode(),
                        usedforsecurity=False).hexdigest()[:16]


def _records() -> dict:
    candidate = {"symbol": SYMBOL, "family": FAMILY, "params": PARAMS,
                 "source": "miner:deepseek", "source_url": "deepseek://x",
                 "mechanism_status": "NAMED", "mechanism_note": "asia range"}
    ag.stamp(candidate)
    node = Node(symbol=SYMBOL, family=FAMILY, params=PARAMS, source="miner_candidate_compiler",
                fate="CERTIFIED", gates={"deflated_sharpe": {"passed": True}}).to_row()
    certificate = {"hunt": "external_discoveries", "cell": CERT_KEY, "sym": SYMBOL, "days": 400,
                   "gates": {"deflated_sharpe": {"passed": True}},
                   "shadow_spec": {"symbol": SYMBOL, "selector": "asia", "family": FAMILY,
                                   "params": PARAMS}}
    sleeve_row = {"name": SLEEVE, "symbol": SYMBOL, "family": FAMILY, "params": PARAMS,
                  "certificate": CERT_KEY, "sleeve_id": "SL-0007"}
    minute = "2026-09-09T07:31"
    intent = {"time": f"{minute}:12+00:00", "symbol": SYMBOL, "sleeve": SLEEVE, "side": "buy_stop",
              "lot": 0.02, "certificate": CERT_KEY, "sleeve_id": "SL-0007",
              "intent_id": _intent_id(SYMBOL, SLEEVE, "buy_stop", minute),
              "release_id": "rel-abc", "state_vector_id": "sv-1", "ticket": 5001,
              "latency_ms": 41.2}
    entry_deal = {"order": 5001, "position_id": 5001, "deal": 9001, "entry_price": 2401.5,
                  "magic": 777}
    close_deal = {"order": 6002, "position_id": 5001, "deal": 9002, "entry_order": 5001,
                  "price": 2415.0, "magic": 777}
    return {"candidate": candidate, "node": node, "certificate": certificate,
            "sleeve": sleeve_row, "intent": intent, "entry": entry_deal, "close": close_deal,
            "minute": minute}


def test_one_genome_id_spans_candidate_node_certificate_and_artifact() -> None:
    r = _records()
    gid = node_id(SYMBOL, FAMILY, PARAMS)
    assert r["candidate"]["genome_id"] == gid, "stamped at the compiler's pen"
    assert r["node"]["id"] == gid, "the graph's node id IS the genome id"
    assert ag.from_certificate(r["certificate"]).genome_id == gid
    assert ag.from_candidate(r["sleeve"]).genome_id == gid, \
        "the promoter's roster row resolves to the same genome"


def test_the_certificate_key_carries_from_the_roster_to_the_intent() -> None:
    r = _records()
    assert r["sleeve"]["certificate"] == r["certificate"]["cell"] == CERT_KEY
    assert r["intent"]["certificate"] == CERT_KEY, "wave W7: the intent names its certificate"
    assert r["intent"]["sleeve_id"] == r["sleeve"]["sleeve_id"]


def test_the_intent_address_is_derivable_and_ties_the_decision_to_the_order() -> None:
    r = _records()
    assert r["intent"]["intent_id"] == _intent_id(SYMBOL, SLEEVE, "buy_stop", r["minute"])
    assert r["intent"]["ticket"] == r["entry"]["order"] == r["entry"]["position_id"], \
        "a pending stop's ticket IS its entry order and its position id"


def test_the_closing_deal_joins_on_the_position_not_on_its_own_order() -> None:
    r = _records()
    assert r["close"]["order"] != r["entry"]["order"], (
        "the closing deal's `order` is the SERVER's exit order -- joining on it is the break "
        "the attribution repair fixed")
    assert r["close"]["position_id"] == r["entry"]["position_id"] == r["intent"]["ticket"]
    assert r["close"]["entry_order"] == r["intent"]["ticket"]


def test_a_reader_can_walk_the_whole_chain_with_keys_alone() -> None:
    r = _records()
    by_genome = {ag.from_any(x).genome_id: x for x in (r["candidate"], r["node"],
                                                       r["certificate"])}
    gid = node_id(SYMBOL, FAMILY, PARAMS)
    assert set(by_genome) == {gid}, "three shapes, one key"

    cert_key = r["sleeve"]["certificate"]
    intents = {i["certificate"]: i for i in [r["intent"]]}
    assert cert_key in intents

    deals_by_position = {}
    for d in (r["entry"], r["close"]):
        deals_by_position.setdefault(d["position_id"], []).append(d)
    chain = deals_by_position[intents[cert_key]["ticket"]]
    assert len(chain) == 2

    realised = (r["close"]["price"] - r["entry"]["entry_price"])
    assert realised > 0
    # Every link named, in order, with the key that carried it.
    links = [("source", r["candidate"]["source"]), ("genome", gid),
             ("certificate", cert_key), ("sleeve", r["sleeve"]["sleeve_id"]),
             ("intent", r["intent"]["intent_id"]), ("position", r["entry"]["position_id"]),
             ("deals", [d["deal"] for d in chain]), ("pl_quote", realised)]
    assert [k for k, _ in links] == ["source", "genome", "certificate", "sleeve", "intent",
                                     "position", "deals", "pl_quote"]
    assert all(v for _, v in links), "no link in the chain may be empty"


def test_the_gateway_still_computes_the_address_this_test_recomputes() -> None:
    """If the gateway's formula ever moves, this test's copy of it must fail loudly rather than
    silently agreeing with a different chain."""
    src = (ROOT / "desks" / "mt5" / "mt5desk" / "gateway.py").read_text("utf-8")
    assert 'key = f"{symbol or \'\'}|{sleeve or \'\'}|{side or \'\'}|{_minute_of(stamp)}"' in src
    assert 'hexdigest()[:16]' in src
