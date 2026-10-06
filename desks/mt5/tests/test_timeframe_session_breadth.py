"""Timeframe x session breadth: measured, published with a target, and targeted by producers.

Principal 2026-10-06: "we dont want only h1 100 percent being discovered only but rather all
timeframes, m1 m15 m30 h1 h4 d1 ... its fr sessions too ... basically all breadths targetted".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import breadth_rotation as br  # noqa: E402
from research.frontier_identity import docket_cell_id  # noqa: E402


def _universe(tmp: Path, charts: dict[str, list[str]]) -> Path:
    uni = tmp / "universe"
    uni.mkdir()
    for sym, tfs in charts.items():
        for tf in tfs:
            (uni / f"{sym}_{tf}.parquet").write_bytes(b"")
    return uni


def _write_row_per_line(path: Path, rows: list[dict[str, Any]]) -> None:
    """The shape merge_hypotheses._write_docket_atomically writes: one JSON row per line."""
    body = ",\n".join(json.dumps(r, separators=(",", ":")) for r in rows)
    path.write_text("[\n" + body + "\n]\n", encoding="utf-8")


def _rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(30):
        out.append({"symbol": "EURUSD", "family": "trend_ma_cross", "params": {"fast": i}})
    for i in range(6):
        out.append({"symbol": "EURUSD", "family": "trend_ma_cross",
                    "params": {"fast": i, "timeframe": "M15", "session": "london"}})
    for i in range(4):
        out.append({"symbol": "EURUSD", "family": "trend_ma_cross",
                    "params": {"fast": i, "timeframe": "D1"}})
    return out


def test_bucket_reads_the_chart_the_judge_loads_and_d1_has_no_session() -> None:
    assert br.bucket_of({"family": "x", "params": {}}) == ("H1", "all")
    assert br.bucket_of({"family": "x", "params": {"timeframe": "m5", "session": "Asia"}}) == \
        ("M5", "asia")
    assert br.bucket_of({"family": "x", "params": {}, "timeframe": "M30"}) == ("M30", "all")
    assert br.bucket_of({"family": "x", "params": {"selector": "ny"}}) == ("H1", "ny")
    assert br.bucket_of({"family": "x", "params": {"timeframe": "D1", "session": "asia"}}) == \
        ("D1", "all")
    # the judge's pin wins over a params chart
    assert br.bucket_of({"family": "lvc_asia_london", "params": {"timeframe": "H1"}})[0] == "M5"


def test_streaming_reader_samples_a_row_per_line_docket_without_loading_it(tmp_path) -> None:
    p = tmp_path / "docket.json"
    rows = _rows()
    _write_row_per_line(p, rows)
    got, meta = br.iter_docket(p, max_parsed=10)
    assert meta["format"] == "row_per_line" and meta["rows"] == len(rows)
    assert meta["stride"] == 4 and len(got) == 10
    full, meta_all = br.iter_docket(p, max_parsed=10_000)
    assert meta_all["stride"] == 1 and len(full) == len(rows)


def test_absent_docket_is_unmeasured_never_zero(tmp_path) -> None:
    rows, meta = br.iter_docket(tmp_path / "nope.json")
    assert rows == [] and meta["why"].startswith("UNMEASURED")


def test_census_measures_discovery_and_judged_share_against_an_equal_share_target(
        tmp_path) -> None:
    uni = _universe(tmp_path, {"EURUSD": ["M15", "H1", "D1"]})
    docket = tmp_path / "docket.json"
    rows = _rows()
    _write_row_per_line(docket, rows)
    # the judge has judged every H1 row and nothing else
    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps({docket_cell_id(r): "t" for r in rows[:30]}), encoding="utf-8")
    c = br.tf_session_census(docket=docket, seen=seen, order=tmp_path / "absent.json",
                             universe=uni)
    assert c["targets"]["reachable_charts"] == ["M15", "H1", "D1"]
    assert c["targets"]["per_chart"] == round(1 / 3, 4)
    # 4 + 4 + 1 buckets reachable: M15 x 4 sessions, H1 x 4 sessions, D1 x all
    assert c["targets"]["per_bucket"] == round(1 / 9, 4)
    assert c["charts"]["H1"]["discovery"]["share"] == 0.75
    assert c["charts"]["H1"]["judged"]["share"] == 1.0
    assert c["charts"]["M15"]["judged"]["share"] == 0.0
    assert c["h1_share"] == {"discovery": 0.75, "judged": 1.0}
    # a chart with no bars is reported, never targeted
    assert c["charts"]["M1"]["reachable"] is False
    assert "M1/all" not in c["buckets"]
    # under-target buckets lead the priority; H1/all (over target on both) is not among them
    assert "H1/all" not in c["under_target"]
    assert "M15/london" in c["under_target"] and "D1/all" in c["under_target"]
    assert c["priority"][-1] == "H1/all"
    assert c["sources"]["judge_order"].startswith("UNMEASURED")


def test_census_without_seen_cells_reports_judged_unmeasured(tmp_path) -> None:
    uni = _universe(tmp_path, {"EURUSD": ["H1"]})
    docket = tmp_path / "docket.json"
    _write_row_per_line(docket, _rows())
    c = br.tf_session_census(docket=docket, seen=tmp_path / "none.json",
                             order=tmp_path / "none2.json", universe=uni)
    assert c["charts"]["H1"]["judged"] == "UNMEASURED"
    assert c["h1_share"]["judged"] == "UNMEASURED"


def test_key_is_neutral_without_a_census_and_puts_under_target_first_with_one() -> None:
    rows = [{"family": "f", "params": {}}, {"family": "f", "params": {"timeframe": "M15"}}]
    neutral = br.tf_session_key({})
    assert [neutral(r) for r in rows] == [0, 0]
    census = {"buckets": {"H1/all": {}, "M15/all": {}}, "under_target": ["M15/all"]}
    key = br.tf_session_key(census)
    assert [key(r) for r in rows] == [1, 0]
    # composed in front of an existing key, the old order holds inside each tier
    old = sorted(rows + [{"family": "a", "params": {"timeframe": "M15"}}],
                 key=lambda r: (key(r), r["family"]))
    assert [r["params"].get("timeframe", "H1") for r in old] == ["M15", "M15", "H1"]
    # a bucket the census does not know (no bars, odd session) is never promoted
    assert key({"family": "f", "params": {"timeframe": "M1"}}) == 1


def test_load_census_reads_the_published_block(tmp_path) -> None:
    p = tmp_path / "PRODUCER_BREADTH.json"
    assert br.load_census(p) is None
    p.write_text(json.dumps({"timeframe_session": {"buckets": {"H1/all": {}},
                                                   "under_target": []}}), encoding="utf-8")
    assert br.load_census(p)["buckets"] == {"H1/all": {}}


def test_producer_breadth_publishes_the_block_and_the_move(tmp_path, monkeypatch) -> None:
    from research import producer_breadth as pb
    monkeypatch.setattr(br, "tf_session_census", lambda **_k: {
        "charts": {"H1": {"discovery": {"share": 0.6}, "judged": {"share": 0.9}}},
        "buckets": {"H1/all": {}}, "under_target": []})
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps({"timeframe_session": {
        "generated_at": "t0", "buckets": {"H1/all": {}},
        "charts": {"H1": {"discovery": {"share": 0.7}, "judged": {"share": 1.0}}}}}),
        encoding="utf-8")
    rows = {"p": {"covered": {"charts": {"H1": 3, "M5": 1}, "sessions": {"all": 4}}}}
    block = pb.timeframe_session_block({"_rows": rows}, prev_path=prev)
    assert block["minted_7d"]["charts"] == {"H1": 0.75, "M5": 0.25}
    assert block["moved_since_previous"]["H1"] == {"discovery": -0.1, "judged": -0.1}


def test_breadth_sweep_order_puts_under_target_buckets_first(monkeypatch) -> None:
    from research import breadth_sweep as bs
    census = {"buckets": {"H1/all": {}, "D1/all": {}, "M5/all": {}},
              "under_target": ["D1/all"]}
    monkeypatch.setattr(br, "load_census", lambda path=None: census)
    monkeypatch.setattr(bs, "_certified_family_counts", lambda: {})
    rows = [{"symbol": "EURUSD", "family": "f", "params": {"timeframe": "M5"}},
            {"symbol": "EURUSD", "family": "f", "params": {}},
            {"symbol": "EURUSD", "family": "f", "params": {"timeframe": "D1"}}]
    out = sorted(rows, key=bs._orthogonal_key())
    assert [r["params"].get("timeframe", "H1") for r in out] == ["D1", "M5", "H1"]


# ----------------------------------------------------------------- producers widened
def test_compiler_expands_onto_m1_h4_and_d1_and_respects_family_timeframes(
        tmp_path, monkeypatch) -> None:
    from research import miner_candidate_compiler as mcc
    uni = _universe(tmp_path, {"EURUSD": ["M1", "M5", "H1", "H4", "D1"]})
    monkeypatch.setattr(mcc, "UNIVERSE", uni)
    monkeypatch.setattr(mcc, "_invariance", lambda _s, _f: None)
    out = mcc.expand_axes([{"symbol": "EURUSD", "family": "trend_ma_cross", "params": {}}])
    charts = {v["axis"]["chart"] for v in out}
    assert charts == {"M1", "M5", "H1", "H4", "D1"}
    assert {v["axis"]["session"] for v in out if v["axis"]["chart"] == "D1"} == {"all"}
    assert len(out) == 4 * 4 + 1
    # a family declared H1/H4/D1-only is not expanded onto M1/M5, and the refusal is counted
    mcc.LAST_TIMEFRAME_SET_ASIDE.clear()
    out = mcc.expand_axes([{"symbol": "EURUSD", "family": "relative_value", "params": {}}])
    assert {v["axis"]["chart"] for v in out} == {"H1", "H4", "D1"}
    assert mcc.LAST_TIMEFRAME_SET_ASIDE == {"relative_value|M1": 1, "relative_value|M5": 1}


def test_fanout_mints_m30_and_d1_but_not_a_declared_inexpressible_chart() -> None:
    from research import timeframe_fanout as tf
    assert {"M30", "D1"} <= set(tf.CHARTS)
    res = tf.mint({"lane": "l", "parent": "P", "symbol": "EURUSD", "family": "relative_value",
                   "params": {}, "session": "", "regime": "", "parent_chart": "H1",
                   "mechanism": "m"}, list(tf.CHARTS), dry_run=True)
    assert res["emitted"] == 3
    assert set(res["refused_charts"]) == {"M1", "M5", "M15", "M30"}


def test_htf_anchor_mints_every_fine_chart_whose_bars_exist(tmp_path, monkeypatch) -> None:
    import htf_anchor_proposer as hap
    assert set(hap.FINE_CHARTS) == {"M1", "M5", "M15", "M30"}


def test_horizon_miner_reaches_m1_and_no_longer_orphans_m30() -> None:
    import transformation_miners as TM
    assert TM.CHART_LADDER[0] == "M1"
    i = TM.CHART_LADDER.index("H1")
    assert TM.CHART_LADDER[i - 1] == "M15"          # H1's faster neighbour is unchanged
    assert TM.OFF_LADDER_NEIGHBOURS["M30"] == ("M15", "H1")
    ok, _why = TM.compatible(None, chart="M30")
    assert ok


@pytest.mark.parametrize("sym", ["XAUUSD"])
def test_free_stack_charts_are_bar_gated_beyond_h1_h4(tmp_path, monkeypatch, sym) -> None:
    import free_stack_proposer as P
    uni = _universe(tmp_path, {sym: ["M15", "D1"]})
    monkeypatch.setattr(P, "UNIVERSE", uni)
    assert P.charts_for(sym) == ["H1", "H4", "M15", "D1"]
    assert P.charts_for("NOPE") == ["H1", "H4"]
