"""H3: gate 1 asks a NAMED cell for the six-field EconomicPrior, and grandfathers what exists."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from research.frontier_identity import (
    GRANDFATHERED_FAMILIES,
    GRANDFATHERED_UNMEASURED,
    PRIOR_COMPLETE,
    PRIOR_FIELDS,
    PRIOR_INCOMPLETE,
    economic_prior,
)

from research import economic_prior_backfill as bf
from research import frontier_identity as fi

DESK = Path(__file__).resolve().parents[1]

FULL = {"mechanism": "structural", "why_it_works": "a", "why_it_might_fail": "b",
        "why_overfit": "c", "why_decay": "d", "how_detect_decay": "e", "what_replaces_it": "f"}


@pytest.fixture(autouse=True)
def _empty_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fi, "_REGISTRY_CACHE", {"families": {}, "mode": "SHADOW"})


def test_a_new_unrostered_named_family_passes_gate_one_as_prior_incomplete() -> None:
    """SHADOW (the default): recorded, missing fields listed, never vetoed."""
    assert "brand_new_mechanism" not in GRANDFATHERED_FAMILIES
    stage = economic_prior({"family": "brand_new_mechanism", "mechanism_status": "NAMED"})
    assert stage["passed"] is True
    assert stage["binding"] is False
    assert stage["verdict"] == PRIOR_INCOMPLETE
    assert stage["missing"] == list(PRIOR_FIELDS)
    assert "brand_new_mechanism" in stage["message"]


def test_the_switch_defaults_to_shadow_and_binds_only_when_live(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert json.loads(fi.PRIOR_MODE_PATH.read_text("utf-8"))["mode"] == "SHADOW"
    monkeypatch.setattr(fi, "_REGISTRY_CACHE", {"families": {}})
    monkeypatch.setattr(fi, "PRIOR_MODE_PATH", tmp_path / "absent.json")
    assert fi.prior_mode() == "SHADOW"
    monkeypatch.setattr(fi, "_REGISTRY_CACHE", {"families": {}, "mode": "LIVE"})
    stage = economic_prior({"family": "brand_new_mechanism"})
    assert stage["passed"] is False and stage["binding"] is True
    assert stage["verdict"] == PRIOR_INCOMPLETE


def test_a_partial_prior_names_exactly_the_missing_fields() -> None:
    partial = {k: v for k, v in FULL.items() if k not in ("why_decay", "what_replaces_it")}
    stage = economic_prior({"family": "brand_new_mechanism", "economic_prior": partial})
    assert stage["passed"] is True
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


def test_the_judge_records_prior_incomplete_and_never_drops_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import external_gauntlet
    specs = [{"sym": "EURUSD", "family": "brand_new_mechanism", "params": {},
              "mechanism_status": "NAMED"},
             {"sym": "XAUUSD", "family": "vol_transition", "params": {},
              "mechanism_status": "NAMED"}]
    eligible, rejected = external_gauntlet.partition_at_economic_prior([dict(s) for s in specs])
    assert len(eligible) == 2 and rejected == []          # SHADOW: no veto
    monkeypatch.setattr(fi, "_REGISTRY_CACHE", {"families": {}, "mode": "LIVE"})
    eligible, rejected = external_gauntlet.partition_at_economic_prior(specs)
    assert [s["family"] for s in eligible] == ["vol_transition"]
    assert len(rejected) == 1
    stage = rejected[0]["stages"]["economic_prior"]
    assert stage["verdict"] == PRIOR_INCOMPLETE and stage["missing"] == list(PRIOR_FIELDS)


def test_full_pipeline_no_longer_asserts_gate_one() -> None:
    src = (DESK / "side_channels" / "full_pipeline.py").read_text("utf-8")
    assert not re.search(r'"economic_prior":\s*\{\s*"passed":\s*True', src)
    assert '"economic_prior": economic_prior(c)' in src


def test_families_off_the_roster_are_reported_not_gated(tmp_path: Path) -> None:
    """The roster is a REPORT: a held family off it is listed, and nothing fails."""
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([{"symbol": "EURUSD", "family": "brand_new_mechanism"}]),
                      encoding="utf-8")
    report = bf.build(docket=docket, certs=tmp_path / "a.json", sleeves=tmp_path / "b.json",
                      registry=tmp_path / "c.json", clocks=tmp_path / "d.json",
                      mode_path=tmp_path / "e.json")
    assert report["held_off_roster"] == ["brand_new_mechanism"]
    assert report["docket"]["gate1_verdicts"] == {PRIOR_INCOMPLETE: 1}


def test_frontier_identity_does_not_import_libs_validation() -> None:
    """The gateway imports frontier_identity for cell_id; the validation package stays out."""
    code = (f"import sys; sys.path[:0] = [{str(DESK.parents[1])!r}, {str(DESK)!r}]\n"
            "import research.frontier_identity as fi\n"
            "fi.cell_id({'sym': 'EURUSD', 'family': 'carry', 'params': {}})\n"
            "print(any(m == 'libs.validation' or m.startswith('libs.validation.')"
            " for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, cwd=str(DESK))
    assert out.stdout.strip() == "False"


def test_local_required_fields_match_the_validator() -> None:
    from libs.validation.economic_prior import REQUIRED_FIELDS
    assert fi.REQUIRED_FIELDS == REQUIRED_FIELDS


def _clocks(path: Path, complete: list[float], incomplete: list[float]) -> None:
    doc = {}
    for i, r in enumerate(complete):
        doc[f"EURUSD.fam_c.s{i}"] = {"n": 20, "exp_r": r, "last_entry": f"2026-11-{i % 28 + 1:02d}"}
    for i, r in enumerate(incomplete):
        doc[f"EURUSD.carry.s{i}"] = {"n": 20, "exp_r": r, "last_entry": f"2026-11-{i % 28 + 1:02d}"}
    doc["USDJPY.asia"] = {"n": 50, "exp_r": 9.0}       # a hunt key names no family: not counted
    doc["EURUSD.carry.young"] = {"n": 3, "exp_r": 9.0}  # under MIN_CLOCK_N: not counted
    path.write_text(json.dumps(doc), encoding="utf-8")


def _switch_case(tmp_path: Path, complete: list[float], incomplete: list[float],
                 start: str) -> dict:
    clocks = tmp_path / "clocks.json"
    _clocks(clocks, complete, incomplete)
    reg = tmp_path / "priors.json"
    reg.write_text(json.dumps({"families": {"fam_c": FULL}}), encoding="utf-8")
    mode = tmp_path / "mode.json"
    mode.write_text(json.dumps({"mode": start}), encoding="utf-8")
    return bf.build(docket=tmp_path / "none.json", certs=tmp_path / "x.json",
                    sleeves=tmp_path / "y.json", registry=reg, clocks=clocks,
                    mode_path=mode, write_switch=True)


def test_switch_promotes_on_two_se_and_demotes_on_one_se(tmp_path: Path) -> None:
    up = _switch_case(tmp_path, [0.5 + 0.01 * i for i in range(12)],
                      [0.0 + 0.01 * i for i in range(12)], "SHADOW")
    assert up["evidence"]["action"] == "PROMOTE" and up["mode"]["mode"] == "LIVE"
    assert json.loads((tmp_path / "mode.json").read_text("utf-8"))["mode"] == "LIVE"
    down = _switch_case(tmp_path, [0.0 + 0.01 * i for i in range(12)],
                        [0.5 + 0.01 * i for i in range(12)], "LIVE")
    assert down["evidence"]["action"] == "DEMOTE" and down["mode"]["mode"] == "SHADOW"
    line = down["missed_growth"][0]
    assert line["gate"] == "economic_prior_six_field" and line["verdict"] == "COSTS_GROWTH"


def test_switch_holds_below_the_window_and_when_pinned(tmp_path: Path) -> None:
    few = _switch_case(tmp_path, [0.9] * 5, [0.0] * 5, "SHADOW")
    assert few["evidence"]["verdict"] == "UNMEASURED" and few["mode"]["mode"] == "SHADOW"
    (tmp_path / "mode.json").write_text(json.dumps({"mode": "SHADOW", "pinned": True}), "utf-8")
    report = bf.build(docket=tmp_path / "none.json", certs=tmp_path / "x.json",
                      sleeves=tmp_path / "y.json", registry=tmp_path / "priors.json",
                      clocks=tmp_path / "clocks.json", mode_path=tmp_path / "mode.json",
                      write_switch=True)
    assert report["mode"]["mode"] == "SHADOW" and report["mode"]["changed"] is False


def test_missed_growth_carries_the_published_line(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    from research import missed_growth as mg
    monkeypatch.setattr(mg, "ECONOMIC_PRIOR", tmp_path / "absent.json")
    assert mg.published_economic_prior_lines()["verdict"] == "UNMEASURED"
    rep = tmp_path / "ECONOMIC_PRIOR_BACKFILL.json"
    report = _switch_case(tmp_path, [0.0] * 12, [0.0] * 12, "SHADOW")
    rep.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(mg, "ECONOMIC_PRIOR", rep)
    got = mg.published_economic_prior_lines()
    assert got["mode"] == "SHADOW" and got["lines"][0]["gate"] == "economic_prior_six_field"


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
                      sleeves=tmp_path / "absent2.json", registry=reg,
                      clocks=tmp_path / "absent3.json", mode_path=tmp_path / "absent4.json")
    assert report["docket"]["gate1_verdicts"] == {GRANDFATHERED_UNMEASURED: 1,
                                                  PRIOR_INCOMPLETE: 1}
    assert report["certificates"]["state"] == "UNMEASURED"
    carry = next(r for r in report["families"] if r["family"] == "carry")
    assert carry["status"] == "INCOMPLETE"
    assert "why_decay" in carry["missing"] and "why_it_works" not in carry["missing"]


def test_prior_record_keys_stay_out_of_the_identity_chain_hash() -> None:
    from research import identity_chain
    assert {"verdict", "missing", "prior_source", "binding"} == identity_chain.PRIOR_RECORD_KEYS
    src = (DESK / "research" / "identity_chain.py").read_text("utf-8")
    assert 'g == "economic_prior"' in src and "k in PRIOR_RECORD_KEYS" in src
