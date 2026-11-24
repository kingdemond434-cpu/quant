"""The all-producer breadth controller (rules-compliance row 13): per-producer docket shares, the
90/10 exotic fence, saturation, the frontier, the advisory steer, and the leg's wiring.

Every input is synthetic and lives in `tmp_path`; nothing here reads or writes box state.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import breadth_controller as bc  # noqa: E402

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
CLASSES = {"EURUSD": "forex", "GBPUSD": "forex", "USDJPY": "forex", "XAUUSD": "commodities",
           "US500": "indices", "USDTRY": "forex exotics", "USDZAR": "forex exotics"}


def _class_of(sym: str) -> str:
    return CLASSES.get(sym, bc.UNCLASSIFIED)


def _row(source: str, sym: str, fam: str, hours_ago: float | None, tf: str = "H1",
         lane: str = "miner_candidates.json") -> dict[str, Any]:
    r: dict[str, Any] = {"symbol": sym, "family": fam, "params": {"timeframe": tf},
                         "source": source, "producer": lane}
    if hours_ago is not None:
        r["first_seen"] = (NOW - timedelta(hours=hours_ago)).isoformat()
    return r


def _docket(tmp: Path, rows: list[dict[str, Any]], age_h: float = 0.5) -> Path:
    p = tmp / "external_survivors.json"
    p.write_text(json.dumps(rows), "utf-8")
    t = NOW.timestamp() - age_h * 3600
    os.utime(p, (t, t))
    return p


def _judge(tmp: Path, rows: list[dict[str, Any]]) -> Path:
    p = tmp / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({"at": NOW.isoformat(), "realised_pass_rate": rows}), "utf-8")
    return p


def _build(tmp: Path, docket: Path, judge: Path | None = None, **kw: Any) -> tuple[dict, dict]:
    args: dict[str, Any] = {
        "docket": docket, "judge_coverage": judge or tmp / "absent_jc.json",
        "producer_breadth": tmp / "absent_pb.json", "producer_yield": tmp / "absent_py.json",
        "generator_coverage": tmp / "absent_gc.json", "class_of": _class_of,
        "symbols": (sorted(CLASSES), "test lane"),
        "families": (["carry", "momentum", "mean_reversion"], "test census"),
        "tf_of": lambda _f: ("H1", "H4"),
    }
    args.update(kw)
    return bc.build(NOW, **args)


def _standard_rows() -> list[dict[str, Any]]:
    rows = []
    # breadth_sweep: broad, recent
    for i, s in enumerate(["EURUSD", "GBPUSD", "XAUUSD", "US500", "USDJPY"] * 4):
        rows.append(_row(f"breadth_sweep/momentum{i % 2}", s, "momentum", 2))
    # a seat via the compiler stamp, all on EURUSD forex -> NARROW
    for _ in range(25):
        rows.append(_row("miner:video_anchor_exit", "EURUSD", "carry", 3))
    # a per-hour sweep spelling folds into its organ
    rows.append(_row("gold_hour_sweep_h07_rr2", "XAUUSD", "momentum", 5, lane="x.py"))
    # a producer last seen 3 days ago -> DEAD in 24h
    rows.append(_row("orthogonal_sweep:carry", "GBPUSD", "carry", 72,
                     lane="orthogonal_candidates.json"))
    return rows


# ------------------------------------------------------------------ discovery and attribution
def test_producer_of_normalises_every_stamp_shape() -> None:
    assert bc.producer_of({"source": "miner:asia:rba_tables"}) == "asia"
    assert bc.producer_of({"source": "orthogonal_sweep:relative_value"}) == "orthogonal_sweep"
    assert bc.producer_of({"source": "breadth_sweep/carry"}) == "breadth_sweep"
    assert bc.producer_of({"source": "gold_hour_sweep_h07_rr2"}) == "gold_hour_sweep"
    assert bc.producer_of({"source": "session_chart_equivalent:x"}) == "session_chart_equivalent"
    assert bc.producer_of({"producer": "local_candidates.json"}) == "local_candidates"
    assert bc.producer_of({}) == "unattributed"


def test_producers_are_discovered_from_the_docket_and_the_rosters(tmp_path: Path) -> None:
    py = tmp_path / "PRODUCER_YIELD.json"
    py.write_text(json.dumps({"producers": [{"producer": "aaii", "verdict": "DEAD"},
                                            {"producer": "breadth_sweep",
                                             "verdict": "PRODUCING"}]}), "utf-8")
    pbr = tmp_path / "PRODUCER_BREADTH.json"
    pbr.write_text(json.dumps({"producers": {"htf_anchor_proposer":
                                             {"seats": ["video_anchor_exit"]}}}), "utf-8")
    doc, _ = _build(tmp_path, _docket(tmp_path, _standard_rows()), producer_yield=py,
                    producer_breadth=pbr)
    prods = doc["producers"]
    # discovered, not listed: the docket's stamps plus the rosters' names
    assert {"breadth_sweep", "gold_hour_sweep", "orthogonal_sweep", "aaii",
            "htf_anchor_proposer"} <= set(prods)
    # the seat stamp folded into the module that owns the seat
    assert "video_anchor_exit" not in prods
    assert prods["htf_anchor_proposer"]["cells_24h"] == 25
    assert prods["breadth_sweep"]["producer_yield_verdict"] == "PRODUCING"
    assert prods["aaii"]["known_from"] == ["PRODUCER_YIELD"]


# ------------------------------------------------------------------ shares and verdicts
def test_shares_class_split_and_verdicts(tmp_path: Path) -> None:
    doc, _ = _build(tmp_path, _docket(tmp_path, _standard_rows()))
    d, p = doc["desk"], doc["producers"]
    assert d["cells_24h"] == 46 and d["cells_7d"] == 47
    bs = p["breadth_sweep"]
    assert bs["cells_24h"] == 20 and bs["share_24h"] == round(20 / 46, 4)
    assert bs["share_7d"] == round(20 / 47, 4)
    assert bs["by_class_7d"]["forex"]["cells"] == 12
    assert bs["top_symbols_7d"][0]["cells"] == 4
    assert bs["verdict"] == "CONTRIBUTING"
    va = p["video_anchor_exit"]
    assert va["verdict"] == "NARROW" and "forex" in va["verdict_why"]
    assert p["orthogonal_sweep"]["verdict"] == "DEAD"
    assert p["orthogonal_sweep"]["cells_7d"] == 1
    # gold_hour_sweep: 1 cell, too small to be called narrow
    assert p["gold_hour_sweep"]["verdict"] == "CONTRIBUTING"
    assert "DEAD" in d["verdicts"] and "orthogonal_sweep" in d["dead"]
    assert doc["class_split"]["window_7d"]["forex"]["cells"] == 12 + 25 + 1


def test_a_roster_producer_with_no_docket_row_is_dead(tmp_path: Path) -> None:
    py = tmp_path / "PRODUCER_YIELD.json"
    py.write_text(json.dumps({"producers": [{"producer": "silent_seat"}]}), "utf-8")
    doc, _ = _build(tmp_path, _docket(tmp_path, _standard_rows()), producer_yield=py)
    row = doc["producers"]["silent_seat"]
    assert row["verdict"] == "DEAD" and row["cells_24h"] == 0
    assert "compiler" in row["verdict_why"]


# ------------------------------------------------------------------ the 90/10 exotic fence
def test_exotic_fence_pass(tmp_path: Path) -> None:
    rows = [*_standard_rows(), _row("miner:x", "USDTRY", "carry", 1)]
    doc, steer = _build(tmp_path, _docket(tmp_path, rows))
    f = doc["exotic_fence"]
    assert f["verdict"] == "PASS" and f["exotic_share_7d"] == round(1 / 48, 4)
    assert steer["exotic_fence"] == "PASS"


def test_exotic_fence_breach_steers_the_exotic_producer_away(tmp_path: Path) -> None:
    rows = _standard_rows() + [_row("miner:exo", s, "carry", 1)
                               for s in ["USDTRY", "USDZAR"] * 15]
    doc, steer = _build(tmp_path, _docket(tmp_path, rows))
    f = doc["exotic_fence"]
    assert f["verdict"] == "BREACH" and f["exotic_share_7d"] > bc.EXOTIC_CEILING
    away = steer["producers"]["exo"]["away"]["classes"]
    assert away and away[0]["class"] == "forex exotics"
    assert away[0]["missed_growth"]["e_log_w"] == bc.UNMEASURED
    # exotics are never steered TOWARD while the fence is breached
    assert all("exotic" not in c for c in steer["desk"]["toward"]["classes"])


# ------------------------------------------------------------------ UNMEASURED, never zero
def test_missing_docket_is_unmeasured_not_zero(tmp_path: Path) -> None:
    doc, steer = _build(tmp_path, tmp_path / "nope.json")
    assert doc["docket"]["status"] == "ABSENT"
    assert doc["desk"]["cells_24h"] == bc.UNMEASURED
    assert doc["exotic_fence"]["verdict"] == bc.UNMEASURED
    assert doc["frontier"]["status"] == bc.UNMEASURED
    assert "docket" in doc["unmeasured_inputs"]
    assert doc["desk"]["dead"] == []
    assert steer["advisory"] is True


def test_a_stale_docket_names_no_producer_dead(tmp_path: Path) -> None:
    doc, _ = _build(tmp_path, _docket(tmp_path, _standard_rows(), age_h=30))
    assert doc["docket"]["windows"] == bc.UNMEASURED
    assert "not rewritten" in doc["docket"]["windows_why"]
    assert set(doc["desk"]["verdicts"]) == {bc.UNMEASURED}
    assert doc["producers"]["orthogonal_sweep"]["cells_24h"] == bc.UNMEASURED


def test_a_silent_docket_is_the_merge_stalled_not_every_producer_dead(tmp_path: Path) -> None:
    rows = [_row("breadth_sweep/x", "EURUSD", "momentum", 40)]
    doc, _ = _build(tmp_path, _docket(tmp_path, rows))
    assert doc["docket"]["windows"] == bc.UNMEASURED
    assert doc["producers"]["breadth_sweep"]["verdict"] == bc.UNMEASURED


def test_a_budget_cut_stream_never_reads_as_dead(tmp_path: Path, monkeypatch: Any) -> None:
    rows = _standard_rows() * 200
    real = time.monotonic
    calls = {"n": 0}

    def clock() -> float:
        calls["n"] += 1
        return real() + (0 if calls["n"] < 3 else 10_000)
    monkeypatch.setattr(bc.time, "monotonic", clock)
    doc, _ = _build(tmp_path, _docket(tmp_path, rows), budget_s=60)
    assert doc["docket"]["status"] == "PARTIAL"
    assert "DEAD" not in doc["desk"]["verdicts"]
    assert all(r["counts_complete"] is False for r in doc["producers"].values())


def test_missing_judge_coverage_leaves_saturation_unmeasured(tmp_path: Path) -> None:
    doc, _ = _build(tmp_path, _docket(tmp_path, _standard_rows()))
    s = doc["family_saturation"]
    assert s["status"] == bc.UNMEASURED and s["saturated"] == []
    assert s["high_share_yield_unmeasured"]
    assert "family_yield" in doc["unmeasured_inputs"]


# ------------------------------------------------------------------ saturation, frontier, steer
def test_saturated_family_gets_a_floor_and_a_missed_growth_line(tmp_path: Path) -> None:
    judge = _judge(tmp_path, [
        {"family": "carry", "judged": 5000, "passed": 0},
        {"family": "momentum", "judged": 5000, "passed": 400},
        {"family": "mean_reversion", "judged": 50, "passed": 0},
    ])
    doc, steer = _build(tmp_path, _docket(tmp_path, _standard_rows()), judge)
    sat = doc["family_saturation"]
    assert [r["family"] for r in sat["saturated"]] == ["carry"]
    assert sat["desk_survivors_per_1k_judged"] == round(1000 * 400 / 10050, 3)
    assert "htf_anchor_proposer" not in steer["producers"]
    va = steer["producers"]["video_anchor_exit"]
    away = va["away"]["families"]
    assert away[0]["family"] == "carry"
    mg = away[0]["missed_growth"]
    assert mg["rail"] == "breadth_controller" and mg["floor_share"] == bc.exploration_floor()
    assert mg["acting"] is False and mg["why"]
    assert va["exploration_floor_share"] == {"carry": bc.exploration_floor()}
    assert doc["producers"]["video_anchor_exit"]["saturated_families_minted"] == ["carry"]
    # every reduction anywhere in the steer carries its line
    for prod in steer["producers"].values():
        for kind in ("families", "classes", "symbols"):
            for item in prod["away"][kind]:
                assert item["missed_growth"]["why"]


def test_frontier_names_never_sampled_cells_first(tmp_path: Path) -> None:
    doc, steer = _build(tmp_path, _docket(tmp_path, _standard_rows()))
    fr = doc["frontier"]
    assert fr["status"] == "MEASURED"
    assert fr["families_never_sampled"] == ["mean_reversion"]
    assert "USDTRY" in fr["symbols_never_sampled"]
    assert fr["space_cells"] == 3 * 2 * len(CLASSES)
    assert fr["sample"][0]["family"] == "mean_reversion"
    sampled = {(r["symbol"], r["params"]["timeframe"], r["family"]) for r in _standard_rows()}
    assert all((c["symbol"], c["timeframe"], c["family"]) not in sampled for c in fr["sample"])
    assert "H4" in fr["timeframes_never_sampled"]
    t = steer["producers"]["breadth_sweep"]["toward"]
    assert t["families_frontier"] == ["mean_reversion"]
    assert "USDTRY" in t["symbols"]
    assert steer["desk"]["toward"]["cells_frontier_first"][0]["family"] == "mean_reversion"


def test_writes_are_atomic_and_land_both_files(tmp_path: Path) -> None:
    doc, steer = _build(tmp_path, _docket(tmp_path, _standard_rows()))
    out, so = bc.write(doc, steer, tmp_path / "r" / "BREADTH_CONTROLLER.json",
                       tmp_path / "d" / "breadth_controller_steer.json")
    assert json.loads(out.read_text("utf-8"))["schema"] == bc.SCHEMA
    st = json.loads(so.read_text("utf-8"))
    assert st["schema"] == bc.STEER_SCHEMA and st["advisory"] is True
    assert not list(tmp_path.rglob("*.tmp"))


def test_budget_follows_the_cycle_cap(monkeypatch: Any) -> None:
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "300")
    assert bc._budget(420) == 240
    monkeypatch.delenv("QUANT_LEG_BUDGET_S")
    assert bc._budget(420) == 420


# ------------------------------------------------------------------ wiring
def test_the_leg_is_on_a_clock_in_a_department_a_layer_and_the_results() -> None:
    hc = importlib.import_module("research.hourly_cycle")
    from libs.research.layers import LEG_LAYER
    assert hc.department_of("breadth_controller") == "meta"
    assert LEG_LAYER["breadth_controller"] == "meta"
    assert hc.LEG_BUDGET_SEC["breadth_controller"] > 420
    # no floor of its own (the floor set is pinned): it self-stops under QUANT_LEG_BUDGET_S instead
    assert "breadth_controller" not in hc.LEG_BUDGET_FLOOR_SEC
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert ('_producer(\n        "breadth_controller", "research/breadth_controller.py", '
            '"--budget-s", "420")') in src
    assert '"breadth_controller": bcl' in src
    side = _ROOT / "docs" / "research" / "runtime_state.d"
    rows = [json.loads(p.read_text("utf-8")) for p in side.glob("leg~breadth_controller-*.json")]
    assert rows and rows[0]["organ"] == "leg:breadth_controller"
    assert rows[0]["artifact"] == "desks/mt5/reports/BREADTH_CONTROLLER.json"
