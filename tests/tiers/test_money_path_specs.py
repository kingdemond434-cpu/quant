"""Formal-verification specs over the REAL money-path function (Tier S layer 31).

Property tests on `decision_core.book_from_allocation`, the pure function that turns the
allocator's artifact into per-sleeve risk fractions. Specs only: this file asserts invariants and
changes nothing in the money path.

  ZERO MEANS NO ORDER    a sleeve the allocator zeroed, and the funding book does not fund,
                         comes back at exactly 0.0
  NO NEGATIVE RISK       every returned fraction is >= 0
  EXPOSURE LIMIT         a returned book never sums above the certified total (+ the 0.005
                         drift tolerance the function itself enforces)
"""
from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from mt5desk.decision_core import book_from_allocation  # noqa: E402

names = st.sampled_from([f"s{i}" for i in range(8)])
weights = st.dictionaries(names, st.floats(0.0, 0.1, allow_nan=False), max_size=8)


@settings(max_examples=300, deadline=None)
@given(total=st.floats(0.0, 0.3, allow_nan=False), book=weights, fb=weights,
       zeroed=st.lists(names, max_size=8), certified=st.booleans())
def test_book_from_allocation_invariants(total: float, book: dict[str, float],
                                         fb: dict[str, float], zeroed: list[str],
                                         certified: bool) -> None:
    out, why = book_from_allocation(total, book, {"book": fb, "name": "baseline"},
                                    certified=certified, why="spec", zeroed=zeroed)
    assert isinstance(why, str)
    if out is None:
        return
    assert all(v >= 0.0 for v in out.values())
    assert sum(out.values()) <= total + 0.005 + 1e-9
    funding = {k for k, v in (book if certified else fb).items() if v > 0}
    for z in zeroed:
        if z not in funding:
            assert out.get(z, 0.0) == 0.0
