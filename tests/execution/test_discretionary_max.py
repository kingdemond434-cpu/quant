"""R0151 discretionary max -- the ceiling-pusher for the discretionary desk.

A HIT RATE is a legal target where a return figure is not: it cannot be reached by sizing, only by
selection, information and filtering. Targeting the process variable is what makes targeting the
outcome variable unnecessary.
"""
from __future__ import annotations

import json

from scripts.run_discretionary_max import REAIM_STEP, TARGET_HIT, build_report, levers


def _state(tmp_path, **files):
    (tmp_path / "data").mkdir(exist_ok=True)
    for name, blob in files.items():
        (tmp_path / f"data/{name}.json").write_text(json.dumps(blob))


def test_with_no_evidence_the_binding_lever_is_evidence(tmp_path):
    rep = build_report(tmp_path)
    assert rep["binding_lever"]["lever"] == "EVIDENCE"
    assert rep["measured_hit_rate"] is None
    assert "UNMEASURED" in rep["aim_note"]


def test_reaching_the_target_re_aims_rather_than_standing_down(tmp_path):
    # L1.25a: the hunt never tires. An organ that reports "target met" has stopped being a
    # ceiling-pusher and become a scoreboard.
    _state(tmp_path, paper_book_pnl={"n_resolved": 200, "win_rate": TARGET_HIT + 0.01})
    rep = build_report(tmp_path)
    assert rep["target_hit_rate"] > TARGET_HIT
    assert abs(rep["target_hit_rate"] - (TARGET_HIT + 0.01 + REAIM_STEP)) < 1e-9
    assert "never reports" in rep["aim_note"]


def test_below_target_it_states_the_gap(tmp_path):
    _state(tmp_path, paper_book_pnl={"n_resolved": 200, "win_rate": 0.33})
    rep = build_report(tmp_path)
    assert rep["target_hit_rate"] == TARGET_HIT
    assert "gap is" in rep["aim_note"]


def test_the_cross_family_lever_unblocks_when_the_second_family_produces(tmp_path):
    _state(tmp_path, paper_book_pnl={"n_resolved": 50, "win_rate": 0.33})
    blocked = {x["lever"]: x for x in levers(tmp_path)}["CROSS-FAMILY"]
    assert blocked["state"] == "BLOCKED" and "OpenRouter" in blocked["action"]
    _state(tmp_path, paper_book_pnl={"n_resolved": 50, "win_rate": 0.33},
           kimi_hunt={"ran": True})
    live = {x["lever"]: x for x in levers(tmp_path)}["CROSS-FAMILY"]
    assert live["state"] == "OPEN" and "wire cross-family" in live["action"]


def test_information_is_ranked_above_every_mechanical_lever(tmp_path):
    # The sleeve reads PUBLIC charts. No amount of filtering manufactures an informational edge,
    # so the ordering has to say so even though INFORMATION is the hardest lever to pull.
    lv = {x["lever"]: x["rank"] for x in levers(tmp_path)}
    assert lv["INFORMATION"] < lv["SELECTION"] < lv["ENSEMBLE"] < lv["EXECUTION"]


def test_an_uninformative_calibration_says_remove_the_sizer(tmp_path):
    _state(tmp_path, paper_book_pnl={"n_resolved": 50, "win_rate": 0.33},
           calibration_probe={"verdict": {"state": "UNINFORMATIVE", "n_resolved": 40}})
    cal = {x["lever"]: x for x in levers(tmp_path)}["CALIBRATION"]
    assert cal["state"] == "OPEN" and "strip the Kelly sizer" in cal["action"]


def test_it_never_returns_nothing_to_do(tmp_path):
    # An idle ceiling-pusher is the failure it exists to prevent (L1.28a).
    rep = build_report(tmp_path)
    assert rep["never_idle"] and "NO LEVERS" not in rep["never_idle"]
    assert rep["binding_lever"]["action"]
