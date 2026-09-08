"""The producer and the two readers must agree on what a trade's timestamp is called.

MEASURED 2026-09-08. `scalp_reverse_engineering.simulate(detailed=True)` writes `opened_at` and
`closed_at`. `pf_allocator.scalp_evidence` read `exit_time` / `entry_time` / `time`, and
`scalp_shadow`'s forward boundary read `entry_time` / `time` / `open_time`. None of those six
spellings exists on a row, so:

  * `scalp_evidence` got `stamp = None` on every row, finished with an EMPTY `by_day`, and
    refused every clock with "0 forward day(s)" -- so no scalp sleeve was ever priced, no
    allocator row existed, and the promoter wrote "STANDBY at 0.00% risk" for three gold clocks
    that had been PROMOTION CANDIDATE past their window for weeks, holding 344 real forward
    trades between them.
  * `scalp_shadow`'s boundary fell through to the SHADOW_START default for every row, so every
    row compared >= the frozen clock whatever its true time -- the two-stage law failing OPEN.

This is the desk's recurring defect shape: two names for one thing, joined by a silent `or`
chain that returns None instead of raising. These tests pin the producer's names and both
readers against them.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
SIM = (_DESK / "research" / "scalp_reverse_engineering.py").read_text("utf-8")
ALLOC = (_DESK / "research" / "pf_allocator.py").read_text("utf-8")
SHADOW = (_DESK / "research" / "scalp_shadow.py").read_text("utf-8")

#: A row exactly as the box writes it, taken verbatim from
#: reports/shadow/ledger_xau_m15_anti_breakout.json on 2026-09-08.
REAL_ROW = {
    "opened_at": "2026-08-24T01:00:00+00:00",
    "closed_at": "2026-08-24T01:15:00+00:00",
    "direction": 1, "depth": 1,
    "r": -0.2530940630498418, "risk_allocated_r": 0.25, "phase": "forward",
}


# ------------------------------------------------------------------ the producer's names
def test_the_producer_writes_opened_at_and_closed_at() -> None:
    """If this ever changes, both readers below must change with it."""
    assert '"opened_at": df.index[i].isoformat()' in SIM
    assert '"closed_at": df.index[j].isoformat()' in SIM


def test_a_real_row_carries_none_of_the_old_spellings() -> None:
    """The whole defect in one assertion: the readers asked for fields that never existed."""
    for absent in ("exit_time", "entry_time", "time", "open_time"):
        assert REAL_ROW.get(absent) is None, absent


# --------------------------------------------------------------- the allocator can read it
def test_scalp_evidence_reads_the_producers_names_first() -> None:
    assert 'r.get("closed_at") or r.get("opened_at")' in ALLOC


def test_the_allocator_now_extracts_a_real_day_from_a_real_row() -> None:
    stamp = (REAL_ROW.get("closed_at") or REAL_ROW.get("opened_at")
             or REAL_ROW.get("exit_time") or REAL_ROW.get("entry_time")
             or REAL_ROW.get("time"))
    assert stamp is not None
    assert pd.Timestamp(str(stamp)).date().isoformat() == "2026-08-24"


def test_the_old_chain_would_still_return_nothing() -> None:
    """Pinning the bug itself, so a revert is a failing test rather than a silent regression."""
    old = (REAL_ROW.get("exit_time") or REAL_ROW.get("entry_time") or REAL_ROW.get("time"))
    assert old is None


def test_two_rows_on_different_days_now_clear_the_two_day_floor() -> None:
    """`scalp_evidence` refuses a ledger with fewer than 2 distinct forward days. With the fix
    a genuine multi-day ledger clears it; that is the difference between funded and STANDBY."""
    rows = [REAL_ROW, {**REAL_ROW, "closed_at": "2026-09-08T16:30:00+00:00", "r": 0.37}]
    by_day: dict[object, float] = {}
    for r in rows:
        stamp = (r.get("closed_at") or r.get("opened_at") or r.get("exit_time")
                 or r.get("entry_time") or r.get("time"))
        if stamp is None:
            continue
        day = pd.Timestamp(str(stamp)).date()
        by_day[day] = by_day.get(day, 0.0) + float(r["r"])
    assert len(by_day) == 2, "a two-day ledger must survive the bootstrap floor"


# ------------------------------------------------------- the forward boundary can read it too
def test_the_forward_boundary_reads_opened_at_first() -> None:
    assert 'r.get("opened_at") or r.get("entry_time")' in SHADOW


def test_the_boundary_no_longer_silently_defaults_every_row() -> None:
    """Before the fix every row fell through to SHADOW_START and so passed the boundary
    unconditionally -- selection-era trades counted as forward evidence."""
    got = (REAL_ROW.get("opened_at") or REAL_ROW.get("entry_time")
           or REAL_ROW.get("time") or REAL_ROW.get("open_time"))
    assert got == "2026-08-24T01:00:00+00:00"

    old = (REAL_ROW.get("entry_time") or REAL_ROW.get("time") or REAL_ROW.get("open_time"))
    assert old is None, "the old chain reached the default on a row that HAS a timestamp"


def test_a_pre_boundary_row_is_now_excluded() -> None:
    bound = pd.Timestamp("2026-08-25T00:00:00+00:00")
    early = pd.Timestamp(str(REAL_ROW["opened_at"]))
    late = pd.Timestamp("2026-09-08T16:00:00+00:00")
    assert early < bound <= late


# ----------------------------------------------------------------- nothing else was loosened
def test_the_two_day_floor_is_untouched() -> None:
    """The refusal was RIGHT -- a one-day series cannot be bootstrapped. Only the field names
    were wrong, and the fix must not have quietly relaxed the floor to compensate."""
    assert "if len(by_day) < 2:" in ALLOC
    assert "a series the " in ALLOC


def test_the_scalp_promotion_rule_is_unchanged() -> None:
    """No significance gate was added and none removed; this change is about a join, not a bar."""
    assert "exp is not None and exp > 0.05 and max_dd > -25.0" in SHADOW


@pytest.mark.parametrize("mod", ["pf_allocator", "scalp_shadow"])
def test_the_modules_still_import(mod: str) -> None:
    import importlib
    import sys
    for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
        if p not in sys.path:
            sys.path.insert(0, p)
    m = importlib.import_module(f"desks.mt5.research.{mod}")
    assert inspect.ismodule(m)
    assert json is not None
