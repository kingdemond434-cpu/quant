"""The occupancy map and the per-candidate orthogonality score -- and their two consumers.

research/occupancy_map.py grids strategy space (family x asset class x timeframe x session x
horizon), counts the funnel per cell, names EMPTY / UNDER-TRIED cells next to proven ground, and
scores each docket (family, symbol) by expected correlation to the LIVE book and the certified
set. Consumer 1: research/judge_coverage.py adds `_occ` + `_orth` beside `_keff` in the docket
order (reorder only). Consumer 2: the leg donates intake rows for EMPTY targets (add only).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pd = pytest.importorskip("pandas")

from research import judge_coverage as jc  # noqa: E402
from research import occupancy_map as om  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
SEEN = (NOW - timedelta(hours=5)).isoformat()


def _sources() -> dict[str, Any]:
    """A book: carry on USDMXN is certified, forward-positive and LIVE; srb on EURUSD tried
    heavily with nothing to show; one carry row on GBPUSD tried once."""
    docket = ([{"family": "carry", "symbol": "USDMXN", "params": {"k": i}, "first_seen": SEEN}
               for i in range(3)]
              + [{"family": "session_range_breakout", "symbol": "EURUSD",
                  "params": {"k": i, "session": "asia"}, "first_seen": SEEN} for i in range(8)]
              + [{"family": "carry", "symbol": "GBPUSD", "params": {}, "first_seen": SEEN}])
    canon = {"survivors": {"x.USDMXN.carry": {"shadow_spec": {"symbol": "USDMXN",
                                                              "family": "carry"}}}}
    shadow = {"USDMXN.carry.continuous": {"n": 12, "exp_r": 0.4, "status": "ACTIVE"},
              "USDMXN.carry.continuous#x=1": {"n": 2, "exp_r": 9.0, "status": "ACTIVE"},
              "EURUSD.session_range_breakout.asia": {"n": 0, "status": "REFUSED"}}
    sleeves = {"sleeves": [{"symbol": "USDMXN", "family": "carry", "status": "LIVE",
                            "risk_frac": 0.01, "shadow_exp": 0.3, "shadow_n": 20}]}
    return {"docket": docket, "ledger": [], "canon": canon, "shadow": shadow,
            "sleeves": sleeves}


def _key(fam: str, sym: str, **kw: Any) -> str:
    return om.cell_key(om.cell_axes(sym, fam, kw.get("params"), kw.get("timeframe"),
                                    kw.get("session")))


# ------------------------------------------------------------------------------ the map
def test_collect_counts_the_funnel_per_cell() -> None:
    cells = om.collect(**_sources())
    carry = cells[_key("carry", "USDMXN")]
    assert carry["tried"] == 4, "three docket rows + the canon survivor"
    assert carry["certified"] == 1 and carry["live"] == 1
    assert carry["forward_enrolled"] == 2
    # A 2-trade clock with exp_r 9.0 does not set the cell's best forward expectancy.
    assert carry["best_forward_exp_r"] == pytest.approx(0.4)
    assert carry["last_tried_at"] is not None
    srb = cells[_key("session_range_breakout", "EURUSD", session="asia")]
    assert srb["tried"] == 8 and srb["certified"] == 0
    assert srb["forward_enrolled"] == 0, "a REFUSED clock never ran"
    assert om.success(carry) == 3 and om.success(srb) == 0


def test_ledger_verdicts_count_as_judged_and_passed() -> None:
    src = _sources()
    fid = om._frontier_id(src["docket"][3])
    src["ledger"] = [{"cell": fid, "passed": False, "terminal_gate": "cpcv", "at": SEEN},
                     {"cell": "EURUSD.session_range_breakout.p=zz", "sym": "EURUSD",
                      "family": "session_range_breakout", "passed": True,
                      "terminal_gate": "PASSED", "at": SEEN},
                     {"cell": "X", "passed": None, "downstream_status": "NOT_RUN_DATA_MISSING"}]
    cells = om.collect(**src)
    srb = cells[_key("session_range_breakout", "EURUSD", session="asia")]
    assert srb["judged"] == 1 and srb["tried"] == 8
    srb_all = cells[_key("session_range_breakout", "EURUSD")]
    assert srb_all["certified"] == 1, "a ledger pass is a certificate"


def test_targets_are_empty_or_under_tried_cells_next_to_success() -> None:
    cells = om.collect(**_sources())
    tg = om.targets(cells, families=["carry", "session_range_breakout", "overnight_gap_decay"],
                    classes=["forex", "forex_exotics", "bonds"], banned=lambda f: False)
    keys = {t["key"]: t for t in tg}
    # GBPUSD carry: same family, forex class, one axis from the proven USDMXN cell, tried once.
    under = keys[_key("carry", "GBPUSD")]
    assert under["kind"] == "UNDER_TRIED" and under["tried"] == 1
    # carry on bonds: never tried, one axis away.
    empty = keys[_key("carry", "UST10Y")]
    assert empty["kind"] == "EMPTY" and empty["priority"] > under["priority"]
    assert tg[0]["occupancy_priority"] == 1.0
    # The proven cell itself and a family in another mechanism are not targets.
    assert _key("carry", "USDMXN") not in keys
    assert not any(t["family"] == "session_range_breakout" for t in tg)
    # A banned family is never named.
    tg2 = om.targets(cells, families=["carry"], classes=["forex", "forex_exotics", "bonds"],
                     banned=lambda f: f == "carry")
    assert tg2 == []


def test_horizon_neighbours_are_reachable_ones() -> None:
    assert "multi_day" in om.reachable_horizons("H1")
    assert "sub_4h" not in om.reachable_horizons("D1")
    assert om.hold_for("H1", "sub_4h") is None, "the chart's own default needs no hold"
    b = om.hold_for("H1", "multi_day")
    assert b is not None and om.ar.horizon_of("H1", {"max_hold": b}) == "multi_day"


# ------------------------------------------------------------------------------ orthogonality
def _panel(n: int = 300, seed: int = 3) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")
    a = rng.normal(0, 0.01, n)
    return {"USDMXN": pd.Series(a, index=idx),
            "TWIN": pd.Series(a + rng.normal(0, 0.001, n), index=idx),
            "INDEP": pd.Series(rng.normal(0, 0.01, n), index=idx)}


def test_orthogonality_scores_a_twin_below_an_independent_instrument() -> None:
    src = _sources()
    panel = _panel()
    doc = om.orthogonality([("carry", "TWIN"), ("carry", "INDEP"), ("carry", "NOBARS"),
                            ("overnight_gap_decay", "TWIN")],
                           sleeves=src["sleeves"], canon=src["canon"], loader=panel.get)
    c = doc["cells"]
    assert c["carry|TWIN"]["score"] < c["carry|INDEP"]["score"]
    assert c["carry|TWIN"]["corr_live"] > 0.9
    # A different mechanism on the same instrument overlaps less than the same family does.
    assert c["overnight_gap_decay|TWIN"]["score"] > c["carry|TWIN"]["score"]
    # No bars: UNMEASURED, never 'the same bet' and never 'independent'.
    assert c["carry|NOBARS"]["score"] is None
    assert doc["status"] == "MEASURED" and doc["par"] is not None


# ------------------------------------------------------------------------------ consumer 1
def _map_doc(tmp: Path, *, at: datetime = NOW) -> Path:
    doc = {"at": at.isoformat(),
           "targets": [{"key": _key("carry", "GBPUSD"), "occupancy_priority": 1.0}],
           "orthogonality": {"par": 0.5, "cells": {"carry|UST10Y": {"score": 0.9},
                                                   "carry|USDMXN": {"score": 0.1}}}}
    p = tmp / "OCCUPANCY_MAP.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


def test_stamp_reads_the_map_and_an_absent_or_stale_map_stamps_nothing(tmp_path: Path) -> None:
    # GBPUSD sits in the target cell (carry | forex | H1 | all | sub_4h); UST10Y is on bonds.
    rows = [{"family": "carry", "symbol": "GBPUSD"}, {"family": "carry", "symbol": "UST10Y"},
            {"family": "carry", "symbol": "USDMXN"}, {"family": "carry", "symbol": "NONE"}]
    doc, _ = om.load(_map_doc(tmp_path), now=NOW)
    out = om.stamp(rows, doc)
    assert out["status"] == "MEASURED" and out["rows_in_targets"] == 1
    assert rows[0]["_occ"] == om.OCC_WEIGHT
    assert rows[1]["_orth"] == pytest.approx(0.4) and rows[2]["_orth"] == pytest.approx(-0.4)
    assert rows[1]["orthogonality"] == 0.9 and rows[3]["orthogonality"] is None
    assert rows[3]["_orth"] == 0.0, "unmeasured sits at par"
    stale, why = om.load(_map_doc(tmp_path, at=NOW - timedelta(hours=om.MAX_AGE_H + 1)), now=NOW)
    assert stale is None and "old" in why
    fresh_rows = [{"family": "carry", "symbol": "GBPUSD"}]
    assert om.stamp(fresh_rows, None, now=NOW)["status"] in ("UNMEASURED", "MEASURED")
    assert om.load(tmp_path / "absent.json")[0] is None


def test_coverage_order_lifts_target_and_orthogonal_rows_and_drops_nothing() -> None:
    rows = [{"family": "carry", "symbol": f"S{i}", "first_seen": f"2026-09-0{i + 1}",
             "_occ": 0.0, "_orth": 0.0} for i in range(5)]
    rows[3]["_occ"] = 1.0                 # the under-tried cell next to proven ground
    rows[4]["_orth"] = 0.4                # the most orthogonal candidate
    rows[0]["_orth"] = -0.4               # the most correlated candidate
    quota = {"carry": 5}
    legacy = jc.coverage_order([dict(r) for r in rows], quota, use_occupancy=False)
    shipped = jc.coverage_order([dict(r) for r in rows], quota)
    assert [r["symbol"] for r in legacy] == ["S0", "S1", "S2", "S3", "S4"]
    assert [r["symbol"] for r in shipped] == ["S3", "S4", "S1", "S2", "S0"]
    assert sorted(r["symbol"] for r in shipped) == sorted(r["symbol"] for r in rows)


def test_order_docket_reads_the_map_publishes_the_score_and_ships_every_row(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(jc, "OCCUPANCY_REPORT",
                        _map_doc(tmp_path, at=datetime.now(tz=UTC)))
    monkeypatch.setattr(jc, "REPORT", tmp_path / "JUDGE_COVERAGE.json")
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "ratchet.json")
    monkeypatch.setattr(jc, "STUDY_BANK", tmp_path / "none.json")
    monkeypatch.setattr(jc, "GATE_LEDGER", tmp_path / "gate.jsonl")
    monkeypatch.setattr(jc, "unrunnable_bank", lambda path=None: {})
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable.json")
    monkeypatch.setattr(jc, "keff_stamp", lambda rows: {"status": "UNMEASURED", "why": "test"})
    rows = [{"family": "carry", "symbol": s, "params": {"i": i}, "first_seen": SEEN}
            for i, s in enumerate(["USDMXN", "UST10Y", "GBPUSD"] * 3)]
    ordered, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(ordered) == len(rows), "reorder only: nothing dropped"
    assert all(not any(k in r for k in ("_occ", "_orth", "_cell", "_keff")) for r in ordered)
    by_sym = {r["symbol"]: r.get("orthogonality") for r in ordered}
    assert by_sym["UST10Y"] == 0.9 and by_sym["USDMXN"] == 0.1 and by_sym["GBPUSD"] is None
    occ = doc["occupancy_order"]
    assert occ["status"] == "MEASURED"
    assert occ["head"]["shipped"]["rows"] == occ["head"]["legacy"]["rows"]
    syms = [r["symbol"] for r in ordered]
    assert syms.index("GBPUSD") < syms.index("UST10Y") < syms.index("USDMXN"), \
        "target cell first, then the orthogonal candidate, the book's twin last"


# ------------------------------------------------------------------------------ consumer 2
def test_proposals_add_rows_for_empty_targets_only(tmp_path: Path) -> None:
    tg = [{"key": "carry|bonds|H1|all|multi_day", "kind": "EMPTY", "family": "carry",
           "asset_class": "bonds", "timeframe": "H1", "session": "all", "horizon": "multi_day",
           "priority": 3.0, "adjacency": 3.0, "adjacent_to": ["carry|forex|H1|all|sub_4h"]},
          {"key": "carry|forex|H1|asia|sub_4h", "kind": "UNDER_TRIED", "family": "carry",
           "asset_class": "forex", "timeframe": "H1", "session": "asia", "horizon": "sub_4h",
           "priority": 1.0, "adjacency": 1.0, "adjacent_to": []}]
    props = om.proposals(tg, by_class={"bonds": ["UST10Y", "UST05Y"], "forex": ["EURUSD"]})
    assert len(props) == 1, "an under-tried cell already has docket rows; it is reordered"
    p = props[0]
    assert p["kind"] == "hypothesis" and p["family"] == "carry" and p["source"] == "occupancy_map"
    assert p["symbols"] == ["UST10Y", "UST05Y"]
    assert om.ar.horizon_of("H1", p["params"]) == "multi_day"
    target = om.write({"at": NOW.isoformat()}, props, report=tmp_path / "OCC.json",
                      intake=tmp_path / "intake")
    assert target is not None and json.loads(target.read_text("utf-8")) == props
    assert om.write({"at": NOW.isoformat()}, [], report=tmp_path / "OCC.json",
                    intake=tmp_path / "intake2") is None


def test_build_end_to_end_on_supplied_sources() -> None:
    src = _sources()
    doc = om.build(now=NOW, loader=_panel().get, families=["carry"],
                   classes=["forex", "forex_exotics", "bonds"], banned=lambda f: False, **src)
    assert doc["totals"]["cells_occupied"] >= 3 and doc["totals"]["targets"] >= 2
    assert doc["orthogonality"]["candidates"] == 3
    cell = next(c for c in doc["cells"] if c["family"] == "carry" and c["live"])
    assert cell["hours_since_tried"] == pytest.approx(5.0)
    json.dumps(doc)                       # the artifact is serialisable as published


# ------------------------------------------------------------------------------ wiring
def test_the_leg_is_wired_hourly_before_judge_coverage() -> None:
    from libs.research import layers
    from research import hourly_cycle as hc
    assert hc.LEG_DEPARTMENT.get("occupancy_map") == "data"
    assert hc.LEG_BUDGET_SEC.get("occupancy_map")
    assert layers.LEG_LAYER.get("occupancy_map") == "information"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert src.index('_costed("occupancy_map"') < src.index('_costed("judge_coverage"')
