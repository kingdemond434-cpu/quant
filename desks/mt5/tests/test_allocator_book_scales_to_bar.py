"""A book hotter than the measured bar is SCALED to it, never discarded.

MEASURED ON THE LIVE BOOK 2026-09-14: the allocator solved 0.3000 total heat against a measured
survival envelope of 0.2250. The whole book was refused, the gateway logged `sizing: no allocator
book` on every pass, and every NON-GOLD sleeve -- which takes its size from that book -- had no
fraction at all and could never place. Gold has its own floor path, so the state line read

    armed=True pos=0 pending=4 brackets=['gold_asia'] sleeves=45

forty-five sleeves and one bracket, for as long as the two numbers disagreed. The principal's
report was that the scalps and the FX book had never traded, ever.

Refusing the book is not the conservative outcome. It deployed the 0.02 floor on ONE sleeve --
less heat, on fewer bets, inside the same survival envelope.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from mt5desk.decision_core import book_from_allocation  # noqa: E402

SOLVE = {"a": 0.15, "b": 0.09, "c": 0.06}      # sums to 0.30
BAR = 0.225                                     # the measured survival envelope


def test_a_book_over_the_bar_is_scaled_not_refused() -> None:
    book, why = book_from_allocation(BAR, dict(SOLVE), None, certified=True, why="test")
    assert book is not None, "refusing the book is what left 44 sleeves unsized"
    assert abs(sum(book.values()) - BAR) < 1e-9, "the total must land exactly on the bar"
    assert "scaled" in why.lower()


def test_every_sleeve_is_sized_BELOW_what_the_optimiser_asked() -> None:
    """Scaling down cannot over-bet. That is the entire safety argument."""
    book, _ = book_from_allocation(BAR, dict(SOLVE), None, certified=True, why="test")
    assert book is not None
    for name, asked in SOLVE.items():
        assert book[name] < asked, f"{name} must receive less than the optimiser asked"


def test_relative_weights_are_preserved() -> None:
    """The weights are the thing the optimiser actually solved for; a scale must not distort them."""
    book, _ = book_from_allocation(BAR, dict(SOLVE), None, certified=True, why="test")
    assert book is not None
    assert abs(book["a"] / book["b"] - SOLVE["a"] / SOLVE["b"]) < 1e-9
    assert abs(book["b"] / book["c"] - SOLVE["b"] / SOLVE["c"]) < 1e-9


def test_a_book_summing_BELOW_the_budget_is_still_refused() -> None:
    """Scaling UP would deploy heat the optimiser never allocated. Only downward is safe."""
    thin = {"a": 0.05, "b": 0.03}               # sums to 0.08 against a 0.225 budget
    book, why = book_from_allocation(BAR, thin, None, certified=True, why="test")
    assert book is None, "a thin book must not be inflated to fill the bar"
    assert "heat says" in why


def test_a_book_already_inside_the_bar_is_untouched() -> None:
    """The common case must not be perturbed by the clamp path."""
    inside = {"a": 0.10, "b": 0.08, "c": 0.045}   # sums to 0.225, exactly the budget
    book, why = book_from_allocation(BAR, dict(inside), None, certified=True, why="test")
    assert book is not None
    assert book == inside
    assert "scaled" not in why.lower()
