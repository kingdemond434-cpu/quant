"""ARCH-30: the evidence each pass question cites is measured hourly, absent reads UNMEASURED,
every part no organ measures is named with its owner, and Q2 is computed per producer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_cro_duties as duties  # noqa: E402
import check_pass_question_evidence as pqe  # noqa: E402

NOW = "2026-11-04T12:00:00+00:00"
FRESH = "2026-11-04T11:00:00+00:00"
OLD = "2026-11-01T11:00:00+00:00"


def _write(root: Path, rel: str, doc: object) -> None:
    p = root / "desks" / "mt5" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")


def _breadth() -> dict:
    return {"generated_utc": FRESH,
            "effective": {"n_nominal": 10, "effective_breadth": 2.0,
                          "readings": [{"name": "exposure_full_sample",
                                        "detail": {"mean_pairwise_corr": 0.2}}]},
            "clusters": {"occupied_either": ["session_liquidity"], "empty_in_both": ["trend"]}}


def _survivor(family: str, hunt: str, at: str) -> dict:
    return {"hunt": hunt, "gated_at": at, "shadow_spec": {"family": family, "hunt": hunt}}


def _run(root: Path) -> tuple[int, dict]:
    out = root / "out.json"
    rc = pqe.main(["--root", str(root), "--out", str(out), "--now", NOW])
    return rc, json.loads(out.read_text("utf-8"))


def test_an_empty_host_is_red_and_every_question_unmeasured(tmp_path: Path) -> None:
    rc, doc = _run(tmp_path)
    assert rc == pqe.EXIT_RED and doc["status"] == "RED"
    assert doc["unmeasured_questions"] == [f"Q{i}" for i in range(1, 8)]
    assert all(v["citations"] == [] for v in doc["questions"].values())
    assert doc["questions"]["Q2"]["producer_gain"]["status"] == "UNMEASURED"
    assert doc["questions"]["Q4"]["contest"]["status"] == "UNMEASURED"


def test_every_part_now_has_an_organ_and_an_absent_one_is_absent_not_clean(
        tmp_path: Path) -> None:
    _, doc = _run(tmp_path)
    assert doc["no_organ"] == []
    subs = {r["name"]: r for q in ("Q4", "Q5") for r in doc["questions"][q]["sub_measures"]}
    assert subs["best_single_sleeve_baseline"]["artifact"].endswith("pf_allocation.json")
    assert subs["executable_book_after_lots_and_costs"]["artifact"].endswith(
        "EXECUTABLE_BOOK.json")
    assert subs["defect_loss_in_elog"]["artifact"].endswith("DEFECT_LOSS.json")
    for name in ("best_single_sleeve_baseline", "executable_book_after_lots_and_costs",
                 "defect_loss_in_elog"):
        assert subs[name]["state"] == "ABSENT"


def test_q4_reads_the_best_single_sleeve_rival_and_the_executable_book(tmp_path: Path) -> None:
    _write(tmp_path, "reports/ALLOCATOR_PROOF.json", {
        "at": FRESH, "passed": True, "scores": {"dynamic": {"robust_score": 0.01}}})
    _write(tmp_path, "reports/pf_allocation.json", {"at": FRESH, "best_single_sleeve": {
        "name": "gold_asia", "heat": 0.2, "robust_score": 0.03, "delta_vs_funded": 0.02,
        "beats_funded": True}})
    _write(tmp_path, "reports/EXECUTABLE_BOOK.json", {"at": FRESH, "n_sending_keys": 1, "keys": {
        "gold_asia": {"allocator_fraction": 0.006, "sending": ["gold_asia"], "rows": []},
        "scalp_eurusd": {"allocator_fraction": 0.004, "sending": [],
                         "rows": [{"name": "scalp_eurusd", "why_zero": "decay_zero"}]}}})
    _, doc = _run(tmp_path)
    q4 = doc["questions"]["Q4"]
    assert q4["status"] == "MEASURED"
    assert q4["contest"]["baselines_beating_dynamic"] == []
    assert q4["best_single_sleeve"]["beats_funded"] is True
    assert q4["best_single_sleeve"]["route"] == pqe.GROWTH_ALLOCATOR
    assert len(q4["citations"]) == 3
    assert q4["executable_book"]["funded_but_not_sending"] == {"scalp_eurusd": ["decay_zero"]}
    assert q4["executable_book"]["route"] == pqe.GROWTH_ALLOCATOR


def test_a_stale_executable_book_left_by_a_failed_replace_is_unmeasured(tmp_path: Path) -> None:
    old = "2026-11-04T09:00:00+00:00"  # 3h before NOW: inside 26h, outside the 2h limit
    _write(tmp_path, "reports/EXECUTABLE_BOOK.json", {"at": old, "n_sending_keys": 0, "keys": {}})
    _, doc = _run(tmp_path)
    q4 = doc["questions"]["Q4"]
    sub = {r["name"]: r for r in q4["sub_measures"]}["executable_book_after_lots_and_costs"]
    assert sub["state"] == "STALE"
    assert q4["executable_book"]["status"] == "UNMEASURED"


def test_a_fresh_artifact_yields_a_citation_the_duty_checker_resolves(tmp_path: Path) -> None:
    _write(tmp_path, "reports/dead_architecture.json", {"at": FRESH, "organs": [{"x": 1}]})
    _write(tmp_path, "reports/SILENT_ORGANS.json", {"at": FRESH, "silent": []})
    _, doc = _run(tmp_path)
    q6 = doc["questions"]["Q6"]
    assert q6["status"] == "MEASURED"
    assert len(q6["citations"]) == 2
    for cite in q6["citations"]:
        assert duties.citation_resolves(cite, tmp_path, ledger=set()), cite


def test_a_stale_artifact_is_not_cited(tmp_path: Path) -> None:
    _write(tmp_path, "reports/dead_architecture.json", {"at": OLD, "organs": []})
    _, doc = _run(tmp_path)
    q6 = doc["questions"]["Q6"]
    assert q6["status"] == "UNMEASURED" and q6["citations"] == []
    assert q6["sub_measures"][0]["state"] == "STALE"


def test_a_fresh_artifact_missing_its_key_is_not_evidence(tmp_path: Path) -> None:
    _write(tmp_path, "reports/dead_architecture.json", {"at": FRESH, "other": 1})
    _, doc = _run(tmp_path)
    row = doc["questions"]["Q6"]["sub_measures"][0]
    assert row["state"] == "KEY_ABSENT" and doc["questions"]["Q6"]["citations"] == []


def test_q2_credits_breadth_per_producer_in_gating_order(tmp_path: Path) -> None:
    survivors = {
        # first into the empty `trend` cluster: credited at the cross rho, opens the cluster
        "a": _survivor("asia_momentum", "hunt_new.json", "2026-11-04T09:00:00+00:00"),
        # second into trend, from another producer: the cluster is now occupied, book rho
        "b": _survivor("multi_speed_trend", "hunt_dup.json", "2026-11-04T10:00:00+00:00"),
        # a payer the desk cannot name is counted, never credited
        "c": _survivor("no_such_family", "hunt_dup.json", "2026-11-04T10:30:00+00:00"),
        # outside the window: not this pass's information
        "d": _survivor("carry", "hunt_old.json", "2026-10-01T10:00:00+00:00"),
    }
    _write(tmp_path, "reports/UNIVERSAL_SURVIVORS.json", {"swept_at": FRESH,
                                                          "survivors": survivors})
    _write(tmp_path, "reports/EFFECTIVE_BREADTH.json", _breadth())
    _write(tmp_path, "reports/PRODUCER_YIELD.json",
           {"generated_utc": FRESH, "producers": [{"producer": "silent_miner"}]})
    _, doc = _run(tmp_path)
    q2 = doc["questions"]["Q2"]
    assert q2["status"] == "MEASURED"
    g = q2["producer_gain"]
    assert g["status"] == "MEASURED" and g["certificates_in_window"] == 3
    by = {p["producer"]: p for p in g["producers"]}
    assert set(by) == {"hunt:hunt_new.json", "hunt:hunt_dup.json"}
    assert by["hunt:hunt_new.json"]["new_clusters"] == ["trend"]
    assert by["hunt:hunt_dup.json"]["new_clusters"] == []
    assert by["hunt:hunt_dup.json"]["unclassified"] == 1
    assert by["hunt:hunt_new.json"]["delta_k_eff"] > by["hunt:hunt_dup.json"]["delta_k_eff"]
    assert g["clusters_before"] == 1 and g["clusters_after"] == 2
    assert g["roster_producers_with_no_certificate_sample"] == ["silent_miner"]
    assert len(q2["citations"]) == 3


def test_q4_names_the_baselines_that_beat_the_allocator(tmp_path: Path) -> None:
    _write(tmp_path, "reports/ALLOCATOR_PROOF.json", {
        "at": FRESH, "passed": False,
        "scores": {"dynamic": {"robust_score": 0.01}, "equal_weight": {"robust_score": 0.02},
                   "inverse_vol": {"robust_score": 0.005}}})
    rc, doc = _run(tmp_path)
    q4 = doc["questions"]["Q4"]
    assert q4["contest"]["baselines_beating_dynamic"] == ["equal_weight"]
    assert q4["contest"]["route"] == pqe.GROWTH_ALLOCATOR
    assert q4["best_single_sleeve"]["status"] == "UNMEASURED"
    # the contest is measured but the single-sleeve rival and the executable book are not
    assert q4["status"] == "PARTIAL" and rc == pqe.EXIT_RED


def test_the_leg_is_scheduled_registered_and_documented() -> None:
    cycle = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text("utf-8")
    assert ('_producer(\n        "pass_question_evidence", '
            '"scripts/check_pass_question_evidence.py")') in cycle
    assert '"pass_question_evidence": (2,)' in cycle            # exit 2 is a verdict
    assert '"pass_question_evidence": pqe' in cycle
    layers = (ROOT / "libs/research/layers.py").read_text("utf-8")
    assert '"pass_question_evidence": "meta"' in layers
    board = (ROOT / "desks/mt5/research/issue_board.py").read_text("utf-8")
    assert '"desks/mt5/reports/PASS_QUESTION_EVIDENCE.json", 3600' in board
    text = (ROOT / "docs/cro/CRO_CYCLE.md").read_text("utf-8")
    assert "PASS_QUESTION_EVIDENCE.json" in text and "`no_organ`" in text
