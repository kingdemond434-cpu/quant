"""The world causal graph conditions every admitted edge on its target's admitted parents and
PUBLISHES which survive (Tier-1 audit G7). The admission itself is unchanged.

Planted in the lake: EURUSD drives USDJPY one hour later and AUDJPY two hours later, so the
pairwise test admits USDJPY -> AUDJPY (a common-driver confound) beside the genuine
EURUSD -> AUDJPY. After conditioning, the report names the first as FAILS and the second as
SURVIVES, and neither status moves.
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

from libs.research import causal_graph as cg  # noqa: E402
from research import world_causal_graph as w  # noqa: E402

UNIVERSE = {s: {"asset_class": "Forex", "currency_profit": "USD", "swap_long": -1.0,
                "swap_short": 0.5} for s in ("EURUSD", "USDJPY", "AUDJPY", "GBPUSD")}


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


def _bars(uni: Path, sym: str, ret: np.ndarray) -> None:
    idx = pd.date_range("2024-01-01", periods=ret.size, freq="h", tz="UTC", name="time")
    close = 100.0 * np.exp(np.cumsum(ret))
    pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999, "close": close,
                  "tick_volume": 100, "spread": 5}, index=idx).to_parquet(
        uni / f"{sym}_H1.parquet")


def test_a_common_driver_edge_is_published_as_failing_conditioning(tmp_path, monkeypatch
                                                                    ) -> None:
    uni = _isolate(tmp_path, monkeypatch)
    rng = np.random.default_rng(11)
    n = 5_000
    z = 0.004 * rng.standard_normal(n)                     # EURUSD, the common driver
    x = 0.002 * rng.standard_normal(n)
    y = 0.002 * rng.standard_normal(n)
    x[1:] += 0.7 * z[:-1]                                  # USDJPY follows EURUSD by one hour
    y[2:] += 0.7 * z[:-2]                                  # AUDJPY follows EURUSD by two
    _bars(uni, "EURUSD", z)
    _bars(uni, "USDJPY", x)
    _bars(uni, "AUDJPY", y)
    _bars(uni, "GBPUSD", 0.003 * rng.standard_normal(n))
    # The cross-asset screen hands the graph both pairs as candidates between MT5 nodes.
    w.CROSS.parent.mkdir(parents=True, exist_ok=True)
    w.CROSS.write_text(json.dumps({"edges": [
        {"driver": "EURUSD", "target": "AUDJPY", "lag": 2, "plausibility": "CAUSAL_ROLE"},
        {"driver": "USDJPY", "target": "AUDJPY", "lag": 1, "plausibility": "CAUSAL_ROLE"},
    ]}), "utf-8")
    w.run(budget_s=180.0)
    rep = w.run(budget_s=180.0)                            # every parent admitted is now known
    assert rep["status"] == "OK"
    rows = {(r["src"], r["dst"]): r for r in rep["admitted_edges"]}
    assert ("EURUSD", "AUDJPY") in rows and ("USDJPY", "AUDJPY") in rows, rows.keys()
    spurious, direct = rows[("USDJPY", "AUDJPY")], rows[("EURUSD", "AUDJPY")]
    # Pairwise, both are ADMITTED -- that admission is the graph's rule and it did not move.
    assert spurious["status"] == cg.ADMITTED and direct["status"] == cg.ADMITTED
    # Conditioned on the other admitted parent of AUDJPY, the confound FAILS and the cause holds.
    assert spurious["conditional"]["status"] == "FAILS", spurious["conditional"]
    assert {p["src"] for p in spurious["conditional"]["parents"]} == {"EURUSD"}
    assert spurious["conditional"]["parents"][0]["lag"] == direct["lag"]
    assert direct["conditional"]["status"] == "SURVIVES", direct["conditional"]
    cond = rep["conditioning"]
    assert "USDJPY->AUDJPY@1" in cond["edges_failing"]
    assert f"EURUSD->AUDJPY@{direct['lag']}" in cond["edges_surviving"]
    assert cond["edges_conditioned"] >= 2
    # The persisted graph carries the same column, so a later reader sees it too.
    g = cg.CausalGraph.load(w.GRAPH)
    e = g.measured_edge("USDJPY", "AUDJPY")
    assert e is not None and e.evidence["conditional"]["status"] == "FAILS"


def test_an_edge_with_no_other_admitted_parent_is_published_unconditioned(tmp_path,
                                                                         monkeypatch) -> None:
    uni = _isolate(tmp_path, monkeypatch)
    rng = np.random.default_rng(12)
    n = 5_000
    z = 0.004 * rng.standard_normal(n)
    y = 0.002 * rng.standard_normal(n)
    y[1:] += 0.7 * z[:-1]
    _bars(uni, "EURUSD", z)
    _bars(uni, "AUDJPY", y)
    w.CROSS.parent.mkdir(parents=True, exist_ok=True)
    w.CROSS.write_text(json.dumps({"edges": [
        {"driver": "EURUSD", "target": "AUDJPY", "lag": 1, "plausibility": "CAUSAL_ROLE"}]}),
        "utf-8")
    rep = w.run(budget_s=120.0)
    row = next(r for r in rep["admitted_edges"] if (r["src"], r["dst"]) == ("EURUSD", "AUDJPY"))
    assert row["conditional"]["status"] == "UNCONDITIONED"
    assert "no admitted parent" in row["conditional"]["why"]
    assert rep["conditioning"]["edges_unconditioned"] >= 1
    assert rep["conditioning"]["edges_failing"] == []


def test_admitted_parents_excludes_the_edge_itself_and_the_unadmitted() -> None:
    g = cg.CausalGraph()
    for nid in ("a", "b", "c", "y"):
        g.add_node(cg.Node(id=nid, kind="currency"))
    g.add_edge(cg.Edge(src="a", dst="y", lag=1, status=cg.ADMITTED, measured_at="t"))
    g.add_edge(cg.Edge(src="b", dst="y", lag=2, status=cg.RECORDED_NOT_ADMITTED,
                       measured_at="t"))
    g.add_edge(cg.Edge(src="c", dst="y", lag=3, status=cg.ADMITTED, measured_at="t"))
    probe = cg.Edge(src="a", dst="y", lag=1, status=cg.ADMITTED, measured_at="t")
    assert [(p.src, p.lag) for p in w.admitted_parents(g, probe)] == [("c", 3)]
