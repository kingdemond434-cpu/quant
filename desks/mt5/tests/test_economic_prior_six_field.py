"""H3: gate 1 asks a NAMED cell for the six-field EconomicPrior, and grandfathers what exists."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from research import economic_prior_backfill as bf
from research import frontier_identity as fi
from research.frontier_identity import (
    GRANDFATHERED_FAMILIES,
    GRANDFATHERED_UNMEASURED,
    PRIOR_COMPLETE,
    PRIOR_FIELDS,
    PRIOR_INCOMPLETE,
    economic_prior,
)

DESK = Path(__file__).resolve().parents[1]

FULL = {"mechanism": "structural", "why_it_works": "a", "why_it_might_fail": "b",
        "why_overfit": "c", "why_decay": "d", "how_detect_decay": "e", "what_replaces_it": "f"}


@pytest.fixture(autouse=True)
def _empty_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fi, "_REGISTRY_CACHE", {"families": {}})


def test_a_new_family_without_a_prior_is_recorded_prior_incomplete() -> None:
    stage = economic_prior({"family": "brand_new_mechanism", "mechanism_status": "NAMED"})
    assert stage["passed"] is False
    assert stage["verdict"] == PRIOR_INCOMPLETE
    assert stage["missing"] == list(PRIOR_FIELDS)
    assert "brand_new_mechanism" in stage["message"]


def test_a_partial_prior_names_exactly_the_missing_fields() -> None:
    partial = {k: v for k, v in FULL.items() if k not in ("why_decay", "what_replaces_it")}
    stage = economic_prior({"family": "brand_new_mechanism", "economic_prior": partial})
    assert stage["passed"] is False
    assert stage["verdict"] == PRIOR_INCOMPLETE
    assert stage["missing"] == ["why_decay", "what_replaces_it"]
    assert stage["prior_source"] == "cell"


def test_a_complete_prior_passes_from_the_cell_or_the_family_registry(
        monkeypatch: pytest.MonkeyPatch) -> None:
    stage = economic_prior({"family": "brand_new_mechanism", "economic_prior": FULL})
    assert stage["passed"] is True and stage["verdict"] == PRIOR_COMPLETE
    monkeypatch.setattr(fi, "_REGISTRY_CACHE", {"families": {"brand_new_mechanism": FULL}})
    stage = economic_prior({"family": "brand_new_mechanism"})
    assert stage["passed"] is True and stage["prior_source"] == "family_registry"


def test_a_grandfathered_family_still_passes_and_its_debt_is_named() -> None:
    stage = economic_prior({"family": "session_range_breakout"})
    assert stage["passed"] is True
    assert stage["verdict"] == GRANDFATHERED_UNMEASURED
    assert stage["missing"] == list(PRIOR_FIELDS)


def test_statistical_only_is_unchanged() -> None:
    stage = economic_prior({"family": "discovered"})
    assert stage["passed"] is False and stage["mechanism_status"] == "STATISTICAL_ONLY"


def test_the_judge_records_prior_incomplete_and_never_drops_it() -> None:
    from scripts import external_gauntlet
    specs = [{"sym": "EURUSD", "family": "brand_new_mechanism", "params": {},
              "mechanism_status": "NAMED"},
             {"sym": "XAUUSD", "family": "vol_transition", "params": {},
              "mechanism_status": "NAMED"}]
    eligible, rejected = external_gauntlet.partition_at_economic_prior(specs)
    assert [s["family"] for s in eligible] == ["vol_transition"]
    assert len(rejected) == 1
    stage = rejected[0]["stages"]["economic_prior"]
    assert stage["verdict"] == PRIOR_INCOMPLETE and stage["missing"] == list(PRIOR_FIELDS)


def test_full_pipeline_no_longer_asserts_gate_one() -> None:
    src = (DESK / "side_channels" / "full_pipeline.py").read_text("utf-8")
    assert not re.search(r'"economic_prior":\s*\{\s*"passed":\s*True', src)
    assert '"economic_prior": economic_prior(c)' in src


def test_no_family_the_desk_holds_today_is_demoted() -> None:
    """Every family in the repo's docket, certificates and sleeves is on the roster."""
    held: set[str] = set()
    docket = DESK / "data" / "hypotheses" / "external_survivors.json"
    if docket.exists():
        held |= {str(r.get("family")) for r in json.loads(docket.read_text("utf-8"))
                 if isinstance(r, dict) and r.get("family")}
    certs = json.loads((DESK / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
    held |= {str((r.get("shadow_spec") or {}).get("family")) for r in certs["survivors"].values()
             if (r.get("shadow_spec") or {}).get("family")}
    sleeves = json.loads((DESK / "data" / "sleeves.json").read_text("utf-8"))["sleeves"]
    held |= {str(r["family"]) for r in sleeves if r.get("family")}
    assert held - GRANDFATHERED_FAMILIES == set()


def test_backfill_report_counts_debt_and_new_family_rejects(tmp_path: Path) -> None:
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([
        {"symbol": "EURUSD", "family": "carry", "mechanism_status": "NAMED"},
        {"symbol": "EURUSD", "family": "brand_new_mechanism", "mechanism_status": "NAMED"},
    ]), encoding="utf-8")
    reg = tmp_path / "priors.json"
    reg.write_text(json.dumps({"families": {"carry": {"mechanism": "risk_premium",
                                                      "why_it_works": "x"}}}), encoding="utf-8")
    report = bf.build(docket=docket, certs=tmp_path / "absent.json",
                      sleeves=tmp_path / "absent2.json", registry=reg)
    assert report["docket"]["gate1_verdicts"] == {GRANDFATHERED_UNMEASURED: 1,
                                                  PRIOR_INCOMPLETE: 1}
    assert report["certificates"]["state"] == "UNMEASURED"
    carry = next(r for r in report["families"] if r["family"] == "carry")
    assert carry["status"] == "INCOMPLETE"
    assert "why_decay" in carry["missing"] and "why_it_works" not in carry["missing"]
