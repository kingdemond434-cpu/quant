"""SOURCE_CONVERSION: counts per source, FAULT flags, UNMEASURED on absence, exotic exclusion."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.frontier_identity import docket_cell_id  # noqa: E402

from research import source_conversion as sc  # noqa: E402


def _w(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _desk(tmp: Path, rows: list[dict[str, Any]], *, seen: list[str] | None = None) -> Path:
    _w(tmp / "data/universe/universe.json", {"EURUSD": {}, "XAUUSD": {}, "GBPUSD": {},
                                             "EURZAR": {}})
    _w(tmp / "data/asia_sources.json", {"sources": [{"id": "pack_a"}, {"id": "pack_b"}]})
    _w(tmp / "data/hypotheses/miner_candidates.json", {"hypotheses": rows})
    if seen is not None:
        _w(tmp / "data/hypotheses/gauntlet_seen_cells.json", dict.fromkeys(seen, "t"))
    return tmp


def _row(sym: str, fam: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"symbol": sym, "family": fam, "params": params or {}}


def test_counts_faults_and_reach(tmp_path: Path) -> None:
    rows = [_row("EURUSD", "exogenous_conditioner", {"source": "pack_a", "signal": "x"}),
            _row("XAUUSD", "exogenous_conditioner", {"source": "pack_a", "signal": "x"}),
            _row("EURUSD", "exogenous_conditioner", {"source": "pack_b", "signal": "y"}),
            _row("EURUSD", "jump")]
    seen = [docket_cell_id(rows[0]), docket_cell_id(rows[3])]
    doc = sc.build(_desk(tmp_path, rows, seen=seen))
    by = {r["source"]: r for r in doc["sources"]}
    assert by["pack_a"]["mined"] == 2 and by["pack_a"]["judged"] == 1
    assert by["pack_a"]["instruments_reached_mined"] == 2
    assert by["pack_a"]["fault"] is False
    assert by["pack_b"]["fault_reason"] == "ZERO_JUDGED"
    assert by["price_bars"]["mined"] == 1 and by["price_bars"]["judged"] == 1
    assert doc["status"] == "FAULT" and doc["judged_basis"] == "gauntlet_seen_cells"


def test_never_mined_when_source_exists_and_unnamed(tmp_path: Path) -> None:
    doc = sc.build(_desk(tmp_path, [_row("EURUSD", "jump")], seen=[]))
    by = {r["source"]: r for r in doc["sources"]}
    assert by["pack_a"]["fault_reason"] == "NEVER_MINED"
    assert by["pack_a"]["mined"] == 0


def test_absent_judged_input_is_unmeasured_not_zero(tmp_path: Path) -> None:
    rows = [_row("EURUSD", "exogenous_conditioner", {"source": "pack_a"})]
    doc = sc.build(_desk(tmp_path, rows, seen=None))
    by = {r["source"]: r for r in doc["sources"]}
    assert by["pack_a"]["judged"] is None
    assert by["pack_a"]["fault"] is False
    assert any("judged" in u for u in by["pack_a"]["unmeasured"])
    assert by["pack_a"]["certified"] is None and by["pack_a"]["live"] is None


def test_no_docket_means_mined_unmeasured_and_no_fault(tmp_path: Path) -> None:
    _w(tmp_path / "data/universe/universe.json", {"EURUSD": {}})
    _w(tmp_path / "data/asia_sources.json", {"sources": [{"id": "pack_a"}]})
    doc = sc.build(tmp_path)
    by = {r["source"]: r for r in doc["sources"]}
    assert by["pack_a"]["mined"] is None and by["pack_a"]["fault"] is False
    assert doc["status"] == "UNMEASURED"


def test_exotics_are_set_aside_and_never_reached(tmp_path: Path) -> None:
    rows = [_row("EURZAR", "exogenous_conditioner", {"source": "pack_a"}),
            _row("EURUSD", "exogenous_conditioner", {"source": "pack_a"})]
    doc = sc.build(_desk(tmp_path, rows, seen=[]))
    assert doc["eligible_universe"]["n"] == 3
    assert doc["eligible_universe"]["exotics_set_aside"] == 1
    assert doc["cells"]["rows_exotic_set_aside"] == 1
    by = {r["source"]: r for r in doc["sources"]}
    assert by["pack_a"]["mined"] == 1 and by["pack_a"]["instruments_reached_mined"] == 1


def test_certified_and_live_attribute_by_family(tmp_path: Path) -> None:
    rows = [_row("EURUSD", "cot_positioning")]
    d = _desk(tmp_path, rows, seen=[docket_cell_id(rows[0])])
    _w(d / "reports/UNIVERSAL_SURVIVORS.json", {"survivors": {
        "h.a": {"cell": "EURUSD.cot_positioning.p=1", "sym": "EURUSD"},
        "h.b": {"cell": "EURZAR.jump.p=2", "sym": "EURZAR"}}})
    _w(d / "data/sleeves.json", {"sleeves": [
        {"symbol": "XAUUSD", "family": "cot_positioning", "status": "LIVE"},
        {"symbol": "XAUUSD", "family": "cot_positioning", "status": "RETIRED"}]})
    doc = sc.build(d)
    by = {r["source"]: r for r in doc["sources"]}
    assert by["cot"]["certified"] == 1 and by["cot"]["live"] == 1
    assert by["price_bars"]["certified"] == 0   # the exotic survivor is excluded


def test_cross_asset_link_counted(tmp_path: Path) -> None:
    rows = [_row("EURUSD", "lead_lag", {"driver_symbol": "XAUUSD"})]
    doc = sc.build(_desk(tmp_path, rows, seen=[]))
    by = {r["source"]: r for r in doc["sources"]}
    assert by["price_bars"]["cross_asset_cells"] == 1


def test_health_board_reads_fault_as_red(tmp_path: Path) -> None:
    from research import health_board as hb
    p = tmp_path / "SC.json"
    _w(p, {"status": "FAULT", "n_faults": 2})
    doc = hb.build(runtime=tmp_path / "x", events=tmp_path / "e", acceptance=tmp_path / "a",
                   stall=tmp_path / "s", readers={"source_conversion": p})
    row = next(o for o in doc["organs"] if o["organ"] == "reader:source_conversion")
    assert row["verdict"] == "RED"


def test_headline_non_exotic_certified(tmp_path: Path) -> None:
    d = _desk(tmp_path, [_row("EURUSD", "jump")], seen=[])
    _w(d / "reports/UNIVERSAL_SURVIVORS.json", {"survivors": {
        "h.a": {"cell": "EURUSD.jump.p=1", "sym": "EURUSD"},
        "h.b": {"cell": "XAUUSD.jump.p=3", "sym": "XAUUSD"},
        "h.c": {"cell": "EURZAR.jump.p=2", "sym": "EURZAR"}}})
    h = sc.build(d)["headline"]
    assert h["total_certified"] == 3 and h["non_exotic_certified"] == 2
    assert h["exotic_certified"] == 1 and abs(h["exotic_share"] - 1 / 3) < 1e-3
    assert h["non_exotic_by_family"] == {"jump": 2}
    assert h["non_exotic_by_source"] == {"price_bars": 2}


def test_headline_unmeasured_without_survivors(tmp_path: Path) -> None:
    h = sc.build(_desk(tmp_path, [_row("EURUSD", "jump")], seen=[]))["headline"]
    assert h["non_exotic_certified"] is None and h["status"] == "UNMEASURED"


def test_widened_targets_never_exotic(monkeypatch: Any) -> None:
    from research import pack_cells as pc
    monkeypatch.setattr(pc, "universe_symbols",
                        lambda: frozenset({"EURUSD", "XAUUSD", "GBPUSD", "EURZAR"}))
    got = pc.widen_targets(["EURUSD"], 0, k=10)
    assert "EURZAR" not in got and got[0] == "EURUSD"
    assert set(got) == {"EURUSD", "XAUUSD", "GBPUSD"}
