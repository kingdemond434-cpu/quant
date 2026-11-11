"""A row that already holds a shared book key carries it; no second row ever sends (#896 MF2).

The carrier walk hands a shared key's whole fraction to the best-evidenced row that FIRES this
pass. Without a holder rule it can pick row A on one pass (B did not fire) and row B on the next
(B now fires and out-ranks A) while A's position from the first pass is still open: two
positions on one allocator cell. These pin the rule end to end on the decision functions and on
the gateway's own venue read:

  * a holder ranks first on its key, ahead of the exact owner and of any better-evidenced twin;
  * the walk is SEEDED with the holder (`held_carriers`), so the fallback can never hand the key
    to anyone else that pass, fired or not;
  * the two-pass scenario above ends with exactly one sending row on the key;
  * `_rows_holding` reads this desk's positions AND resting orders by MAGIC and tag, and an
    unreadable venue seeds nobody.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402

KEY = "CHFNOK_carry_asia"
JOINS = [("chfnok_carry_asia_p_a1", KEY), ("chfnok_carry_asia_p_b2", KEY),
         ("eurusd_trend_ny", "EURUSD_trend_ny")]
EVIDENCE = {"chfnok_carry_asia_p_a1": (0.0, 5.0, 1.0),     # thin record
            "chfnok_carry_asia_p_b2": (12.0, 40.0, 6.0)}   # far better evidenced


def _pass(holding: set[str], fires: set[str]) -> dict[str, float]:
    """One pass of the gateway's carrier decision, exactly as `main` composes it: the pre-pass
    carrier, the walk seeded with the holder, the fallback to the first row that fires."""
    shares = dc.book_shares(JOINS)
    carriers = dc.book_carriers(JOINS, EVIDENCE, holding)
    order = dc.book_carrier_order(JOINS, EVIDENCE, holding)
    carried = dc.held_carriers(order, holding)
    book = {KEY: 0.04, "EURUSD_trend_ny": 0.02}
    sent: dict[str, float] = {}
    for key, rows in order.items():
        for name in rows:
            carrier = carriers.get(name, name)
            if int(shares.get(name, 1)) > 1 and carrier != key:
                carrier = carried.get(key, name)
            frac = book[key] if carrier == name else 0.0
            if frac > 0.0 and name in fires:
                sent[name] = frac
                carried.setdefault(key, name)
    return sent


def test_a_holder_ranks_first_over_owner_and_evidence() -> None:
    order = dc.book_carrier_order(JOINS, EVIDENCE)
    assert order[KEY][0] == "chfnok_carry_asia_p_b2"          # evidence alone picks b2
    held = dc.book_carrier_order(JOINS, EVIDENCE, {"chfnok_carry_asia_p_a1"})
    assert held[KEY][0] == "chfnok_carry_asia_p_a1"           # the holder carries
    owned = [(KEY, KEY), ("chfnok_carry_asia_p_a1", KEY)]
    assert dc.book_carrier_order(owned, None, {"chfnok_carry_asia_p_a1"})[KEY][0] == \
        "chfnok_carry_asia_p_a1", "a holder outranks even the exact owner"
    assert dc.held_carriers(held, {"chfnok_carry_asia_p_a1"}) == {KEY: "chfnok_carry_asia_p_a1"}
    assert dc.held_carriers(held, set()) == {}


def test_two_passes_never_leave_two_positions_on_one_key() -> None:
    # Pass 1: the better-evidenced b2 does not fire, so the walk falls back to a1, which sends.
    first = _pass(holding=set(), fires={"chfnok_carry_asia_p_a1"})
    assert set(first) == {"chfnok_carry_asia_p_a1"}
    # Pass 2: a1's position is still open and b2 now fires. Without the holder rule b2 carried
    # and sent -- a second position on the cell. With it, a1 carries and b2 sends nothing.
    second = _pass(holding={"chfnok_carry_asia_p_a1"},
                   fires={"chfnok_carry_asia_p_a1", "chfnok_carry_asia_p_b2"})
    assert "chfnok_carry_asia_p_b2" not in second
    # ... even when the holder does not fire again this pass, nobody else takes the key.
    third = _pass(holding={"chfnok_carry_asia_p_a1"}, fires={"chfnok_carry_asia_p_b2"})
    assert third == {}


def test_the_gateway_reads_holders_from_positions_and_orders(monkeypatch) -> None:
    pytest.importorskip("MetaTrader5")
    from mt5desk import gateway as gw
    tag_a = sorted(gw.owned_tags("chfnok_carry_asia_p_a1"))[0]
    tag_b = sorted(gw.owned_tags("chfnok_carry_asia_p_b2"))[0]
    venue = NS(positions_get=lambda: [NS(comment=tag_a, magic=gw.MAGIC)],
               orders_get=lambda: [NS(comment=tag_b, magic=gw.MAGIC + 1)])   # not ours
    monkeypatch.setattr(gw, "mt5", venue)
    monkeypatch.setattr(gw, "log", lambda *_: None)
    names = ["chfnok_carry_asia_p_a1", "chfnok_carry_asia_p_b2"]
    assert gw._rows_holding(names) == frozenset({"chfnok_carry_asia_p_a1"})
    venue.orders_get = lambda: [NS(comment=tag_b, magic=gw.MAGIC)]          # a resting bracket
    assert gw._rows_holding(names) == frozenset(names)

    def _boom() -> list:
        raise RuntimeError("terminal gone")
    venue.positions_get = _boom
    assert gw._rows_holding(names) is None                    # UNMEASURED, never "none held"
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    assert "_carried: dict[str, str] = held_carriers(_carry_order, _holding)" in src
    assert src.index("_held = (_hold_fn(") < src.index("_carriers = book_carriers(")
    # every row with a book key is read, joined or not, and a blocked key sends nothing
    assert "_hold_fn([n for n, k in _raw_key.items() if k is not None])" in src
    assert "_blocked = blocked_book_keys(_raw_key, dict(_joins), _held)" in src
    assert 'if _key in _blocked and _blocked[_key] != _s["name"]:' in src


def test_a_key_held_by_a_zeroed_row_is_blocked_for_every_other_row() -> None:
    """#896 audit MF: a1 holds the cell's position, then cert_book_zero / DECAY_ZERO keeps it out
    of the joins. The walk cannot see it, so without the block b2 would carry and open a second
    position on the same key."""
    raw = {"chfnok_carry_asia_p_a1": KEY, "chfnok_carry_asia_p_b2": KEY,
           "eurusd_trend_ny": "EURUSD_trend_ny"}
    joined = {"chfnok_carry_asia_p_a1": None, "chfnok_carry_asia_p_b2": KEY,
              "eurusd_trend_ny": "EURUSD_trend_ny"}
    blocked = dc.blocked_book_keys(raw, joined, {"chfnok_carry_asia_p_a1"})
    assert blocked == {KEY: "chfnok_carry_asia_p_a1"}
    # the walk alone (a1 not joined) would hand the key to b2: the block is what stops it
    alone = [(n, k) for n, k in joined.items()]
    assert dc.book_carriers(alone, EVIDENCE, set())["chfnok_carry_asia_p_b2"] ==         "chfnok_carry_asia_p_b2"
    # a joined holder is not blocked (it carries); nothing held blocks nothing
    assert dc.blocked_book_keys(raw, dict(raw), {"chfnok_carry_asia_p_a1"}) == {}
    assert dc.blocked_book_keys(raw, joined, set()) == {}


def test_an_unreadable_venue_blocks_every_shared_key_and_no_other() -> None:
    """#896 audit SF2: who holds what is UNMEASURED, never "nothing held"."""
    raw = {"chfnok_carry_asia_p_a1": KEY, "chfnok_carry_asia_p_b2": KEY,
           "eurusd_trend_ny": "EURUSD_trend_ny", "off_book": None}
    assert dc.blocked_book_keys(raw, dict(raw), None) == {KEY: "venue unreadable"}
