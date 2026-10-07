"""Follow-ups to #169 (claim_selection + metric_fence), each pinned in the direction that matters:

1. the claim charge reaches the DSR family term as max(campaign, family, claim), never lower;
2. k_eff is measured from the claim lineage and published (UNMEASURED when there are no cells);
3. the breadth units reach alpha_breadth, the coverage tensor and the Tier-1 scorecard;
4. every compiled candidate carries `claim_family` (discovery_compiler children inherit it);
5. a DERIVABLE impossible metric is repaired, and `fence_row` keeps its signature;
6. a declared `claim_selection_trials` is charged as declared, never less;
7. `register_grid` raises on a malformed grid instead of silently registering nothing.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import claim_selection as cs  # noqa: E402
from libs.research import experiment_ledger as el  # noqa: E402
from libs.research import metric_fence as mf  # noqa: E402
from libs.research import trial_ledger as T  # noqa: E402

VIDEO = ("PRIOR: converted from a public video whose reported Sharpe 1.87 was the MAXIMUM of ~200 "
         "searched variations with no multiplicity charge.")


@pytest.fixture
def ledger(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "claim_families.json"
    monkeypatch.setattr(cs, "LEDGER", path)
    monkeypatch.setattr(cs, "BREADTH_REPORT", tmp_path / "CLAIM_BREADTH.json")
    cs._INDEX_CACHE.clear()
    return path


# ------------------------------------------------------------------ 6. declared trials
@pytest.mark.parametrize("declared", [300, "300", 300.0, "~300", "1,300"])
def test_a_declared_search_is_charged_as_declared_without_any_sentence(declared) -> None:
    row = {"source": "miner:forum", "mechanism": "a gap fades by the London open",
           "claim_selection_trials": declared, "symbol": "EURUSD", "family": "gap"}
    assert cs.stamp(row)
    want = 1300 if declared == "1,300" else 300
    assert row["claim_selection_trials"] == want and row["claim_family"].startswith("claim:")


def test_a_declaration_is_never_charged_less_than_the_words() -> None:
    low = {"source": "miner:v", "mechanism_note": VIDEO, "claim_selection_trials": 50}
    high = {"source": "miner:v", "mechanism_note": VIDEO, "claims_searched": 900}
    assert cs.stamp(low) and low["claim_selection_trials"] == 200       # the words win
    assert cs.stamp(high) and high["claim_selection_trials"] == 900     # the declaration wins
    assert low["claim_family"] == high["claim_family"]                  # one claim, one family


def test_a_declared_only_grid_stays_one_family_across_per_cell_titles() -> None:
    rows = [{"source": "miner:p", "mechanism": "one shared mechanism", "title": f"cell {i}",
             "claim_selection_trials": 40} for i in range(5)]
    assert cs.stamp_all(rows) == 5
    assert len({r["claim_family"] for r in rows}) == 1


def test_the_trial_ledger_reads_a_declared_alias_and_a_string() -> None:
    t = T.trial_from_record({"family": "f", "claims_searched": "250"})
    assert t.selection_trials == 250
    assert T.trial_from_record({"family": "f", "claim_selection_trials": "nonsense"}) \
        .selection_trials == 0


def test_no_declaration_and_no_words_stamps_nothing() -> None:
    row = {"source": "miner:x", "mechanism": "carry", "claim_selection_trials": None}
    assert not cs.stamp(row) and "claim_family" not in row


# ------------------------------------------------------------------ 2. k_eff
def test_k_eff_is_the_participation_ratio_of_breadth_unit_sizes() -> None:
    claim = [{"source": "miner:v", "mechanism_note": VIDEO, "genome_id": f"v{i}"}
             for i in range(8)]
    plain = [{"genome_id": f"p{i}"} for i in range(8)]
    cs.stamp_all(claim)
    b = cs.breadth(claim + plain)
    assert b["breadth_units"] == 9
    assert b["k_eff"] == pytest.approx(16 ** 2 / (8 ** 2 + 8), abs=1e-3)
    assert b["k_eff"] <= b["breadth_units"]
    assert cs.breadth([{"genome_id": f"p{i}"} for i in range(6)])["k_eff"] == 6.0


def test_no_cells_is_unmeasured_never_zero(ledger) -> None:
    b = cs.breadth([])
    assert b["k_eff"] is None and b["k_eff_status"] == "UNMEASURED"
    doc = cs.publish_breadth(b)
    assert doc["status"] == "UNMEASURED" and doc["k_eff"] is None and doc["cells"] is None
    (ledger.parent / "CLAIM_BREADTH.json").unlink()
    gone = cs.read_breadth()
    assert gone["status"] == "UNMEASURED" and gone["k_eff"] is None and "absent" in gone["why"]


def test_published_breadth_round_trips(ledger) -> None:
    rows = [{"source": "miner:v", "mechanism_note": VIDEO, "genome_id": f"v{i}"}
            for i in range(4)] + [{"genome_id": "p"}]
    cs.stamp_all(rows)
    cs.publish_breadth(cs.breadth(rows), lifetime_selection_trials=200)
    doc = cs.read_breadth()
    assert (doc["status"], doc["cells"], doc["breadth_units"]) == ("MEASURED", 5, 2)
    assert doc["k_eff"] == pytest.approx(25 / 17, abs=1e-3)
    assert doc["selection_trials_in_docket"] == 200


# ------------------------------------------------------------------ 7. register_grid
@pytest.mark.parametrize("grid", [None, "abc", {"symbol": "EURUSD"}, [], 7])
def test_register_grid_raises_on_a_grid_that_is_not_a_grid(ledger, grid) -> None:
    with pytest.raises(cs.MalformedGrid):
        cs.register_grid(grid)
    assert not ledger.exists()


def test_register_grid_raises_on_a_non_mapping_row(ledger) -> None:
    good = {"symbol": "EURUSD", "family": "f", "params": {}, "mechanism": VIDEO, "source": "v"}
    with pytest.raises(cs.MalformedGrid, match="not mappings"):
        cs.register_grid([good, "row"])


def test_register_grid_raises_on_an_unkeyable_or_unsearched_grid(ledger) -> None:
    with pytest.raises(cs.MalformedGrid, match="genome_id"):
        cs.register_grid([{"mechanism": VIDEO, "source": "v"}])
    with pytest.raises(cs.MalformedGrid, match="searched claim"):
        cs.register_grid([{"symbol": "EURUSD", "family": "f", "params": {},
                           "mechanism": "carry", "source": "v"}])
    assert not ledger.exists()


def test_register_grid_still_registers_a_good_grid(ledger) -> None:
    grid = [{"symbol": s, "family": "htf_anchor_trend", "params": {"m": m},
             "source": "video_anchor_exit", "mechanism": VIDEO}
            for s in ("EURUSD", "XAUUSD") for m in (3, 4)]
    out = cs.register_grid(grid)
    (fam,) = out["claim_families"].values()
    assert fam == {"grid_cells": 4, "selection_trials": 200}


# ------------------------------------------------------------------ 1. the DSR family charge
def _register(ledger_path: Path) -> str:
    grid = [{"symbol": "EURUSD", "family": "htf_anchor_trend", "params": {"m": m},
             "source": "video_anchor_exit", "mechanism": VIDEO} for m in (3, 4)]
    out = cs.register_grid(grid)
    (fid,) = out["claim_families"]
    return fid


def test_claim_charge_reads_the_row_the_ledger_and_the_genome(ledger) -> None:
    fid = _register(ledger)
    gid = sorted(cs.lineage_index())[0]
    assert cs.claim_charge({"mechanism_note": VIDEO, "source": "miner:video_anchor_exit"}) == 200
    assert cs.claim_charge({"claim_family": fid}) == 200
    assert cs.claim_charge({"genome_id": gid}) == 200        # a judged cell, stamp long gone
    assert cs.claim_charge({"genome_id": "nobody", "mechanism": "carry"}) == 0


def test_family_floor_raises_the_strategy_family_never_lowers_it(ledger, monkeypatch) -> None:
    fid = _register(ledger)
    monkeypatch.setattr(el, "_graph_counts", lambda: (10, {"htf_anchor_trend": 10,
                                                           "carry": 900}))
    monkeypatch.setattr(el, "_proposer_counts", lambda: (0, {}))
    monkeypatch.setattr(el, "_mass_screen_counts", lambda: (0, {}))
    monkeypatch.setattr(el, "_prereg_counts", lambda: 0)
    doc = el.lifetime(write=False)
    assert doc["by_family"]["htf_anchor_trend"] == 200       # max(10, claim 200)
    assert doc["by_family"]["carry"] == 900                  # untouched
    assert doc["by_family"][fid] == 200
    assert doc["lifetime_trials"] == 10 + 200                # the union is unchanged
    assert doc["claim_trials"] == {fid: 200}
    assert doc["family_claim_floor"] == {"htf_anchor_trend": 200}
    n, basis = el.family_charge(50, "htf_anchor_trend", fid, doc=doc)
    assert n == 200 and "claim" in basis
    assert el.family_charge(5000, "htf_anchor_trend", fid, doc=doc)[0] == 5000
    assert el.family_charge(50, "carry", None, doc=doc)[0] == 900


def test_claim_campaign_only_ever_raises_and_never_writes(ledger, tmp_path,
                                                          monkeypatch) -> None:
    _register(ledger)
    out = tmp_path / "EXPERIMENT_LEDGER.json"
    monkeypatch.setattr(el, "OUT", out)
    cell = {"sym": "EURUSD", "family": "htf_anchor_trend", "params": {"m": 3}}
    assert el.claim_campaign(50, cell) == 200                # via the genome lineage
    assert el.claim_campaign(5000, cell) == 5000             # never below the campaign
    assert el.claim_campaign(50, {"sym": "GBPUSD", "family": "carry", "params": {}}) == 50
    assert not out.exists()                                  # the judge's read writes nothing
    out.write_text(json.dumps({"family_claim_floor": {"carry": 333}}), "utf-8")
    assert el.claim_campaign(50, {"sym": "GBPUSD", "family": "carry", "params": {}}) == 333


def test_the_dsr_patch_for_the_sealed_judge_is_a_call_site_change_only() -> None:
    """The judge is sealed and untouched; the patch beside it names the provider exactly."""
    gauntlet = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert "claim_campaign" not in gauntlet
    assert "claim_campaign" in inspect.getsource(el)
    assert inspect.signature(el.claim_campaign).parameters.keys() == {"campaign", "cell"}


# ------------------------------------------------------------------ 5. repair, signature
def test_fence_row_signature_is_stable() -> None:
    assert list(inspect.signature(mf.fence_row).parameters) == ["row"]
    assert mf.fence_row({"win_pct": 2281.0, "trades": 2966.0})       # still judges as given


@pytest.mark.parametrize(("row", "key", "want"), [
    ({"win_pct": 2281.0, "trades": 2966.0}, "win_pct", 100 * 2281 / 2966),
    ({"win_rate": 150.0, "wins": 30, "trades": 40}, "win_rate", 75.0),
    ({"pf": -1.5, "gross_profit": 300.0, "gross_loss": -200.0}, "pf", 1.5),
    ({"trades": 100, "metrics": {"win_pct": 64.0 * 10}}, None, None),
])
def test_a_derivable_metric_is_repaired_and_then_passes(row, key, want) -> None:
    fixed, notes = mf.repair_row(row)
    if key is None:                               # 640 > 100 trades: not derivable, untouched
        assert notes == [] and mf.fence_row(fixed)
        return
    assert fixed[key] == pytest.approx(want, abs=1e-3) and notes
    assert mf.fence_row(fixed) == []
    assert row[key] != fixed[key]                 # the input is never mutated


def test_a_nested_block_borrows_the_parent_trade_count() -> None:
    fixed, notes = mf.repair_row({"trades": 200, "metrics": {"win_pct": 120}})
    assert fixed["metrics"]["win_pct"] == 60.0 and notes[0].startswith("metrics.")


def test_what_no_arithmetic_recovers_is_still_refused() -> None:
    for row in ({"max_dd_pct": 140.0}, {"sharpe": 40.0}, {"trades": -3},
                {"win_pct": 2281.0}, {"win_pct": 2281.5, "trades": 2966}):
        fixed, notes = mf.repair_row(row)
        assert notes == [] and mf.fence_row(fixed), row


def test_the_tally_counts_repairs_beside_refusals() -> None:
    t = mf.FenceTally()
    t.add("s", [])
    t.repair("s", ["win_rate_derived:win_pct=2281->76.9 (count_in_rate_field/trades)"])
    d = t.to_dict()
    assert (d["checked"], d["refused"], d["repaired"]) == (1, 0, 1)
    assert d["by_repair"] == {"win_rate_derived": 1}


# ------------------------------------------------------------------ 3. consumers
def test_the_scorecard_carries_research_breadth_beside_its_fourteen_rows(tmp_path,
                                                                        monkeypatch) -> None:
    import tier1_scorecard as sc
    monkeypatch.setattr(sc, "CLAIM_BREADTH", tmp_path / "CLAIM_BREADTH.json")
    assert sc._research_breadth()["status"] == "UNMEASURED"
    (tmp_path / "CLAIM_BREADTH.json").write_text(json.dumps(
        {"status": "MEASURED", "k_eff": 3.5, "breadth_units": 9, "cells": 40,
         "generated_utc": "2026-10-01T00:00:00+00:00"}), "utf-8")
    rb = sc._research_breadth()
    assert (rb["status"], rb["k_eff"], rb["breadth_units"]) == ("MEASURED", 3.5, 9.0)
    assert len(sc.SPEC) == 14


def test_alpha_breadth_and_the_tensor_read_it_unmeasured_when_absent(ledger) -> None:
    import alpha_breadth as ab
    import coverage_tensor as ct
    for doc in (ab.research_breadth(), ct._research_breadth()):
        assert doc["status"] == "UNMEASURED"
    rows = [{"source": "miner:v", "mechanism_note": VIDEO, "genome_id": "a"}, {"genome_id": "b"}]
    cs.stamp_all(rows)
    cs.publish_breadth(cs.breadth(rows))
    a, c = ab.research_breadth(), ct._research_breadth()
    assert a["breadth_units"] == c["breadth_units"] == 2 and a["headline_unchanged"] is True


# ------------------------------------------------------------------ 4. discovery_compiler
def test_discovery_children_carry_their_parents_claim_family() -> None:
    import discovery_compiler as dc
    searched = dc._spec_from_row({"symbol": "EURUSD", "family": "f", "mechanism": VIDEO,
                                  "source": "miner:v"})
    plain = dc._spec_from_row({"symbol": "EURUSD", "family": "f", "mechanism": "carry"})
    assert searched["claim_family"].startswith("claim:")
    assert searched["claim_selection_trials"] == 200
    assert plain["claim_family"] is None
    child = {"family": "f", "symbol": "GBPUSD", "params": {}, "chart": "M15"}
    row = dc._donation_row(child, searched)
    assert row["claim_family"] == searched["claim_family"]
    assert row["claim_selection_trials"] == 200
    assert dc._donation_row(child, plain)["claim_family"] is None
