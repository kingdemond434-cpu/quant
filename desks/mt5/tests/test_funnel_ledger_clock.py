"""The funnel ledger and the trial allocator run on the hourly core clock (Hourly pass 88).

Their only roster was hourly_discovery.ORGANS, which no task runs; the box's
conversion_ledger.json still read generated_utc 2026-09-05 on 2026-11-10.
"""
from __future__ import annotations

import inspect

import hourly_cycle as HC

from libs.research import layers


def test_both_legs_are_core_legs():
    assert {"conversion_ledger", "trial_allocator"} <= HC.CORE_LEGS


def test_both_legs_run_their_organs():
    src = inspect.getsource(HC.conversion_ledger) + inspect.getsource(HC.trial_allocator)
    assert "research/conversion_ledger.py" in src
    assert "research/trial_allocator.py" in src


def test_main_costs_and_reports_both_legs():
    src = inspect.getsource(HC.main)
    assert '_costed("conversion_ledger", conversion_ledger)' in src
    assert '_costed("trial_allocator", trial_allocator)' in src
    assert '"conversion_ledger": cvl' in src and '"trial_allocator": tra' in src


def test_both_legs_belong_to_a_layer():
    for leg in ("conversion_ledger", "trial_allocator"):
        assert layers.LEG_LAYER[leg] == "information"
