"""The content-addressed identity chain's arithmetic (item 1, 2026-09-29)."""
from __future__ import annotations

import pytest

from libs.research import trade_identity as ti


def _nodes() -> dict[str, object]:
    return {k: {"k": k, "v": i} for i, k in enumerate(ti.CHAIN_KINDS)}


def test_a_complete_chain_has_a_head_that_commits_to_every_node() -> None:
    a = ti.chain(_nodes())
    assert a["complete"] and a["broken_at"] is None and a["head"]
    for kind in ti.CHAIN_KINDS:
        n = _nodes()
        n[kind] = {"k": kind, "v": "moved"}
        b = ti.chain(n)
        assert b["head"] != a["head"], f"editing {kind} left the head unchanged"


def test_the_head_is_the_same_on_any_machine_and_for_any_key_order() -> None:
    n = _nodes()
    rev = dict(reversed(list(n.items())))
    assert ti.chain(n)["head"] == ti.chain(rev)["head"]
    assert ti.node_hash("fill", {"a": 1, "b": 2}) == ti.node_hash("fill", {"b": 2, "a": 1})


def test_a_missing_node_breaks_the_chain_there_and_leaves_no_head() -> None:
    n = _nodes()
    n["allocation"] = None
    out = ti.chain(n)
    assert not out["complete"] and out["broken_at"] == "allocation" and out["head"] is None
    links = {r["kind"]: r["link"] for r in out["nodes"]}
    assert links["sleeve"] is not None and links["order"] is None
    assert ti.tag(out["head"]) is None


def test_the_kind_is_inside_the_hash() -> None:
    assert ti.node_hash("order", {"x": 1}) != ti.node_hash("fill", {"x": 1})
    with pytest.raises(ValueError):
        ti.node_hash("rumour", {})


def test_spec_hash_ignores_key_order_and_side_but_not_params() -> None:
    a = {"symbol": "EURCHF", "family": "discovered", "selector": "asia",
         "params": {"feature": "dd_12", "band": [0.75, 0.9]}, "side": None}
    b = {"params": {"band": [0.75, 0.9], "feature": "dd_12"}, "selector": "asia",
         "family": "discovered", "symbol": "EURCHF", "direction": "LONG"}
    assert ti.spec_hash(a) == ti.spec_hash(b)
    c = dict(b, params={"band": [0.75, 0.91], "feature": "dd_12"})
    assert ti.spec_hash(c) != ti.spec_hash(a)


def test_only_exact_and_content_links_are_clean_and_broken_outranks_fuzzy() -> None:
    req = ("a", "b", "c")
    assert ti.classify({"a": {"class": ti.EXACT}, "b": {"class": ti.CONTENT},
                        "c": {"class": ti.EXACT}}, req)["verdict"] == "CLEAN"
    fz = ti.classify({"a": {"class": ti.EXACT}, "b": {"class": ti.FUZZY},
                      "c": {"class": ti.EXACT}}, req)
    assert fz["verdict"] == ti.FUZZY and fz["weak_links"] == ["b"]
    br = ti.classify({"a": {"class": ti.BROKEN}, "b": {"class": ti.FUZZY},
                      "c": {"class": ti.UNMEASURED}}, req)
    assert br["verdict"] == ti.BROKEN
    # An absent link is UNMEASURED, never clean.
    assert ti.classify({"a": {"class": ti.EXACT}}, req)["verdict"] == ti.UNMEASURED


def test_verify_chain_names_the_node_that_moved() -> None:
    n = _nodes()
    rec = ti.chain(n)
    assert ti.verify_chain(rec, n)["intact"]
    n["fill"] = {"k": "fill", "v": "rewritten"}
    v = ti.verify_chain(rec, n)
    assert not v["intact"] and v["moved"] == ["fill"]
