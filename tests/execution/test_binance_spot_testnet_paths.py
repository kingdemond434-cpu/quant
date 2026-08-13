"""Offline coverage of the spot-testnet money path and its fail-closed boundaries."""

from __future__ import annotations

from typing import Any

import pytest

import libs.execution.binance_spot_testnet as spot


class _Response:
    def __init__(self, payload: bytes = b'{"ok": true}') -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_credentials_load_from_env_file_and_fail_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_KEY", "env-key")
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_SECRET", "env-secret")
    assert spot._creds() == ("env-key", "env-secret")
    assert spot.has_keys() is True

    monkeypatch.delenv("BINANCE_SPOT_TESTNET_KEY")
    monkeypatch.delenv("BINANCE_SPOT_TESTNET_SECRET")
    keyfile = tmp_path / "spot.json"
    keyfile.write_text('{"key": "file-key", "secret": "file-secret"}', "utf-8")
    monkeypatch.setattr(spot, "_KEYFILE", keyfile)
    assert spot._creds() == ("file-key", "file-secret")

    keyfile.write_text("{broken", "utf-8")
    assert spot._creds() == (None, None)
    keyfile.unlink()
    assert spot.has_keys() is False
    with pytest.raises(RuntimeError, match="keys"):
        spot._signed("/api/v3/account", {})


def test_public_and_signed_transports_construct_requests(monkeypatch) -> None:
    calls: list[Any] = []

    def open_url(request: Any, timeout: int) -> _Response:
        calls.append((request, timeout))
        return _Response()

    monkeypatch.setattr(spot.urllib.request, "urlopen", open_url)
    assert spot._get("/public", {"symbol": "BTC USDT"}) == {"ok": True}
    assert "symbol=BTC+USDT" in calls[-1][0].full_url

    monkeypatch.setenv("BINANCE_SPOT_TESTNET_KEY", "key")
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_SECRET", "secret")
    monkeypatch.setattr(spot.time, "time", lambda: 1.0)
    assert spot._signed("/signed", {"symbol": "BTCUSDT"}) == {"ok": True}
    assert "signature=" in calls[-1][0].full_url
    assert calls[-1][0].headers["X-mbx-apikey"] == "key"

    assert spot._signed("/signed", {"symbol": "BTCUSDT"}, method="POST") == {"ok": True}
    assert calls[-1][0].method == "POST"
    assert b"signature=" in calls[-1][0].data


def test_public_market_data_and_filters_are_parsed(monkeypatch) -> None:
    monkeypatch.setattr(
        spot,
        "_get",
        lambda path, params=None: [
            {"symbol": "BTCUSDT", "price": "100.5", "bidPrice": "100", "askPrice": "101"}
        ],
    )
    assert spot.prices() == {"BTCUSDT": 100.5}
    assert spot.book_ticker() == {"BTCUSDT": (100.0, 101.0)}
    monkeypatch.setattr(spot, "_get", lambda path, params=None: {"code": -1})
    assert spot.prices() == {}
    assert spot.book_ticker() == {}

    monkeypatch.setattr(
        spot,
        "_get",
        lambda path, params=None: {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAssetPrecision": 5,
                    "filters": [
                        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.002"},
                        {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                    ],
                }
            ]
        },
    )
    assert spot.exchange_filters()["BTCUSDT"] == {
        "step": 0.001,
        "min_qty": 0.002,
        "qty_prec": 5,
        "tick": 0.1,
        "price_prec": 1,
        # 0.0 because this fixture publishes no NOTIONAL/MIN_NOTIONAL filter, and 0.0 is the
        # documented "no published minimum" answer -- callers keep their own conservative floor
        # for that case. The KEY must be present regardless: it was added to binance_spot_live
        # only, while the money path imports THIS module, so the executor sized every order
        # without the venue's minimum order value. An order can clear stepSize and minQty and
        # still be rejected on value, and on a two-legged carry a leg rejected while its partner
        # fills is a naked directional position. tests/execution/test_filter_parity.py pins the
        # two parsers together so the divergence cannot silently return.
        "min_notional": 0.0,
    }
    assert spot._prec_of(1.0) == 0


def test_signed_reads_preserve_venue_truth_and_safe_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(
        spot,
        "_signed",
        lambda path, params, method="GET": [
            {"isBuyer": True, "qty": "2", "quoteQty": "202"},
            {"isBuyer": False, "qty": "9", "quoteQty": "999"},
        ],
    )
    assert spot.avg_fill("BTCUSDT", "BUY", 0) == 101.0
    assert spot.my_trades("BTCUSDT", 10, end_ms=20, limit=4)[0]["qty"] == "2"

    def boom(*args: object, **kwargs: object) -> object:
        raise OSError("venue unavailable")

    monkeypatch.setattr(spot, "_signed", boom)
    assert spot.avg_fill("BTCUSDT", "BUY", 0) is None
    assert spot.my_trades("BTCUSDT", 0) == []


def test_balances_account_value_and_order_construction(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any], str]] = []

    def signed(path: str, params: dict[str, Any], *, method: str = "GET") -> object:
        calls.append((path, params, method))
        if path.endswith("account"):
            return {"balances": [{"asset": "USDT", "free": "10"}, {"asset": "BTC", "free": "2"}]}
        return {"orderId": 7}

    monkeypatch.setattr(spot, "_signed", signed)
    monkeypatch.setattr(spot, "prices", lambda: {"BTCUSDT": 100.0})
    assert spot.balances() == {"USDT": 10.0, "BTC": 2.0}
    assert spot.usdt_balance() == 10.0
    assert spot.account_value_usdt() == 210.0

    assert spot.place_market("BTCUSDT", "BUY", 1.0, cycle="c")["orderId"] == 7
    assert calls[-1][1]["newClientOrderId"]
    assert spot.place_market_quote("BTCUSDT", "BUY", 10.0)["orderId"] == 7
    assert calls[-1][1]["quoteOrderQty"] == 10.0
    assert spot.place_post_only("BTCUSDT", "SELL", 1.0, 101.0)["orderId"] == 7
    assert calls[-1][1]["type"] == "LIMIT_MAKER"

    monkeypatch.setattr(spot, "_signed", lambda *args, **kwargs: "unexpected")
    assert spot.place_market("BTCUSDT", "BUY", 1.0) == {"raw": "unexpected"}
    assert spot.place_market_quote("BTCUSDT", "BUY", 1.0) == {"raw": "unexpected"}
    assert spot.place_post_only("BTCUSDT", "BUY", 1.0, 99.0) == {"raw": "unexpected"}


def test_open_and_cancel_orders_use_safe_shapes(monkeypatch) -> None:
    monkeypatch.setattr(spot, "_signed", lambda *args, **kwargs: [{"orderId": 1}])
    assert spot.open_orders("BTCUSDT") == [{"orderId": 1}]
    monkeypatch.setattr(spot, "_signed", lambda *args, **kwargs: {"code": 200})
    assert spot.open_orders() == []
    assert spot.cancel_all("BTCUSDT") == {"code": 200, "res": {"code": 200}}

    def boom(*args: object, **kwargs: object) -> object:
        raise OSError("nothing to cancel")

    monkeypatch.setattr(spot, "_signed", boom)
    cancelled = spot.cancel_all("BTCUSDT")
    assert cancelled["code"] == 0
    assert "nothing to cancel" in cancelled["msg"]
