"""The hourly world-causal-graph organ: on an empty box it writes the seeded graph and says
UNMEASURED; with bars it measures the chains it can reach through the lake, admits a planted
link, emits the conditioning hints the state builder reads, charges every cell before measuring
any, reads the deep-forest claims defensively, and keeps one edge per pair across passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_discovery as hd  # noqa: E402
from research import world_causal_graph as w  # noqa: E402

from libs.research import causal_graph as cg  # noqa: E402

UNIVERSE = {s: {"asset_class": "Forex" if len(s) == 6 and s[:3] != "XAU" else "Metals",
                "currency_profit": "USD", "swap_long": -1.0, "swap_short": 0.5}
            for s in ("XAUUSD", "XAGUSD", "AUDUSD", "AUDJPY", "EURUSD", "USDJPY")}


def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps(UNIVERSE), "utf-8")
    monkeypatch.setattr(w, "UNI", uni)
    monkeypatch.setattr(w, "UNIVERSE_JSON", uni / "universe.json")
    monkeypatch.setattr(w, "GRAPH", tmp_path / "data" / "world_causal_graph.json")
    monkeypatch.setattr(w, "REPORT", tmp_path / "reports" / "WORLD_CAUSAL_GRAPH.json")
    monkeypatch.setattr(w, "CLAIMS", tmp_path / "data" / "deep_forest_claims.jsonl")
    monkeypatch.setattr(w, "CROSS", tmp_path / "reports" / "CROSS_ASSET_GRAPH.json")
    cot = tmp_path / "data" / "cot"
    monkeypatch.setattr(w, "COT_SOURCES", ((cot, "noncomm_positions_long_all",
                                            "noncomm_positions_short_all"),))
    return uni


def _bars(uni: Path, sym: str, ret: np.ndarray, start: str = "2024-01-01") -> None:
    idx = pd.date_range(start, periods=ret.size, freq="h", tz="UTC", name="time")
    close = 100.0 * np.exp(np.cumsum(ret))
    df = pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                       "close": close, "tick_volume": 100, "spread": 5}, index=idx)
    df.to_parquet(uni / f"{sym}_H1.parquet")


def test_an_empty_box_writes_the_seeded_graph_and_says_unmeasured(tmp_path, monkeypatch,
                                                                    capsys) -> None:
    _isolate(tmp_path, monkeypatch)
    rep = w.run(budget_s=5.0)
    assert rep["status"] == "UNMEASURED"
    assert "_H1.parquet" in rep["why"]
    assert rep["edges_measured"] == 0 and rep["edges_admitted"] == 0
    assert rep["chains_seeded"] >= 10 and rep["chains_measured"] == 0
    assert rep["counts"]["multiplicity_charged"] == 0
    assert w.GRAPH.exists() and w.REPORT.exists()
    g = cg.CausalGraph.load(w.GRAPH)
    assert g.chain_status()["china_physical_gold"]["seeded"]
    assert g.counts()["plausible_unmeasured"] > 20
    assert {n.id for n in g.instrument_nodes()} <= set(UNIVERSE)
    # every hint row the state builder would read is absent, not fabricated
    assert rep["conditioning_hints"] == {}
    # the organ is a zero-exit organ on an empty box, and prints the yield line
    monkeypatch.setattr(sys, "argv", ["world_causal_graph.py", "--budget-s", "5"])
    assert w.main() == 0
    out = capsys.readouterr().out
    assert "WORLD CAUSAL GRAPH  UNMEASURED" in out
    yline = next(ln for ln in out.splitlines() if ln.startswith("YIELD "))
    got = json.loads(yline[len("YIELD "):])
    assert set(got) == {"edges_measured", "edges_admitted", "paths_new", "discovered"}
    # an hour that learned nothing yields nothing: the candidate count is not a yield
    assert got["discovered"] == 0
    assert set(got) & set(hd.YIELD_KEYS) == {"discovered"}
    assert hd.yield_of(rep) == {"discovered": 0}


def test_a_planted_link_in_the_lake_is_admitted_and_becomes_a_conditioning_hint(
        tmp_path, monkeypatch) -> None:
    uni = _isolate(tmp_path, monkeypatch)
    rng = np.random.default_rng(4)
    n = 4_000
    gold = 0.004 * rng.standard_normal(n)
    silver = 0.006 * rng.standard_normal(n)
    silver[1:] += 0.6 * gold[:-1]                  # gold leads silver by one hour
    _bars(uni, "XAUUSD", gold)
    _bars(uni, "XAGUSD", silver)
    _bars(uni, "AUDUSD", 0.003 * rng.standard_normal(n))
    _bars(uni, "AUDJPY", 0.003 * rng.standard_normal(n))
    rep = w.run(budget_s=120.0)
    assert rep["status"] == "OK"
    assert rep["edges_measured"] >= 2 and rep["edges_admitted"] >= 1
    e = next(r for r in rep["admitted_edges"]
             if r["src"] == "commodity:gold" and r["dst"] == "commodity:silver")
    assert e["lag"] == 1 and e["clock"] == "H1" and e["direction"] == "same"
    assert e["measured_via"] == ["XAUUSD", "XAGUSD"]
    assert e["prior_direction"] == "same" and e["plausibility"] == 0.8
    # the null pair between the aussie legs is recorded, not admitted
    aud = next(r for r in rep["recorded_not_admitted"]
               if r["src"] == "currency:AUD" and r["dst"] == "AUDJPY")
    assert "includes zero" in aud["reason"]
    # THE ROW THE STATE BUILDER READS
    hints = rep["conditioning_hints"]["XAGUSD"]
    h = next(r for r in hints if r["src"] == "commodity:gold")
    assert h["lag"] == 1 and h["clock"] == "H1" and h["decay_cls"] == "bar_H1"
    assert h["half_life_s"] == 3600.0 and h["weight_at_one_cadence"] == pytest.approx(0.5)
    assert h["order"] == 1 and h["direction"] == "same"
    assert "XAUUSD" not in rep["conditioning_hints"]    # nothing admitted leads gold
    # every cell was charged before anything was measured: all edges faced the same bar
    bars = {r["n_tests"] for r in rep["admitted_edges"] + rep["recorded_not_admitted"]}
    assert len(bars) == 1 and bars == {rep["counts"]["multiplicity_charged"]}
    assert rep["chains_measured"] >= 1 and rep["chains"]["metals_complex"]["admitted"]
    assert rep["paths"]                                 # second-order chains into instruments
    # what the hour was WORTH: a first pass discovers the edge, a second one re-measuring the
    # same bars discovers nothing and says so rather than counting itself busy again
    assert rep["edges_admitted_new"] >= 1 and rep["discovered"] >= 1
    again = w.run(budget_s=120.0)
    assert again["edges_admitted"] >= 1 and again["discovered"] == 0
    assert hd.yield_of(again) == {"discovered": 0}


def test_passes_keep_one_edge_per_pair_and_the_ledger_never_shrinks(tmp_path,
                                                                     monkeypatch) -> None:
    uni = _isolate(tmp_path, monkeypatch)
    rng = np.random.default_rng(8)
    n = 2_500
    _bars(uni, "XAUUSD", 0.004 * rng.standard_normal(n))
    _bars(uni, "XAGUSD", 0.006 * rng.standard_normal(n))
    first = w.run(budget_s=60.0)
    charged = first["counts"]["multiplicity_charged"]
    assert charged == cg.MAX_LAG * first["measurable"]
    second = w.run(budget_s=60.0)
    assert second["counts"]["multiplicity_charged"] == charged
    assert second["edges_measured"] == first["edges_measured"]
    g = cg.CausalGraph.load(w.GRAPH)
    pairs = [(e.src, e.dst) for e in g.edges.values() if e.status != cg.STRUCTURAL]
    assert len(pairs) == len(set(pairs))
    assert g.counts()["edges"] == first["counts"]["edges"]
    # --symbol names a Fusion instrument, and the world edges are measured THROUGH it: a scope
    # of XAUUSD must reach commodity:gold, not only the edges spelled as Fusion symbols
    scoped = w.run(budget_s=60.0, symbols=["XAUUSD"])
    assert scoped["measurable"] >= 1
    assert any(r["src"] == "commodity:gold" for r in
               scoped["admitted_edges"] + scoped["recorded_not_admitted"])
    away = w.run(budget_s=60.0, symbols=["EURUSD"])
    assert away["measurable"] == 0 and away["status"] == "UNMEASURED"
    assert "scope" in away["why"]


def test_deep_forest_claims_are_read_defensively_and_placed_by_class(tmp_path,
                                                                     monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    rows = [
        {"claim": "gold leads silver", "instruments": {"analogues": ["XAUUSD", "XAGUSD"]},
         "mechanism_class": "lead_lag", "channel": "direct", "horizon": ["daily"],
         "claim_hash": "abc", "evidence_grade": "A", "available_time": "2026-09-01T00:00:00Z"},
        {"claim": "crowded gold longs", "instruments": {"analogues": ["XAUUSD"]},
         "mechanism_class": "positioning", "channel": "direct", "horizon": ["weekly"],
         "claim_hash": "def"},
        {"claim": "ecb hikes", "instruments": {"analogues": ["EURUSD"]},
         "mechanism_class": "policy", "channel": "indirect", "horizon": ["intraday"],
         "claim_hash": "ghi"},
        {"claim": "a story about nothing the graph can place",
         "instruments": {"analogues": ["EURUSD"]}, "mechanism_class": "seasonal",
         "claim_hash": "jkl"},
        {"claim": "not in the universe", "instruments": {"analogues": ["USDTRY"]},
         "mechanism_class": "positioning"},
    ]
    text = "\n".join(json.dumps(r) for r in rows) + "\nnot json at all\n[1, 2]\n"
    w.CLAIMS.parent.mkdir(parents=True, exist_ok=True)
    w.CLAIMS.write_text(text, "utf-8")
    universe = {s: cg.Node(s, cg.MT5) for s in UNIVERSE}
    g = cg.seed_priors(cg.CausalGraph(), universe)
    edges, unmapped = w.claim_candidates(w._read_jsonl(w.CLAIMS), set(UNIVERSE), g)
    keys = {(e.src, e.dst) for e in edges}
    assert ("XAUUSD", "XAGUSD") in keys and ("XAGUSD", "XAUUSD") in keys
    assert ("positioning:COT_gold", "XAUUSD") in keys
    assert ("cb:ECB", "EURUSD") in keys and ("cb:FED", "EURUSD") in keys   # both legs' banks
    assert unmapped == {"seasonal": 1, "positioning": 1}
    pair = next(e for e in edges if (e.src, e.dst) == ("XAUUSD", "XAGUSD"))
    assert pair.clock == "D1" and pair.decay_cls == "bar_D1" and pair.plausibility == 0.4
    assert pair.evidence["prior_source"] == "deep_forest_claims"
    assert pair.evidence["prior_claim_hash"] == "abc"
    cot = next(e for e in edges if e.src == "positioning:COT_gold")
    assert cot.clock == "W1" and cot.decay_cls == "cot"
    # and the run reports what it read, without bars to measure it against
    rep = w.run(budget_s=5.0)
    assert rep["claims"]["rows_read"] == 5 and rep["claims"]["edges_from_claims"] == 5
    assert rep["claims"]["unmapped_by_class"] == {"seasonal": 1, "positioning": 1}
    assert "instruments.analogues" in rep["claims"]["fields_consumed"]


def test_positioning_edges_use_the_feature_store_availability_convention(tmp_path,
                                                                          monkeypatch) -> None:
    uni = _isolate(tmp_path, monkeypatch)
    rng = np.random.default_rng(12)
    n_weeks = 160
    hours = n_weeks * 7 * 24
    _bars(uni, "XAUUSD", 0.003 * rng.standard_normal(hours), start="2023-01-02")
    cot_dir = w.COT_SOURCES[0][0]
    cot_dir.mkdir(parents=True)
    tuesdays = pd.date_range("2023-01-03", periods=n_weeks, freq="7D", tz="UTC")
    net = np.cumsum(rng.standard_normal(n_weeks)) * 1000 + 50_000
    pd.DataFrame({"report_date": tuesdays, "contract_market_name": "GOLD",
                  "noncomm_positions_long_all": net + 20_000,
                  "noncomm_positions_short_all": np.full(n_weeks, 20_000.0)}
                 ).to_parquet(cot_dir / "gold.parquet")
    z = w._cot_z("gold")
    assert z is not None and z.index[0].weekday() == 4 and z.index[0].hour == 21
    rep = w.run(budget_s=60.0)
    e = next(r for r in rep["admitted_edges"] + rep["recorded_not_admitted"]
             if r["src"] == "positioning:COT_gold")
    assert e["clock"] == "W1" and e["decay_cls"] == "cot" and e["n"] >= w.MIN_REPORTS
    assert e["measured_via"] == ["gold", "XAUUSD"]
    assert rep["chains"]["cot_gold_reversal"]["measured"]


def test_cross_asset_graph_edges_are_consumed_as_candidates(tmp_path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    doc = {"edges": [{"driver": "XAUUSD", "target": "EURUSD", "verdict": "NO_EDGE", "lag": 4,
                      "t": -3.8, "plausibility": "STATISTICAL", "direction": "opposite"},
                     {"driver": "USDJPY", "target": "AUDJPY", "verdict": "EDGE", "lag": 1,
                      "t": 4.2, "plausibility": "CAUSAL_ROLE", "role": "USD"},
                     {"driver": "NOPE", "target": "AUDJPY"}]}
    edges = w.cross_asset_candidates(doc, set(UNIVERSE))
    assert [(e.src, e.dst, e.plausibility) for e in edges] == [
        ("XAUUSD", "EURUSD", 0.2), ("USDJPY", "AUDJPY", 0.5)]
    assert edges[1].evidence["prior_lead_lag"]["verdict"] == "EDGE"
    w.CROSS.parent.mkdir(parents=True, exist_ok=True)
    w.CROSS.write_text(json.dumps(doc), "utf-8")
    rep = w.run(budget_s=5.0)
    assert rep["cross_asset_graph_edges"] == 2
    g = cg.CausalGraph.load(w.GRAPH)
    assert g.edge("USDJPY", "AUDJPY", 1) is not None
    assert g.edge("USDJPY", "AUDJPY", 1).status == cg.PLAUSIBLE_UNMEASURED
