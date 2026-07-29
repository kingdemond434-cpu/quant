"""GAP #49 -- idempotent order submission, the Gate-0 no-naked-position prerequisite.

The live order path posted symbol/side/type/quantity and NO client order ID, while
`execution/retry.py` documented the opposite guarantee. On an ambiguous timeout the desk cannot
tell "not placed" from "placed, reply lost" -- and on a delta-neutral book a duplicated leg is
not a slightly-large position, it is an UNHEDGED DIRECTIONAL one.

The chunk-index tests are the ones that would have caught the obvious wrong implementation.
`place_market` splits across MARKET_LOT_SIZE chunks; one shared ID per logical order would have
the venue accept chunk 1 and reject the rest as duplicates, silently under-filling the leg --
converting an idempotency fix into a brand-new source of unhedged exposure.
"""

from __future__ import annotations

import pytest

from libs.execution.idempotency import (
    BUCKET_S,
    MAX_ID_LEN,
    client_order_id,
    is_duplicate_error,
)

T0 = 1_780_000_000.0


# --------------------------------------------------------------- determinism


def test_a_cycle_token_makes_the_id_clock_independent() -> None:
    """THE REAL GUARANTEE. Same logical order, same ID, no matter how long the retry took.

    Written this way because the first version of this test asserted the WEAK guarantee -- a
    wall-clock bucket -- and failed immediately on a boundary: T0 and T0+30s landed either side
    of a 90s grid line, producing different IDs for the same retry. That is not a corner case,
    it is a duplicate unhedged leg every time an order is placed near a boundary, with a window
    that is arbitrary and invisible from the call site. The cycle token removes the clock from
    the identity entirely.
    """
    a = client_order_id("BTCUSDT", "BUY", "open", cycle="pass-1", now=T0)
    b = client_order_id("BTCUSDT", "BUY", "open", cycle="pass-1", now=T0 + 86_400.0)
    assert a == b


def test_a_new_cycle_is_a_genuinely_new_order() -> None:
    assert (client_order_id("BTCUSDT", "BUY", "open", cycle="pass-1")
            != client_order_id("BTCUSDT", "BUY", "open", cycle="pass-2"))


def test_the_time_bucket_fallback_still_dedupes_within_a_bucket() -> None:
    """The fallback is weaker, not broken -- inside one bucket it behaves correctly."""
    anchor = (T0 // BUCKET_S) * BUCKET_S            # start of a bucket, not an arbitrary point
    a = client_order_id("BTCUSDT", "BUY", "open", now=anchor + 1.0)
    b = client_order_id("BTCUSDT", "BUY", "open", now=anchor + BUCKET_S - 1.0)
    assert a == b
    assert client_order_id("BTCUSDT", "BUY", "open", now=anchor + BUCKET_S + 1.0) != a


def test_the_executor_passes_a_cycle_token_so_the_real_path_is_clock_independent() -> None:
    """The connectors accept `cycle`; that only matters if the caller actually supplies one."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2]
           / "scripts/run_cashcarry_executor.py").read_text("utf-8")
    assert "def _pair_cycle(" in src
    assert "cycle=_cycle" in src, "the executor must thread its cycle token into the order path"


@pytest.mark.parametrize(("field", "kw"), [
    ("symbol", {"symbol": "ETHUSDT"}),
    ("side", {"side": "SELL"}),
    ("intent", {"intent": "close"}),
])
def test_distinct_orders_get_distinct_ids(field: str, kw: dict) -> None:
    base = {"symbol": "BTCUSDT", "side": "BUY", "intent": "open", "now": T0}
    assert client_order_id(**base) != client_order_id(**{**base, **kw}), field


def test_close_and_open_never_collide() -> None:
    """A cover and an entry on the same symbol/side must not share an ID inside one bucket."""
    assert (client_order_id("BTCUSDT", "BUY", "close", now=T0)
            != client_order_id("BTCUSDT", "BUY", "open", now=T0))


# --------------------------------------------------------------- chunking


def test_each_chunk_gets_its_own_id() -> None:
    """Shared IDs across chunks would have the venue reject chunks 2..n and under-fill the leg."""
    ids = [client_order_id("BTCUSDT", "BUY", "open", chunk=i, now=T0) for i in range(8)]
    assert len(set(ids)) == 8


def test_chunk_ids_are_still_deterministic_across_a_retry() -> None:
    """Idempotency must survive chunking, or a retried split order duplicates every chunk."""
    first = [client_order_id("BTCUSDT", "BUY", "open", chunk=i, now=T0) for i in range(4)]
    retry = [client_order_id("BTCUSDT", "BUY", "open", chunk=i, now=T0 + 1.0) for i in range(4)]
    assert first == retry


# --------------------------------------------------------------- venue constraints


@pytest.mark.parametrize("sym", ["BTCUSDT", "1000CATUSDT", "COOKIEUSDT", "X", "A" * 40])
def test_ids_satisfy_the_venue_format(sym: str) -> None:
    """Binance accepts ^[\\.A-Z\\:/a-z0-9_-]{1,36}$ -- an over-long ID is a rejected order."""
    import re
    oid = client_order_id(sym, "SELL", "close", chunk=3, now=T0)
    assert 0 < len(oid) <= MAX_ID_LEN
    assert re.fullmatch(r"[A-Za-z0-9_-]+", oid), oid


def test_ids_are_collision_free_across_a_realistic_book() -> None:
    syms = [f"SYM{i}USDT" for i in range(60)]
    ids = {client_order_id(s, side, intent, chunk=c, now=T0)
           for s in syms for side in ("BUY", "SELL")
           for intent in ("open", "close") for c in range(3)}
    assert len(ids) == 60 * 2 * 2 * 3


# --------------------------------------------------------------- duplicate detection


@pytest.mark.parametrize("err", [
    {"code": -2010, "msg": "Duplicate order sent."},
    {"code": -4015, "msg": "Client order id is not valid: duplicate"},
    "APIError(code=-2010): Duplicate order sent.",
    "duplicate clientOrderId",
])
def test_recognised_duplicates_are_detected(err: object) -> None:
    assert is_duplicate_error(err) is True


@pytest.mark.parametrize("err", [
    {"code": -1021, "msg": "Timestamp for this request is outside of the recvWindow."},
    {"code": -2019, "msg": "Margin is insufficient."},
    "connection reset by peer",
    "",
    None,
    {},
])
def test_unknown_errors_are_never_read_as_already_placed(err: object) -> None:
    """FAIL-CLOSED. Treating an unrecognised error as 'already placed' would silently drop a
    real order and leave a leg naked -- the fail-open branch, in the one place it is fatal."""
    assert is_duplicate_error(err) is False


# --------------------------------------------------------------- wiring


@pytest.mark.parametrize("mod", ["binance_live", "binance_testnet"])
def test_both_futures_connectors_send_a_client_order_id(mod: str) -> None:
    """An idempotency guarantee on only one connector is not a guarantee -- and the executor
    imports the TESTNET module today."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "libs/execution" / f"{mod}.py").read_text("utf-8")
    assert src.count("newClientOrderId") >= 2, "market AND post-only paths must both carry one"
    assert "from libs.execution.idempotency import client_order_id" in src


@pytest.mark.parametrize("mod", ["binance_live", "binance_testnet"])
def test_the_market_path_passes_the_chunk_index(mod: str) -> None:
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "libs/execution" / f"{mod}.py").read_text("utf-8")
    assert "client_order_id(symbol, side, intent, chunk=n, cycle=cycle)" in src, (
        "the chunk counter must reach the ID, or a split order self-rejects after chunk 1")
