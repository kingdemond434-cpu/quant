"""R0122b unstructured event collector -- latency is the edge, and fabrication is the enemy."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scripts.collect_announcements import (
    TRADEABLE_MAX_AGE_MIN,
    _iso,
    _symbols,
    _tier,
    _upbit_items,
    collect,
)


def _item(title: str, minutes_old: float | None, **kw):
    pub = (None if minutes_old is None else
           (datetime.now(tz=UTC) - timedelta(minutes=minutes_old)).isoformat())
    return {"source": "okx", "title": title, "body": "", "url": "", "published_at": pub, **kw}


def test_rfc822_and_epoch_timestamps_both_parse():
    # 55 of 80 items on the first live run reported UNMEASURED latency purely because RSS
    # publishes RFC-822 and only ISO was handled.
    assert _iso("Fri, 31 Jul 2026 12:00:00 GMT").startswith("2026-07-31T12:00")
    assert _iso(1785000000).startswith("20")
    assert _iso(1785000000000).startswith("20")          # ms
    assert _iso("not a date") is None                     # absent stays absent


def test_symbols_are_whitelisted_never_english_words():
    # The live run extracted ACROSS/BANKS/AN/AS/LED as "symbols" from ordinary headlines.
    assert _symbols("Global banks test tokenized money across borders as led by BIS") == []
    assert _symbols("OKX to list BTC and SOL perpetuals") == ["BTC", "SOL"]


def test_tiers_rank_forced_repositioning_first():
    assert _tier("Binance will delist XYZ") == 1          # someone MUST reposition
    assert _tier("OKX to list ABC/USDT") == 2
    assert _tier("Website UI refresh") == 3


def test_stale_archive_is_not_tradeable(tmp_path):
    # The first live run ingested the 2021 CREAM exploit as breaking tier-1 news.
    rep = collect(tmp_path, [_item("Massive exploit drains protocol", 3_000_000)], {})
    row = json.loads((tmp_path / "data/exchange_announcements.jsonl").read_text())
    assert row["tier"] == 1 and row["tradeable"] is False
    assert "history, not news" in row["not_tradeable_reason"]
    assert rep["n_tradeable"] == 0


def test_unmeasured_latency_is_not_tradeable(tmp_path):
    # "We do not know how old this is" must never be treated as "it is fresh" (L1.28a).
    collect(tmp_path, [_item("Exchange will delist FOO", None)], {})
    row = json.loads((tmp_path / "data/exchange_announcements.jsonl").read_text())
    assert row["tradeable"] is False and "age unknown" in row["not_tradeable_reason"]


def test_fresh_material_item_is_tradeable(tmp_path):
    rep = collect(tmp_path, [_item("OKX will delist BTC margin pairs", 12)], {})
    row = json.loads((tmp_path / "data/exchange_announcements.jsonl").read_text())
    assert row["tradeable"] is True and row["tier"] == 1 and row["symbols"] == ["BTC"]
    assert rep["n_tradeable"] == 1 and row["latency_minutes"] <= TRADEABLE_MAX_AGE_MIN


def test_dedup_across_runs(tmp_path):
    collect(tmp_path, [_item("OKX to list ABC", 5)], {})
    rep2 = collect(tmp_path, [_item("OKX to list ABC", 5)], {})
    assert rep2["n_new"] == 0                             # an item seen once is not news twice


def test_source_failures_are_recorded_not_hidden(tmp_path):
    live = ("okx_announcements", "upbit_announcements", "defillama_hacks",
            "coindesk", "cointelegraph")
    rep = collect(tmp_path, [], dict.fromkeys(live, "down"))
    assert rep["status"] == "ALL-SOURCES-DOWN"            # never looks like a quiet news day
    assert len(rep["source_errors"]) == 5


def test_standing_blocks_never_count_toward_all_down(tmp_path):
    # binance/bybit are constants of this egress, recorded on every run. Before the split,
    # 2 standing + 2 real failures read ALL-SOURCES-DOWN while both RSS feeds were healthy.
    rep = collect(tmp_path, [], {"binance_announcements": "std", "bybit_announcements": "std",
                                 "okx_announcements": "down", "defillama_hacks": "down"})
    assert rep["status"] == "DEGRADED"


def test_upbit_published_at_is_first_listed_at_never_listed_at():
    # Upbit bumps listed_at on every edit/re-pin; the two differ on 42.5% of rows (median
    # 2.08d). Keying on listed_at would fabricate freshness for re-pinned history (R0298).
    doc = {"success": True, "data": {"notices": [{
        "id": 6458, "title": "BTC, USDT 마켓 신규 거래지원 안내 (CYS)", "category": "거래",
        "listed_at": "2026-08-11T18:10:00+09:00",
        "first_listed_at": "2026-08-10T11:05:54+09:00"}]}}
    (it,) = _upbit_items(doc)
    assert it["published_at"].startswith("2026-08-10T11:05")   # NOT the 08-11 bump
    assert it["source"] == "upbit" and "notice?id=6458" in it["url"]


def test_upbit_korean_titles_tier_like_english():
    assert _tier("가상자산 거래지원 종료 안내 (XYZ)") == 1        # delisting forces repositioning
    assert _tier("레이븐코인(RVN) 거래 유의 종목 지정 안내") == 1  # DAXA caution designation
    assert _tier("프롬(PROM) KRW, USDT 마켓 디지털 자산 추가") == 2  # listing
    assert _tier("BTC, USDT 마켓 신규 거래지원 안내 (CYS)") == 2


def test_upbit_malformed_payload_yields_nothing():
    assert _upbit_items(None) == []
    assert _upbit_items({"data": {}}) == []
    assert _upbit_items({"data": {"notices": [{"id": 1}]}}) == []   # titleless row dropped
