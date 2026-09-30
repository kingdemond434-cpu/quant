"""THE IDENTITY CHAIN organ (item 1, 2026-09-29): every live deal walked back to its bars, each
link graded, the fraction that resolves with no fuzzy join published and ratcheted.

Every fixture is synthetic and lives in tmp_path: the organ's default paths are the desk's live
records and a test must never append to them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import identity_chain as ic  # noqa: E402

from libs.research import trade_identity as ti  # noqa: E402

SPEC = {"symbol": "EURCHF", "family": "discovered", "selector": "asia",
        "params": {"feature": "dd_12", "band": [0.75, 0.9], "horizon": 1, "side": -1}}
CERT = "external.EURCHF.discovered.p=aaaa"


def _jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return path


def _world(tmp: Path, deals: list[dict], *, sleeves: list[dict] | None = None,
           intents: list[dict] | None = None) -> ic.Sources:
    long_name = "eurchf_discovered_asia_p_aaaaaaaaaaaaaaaa"
    sl = sleeves if sleeves is not None else [
        {"name": long_name, "symbol": "EURCHF", "status": "LIVE",
         "certificate": {"cell": CERT},
         "admission": {"status": "LIVE", "risk_frac": 0.01, "joined": f"joined on '{long_name}'"}},
        {"name": "gold_afternoon_v2", "symbol": "XAUUSD", "status": "LIVE", "certificate": None,
         "admission": {"joined": "joined on 'xauusd|afternoon'"}},
        {"name": "gold_afternoon_v3", "symbol": "XAUUSD", "status": "LIVE", "certificate": None,
         "admission": {"joined": "joined on 'xauusd|afternoon'"}},
    ]
    (tmp / "sleeves.json").write_text(json.dumps({"sleeves": sl}), "utf-8")
    ident = {**SPEC, "direction": "SHORT", "timeframe": "H1", "condition": None,
             "code_hash": "c0de", "cost_hash": "c057", "data_venue": "MT5:X",
             "sleeve_id": "s1", "behaviour_hash": "b1"}
    (tmp / "registry.json").write_text(json.dumps({"sleeves": {
        "EURCHF.discovered.asia#x": {"identity": ident, "frozen_at": "2026-09-01"}}}), "utf-8")
    (tmp / "canon.json").write_text(json.dumps({"gate_policy": {"version": "t"}, "survivors": {
        CERT: {"hunt": "external_discoveries", "sym": "EURCHF", "days": 500,
               "gates": {"deflated_sharpe": {"passed": True, "n_trials": 597}},
               "shadow_spec": SPEC}}}), "utf-8")
    (tmp / "input.json").write_text(json.dumps({"rollup": "r0", "files": {
        "EURCHF_H1.parquet": {"sha": "abc", "bytes": 1, "mtime": "t"}}}), "utf-8")
    return ic.Sources(live_ledger=_jsonl(tmp / "live.jsonl", deals),
                      intents=_jsonl(tmp / "intents.jsonl", intents or []),
                      decisions=_jsonl(tmp / "decisions.jsonl", []),
                      sleeves=tmp / "sleeves.json", registry=tmp / "registry.json",
                      canon=tmp / "canon.json", input_identity=tmp / "input.json")


def _deal(deal: int, sleeve: str, entry_order: int | None = None) -> dict:
    return {"deal": deal, "sleeve": sleeve, "symbol": "EURCHF", "entry_order": entry_order,
            "position_id": entry_order, "pl_quote": 1.0, "r_multiple": 0.5,
            "account_kind": "live", "time": "2026-09-20T01:00:00+00:00"}


def test_a_fully_joined_deal_is_clean_and_has_a_chain_head(tmp_path: Path) -> None:
    name = "eurchf_discovered_asia_p_aaaaaaaaaaaaaaaa"
    src = _world(tmp_path, [_deal(1, name, 77)],
                 intents=[{"ticket": 77, "sleeve": name, "symbol": "EURCHF"}])
    r = ic.resolve(src.deals[0], src)
    assert r["verdict"] == "CLEAN", r["joins"]
    assert r["joins"]["certificate->clock"]["class"] == ti.CONTENT
    assert r["chain"]["complete"] and r["tag"] == r["chain"]["head"][:ti.TAG_LEN]


def test_a_truncated_order_comment_is_a_fuzzy_join_never_a_clean_one(tmp_path: Path) -> None:
    src = _world(tmp_path, [_deal(2, "eurchf_discovered_asia_p_aa", 78)],
                 intents=[{"ticket": 78, "sleeve": "", "symbol": "EURCHF"}])
    r = ic.resolve(src.deals[0], src)
    assert r["joins"]["fill->sleeve"]["class"] == ti.FUZZY
    assert r["verdict"] == ti.FUZZY


def test_a_broker_comment_and_a_shared_prefix_are_broken(tmp_path: Path) -> None:
    src = _world(tmp_path, [_deal(3, "[sl 0.94555]", 79), _deal(4, "gold_afternoon", 80)])
    a, b = (ic.resolve(d, src) for d in src.deals)
    assert a["joins"]["fill->sleeve"]["class"] == ti.BROKEN
    assert "broker overwrote" in a["joins"]["fill->sleeve"]["why"]
    assert b["joins"]["fill->sleeve"]["class"] == ti.BROKEN
    assert "ambiguous" in b["joins"]["fill->sleeve"]["why"]
    # An order no journal recorded is broken too: the join must be carried, not inferred.
    assert a["joins"]["fill->order"]["class"] == ti.BROKEN


def test_a_composite_allocator_key_is_fuzzy(tmp_path: Path) -> None:
    s = {"admission": {"joined": "joined on 'eurchf|discovered|asia' (funded book)"}}
    j, payload = ic.link_sleeve_allocation("eurchf_discovered_asia_p_x", s)
    assert j["class"] == ti.FUZZY and payload["key"] == "eurchf|discovered|asia"
    j, _ = ic.link_sleeve_allocation("x", {"admission": {"joined": "no allocator row answers"}})
    assert j["class"] == ti.BROKEN


def test_the_ledger_is_append_only_hash_chained_and_deduplicated(tmp_path: Path) -> None:
    name = "eurchf_discovered_asia_p_aaaaaaaaaaaaaaaa"
    src = _world(tmp_path, [_deal(1, name, 77), _deal(2, "[tp 1.0]", 78)],
                 intents=[{"ticket": 77, "sleeve": name}])
    led, rep = tmp_path / "chain.jsonl", tmp_path / "report.json"
    doc = ic.build(src, ledger=led, report=rep)
    assert doc["ledger"]["appended"] == 2 and doc["ledger"]["verdict"] == "INTACT"
    assert doc["n_deals"] == 2 and doc["clean"] == 1 and doc["clean_fraction"] == 0.5
    first = led.read_text("utf-8")
    again = ic.build(src, ledger=led, report=rep)
    assert again["ledger"]["appended"] == 0 and led.read_text("utf-8") == first
    rows = ic.ledger_rows(led)
    rows[0]["verdict"] = "EDITED"
    assert ic.verify_ledger(rows)["verdict"] == "BROKEN"


def test_a_recorded_trade_is_reconstructable_from_its_row_alone(tmp_path: Path) -> None:
    name = "eurchf_discovered_asia_p_aaaaaaaaaaaaaaaa"
    src = _world(tmp_path, [_deal(1, name, 77)], intents=[{"ticket": 77, "sleeve": name}])
    led = tmp_path / "chain.jsonl"
    ic.build(src, ledger=led, report=tmp_path / "r.json")
    # The roster, the canon and the registry all move on; the row still reconstructs.
    later = tmp_path / "later"
    later.mkdir()
    empty = _world(later, [], sleeves=[])
    out = ic.reconstruct(1, empty, ledger=led)
    assert out["source"] == "ledger" and out["recomputed"]["intact"]
    assert out["row"]["nodes"]["certificate"]["cert"] == CERT


def test_the_clean_fraction_ratchets(tmp_path: Path) -> None:
    name = "eurchf_discovered_asia_p_aaaaaaaaaaaaaaaa"
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps({"high_water": 0.9}), "utf-8")
    src = _world(tmp_path, [_deal(1, name, 77), _deal(2, "[tp 1]", 78)],
                 intents=[{"ticket": 77, "sleeve": name}])
    doc = ic.build(src, ledger=tmp_path / "l.jsonl", report=rep)
    assert doc["high_water"] == 0.9 and doc["ratchet_ok"] is False


def test_no_deals_is_unmeasured_not_clean(tmp_path: Path) -> None:
    doc = ic.build(_world(tmp_path, []), ledger=tmp_path / "l.jsonl",
                   report=tmp_path / "r.json")
    assert doc["status"] == "UNMEASURED" and doc["clean_fraction"] is None


def test_the_order_tag_switch_is_on_and_the_gateway_sends_it() -> None:
    """The chain head rides on every new order (blueprint identity chain, 2026-09-30)."""
    assert ic.PROPOSED_ORDER_TAG is True
    src = (DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert src.count('"comment": _ident["comment"]') == 3, (
        "bracket, family and scalp sends must each carry the identity-tagged comment")


@pytest.mark.parametrize("path", [ic.LIVE_LEDGER, ic.SLEEVES])
def test_the_default_sources_are_the_desks_own_records(path: Path) -> None:
    assert path.parent == DESK / "data"
