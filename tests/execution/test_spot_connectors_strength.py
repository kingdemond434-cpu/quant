"""MUTATION-STRENGTH suite for the two SPOT connectors -- the half of a carry that holds coins.

WHY THIS FILE EXISTS. `tests/execution/test_spot_connectors.py` proves the read helpers
(`quote_depth`, `avg_fill`, `balances`) behave. Nothing anywhere proved that the four ORDER
functions send the venue the order the caller asked for, that `exchange_filters` parses the
fields the sizing path divides by, or that `_prec_of` rounds a quantity to a precision the venue
will accept. Mutation testing measures precisely that gap: a mutant that survives is a line whose
behaviour no test constrains, and on this path the unconstrained lines are the ones that decide
WHAT ORDER IS PLACED.

Both spot modules expose the same surface and were written by copying one from the other, so
every test runs against BOTH -- a defect in one is overwhelmingly likely to be in the other
(the market-cap-cache defect was present in both, identically).

No network and no credentials: `_get` and `_signed` are replaced, and the replacement for
`_signed` RECORDS the call, because on an order path the assertion worth making is about the
request, not the reply.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.execution import binance_spot_live, binance_spot_testnet

MODS = [binance_spot_live, binance_spot_testnet]
IDS = ["spot_live", "spot_testnet"]


def _recorder(mod: Any, monkeypatch: pytest.MonkeyPatch,
              reply: Any = None) -> list[dict[str, Any]]:
    """Replace `_signed` with a recorder. The captured params ARE the order."""
    calls: list[dict[str, Any]] = []

    def fake(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
        calls.append({"path": path, "params": dict(params), "method": method})
        return {"orderId": 1} if reply is None else reply

    monkeypatch.setattr(mod, "_signed", fake)
    return calls


# --------------------------------------------------------------- the order itself

@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_place_market_sends_a_MARKET_order_in_BASE_units(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`quantity` is base units and `quoteOrderQty` is dollars. Sending the caller's base
    quantity in the quote field buys $0.25 of BTC where 0.25 BTC was intended -- a four-order-of-
    magnitude under-fill that leaves the perp leg of a carry naked."""
    calls = _recorder(mod, monkeypatch)
    mod.place_market("BTCUSDT", "BUY", 0.25)
    assert len(calls) == 1
    c = calls[0]
    assert c["method"] == "POST", "an order sent as a GET is not an order"
    assert c["path"] == "/api/v3/order"
    # SUBSET, NOT EXACT EQUALITY. This compared the whole params dict, so it failed the day the
    # connectors began stamping `newClientOrderId` -- an idempotency token, i.e. the mechanism
    # that stops a retry becoming a SECOND order and leaving one leg of a carry naked. A test
    # that goes red on a safety field being added teaches readers to discount red, and the field
    # is asserted below rather than merely tolerated.
    for k, v in {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quantity": 0.25}.items():
        assert c["params"].get(k) == v, f"{k} wrong: {c['params'].get(k)!r} != {v!r}"
    assert "quoteOrderQty" not in c["params"]
    assert c["params"].get("newClientOrderId"), (
        "no client order id: a retry of this order is a SECOND order to the venue, and on a "
        "two-legged carry that is a naked directional position")


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_place_market_quote_sends_QUOTE_units_and_never_a_quantity(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The mirror-image error of the test above, and the more expensive direction: 5000 read as a
    base quantity is an order for 5000 BTC."""
    calls = _recorder(mod, monkeypatch)
    mod.place_market_quote("BTCUSDT", "BUY", 5000.0)
    for k, v in {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET",
                 "quoteOrderQty": 5000.0}.items():
        assert calls[0]["params"].get(k) == v, f"{k} wrong"
    assert "quantity" not in calls[0]["params"]
    assert calls[0]["params"].get("newClientOrderId"), "quote-sized orders need dedup too"


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_post_only_is_LIMIT_MAKER_which_is_what_makes_it_post_only(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """LIMIT_MAKER is REJECTED by the venue rather than crossing. A plain LIMIT at the same price
    crosses and pays taker fees on both legs -- the carry's whole edge is the fee difference, so
    this silently converts a profitable spread into a losing one while every log still says
    'maker'."""
    calls = _recorder(mod, monkeypatch)
    mod.place_post_only("BTCUSDT", "SELL", 0.5, 70000.0)
    assert calls[0]["params"]["type"] == "LIMIT_MAKER"
    assert calls[0]["params"]["quantity"] == 0.5
    assert calls[0]["params"]["price"] == 70000.0
    assert calls[0]["method"] == "POST"


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_an_order_reply_that_is_not_a_dict_is_still_returned_not_dropped(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The venue answered something unexpected -- but an order may well have been PLACED. Losing
    that reply loses the only record the caller has of an order that exists."""
    _recorder(mod, monkeypatch, reply=["weird"])
    assert mod.place_market("BTCUSDT", "BUY", 1.0) == {"raw": ["weird"]}
    assert mod.place_market_quote("BTCUSDT", "BUY", 1.0) == {"raw": ["weird"]}
    assert mod.place_post_only("BTCUSDT", "BUY", 1.0, 2.0) == {"raw": ["weird"]}


# ------------------------------------------------------------------- cancel / read

@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_cancel_all_reports_200_on_success_and_0_when_it_could_not_cancel(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The caller re-pegs a maker quote based on this code. Reporting 200 for a failed cancel
    leaves the old quote resting AND places a new one -- two live orders on one leg, which is the
    accumulated-resting-fill shape that once walked a short through zero."""
    calls = _recorder(mod, monkeypatch, reply=[{"orderId": 7}])
    ok = mod.cancel_all("BTCUSDT")
    assert ok["code"] == 200
    assert calls[0]["method"] == "DELETE", "a cancel sent as a GET cancels nothing"

    def boom(*_a: object, **_k: object) -> Any:
        raise RuntimeError("nothing to cancel")

    monkeypatch.setattr(mod, "_signed", boom)
    bad = mod.cancel_all("BTCUSDT")
    assert bad["code"] == 0 and "nothing to cancel" in bad["msg"]


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_open_orders_filters_by_symbol_only_when_asked(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Passing a symbol filter when none was asked for hides every other symbol's resting order
    from the 'is anything still live?' check that runs before a re-peg."""
    calls = _recorder(mod, monkeypatch, reply=[{"orderId": 1}])
    assert mod.open_orders("BTCUSDT") == [{"orderId": 1}]
    assert calls[0]["params"] == {"symbol": "BTCUSDT"}
    assert mod.open_orders() == [{"orderId": 1}]
    assert calls[1]["params"] == {}


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_open_orders_reads_a_non_list_reply_as_NO_orders_not_a_crash(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _recorder(mod, monkeypatch, reply={"code": -1121})
    assert mod.open_orders("BTCUSDT") == []


# ------------------------------------------------------------ prices and precision

@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_prices_and_book_ticker_parse_the_venue_shape(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """These feed the mark used to size the spot leg. A non-list payload (an error object) must
    read as 'no prices', never as a partially-parsed dict."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: [
        {"symbol": "BTCUSDT", "price": "70000.5"}, {"symbol": "ETHUSDT", "price": "3000"}])
    assert mod.prices() == {"BTCUSDT": 70000.5, "ETHUSDT": 3000.0}

    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: [
        {"symbol": "BTCUSDT", "bidPrice": "69999.0", "askPrice": "70001.0"}])
    assert mod.book_ticker() == {"BTCUSDT": (69999.0, 70001.0)}

    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {"code": -1121, "msg": "bad symbol"})
    assert mod.prices() == {}
    assert mod.book_ticker() == {}


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_prec_of_counts_the_decimals_a_step_actually_implies(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """This number is how many decimals an order price is rounded to. One too few rounds the
    price off the venue's tick grid and the order is rejected; one too many is rejected as
    over-precise. A step of 1 or more implies ZERO decimals, and the `< 1` boundary is exactly
    where that flips."""
    assert mod._prec_of(0.001) == 3
    assert mod._prec_of(0.01) == 2
    assert mod._prec_of(0.00000001) == 8
    assert mod._prec_of(1.0) == 0, "a whole-number step implies no decimals"
    assert mod._prec_of(10.0) == 0
    assert mod._prec_of(0.5) == 1


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_exchange_filters_defaults_are_the_SAFE_side(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A symbol with no LOT_SIZE/PRICE_FILTER still has to produce usable numbers, and each
    default is a decision: min_qty 0.0 and min_notional 0.0 mean 'the venue published no
    minimum', which callers must treat as 'keep your own floor'. price_prec falls back to 8 (the
    finest spot grid) when there is no tick, because rounding to too FEW decimals silently moves
    the price."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {"symbols": [
        {"symbol": "NOFILTUSDT", "filters": []},
    ]})
    got = mod.exchange_filters()["NOFILTUSDT"]
    assert got["step"] == 0.0001
    assert got["min_qty"] == 0.0
    assert got["qty_prec"] == 6, "absent baseAssetPrecision falls back to 6"
    assert got["tick"] == 0.0
    assert got["price_prec"] == 8
    assert got["min_notional"] == 0.0


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_a_zero_tick_string_does_not_become_a_zero_precision(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`tickSize: "0.00000000"` is the venue saying 'no price filter', not 'round to whole
    dollars'. `_prec_of(0.0)` would answer 0, so the code must not consult it -- it answers 8."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {"symbols": [
        {"symbol": "ZEROTICK", "baseAssetPrecision": 4, "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.00000000"}]},
    ]})
    got = mod.exchange_filters()["ZEROTICK"]
    assert got["tick"] == 0.0
    assert got["price_prec"] == 8
    assert got["qty_prec"] == 4


# -------------------------------------------------------------------- account value

@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_account_value_is_rounded_to_CENTS_and_prices_the_right_pair(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """An asset is marked with its OWN `{asset}USDT` pair. Marking BTC at the ETH price is the
    kind of error that reads as a plausible number, and this figure is the denominator of every
    capital-fraction rail."""
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: {"balances": [
        {"asset": "USDT", "free": "10.005"},
        {"asset": "BTC", "free": "0.001"},
        {"asset": "ETH", "free": "1.0"},
    ]})
    monkeypatch.setattr(mod, "prices", lambda: {"BTCUSDT": 70000.0, "ETHUSDT": 3000.0})
    assert mod.account_value_usdt() == pytest.approx(3080.01, abs=1e-9)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_an_asset_with_no_price_is_worth_ZERO_not_its_quantity(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Valuing an unpriceable holding at its unit count fabricates equity, and equity is what the
    sizing rails divide by. Zero is the conservative direction and the only defensible one."""
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: {"balances": [
        {"asset": "USDT", "free": "100.0"}, {"asset": "WEIRD", "free": "12345.0"}]})
    monkeypatch.setattr(mod, "prices", lambda: {})
    assert mod.account_value_usdt() == pytest.approx(100.0)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_quote_depth_defaults_to_a_ONE_PERCENT_band(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Callers rely on the default band. Widening it counts liquidity at prices the desk would
    never pay and reports a thin book as deep -- the direction that sizes into an illiquid name."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {
        "asks": [["100", "1"], ["100.5", "1"], ["101.5", "1"]], "bids": []})
    assert mod.quote_depth("BTCUSDT", "BUY") == pytest.approx(100.0 + 100.5)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_the_touch_level_itself_is_always_inside_the_band(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The best price is by definition affordable. A strict inequality against the touch drops
    it, under-reporting depth by the whole top of book on a one-level book -- which reads as
    'no liquidity' and stands the desk aside from a trade it could do."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {"asks": [["100", "3"]], "bids": []})
    assert mod.quote_depth("BTCUSDT", "BUY", pct=0.0) == pytest.approx(300.0)
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {"asks": [], "bids": [["100", "3"]]})
    assert mod.quote_depth("BTCUSDT", "SELL", pct=0.0) == pytest.approx(300.0)


# ------------------------------------------------------- testnet-only forensic read

def test_my_trades_sends_endTime_only_when_a_window_end_was_given(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Binance refuses startTime+endTime spans over 24h on this endpoint. Sending an endTime the
    caller never asked for turns an open-ended forensic read into an empty one, and the
    reconciliation that consumes it then reports 'no fills' for a leg that filled."""
    calls = _recorder(binance_spot_testnet, monkeypatch, reply=[{"qty": "1"}])
    assert binance_spot_testnet.my_trades("BTCUSDT", 1000) == [{"qty": "1"}]
    assert calls[0]["params"] == {"symbol": "BTCUSDT", "startTime": 1000, "limit": 1000}
    binance_spot_testnet.my_trades("BTCUSDT", 1000, 2000, limit=50)
    assert calls[1]["params"] == {"symbol": "BTCUSDT", "startTime": 1000, "endTime": 2000,
                                  "limit": 50}


def test_my_trades_is_EMPTY_not_an_exception_when_the_read_fails(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def boom(*_a: object, **_k: object) -> Any:
        raise RuntimeError("no keys")

    monkeypatch.setattr(binance_spot_testnet, "_signed", boom)
    assert binance_spot_testnet.my_trades("BTCUSDT", 0) == []
    monkeypatch.setattr(binance_spot_testnet, "_signed", lambda *_a, **_k: {"code": -1})
    assert binance_spot_testnet.my_trades("BTCUSDT", 0) == []


# ------------------------------------------------------------ the live arming gate

def test_every_arming_precondition_INDIVIDUALLY_blocks_a_signed_call(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Three preconditions joined by `all`. If any one of them stops being required -- an `or`
    where an `and` belongs -- possessing a key becomes consent to trade real money, which is the
    exact thing the ceremony exists to prevent. Each is removed in turn."""
    m = binance_spot_live
    keyfile = tmp_path / "k.json"
    keyfile.write_text('{"key": "K", "secret": "S"}', "utf-8")
    enable, vps = tmp_path / "LIVE_ENABLE", tmp_path / "LIVE_VPS_VERIFIED"
    enable.write_text("", "utf-8")
    vps.write_text("", "utf-8")
    monkeypatch.setattr(m, "_KEYFILE", keyfile)
    monkeypatch.setattr(m, "_ENABLE_FLAG", enable)
    monkeypatch.setattr(m, "_VPS_MARKER", vps)
    assert m.is_armed()[0] is True, "all three present must arm, or nothing can ever trade"

    for missing in (keyfile, enable, vps):
        missing.rename(missing.with_suffix(".away"))
        armed, why = m.is_armed()
        assert armed is False, f"removing {missing.name} must disarm"
        assert "=" in why, "the reason string must name the checks"
        with pytest.raises(RuntimeError, match="not armed"):
            m._signed("/api/v3/order", {"symbol": "BTCUSDT"}, method="POST")
        missing.with_suffix(".away").rename(missing)


def test_a_corrupt_keyfile_is_NO_keys_rather_than_a_crash(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A half-written keyfile must disarm the connector, not take down the caller mid-rebalance."""
    m = binance_spot_live
    bad = tmp_path / "k.json"
    bad.write_text("{not json", "utf-8")
    monkeypatch.setattr(m, "_KEYFILE", bad)
    assert m.has_keys() is False
    assert m.is_armed()[0] is False


def test_the_live_spot_base_url_is_pinned_to_the_real_venue() -> None:
    """A live module pointed at testnet reports fills that never happened against real capital
    the desk believes is deployed."""
    assert binance_spot_live._BASE == "https://api.binance.com"
    assert binance_spot_testnet._BASE == "https://testnet.binance.vision"


# ------------------------------------------------------- the signed request itself
#
# Everything above replaces `_signed`, which is the right level for asserting WHAT ORDER was
# asked for -- and it means `_signed` itself was never executed by any test in this repository.
# The census found exactly that: `if method == "GET"` (Eq -> NotEq) survived, i.e. nothing
# checked that a POST carries a body and a GET carries a query string. A POSTed order whose
# parameters went into the URL instead of the body is not a differently-shaped order, it is an
# order the venue never receives.


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def _capture_requests(mod: Any, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Intercept at urlopen, so the real Request object the connector built is inspectable.

    The socket timeout is recorded on the Request too: an unbounded venue call on the order path
    is a hang, and a hang there is a leg whose state nobody knows.
    """
    seen: list[Any] = []

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeResponse:
        req._seen_timeout = timeout
        seen.append(req)
        return _FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    return seen


def _arm_live(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Satisfy all three live-spot preconditions against a temp dir."""
    m = binance_spot_live
    keyfile = tmp_path / "k.json"
    keyfile.write_text('{"key": "KKK", "secret": "SSS"}', "utf-8")
    enable, vps = tmp_path / "LIVE_ENABLE", tmp_path / "LIVE_VPS_VERIFIED"
    enable.write_text("", "utf-8")
    vps.write_text("", "utf-8")
    monkeypatch.setattr(m, "_KEYFILE", keyfile)
    monkeypatch.setattr(m, "_ENABLE_FLAG", enable)
    monkeypatch.setattr(m, "_VPS_MARKER", vps)


def _arm_testnet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_KEY", "KKK")
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_SECRET", "SSS")


def test_a_signed_POST_carries_its_parameters_in_the_BODY(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A POST whose parameters are in the URL and not the body places nothing. The signature
    travels with them, so the venue sees an unsigned, empty order and rejects it -- and the
    caller's `_signed` returned 200, so the desk believes the leg is on."""
    m = binance_spot_testnet
    _arm_testnet(monkeypatch)
    seen = _capture_requests(m, monkeypatch)
    m._signed("/api/v3/order", {"symbol": "BTCUSDT"}, method="POST")
    req = seen[0]
    assert req.get_method() == "POST"
    assert req.full_url == "https://testnet.binance.vision/api/v3/order", (
        "a POST must not carry its parameters in the URL")
    body = (req.data or b"").decode()
    assert "symbol=BTCUSDT" in body and "signature=" in body
    assert req.get_header("X-mbx-apikey") == "KKK"


def test_a_signed_GET_carries_its_parameters_in_the_QUERY_STRING(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The mirror image: a GET with a body is not a GET Binance will answer, so every signed
    READ -- balances, open orders, fills -- silently returns nothing."""
    m = binance_spot_testnet
    _arm_testnet(monkeypatch)
    seen = _capture_requests(m, monkeypatch)
    m._signed("/api/v3/account", {})
    req = seen[0]
    assert req.get_method() == "GET"
    assert req.data is None, "a GET must not carry a body"
    assert req.full_url.startswith("https://testnet.binance.vision/api/v3/account?")
    assert "signature=" in req.full_url


def test_every_signed_call_is_stamped_with_a_timestamp_and_a_recvWindow(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Binance rejects a signed request with no `timestamp`, and `recvWindow` bounds how long a
    delayed order may still execute. Dropping the bound lets a request that sat in a retry queue
    fire minutes late -- an order placed against a market that has moved."""
    m = binance_spot_testnet
    _arm_testnet(monkeypatch)
    seen = _capture_requests(m, monkeypatch)
    m._signed("/api/v3/account", {})
    query = seen[0].full_url.split("?", 1)[1]
    parsed = dict(part.split("=", 1) for part in query.split("&"))
    assert parsed["recvWindow"] == "5000"
    assert int(parsed["timestamp"]) > 1_600_000_000_000, (
        "timestamp must be in MILLISECONDS -- seconds are outside every recvWindow")


def test_HALF_a_credential_pair_refuses_rather_than_signing_with_None(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Key present, secret missing is the shape a partially-applied deploy leaves behind. It must
    raise the same refusal as no keys at all: `not key or not secret`. With `and` in its place a
    half-configured box proceeds to sign, and what the caller gets is an opaque AttributeError
    from the middle of the order path instead of 'no keys'."""
    m = binance_spot_testnet
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_KEY", "KKK")
    monkeypatch.delenv("BINANCE_SPOT_TESTNET_SECRET", raising=False)
    monkeypatch.setattr(m, "_KEYFILE", m.Path("data/secrets/does-not-exist.json"))
    assert m.has_keys() is False
    with pytest.raises(RuntimeError, match="no spot-testnet keys"):
        m._signed("/api/v3/order", {"symbol": "BTCUSDT"}, method="POST")

    monkeypatch.delenv("BINANCE_SPOT_TESTNET_KEY", raising=False)
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_SECRET", "SSS")
    assert m.has_keys() is False
    with pytest.raises(RuntimeError, match="no spot-testnet keys"):
        m._signed("/api/v3/order", {"symbol": "BTCUSDT"}, method="POST")


def test_env_credentials_win_over_the_keyfile_and_a_corrupt_keyfile_is_no_keys(
        tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The env pair is checked FIRST so an operator can point a box at a different testnet
    account without editing files. If the keyfile won instead, a stale file would silently
    override the credentials the operator just set."""
    m = binance_spot_testnet
    keyfile = tmp_path / "k.json"
    keyfile.write_text('{"key": "FILEK", "secret": "FILES"}', "utf-8")
    monkeypatch.setattr(m, "_KEYFILE", keyfile)
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_KEY", "ENVK")
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_SECRET", "ENVS")
    assert m._creds() == ("ENVK", "ENVS")

    monkeypatch.delenv("BINANCE_SPOT_TESTNET_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SPOT_TESTNET_SECRET", raising=False)
    assert m._creds() == ("FILEK", "FILES")

    keyfile.write_text("{not json", "utf-8")
    assert m._creds() == (None, None)
    assert m.has_keys() is False


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_public_reads_append_their_params_and_need_no_keys(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`_get` is the depth/price path. Dropping the query string turns a per-symbol depth read
    into a whole-venue one (or an error), and `quote_depth` swallows the failure as 0.0 -- so a
    broken URL reads as 'this book is empty' and stands the desk aside on every symbol."""
    seen = _capture_requests(mod, monkeypatch)
    assert mod._get("/api/v3/depth", {"symbol": "BTCUSDT", "limit": 100}) == {"ok": True}, (
        "a reader that drops the venue's answer reports 'no data' for every healthy call")
    assert seen[0].full_url == f"{mod._BASE}/api/v3/depth?symbol=BTCUSDT&limit=100"
    assert seen[0].data is None
    mod._get("/api/v3/exchangeInfo")
    assert seen[1].full_url == f"{mod._BASE}/api/v3/exchangeInfo", (
        "no params must mean no trailing '?'")


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_every_venue_call_is_BOUNDED_by_a_socket_timeout(mod, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """An unbounded read on the order path does not fail, it HANGS -- and a hung order is the one
    state the desk cannot reconcile, because it does not know whether the leg exists. 20s is the
    bound; losing it (or stretching it past the caller's own cycle) reintroduces the hang."""
    if mod is binance_spot_live:
        _arm_live(tmp_path, monkeypatch)
    else:
        _arm_testnet(monkeypatch)
    seen = _capture_requests(mod, monkeypatch)
    mod._get("/api/v3/ping")
    assert seen[0]._seen_timeout == 20
    mod._signed("/api/v3/account", {})
    assert seen[1]._seen_timeout == 20


def test_the_LIVE_spot_signed_request_is_built_the_same_way(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The arming ceremony means `binance_spot_live._signed` is never reached by a test that has
    not performed it -- so its request construction (POST body vs GET query, the timestamp, the
    recvWindow) went unexercised on the module that spends REAL money, while its testnet twin
    was covered. Same assertions, armed."""
    m = binance_spot_live
    _arm_live(tmp_path, monkeypatch)
    seen = _capture_requests(m, monkeypatch)

    assert m._signed("/api/v3/order", {"symbol": "BTCUSDT"}, method="POST") == {"ok": True}
    post = seen[0]
    assert post.get_method() == "POST"
    assert post.full_url == "https://api.binance.com/api/v3/order", (
        "a POST must not carry its parameters in the URL")
    body = (post.data or b"").decode()
    assert "symbol=BTCUSDT" in body and "signature=" in body
    assert post.get_header("X-mbx-apikey") == "KKK"

    m._signed("/api/v3/account", {})
    get = seen[1]
    assert get.get_method() == "GET"
    assert get.data is None, "a GET must not carry a body"
    parsed = dict(p.split("=", 1) for p in get.full_url.split("?", 1)[1].split("&"))
    assert parsed["recvWindow"] == "5000"
    assert int(parsed["timestamp"]) > 1_600_000_000_000, (
        "timestamp must be in MILLISECONDS -- seconds are outside every recvWindow")


def test_live_spot_has_keys_needs_BOTH_halves_of_the_pair(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`bool(k and s)` is the whole arming gate's first term. With `or` in its place a keyfile
    carrying only an api key ARMS the live connector, and the desk then signs real orders with a
    None secret -- an opaque crash inside the order path, from a box that reported itself ready."""
    m = binance_spot_live
    keyfile = tmp_path / "k.json"
    monkeypatch.setattr(m, "_KEYFILE", keyfile)
    keyfile.write_text('{"key": "KKK"}', "utf-8")
    assert m.has_keys() is False, "an api key without a secret is not a credential"
    keyfile.write_text('{"secret": "SSS"}', "utf-8")
    assert m.has_keys() is False
    keyfile.write_text('{"key": "", "secret": "SSS"}', "utf-8")
    assert m.has_keys() is False, "an empty key is not a key"
    keyfile.write_text('{"key": "KKK", "secret": "SSS"}', "utf-8")
    assert m.has_keys() is True, "a complete pair must arm, or nothing can ever trade"


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_depth_and_fill_reads_ask_the_venue_for_the_page_size_they_assume(mod, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`quote_depth` sums 'the book' and `avg_fill` averages 'our fills' -- both are really
    'the first N rows the venue returned'. The N is part of the measurement: shrink it and a deep
    book reads thin, grow it past the venue cap and the call is rejected, which `quote_depth`
    swallows as 0.0."""
    got: list[dict[str, Any]] = []
    monkeypatch.setattr(mod, "_get", lambda _p, params=None: got.append(params or {}) or {
        "asks": [["100", "1"]], "bids": []})
    mod.quote_depth("BTCUSDT", "BUY")
    assert got[0] == {"symbol": "BTCUSDT", "limit": 100}

    calls = _recorder(mod, monkeypatch, reply=[])
    mod.avg_fill("BTCUSDT", "BUY", 4242)
    assert calls[0]["params"] == {"symbol": "BTCUSDT", "startTime": 4242, "limit": 100}
