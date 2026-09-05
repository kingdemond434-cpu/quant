"""FeatureROI on a fixture whose answer is known by hand, and the effort it withdraws.

    cd desks/mt5 && python -m pytest tests/test_feature_roi.py -q

The organ joins four artifacts, so the risk is that a wiring change quietly turns a measurement
into a plausible number. Every assertion below is against arithmetic done on paper first:

  1. the cost denominator is the declared table, term by term -- external feeds pay acquisition
     and maintenance, every variant pays multiplicity, compute is the store's own seconds
  2. dE[logW | F_j] is the conditioning ledger's claim times the allocator's OWN share_of_heat
     from RESEARCH_PNL, scaled so the features divide allocator_attribution's state term rather
     than adding a second one beside it -- ROI is that over the cost, to the digit
  3. below MIN_N the verdict is UNMEASURED, the ROI is None, and nothing dies on it
  4. a negative ROI at MIN_N kills the feature and `withdraw` stops the compute
  5. two features that are the same column twice make the second REDUNDANT
  6. the status and the ROI line are written back onto every sidecar of the feature
  7. every absent input is named under `gaps` rather than read as a zero
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import feature_roi as fr  # noqa: E402

from libs.data import feature_lifecycle as lc  # noqa: E402


def _sidecar(root: Path, fid: str, name: str, *, source: str = "bars",
             params: dict[str, Any] | None = None, compute_s: float = 0.5,
             data_hash: str = "d0", status: str = lc.NEW,
             roi: dict[str, Any] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    p = root / f"{fid}.json"
    p.write_text(json.dumps({
        "id": fid, "name": name, "params": params or {}, "source": source,
        "provider": "test", "data_hash": data_hash, "compute_s": compute_s,
        "units": "sigma", "currency": None, "timezone": "UTC",
        "status": status, "roi": roi, "n": 500, "coverage_frac": 1.0,
    }, indent=1), "utf-8")
    return p


def _ledger(path: Path, state: str, n: int, *, mu_state: float, mu_uncond: float,
            heat: float, sleeve: str = "XAUUSD_a") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"t": f"2026-09-0{1 + i % 4}T00:00:00+00:00", "sleeve": sleeve,
                                 "state": state, "category": "BOOST", "multiplier": 1.4,
                                 "n_state": 50, "mu_state": mu_state, "mu_uncond": mu_uncond,
                                 "heat": heat}) + "\n")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fixture tree with every input the organ reads, all of them pointed at tmp_path."""
    monkeypatch.setattr(fr, "FEATURES", tmp_path / "features")
    monkeypatch.setattr(fr, "LEDGER", tmp_path / "capital_modifier_ledger.jsonl")
    monkeypatch.setattr(fr, "MODIFIERS", tmp_path / "CAPITAL_MODIFIERS.json")
    monkeypatch.setattr(fr, "ATTRIBUTION", tmp_path / "allocator_attribution.json")
    monkeypatch.setattr(fr, "RESEARCH_PNL", tmp_path / "RESEARCH_PNL.json")
    monkeypatch.setattr(fr, "STATE_ADMISSION", tmp_path / "STATE_ADMISSION.json")
    monkeypatch.setattr(fr, "CANON", tmp_path / "UNIVERSAL_SURVIVORS.canon.json")
    monkeypatch.setattr(fr, "EXECUTION", tmp_path / "execution_intelligence.json")
    monkeypatch.setattr(fr, "REPORT", tmp_path / "FEATURE_ROI.json")
    return tmp_path


