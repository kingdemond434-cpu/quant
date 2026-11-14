"""The observed zero reaches the registry STAMPED, and a cost-basis change re-judges what it
decided (zero_spread_cost_basis v2, 2026-10-21).

An unstamped registry zero cannot be told from a `symbol_info.spread` read before any tick
arrived: a stub, a read artifact. So the fix is in the tape (`fusion_spread_tape.observed_zero`),
and these tests pin the other two halves:

  * the registry repair writes a zero ONLY as the tape's observed zero, with its evidence on
    the provenance stamp the sealed gate reads, and never indexes a `_provenance` that is not
    a map (a list there used to take the whole pass down);
  * when a symbol's basis changes, `cost_basis_rejudge` puts the cells that basis decided at
    the front of the judge's own re-mint queue, but only after the cell's cache can serve the
    new cost.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "scripts"), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pd = pytest.importorskip("pandas")
rus = pytest.importorskip("repair_universe_spreads")
cbr = pytest.importorskip("cost_basis_rejudge")

_EVIDENCE = {"stamp": "observed_zero", "days_full": 20, "days_zero_median": 20}


@pytest.fixture
def registry(tmp_path, monkeypatch):
    doc = {
        "EURUSD": {"median_spread_pts": 0.0},  # unstamped zero
        "GBPUSD": {"median_spread_pts": 50.0},  # the fixed-era 50
        "LISTY": {"median_spread_pts": 0.0, "_provenance": ["legacy"]},
        "NULLED": {"median_spread_pts": 0.0, "_provenance": None},
        "STUBBY": {"median_spread_pts": 0.0},
    }
    p = tmp_path / "universe.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(rus, "REGISTRY", p)
    monkeypatch.setattr(rus, "REPORT", tmp_path / "SPREAD_PROVENANCE.json")
    monkeypatch.setattr(rus, "TAPE_REPORT", tmp_path / "SPREAD_TAPE.json")
    observed = {"zero_spread": True, "zero_evidence": _EVIDENCE}
    probes = {
        "EURUSD": (0.0, "observed zero", observed),
        "GBPUSD": (0.0, "observed zero", observed),
        "LISTY": (0.0, "observed zero", observed),
        "NULLED": (0.0, "observed zero", observed),
        # a zero the tape did NOT prove (the probe forgot its evidence)
        "STUBBY": (0.0, "hand-made", {"zero_spread": False}),
    }
    monkeypatch.setattr(rus, "tape_spread", lambda sym: probes[sym])
    monkeypatch.setattr(
        rus,
        "load_tape",
        lambda write=True: {"status": "MEASURED", "source": "fusion_zero_m1_tape", "by_symbol": {}},
    )
    return p


def test_only_the_tapes_observed_zero_is_written_and_it_carries_its_evidence(registry):
    r = rus.run(apply=True, write=True, source="tape")
    doc = json.loads(registry.read_text("utf-8"))
    stamp = doc["EURUSD"]["_provenance"]["median_spread_pts"]
    assert stamp["source"] == "fusion_zero_m1_tape" and stamp["zero_spread"] is True
    assert stamp["zero_evidence"] == _EVIDENCE
    assert doc["GBPUSD"]["median_spread_pts"] == 0.0, "the fixed-era 50 corrected to the zero"
    assert doc["GBPUSD"]["_provenance"]["median_spread_pts"]["was"] == 50.0
    assert "STUBBY" in r["unmeasured"] and "_provenance" not in doc["STUBBY"]
    assert set(r["observed_zero_stamped"]) == {"EURUSD", "GBPUSD", "NULLED"}
    assert "STUBBY" in r["zero_unstamped"] and "LISTY" in r["zero_unstamped"]


def test_a_provenance_that_is_not_a_map_is_never_indexed_or_overwritten(registry):
    r = rus.run(apply=True, write=True, source="tape")
    doc = json.loads(registry.read_text("utf-8"))
    assert doc["LISTY"]["_provenance"] == ["legacy"], "somebody's record, left as it was"
    assert "not a map" in r["unmeasured"]["LISTY"]
    assert doc["NULLED"]["_provenance"]["median_spread_pts"]["zero_spread"] is True
    assert rus.is_observed_zero_stamp(doc["EURUSD"])
    assert not rus.is_observed_zero_stamp(doc["LISTY"])
    assert not rus.is_observed_zero_stamp({"_provenance": "a string"})


def test_a_zero_probe_never_divides_or_overrules_the_desks_own_fills(registry, monkeypatch):
    doc = json.loads(registry.read_text("utf-8"))
    doc["FILLED"] = {
        "median_spread_pts": 12.0,
        "_provenance": {"median_spread_pts": {"source": "realized_fills"}},
    }
    registry.write_text(json.dumps(doc), encoding="utf-8")
    probes = dict.fromkeys(
        doc, (0.0, "observed zero", {"zero_spread": True, "zero_evidence": _EVIDENCE})
    )
    monkeypatch.setattr(rus, "tape_spread", lambda sym: probes[sym])
    r = rus.run(apply=True, write=True, source="tape")
    assert "FILLED" in r["kept_realized_fills"]
    assert json.loads(registry.read_text("utf-8"))["FILLED"]["median_spread_pts"] == 12.0


# ------------------------------------------------------------------ the cost-basis re-judge


def _chart(path: Path, last: str) -> None:
    idx = pd.date_range(
        end=pd.Timestamp(last, tz="UTC") + pd.Timedelta(hours=20), periods=48, freq="1h"
    )
    pd.DataFrame({"close": range(48)}, index=idx).to_parquet(path)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    uni = tmp_path / "universe"
    uni.mkdir()
    reg = {
        "EURUSD": {
            "median_spread_pts": 0.0,
            "tick_size": 1e-5,
            "tick_value": 1.0,
            "contract_size": 1e5,
            "swap_long": -1.0,
            "swap_short": 0.5,
        },
        "XAUUSD": {
            "median_spread_pts": 5.0,
            "tick_size": 0.01,
            "tick_value": 1.0,
            "contract_size": 100.0,
            "swap_long": -2.0,
            "swap_short": 1.0,
        },
    }
    (uni / "universe.json").write_text(json.dumps(reg), encoding="utf-8")
    for sym in ("EURUSD", "XAUUSD"):
        _chart(uni / f"{sym}_H1.parquet", "2026-10-20")
    _chart(uni / "EURUSD_M5.parquet", "2026-10-20")
    index = {
        "EURUSD.carry.p=aa": "swap_cost|0",  # decided by the basis: queued
        "EURUSD@M5.orb.p=bb": "PASSED|1",  # a certificate on it: queued
        "EURUSD.carry.p=cc": "deflated_sharpe|0",  # not decided by it: rotation
        "XAUUSD.carry.p=dd": "swap_cost|0",
    }  # its basis did not move
    hyp = tmp_path / "hypotheses"
    hyp.mkdir()
    (hyp / "gate_verdict_index.json").write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setattr(cbr, "GATE_INDEX", hyp / "gate_verdict_index.json")
    monkeypatch.setattr(cbr, "PRIORITY_REMINT", hyp / "priority_remint.json")
    monkeypatch.setattr(cbr, "STATE", tmp_path / "cost_basis_state.json")
    monkeypatch.setattr(cbr, "REPORT", tmp_path / "COST_BASIS_REJUDGE.json")
    return uni


def _stamp_zero(uni: Path) -> None:
    reg = json.loads((uni / "universe.json").read_text("utf-8"))
    reg["EURUSD"]["_provenance"] = {
        "median_spread_pts": {
            "source": "fusion_zero_m1_tape",
            "zero_spread": True,
            "zero_evidence": _EVIDENCE,
        }
    }
    (uni / "universe.json").write_text(json.dumps(reg), encoding="utf-8")


def _move(uni: Path, sym: str, spread: float) -> None:
    reg = json.loads((uni / "universe.json").read_text("utf-8"))
    reg[sym]["median_spread_pts"] = spread
    (uni / "universe.json").write_text(json.dumps(reg), encoding="utf-8")


def _queue(desk_path: Path) -> dict:
    return json.loads((desk_path.parent / "hypotheses" / "priority_remint.json").read_text())


def test_the_fields_mirror_the_sealed_gates():
    eg = pytest.importorskip("scripts.external_gauntlet")
    assert tuple(eg.COST_BASIS_FIELDS) == cbr.COST_BASIS_FIELDS


def test_the_first_reading_is_a_baseline_and_queues_nothing(desk):
    r = cbr.run(universe=desk, gate=None)
    assert r["verdict"] == "BASELINE" and r["n_queued"] == 0
    assert not (desk.parent / "hypotheses" / "priority_remint.json").exists()


def test_a_moved_number_queues_what_the_basis_decided_after_the_cache_rolls(desk):
    from research.gate_policy import ATTESTATION

    cbr.run(universe=desk, gate=None)
    _move(desk, "EURUSD", 3.0)  # a cost NUMBER moves: the cached series is stale
    r = cbr.run(universe=desk, gate=None)
    assert r["changed"] == ["EURUSD"]
    assert r["n_queued"] == 2 and r["n_held_for_the_cache"] == 2 and r["n_released"] == 0
    assert not (desk.parent / "hypotheses" / "priority_remint.json").exists(), (
        "a held cell is not in the judge's queue: its cache would serve the old cost"
    )
    # the chart's data-day rolls: the cache key rolls, the new cost can be served -> released
    for name in ("EURUSD_H1.parquet", "EURUSD_M5.parquet"):
        _chart(desk / name, "2026-10-21")
    r = cbr.run(universe=desk, gate=None)
    assert r["n_released"] == 2 and r["n_held_for_the_cache"] == 0
    q = _queue(desk)
    assert q["attestation"] == ATTESTATION, "the judge reads the queue only under its attestation"
    assert q["cells"] == ["EURUSD.carry.p=aa", "EURUSD@M5.orb.p=bb"]
    assert q["stale_certificate_keys"] == [], "it never marks a certificate stale itself"
    # HOLD_DATA_DAYS later the cells leave the queue
    for name in ("EURUSD_H1.parquet", "EURUSD_M5.parquet"):
        _chart(desk / name, "2026-10-23")
    r = cbr.run(universe=desk, gate=None)
    assert r["n_dropped_after_hold"] == 2 and r["n_queued"] == 0 and _queue(desk)["cells"] == []


def test_another_producers_queue_is_kept(desk):
    from research.gate_policy import ATTESTATION

    cbr.run(universe=desk, gate=None)
    other = {
        "attestation": ATTESTATION,
        "cells": ["GBPUSD.x.p=zz"],
        "stale_certificate_keys": ["cert-1"],
    }
    (desk.parent / "hypotheses" / "priority_remint.json").write_text(json.dumps(other))
    _stamp_zero(desk)
    cbr.run(universe=desk, gate=None)
    for name in ("EURUSD_H1.parquet", "EURUSD_M5.parquet"):
        _chart(desk / name, "2026-10-21")
    cbr.run(universe=desk, gate=None)
    q = _queue(desk)
    assert "GBPUSD.x.p=zz" in q["cells"] and q["stale_certificate_keys"] == ["cert-1"]
    assert set(q["cost_basis_cells"]) == {"EURUSD.carry.p=aa", "EURUSD@M5.orb.p=bb"}


def test_an_unreadable_index_holds_the_change_until_it_reads(desk):
    cbr.run(universe=desk, gate=None)
    cbr.GATE_INDEX.write_text("{not json", encoding="utf-8")
    _stamp_zero(desk)
    r = cbr.run(universe=desk, gate=None)
    assert "UNMEASURED" in r["index"] and r["n_queued"] == 0
    cbr.GATE_INDEX.write_text(json.dumps({"EURUSD.carry.p=aa": "swap_cost|0"}))
    r = cbr.run(universe=desk, gate=None)
    assert r["n_queued"] == 1, "the change waited for the index; it was not forgotten"


def test_cell_ids_name_their_symbol_and_chart():
    assert cbr.sym_tf_of("XAUUSD@M5.carry.p=ab12") == ("XAUUSD", "M5")
    assert cbr.sym_tf_of("EURUSD.overnight_gap_decay.p=ab") == ("EURUSD", "H1")


def _gate(accept_zero: bool):
    """A stand-in for the sealed registry_cost_basis: positive spreads measured, a zero only
    when `accept_zero` (the v2 rule) and the stamp is there."""

    def fn(sym, rows):
        row = rows[sym]
        if row["median_spread_pts"] > 0:
            return {"measured": True}
        ok = accept_zero and cbr.zero_stamped(row)
        return {"measured": ok, "zero_spread": ok}

    return fn


def test_a_stamp_moves_no_cost_number_so_its_cells_are_released_at_once(desk):
    cbr.run(universe=desk, gate=_gate(True))
    _stamp_zero(desk)
    r = cbr.run(universe=desk, gate=_gate(True))
    assert r["changed"] == ["EURUSD"] and r["n_released"] == 2 and r["n_held_for_the_cache"] == 0
    assert set(_queue(desk)["cells"]) == {"EURUSD.carry.p=aa", "EURUSD@M5.orb.p=bb"}


def test_a_moved_cost_number_waits_for_the_cache(desk):
    cbr.run(universe=desk, gate=_gate(True))
    reg = json.loads((desk / "universe.json").read_text("utf-8"))
    reg["XAUUSD"]["median_spread_pts"] = 9.0
    (desk / "universe.json").write_text(json.dumps(reg), encoding="utf-8")
    r = cbr.run(universe=desk, gate=_gate(True))
    assert r["changed"] == ["XAUUSD"] and r["n_held_for_the_cache"] == 1


def test_a_resigned_rule_that_reads_the_same_numbers_differently_is_a_change(desk):
    _stamp_zero(desk)
    cbr.run(universe=desk, gate=_gate(False))  # the stamp is there; the old rule refuses it
    r = cbr.run(universe=desk, gate=_gate(False))
    assert r["changed"] == []
    r = cbr.run(universe=desk, gate=_gate(True))  # the v2 rule is signed: same rows, new verdict
    assert r["changed"] == ["EURUSD"] and r["n_released"] == 2


def test_an_unimportable_gate_never_reads_as_every_symbol_changing(desk):
    cbr.run(universe=desk, gate=_gate(True))
    r = cbr.run(universe=desk, gate=None)
    assert r["changed"] == [] and "UNMEASURED" in r["gate_view"]


# ---------------------------------------------------------------- v2.1 audit should-fixes


def test_a_gateless_reading_then_a_gated_one_marks_nothing_changed(desk):
    """The first reading had no gate keys (the sealed judge would not import); the next one
    has them. A gate key counts only when BOTH readings carry it."""
    cbr.run(universe=desk, gate=None)
    r = cbr.run(universe=desk, gate=_gate(True))
    assert r["changed"] == [] and r["n_queued"] == 0
    # once both carry it, a moved gate verdict IS a change
    _stamp_zero(desk)
    cbr.run(universe=desk, gate=_gate(False))
    r = cbr.run(universe=desk, gate=_gate(True))
    assert r["changed"] == ["EURUSD"]


def test_basis_changes_reads_gate_keys_only_when_both_sides_have_them():
    was = {"median_spread_pts": 0.0, "zero_stamp": False}
    now = {"median_spread_pts": 0.0, "zero_stamp": False, "gate_measured": True}
    assert cbr.basis_changes(was, now) == []
    assert cbr.basis_changes({**was, "gate_measured": False}, now) == ["gate_measured"]
    assert cbr.basis_changes(was, {**now, "zero_stamp": True}) == ["zero_stamp"]


def test_stamp_only_mode_stamps_the_zeros_and_moves_no_value(registry):
    r = rus.run(stamp_zeros_only=True, write=True, source="tape")
    doc = json.loads(registry.read_text("utf-8"))
    assert r["apply_mode"] == "stamp_observed_zeros"
    assert doc["GBPUSD"]["median_spread_pts"] == 50.0, "a value that would move is left alone"
    assert "_provenance" not in doc["GBPUSD"]
    stamp = doc["EURUSD"]["_provenance"]["median_spread_pts"]
    assert stamp["zero_spread"] is True and stamp["mode"] == "stamp_observed_zeros"
    assert stamp["zero_evidence"] == _EVIDENCE
    assert rus.is_observed_zero_stamp(doc["NULLED"])
    assert "_provenance" not in doc["STUBBY"], "an unproven zero is never stamped"
    assert set(r["observed_zero_stamped"]) == {"EURUSD", "NULLED"}
    # idempotent: a stamped zero is not re-stamped
    again = rus.run(stamp_zeros_only=True, write=True, source="tape")
    assert again["n_applied"] == 0


def test_the_widening_and_verified_modes_never_stamp_a_zero_to_zero(registry, tmp_path):
    rus.run(apply=True, widening_only=True, write=True, source="tape")
    doc = json.loads(registry.read_text("utf-8"))
    assert not rus.is_observed_zero_stamp(doc["EURUSD"])


def test_a_collectors_stub_write_replaces_the_observed_zero_stamp():
    """download_all_symbols writes `symbol_info.spread` through universe_registry.merge, which
    REPLACES the field's provenance entry: a stub 0 read before any tick cannot inherit the
    tape's observed-zero stamp, and a positive value cannot either."""
    from mt5desk.universe_registry import merge

    base = {"EURUSD": {"median_spread_pts": 0.0, "_provenance": {"median_spread_pts": {
        "source": "fusion_zero_m1_tape", "zero_spread": True, "zero_evidence": _EVIDENCE}}}}
    for stub in (0, 7):
        out = merge(base, {"EURUSD": {"median_spread_pts": stub}}, source="download_all_symbols")
        assert out["EURUSD"]["median_spread_pts"] == stub
        assert not rus.is_observed_zero_stamp(out["EURUSD"])
        assert out["EURUSD"]["_provenance"]["median_spread_pts"]["source"] == \
            "download_all_symbols"
    assert rus.is_observed_zero_stamp(base["EURUSD"]), "the base is never mutated"
    # a value the collector could not read is not WRITTEN: the old value keeps its own stamp
    kept = merge(base, {"EURUSD": {"median_spread_pts": None}}, source="download_all_symbols")
    assert kept["EURUSD"]["median_spread_pts"] == 0.0 and rus.is_observed_zero_stamp(kept["EURUSD"])
    # the auditor's condition, pinned at the writer: download_all_symbols writes the registry
    # through merge and its rows carry no `_provenance` of their own in code
    src = (_DESK / "scripts" / "download_all_symbols.py").read_text("utf-8")
    code = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
    assert "merge(_prior, universe" in code and "_provenance" not in code
