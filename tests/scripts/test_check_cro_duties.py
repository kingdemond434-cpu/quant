"""check_cro_duties: every STEP 4B duty is measured from the artifacts its own row names."""
from __future__ import annotations

import json
import os
import subprocess
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
    assert duties["D18"]["artifacts"] == ["reports/DATASET_USE.json",
                                          "data/digests/dataset_use_digest.json"]
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


def test_d34_backpressure_goes_to_the_judge_only() -> None:
    """D34 runs twice a day: its action is a standing order, so it must never cut research.
    Law: backpressure goes to the judge only; onboarding, mining and research generation are
    never throttled."""
    row = next(ln for ln in (ROOT / "docs" / "cro" / "CRO_CYCLE.md").read_text(
        encoding="utf-8").splitlines() if ln.startswith("| D34 |"))
    action = row.rstrip(" |").rsplit("|", 1)[-1].strip()
    assert action == ("Raise judge capacity (backpressure goes to the judge only). "
                      "Never throttle onboarding, mining or research generation.")
    assert "throttle onboarding and" not in row.lower()


def test_pass_questions_q1_to_q7_are_in_the_cycle_and_not_duty_rows() -> None:
    """ARCH-30: every pass answers Q1-Q7 with box evidence into `pass_questions`; an
    unmeasured answer is MISSED. The Q rows must never be read as duty rows."""
    text = (ROOT / "docs" / "cro" / "CRO_CYCLE.md").read_text(encoding="utf-8")
    qs = [ln.split("|")[1].strip() for ln in text.splitlines() if ln.startswith("| Q")]
    assert qs[1:] == [f"Q{i}" for i in range(1, 8)]
    assert "`pass_questions`" in text and "`pass_questions_missed`" in text
    assert "UNMEASURED or cites nothing counts as MISSED" in text
    assert not any(k.startswith("Q") for k in ccd.duty_rows(text))
    q4 = next(ln for ln in text.splitlines() if ln.startswith("| Q4 |"))
    for baseline in ("equal-risk", "inverse-vol", "best-single-sleeve",
                     "after lot rounding and costs"):
        assert baseline in q4


def test_pass_questions_are_scored_from_the_review(tmp_path: Path) -> None:
    """ARCH-30 is not doc-only: an absent, UNMEASURED or uncited answer is rewritten MISSED
    and counted in pass_questions_missed; a cited answer stands."""
    good = {"answer": "re-judge the COT backlog",
            "evidence": ["reports/X.json@2026-10-07T01:00:00Z"]}
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "reports" / "X.json").write_text("{}")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"latest": {"at": datetime.now(UTC).isoformat(), "duties": {},
        "pass_questions": {"Q1": good, "Q2": dict(good), "Q3": {**good, "evidence": []},
                           "Q4": {"answer": "UNMEASURED: no baseline artifact",
                                  "evidence": ["x"], "status": "ANSWERED"},
                           "Q5": dict(good), "Q6": dict(good)}}}))
    measured = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)
    res = ccd.apply_to_review(review, measured, (datetime.now(UTC) - timedelta(minutes=1))
                              .isoformat(), root=tmp_path)
    assert res["pass_questions_missed"] == ["Q3", "Q4", "Q7"]
    latest = json.loads(review.read_text())["latest"]
    assert latest["pass_questions_missed"] == ["Q3", "Q4", "Q7"]
    pq = latest["pass_questions"]
    assert pq["Q1"]["status"] == "ANSWERED"
    assert pq["Q3"]["reason"] == "no_evidence"
    assert pq["Q4"]["status"] == "MISSED" and pq["Q4"]["status_claimed"] == "ANSWERED"
    assert pq["Q7"] == {"status": "MISSED", "reason": "absent"}


def test_judging_sweep_items_a_to_g_are_scored_from_the_review(tmp_path: Path) -> None:
    """The JUDGING BOTTLENECK SWEEP is enforced like the pass questions: every item (a)-(g)
    needs a finding and evidence, or it is MISSED and listed in judging_sweep_missed."""
    item = {"finding": "0 first rulings/h",
            "evidence": ["reports/JUDGING_BURNDOWN.json@2026-10-07T01:00:00Z"]}
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "reports" / "JUDGING_BURNDOWN.json").write_text("{}")
    sweep = {k: dict(item) for k in "abcdef"}
    sweep["c"] = {"finding": "UNMEASURED", "evidence": ["x"]}
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"latest": {"at": datetime.now(UTC).isoformat(), "duties": {},
                                             "judging_sweep": sweep}}))
    measured = ccd.measure(ccd.duty_rows(TABLE), SPEC, root=tmp_path)
    res = ccd.apply_to_review(review, measured, (datetime.now(UTC) - timedelta(minutes=1))
                              .isoformat(), root=tmp_path)
    assert res["judging_sweep_missed"] == ["c", "g"]
    latest = json.loads(review.read_text())["latest"]
    assert latest["judging_sweep"]["a"]["status"] == "MEASURED"
    assert latest["judging_sweep"]["g"] == {"status": "MISSED", "reason": "absent"}


