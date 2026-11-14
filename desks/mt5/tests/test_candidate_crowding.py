"""`candidate_crowding` (H6, the candidate half): a crowding mark on every docket row and the
desk's own measured decay, as a two-sided report-only expected-edge multiplier.

  0. seats parse through regional nesting; literature is dated or UNMEASURED, never "unpublished";
  1. retail narrative velocity reads acceleration; CFTC extremeness never reads an unknowable row;
  2. the publication split measures decay with an interval, and says UNMEASURED when it cannot;
  3. the edge trend is two-sided and shrunk by its own precision;
  4. the multiplier prefers measurement over the borrowed prior, and is clamped both ways;
  5. a whole pass marks every row, credits original mechanisms, and its marks round-trip;
  6. the leg, layer and graph are wired.
All inputs are synthetic.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import candidate_crowding as C  # noqa: E402

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


def test_seats_parse_through_regional_nesting_and_literature_is_dated_or_unmeasured():
    assert C._seat("miner:asia:collective2") == "collective2"
    assert C._seat("miner:standing_questions:Q6") == "standing_questions"
    assert C._seat("miner:video_anchor_exit") == "video_anchor_exit"
    v, lit = C.literature_component("turn_of_month", NOW)
    assert lit["status"] == C.MEASURED and lit["year"] == 1987 and v == pytest.approx(1.0)
    v2, lit2 = C.literature_component("session_range_breakout", NOW)
    assert lit2["kind"] == "book" and v2 == pytest.approx(0.8)
    v3, lit3 = C.literature_component("never_heard_of_it", NOW)
    assert v3 is None and lit3["status"] == C.UNMEASURED


def test_retail_velocity_and_cot_never_reads_the_future(tmp_path):
    rows = ([{"family": "hot", "source": "miner:youtube",
              "first_seen": (NOW - timedelta(days=d)).isoformat()} for d in range(0, 30, 2)]
            + [{"family": "cold", "source": "miner:reddit",
                "first_seen": (NOW - timedelta(days=d)).isoformat()} for d in range(31, 120, 3)]
            + [{"family": "internal", "source": "miner:discovery_compiler",
                "first_seen": NOW.isoformat()}])
    vel = C.retail_velocity(rows, NOW)
    assert vel["hot"] > 0.9 and vel["cold"] < 0.1 and "internal" not in vel

    start = NOW - timedelta(days=3 * 365)
    pts = [{"symbol": "XAUUSD", "knowable_at": (start + timedelta(weeks=i)).date().isoformat(),
            "net_pct_oi": 0.1 + 0.001 * i} for i in range(150)]
    # a row stamped knowable tomorrow is the most extreme of all -- and must not be read
    pts.append({"symbol": "XAUUSD", "knowable_at": (NOW + timedelta(days=1)).date().isoformat(),
                "net_pct_oi": -0.9})
    p = tmp_path / "cot.json"
    p.write_text(json.dumps({"rows": pts}))
    cot = C.cot_concentration(p, NOW)
    assert cot["XAUUSD"]["percentile"] == pytest.approx(1.0)
    assert cot["XAUUSD"]["extremeness"] == pytest.approx(1.0)
    assert cot["XAUUSD"]["crowd_side"] == "long"


def test_publication_split_measures_with_an_interval_or_says_unmeasured():
    rng = np.random.default_rng(0)
    t_pre = [datetime(2015, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(200)]
    t_post = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(200)]
    pnl = list(rng.normal(0.004, 0.001, 200)) + list(rng.normal(0.001, 0.001, 200))
    got = C.split_decay(pnl, t_pre + t_post, datetime(2018, 1, 1, tzinfo=UTC))
    assert got["status"] == C.MEASURED
    assert got["decay"] == pytest.approx(0.75, abs=0.05)
    assert got["ci90"][0] < got["decay"] < got["ci90"][1]
    none_pre = C.split_decay(pnl[200:], t_post, datetime(2018, 1, 1, tzinfo=UTC))
    assert none_pre["status"] == "UNMEASURED_NO_PRE_PUBLICATION_BARS"


def test_edge_trend_is_two_sided_and_precision_shrunk():
    rng = np.random.default_rng(1)
    times, grow, fade = [], [], []
    for k, yr in enumerate(range(2018, 2026)):
        for i in range(200):
            times.append(datetime(yr, 1, 1, tzinfo=UTC) + timedelta(hours=i * 7))
            grow.append(rng.normal(0.0005 * (k + 1), 0.0005))
            fade.append(rng.normal(0.0005 * (8 - k), 0.0005))
    g = C.edge_trend(grow, times, NOW)
    f = C.edge_trend(fade, times, NOW)
    assert g["status"] == f["status"] == C.MEASURED
    assert g["projected_ratio_now"] > 1.0 > f["projected_ratio_now"]
    mg, kg = C.shrink_trend(g)
    mf, _ = C.shrink_trend(f)
    assert mg > 1.0 > mf and 0.0 < kg <= 1.0
    # a noisy measurement barely moves the multiplier
    wide = {"projected_ratio_now": 3.0, "ci90": [-10.0, 15.0]}
    assert abs(C.shrink_trend(wide)[0] - 1.0) < 0.05
    few = C.edge_trend(grow[:300], times[:300], NOW)
    assert few["status"] == "UNMEASURED_FEW_YEARS"


def test_multiplier_prefers_measurement_and_is_clamped_both_ways():
    lit = {"status": C.MEASURED, "kind": "academic"}
    m, basis = C.multiplier(0.9, lit, {"status": C.MEASURED, "decay": 0.95}, NOW)
    assert m == C.MULT_FLOOR and basis.startswith(C.MEASURED)
    m, basis = C.multiplier(0.9, lit, {"status": C.MEASURED, "decay": -2.0}, NOW)
    assert m == C.MULT_CEIL
    trend = {"status": C.MEASURED, "projected_ratio_now": 1.4, "ci90": [1.2, 1.6]}
    m, basis = C.multiplier(0.9, lit, {"status": "UNMEASURED_X", "trend": trend}, NOW)
    assert m > 1.0 and basis.startswith("MEASURED_TREND")
    m, basis = C.multiplier(0.9, lit, None, NOW)
    assert basis.startswith(C.BORROWED) and m == pytest.approx(1 - 0.58 * 0.95)
    m, basis = C.multiplier(None, {"status": C.UNMEASURED}, None, NOW)
    assert m == 1.0 and "neutral" in basis


def test_a_pass_marks_every_row_credits_originality_and_round_trips(tmp_path, monkeypatch):
    docket = [
        {"genome_id": "g1", "symbol": "EURUSD", "family": "turn_of_month",
         "source": "miner:youtube", "contributing_sources": ["reddit", "asia:collective2"],
         "first_seen": NOW.isoformat()},
        {"genome_id": "g2", "symbol": "XAUUSD", "family": "brand_new_mechanism",
         "source": "miner:moat_factory", "first_seen": NOW.isoformat()},
        {"symbol": "USDJPY", "family": "turn_of_month", "source": "miner:anomalies",
         "params": {"k": 1}},
    ]
    intel = tmp_path / "intel"
    (intel / "forexfactory").mkdir(parents=True)
    (intel / "forexfactory" / "d.json").write_text(json.dumps([{"family": "turn_of_month"}]))
    (intel / "not_public_seat").mkdir()
    (intel / "not_public_seat" / "d.json").write_text(json.dumps([{"family": "x"}]))
    monkeypatch.setattr(C, "DECAY_CACHE", tmp_path / "cache.json")
    rep = C.run(now=NOW, docket=docket, write=False, bars=lambda s: None,
                intel_root=intel, cot_path=tmp_path / "absent.json", budget_s=30)
    marks = rep["_marks"]
    assert rep["docket_rows"] == 3 and len(marks) == 3 and rep["coverage"] == 1.0
    crowded, novel = marks["g1"], marks["g2"]
    assert crowded["crowding_score"] > novel["crowding_score"]
    assert novel["original_mechanism"] and not crowded["original_mechanism"]
    assert novel["expected_edge_multiplier"] == 1.0
    assert crowded["expected_edge_multiplier"] < 1.0
    assert crowded["components"]["cot_concentration"] is None      # UNMEASURED, not zero
    assert "forexfactory" in crowded["public_seats"] or "youtube" in crowded["public_seats"]
    assert 0 < rep["crowding_adjusted_share"] < 1
    assert rep["decay"]["turn_of_month"]["status"] == "UNMEASURED_NO_TRADES"
    assert "REPORT-ONLY" in rep["authority"]

    path = tmp_path / "marks.json"
    C._atomic(path, {"fields": list(C.COMPACT_FIELDS), "marks": C.compact_marks(marks)})
    got = C.read_mark("g1", path)
    assert got["crowding_score"] == crowded["crowding_score"]
    assert got["expected_edge_multiplier"] == crowded["expected_edge_multiplier"]
    assert C.read_mark("nope", path) is None
    assert C.row_key(docket[2]).startswith("id:")


def test_empty_docket_is_unmeasured(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "DECAY_CACHE", tmp_path / "cache.json")
    rep = C.run(now=NOW, docket=[], write=False, bars=lambda s: None,
                intel_root=tmp_path, cot_path=tmp_path / "x.json", budget_s=5)
    assert rep["status"] == C.UNMEASURED and rep["coverage"] == C.UNMEASURED


def test_leg_layer_and_graph_are_wired():
    hc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"candidate_crowding", "research/candidate_crowding.py"' in hc
    assert '"candidate_crowding": ccr' in hc
    cg = (ROOT / "libs" / "ops" / "capability_graph.py").read_text("utf-8")
    assert '"desks/mt5/research/candidate_crowding.py"' in cg
    from libs.research import layers
    assert layers.LEG_LAYER["candidate_crowding"] == "meta"
