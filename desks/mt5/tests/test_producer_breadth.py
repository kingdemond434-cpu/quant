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
    assert "lead_lag" not in supplied and "execution_state" not in supplied


def test_the_sealed_gauntlet_builds_lead_lag_and_event_reaction_with_no_signals(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """PINNED: the day the gauntlet is re-signed with these branches this test fails, and
    `gauntlet_buildability` must be corrected rather than left stale."""
    sys.path.insert(0, str(_DESK / "scripts"))
    import external_gauntlet as eg
    from mt5desk.family_event_reaction import family_event_reaction
    from mt5desk.family_lead_lag import family_lead_lag

    from research import orthogonal_sweep as osw
    tgt, drv = _frame(1), _frame(2)
    frames = {"GGGHHH": tgt, "DRV": drv}
    monkeypatch.setattr(eg, "_bars_for", lambda sym, tf="H1": frames.get(sym))
    ll = {"driver_symbol": "DRV", "lag": 1, "direction": "same", "entry_z": 1.5, "norm": 240,
          "hold_bars": 4}
    assert family_lead_lag(tgt, driver=drv, **ll), "the family trades when handed its driver"
    cell = eg.build_cell("GGGHHH", "lead_lag", dict(ll), {})
    assert cell is not None and not cell["sigs"]
    events = [{"symbol": "GGGHHH", "at": str(ts)} for ts in tgt.index[300::50]]
    assert family_event_reaction(tgt, events=events, symbol="GGGHHH", mode="drift")
    monkeypatch.setattr(osw, "_event_index",
                        lambda: pd.DatetimeIndex([pd.Timestamp(e["at"]) for e in events]))
    cell = eg.build_cell("GGGHHH", "event_reaction", {"mode": "drift", "symbol": "GGGHHH"}, {})
    assert cell is not None and not cell["sigs"]
    assert gb.family_verdict("lead_lag")[0] == gb.INPUT_NOT_SUPPLIED
    assert gb.family_verdict("event_reaction")[0] == gb.SEALED_INPUT_DEFECT
    assert gb.family_verdict("execution_state")[0] == gb.INPUT_NOT_SUPPLIED
    assert gb.family_verdict("discovered")[0] == gb.BANNED


def test_a_cell_is_refused_on_a_chart_its_family_declares_inexpressible() -> None:
    assert gb.cell_verdict("relative_value", {"timeframe": "M5"})[0] == gb.TIMEFRAME_REFUSED
    assert gb.cell_verdict("relative_value", {"timeframe": "H4"})[0] == gb.BUILDABLE
    assert gb.cell_verdict("calendar_month", {})[0] == gb.MISSING_PARAMS
    assert gb.cell_verdict("session_range_breakout", {"timeframe": "M15"})[0] == gb.BUILDABLE


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
    assert not fams & {"lead_lag", "event_reaction", "execution_state", "triangle",
                       "discovered"}
    assert not [r for r in rows if r["family"] == "relative_value"
                and (r["params"] or {}).get("timeframe") == "M5"]
    doc = bs.write_report(rows, ["EURUSD", "XAUUSD"], None, None)
    assert doc["set_aside_cells"] > 0
    assert {a["family"] for a in doc["set_aside_untestable"]} >= {"lead_lag", "event_reaction"}
    assert json.loads((tmp_path / "BREADTH_SWEEP.json").read_text())["cells_built"] == len(rows)


def test_breadth_sweep_spends_its_cap_on_the_least_judged_pairs_first(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import breadth_sweep as bs
    _seen(tmp_path, monkeypatch, [f"AUDUSD.vol_transition.p={i}" for i in range(9)])
    monkeypatch.setattr(bs, "_with_bars", lambda: ["AUDUSD", "ZARJPY"])
    monkeypatch.setattr(bs, "_charts_for", lambda sym: ["H1"])
    rows = bs.cells("vol_transition")
    assert rows[0]["symbol"] == "ZARJPY", "the unjudged instrument leads, not the alphabet"


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
def test_the_forcer_names_a_cluster_whose_every_family_the_sealed_judge_cannot_build(
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
    assert rows["cross_asset_lead_lag"]["verdict"] != "BLOCKED_BY_SEALED_GAUNTLET"
    assert rows["event_surprise"]["verdict"] == "BLOCKED_BY_SEALED_GAUNTLET"
    assert rows["news_reaction"]["verdict"] == "UNREACHABLE"
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
    assert cag["cells_7d"] == 1 and cag["buildable_share"] == 0.0
    assert cag["status"] == "LEFT_UNTESTABLE"
    unfed = {u["cluster"]: u["why"] for u in doc["totals"]["empty_clusters_unfed"]}
    # cross_asset_graph's plain lead_lag cannot be built, but the cluster holds a buildable
    # family (`lead_lag_class_catchup`), so the leg names it UNMINTED, not blocked.
    assert unfed["cross_asset_lead_lag"].startswith("UNMINTED")
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
    assert ecf["buildable_share"] == 0.5
    assert ecf["covered"]["sessions"] == {"all": 1, "london": 1}
    assert ecf["scheduled"] and "hourly_cycle:empty_cluster_forcer" in ecf["clocks"]


def test_producer_breadth_counts_a_mechanism_once(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """A grid of one mechanism over many symbols and parameter points is ONE breadth unit:
    `breadth_k` counts mechanisms, `cells_7d` still counts every cell."""
    intel = tmp_path / "intel" / "specialist_cell"
    intel.mkdir(parents=True)
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    rows: list[dict[str, Any]] = [
        {"family": "fx_fixing_reversal", "symbol": f"FX{i:02d}",
         "params": {"fix_hour": 18 + (j % 2), "hold_bars": 3 + j},
         "breadth_unit": "fx/wmr_fix_reversal",
         "evidence": {"specialist_mechanism": "wmr_fix_reversal", "asset_class_desk": "fx"}}
        for i in range(22) for j in range(16)]
    rows.append({"family": "forced_flow", "symbol": "EURUSD", "params": {"mode": "pre_flow"},
                 "evidence": {"specialist_mechanism": "fix_forced_flow",
                              "asset_class_desk": "fx"}})
    rows.append({"family": "overnight_gap_decay", "symbol": "US500", "params": {}})
    (intel / "discoveries_20260930T11.json").write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(pb, "INTEL", tmp_path / "intel")
    doc = pb.build(now=now, db=tmp_path / "absent.sqlite")
    sc = doc["producers"]["specialist_cell"]
    assert sc["cells_7d"] == 354
    assert sc["breadth_k"] == 3
    assert sc["units"]["fx/wmr_fix_reversal"] == 352
    assert set(sc["units"]) == {"fx/wmr_fix_reversal", "fx/fix_forced_flow",
                                "overnight_gap_decay"}
    assert sc["largest_unit_share"] == round(352 / 354, 4)
    assert doc["totals"]["breadth_k"] >= 3


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
