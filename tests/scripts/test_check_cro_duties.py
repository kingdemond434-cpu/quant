"""check_cro_duties: every STEP 4B duty is measured from the artifacts its own row names."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_cro_duties as ccd  # noqa: E402

TABLE = "\n".join((
    "| D41 | **Nothing is a museum** | orphan (`reports/dead_architecture.json`) | 0 | Wire. |",
    "| D44 | **Self-evolution** | gains (`reports/TIER1_BREADTH_REVIEW.json`) | >= 1 | Land. |",
    "| D5 | **Procedure** | judged from the pass record | x | y |",
    "| D45 | **No artifact** | judged from git | x | y |",
))
SPEC = {"default_max_age_h": 26, "duties": {
    "D41": {"metrics": ["unreached"],
            "targets": [{"metric": "unreached", "op": "len==", "value": 0}]},
    "D44": {"metrics": ["machinery_improvements"]}}}


def _write(root: Path, rel: str, doc: object, age_h: float = 0.0,
           stamped: bool = True) -> Path:
    """The artifact carries its own `at`, as the desk's reports do; mtime is set to NOW so a
    test passing on mtime would be caught (adoption resets mtime on the box)."""
    p = root / "desks" / "mt5" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if stamped and isinstance(doc, dict):
        doc = {"at": (datetime.now(UTC) - timedelta(hours=age_h)).isoformat(), **doc}
    p.write_text(json.dumps(doc), "utf-8")
    t = time.time()
    os.utime(p, (t, t))
    return p


def test_every_row_and_its_artifacts_are_read_from_the_table() -> None:
    rows = ccd.duty_rows(TABLE)
    assert rows["D41"]["artifacts"] == ["reports/dead_architecture.json"]
    assert rows["D44"]["artifacts"] == ["reports/TIER1_BREADTH_REVIEW.json"]
    assert rows["D45"]["artifacts"] == []


def test_the_real_table_names_an_artifact_for_every_new_duty() -> None:
    rows = ccd.duty_rows(ccd.CYCLE.read_text("utf-8"))
    for d in ("D37", "D38", "D39", "D40", "D41", "D42", "D43", "D44"):
        assert rows[d]["artifacts"], d
    spec = json.loads(ccd.METRICS.read_text("utf-8"))
    assert set(spec["duties"]) <= set(rows)


def test_an_absent_artifact_is_unmeasured_and_missed(tmp_path: Path) -> None:
    doc = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)
    assert doc["duties"]["D41"]["status"] == "UNMEASURED"
    assert doc["duties"]["D41"]["counts_as"] == "MISSED"
    assert doc["duties"]["D5"]["status"] == "NO_ARTIFACT_NAMED"
    assert doc["duties"]["D45"]["status"] == "UNMEASURED"
    assert "D41" in doc["missed"] and "D45" in doc["missed"] and "D5" not in doc["missed"]


def test_a_stale_artifact_is_never_measured(tmp_path: Path) -> None:
    _write(tmp_path, "reports/dead_architecture.json", {"unreached": []}, age_h=40)
    d = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)["duties"]["D41"]
    assert d["status"] == "UNMEASURED"
    assert d["artifacts"]["reports/dead_architecture.json"]["status"] == "STALE"


def test_a_fresh_artifact_scores_its_target(tmp_path: Path) -> None:
    _write(tmp_path, "reports/dead_architecture.json", {"organs": {"unreached": ["a"]}})
    d = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)["duties"]["D41"]
    assert d["status"] == "NOT_MET" and d["counts_as"] == "MISSED"
    _write(tmp_path, "reports/dead_architecture.json", {"organs": {"unreached": []}})
    d = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)["duties"]["D41"]
    assert d["status"] == "MET" and d["counts_as"] is None


def test_an_unpublished_counter_is_unmeasured(tmp_path: Path) -> None:
    _write(tmp_path, "reports/TIER1_BREADTH_REVIEW.json", {"latest": {}})
    d = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)["duties"]["D44"]
    assert d["status"] == "UNMEASURED"
    assert d["metrics"]["machinery_improvements"]["status"] == "UNMEASURED"


def test_review_downgrades_only_an_unbacked_claim_of_this_pass(tmp_path: Path) -> None:
    start = datetime.now(UTC) - timedelta(minutes=5)
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"latest": {"at": datetime.now(UTC).isoformat(), "duties": {
        "D41": {"status": "MET"}, "D5": {"status": "MET"}, "D44": {"status": "BLOCKED"}}}}))
    measured = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)
    res = ccd.apply_to_review(review, measured, start.isoformat())
    assert res["applied"] and res["changed"] == ["D41", "D45"]
    duties = json.loads(review.read_text())["latest"]["duties"]
    assert duties["D41"]["status"] == "MISSED" and duties["D41"]["status_claimed"] == "MET"
    assert duties["D5"]["status"] == "MET"
    assert duties["D44"]["status"] == "BLOCKED" and duties["D44"]["counts_as"] == "MISSED"


def test_an_earlier_passes_review_is_never_rewritten(tmp_path: Path) -> None:
    review = tmp_path / "review.json"
    before = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    review.write_text(json.dumps({"latest": {"at": before, "duties": {"D41": {"status": "MET"}}}}))
    measured = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)
    res = ccd.apply_to_review(review, measured, datetime.now(UTC).isoformat())
    assert not res["applied"]
    assert json.loads(review.read_text())["latest"]["duties"]["D41"]["status"] == "MET"


def test_an_artifact_backed_duty_with_no_artifact_named_cannot_be_met(tmp_path: Path) -> None:
    """From D15 on a duty is backed by an artifact; a row naming only counters is UNMEASURED,
    so a MET the pass claims for it is rewritten MISSED. Procedure duties are left alone."""
    measured = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)
    assert measured["duties"]["D45"]["status"] == "UNMEASURED"
    assert measured["duties"]["D5"]["status"] == "NO_ARTIFACT_NAMED"
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"latest": {"at": datetime.now(UTC).isoformat(), "duties": {
        "D45": {"status": "MET"}, "D5": {"status": "MET"}}}}))
    ccd.apply_to_review(review, measured, (datetime.now(UTC) - timedelta(minutes=1)).isoformat())
    duties = json.loads(review.read_text())["latest"]["duties"]
    assert duties["D45"]["status"] == "MISSED" and duties["D45"]["verdict"] == "UNMEASURED"
    assert duties["D5"]["status"] == "MET"


def test_a_measured_target_that_failed_cannot_be_claimed_met(tmp_path: Path) -> None:
    _write(tmp_path, "reports/dead_architecture.json",
           {"generated_at": datetime.now(UTC).isoformat(), "unreached": ["organ_a"]})
    measured = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)
    assert measured["duties"]["D41"]["status"] == "NOT_MET"
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"latest": {"at": datetime.now(UTC).isoformat(), "duties": {
        "D41": {"status": "MET"}}}}))
    res = ccd.apply_to_review(review, measured,
                              (datetime.now(UTC) - timedelta(minutes=1)).isoformat())
    assert "D41" in res["changed"]
    d41 = json.loads(review.read_text())["latest"]["duties"]["D41"]
    assert d41["status"] == "MISSED" and d41["status_claimed"] == "MET"
    assert d41["verdict"] == "NOT_MET" and d41["reason"] == "measured_target_not_met"


def test_an_unstamped_artifact_is_never_fresh_by_mtime(tmp_path: Path) -> None:
    _write(tmp_path, "reports/dead_architecture.json", {"unreached": []}, stamped=False)
    d = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)["duties"]["D41"]
    assert d["artifacts"]["reports/dead_architecture.json"]["status"] == "UNSTAMPED"
    assert d["status"] == "UNMEASURED" and d["counts_as"] == "MISSED"


def test_d17_to_d21_name_their_publishing_artifacts() -> None:
    rows = ccd.duty_rows(ccd.CYCLE.read_text("utf-8"))
    assert rows["D17"]["artifacts"] == ["reports/BOX_STATE_FRESHNESS.json"]
    duties = json.loads(ccd.METRICS.read_text("utf-8"))["duties"]
    assert duties["D18"]["artifacts"] == ["reports/DATASET_EXPLOITATION.json"]
    assert duties["D19"]["artifacts"] == ["reports/PAID_SOURCES_SUBSTITUTED.json"]
    assert duties["D20"]["artifacts"] == ["reports/CULTURE_ORTHOGONALITY_VERDICTS.json"]
    assert duties["D21"]["artifacts"] == ["reports/RESEARCH_LIVE_IDENTITY.json"]


def test_artifacts_named_in_the_metrics_file_are_read(tmp_path: Path) -> None:
    rows = {"D19": {"name": "Paid-substitute coverage", "artifacts": []}}
    spec = {"artifact_backed_from": 15, "duties": {"D19": {
        "artifacts": ["reports/PAID_SOURCES_SUBSTITUTED.json"],
        "metrics": ["paid_sources_substituted"]}}}
    d = ccd.measure(rows, spec, root=tmp_path)["duties"]["D19"]
    assert d["status"] == "UNMEASURED" and "absent" in json.dumps(d["artifacts"])
    _write(tmp_path, "reports/PAID_SOURCES_SUBSTITUTED.json", {"paid_sources_substituted": 3})
    d = ccd.measure(rows, spec, root=tmp_path)["duties"]["D19"]
    assert d["status"] == "MEASURED"
    assert d["metrics"]["paid_sources_substituted"]["value"] == 3
