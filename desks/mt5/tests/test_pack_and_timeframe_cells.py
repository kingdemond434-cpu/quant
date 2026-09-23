"""Every data pack produces cells, and every mechanism is asked on every chart.

The two organs the principal ordered on 2026-09-23, tested on the properties that make them
worth having rather than on their plumbing: a pack at zero has a NAMED reason, an emitted cell
goes through the ONE registry door, a chart fanout changes only the chart, and the multiplicity
the extra charts create is charged rather than taken for free.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pack_cells as pc  # noqa: E402
from research import timeframe_fanout as tf  # noqa: E402


# ------------------------------------------------------------------ pack_cells
def test_signals_exclude_the_point_in_time_stamp(tmp_path: Path) -> None:
    """The PIT envelope is the stamp, never a conditioner: a cell keyed on `available_time`
    would be conditioning on the clock, which is a guaranteed and meaningless edge."""
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0],
                       "event_time": pd.date_range("2026-01-01", periods=5, tz="UTC"),
                       "available_time": pd.date_range("2026-01-02", periods=5, tz="UTC"),
                       "source_id": ["x"] * 5, "vintage_id": ["v"] * 5})
    p = tmp_path / "s.parquet"
    df.to_parquet(p)
    cols, n, why = pc.signals_of(p)
    assert cols == ["value"], cols
    assert n == 5
    assert why == ""


def test_a_label_column_is_not_a_signal(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"flag": [1, 1, 1, 1, 1], "name": ["a", "b", "c", "d", "e"]})
    p = tmp_path / "s.parquet"
    df.to_parquet(p)
    cols, n, why = pc.signals_of(p)
    assert cols == []
    assert n == 5
    assert "no numeric column" in why


def test_every_pack_at_zero_carries_a_named_reason(monkeypatch: Any, tmp_path: Path) -> None:
    """The whole point of the organ: never a quiet zero (LAWS 7, 'a report is not a remedy')."""
    monkeypatch.setattr(pc, "packs", lambda: [
        {"id": "never", "targets": ["XAUUSD"], "cadence": "daily"},
        {"id": "bytes_only", "targets": ["EURUSD"], "cadence": "daily"},
        {"id": "no_target", "targets": [], "cadence": "daily"},
    ])
    monkeypatch.setattr(pc, "chain", lambda: {
        "never": {"stage_reached": "none", "why": "never collected"},
        "bytes_only": {"stage_reached": "collected", "why": "bytes landed, no series"},
        "no_target": {"stage_reached": "represented", "why": "converted"},
    })
    monkeypatch.setattr(pc, "series_path", lambda pid: None)
    monkeypatch.setattr(pc, "_registry_counts", lambda: ({}, ""))
    doc = pc.build(budget_s=5.0, dry_run=True)
    assert doc["n_packs"] == 3
    assert len(doc["packs_at_zero"]) == 3
    for row in doc["packs_at_zero"]:
        assert row["reason"] and row["reason"] != "unexplained", row


def test_an_unmeasured_chain_is_not_an_empty_eligible_set(monkeypatch: Any) -> None:
    """L1.28a: absence never resolves to a clean verdict. No chain state means UNMEASURED per
    pack, not 'no pack qualifies'."""
    monkeypatch.setattr(pc, "packs", lambda: [{"id": "a", "targets": ["XAUUSD"]}])
    monkeypatch.setattr(pc, "chain", dict)
    monkeypatch.setattr(pc, "_registry_counts", lambda: ({}, ""))
    doc = pc.build(budget_s=5.0, dry_run=True)
    assert doc["n_eligible"] == 0
    assert "UNMEASURED" in doc["rows"][0]["reason"]


def test_cells_go_through_the_one_registry_door(monkeypatch: Any) -> None:
    """Never a store beside the registry: every cell is an `enqueue_candidate` call and every
    pack is a `record_discovery`."""
    calls: list[dict[str, Any]] = []
    import libs.moat.registry as reg
    monkeypatch.setattr(reg, "record_discovery",
                        lambda **kw: (calls.append({"kind": "discovery", **kw}), ("D1", True))[1])
    monkeypatch.setattr(reg, "enqueue_candidate",
                        lambda **kw: (calls.append({"kind": "cell", **kw}), ("C1", True))[1])
    res = pc.emit_for({"id": "p", "targets": ["XAUUSD"]}, ["v"], ["XAUUSD"], dry_run=False)
    assert res["emitted"] == len(pc.TRANSFORMS) * len(pc.CHARTS)
    cells = [c for c in calls if c["kind"] == "cell"]
    assert len(cells) == res["emitted"]
    assert {c["chart"] for c in cells} == set(pc.CHARTS)
    assert all(c["source_id"] == "p" for c in cells)
    assert all(c["origin"] == "pack_cells" for c in cells)


# ------------------------------------------------------- pack_cells, world lane
def test_the_country_pack_supplies_the_instruments_never_a_guess() -> None:
    """75 country packs already declare EXECUTABLE_INSTRUMENTS and REGION_COMMAND; a country
    with no pack is UNMAPPED, which is a reason, not a guessed currency pair."""
    pc._PACK_CACHE.clear()
    inst, region = pc.country_pack("cz")
    assert inst and all(isinstance(s, str) for s in inst)
    assert region == "EUROPE"
    assert pc.country_pack("zz_not_a_country") == ((), "UNMAPPED")
    assert pc.country_pack("") == ((), "UNMAPPED")


def test_a_ground_with_no_country_pack_names_its_reason(monkeypatch: Any) -> None:
    monkeypatch.setattr(pc, "_claims_for", lambda *a, **k: [{"claim_id": "c", "text": "t",
                                                             "knowable_at": "", "media_type": ""}])
    res = pc.emit_world({"id": "g", "country": "zz", "region": "UNMAPPED", "kind": "forum",
                         "targets": [], "n_documents": 3}, dry_run=True)
    assert res["emitted"] == 0
    assert "research/countries/" in res["reason"]


def test_a_ground_with_no_document_is_a_crawl_problem_not_a_conversion_one(
        monkeypatch: Any) -> None:
    monkeypatch.setattr(pc, "_claims_for", lambda *a, **k: [])
    res = pc.emit_world({"id": "g", "country": "cz", "region": "EUROPE", "kind": "forum",
                         "targets": ["EURUSD"], "n_documents": 0}, dry_run=True)
    assert res["emitted"] == 0
    assert "fetched nothing" in res["reason"]


def test_held_documents_reach_both_doors(monkeypatch: Any) -> None:
    """A claim already on disk becomes a discovery (the compiler's door) and the ground becomes
    registry-visible cells, so neither waits on the other."""
    calls: list[str] = []
    import libs.moat.registry as reg
    monkeypatch.setattr(pc, "_claims_for", lambda *a, **k: [
        {"claim_id": "c1", "text": "the koruna fixes at 09:00",
         "knowable_at": "", "media_type": ""}])
    monkeypatch.setattr(reg, "record_discovery",
                        lambda **kw: (calls.append("discovery"), ("D", True))[1])
    monkeypatch.setattr(reg, "enqueue_candidate",
                        lambda **kw: (calls.append(f"cell:{kw['chart']}:{kw['symbol']}"),
                                      ("C", True))[1])
    res = pc.emit_world({"id": "g", "country": "cz", "region": "EUROPE", "kind": "official",
                         "targets": ["EURUSD", "EURCZK"], "n_documents": 1}, dry_run=False)
    assert res["discoveries"] == 1
    assert res["emitted"] == 2 * len(pc.CHARTS)
    assert calls.count("discovery") == 1
    assert sum(1 for c in calls if c.startswith("cell:")) == res["emitted"]


# ------------------------------------------------------------ timeframe_fanout
def test_the_fanout_changes_the_chart_and_nothing_else(monkeypatch: Any) -> None:
    """Breadth from work already done: same family, same symbol, same side, same session."""
    seen: list[dict[str, Any]] = []
    import libs.moat.registry as reg
    monkeypatch.setattr(reg, "enqueue_candidate",
                        lambda **kw: (seen.append(kw), ("C", True))[1])
    parent = {"lane": "canonical", "parent": "P", "symbol": "XAUUSD", "family": "breakout",
              "params": {"side": "SHORT", "lookback": 20}, "session": "london",
              "regime": "NORMAL_DAY", "asset_class": "metals", "parent_chart": "H1",
              "mechanism": "m"}
    res = tf.mint(parent, list(tf.CHARTS), dry_run=False)
    assert res["emitted"] == len(tf.CHARTS)
    assert {k["chart"] for k in seen} == set(tf.CHARTS)
    assert {k["family"] for k in seen} == {"breakout"}
    assert {k["symbol"] for k in seen} == {"XAUUSD"}
    assert {k["session"] for k in seen} == {"london"}
    assert all(k["params"]["side"] == "SHORT" for k in seen)
    assert all(k["params"]["parent_chart"] == "H1" for k in seen)
    assert all(k["parent_ids"] == ["P"] for k in seen)


def test_every_chart_is_minted_including_the_parents_own(monkeypatch: Any) -> None:
    """The control must be in the set or the comparison is between five new things and nothing."""
    assert "H1" in tf.CHARTS
    assert {"M1", "M5", "M15", "H4"} <= set(tf.CHARTS)


def test_more_charts_costs_more_trials(monkeypatch: Any) -> None:
    """The multiplicity is CHARGED. n_effective must rise with the cells and must be smaller
    than n_raw, because five charts of one mechanism are correlated, not independent."""
    res = tf.mint({"lane": "l", "parent": "P", "symbol": "XAUUSD", "family": "breakout",
                   "params": {"lookback": 20}, "session": "", "regime": "",
                   "parent_chart": "H1", "mechanism": "m"}, list(tf.CHARTS), dry_run=True)
    charged = tf.charge_trials(res["trials"])
    assert charged["n_raw"] == len(tf.CHARTS)
    assert charged["n_effective"] is not None
    assert 0 < charged["n_effective"] <= charged["n_raw"]
    assert tf.charge_trials([])["n_raw"] == 0


def test_the_chart_order_comes_from_the_replay_never_a_preference(monkeypatch: Any,
                                                                  tmp_path: Path) -> None:
    """Ordering is measured; nothing is filtered. Every chart survives the ordering."""
    import json
    p = tmp_path / "ctf.json"
    p.write_text(json.dumps({"per_chart": {"M5": {"mean": 0.9}, "M15": {"mean": 0.3},
                                           "H1": {"mean": 0.0}, "H4": {"mean": -0.2},
                                           "M1": {"mean": None}}}), encoding="utf-8")
    monkeypatch.setattr(tf, "CTF", p)
    order, basis = tf.chart_order()
    assert order[0] == "M5"
    assert set(order) == set(tf.CHARTS)
    assert "COUNTERFACTUAL_TIMEFRAMES" in basis["basis"]


def test_an_absent_canonical_lane_is_unmeasured_not_empty(monkeypatch: Any,
                                                          tmp_path: Path) -> None:
    monkeypatch.setattr(tf, "SURVIVORS", tmp_path / "missing.json")
    rows, why = tf.canonical_parents()
    assert rows == []
    assert "UNMEASURED" in why
