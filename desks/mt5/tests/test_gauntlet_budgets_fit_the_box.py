"""The gauntlet's budgets are sized from what the box MEASURES, and they cannot silently shrink.

MEASURED 2026-09-08: docket 23,465, reached a backtest 147, judged last pass 42. At 42 cells an
hour the docket needed 558 passes -- 23 days -- to judge work the miners had already delivered.

THE MORNING'S FIX WAS WRONG BY ONE ORDER OF MAGNITUDE. The memory floor went 1200 -> 8192 on the
principal's report of an 80GB box. Every counter the box has ever published says 8GB (free RAM
cycling 3329 -> 448MB around a 3.7GB searcher; "phys 142MB free / virt 11719MB"; a page file
"full at 12,756MB"; one 4882MB process "leaving 280MB free"), and `exclusive_job` fails CLOSED on
the declared figure -- so 8192 would have stood the sweep down at the door every hour: rc=75, no
backtests, no certificates, the exact regression the raise was meant to end. 80GB is the disk.

The floor is back to the measured 1200 and the throughput problem is solved where it lives: the
BUDGET is no longer pinned to the floor but takes the room the box actually has at start, so a
big box is used and a small one is not overdrawn -- and the number the sweep is admitted on is
that same budget. These tests pin the measured floor, the headroom rule, and the one-number
property that keeps ask and throttle from disagreeing again.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
SRC = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")


def _const(name: str) -> str:
    m = re.search(rf"^{name}\s*=\s*(.+)$", SRC, re.M)
    assert m, name
    return m.group(1).strip()


def _budget_with(need: float, free: float | None, share: float = 0.5, cap: float = 8192.0,
                 env: dict | None = None) -> float:
    """Run the real `_measured_budget_mb` against a stubbed box."""
    m = re.search(r"^def _measured_budget_mb\(\) -> float:\n(?:[ \t].*\n|\n)+", SRC, re.M)
    assert m
    src = m.group(0)
    # The function imports from `research.job_lock`; feed it a stub module instead.
    import sys
    import types
    stub = types.ModuleType("research.job_lock")
    stub.measured_need_mb = lambda name, declared: (max(int(declared), int(need)), "stub")
    stub.free_mb = lambda: free
    pkg = types.ModuleType("research")
    pkg.job_lock = stub
    saved = {k: sys.modules.get(k) for k in ("research", "research.job_lock")}
    sys.modules["research"] = pkg
    sys.modules["research.job_lock"] = stub

    class _OS:
        environ = env or {}

    ns: dict = {"os": _OS, "DECLARED_NEED_MB": 1200, "HEADROOM_SHARE": share,
                "HEADROOM_CAP_MB": cap}
    try:
        exec(textwrap.dedent(src), ns)
        return ns["_measured_budget_mb"]()
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


# --------------------------------------------------------------------------- the measured floor
def test_the_declared_memory_floor_is_the_measured_one_not_the_claimed_one() -> None:
    assert _const("DECLARED_NEED_MB") == "1200"


def test_the_reason_the_8192_came_and_went_is_recorded_beside_the_number() -> None:
    """The next person handed a hardware figure must find the counters that contradicted the
    last one, in the file where the mistake was made."""
    assert "1200 IS THE MEASURED FLOOR, AND IT IS BACK" in SRC
    assert "phys 142MB free / virt 11719MB" in SRC
    assert "80GB is the size of\n#: its DISK" in SRC or "80GB is the size of its DISK" in SRC
    assert "rc=75" in SRC


def test_the_build_budget_is_forty_five_minutes() -> None:
    assert _const("FRESH_BUILD_BUDGET_SEC") == \
        'float(os.environ.get("GAUNTLET_FRESH_BUDGET_SEC", "2700"))'


def test_the_build_budget_still_fits_the_hourly_cadence_with_room_for_the_gates() -> None:
    """The gates measured twelve minutes in the pure-cache regime. 45 + 12 < 60."""
    assert 2700 + 12 * 60 < 3600


# ------------------------------------------------------------------------ the headroom budget
def test_on_the_8gb_box_the_budget_is_the_measured_need_and_nothing_more() -> None:
    """2,500MB free, p75 peak 1,619MB: half the room is 1,250, below the need, so the need
    stands. The sweep behaves exactly as it was measured to."""
    assert _budget_with(need=1619, free=2500) == 1619


def test_on_a_box_with_room_the_budget_grows_into_it_up_to_the_cap() -> None:
    assert _budget_with(need=1619, free=12_000) == 6000          # half of what is free
    assert _budget_with(need=1619, free=60_000) == 8192          # the cap, not 30,000


def test_the_share_and_the_cap_are_measured_not_typed_and_stay_overridable() -> None:
    assert _const("HEADROOM_SHARE") == 'float(os.environ.get("GAUNTLET_HEADROOM_SHARE", "0.5"))'
    assert _const("HEADROOM_CAP_MB") == \
        'float(os.environ.get("GAUNTLET_HEADROOM_CAP_MB", "8192"))'
    assert 'os.environ.get("GAUNTLET_MEMORY_BUDGET_MB")' in SRC
    assert _budget_with(need=1619, free=60_000, env={"GAUNTLET_MEMORY_BUDGET_MB": "3000"}) == 3000


def test_an_unmeasurable_box_gets_the_measured_need_never_unlimited() -> None:
    assert _budget_with(need=1619, free=None) == 1619
    assert "an unmeasurable box must not have its throttle removed" in SRC


def test_the_budget_never_falls_below_the_declared_floor() -> None:
    """A box with almost nothing free still declares the floor: admission then refuses it
    honestly (rc=75) rather than the sweep running under-provisioned and thrashing."""
    assert _budget_with(need=1200, free=300) == 1200


# ---------------------------------------------------- ask and throttle remain ONE number
def test_the_admission_ask_is_the_budget_itself() -> None:
    """Raising the throttle without raising what `exclusive_job` is told would let the sweep in
    on a false statement; asking for more than the throttle refuses it for room it will not
    use. The ask must be MEMORY_BUDGET_MB, and the reproduction lane keeps its 300."""
    assert "_need = 300 if _REPRO is not None else int(MEMORY_BUDGET_MB)" in SRC
    assert 'measured_need_mb("external_gauntlet", DECLARED_NEED_MB)' in SRC
    assert "return float(DECLARED_NEED_MB)" in SRC     # the fallback when nothing can be measured


def test_the_budget_is_computed_after_its_inputs_exist() -> None:
    """`MEMORY_BUDGET_MB = _measured_budget_mb()` runs at import and reads HEADROOM_SHARE and
    HEADROOM_CAP_MB; defining either below it would be a NameError swallowed into the
    declaration fallback -- a silent throttle, the shape this file fences."""
    assert SRC.index("HEADROOM_SHARE = ") < SRC.index("MEMORY_BUDGET_MB = _measured_budget_mb()")
    assert SRC.index("HEADROOM_CAP_MB = ") < SRC.index("MEMORY_BUDGET_MB = _measured_budget_mb()")
    assert (SRC.index("DECLARED_NEED_MB = 1200")
            < SRC.index("MEMORY_BUDGET_MB = _measured_budget_mb()"))
