"""The CEO block: the ignorance ledger on the board, and an absence that never reads as a zero.

Measured absent on 2026-09-23 (Tier-1 W18): the dashboard state builder read the account, the
pipeline and the wiring audit, and read NOTHING of the scorecard, the departments, the unseen
frontier, the wiring hunter or the ignorance ledger -- so the one view a principal opens said
nothing about whether the research machine was getting better.

Three properties:

  * SEVEN ARTIFACTS, EACH WITH A VERDICT. Present or absent, with the leg that writes it named,
    so a reader can see which clock is silent rather than guess.
  * THIRTEEN LIFETIME ROWS, each carrying its value, the artifact it came from, and UNMEASURED
    with the reason when that artifact is not there.
  * AN ABSENT ARTIFACT IS NEVER A ZERO. A board showing 0.0% frontier explored because a file
    was missing is indistinguishable from a desk that explored nothing, and only one of those is
    an emergency. A MEASURED zero, by contrast, stays a zero and stays MEASURED.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_zentech_state.py"
SPEC = importlib.util.spec_from_file_location("build_zentech_state_ceo", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

#: The thirteen the principal named. A row that quietly stopped being published would be a
#: metric the desk no longer owes an answer for, which is how a board goes blind one line
#: at a time.
LIFETIME_KEYS = (
    "frontier_explored_pct", "survivor_yield_per_source", "pit_clean_axes",
    "novel_mechanisms_per_week", "survivors_per_compute_hour", "fdr_and_replication_rate",
    "n_eff", "posterior_edge_distribution", "live_half_life_days",
    "alpha_captured_vs_theoretical", "realised_vs_predicted_log_growth",
    "meta_rd_productivity", "unseen_mechanism_mass",
)


def _desk(tmp_path: Path, **artifacts: Any) -> Path:
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports").mkdir(parents=True, exist_ok=True)
    for name, doc in artifacts.items():
        (desk / "reports" / name.replace("__", ".")).write_text(
            json.dumps(doc), encoding="utf-8")
    return desk


# ------------------------------------------------------------------ absence is never a zero
def test_an_empty_host_renders_every_row_unmeasured_with_a_reason_and_never_zero(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "DESK", _desk(tmp_path))
    block = module._ceo_block()
    assert block["status"] == "UNMEASURED"
    assert [r["key"] for r in block["lifetime"]] == list(LIFETIME_KEYS)
    assert block["n_measured"] == 0 and block["n_unmeasured"] == len(LIFETIME_KEYS)
    for row in block["lifetime"]:
        assert row["status"] == "UNMEASURED", row
        assert row["value"] is None, row          # NEVER 0.0 -- that is the whole point
        assert row["value"] != 0
        assert row["source"].startswith("desks/mt5/reports/")
        assert row["why"] and ("is not on this host" in row["why"]
                               or "UNMEASURED" in row["why"])
    assert block["artifacts_present"] == 0
    assert sorted(block["artifacts_absent"]) == sorted(k for k, _, _ in module.CEO_ARTIFACTS)


def test_every_ceo_artifact_carries_a_verdict_and_names_the_leg_that_writes_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "DESK", _desk(tmp_path))
    block = module._ceo_block()
    assert len(block["artifacts"]) == 7
    for key, name, leg in module.CEO_ARTIFACTS:
        row = block["artifacts"][key]
        assert row["status"] == "ABSENT"
        assert row["artifact"] == f"desks/mt5/reports/{name}"
        assert row["leg"] == leg
        assert name in row["why"] and leg in row["why"]
        assert row["digest"] is None


def test_a_measured_zero_stays_a_zero_and_stays_measured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The distinction the block exists for: nobody measured it, versus it measured zero."""
    monkeypatch.setattr(module, "DESK", _desk(
        tmp_path,
        scaling_laws__json={"by_day": [{"day": "d", "hours": 8.0, "certified": 0}],
                            "law": {"status": "UNMEASURED", "why": "too few days"}},
        PIT_CENSUS__json={"census": {"sidecars": 20, "stamped": 0}}))
    rows = {r["key"]: r for r in module._ceo_block()["lifetime"]}
    assert rows["survivors_per_compute_hour"]["status"] == "MEASURED"
    assert rows["survivors_per_compute_hour"]["value"] == 0.0
    assert "8.0 recorded compute hour" in rows["survivors_per_compute_hour"]["why"]
    assert rows["pit_clean_axes"]["status"] == "MEASURED"
    assert rows["pit_clean_axes"]["value"] == 0.0
    # and the artifacts that are still missing are still UNMEASURED, not zero
    assert rows["n_eff"]["value"] is None and rows["n_eff"]["status"] == "UNMEASURED"