def _known_answer_tree(desk: Path, *, mu_state: float = 0.002, rows: int = 40) -> None:
    """One external feature the ledger credits, one bars feature it does not.

    BY HAND, and the test asserts every step of it:
      cot_z      cost = acquisition 5 + compute 2.0 + maintenance 3 + multiplicity 1  = 11.0
      log_return cost = acquisition 0 + compute 1.0 + maintenance 0 + multiplicity 2  =  3.0
      d          = (mu_state - mu_uncond) * share_of_heat = (0.002 - 0.001) * 0.5 = 0.0005
      scale      = state term / total claim                = 0.001 / 0.0005      = 2.0
      benefit    = 0.0005 * 2.0                                                  = 0.001
      roi(cot_z) = 0.001 / 11.0
    """
    feats = desk / "features"
    _sidecar(feats, "a1", "cot_z", source="cftc_cot", params={"symbol": "XAUUSD", "w": 52},
             compute_s=2.0)
    _sidecar(feats, "b1", "log_return", params={"h": 1}, compute_s=0.5)
    _sidecar(feats, "b2", "log_return", params={"h": 24}, compute_s=0.5)
    _ledger(desk / "capital_modifier_ledger.jsonl", "cot_z_high", rows,
            mu_state=mu_state, mu_uncond=0.001, heat=0.2)
    (desk / "RESEARCH_PNL.json").write_text(json.dumps(
        {"sleeves": {"XAUUSD_a": {"weight": 0.2, "share_of_heat": 0.5,
                                  "growth_per_day": 0.004}}}), "utf-8")
    (desk / "allocator_attribution.json").write_text(json.dumps(
        {"growth_decomposition": {"terms": {"state": {"value": 0.001}}}}), "utf-8")
    (desk / "UNIVERSAL_SURVIVORS.canon.json").write_text(json.dumps(
        {"survivors": {"H-1": {"condition": "cot_z > 1"}}}), "utf-8")


# ------------------------------------------------- 1. the cost denominator

def test_the_cost_table_is_applied_term_by_term() -> None:
    external = [{"source": "cftc_cot", "params": {"w": 52}, "compute_s": 2.0}]
    c = fr.cost_units(external)
    assert c["acquisition"] == fr.ACQUISITION_EXTERNAL
    assert c["maintenance"] == fr.MAINTENANCE_EXTERNAL
    assert c["compute"] == pytest.approx(2.0 * fr.COMPUTE_UNITS_PER_S)
    assert c["multiplicity"] == 1 * fr.MULTIPLICITY_PER_VARIANT
    assert c["total"] == pytest.approx(11.0)


def test_bars_pay_no_acquisition_and_every_variant_pays_multiplicity() -> None:
    bars = [{"source": "bars", "params": {"h": 1}, "compute_s": 0.5},
            {"source": "bars", "params": {"h": 24}, "compute_s": 0.5}]
    c = fr.cost_units(bars)
    assert c["acquisition"] == 0.0 and c["maintenance"] == 0.0
    assert c["variants"] == 2 and c["multiplicity"] == 2 * fr.MULTIPLICITY_PER_VARIANT
    assert c["total"] == pytest.approx(3.0)


def test_a_costless_feature_still_costs_the_floor() -> None:
    c = fr.cost_units([{"source": "bars", "params": {}, "compute_s": 0.0}])
    assert c["total"] >= fr.MIN_COST_UNITS, "a zero denominator is an infinite ROI, not a free "\
                                            "feature"


# ------------------------------------------------- 2. the arithmetic, to the digit

def test_feature_roi_matches_the_hand_computed_answer(desk: Path) -> None:
    _known_answer_tree(desk)
    doc = fr.run()
    cot = doc["per_feature"]["cot_z"]
    assert cot["n"] == 40 and cot["verdict"] == "MEASURED"
    assert cot["benefit_unscaled"] == pytest.approx(0.0005)
    assert doc["state_scale"] == pytest.approx(2.0)
    assert cot["benefit_logw_per_day"] == pytest.approx(0.001)
    assert cot["cost_units"]["total"] == pytest.approx(11.0)
    assert cot["roi"] == pytest.approx(0.001 / 11.0)
    assert cot["ci"] == [pytest.approx(0.001 / 11.0), pytest.approx(0.001 / 11.0)]


def test_the_allocator_s_share_of_heat_is_preferred_over_the_ledger_s_raw_heat(
        desk: Path) -> None:
    _known_answer_tree(desk)
    doc = fr.run()
    assert doc["per_feature"]["cot_z"]["heat_fallback_rows"] == 0
    # Drop the sleeve from RESEARCH_PNL: the row's own heat (0.2) is used and the fallback counted.
    (desk / "RESEARCH_PNL.json").write_text(json.dumps({"sleeves": {}}), "utf-8")
    doc = fr.run()
    cot = doc["per_feature"]["cot_z"]
    assert cot["heat_fallback_rows"] == 40
    assert cot["benefit_unscaled"] == pytest.approx((0.002 - 0.001) * 0.2)


