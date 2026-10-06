"""RESEARCH-LIVE IDENTITY: the spec the gateway trades against the spec research certified.

    python -m pytest desks/mt5/tests/test_research_live_identity.py -q

WHAT MUST NOT REGRESS:

  1. a LIVE row whose five fields agree with its certificate and frozen clock is MATCH
  2. a differing field (params, selector, code whose bytecode moved) is MISMATCH, named, with
     both values; a code difference whose bytecode agrees is prose, not a mismatch
  3. params are recovered the way the gateway recovers them (explicit row params win; else the
     docket digest; a qquant descriptor yields its side)
  4. a row the join cannot make (a gold window, a lane certificate, an unrecoverable cell) is
     UNMEASURED with the reason -- never a match
  5. the Tier S door lists a mismatched LIVE row in review_live, and a stale/absent report
     lists nothing
  6. the organ is an hourly core leg before tier_s
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.tiers import promotion_authority as pa  # noqa: E402
from libs.tiers import research_live_identity as rli  # noqa: E402

CELL = "external.AUDCAD.discovered.p=7c996ac8456c8919"
PARAMS = {"feature": "ext_resid_EURGBP_z", "band": [0.9, 1.0], "horizon": 1, "side": -1}


def _world(**over: Any) -> dict[str, Any]:
    survivors = {CELL: {"cell": "AUDCAD.discovered.p=7c996ac8456c8919", "sym": "AUDCAD",
                        "shadow_spec": {"symbol": "AUDCAD", "selector": "asia",
                                        "family": "discovered", "params": dict(PARAMS)}}}
    registry = {"AUDCAD.discovered.asia#x": {"status": "LIVE", "identity": {
        "family": "discovered", "symbol": "AUDCAD", "selector": "asia",
        "params": dict(PARAMS), "code_hash": "c0de", "behaviour_hash": "beh0"}}}
    w = {"survivors": survivors, "registry": registry,
         "docket_index": {"AUDCAD.discovered.p=7c996ac8456c8919": dict(PARAMS)},
         "docket_by_sym_family": {}, "code_of": lambda fam: ("c0de", "beh0")}
    w.update(over)
    return w


def _row(**over: Any) -> dict[str, Any]:
    r = {"name": "audcad_discovered_asia_p_7c99", "symbol": "AUDCAD", "family": "discovered",
         "selector": "asia", "status": "LIVE", "exec": "family_market",
         "certificate": {"source": "UNIVERSAL_SURVIVORS", "cell": CELL}}
    r.update(over)
    return r


def test_all_five_fields_agree_is_match() -> None:
    out = rli.judge_row(_row(), **_world())
    assert out["verdict"] == rli.MATCH, out
    assert out["params_basis"] == "docket_digest"


def test_params_drift_is_a_named_mismatch() -> None:
    out = rli.judge_row(_row(params={**PARAMS, "horizon": 3}), **_world())
    assert out["verdict"] == rli.MISMATCH
    assert out["fields"] == ["params"]
    assert out["diff"]["params"]["traded"]["horizon"] == 3
    assert out["why"].startswith("IDENTITY_MISMATCH")


def test_selector_drift_is_a_mismatch() -> None:
    out = rli.judge_row(_row(selector="london"), **_world())
    assert out["verdict"] == rli.MISMATCH and "selector" in out["fields"]


def test_code_behaviour_change_is_a_mismatch_but_prose_is_not() -> None:
    moved = rli.judge_row(_row(), **_world(code_of=lambda fam: ("new1", "beh1")))
    assert moved["verdict"] == rli.MISMATCH and moved["fields"] == ["code"]
    prose = rli.judge_row(_row(), **_world(code_of=lambda fam: ("new1", "beh0")))
    assert prose["verdict"] == rli.MATCH and prose["code"]["prose_only"] is True


def test_unjoinable_rows_are_unmeasured_with_a_reason() -> None:
    gold = rli.judge_row({"name": "gold_asia_v2", "symbol": "XAUUSD", "status": "LIVE"},
                         **_world())
    assert gold["verdict"] == rli.UNMEASURED and "family" in gold["why"]
    lane = rli.judge_row(_row(certificate="forward_clock"), **_world())
    assert lane["verdict"] == rli.UNMEASURED and "lane" in lane["why"]
    lost = rli.judge_row(_row(), **_world(docket_index={}))
    assert lost["verdict"] == rli.UNMEASURED and "docket" in lost["why"]
    nocode = rli.judge_row(_row(), **_world(code_of=lambda fam: (None, None)))
    assert nocode["verdict"] == rli.UNMEASURED and "resolves" in nocode["why"]


def test_qquant_side_word_and_explicit_params() -> None:
    p, basis = rli.recover_params(
        {"certificate": {"cell": "qquant.hunt16.json.AUDNZD dav SHORT afternoon"}}, {})
    assert p == {"side": -1} and basis == "qquant_side_word"
    p2, basis2 = rli.recover_params({"params": {"x": 1}, "certificate": {"cell": CELL}}, {})
    assert p2 == {"x": 1} and basis2 == "row"


def test_judge_rolls_up_defects() -> None:
    res = rli.judge([_row(), _row(name="bad", params={"x": 1})], **_world())
    assert res["counts"] == {"MATCH": 1, "MISMATCH": 1, "UNMEASURED": 0}
    assert res["mismatched"] == ["bad"]
    assert rli.mismatch_reasons(res) == {"bad": res["defects"][0]["why"]}


# ---------------------------------------------------------------------------- the door
def _door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, doc: dict[str, Any] | None) -> None:
    path = tmp_path / "RESEARCH_LIVE_IDENTITY.json"
    if doc is not None:
        path.write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(pa, "IDENTITY", path)
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    monkeypatch.setattr(pa, "block", lambda name: None)


def test_door_lists_a_mismatched_live_row(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    res = rli.judge([_row(), _row(name="bad", params={"x": 1})], **_world())
    _door(tmp_path, monkeypatch, {"generated_utc": datetime.now(UTC).isoformat(), **res})
    out = pa.review_live(["audcad_discovered_asia_p_7c99", "bad"])
    assert set(out) == {"bad"} and out["bad"].startswith("IDENTITY_MISMATCH")


def test_door_lists_nothing_on_absent_or_stale(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    _door(tmp_path, monkeypatch, None)
    assert pa.review_live(["bad"]) == {}
    res = rli.judge([_row(name="bad", params={"x": 1})], **_world())
    old = (datetime.now(UTC) - timedelta(hours=pa.MAX_AGE_H + 1)).isoformat()
    _door(tmp_path, monkeypatch, {"generated_utc": old, **res})
    assert pa.review_live(["bad"]) == {}


def test_door_fails_closed_on_a_damaged_report(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    _door(tmp_path, monkeypatch, None)
    (tmp_path / "RESEARCH_LIVE_IDENTITY.json").write_text("{torn", "utf-8")
    out = pa.review_live(["a"])
    assert out["a"].startswith("DOOR_ERROR: the identity check raised")


# ---------------------------------------------------------------------------- the organ
def test_organ_writes_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import research_live_identity as organ
    w = _world()
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [_row(), _row(name="standby",
                                                            status="STANDBY")]}), "utf-8")
    surv = tmp_path / "UNIVERSAL_SURVIVORS.json"
    surv.write_text(json.dumps({"survivors": w["survivors"]}), "utf-8")
    reg = tmp_path / "sleeve_registry.json"
    reg.write_text(json.dumps({"sleeves": w["registry"]}), "utf-8")
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps([{"symbol": "AUDCAD", "family": "discovered",
                                   "params": dict(PARAMS)}]), "utf-8")
    monkeypatch.setattr(organ, "SLEEVES", sleeves)
    monkeypatch.setattr(organ, "SURVIVORS", (surv,))
    monkeypatch.setattr(organ, "REGISTRY", reg)
    monkeypatch.setattr(organ, "DOCKET", docket)
    monkeypatch.setattr(organ, "REPORT", tmp_path / "out.json")
    monkeypatch.setattr(organ, "ROOT", tmp_path)
    monkeypatch.setattr(organ, "code_of", lambda fam: ("c0de", "beh0"))
    doc = organ.run()
    assert doc["n_live"] == 1 and doc["counts"]["MATCH"] == 1, doc["rows"]
    assert json.loads((tmp_path / "out.json").read_text("utf-8"))["counts"]["MATCH"] == 1


def test_is_a_core_leg_before_tier_s() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert src.index('_costed("research_live_identity", research_live_identity)') < \
        src.index('_costed("tier_s", tier_s)')
    import hourly_cycle as hc
    assert "research_live_identity" in hc.CORE_LEGS
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["research_live_identity"] == "meta"
