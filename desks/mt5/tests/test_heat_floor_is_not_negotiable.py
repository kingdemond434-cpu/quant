"""THE 20% NOMINAL FLOOR IS THE PRINCIPAL'S ONE FIXED POLICY, AND NOTHING MAY QUIETLY LOWER IT.

    "keep minimum 24 7 deployed heat floor 20 dont let it deploy below it even if it asks fr
     evidence blah blah to move upto 20"                        -- the principal, 2026-09-05

Everything else on this desk is falsifiable and E[log W]-governed. This is not. It is a standing
instruction to have capital at work, and the desk's job is to find the best composition that
satisfies it -- never to satisfy itself that today is an exception.

WHY A TEST AND NOT A COMMENT. The floor has already been eroded once by a mechanism that looked
principled: `evidence_readiness()` ramped it with out-of-sample evidence, so a book of
backtest-only sleeves was held below 20% until it had "earned" the target. That is a defensible
piece of risk thinking and it is not the principal's policy, and the difference was visible only
to someone reading `resolve()` line by line. The ramp is gone. This is what stops the next one:
any future mechanism -- a readiness gate, a drift sentinel, a novelty flag, a concentration
penalty, a confidence discount -- that pulls the resolved heat below the floor fails here, by
name, whatever its reasoning.

WHAT IS *NOT* FENCED, deliberately. Everything ABOVE the floor stays evidence-determined: the
growth curve may license 23%, 31%, 42%, 45%, and the effective-heat ceiling may hold the book at
the floor when independent risk has not been earned. Holding AT the floor is correct. Going below
it is the thing that cannot happen.

THE ONE LEGITIMATE EXCEPTION IS TECHNICAL, NOT ANALYTICAL. Market closed, broker down, prices
stale, exposure unknown, reconciliation failed, no certified executable sleeve -- then the floor
is UNSATISFIABLE and must say so explicitly with its cause, rather than being silently reduced to
whatever was reachable. `mandate=False` is that path: an explicit caller-level declaration, not
something a scoring function can reach on its own.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import heat_policy as hp  # noqa: E402


def _resolve(free_optimum: float = 0.03, **kw):
    """resolve() with the mandate on and a free optimum BELOW the floor by default.

    Below on purpose: the floor only does anything when the unconstrained growth optimum wants
    less than 20%, so a default that sits above it would make most of this file pass without the
    floor existing at all.
    """
    kw.setdefault("mandate", True)
    return hp.resolve(free_optimum, **kw)


def test_the_floor_is_the_target_flat() -> None:
    """No argument to resolve() produces a floor below the target while the mandate is on."""
    v = _resolve(curve={}, readiness=0.0)
    assert v.floor == pytest.approx(hp.HEAT_TARGET), (
        f"floor {v.floor} is not the {hp.HEAT_TARGET} target -- something is scaling it")


@pytest.mark.parametrize("readiness", [0.0, 0.01, 0.25, 0.5, 0.75, 0.99, 1.0])
def test_readiness_never_moves_the_floor(readiness: float) -> None:
    """The exact defect that was removed: readiness is REPORTED, it is not an input to the floor.

    Parameterised across the whole range rather than tested at 0 and 1, because a ramp is a
    property of the middle -- a reintroduced ramp that happened to be flat at the endpoints would
    pass a two-point test and still hold a half-evidenced book at 12%.
    """
    v = _resolve(curve={}, readiness=readiness)
    assert v.floor == pytest.approx(hp.HEAT_TARGET)
    assert v.total_heat >= hp.HEAT_TARGET - 1e-9, (
        f"readiness {readiness} pulled deployed heat to {v.total_heat:.4%}, below the "
        f"{hp.HEAT_TARGET:.0%} floor. The floor is the principal's one fixed policy: readiness "
        f"may change WHICH sleeves carry the heat, never HOW MUCH the book carries.")


def test_a_growth_curve_that_wants_less_is_floored_not_obeyed() -> None:
    """The optimum below the floor is exactly when the floor is doing its job.

    A curve whose peak is beneath 20% is the case a purely E[log W]-governed desk would answer by
    standing down. The principal's instruction overrides that, and `binding` must say so out loud
    rather than the number quietly arriving from somewhere else.
    """
    curve = {0.05: 0.004, 0.10: 0.002, 0.20: -0.001, 0.30: -0.006}
    v = _resolve(curve=curve, readiness=1.0)
    assert v.total_heat >= hp.HEAT_TARGET - 1e-9
    assert v.binding == "mandate", f"floored to {v.total_heat:.2%} but binding says {v.binding!r}"


def test_the_effective_heat_ceiling_holds_at_the_floor_and_never_under_it() -> None:
    """A concentrated book is held AT 20% nominal, not cut below it.

    The ceiling counts EFFECTIVE heat and the floor counts NOMINAL, and this asymmetry is the
    whole design: measuring the floor in effective terms would let a correlation estimate cut the
    book's deployed capital and call it diversification. Concentration limits WHICH combinations
    may satisfy the floor and is a reason to research independent opportunities. It is not a
    reason to stand down.
    """
    for eff in (0.0, 0.01, 0.05, 0.5, 1.0):
        v = _resolve(0.03, curve={0.2: 0.01, 0.3: 0.02, 0.45: 0.03}, readiness=1.0,
                     effective_heat=eff)
        assert v.total_heat >= hp.HEAT_TARGET - 1e-9, (
            f"effective heat {eff} pulled nominal deployed heat to {v.total_heat:.4%}")


def test_a_state_curve_may_raise_the_floor_and_may_never_cut_it() -> None:
    """Rule 2 in one line, and rule 1 in the other: opportunity raises, nothing reduces."""
    cut = {"stress": hp.StateCurve("stress", {0.05: 0.01, 0.2: -0.02}, 400)}
    v = _resolve(curve={0.2: 0.005}, readiness=1.0, curves=cut, state="stress")
    assert v.total_heat >= hp.HEAT_TARGET - 1e-9, (
        "a state-conditional curve cut the book below the floor -- a reduction is a rail and "
        "this one has not proved its dE[log W]")


def test_room_above_the_floor_is_still_earned_not_granted() -> None:
    """The fence must not become a reason to deploy MORE. 20% is a floor, not a target to exceed.

    Without this the file above reads as "heat may only go up", and the next edit that reaches
    for the hard ceiling by default would pass every test here. Everything above the floor stays
    evidence-determined, which is the half of the policy that is NOT fixed.
    """
    v = _resolve(0.30, curve={0.2: 0.01, 0.3: 0.005, 0.45: -0.01}, readiness=1.0)
    assert v.total_heat <= hp.HEAT_HARD_CEILING + 1e-9
    assert v.total_heat < 0.45, (
        "the book took the top of the measurable range while the curve turned negative there -- "
        "45% is part of the search DOMAIN, never a target")


def test_the_fence_can_actually_fail() -> None:
    """L1.28a. If `resolve` ever stopped flooring, these assertions must be able to see it.

    `mandate=False` is the one path that legitimately produces no floor -- the explicit
    caller-level declaration used when the floor is technically unsatisfiable. It must therefore
    behave differently from the mandated path, or every assertion above is passing on a constant.
    """
    off = hp.resolve(0.03, curve={0.05: 0.01, 0.2: -0.05}, readiness=1.0, mandate=False)
    assert off.floor == 0.0, "mandate=False must yield no floor, or the fence proves nothing"
    assert off.total_heat < hp.HEAT_TARGET, (
        "with the mandate off and a curve that peaks at 5%, resolved heat should fall below the "
        "target -- if it does not, the floor is coming from somewhere this fence cannot see")