def test_an_unmeasured_state_term_leaves_the_claims_unscaled_and_says_so(desk: Path) -> None:
    _known_answer_tree(desk)
    (desk / "allocator_attribution.json").write_text(json.dumps(
        {"growth_decomposition": {"terms": {"state": {"value": "UNMEASURED"}}}}), "utf-8")
    doc = fr.run()
    assert doc["state_scale"] == 1.0
    assert "UNMEASURED" in doc["state_scale_why"]
    assert doc["per_feature"]["cot_z"]["benefit_logw_per_day"] == pytest.approx(0.0005)


# ------------------------------------------------- 3. below MIN_N nothing dies

def test_below_min_n_the_verdict_is_unmeasured_and_the_roi_is_none(desk: Path) -> None:
    _known_answer_tree(desk, rows=lc.MIN_N - 1)
    doc = fr.run()
    cot = doc["per_feature"]["cot_z"]
    assert cot["n"] == lc.MIN_N - 1
    assert cot["verdict"] == "UNMEASURED" and cot["roi"] is None
    assert cot["status"] != lc.DEAD


def test_a_feature_the_ledger_never_names_is_unmeasured_not_zero(desk: Path) -> None:
    _known_answer_tree(desk)
    lr = fr.run()["per_feature"]["log_return"]
    assert lr["n"] == 0 and lr["roi"] is None and lr["verdict"] == "UNMEASURED"
    assert lr["status"] == lc.NEW, "silence is not a verdict"
    assert lc.withdraw(lr["status"]).may_spend


# ------------------------------------------------- 4. a negative ROI withdraws effort

def test_a_negative_roi_at_min_n_kills_the_feature_and_stops_its_compute(desk: Path) -> None:
    _known_answer_tree(desk, mu_state=0.0005)          # below the unconditional mean of 0.001
    doc = fr.run()
    cot = doc["per_feature"]["cot_z"]
    assert cot["benefit_unscaled"] < 0
    assert cot["status"] == lc.DEAD
    assert cot["may_spend_compute"] is False
    assert "withdraw" in cot["effort_why"]
    assert doc["counts"]["dead"] == 1


def test_a_gauntlet_certificate_makes_a_measured_feature_useful(desk: Path) -> None:
    _known_answer_tree(desk)
    cot = fr.run()["per_feature"]["cot_z"]
    assert cot["status"] == lc.USEFUL
    assert lc.CONSUMER_GAUNTLET in cot["consumers"]
    assert cot["may_spend_compute"] is True


def test_an_admitted_state_dimension_alone_makes_it_state_only(desk: Path) -> None:
    _known_answer_tree(desk)
    (desk / "UNIVERSAL_SURVIVORS.canon.json").write_text(json.dumps({"survivors": {}}), "utf-8")
    cot = fr.run()["per_feature"]["cot_z"]
    assert cot["status"] == lc.STATE_ONLY
    assert cot["consumers"] == [lc.CONSUMER_STATE]


# ------------------------------------------------- 5. redundancy from the blocks themselves

def test_the_second_copy_of_a_column_is_redundant(desk: Path) -> None:
    feats = desk / "features"
    rng = np.random.default_rng(0)
    base = rng.normal(size=400)
    _sidecar(feats, "x1", "alpha_one", data_hash="same")
    _sidecar(feats, "x2", "alpha_two", data_hash="same")
    np.save(feats / "x1.npy", base)
    np.save(feats / "x2.npy", base * 3.0 + 1.0)          # the same column, rescaled: |corr| = 1
    doc = fr.run()
    statuses = {n: f["status"] for n, f in doc["per_feature"].items()}
    assert statuses == {"alpha_one": lc.REDUNDANT, "alpha_two": lc.REDUNDANT}
    span = doc["per_feature"]["alpha_one"]["spanned"]
    assert span["spanned_by"] == "alpha_two" and span["max_abs_corr"] == pytest.approx(1.0)
    assert doc["per_feature"]["alpha_one"]["may_spend_compute"] is False


def test_independent_columns_are_not_redundant(desk: Path) -> None:
    feats = desk / "features"
    rng = np.random.default_rng(1)
    _sidecar(feats, "x1", "alpha_one", data_hash="same")
    _sidecar(feats, "x2", "alpha_two", data_hash="same")
    np.save(feats / "x1.npy", rng.normal(size=2000))
    np.save(feats / "x2.npy", rng.normal(size=2000))
    doc = fr.run()
    assert {f["status"] for f in doc["per_feature"].values()} == {lc.NEW}


