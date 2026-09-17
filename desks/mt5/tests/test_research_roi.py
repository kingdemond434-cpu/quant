"""THE FIVE-ROI REALLOCATOR on a tmp registry: the formula exactly, the floors that make it a
reallocation rather than a cut, and the walk that makes delayed credit reach the seed.

The load-bearing assertions:

  * THE FORMULA IS THE LAW'S, TERM BY TERM. ROI_region = (novel mechanisms + useful datasets +
    survivors + dE[log W]) / (compute + API + trial budget). It is recomputed here from planted
    rows whose answer is known before the code runs, so a green test means the ARITHMETIC.
  * THE SCOUT FLOOR IS NEVER ZERO. A region with the worst ROI on the desk still gets a worker,
    because the one thing a dead region must be able to do is notice it stopped being dead.
  * THE TOTAL NEVER FALLS. Shares move between keys and sum to 1.0; a reallocation that shrank the
    total would be a cut wearing a ranking.
  * DELAYED CREDIT REACHES THE SEED THROUGH TWO HOPS. source -> discovery -> cell is how every
    mined mechanism arrives, so a credit that only pays direct parents pays nobody who mines.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import research_roi as rr  # noqa: E402


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A tmp registry and tmp artifacts: nothing reads or writes the box that trades."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    for name in ("FORWARD_DATA", "FORWARD_REPORT", "SLEEVES", "SURVIVORS", "ALLOCATION",
                 "RESEARCH_PNL", "COMPUTE_LEDGER", "API_LEDGER", "REPRESENTATION",
                 "GATE_LEDGER", "ALLOC_OUT", "FOREST_OUT", "CAPITAL_OUT", "REPORT"):
        monkeypatch.setattr(rr, name, tmp_path / f"{name}.json")
    yield {"tmp": tmp_path}
    R.set_path(None)


def _gate_ledger(tmp: Path, rows: list[dict]) -> None:
    rr.GATE_LEDGER.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def _two_hop_survivor() -> tuple[str, str, str]:
    """source -> discovery -> cell, the shape every mined mechanism actually has.

    `record_discovery` writes the source->discovery edge; `enqueue_candidate` with a discovery_id
    writes the discovery->cell edge. Nothing here links the source to the cell directly, which is
    exactly the point: only a WALK can pay the seed.
    """
    did, _ = R.record_discovery(source_id="ground:cn:7hcn", source_type="interview",
                                origin="MOAT", generator="deep_forest_miner",
                                mechanism="carry_rollover", assets=["EURUSD"])
    cid, _ = R.enqueue_candidate(family="carry", symbol="EURUSD", params={"a": 1}, origin="MOAT",
                                 mechanism="carry_rollover", generator="deep_forest_miner",
                                 chart="H1", discovery_id=did)
    return "ground:cn:7hcn", did, cid


def _survivor_artifacts(cell: str = "EURUSD_carry_asia", family: str = "carry",
                        symbol: str = "EURUSD", elog: float = 0.004) -> None:
    rr.SURVIVORS.write_text(json.dumps({"survivors": {
        cell: {"shadow_spec": {"symbol": symbol, "family": family}}}}), encoding="utf-8")
    rr.ALLOCATION.write_text(json.dumps({"marginal_delta_elog": {cell: elog}}), encoding="utf-8")


# ------------------------------------------------------------------- delayed credit, two hops --
def test_delayed_credit_reaches_the_seed_source_through_two_provenance_hops(rig) -> None:
    src, did, cid = _two_hop_survivor()
    _survivor_artifacts()
    doc = rr.run(budget_s=30, dry_run=True)
    credit = doc["delayed_credit"]
    assert credit["n_unjoined"] == 0, "the survivor joined its candidate by (symbol, family)"
    assert src in credit["by_source"], "a two-hop ancestor was not credited: the walk is broken"
    row = credit["by_source"][src]
    assert row["survivors"] == 1.0
    assert row["delta_elogw"] == pytest.approx(0.004)
    assert row["max_hops"] >= 2, "the seed is two hops up; a one-hop join would pay nobody"
    assert did in credit["by_discovery"]
    # ...and the SCIENTIST is credited on the same walk.
    assert credit["by_generator"]["deep_forest_miner"]["survivors"] == 1.0
    assert doc["source_roi"][src]["credited_survivors"] == 1.0
    assert doc["scientist_roi"]["deep_forest_miner"]["credited_survivors"] == 1.0
    _ = cid


def test_a_survivor_is_credited_once_however_many_lanes_name_it(rig) -> None:
    src, _did, _cid = _two_hop_survivor()
    _survivor_artifacts(cell="EURUSD_carry_asia")
    rr.SLEEVES.write_text(json.dumps({"sleeves": [
        {"name": "EURUSD_carry_asia", "family": "carry", "symbol": "EURUSD", "status": "LIVE"}]}),
        encoding="utf-8")
    doc = rr.run(budget_s=30, dry_run=True)
    assert doc["counts"]["survivors"] == 1, "the same cell in two lanes is one survivor"
    assert doc["delayed_credit"]["by_source"][src]["survivors"] == 1.0


# ------------------------------------------------------------------------ the region formula --
def test_roi_region_is_exactly_the_laws_formula(rig) -> None:
    src, _did, _cid = _two_hop_survivor()
    conn = R.connect()
    try:
        conn.execute("INSERT INTO sources(source_id, kind, country, language, first_seen, status) "
                     "VALUES(?,?,?,?,?,?)", (src, "interview", "cn", "zh", rr._now(), "active"))
        conn.execute("INSERT INTO source_yield(source_id, leads, claims, mechanisms, compute_s, "
                     "updated_at) VALUES(?,?,?,?,?,?)", (src, 10, 5, 2, 7200.0, rr._now()))
        conn.commit()
    finally:
        conn.close()
    _survivor_artifacts()
    doc = rr.run(budget_s=30, dry_run=True)
    china = doc["region_roi"]["by_region"]["china"]
    # novel mechanisms 2 x ... no: the SOURCE row carries the mechanisms count directly.
    assert china["novel_mechanisms"] == 2.0
    assert china["survivors"] == 1.0
    assert china["delta_elogw"] == pytest.approx(0.004)
    assert china["compute_hours"] == pytest.approx(2.0)        # 7200 s
    assert china["trials"] == 1.0                              # one candidate under this source
    assert china["api_calls"] == 0.0 and "UNMEASURED" in str(china["api_status"])
    expected_num = 2.0 + china["useful_datasets"] + 1.0 + 0.004
    expected_den = 2.0 + 0.0 + 1.0
    assert china["numerator"] == pytest.approx(expected_num)
    assert china["denominator"] == pytest.approx(expected_den)
    assert china["roi"] == pytest.approx(expected_num / expected_den)
    assert china["formula"] == rr.ROI_REGION_FORMULA
    assert doc["formula"] == ("ROI_region = (novel mechanisms + useful datasets + survivors + "
                             "dE[log W]) / (compute + API + trial budget)")


def test_a_region_with_no_denominator_is_unmeasured_never_infinite(rig) -> None:
    doc = rr.run(budget_s=30, dry_run=True)
    for name in rr.REGIONS:
        row = doc["region_roi"]["by_region"][name]
        assert row["roi"] is None and row["roi_status"] == "UNMEASURED"
        assert row["denominator"] == 0.0


def test_the_api_term_is_unmeasured_by_name_and_never_a_zero(rig) -> None:
    doc = rr.run(budget_s=30, dry_run=True)
    why = [u for u in doc["unmeasured"] if u["what"] == "API ledger"]
    assert why and "UNMEASURED, never 0" in why[0]["why"]
    assert any("research_api_calls.jsonl" in lim for lim in doc["limitations"])


# --------------------------------------------------------------------------- the scout floor --
def test_every_region_keeps_a_scout_however_bad_its_roi(rig) -> None:
    doc = rr.run(budget_s=30, dry_run=True)
    forest = doc["reallocation"]["forest"]
    assert set(forest["forests"]) == set(rr.REGIONS) and len(rr.REGIONS) == 17
    for name, row in forest["forests"].items():
        assert row["workers"] >= 1, f"{name} lost its source scout"
        assert row["scout_floor"] is True
        assert isinstance(row["budget_s"], int) and row["budget_s"] >= rr.MIN_BUDGET_S
        assert row["why"].strip()
        assert row["roi"] is None or isinstance(row["roi"], float)


def test_an_unmeasured_region_takes_the_declared_default_not_a_zero(rig) -> None:
    forest = rr.run(budget_s=30, dry_run=True)["reallocation"]["forest"]
    row = forest["forests"]["latam"]
    assert row["workers"] == rr.DEFAULT_WORKERS and row["budget_s"] == rr.DEFAULT_BUDGET_S
    assert "UNMEASURED" in row["why"]


def test_the_worst_region_is_reduced_two_sidedly_and_never_below_its_clip(rig) -> None:
    """A measured, zero-ROI region sitting beside a productive one: the productive one gains, the
    barren one is reduced to the clip and no further -- the band is symmetric on purpose."""
    regions = {r: {"roi": 0.0 if r != "japan" else 10.0, "roi_status": "MEASURED"}
               for r in rr.REGIONS}
    forest = rr.forest_allocation({"by_region": regions})
    assert forest["forests"]["japan"]["workers"] > rr.DEFAULT_WORKERS
    assert forest["forests"]["japan"]["workers"] <= rr.MAX_WORKERS
    for name in rr.REGIONS:
        assert forest["forests"][name]["workers"] >= rr.SCOUT_FLOOR_WORKERS >= 1
    assert forest["forests"]["latam"]["workers"] == round(
        rr.DEFAULT_WORKERS * rr.FACTOR_CLIP[0])


def test_the_scout_floor_binds_when_the_arithmetic_would_round_to_zero(
        rig, monkeypatch) -> None:
    """The floor is not decoration: with a small default, the two-sided factor rounds a barren
    region to ZERO workers, and the floor is what puts the scout back."""
    monkeypatch.setattr(rr, "DEFAULT_WORKERS", 1)
    regions = {r: {"roi": 0.0 if r != "japan" else 10.0, "roi_status": "MEASURED"}
               for r in rr.REGIONS}
    forest = rr.forest_allocation({"by_region": regions})
    assert round(rr.DEFAULT_WORKERS * rr.FACTOR_CLIP[0]) == 0, "the arithmetic must reach zero"
    assert forest["forests"]["latam"]["workers"] == rr.SCOUT_FLOOR_WORKERS == 1
    assert "scout floor" in forest["forests"]["latam"]["why"]


def test_the_forest_contract_is_exactly_the_shape_the_runner_expects(rig) -> None:
    rr.run(budget_s=30)
    doc = json.loads(rr.FOREST_OUT.read_text(encoding="utf-8"))
    assert set(doc) == {"at", "rule", "forests"}
    for name, row in doc["forests"].items():
        assert name in rr.REGIONS
        assert set(row) == {"workers", "budget_s", "scout_floor", "roi", "why"}
        assert isinstance(row["workers"], int) and isinstance(row["budget_s"], int)


# --------------------------------------------------------- shares rise and fall, total is kept --
def test_shares_are_two_sided_and_the_total_never_falls() -> None:
    shares = rr._two_sided_shares({"a": 10.0, "b": 1.0, "c": 0.0}, rr.MIN_FAMILY_SHARE)
    assert shares["a"] > 1 / 3 > shares["c"], "the shares must move in BOTH directions"
    assert sum(shares.values()) == pytest.approx(1.0)
    assert min(shares.values()) >= rr.MIN_FAMILY_SHARE
    # An UNMEASURED key holds the middle rather than being defunded for not being measured.
    mixed = rr._two_sided_shares({"a": 10.0, "b": None, "c": 0.0}, rr.MIN_FAMILY_SHARE)
    assert sum(mixed.values()) == pytest.approx(1.0)
    assert mixed["b"] > mixed["c"]
    # Nothing measured at all: the equal split, conserved.
    flat = rr._two_sided_shares({"a": None, "b": None}, rr.MIN_FAMILY_SHARE)
    assert flat == {"a": 0.5, "b": 0.5}


def test_the_total_share_is_conserved_across_two_different_worlds(rig) -> None:
    _gate_ledger(rig["tmp"], [{"family": "carry", "passed": True}] * 5)
    first = rr.run(budget_s=30, dry_run=True)
    _gate_ledger(rig["tmp"], [{"family": "carry", "passed": False}] * 80
                 + [{"family": "breakout", "passed": True}] * 5)
    second = rr.run(budget_s=30, dry_run=True)
    for doc in (first, second):
        total = doc["reallocation"]["trial_budget_by_family"]["total_share"]
        assert total == pytest.approx(1.0)
    assert second["reallocation"]["trial_budget_by_family"]["total_share"] >= \
        first["reallocation"]["trial_budget_by_family"]["total_share"]


def test_department_shares_sum_to_one_and_keep_their_floor(rig) -> None:
    doc = rr.run(budget_s=30, dry_run=True)
    depts = doc["reallocation"]["departments"]
    if depts["shares"]:
        assert sum(depts["shares"].values()) == pytest.approx(1.0)
        assert min(depts["shares"].values()) >= rr.MIN_DEPT_SHARE * 0.5
        assert depts["total_share"] == pytest.approx(1.0)


# ------------------------------------------------------------------------ negative knowledge --
def test_a_failed_family_is_published_as_negative_knowledge(rig) -> None:
    _gate_ledger(rig["tmp"], [{"family": "turn_of_month", "passed": False}]
                 * (rr.NEGATIVE_MIN_JUDGED + 5))
    doc = rr.run(budget_s=30, dry_run=True)
    neg = doc["negative_knowledge"]
    assert [n["family"] for n in neg] == ["turn_of_month"]
    row = neg[0]
    assert row["kind"] == "NEGATIVE_KNOWLEDGE" and row["passed"] == 0
    assert row["judged"] == rr.NEGATIVE_MIN_JUDGED + 5 and row["roi"] == 0.0
    assert "generate DIFFERENTLY, never less" in row["instruction"]
    assert row["floor"] == rr.MIN_FAMILY_SHARE, "even negative knowledge keeps a floor"
    assert doc["mechanism_roi"]["turn_of_month"]["verdict"] == "NEGATIVE_KNOWLEDGE"


def test_too_few_judged_is_unmeasured_not_negative_knowledge(rig) -> None:
    _gate_ledger(rig["tmp"], [{"family": "thin", "passed": False}] * 3)
    doc = rr.run(budget_s=30, dry_run=True)
    assert doc["negative_knowledge"] == []
    assert doc["mechanism_roi"]["thin"]["verdict"] == "UNMEASURED"


def test_a_family_that_pays_is_never_negative(rig) -> None:
    _gate_ledger(rig["tmp"], [{"family": "carry", "passed": False}] * 80
                 + [{"family": "carry", "passed": True}])
    doc = rr.run(budget_s=30, dry_run=True)
    assert doc["mechanism_roi"]["carry"]["verdict"] == "PAYS"
    assert doc["negative_knowledge"] == []


# ------------------------------------------------------------------- representation and capital --
def test_representation_roi_is_unmeasured_by_name_when_the_forge_has_not_written(rig) -> None:
    doc = rr.run(budget_s=30, dry_run=True)
    assert doc["representation_roi"]["status"] == "UNMEASURED"
    assert doc["representation_roi"]["by_representation"] == {}
    why = [u for u in doc["unmeasured"] if u["what"] == "representation ROI"]
    assert why and "this organ never writes it" in why[0]["why"]
    assert any("REPRESENTATION_FORGE.json" in lim for lim in doc["limitations"])


def test_representation_roi_is_measured_when_the_forge_has(rig) -> None:
    rr.REPRESENTATION.write_text(json.dumps({"representations": {
        "zscore": {"n_series": 40, "n_candidates": 10, "n_survivors": 2, "compute_h": 4.0}}}),
        encoding="utf-8")
    doc = rr.run(budget_s=30, dry_run=True)
    rep = doc["representation_roi"]
    assert rep["status"] == "MEASURED"
    assert rep["by_representation"]["zscore"]["roi"] == pytest.approx(0.5)


def test_capital_is_published_as_evidence_with_its_missing_consumer_named(rig) -> None:
    _gate_ledger(rig["tmp"], [{"family": "carry", "passed": True}] * 3)
    rr.run(budget_s=30)
    doc = json.loads(rr.CAPITAL_OUT.read_text(encoding="utf-8"))
    assert doc["kind"] == "evidence"
    assert doc["consumer"]["status"] == "MISSING" and doc["consumer"]["to_wire"].strip()
    assert "no fraction, no cap and no veto" in doc["boundary"]
    assert doc["by_mechanism"]["carry"]["verdict"] == "PAYS"
    # NEVER A CAP: nothing in the payload is a limit, a ceiling or a veto.
    body = json.dumps(doc).lower()
    assert "max_risk" not in body and "cap_at" not in body


# ------------------------------------------------------------------------- artifacts and CLI --
def test_the_allocation_file_names_every_consumer_it_feeds(rig) -> None:
    rr.run(budget_s=30)
    doc = json.loads(rr.ALLOC_OUT.read_text(encoding="utf-8"))
    assert set(doc["consumers"]) == {"departments", "trial_budget_by_family",
                                     "forward_slot_weights"}
    assert "research_departments" in doc["consumers"]["departments"]
    assert "gauntlet_backpressure" in doc["consumers"]["trial_budget_by_family"]
    assert "forward_slot_ranker" in doc["consumers"]["forward_slot_weights"]
    assert doc["collision_note"].strip()
    assert doc["forward_slot_weights"]["unmeasured_reads"] == 1.0


def test_dry_run_writes_nothing(rig) -> None:
    doc = rr.run(budget_s=30, dry_run=True)
    assert doc["dry_run"] is True
    for p in (rr.ALLOC_OUT, rr.FOREST_OUT, rr.CAPITAL_OUT, rr.REPORT):
        assert not p.exists()


def test_the_report_carries_the_five_rois_and_its_limitations(rig) -> None:
    rr.run(budget_s=30)
    doc = json.loads(rr.REPORT.read_text(encoding="utf-8"))
    for key in ("source_roi", "dataset_roi", "representation_roi", "mechanism_roi",
                "scientist_roi", "region_roi"):
        assert key in doc, key
    assert len(doc["limitations"]) >= 4
    assert doc["rule"].strip() and doc["formula"] == rr.ROI_REGION_FORMULA


def test_an_empty_desk_is_measured_not_a_crash(rig) -> None:
    doc = rr.run(budget_s=30, dry_run=True)
    assert doc["counts"]["sources"] == 0 and doc["delayed_credit"]["n_survivors"] == 0
    assert doc["n_negative_families"] == 0


def test_cli_dry_run_prints_the_formula_and_writes_nothing(rig, capsys) -> None:
    assert rr.main(["--once", "--budget-s", "30", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert rr.ROI_REGION_FORMULA in out and "--dry-run: nothing written" in out
    assert not rr.REPORT.exists()


def test_region_routing_is_an_explicit_table_never_a_guess() -> None:
    assert rr.region_of("cn") == "china" and rr.region_of("ja") == "japan"
    assert rr.region_of("ground:cn:7hcn") == "china"
    assert rr.region_of("not_a_place") is None
    assert set(rr.REGION_OF.values()) <= set(rr.REGIONS)
