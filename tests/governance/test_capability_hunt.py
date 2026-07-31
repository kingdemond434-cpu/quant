"""L1.30 replacement rate + L1.31 daily two-family capability hunt."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.check_replacement_rate import build_report


def _seed(root: Path, *, deaths: int = 0, births=None, occupied: int = 2) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    lines = [f"### edge_{i} -- KILLED {today}" for i in range(deaths)]
    (root / "docs/graveyard.md").write_text("\n".join(lines) or "# empty", "utf-8")
    q = {"slots": {"occupied": occupied, "cap": 12}}
    if births is not None:
        q["promotion_history"] = [{"promoted_at": today} for _ in range(births)]
    (root / "data/promotion_queue.json").write_text(json.dumps(q), "utf-8")


def test_uncountable_births_never_prints_dying(tmp_path):
    _seed(tmp_path, deaths=3, births=None)
    rep = build_report(tmp_path)
    assert rep["status"] == "UNMEASURED-BIRTHS"       # NOT "DYING" -- absence of count != zero
    assert rep["births_measured"] is False
    assert rep["live_forward_clocks"] == 2            # real slot occupancy, not a phantom key


def test_dying_when_deaths_outpace_measured_births(tmp_path):
    _seed(tmp_path, deaths=4, births=1)
    rep = build_report(tmp_path)
    assert rep["status"] == "DYING"
    assert rep["replacement_rate"] == 0.25


def test_ok_when_births_keep_pace(tmp_path):
    _seed(tmp_path, deaths=2, births=3)
    assert build_report(tmp_path)["status"] == "OK"


def test_old_deaths_fall_out_of_window(tmp_path):
    _seed(tmp_path, deaths=0, births=0)
    old = (datetime.now(tz=UTC) - timedelta(days=200)).strftime("%Y-%m-%d")
    (tmp_path / "docs/graveyard.md").write_text(f"### ancient -- KILLED {old}", "utf-8")
    rep = build_report(tmp_path, window_days=90)
    assert rep["deaths"] == 0 and rep["graveyard_entries_total"] == 1


def test_laws_and_wiring_present():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.30 REPLACEMENT RATE" in const
    assert "L1.31 THE DESK HUNTS ITS OWN MISSING CAPABILITIES" in const
    doc = Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert "L1.30" in doc and "L1.31" in doc
    mx = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.30"' in mx and '"L1.31"' in mx
    man = Path("ops/crontab.manifest").read_text("utf-8")
    assert "check_replacement_rate.py" in man and "run_capability_hunt.sh" in man
    # the twin hunts too
    assert "run_capability_hunt.sh" in Path("ops/crontab.research.manifest").read_text("utf-8")


def test_hunt_keeps_families_independent_and_flags_degradation():
    src = Path("scripts/run_capability_hunt.py").read_text("utf-8")
    # Neither proposal prompt may contain the other's output: both are built from _HUNT_BRIEF
    # alone, and only the BUILD stage sees both.
    assert "_HUNT_BRIEF.format(context=_CONTEXT)" in src
    assert "SINGLE-FAMILY" in src                     # honest degradation when GPT seat is dead
    assert "_BUILD_BRIEF.format(a=a, b=b" in src
