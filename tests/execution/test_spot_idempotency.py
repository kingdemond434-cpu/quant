"""GAP #49 ON THE SPOT LEG -- the half of the delta-neutral pair it was never wired into.

Every futures order has carried a deterministic client order ID since GAP #49. No spot order
carried one at all, and nothing noticed for the same reason nothing usually does: each connector
tested in isolation looked correct, and the defect lived in the SHAPE OF THE PAIR.

    _cycle = _pair_cycle(sym, spot_side, qty)
    spot_res = spot.place_market(sym, spot_side, qty)                   # <- no ID, no cycle
    fut_res  = fut.place_market(sym, fut_side, qty, ..., cycle=_cycle)  # <- protected

with a comment above it explaining that "a duplicated leg on a delta-neutral book is an unhedged
directional position". On an ambiguous timeout the retry is deduped by the venue on the futures
leg and PLACED AGAIN on the spot leg: two spot longs against one perp short. That is not an
oversized carry, it is a naked long -- produced by the exact mechanism the protection was written
to prevent, arriving through the leg it was never applied to.

HALF AN IDEMPOTENCY GUARANTEE ON A TWO-LEGGED TRADE IS WORSE THAN NONE. With neither leg
protected, a retry doubles both and the book stays hedged at twice the size -- bad, but still
delta-neutral, and the reconciler sees it. With exactly one leg protected, the retry doubles ONLY
the unprotected side, and the imbalance is manufactured by the guard's own asymmetry.

THE LAST TEST IN THIS FILE IS THE ONE THAT WOULD HAVE CAUGHT IT. Unit-testing the connectors can
never find a missing argument at a call site, so the pair placement is asserted structurally
against the executor's source. It is the only kind of test that fails when someone adds a third
leg and wires up two of them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from libs.execution import binance_spot_live as SL
from libs.execution import binance_spot_testnet as ST
from libs.execution.idempotency import BUCKET_S, MAX_ID_LEN

_MODULES = (SL, ST)
_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def mod(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Each spot connector with its signed transport recording instead of sending."""
    m = request.param
    m._sent = []  # type: ignore[attr-defined]

    def _signed(_path: str, params: dict[str, Any], method: str = "GET") -> Any:
        m._sent.append({"method": method, **params})
        return {"orderId": len(m._sent), "status": "FILLED"}

    monkeypatch.setattr(m, "_signed", _signed)
    return m


def test_EVERY_spot_order_carries_a_client_order_id(mod: Any) -> None:
    """The bar itself. An order without one cannot be deduped by the venue, and the venue is the
    only deduplicator that survives a process restart -- which is precisely when the re-place
    happens."""
    mod.place_market("BTCUSDT", "BUY", 1.0)
    mod.place_market_quote("BTCUSDT", "BUY", 100.0)
    mod.place_post_only("BTCUSDT", "BUY", 1.0, 90.0)
    assert len(mod._sent) == 3
    for order in mod._sent:
        cid = order.get("newClientOrderId")
        assert cid, f"a spot order went out with no client order ID: {order}"
        assert len(cid) <= MAX_ID_LEN, f"the venue rejects IDs over {MAX_ID_LEN} chars: {cid}"


def test_THE_SAME_CYCLE_REPRODUCES_THE_SAME_ID(mod: Any) -> None:
    """This is the whole guarantee: a retry of one logical order is the same order to the venue.
    Not 'usually the same', not 'the same if the retry is fast' -- the same, with the wall clock
    removed from the identity entirely."""
    mod.place_market("BTCUSDT", "BUY", 1.0, cycle="pair-abc")
    mod.place_market("BTCUSDT", "BUY", 1.0, cycle="pair-abc")
    a, b = (o["newClientOrderId"] for o in mod._sent)
    assert a == b, "a retry inside one cycle produced a NEW id -- the venue would place it again"


def test_A_RETRY_WITH_A_DRIFTED_QUANTITY_IS_STILL_THE_SAME_ORDER(mod: Any) -> None:
    """Quantity is deliberately NOT in the identity. A retry after a partial fill, or after the
    sizer re-reads a balance that moved by dust, is the same logical leg -- and if a hair of drift
    minted a new ID the dedupe would evaporate exactly when it is needed. Pinned because putting
    qty in the hash looks like an obvious improvement and would silently remove the protection."""
    mod.place_market("BTCUSDT", "BUY", 1.0, cycle="pair-abc")
    mod.place_market("BTCUSDT", "BUY", 1.000_001, cycle="pair-abc")
    a, b = (o["newClientOrderId"] for o in mod._sent)
    assert a == b


