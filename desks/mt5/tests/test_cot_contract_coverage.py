"""Every non-exotic MT5 instrument with a CFTC contract is mapped; the rest are listed, never guessed.

MEASURED on 013f0b3f76: 1,428 raw-COT cells probed `cot_mapping`, 36 `cot_file:eur.parquet`, and
1,411 `cot_positioning` cells `cot_series:<SYM>` (data/cot_zcache.parquet had 11 columns).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
sys.path.insert(0, str(ROOT))

from mt5desk import cot_contracts as cc  # noqa: E402

_spec = importlib.util.spec_from_file_location("refresh_cot_zcache",
                                               ROOT / "scripts" / "refresh_cot_zcache.py")
rz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rz)

UNI = json.loads((ROOT / "desks/mt5/data/universe/universe.json").read_text())
LIVE = json.loads((ROOT / "desks/mt5/data/observables/cftc_cot_live.json").read_text())
NAMES = {r["market_and_exchange_names"] for r in LIVE["raw"]}


def _symbols(*classes):
    return sorted(k for k, v in UNI.items() if not k.startswith("_")
                  and v.get("asset_class") in classes)


def test_the_old_twenty_still_map_the_same() -> None:
    old = {"XAUUSD": "gold", "XAGUSD": "silver", "USDJPY": "jpy", "EURJPY": "jpy",
           "GBPJPY": "jpy", "CADJPY": "jpy", "AUDJPY": "jpy", "NZDJPY": "jpy", "CHFJPY": "jpy",
           "EURUSD": "eur", "EURGBP": "eur", "EURCHF": "eur", "GBPUSD": "gbp", "USDCAD": "cad",
           "AUDUSD": "aud", "NZDUSD": "nzd", "USDCHF": "chf", "DXY": "dxy", "SP500": "sp500",
           "NDX": "nasdaq100"}
    assert {k: cc.SYMBOL_SLUG[k] for k in old} == old


def test_every_non_exotic_fx_pair_in_the_registry_is_mapped_and_exotics_never() -> None:
    fx = [s for s in _symbols("Forex") if cc.fx_legs(s)]
    assert len(fx) == 28 and set(fx) == set(cc.FX_PAIRS)
    for s in fx:
        assert s in cc.SYMBOL_SLUG
    for s in _symbols("Forex Exotics"):
        assert s not in cc.SYMBOL_SLUG and s not in cc.ZCACHE_DIRECT
    # USDHKD sits under "Forex" in the registry but HKD is outside the allowed legs
    assert "USDHKD" not in cc.SYMBOL_SLUG and "USDHKD" in cc.UNMAPPED


def test_no_mapped_symbol_carries_an_exotic_leg() -> None:
    for s in list(cc.SYMBOL_SLUG) + list(cc.ZCACHE_DIRECT):
        if len(s) == 6 and s.isalpha() and s[:3] in cc.ALLOWED_FIAT + ("XAU", "XAG", "XPT",
                                                                       "XPD", "XTI", "XBR",
                                                                       "XNG", "XCU", "BTC", "ETH"):
            legs = cc.fx_legs(s)
            if legs:
                assert set(legs) <= set(cc.ALLOWED_FIAT)


def test_every_non_equity_instrument_is_mapped_or_named_unmapped() -> None:
    for s in _symbols("Commodities", "Soft Commodity", "Energy", "Bonds", "Indices", "Crypto"):
        assert s in cc.SYMBOL_SLUG or s in cc.UNMAPPED, s
        assert not (s in cc.SYMBOL_SLUG and s in cc.UNMAPPED), s


def test_every_slug_has_an_address() -> None:
    for slug in set(cc.SYMBOL_SLUG.values()):
        assert slug in cc.LEGACY_SLUGS or slug in cc.MARKETS or slug in cc.CODES, slug
    # eur had the legacy route only and never landed: it now has an exact-market fallback too
    assert "eur" in cc.MARKETS


def test_every_market_name_is_spelled_as_the_cftc_feed_spells_it() -> None:
    for name in list(cc.MARKETS.values()) + [n for ns in cc.ZCACHE_DIRECT.values() for n in ns]:
        assert name in NAMES, name


def test_zcache_covers_every_mapped_symbol_with_a_contract() -> None:
    cols = set(rz.NEEDLES) | set(cc.ZCACHE_DIRECT) | set(cc.FX_PAIRS) | set(cc.ZCACHE_ALIAS)
    for s in cc.SYMBOL_SLUG:
        if s in ("DXY", "SP500", "NDX"):       # registry-less aliases of USDX/US500/NAS100
            continue
        assert s in cols, f"{s} has a raw-file mapping but no zcache column"


def _dates(n=300):
    return pd.date_range("2018-01-02", periods=n, freq="7D", tz="UTC")


def _cache(cols):
    idx = _dates()
    return pd.DataFrame({c: [math.sin(i / 7.0 + k) for i in range(len(idx))]
                         for k, c in enumerate(cols)}, index=idx)


def _raw(name, n=300, mult=1.0):
    return [{"market_and_exchange_names": name,
             "report_date_as_yyyy_mm_dd": d.strftime("%Y-%m-%dT00:00:00.000"),
             "noncomm_positions_long_all": str(1000 + i * mult + 50 * math.sin(i)),
             "noncomm_positions_short_all": str(500 + 3 * i % 40)}
            for i, d in enumerate(_dates(n))]


def test_direct_columns_are_built_from_full_history_and_unmatched_are_reported() -> None:
    out = _cache(["EURUSD"])
    rows = _raw(cc.ZCACHE_DIRECT["UST10Y"][0])
    out, built, unmatched = rz.backfill_direct(
        out, {"UST10Y": cc.ZCACHE_DIRECT["UST10Y"], "CORN": cc.ZCACHE_DIRECT["CORN"]},
        fetch_markets=lambda names: rows)
    assert built == ["UST10Y"] and unmatched == ["CORN"] and "CORN" not in out.columns
    assert out["UST10Y"].dropna().shape[0] >= 250       # 52-week reader floor met


def test_a_failed_history_fetch_leaves_banked_columns_alone() -> None:
    out = _cache(["EURUSD", "US500"])
    before = out["US500"].copy()

    def boom(names):
        raise OSError("down")
    out, built, unmatched = rz.backfill_direct(out, {"US500": cc.ZCACHE_DIRECT["US500"]},
                                               fetch_markets=boom)
    assert built == [] and unmatched == ["US500"] and out["US500"].equals(before)


def test_crosses_are_built_from_legs_and_usd_pairs_are_not_touched() -> None:
    out = _cache(["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD",
                  "XAUUSD", "XAGUSD"])
    out, derived, skipped = rz.derive_columns(out, cc)
    assert skipped == {}
    s2 = math.sqrt(2.0)
    assert ((out["EURGBP"] - (out["EURUSD"] - out["GBPUSD"]) / s2).abs() < 1e-12).all()
    # JPY leg is the NEGATED USDJPY column
    assert ((out["EURJPY"] - (out["EURUSD"] + out["USDJPY"]) / s2).abs() < 1e-12).all()
    assert ((out["CADJPY"] - (-out["USDCAD"] + out["USDJPY"]) / s2).abs() < 1e-12).all()
    assert ((out["XAUEUR"] - out["XAUUSD"]).abs() < 1e-12).all()
    for pair in cc.FX_PAIRS:
        if "USD" in pair:
            assert pair not in derived
        else:
            assert pair in out.columns
    assert not any(c in out.columns for c in ("USDHKD", "USDMXN"))


def test_a_cross_with_a_missing_leg_is_skipped_by_name() -> None:
    out = _cache(["EURUSD", "GBPUSD"])
    out, derived, skipped = rz.derive_columns(out, cc)
    assert "EURGBP" in derived and "EURJPY" in skipped and "NZDCAD" in skipped
