"""THE LIVE ORDER PATH -- the least-tested substantial code in the repository.

Coverage was measured for the first time on 2026-08-04 and the shape inverted the risk:
`binance_live.py` sat at 29.9% while the repo sat at 88.1%. The code that can place orders and
move funds was the code nobody tested, and a real defect in `_market_max_qty` was found the same
day sitting in the seventy percent that nothing exercised.

Every test here is on an ERROR or BOUNDARY branch rather than a happy path, because every incident
this desk has recorded came from one:

  incident #6   accumulated resting fills walked a short THROUGH ZERO into a +916,772 long
  the -4005     COOKIEUSDT maxQty 150,000 rejected every 183,140-unit order, which is what pushed
                the executor onto the resting-limit fallback that caused #6
  GAP #49       an ambiguous timeout is indistinguishable from a failure, so a retry places a
                SECOND leg -- on a delta-neutral book, an unhedged directional position

No network. `_signed` and `_get` are replaced, so nothing here can reach a venue.
"""

from __future__ import annotations

import pytest

from libs.execution import binance_live as L


@pytest.fixture
def venue(monkeypatch):
    """A recording stand-in for the signed endpoint. Returns the calls it was asked to make."""
    sent: list[dict] = []

    def _signed(path, params, method="GET"):
        sent.append({"path": path, "method": method, **params})
        return {"orderId": len(sent), "status": "FILLED"}

    monkeypatch.setattr(L, "_signed", _signed)
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"symbols": []})
    L._MKT_MAX_CACHE.clear()
    yield sent
    L._MKT_MAX_CACHE.clear()


def test_an_order_above_the_venue_cap_is_SPLIT_not_rejected(venue) -> None:
    """THE -4005 INCIDENT, DIRECTLY. COOKIEUSDT's maxQty is 150,000 and the executor sent 183,140
    in one order; the venue rejected all of it and the fallback path did the damage."""
    L._MKT_MAX_CACHE["COOKIEUSDT"] = 150_000.0
    L.place_market("COOKIEUSDT", "BUY", 183_140.0)
    qtys = [c["quantity"] for c in venue]
    assert len(qtys) == 2, f"expected a split, got {qtys}"
    assert max(qtys) <= 150_000.0, "a chunk exceeded the venue cap -- this is the -4005 again"
    assert sum(qtys) == pytest.approx(183_140.0), "the split lost or invented quantity"


def test_every_chunk_carries_a_DISTINCT_client_order_id(venue) -> None:
    """GAP #49's second half. Sharing one ID across chunks makes the venue reject chunks 2..n as
    duplicates and silently UNDER-FILL the leg -- which on a delta-neutral book is a naked
    directional position that nothing reports."""
    L._MKT_MAX_CACHE["COOKIEUSDT"] = 100.0
    L.place_market("COOKIEUSDT", "SELL", 250.0)
    ids = [c["newClientOrderId"] for c in venue]
    assert len(ids) == 3
    assert len(set(ids)) == 3, f"chunks shared an ID -- the venue will drop all but one: {ids}"


def test_the_same_logical_order_is_IDEMPOTENT_across_a_retry(venue) -> None:
    """The reason the ID exists at all: an ambiguous timeout is indistinguishable from a failure,
    so the retry must present the SAME id and be rejected as a duplicate rather than fill twice."""
    L._MKT_MAX_CACHE["BTCUSDT"] = float("inf")
    L.place_market("BTCUSDT", "BUY", 1.0, cycle="cycle-a")
    first = venue[-1]["newClientOrderId"]
    L.place_market("BTCUSDT", "BUY", 1.0, cycle="cycle-a")
    assert venue[-1]["newClientOrderId"] == first, (
        "a retry of the same logical order minted a NEW id -- the venue cannot dedupe it and the "
        "position doubles")


def test_a_close_and_an_open_never_share_an_id(venue) -> None:
    """GAP #49's first half: intent is in the ID because a cover and an entry on the same symbol
    and side within one cycle would otherwise collide, and the venue would drop the second."""
    L._MKT_MAX_CACHE["BTCUSDT"] = float("inf")
    L.place_market("BTCUSDT", "BUY", 1.0, reduce_only=True, cycle="c1")
    close_id = venue[-1]["newClientOrderId"]
    L.place_market("BTCUSDT", "BUY", 1.0, reduce_only=False, cycle="c1")
    assert venue[-1]["newClientOrderId"] != close_id


def test_reduce_only_is_transmitted_because_it_is_what_forbids_passing_through_zero(venue) -> None:
    """The flag that makes a cover arithmetically incapable of opening the opposite position. Its
    absence is incident #6's mechanism, so it is asserted on the wire, not at the call site."""
    L._MKT_MAX_CACHE["BTCUSDT"] = float("inf")
    L.place_market("BTCUSDT", "SELL", 2.0, reduce_only=True)
    assert venue[-1].get("reduceOnly") == "true"
    L.place_market("BTCUSDT", "SELL", 2.0, reduce_only=False)
    assert "reduceOnly" not in venue[-1], "an OPEN must never be sent reduce-only: it would no-op"


def test_the_chunk_loop_cannot_spin_forever(venue) -> None:
    """A cap of zero or a rounding pathology must not produce an unbounded stream of orders at a
    live venue. The bound is 50 chunks, and it is a rail rather than a tuning knob."""
    L._MKT_MAX_CACHE["X"] = 1e-9
    L.place_market("X", "BUY", 1_000_000.0)
    assert len(venue) <= 50, f"the loop placed {len(venue)} orders -- it is not bounded"


def test_a_post_only_order_is_GTX_and_carries_its_own_intent(venue) -> None:
    """Post-only is guaranteed-maker: rejected rather than crossed. A resting order is MORE
    dangerous to duplicate than a market order, not less -- incident #6 was resting fills."""
    L._MKT_MAX_CACHE["BTCUSDT"] = float("inf")
    L.place_post_only("BTCUSDT", "BUY", 1.0, 50_000.0, cycle="c9")
    sent = venue[-1]
    assert sent["timeInForce"] == "GTX"
    post_id = sent["newClientOrderId"]

    # The intent is HASHED into the id rather than spelled out, so the property to assert is the
    # one that matters operationally: a post-only and a market order on the same symbol, side and
    # cycle must not collide. Asserting the literal word would have been a test of the encoding,
    # which is free to change, instead of the invariant, which is not.
    L.place_market("BTCUSDT", "BUY", 1.0, cycle="c9")
    assert venue[-1]["newClientOrderId"] != post_id, (
        "a resting post-only and a market order shared an id -- the venue drops one, and the leg "
        "silently under-fills")
