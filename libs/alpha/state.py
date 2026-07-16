"""Alpha lifecycle state machine.

candidate -> probation -> active -> watch -> decaying -> retirement_candidate -> retired,
with recovery edges (watch -> active, decaying -> watch) and an emergency path to retired from
any live state. Transitions are validated; an invalid transition raises.
"""

from __future__ import annotations

from enum import StrEnum

from libs.alpha.errors import AlphaStateError


class AlphaState(StrEnum):
    CANDIDATE = "candidate"
    PROBATION = "probation"
    ACTIVE = "active"
    WATCH = "watch"
    DECAYING = "decaying"
    RETIREMENT_CANDIDATE = "retirement_candidate"
    RETIRED = "retired"


# Forward (toward retirement) + recovery edges. RETIRED is terminal.
ALLOWED_TRANSITIONS: dict[AlphaState, frozenset[AlphaState]] = {
    AlphaState.CANDIDATE: frozenset({AlphaState.PROBATION, AlphaState.RETIRED}),
    AlphaState.PROBATION: frozenset(
        {AlphaState.ACTIVE, AlphaState.RETIREMENT_CANDIDATE, AlphaState.RETIRED}
    ),
    AlphaState.ACTIVE: frozenset({AlphaState.WATCH, AlphaState.DECAYING, AlphaState.RETIRED}),
    AlphaState.WATCH: frozenset(
        {AlphaState.ACTIVE, AlphaState.DECAYING, AlphaState.RETIREMENT_CANDIDATE,
         AlphaState.RETIRED}
    ),
    AlphaState.DECAYING: frozenset(
        {AlphaState.WATCH, AlphaState.RETIREMENT_CANDIDATE, AlphaState.RETIRED}
    ),
    AlphaState.RETIREMENT_CANDIDATE: frozenset({AlphaState.RETIRED, AlphaState.WATCH}),
    AlphaState.RETIRED: frozenset(),
}

# The canonical "promote upward" target for each state.
_PROMOTE_TARGET: dict[AlphaState, AlphaState] = {
    AlphaState.CANDIDATE: AlphaState.PROBATION,
    AlphaState.PROBATION: AlphaState.ACTIVE,
    AlphaState.WATCH: AlphaState.ACTIVE,
    AlphaState.DECAYING: AlphaState.WATCH,
}


def can_transition(from_state: AlphaState, to_state: AlphaState) -> bool:
    """Whether ``from_state -> to_state`` is an allowed transition."""
    return to_state in ALLOWED_TRANSITIONS[from_state]


def assert_transition(from_state: AlphaState, to_state: AlphaState) -> None:
    """Raise :class:`AlphaStateError` if the transition is not allowed."""
    if not can_transition(from_state, to_state):
        raise AlphaStateError(f"illegal transition {from_state.value} -> {to_state.value}")


def promote_target(from_state: AlphaState) -> AlphaState:
    """The state an alpha is promoted *to* from ``from_state``."""
    try:
        return _PROMOTE_TARGET[from_state]
    except KeyError as exc:
        raise AlphaStateError(f"cannot promote from {from_state.value}") from exc
