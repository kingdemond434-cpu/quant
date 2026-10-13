"""BTC on-chain explorer state and the access-record rows, on fixtures only.

The mempool.space responses are HAND-BUILT in the shape the live API returned to a WebFetch probe
on 2026-10-13 (`fixtures/free_stack/mempool_*.synthetic.json`); no test touches the network.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "free_stack"
ROSTER = _DESK / "data" / "free_stack_sources.json"
#: 2026-09-23 12:00 UTC -- after every fixture block.
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _row(rid: str) -> dict:
    doc = json.loads(ROSTER.read_text("utf-8"))
    return next(r for r in doc["sources"] if r["id"] == rid)


def _fetcher(blocks: str = "mempool_blocks.synthetic.json", fail_summary_for: str = ""):
    calls: list[str] = []

    def fetch(url: str, headers=None, body=None) -> bytes:
        calls.append(url)
        if url.endswith("/v1/fees/recommended"):
            return (FIX / "mempool_fees.synthetic.json").read_bytes()
        if url.endswith("/mempool"):
            return (FIX / "mempool_backlog.synthetic.json").read_bytes()
        if "/summary" in url:
            if fail_summary_for and fail_summary_for in url:
                raise fs.FetchError("http_429", url)
            return (FIX / "mempool_block_summary.synthetic.json").read_bytes()
        if "/v1/blocks" in url:
            return (FIX / blocks).read_bytes()
        raise fs.FetchError("http_404", url)
    return fetch, calls


def test_parsers_read_the_live_shapes_and_refuse_garbage() -> None:
    assert fs.parse_mempool_fees((FIX / "mempool_fees.synthetic.json").read_bytes()) == {
        "btc_fee_fastest": 12.0, "btc_fee_halfhour": 9.0, "btc_fee_hour": 7.0,
        "btc_fee_economy": 3.0}
    back = fs.parse_mempool_backlog((FIX / "mempool_backlog.synthetic.json").read_bytes())
    assert back["btc_mempool_tx"] == 80498 and back["btc_mempool_vmb"] == pytest.approx(39.125496)
    blocks = fs.parse_mempool_blocks((FIX / "mempool_blocks.synthetic.json").read_bytes())
    assert [b["height"] for b in blocks] == [100, 101, 102]           # oldest first
    assert blocks[0]["fees_btc"] == pytest.approx(0.02)
    summ = fs.parse_block_summary((FIX / "mempool_block_summary.synthetic.json").read_bytes())
    # the 500 BTC coinbase is not a transfer; 150 and 1200 BTC are >= 100, only 1200 >= 1000
    assert summ == {"large_100": 2.0, "large_1000": 1.0, "large_value_btc": 1350.0}
    for parse in (fs.parse_mempool_fees, fs.parse_mempool_backlog, fs.parse_mempool_blocks):
        assert not parse(b"<html>rate limited</html>")
    assert fs.parse_block_summary(b"{}") is None


def test_snapshot_is_stamped_at_the_read_and_open_hours_wait_for_the_close() -> None:
    fetch, _ = _fetcher()
    row = _row("btc_onchain_mempool")
    h = fs.fetch_onchain_explorer(fetch, row, {"last_height": 99}, NOW,
                                  crypto_cfds=["BTCUSD", "ETHUSD", "SOLUSD"])
    assert h.status == "OK"
    keys = {o["key"] for o in h.obs}
    assert {"btc_fee_fastest", "btc_mempool_tx"} <= keys
    # block 102 (10:30) is the latest read: the 08:00 hour needs a block stamped >= 11:00
    assert "btc_large_tx_100" not in keys
    assert h.cursor["last_height"] == 102 and "2026-09-23T08:00:00+00:00" in h.cursor["acc"]
    for o in h.obs:
        assert o["publication_time"] == NOW.isoformat()       # never knowable before the read
    assert h.columns["btc_fee_fastest"]["hypothesis"] == ["BTCUSD", "ETHUSD"]
    assert any("UNMEASURED" in n and "exchange" in n for n in h.notes)

    fetch2, _ = _fetcher("mempool_blocks_next.synthetic.json")
    h2 = fs.fetch_onchain_explorer(fetch2, row, h.cursor, NOW, crypto_cfds=["BTCUSD"])
    got = {(o["key"], o["period_end"]): o["value"] for o in h2.obs}
    pe = "2026-09-23T09:00:00+00:00"
    assert got[("btc_blocks", pe)] == 2.0
    assert got[("btc_large_tx_100", pe)] == 4.0 and got[("btc_large_tx_1000", pe)] == 2.0
    assert got[("btc_large_value_btc", pe)] == pytest.approx(2700.0)
    assert got[("btc_block_fees_btc", pe)] == pytest.approx(0.03)
    assert got[("btc_median_fee_rate", pe)] == pytest.approx(3.0)
    assert ("btc_blocks", "2026-09-23T11:00:00+00:00") not in got        # 10:00 hour still open
    assert h2.cursor["last_height"] == 103
    assert h2.columns["btc_blocks"]["hypothesis"] == ["BTCUSD"]   # ETHUSD absent from registry


def test_the_height_cursor_never_steps_over_an_unread_block() -> None:
    fetch, _ = _fetcher(fail_summary_for=f"{101:064x}")
    h = fs.fetch_onchain_explorer(fetch, _row("btc_onchain_mempool"), {"last_height": 99}, NOW)
    assert h.cursor["last_height"] == 100                 # 101 failed: stop, owe it next pass
    assert h.failures["http_429"] == 1


def test_a_backlog_beyond_the_bound_is_named_not_filled() -> None:
    fetch, _ = _fetcher()
    h = fs.fetch_onchain_explorer(fetch, _row("btc_onchain_mempool"), {"last_height": -50}, NOW)
    assert h.cursor["skipped_heights"] == [-49, 92]
    assert any("backlog" in n for n in h.notes)


def test_access_records_make_no_request_and_report_their_state() -> None:
    doc = json.loads(ROSTER.read_text("utf-8"))
    recs = [r for r in doc["sources"] if r["kind"] == "access_record"]
    assert {r["id"]: r["access_state"] for r in recs} == {
        "eth_onchain_blockscout": "HELD", "histdata_fx_m1": "METHOD_BLOCKED",
        "ais_aisstream": "NEEDS_KEY", "ais_aishub": "NEEDS_KEY",
        "ais_marinetraffic": "NEEDS_KEY", "tradingeconomics_asia_macro": "NEEDS_KEY",
        "investing_econ_calendar": "IDEAS_ONLY"}

    def never(url: str, headers=None, body=None) -> bytes:
        raise AssertionError(f"an access record fetched {url}")
    for r in recs:
        ev = r["access_evidence"]
        assert ev["terms_url"].startswith("https://") and ev["terms_quote"], r["id"]
        assert ev["judgement"].startswith(r["access_state"]) and ev["checked_at"], r["id"]
        assert r["machine_use_allowed"] is False
        h = fs.FETCHERS["access_record"](never, r, {}, NOW)
        assert h.status == r["access_state"] and h.requests == 0 and not h.obs


def test_the_onchain_row_carries_its_terms_and_reaches_no_trading_venue() -> None:
    sys.path.insert(0, str(_ROOT / "scripts"))
    from check_mt5_purity import _VENUE_HOSTS
    row = _row("btc_onchain_mempool")
    ev = row["terms_evidence"]
    assert "enforce rate limits" in ev["api_quote"] and "API services" in ev["terms_quote"]
    text = ROSTER.read_text("utf-8") + (_ROOT / "libs" / "data" / "free_stack.py").read_text(
        "utf-8")
    assert not [h for h in _VENUE_HOSTS if h in text]


def test_hunter_publishes_onchain_columns_for_the_crypto_cfds(tmp_path: Path) -> None:
    from free_stack_hunter import Store, run
    st = Store(tmp_path)
    (tmp_path / "data" / "universe").mkdir(parents=True)
    real = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(real), "utf-8")
    roster = tmp_path / "roster.json"
    rows = [_row("btc_onchain_mempool"), _row("histdata_fx_m1"), _row("ais_aisstream")]
    roster.write_text(json.dumps({"sources": rows}), "utf-8")
    fetch, _ = _fetcher()
    rep = run(budget_s=60, fetch=fetch, store=st, roster=roster, now=NOW, live=False)
    per = rep["per_source"]
    assert per["btc_onchain_mempool"]["status"] == "OK"
    assert per["histdata_fx_m1"]["status"] == "METHOD_BLOCKED"
    assert per["ais_aisstream"]["status"] == "NEEDS_KEY"           # its own state, not a refusal
    assert per["ais_aisstream"]["requests"] == 0
    cols = json.loads(st.columns.read_text("utf-8"))["btc_onchain_mempool"]
    assert set(cols["btc_fee_fastest"]["hypothesis"]) == {"BTCUSD", "ETHUSD"}
    assert (st.series / "fs_btc_onchain_mempool.parquet").exists()