def test_DIFFERENT_CYCLES_ARE_DIFFERENT_ORDERS(mod: Any) -> None:
    """The opposite error is as bad: if every order on a symbol collapsed to one ID, the SECOND
    genuine rebalance of the day would be rejected as a duplicate and the leg silently never
    placed."""
    mod.place_market("BTCUSDT", "BUY", 1.0, cycle="pair-1")
    mod.place_market("BTCUSDT", "BUY", 1.0, cycle="pair-2")
    a, b = (o["newClientOrderId"] for o in mod._sent)
    assert a != b


def test_SIDE_AND_SYMBOL_AND_ORDER_KIND_ALL_SEPARATE_THE_ID(mod: Any) -> None:
    """A BUY and a SELL colliding would have an unwind rejected as a duplicate of the entry that
    opened it -- the position stays on. And a maker quote must not collide with the taker sweep
    that replaces it when the quote does not fill, or the sweep never goes out."""
    mod.place_market("BTCUSDT", "BUY", 1.0, cycle="c")
    mod.place_market("BTCUSDT", "SELL", 1.0, cycle="c")
    mod.place_market("ETHUSDT", "BUY", 1.0, cycle="c")
    mod.place_market_quote("BTCUSDT", "BUY", 100.0, cycle="c")
    mod.place_post_only("BTCUSDT", "BUY", 1.0, 90.0, cycle="c")
    ids = [o["newClientOrderId"] for o in mod._sent]
    assert len(set(ids)) == len(ids), f"two distinct spot orders share one ID: {ids}"


def test_WITHOUT_A_CYCLE_THE_CLOCK_IS_THE_FALLBACK_AND_IT_HAS_A_SEAM(mod: Any) -> None:
    """Documented honestly rather than sold as equivalent. With no cycle the identity comes from a
    fixed time grid, so an order placed just before a bucket rolls has a retry window of whatever
    is left of it -- after that the retry hashes anew and the venue places the duplicate. That is
    why the pair path passes an explicit cycle, and why this test asserts the fallback EXISTS
    rather than asserting it is sufficient."""
    mod.place_market("BTCUSDT", "BUY", 1.0)
    mod.place_market("BTCUSDT", "BUY", 1.0)
    a, b = (o["newClientOrderId"] for o in mod._sent)
    assert a == b, "back-to-back calls must land in one bucket"
    assert BUCKET_S > 0


def test_the_order_PAYLOAD_is_otherwise_unchanged(mod: Any) -> None:
    """The ID is an addition, not a rewrite. Type, side, and sizing field must be byte-identical to
    before -- a spot order that quietly changed shape is a worse bug than the one being fixed."""
    mod.place_market("BTCUSDT", "BUY", 2.5, cycle="c")
    mod.place_market_quote("BTCUSDT", "BUY", 100.0, cycle="c")
    mod.place_post_only("BTCUSDT", "SELL", 2.5, 90.0, cycle="c")
    market, quote, maker = mod._sent
    assert market["type"] == "MARKET" and market["quantity"] == 2.5
    assert "quoteOrderQty" not in market, "a base-sized order grew a quote field"
    assert quote["type"] == "MARKET" and quote["quoteOrderQty"] == 100.0
    assert "quantity" not in quote, "sending both sizing fields is a venue rejection"
    assert maker["type"] == "LIMIT_MAKER" and maker["price"] == 90.0
    assert all(o["method"] == "POST" for o in mod._sent)


