"""C5: the eleven-slot mechanism genome, and recombination at the level of the economics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from libs.research import mechanism_genome as mg


def test_eleven_slots_and_every_registered_family_declares_all_of_them() -> None:
    assert len(mg.SLOTS) == 11
    for fam, row in mg.FAMILY_GENOME.items():
        missing = [s for s in mg.SLOTS if not row.get(s)]
        assert not missing, f"{fam} leaves {missing} undeclared"


def test_the_grid_registry_is_fully_declared_and_coherent() -> None:
    """A family the desk can search but cannot describe is the drift this table exists to stop."""
    # `mt5desk` is importable only with desks/mt5 on sys.path (the desk's own tests put it
    # there); adding it here keeps this assertion RUNNING rather than skipping, which is the
    # point -- a skipped coverage test is a coverage claim nobody cashed.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desks" / "mt5"))
    try:
        from mt5desk.families import FAMILY_REGISTRY
    except Exception:                                       # pragma: no cover - import env
        pytest.skip("mt5desk.families is not importable on this host")
    c = mg.census(list(FAMILY_REGISTRY))
    assert c["n_undeclared"] == 0, c["undeclared"]
    assert c["incoherent"] == [], c["incoherent"]


def test_an_unknown_family_is_undeclared_rather_than_guessed() -> None:
    g = mg.from_family("a_family_nobody_registered")
    assert g.declared is False
    assert g.n_declared == 0
    assert g.actor == mg.UNDECLARED


def test_incoherent_children_are_not_minted() -> None:
    a = mg.from_family("overnight_drift")          # risk_premium / next_open / overnight
    b = mg.from_family("cot_net_fade")             # risk_premium / signal_flip / multiweek
    kids = mg.recombine(a, b)
    for k in kids:
        ok, why = mg.compatible(mg.Genome(declared=True, family="child",
                                          **{s: k["genome"][s] for s in mg.SLOTS}))
        assert ok, why
    # Taking `exit=weekly_rebalance` into an intraday parent is exactly what must not be minted.
    bad = mg.Genome(declared=True, holding="intraday", exit="weekly_rebalance")
    ok, why = mg.compatible(bad)
    assert not ok and "holding" in why


def test_a_child_differs_from_its_parent_in_exactly_one_slot() -> None:
    a = mg.from_family("session_range_breakout")
    b = mg.from_family("carry")
    for k in mg.recombine(a, b):
        diff = [s for s in mg.SLOTS if k["genome"][s] != getattr(a, s)]
        assert diff == [k["slot"]], (k["slot"], diff)


def test_an_undeclared_transmission_is_unjudged_not_incompatible() -> None:
    """UNMEASURED is a verdict; a missing table row must not become one about an alpha."""
    ok, _why = mg.compatible(mg.Genome(declared=True, trigger="time_of_day"))
    assert ok is True
