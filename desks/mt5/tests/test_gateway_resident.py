"""The resident gateway loop's three measured defects of 2026-09-16.

1. `import run_gateway_loop` resolved to the LEGACY desk-root wrapper (pid-less "locked" lock,
   stolen after five minutes) because the script's own directory was already on sys.path and the
   guard skipped it; the per-minute task ran the modern wrapper, and the two ran passes
   concurrently whenever a pass took longer than five minutes -- the same signal bar sent twice.
2. Passes were spaced from each other, not from the clock, so the pass after a bar close could
   begin anywhere in the following minute.
3. The recycle ceiling was a flat 900 MB sized for the 8 GB box; on 98 GB it recycled every 2-4
   passes and each recycle waited up to ten minutes for the keep-alive trigger.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import gateway_resident as gr  # noqa: E402


def test_the_loop_wrapper_is_the_research_one_never_the_desk_root_copy() -> None:
    path = gr.loop_module_path().replace("\\", "/")
    assert path.endswith("desks/mt5/research/run_gateway_loop.py"), path
    # And the legacy copy at the desk root delegates rather than carrying its own lock rule.
    legacy = (_DESK / "run_gateway_loop.py").read_text("utf-8")
    assert "research" in legacy and 'LOCK.write_text("locked"' not in legacy
    assert "_mod.main" in legacy


def test_passes_align_to_the_minute_boundary_plus_slack() -> None:
    base = 1_000_020.0                                   # a minute boundary (divisible by 60)
    # 20 s into the minute, a 12 s pass: sleep to the next boundary and three seconds past it.
    assert gr.next_boundary_wait(base + 20.0, 12.0, slack_s=3.0) == pytest.approx(43.0)
    # One second into the minute (inside the slack): wait only the remaining slack.
    assert gr.next_boundary_wait(base + 1.0, 0.5, slack_s=3.0) == pytest.approx(2.0)
    # A pass that overran the interval starts again after one second.
    assert gr.next_boundary_wait(base + 20.0, 75.0, slack_s=3.0) == 1.0
    # Never below one second.
    assert gr.next_boundary_wait(base + 59.9, 0.1, slack_s=0.0) >= 1.0


def test_the_recycle_ceiling_is_a_tenth_of_measured_memory_floored_at_the_8gb_tuning() -> None:
    assert gr.default_recycle_mb(98_297.6) == 9830.0
    assert gr.default_recycle_mb(8_186.0) == 900.0
    assert gr.default_recycle_mb(None) == 900.0
    assert gr.default_recycle_mb(0.0) == 900.0
