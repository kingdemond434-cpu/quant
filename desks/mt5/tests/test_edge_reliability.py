"""P(works now) is a fused score with named factors; below MIN_N it is UNMEASURED, not 0.5."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import edge_reliability as er  # noqa: E402


def test_factors_move_the_right_way() -> None:
    assert er.evidence_factor(5, 3.0)[0] == 0.5, "below MIN_N the ledger says nothing"
    assert er.evidence_factor(40, 2.0)[0] > 0.9 > 0.5 > er.evidence_factor(40, -2.0)[0]
    assert er.e_factor(None) == (1.0, "absent") and er.e_factor(0.3)[0] == 1.0
    assert er.e_factor(100.0)[0] == 0.5 and er.e_factor(1000.0)[0] < 0.1
    assert er.half_life_factor(None)[0] == 1.0 and er.half_life_factor(7.0)[0] == 0.25
    assert er.half_life_factor(400.0)[0] == 1.0


def test_sleeve_score_fuses_and_names_what_is_absent() -> None:
    row = {"status": "FORWARD", "n": 40, "forward_t": 2.0, "exp_r": 0.3, "e_value": 100.0,
           "sleeve_id": "s1", "certificate": "external.x"}
    s = er.sleeve_score(row, {"verdict": "FADE", "decay_model": {"half_life_days": 7.0}})
    assert s["status"] == "MEASURED" and s["absent"] == []
    f = s["factors"]
    assert f["decay"] == 0.5 and f["e_process"] == 0.5 and f["half_life"] == 0.25
    assert s["p_works_now"] == round(f["evidence"] * 0.5 * 0.5 * 0.25, 4)
    s2 = er.sleeve_score({"status": "FORWARD", "n": 40, "t": 1.0}, None)
    assert s2["absent"] == ["decay", "e_process", "half_life"] and s2["factors"]["decay"] == 1.0
    s3 = er.sleeve_score({"status": "FORWARD", "n": 3, "t": 5.0}, None)
    assert s3["status"] == "UNMEASURED" and s3["p_works_now"] is None


def test_build_reads_every_lane_and_ranks_the_measured(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(json.dumps({
        "a": {"status": "FORWARD", "n": 40, "forward_t": 2.5},
        "meta": "not a row"}), "utf-8")
    (shadow / "scalp_shadow_state.json").write_text(json.dumps({"sleeves": {
        "b": {"status": "FORWARD", "n": 40, "t": -1.0},
        "c": {"status": "FORWARD", "n": 2}}}), "utf-8")
    decay = tmp_path / "decay.json"
    decay.write_text(json.dumps({"verdicts": {"a": {"verdict": "HEALTHY"},
                                              "b": {"verdict": "RETIRE"}}}), "utf-8")
    doc = er.build(shadow=shadow, decay_path=decay)
    assert doc["n_sleeves"] == 3 and doc["n_measured"] == 2 and doc["status"] == "MEASURED"
    assert [r["sleeve"] for r in doc["ranked"]] == ["a", "b"]
    assert doc["sleeves"]["c"]["status"] == "UNMEASURED"
    empty = er.build(shadow=tmp_path / "none", decay_path=tmp_path / "none.json")
    assert empty["status"] == "NO_SLEEVES"


def test_main_writes_the_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(er, "SHADOW", tmp_path / "shadow")
    monkeypatch.setattr(er, "DECAY", tmp_path / "d.json")
    monkeypatch.setattr(er, "OUT", tmp_path / "out.json")
    assert er.main([]) == 0
    doc = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert doc["status"] == "NO_SLEEVES" and "consumer: none yet" in doc["basis"]
