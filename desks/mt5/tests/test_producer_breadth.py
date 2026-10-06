"""Producers at full, orthogonal, TESTABLE breadth (principal 2026-09-30), and the leg measuring it.

Every input is synthetic or redirected into `tmp_path`; nothing here reads or writes box state.
"""
from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import breadth_rotation as br_top  # noqa: E402

from research import breadth_rotation as br  # noqa: E402
from research import gauntlet_buildability as gb  # noqa: E402
from research import producer_breadth as pb  # noqa: E402


def _seen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keys: list[str]) -> None:
    """Point both import spellings of the rotation module at one judged-cells file."""
    p = tmp_path / "gauntlet_seen_cells.json"
    p.write_text(json.dumps(dict.fromkeys(keys, "2026-09-30T00:00:00+00:00")), "utf-8")
    monkeypatch.setattr(br, "SEEN_CELLS", p)
    monkeypatch.setattr(br_top, "SEEN_CELLS", p)


def _frame(seed: int, n: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c,
                         "tick_volume": 100, "spread": 2}, index=idx)


# ------------------------------------------------------------------ the ring
def test_a_rotating_window_reaches_every_item_within_one_lap() -> None:
    ring = [f"S{i:02d}" for i in range(14)]
    seen: set[str] = set()
    for turn in range(-(-len(ring) // 3)):
        win = br.rotating_window(ring, 3, turn=turn)
        assert len(win) == 3
        seen.update(win)
    assert seen == set(ring), "a lap of ceil(n/k) turns must visit the whole ring"
    assert br.rotating_window(ring[:2], 3, turn=5) == ring[:2], "a short ring is returned whole"


def test_the_ring_puts_the_least_judged_instruments_first(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    _seen(tmp_path, monkeypatch, ["EURUSD.carry.p=1", "EURUSD.carry.p=2", "AUDUSD.carry.p=3",
                                  "AUDUSD.trend.p=4", "GBPUSD.trend.p=5"])
    assert br.orthogonal_ring(["EURUSD", "AUDUSD", "GBPUSD", "NZDUSD"]) == \
        ["NZDUSD", "GBPUSD", "AUDUSD", "EURUSD"]
    assert br.orthogonal_ring(["EURUSD", "AUDUSD", "GBPUSD"], "carry") == \
        ["GBPUSD", "AUDUSD", "EURUSD"]


def test_an_unreadable_coverage_file_falls_back_to_name_order(tmp_path: Path) -> None:
    by_sym, by_pair = br.judged_counts(tmp_path / "absent.json")
    assert by_sym == {} and by_pair == {}
    assert br.orthogonal_ring(["B", "A"], counts=({}, {})) == ["A", "B"]


def test_the_lane_never_includes_a_single_name_equity() -> None:
    from research.universe_policy import may_hypothesise
    lane = br.hypothesis_symbols()
    if not lane:
        pytest.skip("no hypothesis-lane bars on this host -- UNMEASURED, not a pass")
    assert all(may_hypothesise(s) for s in lane)


# ------------------------------------------------------------------ qd_frontier
def test_qd_frontier_reaches_the_whole_class_not_its_first_three(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import axis_registry as ar
    import qd_frontier as qd
    _seen(tmp_path, monkeypatch, [])
    monkeypatch.setattr(ar, "may_hypothesise", lambda s: not s.startswith("EQ"))
    klass = [f"FX{i:02d}" for i in range(11)] + ["EQAPPLE"]
    by_class = {"forex": klass}
    old_prefix = set(klass[:qd.PROPOSAL_SYMBOLS])
    reached: set[str] = set()
    for turn in range(-(-11 // qd.PROPOSAL_SYMBOLS)):
        got = qd._symbols("forex", by_class, turn)
        assert len(got) == qd.PROPOSAL_SYMBOLS
        assert "EQAPPLE" not in got, "the event lane is never hunted"
        reached.update(got)
    assert reached == set(klass) - {"EQAPPLE"}
    assert reached - old_prefix, "the rotation reaches instruments the old prefix never did"


# ------------------------------------------------------------------ the sealed judge's reach
def test_the_supplied_set_is_read_from_the_sealed_build_cell() -> None:
    supplied = gb.supplied_families()
    assert {"relative_value", "cross_asset_residual", "cot_positioning", "carry"} <= supplied
    # Sealed pass 2 (76895fedc) re-signed build_cell with these branches; read from its source.
    assert {"lead_lag", "execution_state", "event_reaction"} <= supplied


def test_the_resigned_gauntlet_supplies_lead_lag_execution_state_and_event_reaction() -> None:
    """PINNED to the re-signed truth (Sealed pass 2, 76895fedc): the three families that once
    built ZERO signals now have branches that load their inputs, so the verdict is BUILDABLE and
    no declared defect is left. A gauntlet that loses a branch fails this the way the old pin
    failed when the branch arrived."""
    src = (_DESK / "scripts" / "external_gauntlet.py").read_text(encoding="utf-8")
    assert 'family == "lead_lag"' in src and 'family == "execution_state"' in src
    assert "events_for_symbol(events, sym)" in src and 'call_params["symbol"] = sym' in src
    assert gb.SEALED_INPUT_DEFECTS == {}
    for fam in ("lead_lag", "event_reaction", "execution_state"):
        assert gb.family_verdict(fam)[0] == gb.BUILDABLE, fam
    assert gb.family_verdict("discovered")[0] == gb.BANNED


def test_a_cell_is_refused_on_a_chart_its_family_declares_inexpressible() -> None:
    assert gb.cell_verdict("relative_value", {"timeframe": "M5"})[0] == gb.TIMEFRAME_REFUSED
    assert gb.cell_verdict("relative_value", {"timeframe": "H4"})[0] == gb.BUILDABLE
    assert gb.cell_verdict("calendar_month", {})[0] == gb.MISSING_PARAMS
    assert gb.cell_verdict("session_range_breakout", {"timeframe": "M15"})[0] == gb.BUILDABLE
    missing_hour = gb.cell_verdict("clock_transition", {"label": "london_fix", "stamp_hour": None})
    valid_hour = gb.cell_verdict("clock_transition", {"label": "london_fix", "stamp_hour": 18})
    assert missing_hour[0] == gb.MISSING_PARAMS
    assert valid_hour[0] == gb.BUILDABLE


# ------------------------------------------------------------------ breadth_sweep
def test_breadth_sweep_mints_only_testable_cells_and_reports_what_it_set_aside(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import breadth_sweep as bs
    _seen(tmp_path, monkeypatch, [])
    monkeypatch.setattr(bs, "_with_bars", lambda: ["EURUSD", "XAUUSD"])
    monkeypatch.setattr(bs, "_charts_for", lambda sym: ["M5", "H1", "D1"])
    monkeypatch.setattr(bs, "REPORT", tmp_path / "BREADTH_SWEEP.json")
    rows = bs.cells()
    assert rows
    for r in rows:
        tf = (r["params"] or {}).get("timeframe", "H1")
        assert gb.cell_verdict(r["family"], r["params"], tf)[0] == gb.BUILDABLE, r
    fams = {r["family"] for r in rows}
    assert "discovered" not in fams
    assert not [r for r in rows if r["family"] == "relative_value"
                and (r["params"] or {}).get("timeframe") == "M5"]
    doc = bs.write_report(rows, ["EURUSD", "XAUUSD"], None, None)
    assert doc["set_aside_cells"] > 0
    assert all(a["verdict"] != gb.SEALED_INPUT_DEFECT for a in doc["set_aside_untestable"])
    assert json.loads((tmp_path / "BREADTH_SWEEP.json").read_text())["cells_built"] == len(rows)


def test_breadth_sweep_spends_its_cap_on_the_least_judged_pairs_first(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import breadth_sweep as bs
    _seen(tmp_path, monkeypatch, [f"AUDUSD.vol_transition.p={i}" for i in range(9)])
    monkeypatch.setattr(bs, "_with_bars", lambda: ["AUDUSD", "ZARJPY"])
    monkeypatch.setattr(bs, "_charts_for", lambda sym: ["H1"])
    rows = bs.cells("vol_transition")
    assert rows[0]["symbol"] == "ZARJPY", "the unjudged instrument leads, not the alphabet"


def test_breadth_sweep_prefers_under_certified_mechanisms_without_banning_others(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import breadth_sweep as bs
    canon = tmp_path / "UNIVERSAL_SURVIVORS.canon.json"
    canon.write_text(json.dumps({"survivors": {
        "a": {"shadow_spec": {"family": "carry"}},
        "b": {"shadow_spec": {"family": "carry"}},
    }}), "utf-8")
    monkeypatch.setattr(bs, "CERTIFICATES", canon)
    _seen(tmp_path, monkeypatch, [])
    key = bs._orthogonal_key()
    unseen = {"symbol": "EURUSD", "family": "vol_transition",
              "params": {"timeframe": "M5"}}
    saturated = {"symbol": "EURUSD", "family": "carry",
                 "params": {"timeframe": "M5"}}
    assert key(unseen) < key(saturated)
    assert bs._certified_family_counts() == {"carry": 2}


# ------------------------------------------------------------------ htf_anchor_proposer
def test_htf_anchor_mints_fine_charts_only_where_their_bars_exist(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import htf_anchor_proposer as hp
    _seen(tmp_path, monkeypatch, ["EURUSD.htf_anchor_trend.p=1"])
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    (uni / "XAUUSD_M15.parquet").write_bytes(b"")
    monkeypatch.setattr(hp, "BASE", tmp_path)
    rows = hp.build_candidates({"binding": []}, ["EURUSD", "XAUUSD"])
    charts = {(r["symbol"], r["params"]["timeframe"]) for r in rows}
    assert ("XAUUSD", "M15") in charts, "a fine chart with bars is minted"
    assert ("EURUSD", "M15") not in charts and ("XAUUSD", "M30") not in charts
    assert {("EURUSD", c) for c in hp.CHARTS} <= charts, "the old ladder is unchanged"
    assert rows[0]["symbol"] == "XAUUSD", "the least-judged instrument is walked first"
    assert all(gb.cell_verdict(r["family"], r["params"])[0] == gb.BUILDABLE for r in rows)


# ------------------------------------------------------------------ empty_cluster_forcer
def test_the_forcer_hands_every_reachable_cluster_to_its_proposer_and_forces_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import empty_cluster_forcer as ecf
    breadth = tmp_path / "EFFECTIVE_BREADTH.json"
    breadth.write_text(json.dumps({"clusters": {"empty_in_both": [
        "cross_asset_lead_lag", "event_surprise", "news_reaction"]}}), "utf-8")
    monkeypatch.setattr(ecf, "BREADTH", breadth)
    monkeypatch.setattr(ecf, "MANDATE", tmp_path / "absent.json")
    doc = ecf.plan()
    rows = {r["cluster"]: r for r in doc["clusters"]}
    # `lead_lag_class_catchup` (the class books, 2026-09-30) loads its own leader panel, so the
    # lead-lag cluster now has a family the sealed judge CAN build and is no longer blocked.
    assert gb.family_verdict("lead_lag_class_catchup")[0] == gb.BUILDABLE
    # Since the re-signed gauntlet (76895fedc) event_reaction is buildable too, and the news lane
    # (analyst families, LIVE 2026-09-30) classifies into news_reaction: all three clusters are
    # reachable through a proposer, none is sealed off and none is family-less.
    for c in ("cross_asset_lead_lag", "event_surprise", "news_reaction"):
        assert rows[c]["verdict"] == "PROPOSER_OWNED", (c, rows[c]["verdict"])
    assert doc["n_cells_minted"] == 0, "no zero-signal cell is ever forced"


def test_the_forcer_rotates_over_the_lane_rather_than_twelve_fixed_names(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import empty_cluster_forcer as ecf
    _seen(tmp_path, monkeypatch, [])
    lane = [f"FX{i:02d}" for i in range(20)]
    monkeypatch.setattr(br, "hypothesis_symbols", lambda universe=None: lane)
    reached: set[str] = set()
    for turn in range(-(-len(lane) // ecf.CELLS_PER_CLUSTER)):
        reached.update(ecf._symbols_for("vol_transition", {}, turn))
    assert reached == set(lane)


# ------------------------------------------------------------------ the leg
def _registry(db: Path, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    con = sqlite3.connect(db)
    con.execute("create table research_candidates (id text, created_at text, family text, "
                "symbol text, chart text, session text, generator text, discovery_id text)")
    con.execute("create table discoveries (discovery_id text, generator text)")
    for i, (gen, fam, sym, chart, sess, at) in enumerate(rows):
        con.execute("insert into research_candidates values (?,?,?,?,?,?,?,?)",
                    (f"c{i}", at, fam, sym, chart, sess, gen, f"d{i}"))
        con.execute("insert into discoveries values (?,?)", (f"d{i}", gen))
    con.commit()
    con.close()


def test_the_leg_measures_each_producer_from_the_registry(tmp_path: Path) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    fresh = (now - timedelta(hours=2)).isoformat()
    week = (now - timedelta(days=3)).isoformat()
    old = (now - timedelta(days=30)).isoformat()
    db = tmp_path / "alpha_registry.sqlite"
    _registry(db, [
        ("video_anchor_exit", "htf_anchor_trend", "EURUSD", "M15", "all", fresh),
        ("video_anchor_exit", "htf_anchor_trend", "XAUUSD", "H4", "all", week),
        ("cross_asset_graph", "lead_lag", "GBPUSD", "H1", "all", fresh),
        ("cross_asset_graph", "lead_lag", "GBPUSD", "H1", "all", old),
    ])
    doc = pb.build(now=now, db=db)
    htf = doc["producers"]["htf_anchor_proposer"]
    assert htf["measured_from"] == "registry"
    assert htf["cells_24h"] == 1 and htf["cells_7d"] == 2
    assert htf["covered"]["charts"] == {"M15": 1, "H4": 1}
    assert htf["buildable_share"] == 1.0
    assert htf["scheduled"] and "hourly_cycle:htf_anchor" in htf["clocks"]
    cag = doc["producers"]["cross_asset_graph"]
    assert cag["cells_7d"] == 1 and cag["buildable_share"] == 1.0
    assert cag["status"] == "WIDENED"
    unfed = {u["cluster"]: u["why"] for u in doc["totals"]["empty_clusters_unfed"]}
    # cross_asset_graph's lead_lag cell is buildable since 76895fedc, so the registry's fresh
    # cell FEEDS the lead-lag cluster: it is no longer listed as unfed at all.
    assert "cross_asset_lead_lag" not in unfed
    assert unfed["options_implied"].startswith("NO_FAMILY")


def test_a_producer_no_source_can_see_is_unmeasured_never_zero(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pb, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pb, "HYP", tmp_path / "hyp")
    monkeypatch.setattr(pb, "BASE", tmp_path)
    doc = pb.build(now=datetime(2026, 9, 30, tzinfo=UTC), db=tmp_path / "absent.sqlite")
    qd = doc["producers"]["qd_frontier"]
    assert qd["cells_7d"] == pb.UNMEASURED and qd["measured_from"].startswith(pb.UNMEASURED)
    assert "qd_frontier" in doc["totals"]["unmeasured"]
    assert doc["registry"].startswith(pb.UNMEASURED)


def test_seat_files_are_read_when_the_registry_is_silent(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    intel = tmp_path / "intel" / "breadth"
    intel.mkdir(parents=True)
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    rows: list[dict[str, Any]] = [
        {"kind": "hypothesis", "family": "vol_transition", "symbols": ["EURUSD"]},
        {"kind": "hypothesis", "family": "lead_lag", "symbols": ["GBPUSD"],
         "params": {"timeframe": "H4", "session": "london"}},
    ]
    (intel / "empty_cluster_20260930T11.json").write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(pb, "INTEL", tmp_path / "intel")
    doc = pb.build(now=now, db=tmp_path / "absent.sqlite")
    ecf = doc["producers"]["empty_cluster_forcer"]
    assert ecf["cells_24h"] == 2 and ecf["cells_7d"] == 2
    assert ecf["buildable_share"] == 1.0
    assert ecf["covered"]["sessions"] == {"all": 1, "london": 1}
    assert ecf["scheduled"] and "hourly_cycle:empty_cluster_forcer" in ecf["clocks"]


def test_the_leg_is_on_a_clock_in_a_department_a_layer_and_the_results() -> None:
    hc = importlib.import_module("research.hourly_cycle")
    from libs.research.layers import LEG_LAYER
    assert "producer_breadth" in hc.CORE_LEGS
    assert hc.department_of("producer_breadth") == "meta"
    assert LEG_LAYER["producer_breadth"] == "meta"
    assert hc.LEG_BUDGET_SEC["producer_breadth"] >= 120
    for leg in ("htf_anchor", "empty_cluster_forcer"):
        assert hc.department_of(leg) == "discovery"
        assert leg in LEG_LAYER and hc.LEG_BUDGET_SEC[leg] >= 120
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("producer_breadth", "htf_anchor", "empty_cluster_forcer"):
        assert f'_costed("{leg}"' in src and f'"{leg}": ' in src


def test_the_artifact_is_written_atomically(tmp_path: Path) -> None:
    out = pb.write({"totals": {}, "producers": {}}, tmp_path / "PRODUCER_BREADTH.json")
    assert json.loads(out.read_text()) == {"totals": {}, "producers": {}}
    assert not list(tmp_path.glob("*.tmp"))
