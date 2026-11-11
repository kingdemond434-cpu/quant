"""The Dukascopy vendor map: codes, factors, refusals and the backfill's use of them. Offline."""

from __future__ import annotations

import json
import lzma
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from research import build_dukascopy_instruments as builder
from research import dukascopy_backfill as db
from research import fetch_dukascopy as fd

MAP = json.loads(fd.INSTRUMENTS.read_text(encoding="utf-8"))

# One or more per asset class: Fusion symbol -> (vendor code, decimal factor), as published by
# dukascopy-node@1.46.4 (commit 4bb92bcb).
SAMPLE = {
    "EURUSD": ("EURUSD", 100000), "USDJPY": ("USDJPY", 1000),          # Forex
    "USDZAR": ("USDZAR", 100000), "USDTHB": ("USDTHB", 10000),          # Forex Exotics
    "AUDHUF": ("AUDHUF", 1000),
    "XAUUSD": ("XAUUSD", 1000), "XCUUSD": ("COPPERCMDUSD", 10000),      # Commodities
    "XPTUSD": ("XPTCMDUSD", 1000),
    "XTIUSD": ("LIGHTCMDUSD", 1000), "XNGUSD": ("GASCMDUSD", 10000),    # Energy
    "US500": ("USA500IDXUSD", 1000), "NAS100": ("USATECHIDXUSD", 1000),  # Indices
    "GER40": ("DEUIDXEUR", 1000), "JPN225": ("JPNIDXJPY", 1000),
    "COFARA": ("COFFEECMDUSX", 1000), "SUGAR": ("SUGARCMDUSD", 1000),   # Soft Commodity
    "UKGILT": ("UKGILTTRGBP", 1000),                                    # Bonds
    "BTCUSD": ("BTCUSD", 10), "XLMUSD": ("XLMUSD", 100000),             # Crypto
    "MATICUSD": ("MATUSD", 1000),
    "Apple": ("AAPLUSUSD", 1000), "Berkshire": ("BRKBUSUSD", 1000),     # Equities
}


def _blob(prices: list[tuple[int, float, float]], factor: float) -> bytes:
    payload = b"".join(fd.REC.pack(ms, round(a * factor), round(b * factor), 1.0, 1.0)
                       for ms, b, a in prices)
    return lzma.compress(payload, format=lzma.FORMAT_ALONE)


def test_source_is_cited_and_pinned() -> None:
    src = MAP["source"]
    assert src["commit"] == builder.SOURCE_COMMIT and len(src["commit"]) == 40
    assert src["commit"] in src["url"] and src["url"].startswith("https://raw.githubusercontent")


@pytest.mark.parametrize(("symbol", "code", "factor"),
                         [(s, c, f) for s, (c, f) in SAMPLE.items()])
def test_sample_codes_and_factors(symbol: str, code: str, factor: int) -> None:
    row = MAP["mapped"][symbol]
    assert (row["vendor_code"], row["decimal_factor"]) == (code, factor)
    assert fd.vendor_code(symbol) == code
    assert fd.point_factor(symbol) == factor
    assert f"/datafeed/{code}/2025/00/02/" in fd.hour_url(symbol, datetime(2025, 1, 2, tzinfo=UTC))


def test_every_asset_class_reached() -> None:
    classes = {r["asset_class"] for r in MAP["mapped"].values()}
    assert {"Forex", "Forex Exotics", "Commodities", "Energy", "Indices", "Soft Commodity",
            "Bonds", "Crypto", "Equities"} <= classes


def test_point_fallback_unchanged_where_the_vendor_id_is_the_fusion_name() -> None:
    # The map overrides POINT only where POINT's name was never a vendor id.
    overridden = {"XTIUSD", "XBRUSD", "XNGUSD", "XPTUSD", "XPDUSD"}
    for sym, factor in fd.POINT.items():
        if sym in overridden:
            assert fd.vendor_code(sym) != sym
            continue
        assert fd.vendor_code(sym) == sym and fd.point_factor(sym) == factor


