"""Locks the 2026-07-31 EV-gate recalibration (R0023/R0034) to its two reference points.

The defect this prevents from regrowing: a threshold sitting ABOVE the best honestly-scored
real candidate, which auto-rejects honesty and rewards inflated est_sharpe. Both anchors are
MEASURED desk classes, not invented numbers: carry-class is the one validated family; the
junk anchor is the graveyard's hard-kill profile.
"""

from __future__ import annotations

from libs.research.alpha_economics import Idea, ev_score


def test_honest_carry_class_queues() -> None:
    idea = Idea(name="carry_class_reference", est_sharpe=0.8, breadth=60,
                orthogonality=1.0, effort_h=20, maintenance=1.5,
                tags=("funding_family",))
    assert "QUEUE" in ev_score(idea)["verdict"]


def test_hard_kill_junk_still_rejects() -> None:
    idea = Idea(name="junk_reference", est_sharpe=0.5, breadth=3,
                orthogonality=0.5, effort_h=20, maintenance=1.5,
                tags=("price_only", "narrow_breadth"))
    assert "REJECT" in ev_score(idea)["verdict"]


def test_modest_honest_idea_is_no_longer_auto_rejected() -> None:
    # The R0034 class: honest modest inputs, real mechanism, decent breadth. Under the 0.05
    # bar this scored ~0.004 and died; it is exactly the many-small-decorrelated profile the
    # constitution says beats one perfect backtest.
    idea = Idea(name="modest_reference", est_sharpe=0.4, breadth=40,
                orthogonality=0.8, effort_h=15, maintenance=1.0, tags=())
    assert "QUEUE" in ev_score(idea)["verdict"]
