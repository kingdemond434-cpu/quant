"""Tests for the alpha lifecycle state machine."""

from __future__ import annotations

import pytest

from libs.alpha.errors import AlphaStateError
from libs.alpha.state import AlphaState, assert_transition, can_transition, promote_target


def test_states_present() -> None:
    assert {s.value for s in AlphaState} == {
        "candidate", "probation", "active", "watch", "decaying",
        "retirement_candidate", "retired",
    }


def test_legal_and_illegal_transitions() -> None:
    assert can_transition(AlphaState.CANDIDATE, AlphaState.PROBATION)
    assert can_transition(AlphaState.ACTIVE, AlphaState.RETIRED)
    assert not can_transition(AlphaState.CANDIDATE, AlphaState.ACTIVE)  # must pass probation
    assert not can_transition(AlphaState.RETIRED, AlphaState.ACTIVE)  # terminal


def test_promote_targets() -> None:
    assert promote_target(AlphaState.CANDIDATE) is AlphaState.PROBATION
    assert promote_target(AlphaState.PROBATION) is AlphaState.ACTIVE
    assert promote_target(AlphaState.WATCH) is AlphaState.ACTIVE
    assert promote_target(AlphaState.DECAYING) is AlphaState.WATCH


def test_promote_from_active_is_invalid() -> None:
    with pytest.raises(AlphaStateError):
        promote_target(AlphaState.ACTIVE)


def test_assert_transition_raises() -> None:
    with pytest.raises(AlphaStateError):
        assert_transition(AlphaState.CANDIDATE, AlphaState.RETIREMENT_CANDIDATE)
