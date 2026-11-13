"""A cell certified on a resting LIMIT order may not hold capital while the gateway can only send
market orders (audit of #222, 2026-10-07): the boundary in `mt5desk.executables` names it
PENDING_EXECUTOR, and the law-gate fence fails when such a row is LIVE or STANDBY."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import executables as ex  # noqa: E402


def test_a_market_or_unstyled_row_has_no_gap() -> None:
    assert ex.order_style_gap({}) is None
    assert ex.order_style_gap({"execution_style": "market"}) is None
    assert ex.order_style_gap({"entry_style": ""}) is None
    assert ex.order_style_gap(None) is None


def test_a_limit_row_is_pending_executor_by_name() -> None:
    for key in ex.ORDER_STYLE_KEYS:
        why = ex.order_style_gap({key: "Limit"})
        assert why is not None and why.startswith(ex.PENDING_EXECUTOR)
        assert f"{key}='limit'" in why and "market orders" in why


def test_the_clock_key_carries_the_style() -> None:
    import shadow_forward as sf

    key = sf.sleeve_key("EURUSD", "continuous", {"execution_style": "limit", "lookback": 5},
                        "trend_ma_cross")
    assert (ex.order_style_gap_of_key(key) or "").startswith(ex.PENDING_EXECUTOR)
    plain = sf.sleeve_key("EURUSD", "continuous", {"lookback": 5}, "trend_ma_cross")
    assert ex.order_style_gap_of_key(plain) is None
    assert ex.order_style_gap_of_key("A.f.w#entry_style=limit_lookback=5").startswith(
        ex.PENDING_EXECUTOR)


def test_the_day_the_executor_lands_the_gap_closes(monkeypatch) -> None:
    monkeypatch.setattr(ex, "GATEWAY_ORDER_STYLES", frozenset({"", "market", "limit"}))
    assert ex.order_style_gap({"execution_style": "limit"}) is None


def _write(p: Path, doc: object) -> Path:
    p.write_text(json.dumps(doc), "utf-8")
    return p


def test_the_fence_fails_on_a_live_or_standby_limit_row(tmp_path) -> None:
    import check_order_style_executor as fence

    roster = _write(tmp_path / "sleeves.json", {"sleeves": [
        {"name": "XAUUSD.x.asia", "status": "LIVE", "params": {}},
        {"name": "EURUSD.f.w#execution_style=limit", "status": "STANDBY",
         "params": {"execution_style": "limit"}},
        {"name": "GBPUSD.f.w#execution_style=limit", "status": "RETIRED",
         "params": {"execution_style": "limit"}}]})
    registry = _write(tmp_path / "reg.json", {"sleeves": {
        "USDJPY.f.w#entry_style=limit": {"status": "LIVE", "identity": {"params": {}}}}})
    rep = fence.scan(roster, registry)
    assert rep["status"] == ex.PENDING_EXECUTOR and rep["n_judged"] == 3
    assert sorted(p["name"] for p in rep["pending"]) == [
        "EURUSD.f.w#execution_style=limit", "USDJPY.f.w#entry_style=limit"]
    assert fence.main(["--roster", str(roster), "--registry", str(registry),
                       "--report", str(tmp_path / "r.json")]) == 2


def test_the_fence_passes_a_market_book_and_names_an_absent_host(tmp_path) -> None:
    import check_order_style_executor as fence

    roster = _write(tmp_path / "sleeves.json", {"sleeves": [
        {"name": "XAUUSD.x.asia", "status": "LIVE", "params": {"execution_style": "market"}}]})
    assert fence.scan(roster, tmp_path / "absent.json")["status"] == "OK"
    gone = fence.scan(tmp_path / "a.json", tmp_path / "b.json")
    assert gone["status"] == "NOT-READABLE-HERE"
    empty = _write(tmp_path / "e.json", {"sleeves": []})
    assert fence.scan(empty, tmp_path / "b.json")["status"] == "UNMEASURED"
