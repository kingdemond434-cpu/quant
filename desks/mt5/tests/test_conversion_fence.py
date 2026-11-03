"""ROW 78: THE CONVERSION FENCE IS RED WHEN A STAGE CONVERTS NOTHING WHILE ITS INPUTS FLOW.

conversion_funnel measured every stage and judged none of them, conversion_ledger.json sat at
2026-09-05 with three organs reading it, and CONVERSION_FUNNEL.json never crossed the wire. These
pin the per-stage fence, its carried stall counter, the ledger refresh, and the publication.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

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


def _ledger(at: str, binding: str, rates: dict[str, float],
            tried: dict[tuple[str, str], int]) -> dict:
    return {"generated_utc": at, "binding_stage": binding, "binding_rate": min(rates.values()),
            "stages": [{"name": k, "rate": v} for k, v in rates.items()],
            "cell_type_yield": [{"family": f, "asset_class": c, "tried": n}
                                for (f, c), n in tried.items()]}


def test_a_refresh_records_what_it_moved() -> None:
    before = _ledger("2026-09-05T14:36:50+00:00", "verdict -> cert",
                     {"verdict -> cert": 0.001, "cert -> clock": 1.0},
                     {("discovered", "equity"): 75, ("srb", "fx"): 25})
    after = _ledger("2026-11-03T17:00:00+00:00", "card -> verdict",
                    {"verdict -> cert": 0.02, "cert -> clock": 1.0, "card -> verdict": 0.0001},
                    {("discovered", "equity"): 25, ("srb", "fx"): 75})
    d = cf.refresh_delta(before, after)
    assert d["status"] == "MEASURED" and d["binding_changed"] is True
    assert d["binding_before"] == "verdict -> cert" and d["binding_after"] == "card -> verdict"
    moves = {r["key"]: r for r in d["stage_rate_moves"]}
    assert moves["verdict -> cert"]["delta"] == pytest.approx(0.019)
    assert moves["card -> verdict"]["before"] is None
    assert "cert -> clock" not in moves
    shares = {r["key"]: r for r in d["trial_share_moves"]}
    assert shares["discovered x equity"]["delta"] == pytest.approx(-0.5)
    assert d["max_abs_trial_share_delta"] == pytest.approx(0.5)
    assert d["prior_age_h"] is not None and d["prior_age_h"] > 24


def test_a_first_refresh_says_there_was_no_prior() -> None:
    d = cf.refresh_delta(None, _ledger("2026-11-03T17:00:00+00:00", "a", {"a": 0.1}, {}))
    assert d["status"] == "NO_PRIOR" and d["after"]["binding_stage"] == "a"


def test_the_refresh_publishes_its_delta_and_one_event(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    old = _ledger("2026-09-05T14:36:50+00:00", "x", {"x": 0.001}, {("a", "b"): 1})
    (desk / "data" / "conversion_ledger.json").write_text(json.dumps(old), "utf-8")
    new = _ledger("2026-11-03T17:00:00+00:00", "y", {"x": 0.5, "y": 0.0001}, {("a", "b"): 1})

    import research.conversion_ledger as cl

    def fake_run(base: Path) -> dict:
        (base / "data" / "conversion_ledger.json").write_text(json.dumps(new), "utf-8")
        return dict(new)

    monkeypatch.setattr(cl, "run", fake_run)
    events_path = tmp_path / "events.jsonl"
    out = cf.refresh_conversion_ledger(desk, deadline=time.monotonic() + 60,
                                       events_path=events_path)
    assert out["status"] == "WRITTEN"
    assert out["refresh_delta"]["binding_changed"] is True
    rows = [json.loads(x) for x in events_path.read_text("utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "DATA_UPDATED" and rows[0]["topic"] == "conversion_ledger_refresh"
    assert rows[0]["binding_after"] == "y" and not rows[0].get("unknown_kind")
