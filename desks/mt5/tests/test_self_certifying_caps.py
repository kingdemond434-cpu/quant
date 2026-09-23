"""The family and sleeve caps re-certify themselves -- and the four ways that must not go wrong.

    "Instead of family cap = 60%, sleeve cap = 25%, heat cap = 30% forever ... have an outer
     optimiser evaluate them. Then even your risk architecture is empirical. But eventually even
     60% shouldn't be sacred -- let the cap continuously re-certify itself."
                                                            -- the principal, 2026-09-07

WHAT WAS ALREADY THERE AND WHY THE CAPS WERE LEFT OUT. `missed_growth` measures every rail's
opportunity cost in forward log-wealth and walks the TUNABLE ones toward looseness when they
prove expensive -- never tighter, one STEP per pass, clipped to declared bounds. `hazard_shrink`
and `position_inertia` have been in that loop for days.

The two caps could not join it, for a reason that is easy to miss: the loop only knew how to walk
a multiplier DOWN. For a shrink, down is looser. For a CAP, down is TIGHTER -- so making them
tunable would have made the loop shrink a cap every time it proved expensive, which is the growth
governance running exactly backwards. `Rail.weaken_dir` fixes the direction; every rail that
existed before keeps the default and behaves identically.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import rails  # noqa: E402
from mt5desk.gateway_config_fallback import (  # noqa: E402
    MAX_FAMILY_HEAT_SHARE,
    MAX_SLEEVE_HEAT_SHARE,
)
from research import heat_policy  # noqa: E402


# ------------------------------------------------------------------------ the rails are declared
def test_both_caps_are_tunable_in_the_LOOSENING_direction_only() -> None:
    for name in ("family_cap", "sleeve_share_cap"):
        r = rails.rail(name)
        assert r.tunable, name
        assert r.weaken_dir == "up", f"{name}: walking a cap DOWN tightens it"
        assert r.lo == 1.0, f"{name}: this loop must never walk a cap tighter than declared"
        assert r.hi > 1.0, name
        assert r.weaken_means, f"{name} must say what loosening it means"


def test_the_bound_on_the_bound_keeps_this_a_recertification_not_a_removal() -> None:
    """A rail that can walk to "no rail" is not a rail. The desk has already measured that
    concentration past 60% worsened its tail characteristics, so evidence may loosen the cap and
    may not delete it."""
    assert rails.rail("family_cap").hi == 1.25          # 60% -> at most 75% in one mechanism
    assert rails.rail("sleeve_share_cap").hi == 1.4     # 25% -> at most 35% in one name
    assert MAX_FAMILY_HEAT_SHARE * 1.25 <= 0.75 + 1e-9
    assert MAX_SLEEVE_HEAT_SHARE * 1.4 <= 0.35 + 1e-9


def test_every_pre_existing_rail_still_walks_down() -> None:
    """The direction field must not have silently flipped a rail that was working."""
    for name in ("position_inertia", "hazard_shrink"):
        assert rails.rail(name).weaken_dir == "down", name


# ---------------------------------------------------------------- the caps read the calibration
def test_an_uncalibrated_desk_gets_exactly_the_declared_constants(monkeypatch) -> None:
    """No ledger means multiplier 1.0, which is today's behaviour byte for byte. A missing
    calibration must never move a money-path cap."""
    monkeypatch.setattr(heat_policy, "_rail_mult", lambda name: 1.0)
    fam = heat_policy.enforce_family_cap({"a": 0.09, "b": 0.01}, {"a": "F", "b": "G"}, 0.10)
    assert fam["a"] == pytest.approx(MAX_FAMILY_HEAT_SHARE * 0.10)
    b = heat_policy.per_sleeve_bounds({"a": 0.5}, 0.20)   # tiny dd -> the SHARE cap binds
    assert b["a"] == pytest.approx(MAX_SLEEVE_HEAT_SHARE * 0.20)


def test_a_measured_cost_loosens_the_family_cap_and_nothing_else(monkeypatch) -> None:
    monkeypatch.setattr(heat_policy, "_rail_mult",
                        lambda name: 1.2 if name == "family_cap" else 1.0)
    fam = heat_policy.enforce_family_cap({"a": 0.09, "b": 0.01}, {"a": "F", "b": "G"}, 0.10)
    assert fam["a"] == pytest.approx(MAX_FAMILY_HEAT_SHARE * 1.2 * 0.10)
    b = heat_policy.per_sleeve_bounds({"a": 0.5}, 0.20)
    assert b["a"] == pytest.approx(MAX_SLEEVE_HEAT_SHARE * 0.20), "the sleeve cap must not move"


def test_a_measured_cost_loosens_the_sleeve_cap_and_nothing_else(monkeypatch) -> None:
    monkeypatch.setattr(heat_policy, "_rail_mult",
                        lambda name: 1.3 if name == "sleeve_share_cap" else 1.0)
    b = heat_policy.per_sleeve_bounds({"a": 0.5}, 0.20)
    assert b["a"] == pytest.approx(MAX_SLEEVE_HEAT_SHARE * 1.3 * 0.20)
    fam = heat_policy.enforce_family_cap({"a": 0.09, "b": 0.01}, {"a": "F", "b": "G"}, 0.10)
    assert fam["a"] == pytest.approx(MAX_FAMILY_HEAT_SHARE * 0.10)


def test_an_explicit_share_still_wins_over_the_calibration(monkeypatch) -> None:
    """A caller pinning the cap -- a test, a sweep, a what-if -- is asking a specific question and
    must get a specific answer, not the live calibration."""
    monkeypatch.setattr(heat_policy, "_rail_mult", lambda name: 1.25)
    fam = heat_policy.enforce_family_cap({"a": 0.09, "b": 0.01}, {"a": "F", "b": "G"}, 0.10,
                                         share=0.40)
    assert fam["a"] == pytest.approx(0.04)


def test_a_broken_rails_module_falls_back_to_the_declared_constant(monkeypatch) -> None:
    """`heat_policy` is on the sizing path and must not acquire a hard dependency on a ledger."""
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if name == "libs.portfolio.rails":
            raise ImportError("no rails here")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", boom)
    assert heat_policy._rail_mult("family_cap") == 1.0


def test_the_multiplier_is_clipped_to_the_rails_bounds() -> None:
    """Even a corrupt calibration file cannot push a cap past its declared ceiling."""
    for name, hi in (("family_cap", 1.25), ("sleeve_share_cap", 1.4)):
        r = rails.rail(name)
        assert min(r.hi, max(r.lo, 99.0)) == hi
        assert min(r.hi, max(r.lo, 0.01)) == 1.0


# --------------------------------------------------------------------------- the walk itself
def test_the_calibration_loop_walks_a_cap_UP_and_a_shrink_DOWN() -> None:
    """The direction bug this change exists to fix, pinned in the loop that would have had it."""
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert 'getattr(r, "weaken_dir", "down") == "up"' in src
    assert "nxt = min(r.hi, cur * (1.0 + STEP))" in src
    assert "nxt = max(r.lo, cur * (1.0 - STEP))" in src


def test_the_walk_only_fires_on_a_MEASURED_cost() -> None:
    """A cap is not loosened because nobody measured it. The loop's guard is `verdict != COSTS`,
    and UNMEASURED is not COSTS."""
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert "if v != COSTS:\n            continue" in src


def test_the_loop_never_strengthens_a_rail() -> None:
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert "a rail is never strengthened by this loop" in src
