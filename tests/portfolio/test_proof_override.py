"""A hold is only a hold if the held book still holds its certificate."""
from __future__ import annotations

from libs.portfolio.allocator_proof import MARGIN_FRAC, held_book_still_wins


def _s(v: float) -> dict[str, float]:
    return {"robust_score": v, "mean_log_growth": v}


def test_held_book_that_beats_the_bench_by_the_margin_wins() -> None:
    scores = {"dynamic": _s(0.02), "static_incumbent": _s(0.0110),
              "robust_kelly": _s(0.0100), "equal_weight": _s(0.005)}
    ok, why = held_book_still_wins(scores)
    assert ok and "robust_kelly" in why


def test_held_book_inside_the_margin_loses() -> None:
    best = 0.0100
    scores = {"dynamic": _s(0.02), "static_incumbent": _s(best + best * MARGIN_FRAC * 0.5),
              "robust_kelly": _s(best)}
    ok, _ = held_book_still_wins(scores)
    assert not ok


def test_ruinous_or_missing_incumbent_never_wins() -> None:
    assert held_book_still_wins({"dynamic": _s(0.02), "robust_kelly": _s(0.01)})[0] is False
    assert held_book_still_wins({"dynamic": _s(0.02), "static_incumbent": _s(float("-inf")),
                                 "robust_kelly": _s(0.01)})[0] is False


def test_no_finite_rival_means_the_hold_stands() -> None:
    ok, why = held_book_still_wins({"static_incumbent": _s(0.01),
                                    "equal_weight": _s(float("-inf"))})
    assert ok and "no finite baseline" in why