def test_a_burndown_older_than_two_hours_is_stale_for_d3(tmp_path: Path) -> None:
    """D3 reads the burndown at a 2h window even though the duty default is 26h."""
    rep = tmp_path / "desks" / "mt5" / "reports"
    rep.mkdir(parents=True)
    at = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    (rep / "JUDGING_BURNDOWN.json").write_text(json.dumps(
        {"generated_at": at, "first_rulings_per_hour": 0.0, "created_per_hour": 3750.0}))
    rows = {"D3": {"name": "Judging", "artifacts": ["reports/JUDGING_BURNDOWN.json"]}}
    spec = {"duties": {"D3": {"artifact_max_age_h": {"reports/JUDGING_BURNDOWN.json": 2},
                              "metrics": ["first_rulings_per_hour"]}}}
    d3 = ccd.measure(rows, spec, root=tmp_path)["duties"]["D3"]
    assert d3["artifacts"]["reports/JUDGING_BURNDOWN.json"]["status"] == "STALE"
    assert d3["counts_as"] == "MISSED"


def test_the_cycle_carries_the_judging_sweep_and_the_d3_d4_d38_extensions() -> None:
    text = (ROOT / "docs" / "cro" / "CRO_CYCLE.md").read_text(encoding="utf-8")
    items = [ln.split("|")[1].strip() for ln in text.splitlines()
             if len(ln) > 4 and ln[:2] == "| " and ln[2] in "abcdefg" and ln[3:5] == " |"]
    assert items == list("abcdefg")
    rows = ccd.duty_rows(text)
    assert "reports/JUDGING_BURNDOWN.json" in rows["D3"]["artifacts"]
    assert "reports/JUDGE_COVERAGE.json" in rows["D4"]["artifacts"]
    spec = json.loads((ROOT / "docs" / "cro" / "cro_duty_metrics.json").read_text("utf-8"))
    assert spec["duties"]["D3"]["artifact_max_age_h"]["reports/JUDGING_BURNDOWN.json"] == 2
    assert {"warm_rate", "cold_build_seconds", "build_failures_by_cause"} <= set(
        spec["duties"]["D38"]["metrics"])
    assert "1,389,434" in text and "`judging_sweep`" in text


def test_a_citation_must_resolve_to_a_timestamped_artifact_a_ledger_row_or_a_commit(
        tmp_path: Path) -> None:
    """Any non-empty string is not evidence: only a timestamped path to a file on this host,
    a cro_cycle_ledger row or work-item id, or a commit sha this checkout knows."""
    data = tmp_path / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    (data / "cro_cycle_ledger.jsonl").write_text(json.dumps(
        {"lane": "noon", "date": "2026-10-07", "work_items": [{"id": "noon-1007-01"}]}) + "\n")
    (tmp_path / "desks" / "mt5" / "reports").mkdir()
    (tmp_path / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json").write_text("{}")
    ok = ccd.citation_resolves
    assert ok("reports/JUDGE_COVERAGE.json@2026-10-01T11:58:00Z", tmp_path)
    assert ok("desks/mt5/reports/JUDGE_COVERAGE.json@2026-10-01T11:58:00+00:00", tmp_path)
    assert not ok("reports/JUDGE_COVERAGE.json", tmp_path)            # no timestamp
    assert not ok("reports/ABSENT.json@2026-10-01T11:58:00Z", tmp_path)  # not on this host
    assert not ok("../etc/passwd@2026-10-01T11:58:00Z", tmp_path)
    assert not ok("/etc/passwd@2026-10-01T11:58:00Z", tmp_path)           # absolute escapes
    assert not ok(f"{tmp_path}/desks/mt5/reports/JUDGE_COVERAGE.json@2026-10-01T11:58:00Z",
                  tmp_path)
    assert not ok("reports@2026-10-01T11:58:00Z", tmp_path)                 # a directory
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert not ok(f"reports/JUDGE_COVERAGE.json@{future}", tmp_path)       # not yet measured
    (tmp_path / "desks" / "mt5" / "reports" / "LINK.json").symlink_to("/etc/hostname")
    assert not ok("reports/LINK.json@2026-10-01T11:58:00Z", tmp_path)       # symlink escape
    assert ok("ledger:noon-2026-10-07", tmp_path) and ok("ledger:noon-1007-01", tmp_path)
    assert not ok("ledger:noon-2026-10-08", tmp_path)
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()
    assert ok(f"sha:{head[:9]}", ROOT) and ok(head, ROOT)
    assert not ok("sha:0000000deadbeef", ROOT)
    assert not ok("the judge looked slow", tmp_path)
    assert ccd._entry_miss({"answer": "x", "evidence": ["trust me"]}, "answer",
                           tmp_path) == "evidence_unresolvable"
