"""The data-discovery swarm: four registers of need, a validated catalogue, one ranking.

Every register the scout reads is redirected into `tmp_path` or monkeypatched, so what the tests
measure is the JOIN itself -- which needs the desk can still name, whether a declared catalogue
row is complete enough to be bought from, how a source's rank is built, and that a second pass
records nothing twice. The absence tests matter as much as the presence ones: an absent register
must arrive as a NAMED absence, because a scout that reports zero needs when its inputs are
missing is indistinguishable from a desk that needs nothing (L1.28a).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import data_scout as ds  # noqa: E402

from libs.moat import registry as R  # noqa: E402
from libs.research import mechanism_ontology as onto  # noqa: E402
from libs.research_os import store  # noqa: E402

#: One observable per register, each spelled the way that register actually spells it.
REG_OBS = "broker_swap_terms_by_symbol"
VOD_OBS = "crude oil inventory draw"
OS_OBS = "vault_holdings"
ONTO_OBS = "delivery_notices"

VALUE_DOC = {
    "at": "2026-09-17T00:00:00+00:00", "n_needs": 3,
    "top": [
        {"need_id": f"blocked:{VOD_OBS}", "kind": "axis_series", "what": VOD_OBS, "value": 0.25,
         "serves": 6, "why": "six residual findings correlate with this series",
         "for_hypotheses": ["XTIUSD", "XBRUSD"]},
        {"need_id": "forward_trades:gold", "kind": "forward_trades",
         "what": "20 more forward trades on gold_asia", "value": 0.9, "serves": 1,
         "why": "the sleeve's posterior is wide", "for_hypotheses": ["gold_asia"]},
    ],
}

MECH = onto.Mechanism(
    mechanism_id="DELIVERY_SQUEEZE",
    economic_rationale="a holder short into delivery must buy back or deliver",
    observables=(ONTO_OBS, "settlement"),
    valid_transforms=("LEVEL",), valid_horizons=("DAILY",),
    falsifiers=("delivery pressure does not move the front month",))

#: A two-row catalogue for the ranking tests: the same observable at two prices.
TINY_CATALOGUE = (
    {"source": "cheap official feed", "observable_class": "energy",
     "observables": ("inventory", "crude_stocks"), "access": "free", "cadence": "weekly",
     "pit_status": "Wednesday 10:30 ET for the Friday-ending week: 5-day lag",
     "cost": 1.0, "integration_effort": 1.0, "how_to_fetch": "research_api macro.query"},
    {"source": "expensive vendor feed", "observable_class": "energy",
     "observables": ("inventory",), "access": "licensed", "cadence": "weekly",
     "pit_status": "same data, redistributed; licence read before any reuse",
     "cost": 6.0, "integration_effort": 4.0, "how_to_fetch": "no fetcher on this tree"},
)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A throwaway registry, an empty axes directory, a planted value-of-data file, and the two
    live registers (research_os, the ontology) replaced by fixtures."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    axes = tmp_path / "axes"
    axes.mkdir()
    value_path = tmp_path / "VALUE_OF_DATA.json"
    value_path.write_text(json.dumps(VALUE_DOC), encoding="utf-8")
    monkeypatch.setattr(ds, "AXES", axes)
    monkeypatch.setattr(ds, "VALUE_OF_DATA", value_path)
    monkeypatch.setattr(ds, "OUT", tmp_path / "DATA_SCOUT.json")
    monkeypatch.setattr(store, "blocking_observables", lambda: [
        {"observable": OS_OBS, "mechanisms_blocked": 2, "hypotheses_blocked": 5}])
    monkeypatch.setattr(onto, "CORE_MECHANISMS", {MECH.mechanism_id: MECH})
    yield {"tmp": tmp_path, "axes": axes, "value": value_path}
    R.set_path(None)


def _registry_need(conn: Any = None, observable: str = REG_OBS, n: int = 3) -> None:
    for i in range(n):
        R.record_discovery(source_id=f"miner{i}", source_type="miner",
                           mechanism=f"carry needs the swap terms {i}", origin="EXTERNAL",
                           generator="planted", assets=["EURUSD"],
                           exact_rule_if_known=f"carry rule {i}", required_data=[observable],
                           conn=conn)


# ------------------------------------------------------------------------ 1. gathering needs

def test_a_need_is_gathered_from_every_register(desk):
    _registry_need()
    needs, registers = ds.gather(axes_dir=desk["axes"], value_path=desk["value"])
    by_obs = {row["observable"]: row for row in needs}

    assert REG_OBS in by_obs and by_obs[REG_OBS]["blocked_hypotheses"] == 3
    assert VOD_OBS in by_obs and by_obs[VOD_OBS]["value"] == pytest.approx(0.25)
    assert OS_OBS in by_obs and by_obs[OS_OBS]["blocked_hypotheses"] == 5
    assert ONTO_OBS in by_obs and MECH.mechanism_id in by_obs[ONTO_OBS]["mechanisms"]
    assert {"registry", "value_of_data", "research_os", "mechanism_ontology"} <= set(registers)
    # The unpurchasable row is set aside and SAID SO rather than silently dropped.
    assert "not purchasable" in registers["value_of_data"]
    assert "forward trades" not in " ".join(by_obs)


def test_an_observable_the_desk_already_holds_is_not_re_shopped_for(desk):
    (desk["axes"] / "fred.json").write_text(
        json.dumps({"series": {"DGS10": {"points": []}}}), encoding="utf-8")
    _registry_need(observable="fred")
    needs, _ = ds.gather(axes_dir=desk["axes"], value_path=desk["value"])
    assert "fred" not in {row["observable"] for row in needs}

    marks, why_held = ds.held_observables(desk["axes"])
    assert "fred" in marks and "dgs10" in marks
    assert "macro.query" in why_held["fred"]
    assert not ds.is_missing("fred", marks) and not ds.is_missing("hourly bars", marks)
    # `open` is not a mark, so an exchange observable is not retired by a bar column.
    assert ds.is_missing("open_interest", marks)


def test_a_crypto_native_observable_is_refused_by_the_mandate_and_never_shopped(desk):
    _registry_need(observable="funding_rate")
    needs, registers = ds.gather(axes_dir=desk["axes"], value_path=desk["value"])
    assert "funding_rate" not in {row["observable"] for row in needs}
    assert "funding_rate" in registers["mandate_refused"]
    assert "crypto" in registers["mandate_refused"]["funding_rate"]
    assert ds.mandate_reason("perp_spot_spread") and not ds.mandate_reason("open_interest")


def test_an_absent_register_is_a_named_absence_not_a_zero(desk, monkeypatch):
    monkeypatch.setattr(ds, "VALUE_OF_DATA", desk["tmp"] / "gone.json")
    doc = ds.build(dry_run=True, axes_dir=desk["axes"], value_path=desk["tmp"] / "gone.json")
    named = {row["what"]: row["why"] for row in doc["unmeasured"]}
    assert "value_of_data" in named and named["value_of_data"].startswith("UNMEASURED")


# -------------------------------------------------------------------------- 2. the catalogue

def test_every_shipped_catalogue_row_carries_the_six_fields():
    usable, complaints = ds.validate_catalogue()
    assert complaints == []
    assert len(usable) == len(ds.CATALOGUE) >= 25
    for row in usable:
        for field_ in ds.CATALOGUE_FIELDS:
            assert str(row[field_]).strip(), f"{row.get('source')} is missing {field_}"
        assert row["access"] in ds.ACCESS
        assert isinstance(row["cost"], (int, float)) and float(row["cost"]) > 0
        assert row["observables"], f"{row['source']} declares no observable"


def test_the_catalogue_spans_the_declared_source_classes():
    classes = {str(row["observable_class"]) for row in ds.CATALOGUE}
    assert {"macro_rates", "positioning", "central_bank", "fx_structure", "exchange_public",
            "energy", "softs", "metals", "national_statistics", "multilateral",
            "filings_event_lane"} <= classes
    edgar = next(r for r in ds.CATALOGUE if "EDGAR" in r["source"])
    assert "EVENT LANE ONLY" in edgar["how_to_fetch"]
    assert not any("funding" in str(r["observables"]).lower() for r in ds.CATALOGUE)


def test_an_incomplete_catalogue_row_is_refused_and_named():
    broken = ({"source": "a source with no PIT story", "access": "free", "cadence": "daily",
               "pit_status": "", "cost": 1.0, "how_to_fetch": "x", "observables": ("y",)},
              {"source": "a source with an invented access mode", "access": "stolen",
               "cadence": "daily", "pit_status": "ok", "cost": 1.0, "how_to_fetch": "x",
               "observables": ("y",)})
    usable, complaints = ds.validate_catalogue(broken)
    assert usable == []
    assert "missing pit_status" in complaints[0]
    assert "access" in complaints[1]


# ---------------------------------------------------------------------------- 3. the ranking

def test_the_cheapest_pit_clean_source_wins_and_the_score_is_the_declared_formula():
    need = {"observable": "crude oil inventory draw", "blocked_hypotheses": 6, "value": 0.25}
    options = ds.rank_sources(need, TINY_CATALOGUE)
    assert [o["source"] for o in options] == ["cheap official feed", "expensive vendor feed"]
    assert options[0]["score"] == pytest.approx(6 * 0.25 / (1.0 + 1.0))
    assert options[1]["score"] == pytest.approx(6 * 0.25 / (6.0 + 4.0))
    assert options[0]["value_unmeasured"] is False


def test_an_unpriced_need_takes_the_declared_prior_and_never_zero():
    need = {"observable": "crude oil inventory draw", "blocked_hypotheses": 0, "value": None}
    best = ds.rank_sources(need, TINY_CATALOGUE)[0]
    assert best["value_used"] == pytest.approx(ds.VALUE_PRIOR)
    assert best["value_unmeasured"] is True
    assert best["score"] > 0.0


def test_a_source_rank_sums_the_needs_it_unblocks(desk):
    needs = [{"observable": "crude oil inventory draw", "blocked_hypotheses": 6, "value": 0.25},
             {"observable": "crude_stocks", "blocked_hypotheses": 2, "value": 0.10}]
    rows, ranked = ds.rank(needs, TINY_CATALOGUE)
    cheap = next(r for r in ranked if r["source"] == "cheap official feed")
    dear = next(r for r in ranked if r["source"] == "expensive vendor feed")
    assert cheap["needs_unblocked"] == 2 and dear["needs_unblocked"] == 1
    assert cheap["hypotheses_blocked"] == 8
    assert ranked[0]["source"] == "cheap official feed"
    assert rows[0]["best_source"]["source"] == "cheap official feed"
    assert rows[0]["alternatives"][0]["source"] == "expensive vendor feed"


def test_an_observable_no_catalogue_row_exposes_is_published_as_a_gap(desk):
    _registry_need(observable="an_observable_nobody_sells")
    doc = ds.build(dry_run=True, axes_dir=desk["axes"], value_path=desk["value"])
    row = next(r for r in doc["needs"] if r["observable"] == "an_observable_nobody_sells")
    assert row["unserved"] is True and row["best_source"] is None
    assert any(u["what"] == "an_observable_nobody_sells" for u in doc["unmeasured"])


# -------------------------------------------------------------------- 4. what the scout records

def test_each_ranked_source_becomes_a_discovery_and_a_candidate_source_row(desk):
    _registry_need()
    doc = ds.build(axes_dir=desk["axes"], value_path=desk["value"])
    assert doc["discoveries_recorded"] > 0
    assert doc["sources_registered"] == doc["discoveries_recorded"]

    datasets = [d for d in R.discoveries(limit=500) if d["source_type"] == "dataset"]
    assert datasets and all(d["state"] == "UNPROCESSED" for d in datasets)
    assert all(d["origin"] == "EXTERNAL" and d["generator"] == "data_scout" for d in datasets)
    payload = json.loads(datasets[0]["payload_json"])
    assert {"observable", "source", "pit_status", "needs", "how_to_fetch"} <= set(payload)

    conn = R.connect()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM sources")]
    finally:
        conn.close()
    assert rows and all(r["status"] == "candidate" and r["kind"] == "dataset" for r in rows)
    assert all(r["source_id"].startswith("dataset:") for r in rows)
    assert all(r["discovered_from"] == "data_scout" for r in rows)


def test_a_second_pass_records_nothing_twice(desk):
    _registry_need()
    first = ds.build(axes_dir=desk["axes"], value_path=desk["value"])
    before = len(R.discoveries(limit=500))
    second = ds.build(axes_dir=desk["axes"], value_path=desk["value"])

    assert first["discoveries_recorded"] > 0
    assert second["discoveries_recorded"] == 0 and second["sources_registered"] == 0
    assert len(R.discoveries(limit=500)) == before
    conn = R.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    finally:
        conn.close()
    assert n == first["sources_registered"]


def test_dry_run_records_nothing_registers_nothing_and_writes_nothing(desk):
    _registry_need()
    doc = ds.build(dry_run=True, axes_dir=desk["axes"], value_path=desk["value"])
    assert doc["dry_run"] is True
    assert doc["discoveries_recorded"] == 0 and doc["sources_registered"] == 0
    assert [d for d in R.discoveries(limit=500) if d["source_type"] == "dataset"] == []
    conn = R.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
    finally:
        conn.close()
    assert not (desk["tmp"] / "DATA_SCOUT.json").exists()


def test_the_artifact_carries_the_contract_keys(desk, monkeypatch):
    _registry_need()
    monkeypatch.setattr(ds, "AXES", desk["axes"])
    monkeypatch.setattr(ds, "VALUE_OF_DATA", desk["value"])
    assert ds.main(["--budget-s", "60"]) == 0
    doc = json.loads((desk["tmp"] / "DATA_SCOUT.json").read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "n_needs", "needs", "catalogue_size", "discoveries_recorded",
                        "sources_registered", "unmeasured", "rule"}
    assert doc["rule"] == ds.RULE and doc["catalogue_size"] == len(ds.CATALOGUE)
    row = doc["needs"][0]
    assert set(row) >= {"observable", "blocked_hypotheses", "mechanisms", "best_source",
                        "alternatives"}
    assert "no network call" in doc["boundary"]


def test_the_cli_dry_run_returns_zero_and_writes_nothing(desk, monkeypatch, capsys):
    _registry_need()
    monkeypatch.setattr(ds, "AXES", desk["axes"])
    monkeypatch.setattr(ds, "VALUE_OF_DATA", desk["value"])
    assert ds.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DATA SCOUT" in out and "dry-run" in out
    assert not (desk["tmp"] / "DATA_SCOUT.json").exists()