def test_blocks_on_different_bars_are_never_compared(desk: Path) -> None:
    """A correlation between two different histories is not a statement about the features."""
    feats = desk / "features"
    base = np.random.default_rng(2).normal(size=400)
    _sidecar(feats, "x1", "alpha_one", data_hash="bars_a")
    _sidecar(feats, "x2", "alpha_two", data_hash="bars_b")
    np.save(feats / "x1.npy", base)
    np.save(feats / "x2.npy", base)
    doc = fr.run()
    assert all(f["spanned"] is None for f in doc["per_feature"].values())


# ------------------------------------------------- 6. the verdict is written back

def test_the_status_and_roi_line_land_on_every_sidecar_of_the_feature(desk: Path) -> None:
    _known_answer_tree(desk)
    fr.run()
    for fid in ("b1", "b2"):
        doc = json.loads((desk / "features" / f"{fid}.json").read_text("utf-8"))
        assert doc["status"] == lc.NEW and doc["roi"]["verdict"] == "UNMEASURED"
        assert doc["status_at"], "a status with no time on it cannot be aged"
    cot = json.loads((desk / "features" / "a1.json").read_text("utf-8"))
    assert cot["status"] == lc.USEFUL
    assert cot["roi"]["roi"] == pytest.approx(0.001 / 11.0)
    assert cot["roi"]["cost_units"]["total"] == pytest.approx(11.0)


def test_a_run_that_does_not_write_leaves_the_sidecars_alone(desk: Path) -> None:
    _known_answer_tree(desk)
    fr.run(write=False)
    assert json.loads((desk / "features" / "a1.json").read_text("utf-8"))["status"] == lc.NEW
    assert not (desk / "FEATURE_ROI.json").exists()


def test_the_report_is_written_with_the_formula_on_it(desk: Path) -> None:
    _known_answer_tree(desk)
    fr.run()
    doc = json.loads((desk / "FEATURE_ROI.json").read_text("utf-8"))
    assert "dE[logW | F_j]" in doc["formula"]
    assert doc["counts"]["useful"] == 1
    assert doc["min_n"] == lc.MIN_N


def test_decay_is_counted_across_passes_from_the_previous_roi_line(desk: Path) -> None:
    _known_answer_tree(desk)
    fr.run()
    # A second pass with a smaller claim: the ROI falls, and the falling-window counter moves.
    _ledger(desk / "capital_modifier_ledger.jsonl", "cot_z_high", 40,
            mu_state=0.0015, mu_uncond=0.001, heat=0.2)
    assert fr.run()["per_feature"]["cot_z"]["falling_windows"] == 1


# ------------------------------------------------- 7. absent inputs are named

def test_every_absent_input_is_named_as_a_gap(desk: Path) -> None:
    doc = fr.run()
    assert doc["counts"]["useful"] == 0
    for key in ("warehouse", "conditioning_ledger", "research_pnl", "allocator_attribution"):
        assert key in doc["gaps"], f"{key} absent and not named"
    assert "not zero" in doc["gaps"]["conditioning_ledger"]


def test_a_ledger_that_names_no_warehouse_feature_says_so(desk: Path) -> None:
    _known_answer_tree(desk)
    _ledger(desk / "capital_modifier_ledger.jsonl", "weekday", 40,
            mu_state=0.002, mu_uncond=0.001, heat=0.2)
    doc = fr.run()
    assert "state_join" in doc["gaps"]
    assert "weekday" in doc["gaps"]["state_join"]
    assert doc["per_feature"]["cot_z"]["n"] == 0


def test_a_state_key_matches_on_tokens_never_on_substrings() -> None:
    names = {"hour", "cot_z"}
    assert fr.state_features("xauusd_cot_z_high", names) == {"cot_z"}
    assert fr.state_features("hour", names) == {"hour"}
    assert fr.state_features("hourly_phase", names) == set(), "a substring is not a name"


def test_main_runs_and_reports(desk: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _known_answer_tree(desk)
    assert fr.main([]) == 0
    out = capsys.readouterr().out
    assert "FEATURE ROI" in out and "cot_z" in out and "USEFUL" in out
