"""COST_SURFACES: measured cells from real fills, UNMEASURED without them, spread prior fallback."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import cost_surfaces as cs  # noqa: E402

UNIVERSE = {"EURGBP": {"tick_size": 1e-05, "tick_value": 1.0, "median_spread_pts": 9.0},
            "USDZAR": {"tick_size": 1e-05, "tick_value": 0.05, "median_spread_pts": 300.0}}
PRIOR = {"symbols": {"EURGBP": {"pooled_median_spread_pts": 9.0, "hours": {
    "8": {"status": "MEASURED", "p50": 12.0}, "9": {"status": "MEASURED", "p50": 14.0},
    "2": {"status": "UNMEASURED"}}}}}


def _fill(i: int, status: str = "FILLED", **kw) -> dict:
    row = {"symbol": "EURGBP", "hour": 9, "lots": 0.1, "stop_frac": 0.002, "direction": -1,
           "order_type": "market", "status": status, "ticket": 1000 + i,
           "spread_points_at_decision": 10.0 + i, "slip_points": 1.0 * i, "slip_r": 0.01 * i,
           "latency_decision_to_send_ms": 40.0, "latency_send_to_ack_ms": 10.0,
           "markout_5m_r": -0.05}
    row.update(kw)
    return row


def _deal(i: int) -> dict:
    return {"symbol": "EURGBP", "time": "2026-09-16T09:30:00+00:00", "volume": 0.1,
            "entry_price": 0.85651, "sl": 0.85751, "commission": -0.5, "swap": -0.25,
            "entry_order": 1000 + i}


def _build(corpus=None, ledger=None) -> dict:
    return cs.build(corpus=[_fill(i) for i in range(3)] if corpus is None else corpus,
                    ledger=[_deal(i) for i in range(3)] if ledger is None else ledger,
                    prior=PRIOR, universe=UNIVERSE)


def test_exact_cell_is_measured_from_real_fills() -> None:
    doc = _build()
    key = "EURGBP|london|all|all|short|market"
    cell = doc["levels"]["exact"][key]
    t = cell["terms"]
    assert t["spread_points"] == {"status": "MEASURED", "n": 3, "value": 11.0, "mean": 11.0,
                                  "p90": 12.0}
    assert t["slippage_points"]["value"] == 1.0
    assert t["latency_ms"]["value"] == 50.0
    assert t["adverse_selection_r"]["value"] == 0.05
    assert t["fill_probability"] == {"status": "MEASURED", "n": 3, "value": 1.0}
    # risk = 0.001/1e-5 * 1.0 * 0.1 = 10 account units; commission 0.5 -> 0.05 R paid
    assert t["commission_r"]["value"] == 0.05
    assert t["swap_r"]["value"] == 0.025
    assert doc["status"] == "MEASURED"


def test_no_fills_is_unmeasured_never_zero() -> None:
    doc = _build(corpus=[], ledger=[])
    assert doc["status"] == "UNMEASURED"
    assert doc["levels"]["exact"] == {}
    got = cs.cost_for("USDZAR", hour=1, lots=1.0, direction=1, order_type="stop", surface=doc)
    for term, v in got["terms"].items():
        if term == "spread_points":
            continue
        assert v == {"status": "UNMEASURED", "level": "none"}, term
    # USDZAR has no measured hour: the prior falls to the pooled registry spread.
    assert got["terms"]["spread_points"]["status"] == "PRIOR"
    assert got["terms"]["spread_points"]["value"] == 300.0


def test_thin_cell_is_unmeasured_with_its_n() -> None:
    doc = _build(corpus=[_fill(0), _fill(1)], ledger=[])
    t = doc["levels"]["exact"]["EURGBP|london|all|all|short|market"]["terms"]
    assert t["spread_points"] == {"status": "UNMEASURED", "n": 2}
    assert "value" not in t["slippage_r"]


def test_cost_for_backs_off_then_falls_to_the_spread_x_hour_prior() -> None:
    doc = _build()
    # A limit order in the same session: exact and order-type levels miss, session level hits.
    got = cs.cost_for("EURGBP", hour=9, lots=0.1, direction=-1, order_type="limit",
                      surface=doc)
    assert got["terms"]["spread_points"]["level"] == "instrument_session"
    # A session with no fills: spread comes from the prior, the rest are UNMEASURED.
    got = cs.cost_for("EURGBP", hour=13, direction=1, surface=doc)
    assert got["terms"]["spread_points"]["level"] == "instrument"
    got = cs.cost_for("EURGBP", hour=13, surface=_build(corpus=[], ledger=[]))
    sp = got["terms"]["spread_points"]
    assert sp["status"] == "PRIOR" and sp["value"] == 9.0      # no NY hours -> pooled
    got = cs.cost_for("EURGBP", hour=9, surface=_build(corpus=[], ledger=[]))
    assert got["terms"]["spread_points"]["value"] == 13.0       # london median of 12, 14


def test_fill_probability_and_rejects_count_unfilled_intents() -> None:
    corpus = [_fill(0), _fill(1, status="UNFILLED"), _fill(2, status="UNFILLED"),
              _fill(3, status="REJECTED", rejected=True)]
    doc = _build(corpus=corpus, ledger=[])
    t = doc["levels"]["instrument"]["EURGBP|*|*|*|*|*"]["terms"]
    assert t["fill_probability"]["value"] == round(1 / 3, 4)
    assert t["reject_rate"]["value"] == 0.25
    # Unfilled intents never contribute a zero slippage.
    assert t["slippage_points"] == {"status": "UNMEASURED", "n": 1}


def test_buckets_are_derived_from_traded_sizes() -> None:
    corpus = [_fill(i, lots=0.01 * (i + 1)) for i in range(9)]
    doc = _build(corpus=corpus, ledger=[])
    edges = doc["size_bucket_edges_lots"]
    assert len(edges) == 2 and edges[0] < edges[1]
    assert {k.split("|")[2] for k in doc["levels"]["exact"]} == {"low", "mid", "high"}


def test_publish_only_records_consumers_not_adopted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cs, "CORPUS", tmp_path / "none.jsonl")
    monkeypatch.setattr(cs, "LEDGER", tmp_path / "none2.jsonl")
    out = tmp_path / "COST_SURFACES.json"
    assert cs.main(["--once", "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["schema"] == cs.SCHEMA
    assert doc["adoption"] and all(c["status"] == "NOT_ADOPTED" for c in doc["adoption"])
    assert any("external_gauntlet" in c["consumer"] for c in doc["adoption"])


def test_wired_as_an_hourly_execution_leg() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("cost_surfaces", lambda: _producer(' in src
    assert '"cost_surfaces", "research/cost_surfaces.py"' in src
    sys.path.insert(0, str(DESK.parent.parent))
    from libs.research import layers
    assert layers.LEG_LAYER["cost_surfaces"] == "execution"
    assert cs.OUT.name == "COST_SURFACES.json" and cs.OUT.parent.name == "reports"
