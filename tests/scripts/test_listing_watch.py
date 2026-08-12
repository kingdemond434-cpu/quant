"""Listing watch: delisting-schedule surfacing (R0292) and the original TRADING diff.

The defect this pins: run_listing_watch filtered on status=='TRADING', so the 123 PERPETUAL
symbols carrying a REAL deliveryDate were invisible until they left the universe -- the
delisting-unwind window (§42 named ground) was over before the desk heard about it. The
schedule must come from deliveryDate != sentinel on PERPETUAL contracts only: a quarterly's
real deliveryDate is the product, not a delisting.

NO NETWORK: everything is driven through the module's own `_get` seam.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_listing_watch as lw

_DAY_MS = 86_400_000
_T0_MS = 1_780_000_000_000


def _sym(symbol: str, status: str = "TRADING", contract: str = "PERPETUAL",
         delivery: int = lw._DELIVERY_SENTINEL) -> dict:
    return {"symbol": symbol, "status": status, "contractType": contract,
            "deliveryDate": delivery}


def _wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, symbols: list[dict],
          prem: list[dict] | None = None) -> None:
    def fake_get(url: str) -> object:
        if "exchangeInfo" in url:
            return {"symbols": symbols}
        return prem or []
    monkeypatch.setattr(lw, "_get", fake_get)
    monkeypatch.setattr(lw, "_SNAP", tmp_path / "listing_universe.json")
    monkeypatch.setattr(lw, "_LOG", tmp_path / "listings.jsonl")
    monkeypatch.setattr(lw, "_SCHED", tmp_path / "delisting_schedule.json")


def _events(tmp_path: Path) -> list[dict]:
    p = tmp_path / "listings.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text("utf-8").splitlines()]


def test_baseline_writes_schedule_but_no_events(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, [
        _sym("AAAUSDT"),
        _sym("OLDUSDT", status="SETTLING", delivery=_T0_MS - 30 * _DAY_MS),
    ])
    lw.main()
    assert _events(tmp_path) == []          # first run is a baseline, never a detection
    sched = json.loads((tmp_path / "delisting_schedule.json").read_text("utf-8"))
    assert sched["n"] == 1
    assert sched["scheduled"][0]["symbol"] == "OLDUSDT"
    assert sched["scheduled"][0]["status"] == "SETTLING"
    snap = json.loads((tmp_path / "listing_universe.json").read_text("utf-8"))
    assert snap["delivery_dates"] == {"OLDUSDT": _T0_MS - 30 * _DAY_MS}


def test_trading_symbol_acquiring_delivery_date_fires_once(monkeypatch, tmp_path):
    base = [_sym("AAAUSDT"), _sym("BBBUSDT")]
    _wire(monkeypatch, tmp_path, base)
    lw.main()

    announced = [_sym("AAAUSDT"),
                 _sym("BBBUSDT", delivery=_T0_MS + 14 * _DAY_MS)]  # still TRADING
    _wire(monkeypatch, tmp_path, announced,
          prem=[{"symbol": "BBBUSDT", "lastFundingRate": "-0.0075", "markPrice": "2.5"}])
    lw.main()
    evs = _events(tmp_path)
    assert [e["event"] for e in evs] == ["delist_scheduled"]
    assert evs[0]["symbol"] == "BBBUSDT"
    assert evs[0]["funding_at_detect"] == pytest.approx(-0.0075)
    assert "delivery_ts" in evs[0] and "days_to_delivery" in evs[0]

    lw.main()                                # same schedule again: no duplicate event
    assert len(_events(tmp_path)) == 1


def test_quarterlies_never_enter_the_schedule(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, [
        _sym("AAAUSDT"),
        _sym("BTCUSDT_260327", contract="CURRENT_QUARTER", delivery=_T0_MS + 60 * _DAY_MS),
    ])
    lw.main()
    sched = json.loads((tmp_path / "delisting_schedule.json").read_text("utf-8"))
    assert sched["n"] == 0


def test_legacy_snapshot_without_delivery_key_baselines_silently(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, [
        _sym("AAAUSDT"),
        _sym("OLDUSDT", status="SETTLING", delivery=_T0_MS - 30 * _DAY_MS),
    ])
    (tmp_path / "listing_universe.json").write_text(
        json.dumps({"ts": "2026-01-01T00:00:00+00:00", "symbols": ["AAAUSDT"]}), "utf-8")
    lw.main()
    assert _events(tmp_path) == []          # no burst of pre-watch settlements as if seen today
    snap = json.loads((tmp_path / "listing_universe.json").read_text("utf-8"))
    assert snap["delivery_dates"] == {"OLDUSDT": _T0_MS - 30 * _DAY_MS}


def test_original_listing_diff_still_fires(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, [_sym("AAAUSDT")])
    lw.main()
    _wire(monkeypatch, tmp_path, [_sym("AAAUSDT"), _sym("NEWUSDT")],
          prem=[{"symbol": "NEWUSDT", "lastFundingRate": "0.03", "markPrice": "1.0"}])
    lw.main()
    evs = _events(tmp_path)
    assert [e["event"] for e in evs] == ["listed"]
    assert evs[0]["symbol"] == "NEWUSDT"
    assert evs[0]["funding_at_detect"] == pytest.approx(0.03)
