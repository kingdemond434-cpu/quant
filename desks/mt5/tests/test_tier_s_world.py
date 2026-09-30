"""Tier S world group (layers 2, 3, 16, 18, 43): the joins and worlds the ledger said were missing.

  S02  one record per source joining data_registry x ingestion_ledger x vintage; acquisition
       predictions scored on the gate yield of the source's information class
  S03  the world model's own listed edge list classified; non-price nodes UNMEASURED by kind
  S16  the per-bar swap/rollover stress world in synthetic_regimes, joined per certificate
  S18  jurisdiction and regime on every evidence item; the graph persisted between passes
  S43  operations-research (dealer inventory) and motif labs on the bar stream
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import vintage  # noqa: E402
from libs.tiers import (  # noqa: E402
    bitemporal,
    data_os,
    graph_edges,
    science_labs,
    swap_world,
    theory,
    theory_context,
)

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


# ------------------------------------------------------------------------------------------ S02

REGISTRY = {
    "fred_macro": {"lifecycle": "CORE", "source": "FRED", "path": "data/lake/fred_*.parquet",
                   "series": ["DGS10", "M2SL"]},
    "cot": {"lifecycle": "CORE", "source": "CFTC"},
    "mt5_h1_universe": {"lifecycle": "INGESTED", "path": "data/universe/*_H1.parquet"},
    "gdelt": {"lifecycle": "DISCOVERED", "source": "GDELT 2.0"},
}
LEDGER = [
    {"at": "2026-09-29T00:00:00+00:00", "dataset": "axis:fred", "kind": "axis_series",
     "unit_id": "fred:DGS10", "pit": True, "disposition": "EXPLOITED",
     "downstream_state": "WORLD_MODEL_INPUT", "access_label": "OPEN_DATA",
     "path": "desks/mt5/data/axes/fred.json"},
    {"at": "2026-09-29T00:00:00+00:00", "dataset": "axis:cot", "kind": "axis_series",
     "unit_id": "cot:EUR", "pit": False, "disposition": "STRANDED",
     "path": "desks/mt5/data/axes/cot.json"},
    {"at": "2026-09-30T00:00:00+00:00", "dataset": "axis:cot", "kind": "axis_series",
     "unit_id": "cot:EUR", "pit": True, "disposition": "EXPLOITED"},       # latest row wins
    {"at": "2026-09-29T00:00:00+00:00", "dataset": "universe_bars", "kind": "universe_bars",
     "unit_id": "EURUSD_H1", "pit": True, "disposition": "EXPLOITED",
     "path": "desks/mt5/data/universe/EURUSD_H1.parquet"},
    {"at": "2026-09-29T00:00:00+00:00", "dataset": "axis:mystery", "kind": "axis_series",
     "unit_id": "mystery:x", "pit": False, "disposition": "PENDING"},
]


def _classify(fam: str) -> str:
    return {"cot_net_fade": "positioning", "macro_conditional": "macro"}.get(fam, "price_only")


def test_one_record_per_source_joins_the_three_ledgers(tmp_path: Path) -> None:
    vintage.record(tmp_path, "DGS10", {"2026-09-01": 4.1}, vintage="2026-09-02")
    vintage.record(tmp_path, "DGS10", {"2026-09-01": 4.2}, vintage="2026-09-03")
    vintage.record(tmp_path, "ORPHAN", {"2026-09-01": 1.0}, vintage="2026-09-02")
    ing = data_os.ingestion_by_dataset(LEDGER)
    assert ing["axis:cot"]["units"] == 1 and ing["axis:cot"]["pit_share"] == 1.0
    vint = data_os.vintage_series([tmp_path])
    yields = data_os.gate_yield([{"at": "2026-09-29T00:00:00+00:00", "family": "cot_net_fade",
                                  "passed": True}], _classify, NOW)
    doc = data_os.source_records(REGISTRY, ing, vint, yields)
    recs = {r["source"]: r for r in doc["records"]}
    fred = recs["fred_macro"]
    assert fred["joined"] == ["ingestion", "registry", "vintage"]
    assert {j["basis"] for j in fred["join"]} == {"leading_name_token", "declared_series"}
    assert fred["vintage"][0]["n_vintages"] == 2
    assert recs["cot"]["join"][0]["basis"] == "exact_name"
    assert recs["cot"]["gate_yield"]["yield"] == 1.0
    assert recs["mt5_h1_universe"]["join"][0]["basis"] == "declared_path"
    # every missing side is UNMEASURED with a reason, never an empty clean join
    assert recs["gdelt"]["ingestion_status"]["status"] == "UNMEASURED"
    assert recs["gdelt"]["vintage_status"]["status"] == "UNMEASURED"
    assert recs["ingested:mystery"]["registry"]["status"] == "UNMEASURED"
    assert recs["vintage:ORPHAN"]["registry"]["status"] == "UNMEASURED"
    assert doc["orphans"] == {"registry_only": ["gdelt"], "ingestion_only": ["axis:mystery"],
                              "vintage_only": ["ORPHAN"]}
    assert doc["fully_joined"] == 1
    assert recs["fred_macro"]["gate_yield"]["status"] == "UNMEASURED"   # no macro verdict


def test_gate_yield_is_windowed_per_class_and_never_a_fake_zero() -> None:
    old = (NOW - timedelta(days=90)).isoformat()
    rows = ([{"at": "2026-09-29T00:00:00+00:00", "family": "cot_net_fade", "passed": p}
             for p in (True, False, False, False)]
            + [{"at": old, "family": "macro_conditional", "passed": True}]
            + [{"family": "cot_net_fade", "passed": True}])
    y = data_os.gate_yield(rows, _classify, NOW)
    assert y["positioning"]["yield"] == 0.25 and y["positioning"]["verdicts"] == 4
    assert "macro" not in y, "a class with no verdict in the window has no yield at all"
    assert y["all"]["undated_rows"] == 1
    assert data_os.metric_now(y) == {"gate_yield:positioning": 0.25, "gate_yield:all": 0.25}


def test_acquisitions_are_scored_on_gate_yield_not_pit_share() -> None:
    legacy = bitemporal.Prediction(item="cot_tff", kind="dataset", ranker="evig",
                                   predicted_gain=0.1, cost_eur=0, cost_cpu_h=0.1,
                                   metric="pit_share", metric_before=0.4, at="x")
    fresh = bitemporal.Prediction(item="cot_disagg", kind="dataset", ranker="evig",
                                  predicted_gain=0.1, cost_eur=0, cost_cpu_h=0.1,
                                  metric="gate_yield:positioning", metric_before=None, at="x")
    unknown = bitemporal.Prediction(item="zzz", kind="thing", ranker="evig", predicted_gain=0.1,
                                    cost_eur=0, cost_cpu_h=0.1, metric="gate_yield:UNKNOWN",
                                    metric_before=None, at="x")
    preds = [legacy, fresh, unknown]
    moved = data_os.retarget(preds, {"gate_yield:positioning": 0.10, "gate_yield:all": 0.05})
    assert moved == {"retargeted": 1, "baseline_stamped": 3}
    assert legacy.metric == "gate_yield:positioning" and legacy.metric_before == 0.10
    assert unknown.metric == "gate_yield:all" and unknown.metric_before == 0.05
    now = {"gate_yield:positioning": 0.30, "gate_yield:all": 0.05}
    n = bitemporal.resolve(preds, {"cot_tff": NOW, "cot_disagg": NOW}, now, NOW.isoformat())
    assert n == 2 and legacy.realised_gain == pytest.approx(0.20)
    # a class that is UNMEASURED stays open with no baseline, never stamped with a zero
    p = bitemporal.Prediction(item="cot_x", kind="dataset", ranker="r", predicted_gain=0.1,
                              cost_eur=0, cost_cpu_h=0.1, metric="gate_yield:positioning",
                              metric_before=None, at="x")
    data_os.retarget([p], {})
    assert p.metric_before is None


def test_organ_data_os_publishes_the_source_records(monkeypatch: Any, tmp_path: Path) -> None:
    led = tmp_path / "ingestion_ledger.jsonl"
    led.write_text("\n".join(json.dumps(r) for r in LEDGER), "utf-8")
    reg = tmp_path / "data_registry.json"
    reg.write_text(json.dumps({"datasets": REGISTRY}), "utf-8")
    gates = tmp_path / "gates.jsonl"
    gates.write_text(json.dumps({"at": ts.NOW.isoformat(), "family": "cot_net_fade",
                                 "passed": True}) + "\n", "utf-8")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "DATA_ACQUISITION.json").write_text(json.dumps(
        {"ranking": [{"item": "cot_tff", "value": 0.2}]}), "utf-8")
    monkeypatch.setattr(ts, "INGESTION_LEDGER", led)
    monkeypatch.setattr(ts, "DATA_REGISTRY", reg)
    monkeypatch.setattr(ts, "GATE_LEDGER", gates)
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(ts, "HGRAPH", tmp_path / "none.jsonl")
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "acquisition.json").write_text(json.dumps({"predictions": [
        {"item": "cot_tff", "kind": "dataset", "ranker": "legacy", "predicted_gain": 0.1,
         "cost_eur": 0.0, "cost_cpu_h": 0.1, "metric": "pit_share", "metric_before": 0.4,
         "at": "2026-09-01T00:00:00+00:00"}]}), "utf-8")
    out = ts.organ_data_os()
    assert out["acquisition"]["scored_on"]["landed"] == "gate_yield"
    assert out["gate_yield"]["positioning"]["yield"] == 1.0
    assert out["metric"]["sources"] == out["sources"]["n_sources"] >= 5
    for top in out["acquisition"]["top"]:   # ranker rows (own metric) carry their class yield
        assert "info_class" in top and "class_gate_yield" in top
    saved = json.loads((tmp_path / "state" / "acquisition.json").read_text("utf-8"))
    legacy = [p for p in saved["predictions"] if p["ranker"] == "legacy"]
    assert legacy[0]["metric"] == "gate_yield:positioning", "pit_share rows move to gate yield"
    assert legacy[0]["metric_before"] == 1.0


# ------------------------------------------------------------------------------------------ S03

def _series(values: np.ndarray, start: str = "2026-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=idx)


def test_the_listed_edge_list_itself_is_classified() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1e-3, 3000)
    y = np.r_[0.0, 0.6 * x[:-1]] + rng.normal(0, 4e-4, 3000)
    noise = rng.normal(0, 1e-3, 3000)
    rets = {"EURUSD": _series(x), "GBPUSD": _series(y), "USDJPY": _series(noise)}
    causal = {"nodes": [{"id": "EURUSD", "kind": "mt5_instrument"},
                        {"id": "GBPUSD", "kind": "mt5_instrument"},
                        {"id": "USDJPY", "kind": "mt5_instrument"},
                        {"id": "cb:FED", "kind": "central_bank"}],
              "edges": [{"src": "EURUSD", "dst": "GBPUSD", "lag": 1, "direction": "opposite"},
                        {"src": "USDJPY", "dst": "GBPUSD", "lag": 1, "direction": "same"},
                        {"src": "cb:FED", "dst": "EURUSD", "lag": 1},
                        {"src": "EURUSD", "dst": "XTIUSD", "lag": 1}]}
    cross = {"edges": [{"driver": "EURUSD", "target": "GBPUSD", "lag": 1, "direction": "same",
                        "verdict": "EDGE"}]}
    listed = graph_edges.listed_edges(causal, cross)
    assert len(listed) == 5
    out = graph_edges.classify_listed(listed, rets)
    by = {(e["origin"], e["driver"], e["target"]): e for e in out["edges"]}
    ce = by[("cross_asset_graph", "EURUSD", "GBPUSD")]
    assert ce["class"] == "STABLE" and ce["agrees_with_listing"] is True
    flip = by[("world_causal_graph", "EURUSD", "GBPUSD")]
    assert flip["sign_flip"] is True and flip["agrees_with_listing"] is False
    assert by[("world_causal_graph", "USDJPY", "GBPUSD")]["class"] == "FALSE"
    fed = by[("world_causal_graph", "cb:FED", "EURUSD")]
    assert fed["class"] == "UNMEASURED" and "central_bank" in fed["why"]
    assert "no H1 bars" in by[("world_causal_graph", "EURUSD", "XTIUSD")]["why"]
    assert out["unmeasured_node_kinds"] == {"central_bank": 1}
    assert out["bonferroni_tests"] == 3 and out["contradicted"] >= 2


def test_listed_edges_join_on_timestamp_not_on_the_tail() -> None:
    rng = np.random.default_rng(4)
    x = rng.normal(0, 1e-3, 3000)
    y = np.r_[0.0, 0.6 * x[:-1]] + rng.normal(0, 4e-4, 3000)
    # the target series is the same hours shifted by a week: tail alignment would pair the
    # wrong bars; the timestamp join pairs the right ones and drops the rest
    ys = _series(y)
    ys = pd.concat([ys, _series(rng.normal(0, 1e-3, 168), "2026-05-06")])
    edges = graph_edges.listed_edges(None, {"edges": [
        {"driver": "EURUSD", "target": "GBPUSD", "lag": 1, "direction": "same"}]})
    out = graph_edges.classify_listed(edges, {"EURUSD": _series(x), "GBPUSD": ys})
    assert out["edges"][0]["class"] == "STABLE"
    assert out["edges"][0]["n_joined"] == 3000


def test_organ_world_science_carries_the_listed_graph(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(ts, "CAUSAL_GRAPH", tmp_path / "absent.json")
    monkeypatch.setattr(ts, "CROSS_ASSET_GRAPH", tmp_path / "absent2.json")
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "_returns_panel", lambda: ({}, {}, {}))
    out = ts.organ_world_and_science()
    assert out["listed_graph"]["status"] == "UNMEASURED"
    assert "neither" in out["listed_graph"]["why"]


# ------------------------------------------------------------------------------------------ S43

def test_operations_lab_finds_a_planted_inventory_release() -> None:
    rng = np.random.default_rng(5)
    n = 3000
    v = rng.uniform(50, 150, n)
    r = rng.normal(0, 1e-3, n)
    for t in range(200, n - 1):
        z = science_labs.inventory_z(r[: t + 1], v[: t + 1])[-1]
        if np.isfinite(z):
            r[t + 1] -= 6e-4 * z                      # dealers lay off accumulated flow
    hits = science_labs.operations_lab({"EURUSD": r}, {"EURUSD": v})
    assert hits and hits[0]["lab"] == "operations" and hits[0]["corr"] < 0
    expr = ts.xsci_expression(hits[0])
    assert expr is not None and expr.startswith("neg(") and ag.is_valid(ag.from_str(expr))
    assert science_labs.operations_lab({"EURUSD": rng.normal(0, 1e-3, n)},
                                       {"EURUSD": v}) == [], "white noise has no inventory"


def test_motif_lab_finds_a_planted_run_reversal_and_states_it_exactly() -> None:
    rng = np.random.default_rng(6)
    r = rng.normal(0, 1e-3, 4000)
    for t in range(3, len(r)):
        if r[t - 3] > 0 and r[t - 2] > 0 and r[t - 1] > 0:
            r[t] = -abs(r[t]) * 1.5                   # after UUU the next bar falls
    hits = science_labs.motif_lab({"XAUUSD": r})
    uuu = [h for h in hits if h["motif"] == "UUU"]
    assert uuu and uuu[0]["follow"] == "reverses"
    expr = ts.xsci_expression(uuu[0])
    assert expr == "neg(add(min(sign(ret), 3), abs(min(sign(ret), 3))))"
    assert ag.is_valid(ag.from_str(expr))
    # the grammar indicator fires on exactly the bars the lab counted
    s = pd.Series(np.sign(r))
    ind = s.rolling(3).min()
    grammar = (ind + ind.abs()).to_numpy() > 0
    assert np.array_equal(grammar, science_labs.run_indicator(r, 3, True) > 0)
    for up in (True, False):
        for follow in ("continues", "reverses"):
            for n in science_labs.MOTIF_LENGTHS:
                e = science_labs.expression({"lab": "motif", "length": n, "up": up,
                                             "follow": follow})
                assert e is not None and ag.is_valid(ag.from_str(e)), e


def test_the_two_labs_reach_the_expression_queue(monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "_may_hypothesise", lambda s: True)
    labs = {"operations": [{"lab": "operations", "symbols": ["EURUSD"], "corr": 0.1}],
            "motif": [{"lab": "motif", "symbols": ["USDJPY"], "length": 5, "up": False,
                       "follow": "continues"}]}
    rows, exprs = ts.science_rows(labs, [])
    assert rows == []
    assert {e["generator"] for e in exprs} == {"cross_science:operations", "cross_science:motif"}
    assert all(ag.is_valid(ag.from_str(e["expr"])) for e in exprs)


# ------------------------------------------------------------------------------------------ S16

def test_stressed_nights_charge_both_triple_days() -> None:
    wed = pd.Timestamp("2026-09-30 20:00")                # a Wednesday
    assert swap_world.stressed_nights(wed, wed + pd.Timedelta(hours=2)) == 3
    fri = pd.Timestamp("2026-10-02 20:00")
    assert swap_world.stressed_nights(fri, fri + pd.Timedelta(hours=2)) == 3
    assert swap_world.stressed_nights(fri, fri + pd.Timedelta(hours=26)) == 4
    assert swap_world.baseline_nights(fri, fri + pd.Timedelta(hours=2)) == 1.0
    assert swap_world.stressed_nights(wed, wed) == 0


def _trade(entry: str, exit_: str, r: float = 0.5) -> SimpleNamespace:
    return SimpleNamespace(entry_time=pd.Timestamp(entry), exit_time=pd.Timestamp(exit_),
                           entry=100.0, stop=99.0, r_multiple=r, units=1.0)


def test_swap_world_only_costs_and_leaves_intraday_trades_alone() -> None:
    trades = [_trade("2026-09-29 10:00", "2026-09-29 14:00"),        # intraday: untouched
              _trade("2026-09-30 20:00", "2026-10-01 02:00"),        # Wednesday night
              _trade("2026-09-29 21:00", "2026-09-29 23:00")]        # rollover-bar legs
    rs, touched = swap_world.stress_r(trades, swap_per_lot=10.0, spread_per_lot=4.0,
                                      contract=100.0)
    assert rs[0] == 0.5 and touched == 2
    # Wednesday: 3 stressed nights x3 - 3 baseline = 6 nights x 10 / 100 / 1.0 stop
    assert rs[1] == pytest.approx(0.5 - 0.6)
    assert all(a <= b for a, b in zip(rs, [t.r_multiple for t in trades], strict=True))


def test_synthetic_regimes_carries_the_swap_world() -> None:
    from research import synthetic_regimes as sr
    assert swap_world.NAME in sr.SCENARIOS
    assert sr.FLAG_RULES["dies_on_swap_rollover"] == (swap_world.NAME, "sign")
    idx = pd.date_range("2026-09-28", periods=100, freq="h", tz="UTC")
    bars = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    w = sr.SCENARIOS[swap_world.NAME][1](bars, "EURUSD", 0, "x")
    assert w.swap_stress and w.applied == 8                  # 21:00 and 22:00 on four days

    class Costs:
        spread_per_lot, contract_oz = 4.0, 100.0

        def __init__(self, swap: float) -> None:
            self.swap_per_lot_per_night = swap

        @classmethod
        def from_symbol(cls, meta: dict[str, Any], mult: float = 1.0) -> Costs:
            return cls(float(meta.get("swap", 0.0)))

    def run_backtest(df: Any, sigs: Any, costs: Any) -> Any:
        return SimpleNamespace(trades=[_trade("2026-09-30 20:00", "2026-10-01 02:00")])

    eng = (run_backtest, Costs)
    assert sr._swap_replay(w, [1], eng, {"swap": 10.0}, "EURUSD") == [pytest.approx(-0.1)]
    assert "zero-swap" in str(sr._swap_replay(w, [1], eng, {}, "EURUSD"))
    assert "engine" in str(sr._swap_replay(w, [1], None, {"swap": 1.0}, "EURUSD"))


def test_organ_worlds_joins_the_swap_world_per_certificate(monkeypatch: Any,
                                                          tmp_path: Path) -> None:
    doc = {"scenarios": [{"name": "spread_x5"}, {"name": swap_world.NAME}],
           "results": [{"symbol": "EURUSD", "family": "f", "flags": ["dies_on_swap_rollover"],
                        "scenarios": {swap_world.NAME: {"status": "MEASURED",
                                                        "expectancy": -0.1,
                                                        "delta_expectancy": -0.3,
                                                        "applied": 12}}},
                       {"symbol": "GBPUSD", "family": "f", "flags": [],
                        "scenarios": {swap_world.NAME: {"status": "UNMEASURED",
                                                        "why": "no swap terms"}}}]}
    monkeypatch.setattr(ts, "_read", lambda p: doc if "SYNTHETIC" in str(p) else {})
    monkeypatch.setattr(ts, "survivors", lambda: {
        "a": {"shadow_spec": {"symbol": "EURUSD", "family": "f"}},
        "b": {"shadow_spec": {"symbol": "GBPUSD", "family": "f"}},
        "c": {"shadow_spec": {"symbol": "USDJPY", "family": "f"}}})
    monkeypatch.setattr(ts, "STATE", tmp_path)
    out = ts.organ_worlds()
    assert out["swap_world"]["by_status"] == {"MEASURED": 1, "UNMEASURED": 2}
    assert out["swap_world"]["dies_on_swap_rollover"] == 1
    assert out["metric"]["swap_world_measured_share"] == pytest.approx(1 / 3)
    doc["scenarios"] = [{"name": "spread_x5"}]
    old = ts.organ_worlds()
    assert old["swap_world"]["by_status"] == {"UNMEASURED": 3}


# ------------------------------------------------------------------------------------------ S18

@pytest.mark.parametrize("sym,want", [("EURUSD", "EU+US"), ("XAUUSD", "US"), ("JP225", "JP"),
                                      ("GER40", "DE"), ("USDJPY", "JP+US"), ("", "UNMEASURED")])
def test_jurisdiction_of_an_instrument(sym: str, want: str) -> None:
    assert theory_context.jurisdiction_of(sym) == want


def test_jurisdiction_falls_back_to_the_profit_currency() -> None:
    assert theory_context.jurisdiction_of("SOMECFD", {"currency_profit": "GBP"}) == "GB"
    assert theory_context.jurisdiction_of("SOMECFD", {}) == "UNMEASURED"


def test_regime_context_and_context_dependence() -> None:
    assert theory_context.declared_regime("EURUSD.x.vol_filter=high") == "vol_filter=high"
    assert theory_context.declared_regime("EURUSD.plain") is None
    rng = np.random.default_rng(1)
    calm = 100 * np.exp(np.cumsum(rng.normal(0, 1e-4, 1500)))
    wild = np.r_[calm, calm[-1] * np.exp(np.cumsum(rng.normal(0, 1e-2, 300)))]
    assert theory_context.vol_regime(wild) == "vol_high"
    assert theory_context.vol_regime(calm[:100]) == "UNMEASURED"
    g = theory.TheoryGraph()
    t = g.theory(theory.Mechanism(cause="c", family="f"))
    for i in range(12):
        theory_context.add(t, experiment=f"jp{i}", supports=True, source="forward",
                           jurisdiction="JP+US", regime="vol_high")
        theory_context.add(t, experiment=f"eu{i}", supports=False, source="forward",
                           jurisdiction="EU+US", regime="vol_high")
    rep = theory_context.context_report(g)[t.mechanism.mid]
    assert rep["by_jurisdiction"]["JP+US"]["status"] == "SUPPORTED"
    assert rep["by_jurisdiction"]["EU+US"]["status"] == "REFUTED"
    assert rep["context_dependent"] == ["jurisdiction"]


def test_the_graph_persists_between_passes(tmp_path: Path) -> None:
    path = tmp_path / "theory_graph.json"
    m = theory.Mechanism(cause="c", falsifier="f", family="fam")
    g1 = theory.TheoryGraph()
    theory_context.add(g1.theory(m), experiment="forward:retired", supports=False,
                       source="forward", jurisdiction="EU+US", regime="vol_low")
    theory_context.add(g1.theory(m), experiment="bt:1", supports=True, source="backtest")
    r1 = theory_context.merge_persisted(g1, path, "t1")
    assert r1["passes"] == 1 and r1["carried"] == 0
    # pass 2: the retired forward clock is gone from the ledgers; the graph keeps its evidence
    g2 = theory.TheoryGraph()
    theory_context.add(g2.theory(m), experiment="bt:1", supports=True, source="backtest")
    r2 = theory_context.merge_persisted(g2, path, "t2")
    assert r2["passes"] == 2 and r2["carried"] == 1
    t = g2.theories[m.mid]
    assert t.contra == theory.EVIDENCE_WEIGHT["forward"] and t.support == 1.0
    carried = [e for e in t.evidence if e.get("carried")]
    assert carried[0]["jurisdiction"] == "EU+US" and carried[0]["regime"] == "vol_low"
    # a theory absent from this pass entirely is rebuilt from its stored mechanism
    g3 = theory.TheoryGraph()
    r3 = theory_context.merge_persisted(g3, path, "t3")
    assert m.mid in g3.theories and r3["carried"] == 2
    traj = theory_context.trajectory(path, m.mid)
    assert [h["at"] for h in traj] == ["t1", "t2", "t3"]


def test_organ_theory_writes_context_and_persists(monkeypatch: Any, tmp_path: Path) -> None:
    gates = tmp_path / "gates.jsonl"
    gates.write_text("\n".join(json.dumps({"cell": f"EURUSD.fam{i}", "family": "fam",
                                           "sym": "EURUSD", "passed": i % 2 == 0})
                               for i in range(6)), "utf-8")
    monkeypatch.setattr(ts, "GATE_LEDGER", gates)
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "THEORY_GRAPH", tmp_path / "theory_graph.json")
    monkeypatch.setattr(ts, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(ts, "survivors", dict)
    monkeypatch.setattr(ts, "registry", dict)
    monkeypatch.setattr(ts, "live_rows", list)
    monkeypatch.setattr(ts, "shadow_rows", dict)
    monkeypatch.setattr(ts, "REPORTS", tmp_path)
    out = ts.organ_theory()
    assert out["persisted"]["passes"] == 1
    ctx = out["theories"][0]["context"]
    assert set(ctx["by_jurisdiction"]) == {"EU+US"}
    assert set(ctx["by_regime"]) == {"full_sample"}
    assert (tmp_path / "theory_graph.json").exists()
    again = ts.organ_theory()
    assert again["persisted"]["passes"] == 2 and again["persisted"]["carried"] == 0
