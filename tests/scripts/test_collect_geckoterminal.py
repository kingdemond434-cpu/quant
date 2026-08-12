"""Row shape, dedup, overflow honesty and refusal ladder for the GeckoTerminal signed-DEX-flow
collector (R0291).

The two things that can destroy this axis silently: (a) duplicated trades (the venue re-serves
its whole ~300-trade window every call, so dedup is the difference between flow and noise), and
(b) a turned-over window reading as a quiet market -- the venue keeps only the last ~300 trades,
so "captured everything served" and "captured everything that happened" are different claims and
the overflow flag is what separates them. Clock provenance: block_timestamp is the CHAIN's stamp
(t_venue), receipt is OURS (t, c="recv") -- L1.46 says both live in the row.

NO NETWORK: everything is driven through the module's own `_get` seam; `time.sleep` is
neutralised.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from scripts import collect_geckoterminal_trades as gt

_RECV_MS = 1_784_000_000_000


def _attrs(tx: str, **over: Any) -> dict[str, Any]:
    base = {"tx_hash": tx, "tx_from_address": "0xwallet", "kind": "buy",
            "volume_in_usd": "1234.5", "block_number": 21_000_000,
            "block_timestamp": "2026-08-12T01:00:00Z",
            "from_token_amount": "2.0", "to_token_amount": "4000.1",
            "price_to_in_usd": "0.5", "price_from_in_usd": "1000.2"}
    base.update(over)
    return base


def _wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
          trades: list[dict[str, Any]]) -> None:
    def fake_get(url: str) -> tuple[Any, str]:
        if "trending_pools" in url and "/eth/" in url:
            return {"data": [{"attributes": {"address": "0xpool", "name": "FOO / WETH"}}]}, ""
        if "trending_pools" in url:
            return {"data": []}, ""            # solana: discovery serves nothing addressable
        if "/pools/0xpool/trades" in url:
            return {"data": [{"attributes": a} for a in trades]}, ""
        return None, "unexpected url"
    monkeypatch.setattr(gt, "_get", fake_get)
    monkeypatch.setattr(gt, "_ROOT", tmp_path)
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def test_trade_row_carries_both_clocks_and_refuses_without_the_dedup_key() -> None:
    row = gt.trade_row(_attrs("0xabc"), network="eth", pool="0xpool",
                       pool_name="FOO / WETH", recv_ms=_RECV_MS)
    assert row is not None
    assert row["t"] == _RECV_MS and row["c"] == "recv"
    assert row["t_venue"] == 1_786_496_400_000   # 2026-08-12T01:00:00Z, the CHAIN's stamp
    assert row["t"] != row["t_venue"], "the two clocks must stay distinct columns"
    assert (row["tx_from"], row["kind"], row["volume_usd"]) == ("0xwallet", "buy", 1234.5)

    assert gt.trade_row(_attrs("0xabc", tx_hash=None), network="eth", pool="p",
                        pool_name="n", recv_ms=_RECV_MS) is None
    bad = gt.trade_row(_attrs("0xdef", block_timestamp="not-a-time"), network="eth",
                       pool="p", pool_name="n", recv_ms=_RECV_MS)
    assert bad is not None and bad["t_venue"] is None, "unparseable stamp is None, never a guess"


def test_dedup_holds_across_runs_and_overflow_is_flagged(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, tmp_path, [_attrs("0x1"), _attrs("0x2"), _attrs("0x3")])
    status: dict[str, Any] = {}
    rows, errors, _, _ = gt.fetch_all(status)
    assert [r["tx_hash"] for r in rows] == ["0x1", "0x2", "0x3"]
    assert not status["overflow"], "first sight of a pool is baseline, not overflow"
    assert "solana/trending" in errors, "an empty discovery is recorded, never silent"

    rows2, _, _, _ = gt.fetch_all(status)           # identical window: nothing new
    assert rows2 == []
    assert not status["overflow"]

    _wire(monkeypatch, tmp_path, [_attrs("0x7"), _attrs("0x8"), _attrs("0x9")])
    rows3, _, _, _ = gt.fetch_all(status)           # whole window turned over between runs
    assert [r["tx_hash"] for r in rows3] == ["0x7", "0x8", "0x9"]
    assert status["overflow"] == {"eth:0xpool": True}, \
        "a turned-over window must be flagged, not read as a quiet market"


def test_main_appends_once_and_status_names_the_verdict(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, tmp_path, [_attrs("0xa"), _attrs("0xb")])
    monkeypatch.setattr("sys.argv", ["collect_geckoterminal_trades.py"])
    assert gt.main() == 0
    out = tmp_path / gt._OUT
    assert len(out.read_text("utf-8").splitlines()) == 2
    status = json.loads((tmp_path / gt._STATUS).read_text("utf-8"))
    assert status["verdict"] == "CAPTURED" and status["appended"] == 2

    assert gt.main() == 0                        # same window again: no duplicate rows
    assert len(out.read_text("utf-8").splitlines()) == 2
    status = json.loads((tmp_path / gt._STATUS).read_text("utf-8"))
    assert status["verdict"].startswith("QUIET")


def test_total_outage_refuses_loudly_and_fabricates_nothing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gt, "_get", lambda _u: (None, "URLError: down"))
    monkeypatch.setattr(gt, "_ROOT", tmp_path)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    monkeypatch.setattr("sys.argv", ["collect_geckoterminal_trades.py"])
    assert gt.main() == 1
    assert not (tmp_path / gt._OUT).exists(), "an outage must not fabricate rows"
    status = json.loads((tmp_path / gt._STATUS).read_text("utf-8"))
    assert status["verdict"].startswith("REFUSED-EMPTY")
    assert status["errors"], "the outage is named per endpoint"