@pytest.mark.parametrize("symbol", ["CORN", "UST10Y", "CHINAH", "SOLUSD", "NOSUCHSYM"])
def test_unknown_or_unmapped_symbol_is_refused(symbol: str) -> None:
    assert fd.point_factor(symbol) is None
    blob = _blob([(0, 1.0, 1.1)], 1000)
    with pytest.raises(KeyError):
        fd.decode_hour(blob, symbol, datetime(2025, 6, 3, 14, tzinfo=UTC))
    if symbol != "NOSUCHSYM":
        assert MAP["unmapped"][symbol]["reason"]


def test_unmapped_rows_name_a_reason() -> None:
    assert MAP["unmapped"] and all(r["reason"] for r in MAP["unmapped"].values())
    assert not set(MAP["unmapped"]) & set(MAP["mapped"])


@pytest.mark.parametrize(("symbol", "bid", "ask"), [
    ("US500", 5612.125, 5612.625), ("XNGUSD", 3.1234, 3.1279), ("BTCUSD", 64123.4, 64130.1),
    ("COFARA", 312.45, 312.6), ("USDZAR", 18.21234, 18.21534),
])
def test_synthetic_hour_decodes_on_the_vendor_scale(symbol: str, bid: float, ask: float) -> None:
    t = datetime(2025, 6, 3, 14, tzinfo=UTC)
    rows, status = fd.decode_hour(_blob([(0, bid, ask)], fd.point_factor(symbol) or 0.0), symbol, t)
    assert status == "ok"
    assert rows[0][1] == pytest.approx(bid) and rows[0][2] == pytest.approx(ask)


def test_check_scale() -> None:
    assert fd.check_scale(5600.0, 5650.0) == "OK"
    assert fd.check_scale(560.0, 5650.0) == "SCALE_MISMATCH"
    assert fd.check_scale(56000.0, 5650.0) == "SCALE_MISMATCH"
    assert fd.check_scale(5600.0, None) == "UNMEASURED"


def test_rotation_keeps_priority_and_brings_unlike_classes_early() -> None:
    rot = db.rotation()
    assert rot[:len(db.PRIORITY)] == db.PRIORITY
    assert len(rot) == len(set(rot)) == len(fd.supported_symbols())
    early = {MAP["mapped"][s]["asset_class"] for s in rot[len(db.PRIORITY):len(db.PRIORITY) + 9]}
    assert {"Indices", "Soft Commodity", "Bonds", "Crypto", "Equities"} <= early


def test_builder_maps_only_confirmed_instruments() -> None:
    meta = {
        "eurusd": {"name": "EUR/USD", "decimalFactor": 100000, "description": "Euro"},
        "usa500idxusd": {"name": "USA500.IDX/USD", "decimalFactor": 1000, "description": "S&P"},
        "aaplususd": {"name": "AAPL.US/USD", "decimalFactor": 1000, "description": "Apple"},
        "lightcmdusd": {"name": "LIGHT.CMD/USD", "description": "no factor published"},
    }
    universe = {s: {"asset_class": c} for s, c in [
        ("EURUSD", "Forex"), ("US500", "Indices"), ("Apple", "Equities"),
        ("XTIUSD", "Energy"), ("CORN", "Soft Commodity"), ("USDRUB", "Forex Exotics")]}
    doc = builder.build(universe, meta)
    assert doc["mapped"]["US500"]["vendor_code"] == "USA500IDXUSD"
    assert doc["mapped"]["Apple"]["vendor_code"] == "AAPLUSUSD"
    assert doc["mapped"]["EURUSD"]["decimal_factor"] == 100000
    assert set(doc["unmapped"]) == {"XTIUSD", "CORN", "USDRUB"}  # no factor -> no mapping


def _fake_hour(price: float):
    def fake(symbol, when, pause=0.0):
        return [(int(when.timestamp() * 1000), price, price + 0.5, 1.0, 1.0)], "ok"
    return fake


def _bars(universe_dir: Path, symbol: str, close: float, day: date) -> None:
    universe_dir.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range(pd.Timestamp(day, tz="UTC"), periods=24, freq="h")
    pd.DataFrame({"close": [close] * 24}, index=idx).to_parquet(
        universe_dir / f"{symbol}_H1.parquet")


