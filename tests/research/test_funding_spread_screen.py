"""R0115 cross-exchange funding-spread screen -- the candidate 2nd sleeve's Stage-A machinery."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.screen_funding_spread import (
    _hour_key,
    _norm_symbol,
    build_report,
    build_spreads,
    summarise,
)


def _write(root: Path, rel: str, rows: list[dict]) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")


def test_symbol_normalisation_makes_the_cross_venue_join_possible():
    # A silent join failure produces an empty screen that LOOKS like an honest null.
    assert _norm_symbol("BTCUSDT") == _norm_symbol("XBTUSD") == _norm_symbol("BTC") == "BTC"
    assert _norm_symbol("ETH-PERP") == "ETH"


def test_hour_bucketing_handles_iso_and_epoch_ms():
    assert _hour_key("2026-07-31T14:23:11Z") == "2026-07-31T14"
    assert _hour_key(1785000000000) == _hour_key(1785000000)     # ms and s agree


def test_spread_is_computed_per_pair_and_symbol(tmp_path):
    _write(tmp_path, "data/bitmex_funding.jsonl",
           [{"timestamp": "2026-07-31T08:00:00Z", "symbol": "XBTUSD", "fundingRate": 0.0010}])
    _write(tmp_path, "data/hyperliquid_funding.jsonl",
           [{"timestamp": "2026-07-31T08:12:00Z", "coin": "BTC", "hl_funding": 0.0002}])
    sp = build_spreads(tmp_path)
    rows = sp["pairs"]["bitmex|hyperliquid"]
    assert len(rows) == 1
    assert abs(rows[0]["spread"] - 0.0008) < 1e-12       # 8 bps apart, joined across formats


def test_below_cost_spread_is_called_unharvestable(tmp_path):
    _write(tmp_path, "data/bitmex_funding.jsonl",
           [{"timestamp": f"2026-07-31T{h:02d}:00:00Z", "symbol": "BTC", "fundingRate": 0.0001}
            for h in range(20)])
    _write(tmp_path, "data/hyperliquid_funding.jsonl",
           [{"timestamp": f"2026-07-31T{h:02d}:00:00Z", "coin": "BTC", "hl_funding": 0.00009}
            for h in range(20)])
    s = summarise(build_spreads(tmp_path), round_trip_bps=8.0)
    assert "UNHARVESTABLE" in s["bitmex|hyperliquid"]["verdict"]


def test_wide_spread_is_a_harvestable_candidate(tmp_path):
    _write(tmp_path, "data/bitmex_funding.jsonl",
           [{"timestamp": f"2026-07-31T{h:02d}:00:00Z", "symbol": "BTC", "fundingRate": 0.0030}
            for h in range(20)])
    _write(tmp_path, "data/hyperliquid_funding.jsonl",
           [{"timestamp": f"2026-07-31T{h:02d}:00:00Z", "coin": "BTC", "hl_funding": 0.0001}
            for h in range(20)])
    s = summarise(build_spreads(tmp_path), round_trip_bps=8.0)
    assert s["bitmex|hyperliquid"]["verdict"] == "HARVESTABLE-CANDIDATE"
    assert s["bitmex|hyperliquid"]["pct_above_round_trip_cost"] == 100.0


def test_no_overlap_reports_unmeasured_not_a_null(tmp_path):
    # The critical honesty property: "we could not measure" must never read as "no edge".
    rep = build_report(tmp_path)
    assert rep["status"] == "NO-DATA"
    assert "UNMEASURED, not a null" in rep["detail"]
    assert set(rep["venues_absent"]) == {"bitmex", "hyperliquid", "binance"}


def test_screen_claims_no_promotion_authority():
    rep = build_report(Path("."))
    assert "STAGE A ONLY" in rep["authority"]
    assert "never" in rep["authority"] and "capital" in rep["authority"]
    src = Path("scripts/screen_funding_spread.py").read_text("utf-8")
    for banned in ("place_order", "place_market", "place_post_only"):
        assert banned not in src               # a screen that can trade is not a screen