def test_THE_TWO_CONNECTORS_STAYED_DROP_IN(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live and testnet are documented drop-in replacements, and testnet is where this is rehearsed
    -- including the NEW failure mode, a duplicate rejection, which an operator needs to have seen
    on testnet before it happens with money. A signature that drifted would mean the rehearsal
    exercises a different function from the one that trades."""
    import inspect
    for name in ("place_market", "place_market_quote", "place_post_only"):
        live = inspect.signature(getattr(SL, name))
        test = inspect.signature(getattr(ST, name))
        assert live == test, f"{name} drifted between the live and testnet spot connectors"
        assert "cycle" in live.parameters, f"{name} cannot be made idempotent by its caller"


def test_THE_CASH_CARRY_PAIR_PASSES_ONE_CYCLE_TO_BOTH_LEGS() -> None:
    """THE TEST THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT, and the reason it is structural.

    No unit test of either connector can see a missing argument at a call site. The executor
    computed the cycle token, wrote a comment about unhedged legs, and then handed it to one of
    the two `place_market` calls. Everything below that line passed.

    So this reads the pair-placement source directly and requires BOTH legs to carry the cycle.
    Source-reading tests are usually a smell; here the invariant genuinely is a property of the
    source -- 'every leg of this pair shares one idempotency token' -- and it is the invariant
    that fails silently, in money, when someone adds a third leg and wires up two.
    """
    src = (_ROOT / "scripts" / "run_cashcarry_executor.py").read_text("utf-8")
    legs = re.findall(r"^\s*\w+_res = (?:spot|fut)\.place_market\(.*?\)\s*$",
                      src, flags=re.MULTILINE | re.DOTALL)
    assert len(legs) >= 2, f"pair placement not found -- this test has gone stale: {legs}"
    for leg in legs:
        assert "cycle=" in leg, (
            "a leg of the delta-neutral pair is placed WITHOUT the shared cycle token. Its retry "
            f"will be placed again while the other leg is deduped -> naked directional: {leg}")
    tokens = set(re.findall(r"cycle=(\w+)", " ".join(legs)))
    assert len(tokens) == 1, (
        f"the legs carry DIFFERENT cycle tokens {tokens} -- separate tokens dedupe separately, "
        "which is the same imbalance by a longer route")


def test_EVERY_ORDER_IN_THE_PAIR_MACHINERY_CARRIES_A_CYCLE() -> None:
    """THE MAKER PATH IS THE DEFAULT FOR OPENS, and it had the same hole one level down.

    `_maker_pair` quotes both legs post-only, waits, then TAKER-FILLS whatever did not fill -- and
    the caller wraps the whole thing in `except -> market pair`. So a maker attempt that placed the
    spot taker fallback and then raised (a cancel_all timing out, an open_orders read failing --
    anything after the first line of that loop) fell through to the caller's market pair, which
    placed the spot leg AGAIN. Under two different cycle tokens the venue sees two different
    orders and fills both: double spot against a single perp short.

    So the bar is not "the market fallback is protected", it is EVERY placement inside the pair
    machinery sharing one identity. Asserted over the whole function body rather than the two
    lines that were wrong, because the next hole will be a third placement someone adds.
    """
    src = (_ROOT / "scripts" / "run_cashcarry_executor.py").read_text("utf-8")
    body = src[src.index("def _maker_pair("):src.index("def _filled(")]
    placements = re.findall(r"\.place_(?:market|post_only|market_quote)\(.*?\)", body,
                            flags=re.DOTALL)
    assert placements, "no placements found in _maker_pair -- this test has gone stale"
    for call in placements:
        assert "cycle=" in call, (
            f"an order in the maker path is placed with no shared cycle: {call.strip()}. Its "
            "retry -- including the caller's own market fallback -- is a SECOND order to the "
            "venue, and on a two-legged trade that is a naked directional position.")


def test_THE_CYCLE_IS_COMPUTED_BEFORE_THE_MAKER_ATTEMPT() -> None:
    """Order of two lines, and it decides whether the dedupe exists at all.

    `_pair_cycle` carries a coarse time term, and the maker path deliberately WAITS. Computing the
    token after the maker attempt therefore recomputes it on the far side of that wait, which can
    land in the next window -- so the fallback's identity differs from the attempt it is falling
    back from, at exactly the moment two attempts exist. Cheap to get wrong, invisible in review,
    and it un-does the whole guarantee.
    """
    src = (_ROOT / "scripts" / "run_cashcarry_executor.py").read_text("utf-8")
    body = src[src.index("def _execute_pair_impl("):src.index("def _mark(")]
    assert body.index("_cycle = _pair_cycle(") < body.index("_maker_pair("), (
        "the cycle token is computed AFTER the maker attempt -- the maker path and the market "
        "fallback that catches it would carry different identities across the maker wait")
