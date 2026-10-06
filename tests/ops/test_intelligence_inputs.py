"""The three intelligence-cycle inputs are DERIVED, and an underivable field stays UNMEASURED."""
from __future__ import annotations

import json
from pathlib import Path

from libs.ops import intelligence_inputs as ii


def _row(run: str, at: str, *, outcome: str = "ok", sha: str = "a" * 40,
         out: str | None = "h1", cpu: float = 1.0, wall: float = 2.0) -> dict:
    return {"at": at, "started_at": at, "run": run, "outcome": outcome, "cpu_s": cpu,
            "wall_s": wall, "commit_sha": sha, "output_hash": out}


def test_cadence_counts_productive_fires_by_changed_output_and_measures_the_interval() -> None:
    rows = [_row("leg", f"2026-09-29T{h:02d}:00:00+00:00", out=o)
            for h, o in ((1, "h1"), (2, "h1"), (3, "h2"), (4, "h3"))]
    rows.append(_row("leg", "2026-09-29T05:00:00+00:00", out="h4", outcome="TIMEOUT"))
    (job,) = ii.cadence_production(rows)["jobs"]
    assert job["fires"] == 5 and job["interval_minutes"] == 60.0
    assert job["productive_fires"] == 3 and job["findings"] == 3      # h1, h2, h3; not the timeout
    assert job["cost_per_fire"] == 1.0


def test_a_job_without_output_hashes_is_unmeasured_not_barren() -> None:
    rows = [_row("dark", f"2026-09-29T{h:02d}:00:00+00:00", out=None) for h in range(1, 5)]
    doc = ii.cadence_production(rows)
    assert doc["jobs"] == [] and doc["unmeasured"][0]["job"] == "dark"
    assert "UNMEASURED" in doc["unmeasured"][0]["why"]


def test_snapshots_compare_the_two_latest_code_versions() -> None:
    rows = [_row("leg", f"2026-09-28T{h:02d}:00:00+00:00", sha="a" * 40) for h in range(1, 4)]
    rows += [_row("leg", f"2026-09-29T{h:02d}:00:00+00:00", sha="b" * 40,
                  outcome="ok" if h > 1 else "TIMEOUT") for h in range(1, 4)]
    doc = ii.capability_snapshots(rows)
    (cmp,) = doc["comparisons"]
    assert cmp["before"]["metrics"]["reliability"] == 1.0
    assert round(cmp["after"]["metrics"]["reliability"], 4) == round(2 / 3, 4)
    from libs.self_improvement.capability_regression import CapabilitySnapshot, verdict
    b = CapabilitySnapshot(subsystem="leg", metrics=cmp["before"]["metrics"])
    a = CapabilitySnapshot(subsystem="leg", metrics=cmp["after"]["metrics"])
    assert verdict(b, a)[0] == "REGRESSION"                         # the reader sees the loss
    one = ii.capability_snapshots(rows[:3])
    assert one["comparisons"] == [] and one["unmeasured"]


def test_horizons_come_from_the_fitted_half_life_and_the_chart() -> None:
    decay = {"decay_model": {"s1": {"half_life_days": 2.0, "basis": "forward"},
                             "s2": {"half_life_days": None}, "s3": {"half_life_days": 1.0}}}
    sleeves = {"sleeves": [{"name": "s1", "timeframe": "M15"}, {"name": "s2", "timeframe": "H1"},
                           {"name": "s3"}]}
    doc = ii.strategy_horizons(decay, sleeves)
    assert doc["strategies"] == [{"strategy": "s1", "half_life_minutes": 2880.0,
                                  "interval_minutes": 15.0, "edge_bps": 0.0,
                                  "opportunities_per_day": 0.0, "hard_floor_reason": "",
                                  "basis": "forward"}]
    assert {u["strategy"] for u in doc["unmeasured"]} == {"s2", "s3"}
    assert ii.strategy_horizons(None, None)["status"].startswith("UNMEASURED")


def test_write_all_writes_the_three_paths_the_cycle_reads(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("", "utf-8")
    counts = ii.write_all(ledger=ledger, root=tmp_path, decay=tmp_path / "none.json",
                          sleeves=tmp_path / "none.json")
    for name in ("cadence_production.json", "capability_snapshots.json",
                 "strategy_horizons.json"):
        assert isinstance(json.loads((tmp_path / "data" / name).read_text("utf-8")), dict)
    assert counts["cadence_jobs"] == 0 and counts["horizon_strategies"] == 0