def test_scale_mismatch_is_refused_and_not_published(tmp_path: Path, monkeypatch) -> None:
    day = date(2026, 9, 26)
    _bars(tmp_path / "uni", "US500", 560.0, day)          # broker is 10x below the vendor
    monkeypatch.setattr(db, "SYMBOLS", ("US500",))
    monkeypatch.setattr(db, "fetch_hour", _fake_hour(5600.0))
    monkeypatch.setattr(db, "fetch_day", _bound_fetch_day(tmp_path / "uni"))
    state = tmp_path / "state.json"
    report = db.run(root=tmp_path / "ticks", state_path=state,
                    report_path=tmp_path / "r.json", symbol_days=1,
                    now=datetime(2026, 9, 27, 12, tzinfo=UTC))
    assert report["scale_mismatch"] == 1 and report["written"] == 0
    assert not db._day_path(tmp_path / "ticks", "US500", day).exists()
    saved = json.loads(state.read_text())
    assert saved["refused"]["US500"]["vendor_code"] == "USA500IDXUSD"
    assert saved["next_date"]["US500"] == day.isoformat()
    assert report["coverage"]["symbols"]["US500"]["status"] == "REFUSED"


def _bound_fetch_day(universe_dir: Path):
    real = db.fetch_day

    def bound(symbol, day, root, **kw):
        kw["universe_dir"] = universe_dir
        return real(symbol, day, root, **kw)
    return bound


def test_written_day_uses_vendor_code_and_feeds_coverage(tmp_path: Path, monkeypatch) -> None:
    day = date(2026, 9, 26)
    _bars(tmp_path / "uni", "US500", 5650.0, day)
    monkeypatch.setattr(db, "SYMBOLS", ("US500",))
    monkeypatch.setattr(db, "fetch_hour", _fake_hour(5600.0))
    monkeypatch.setattr(db, "fetch_day", _bound_fetch_day(tmp_path / "uni"))
    report = db.run(root=tmp_path / "ticks", state_path=tmp_path / "s.json",
                    report_path=tmp_path / "r.json", symbol_days=1,
                    now=datetime(2026, 9, 27, 12, tzinfo=UTC))
    res = report["results"][0]
    assert res["status"] == "WRITTEN" and res["scale_check"] == "OK"
    assert res["vendor_code"] == "USA500IDXUSD"
    assert Path(res["file"]).name == "US500_ticks_20260926.parquet"   # keyed by Fusion symbol
    cov = report["coverage"]
    assert cov["symbols"]["US500"]["fetched_days"] == 1
    assert cov["universe_symbols_with_days"] == 1
    assert cov["symbols"]["CORN"]["status"] == "UNMAPPED"
    assert cov["mapped"] + cov["unmapped"] + cov["refused"] == cov["universe_symbols"]


def test_legacy_cursor_under_a_wrong_code_is_rewound_and_empties_refetched(
        tmp_path: Path, monkeypatch) -> None:
    # A pre-map state fetched XTIUSD under its Fusion name: every hour 404'd, so the days it
    # published are EMPTY. The new code rewinds to the newest day and re-fetches those empties.
    root = tmp_path / "ticks"
    empty_day = date(2026, 9, 26)
    target = db._day_path(root, "XTIUSD", empty_day)
    target.parent.mkdir(parents=True)
    pd.DataFrame({"bid": []}).to_parquet(target)
    state = tmp_path / "s.json"
    state.write_text(json.dumps({"next_date": {"XTIUSD": "2026-09-20"}, "rotation": 0}))
    monkeypatch.setattr(db, "SYMBOLS", ("XTIUSD",))
    monkeypatch.setattr(db, "fetch_hour", _fake_hour(70.0))
    monkeypatch.setattr(db, "fetch_day", _bound_fetch_day(tmp_path / "uni"))
    report = db.run(root=root, state_path=state, report_path=tmp_path / "r.json",
                    symbol_days=1, now=datetime(2026, 9, 27, 12, tzinfo=UTC))
    assert report["results"][0]["status"] == "WRITTEN"
    assert len(pd.read_parquet(target)) == 24
    saved = json.loads(state.read_text())
    assert saved["vendor_code"]["XTIUSD"] == "LIGHTCMDUSD"
    assert saved["requeue_empty_after"]["XTIUSD"] == "2026-09-20"
    assert saved["next_date"]["XTIUSD"] == "2026-09-25"