# ------------------------------------------------------------------- present artifacts are read
def test_the_present_artifacts_are_read_into_values_and_digests(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "DESK", _desk(
        tmp_path,
        TIER1_SCORECARD__json={"n_rows": 14, "overall": {"at_or_above": 2, "below": 12,
                                                         "unmeasured": 0,
                                                         "weakest_measured": ["a", "b", "c",
                                                                              "d"]}},
        RESEARCH_DEPARTMENTS__json={"departments": {"data": {}, "macro": {}},
                                    "binding_resource": {"binding": "gauntlet"},
                                    "spend": {"applied": True, "why": "every input measured"}},
        UNSEEN_FRONTIER__json={"n_sightings": 90, "n_species": 12,
                               "most_open": [{"ground_id": "zhihu", "n_unseen": 7.0}],
                               "grounds": {"zhihu": {"n": 40, "coverage": 0.5,
                                                     "n_unseen": 7.0},
                                           "qihe": {"n": 60, "coverage": 0.9,
                                                    "n_unseen": 3.0}}},
        WIRING_CEO__json={"n_organs": 400, "n_unwired": 12, "n_probation": 3,
                          "floor": {"status": "HELD"}, "certificates_without_clocks": 5},
        RESIDUAL_QUEUE__json={"n_items": 30, "n_open": 22, "n_donated": 6, "n_explained": 2,
                              "by_level": {"macro": {"open": 4}}},
        SOURCE_REGISTRY__json={"n_sources": 639, "by_kind": {"web": 400},
                               "language_gaps": ["ja", "ko"],
                               "judged": {"pooled_pass_rate": 0.002, "n_cells_judged": 3000,
                                          "n_passed": 6, "why": "pooled"},
                               "top_by_roi": [{"source_id": "seat:cot"}]},
        POSTERIOR_ALPHA__json={"n_sleeves": 4, "n_credible": 1, "counts": {"x": 1},
                               "sleeves": [{"mu_mean": 0.1}, {"mu_mean": 0.3},
                                           {"mu_mean": -0.2}, {"mu_mean": 0.5}]},
        EFFECTIVE_BREADTH__json={"effective": {"effective_breadth": 2.057, "n_nominal": 160,
                                               "binding_reading": "realised_returns",
                                               "breadth_ratio": 0.0129}}))
    block = module._ceo_block()
    assert block["status"] == "MEASURED"
    assert block["artifacts_present"] == 7 and block["artifacts_absent"] == []
    assert block["artifacts"]["scorecard"]["digest"]["below"] == 12
    assert block["artifacts"]["scorecard"]["digest"]["weakest"] == ["a", "b", "c"]
    assert block["artifacts"]["departments"]["digest"]["n_departments"] == 2
    assert block["artifacts"]["departments"]["digest"]["spend_applied"] is True
    assert block["artifacts"]["wiring"]["digest"]["n_unwired"] == 12
    assert block["artifacts"]["ignorance_ledger"]["digest"]["n_open"] == 22
    assert block["artifacts"]["sources"]["digest"]["n_sources"] == 639
    assert block["artifacts"]["unseen_frontier"]["digest"]["most_open"]["ground_id"] == "zhihu"

    rows = {r["key"]: r for r in block["lifetime"]}
    # frontier explored is the sightings-weighted Good-Turing coverage: (0.5*40 + 0.9*60)/100
    assert rows["frontier_explored_pct"]["value"] == pytest.approx(74.0)
    assert rows["frontier_explored_pct"]["detail"]["grounds"] == 2
    assert rows["unseen_mechanism_mass"]["value"] == pytest.approx(10.0)
    assert rows["n_eff"]["value"] == pytest.approx(2.057)
    assert rows["survivor_yield_per_source"]["value"] == pytest.approx(0.002)
    assert rows["survivor_yield_per_source"]["detail"]["best_source"] == "seat:cot"
    assert rows["posterior_edge_distribution"]["value"] == pytest.approx(0.3)
    assert rows["posterior_edge_distribution"]["detail"]["n_credible"] == 1
    assert all(r["source"] for r in block["lifetime"])
    assert block["n_measured"] >= 5


def test_the_growth_row_reports_realised_against_predicted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "DESK", _desk(
        tmp_path,
        GROWTH_ATTRIBUTION_WEEKLY__json={
            "identity": {"dlogw_per_day": 0.05, "terms_summed_logw_per_day": 0.002,
                         "terms_in_identity": ["selection", "sizing"]},
            "measured": ["selection"], "unmeasured": ["entry"]}))
    row = {r["key"]: r for r in module._ceo_block()["lifetime"]}[
        "realised_vs_predicted_log_growth"]
    assert row["status"] == "MEASURED"
    assert row["value"] == pytest.approx(0.048)
    assert row["detail"]["realised"] == pytest.approx(0.05)
    assert row["detail"]["predicted"] == pytest.approx(0.002)


# --------------------------------------------------------------------------- it never crashes
def test_a_corrupt_or_bom_marked_artifact_never_crashes_the_board(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    desk = _desk(tmp_path)
    (desk / "reports" / "TIER1_SCORECARD.json").write_text("{not json", encoding="utf-8")
    # A BOM is what several desk organs write; utf-8 alone would call this file ABSENT.
    (desk / "reports" / "SOURCE_REGISTRY.json").write_text(
        json.dumps({"n_sources": 7, "judged": {"pooled_pass_rate": 0.5}}),
        encoding="utf-8-sig")
    monkeypatch.setattr(module, "DESK", desk)
    block = module._ceo_block()
    assert block["artifacts"]["scorecard"]["status"] == "ABSENT"      # unreadable, and it says so
    assert block["artifacts"]["sources"]["status"] == "PRESENT"
    assert block["artifacts"]["sources"]["digest"]["n_sources"] == 7
    rows = {r["key"]: r for r in block["lifetime"]}
    assert rows["survivor_yield_per_source"]["value"] == pytest.approx(0.5)


def test_the_board_carries_the_ceo_block(tmp_path: Path,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "DESK", _desk(tmp_path))
    payload = module.build()
    assert "ceo" in payload
    assert [r["key"] for r in payload["ceo"]["lifetime"]] == list(LIFETIME_KEYS)
    assert payload["ceo"]["artifacts_total"] == 7
    assert "never" in payload["ceo"]["rule"]
