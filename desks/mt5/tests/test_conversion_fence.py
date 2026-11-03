"""ROW 78: THE CONVERSION FENCE IS RED WHEN A STAGE CONVERTS NOTHING WHILE ITS INPUTS FLOW.

conversion_funnel measured every stage and judged none of them, conversion_ledger.json sat at
2026-09-05 with three organs reading it, and CONVERSION_FUNNEL.json never crossed the wire. These
pin the per-stage fence, its carried stall counter, the ledger refresh, and the publication.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conversion_funnel as cf  # noqa: E402


def _funnel(mined: int, cells: int, judged: int, passed: int, certs: int,
            clocks: int) -> list[dict]:
    return [{"stage": "mined", "n": mined}, {"stage": "testable_cell", "n": cells},
            {"stage": "judged", "n": judged}, {"stage": "verdict", "by_class": {}},
            {"stage": "pass", "n": passed}, {"stage": "certificate", "n": certs},
            {"stage": "forward_clock", "n": clocks}]


def test_a_healthy_funnel_is_green() -> None:
    fence = cf.conversion_fence(_funnel(100, 80, 60, 5, 4, 4))
    assert fence["verdict"] == "GREEN" and fence["red"] == []
    assert {r["stage"] for r in fence["stages"]} == {f"{a}->{b}" for a, b in cf.FENCE_PAIRS}


def test_a_stage_that_converts_nothing_is_red() -> None:
    fence = cf.conversion_fence(_funnel(100, 80, 60, 5, 0, 0))
    assert fence["verdict"] == "RED" and "pass->certificate" in fence["red"]


def test_inputs_that_flow_into_a_stage_that_does_not_move_go_red_after_three_passes() -> None:
    prior = None
    for i in range(cf.STALL_PASSES + 1):
        fence = cf.conversion_fence(_funnel(100 + 10 * i, 80, 60, 5, 4, 4), prior)
        prior = fence
    assert fence["verdict"] == "RED" and "mined->testable_cell" in fence["red"]
    row = next(r for r in fence["stages"] if r["stage"] == "mined->testable_cell")
    assert row["state"] == "STALLED" and row["stalled_passes"] >= cf.STALL_PASSES


def test_output_that_moves_resets_the_stall() -> None:
    prior = cf.conversion_fence(_funnel(100, 80, 60, 5, 4, 4))
    prior = cf.conversion_fence(_funnel(110, 80, 60, 5, 4, 4), prior)
    fence = cf.conversion_fence(_funnel(120, 90, 60, 5, 4, 4), prior)
    row = next(r for r in fence["stages"] if r["stage"] == "mined->testable_cell")
    assert row["stalled_passes"] == 0 and row["state"] == "OK"


def test_an_unreadable_stage_is_unmeasured_never_green() -> None:
    funnel = _funnel(100, 80, 60, 5, 4, 4)
    funnel[5]["n"] = None
    fence = cf.conversion_fence(funnel)
    assert fence["verdict"] == "UNMEASURED"


def test_the_ledger_refresh_says_when_it_was_skipped(tmp_path: Path) -> None:
    out = cf.refresh_conversion_ledger(tmp_path, deadline=time.monotonic() - 1)
    assert out["status"] == "SKIPPED"


def test_the_funnel_and_the_ledger_are_published_from_the_box() -> None:
    sync = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text(encoding="utf-8")
    block = sync.split("$reportPaths = @(", 1)[1].split("\n)\n", 1)[0]
    for rel in ("desks/mt5/reports/CONVERSION_FUNNEL.json",
                "desks/mt5/data/conversion_ledger.json"):
        assert f'"{rel}"' in block, rel
