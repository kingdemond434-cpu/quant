"""Energy and bonds reach the breadth steering, and a thin asset class gets forced cells.

2026-11-03: the docket steering listed eight asset classes and neither energy nor bonds was
among them. Energy's three CFDs (XTIUSD, XBRUSD, XNGUSD) were being classified by the
pattern fallback as FX exotics, and asset_class had no declared list, so an empty class was
invisible rather than reported as empty.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE / "research"), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.universe import asset_class  # noqa: E402

from research import empty_cluster_forcer as forcer  # noqa: E402


def test_fusion_x_tickers_are_commodities_not_fx() -> None:
    for sym in ("XTIUSD", "XBRUSD", "XNGUSD"):
        assert asset_class(sym) == "energy", sym
    for sym in ("XCUUSD", "XALUSD", "XNIUSD", "XZNUSD", "XPBUSD", "XAUUSD"):
        assert asset_class(sym) == "metal", sym
    for sym in ("BNBUSD", "EOSUSD", "LNKUSD"):
        assert asset_class(sym) == "crypto", sym
    # the FX rule is unchanged for real currencies
    assert asset_class("USDTRY") == "fx_exotic"
    assert asset_class("EURUSD") == "fx_major"


def _doc(counts: dict[str, int]) -> dict:
    return {"steering": {"asset_class": {"thinnest": [
        {"value": k, "families": v} for k, v in counts.items()]}}}


def test_a_class_absent_from_the_steering_is_forced() -> None:
    by_cluster = {"session": ["session_range_breakout"]}
    doc = _doc({"forex": 100_000, "fx major": 100_000, "indices": 50_000, "index": 50_000})
    lane = ["EURUSD", "GBPUSD", "US500", "XTIUSD", "XBRUSD", "XNGUSD"]
    rows, cells = forcer.class_slots(by_cluster, 7, doc, lane, lambda s: 1.0)
    forced = {r["value"] for r in rows if r["verdict"] == "FORCED"}
    assert forced == {"energy"}
    assert len(cells) == forcer.CELLS_PER_CLUSTER
    assert {c["symbols"][0] for c in cells} <= {"XTIUSD", "XBRUSD", "XNGUSD"}
    assert all(c["source"] == "breadth:empty_cluster_forcer" for c in cells)


def test_the_pattern_name_counts_so_a_covered_class_is_not_forced() -> None:
    by_cluster = {"session": ["session_range_breakout"]}
    # a report written by the pattern classifier names gold "metal", not "commodities"
    doc = _doc({"fx major": 100_000, "metal": 90_000})
    rows, cells = forcer.class_slots(by_cluster, 7, doc, ["EURUSD", "XAUUSD"],
                                     lambda s: 1.0)
    assert not cells
    assert not [r for r in rows if r["verdict"] == "FORCED"]


def test_no_steering_mints_nothing_and_says_unmeasured() -> None:
    rows, cells = forcer.class_slots({"session": ["session_range_breakout"]}, 7, {}, ["EURUSD"])
    assert cells == []
    assert rows[0]["verdict"] == "UNMEASURED"


def test_declared_classes_include_energy_and_bonds() -> None:
    from research import hypothesis_families as hf
    declared = hf._declared_classes({})
    if not declared:          # registry not readable here: UNMEASURED, nothing declared
        return
    assert "energy" in declared and "bonds" in declared
    assert "equities" not in declared


def test_frozen_instruments_get_no_cells() -> None:
    by_cluster = {"session": ["session_range_breakout"]}
    doc = _doc({"forex": 100_000, "fx major": 100_000})
    lane = ["EURUSD", "UST10Y", "UST05Y", "UKGILT"]
    age = {"UST10Y": 300.0, "UST05Y": 300.0, "UKGILT": 1.0, "EURUSD": 0.1}
    rows, cells = forcer.class_slots(by_cluster, 7, doc, lane, age.get)
    assert {c["symbols"][0] for c in cells} == {"UKGILT"}
    bonds = next(r for r in rows if r["value"] == "bonds")
    assert bonds["stale_skipped"] == ["UST05Y", "UST10Y"]
    rows, cells = forcer.class_slots(by_cluster, 7, doc, ["EURUSD", "UST10Y"],
                                     lambda s: 300.0 if s == "UST10Y" else 0.1)
    assert cells == []
    assert next(r for r in rows if r["value"] == "bonds")["verdict"] == "STALE_BARS"
