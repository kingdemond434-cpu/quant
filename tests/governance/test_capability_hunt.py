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
    assert "_HUNT_BRIEF.format(context=_CONTEXT, lens=lens)" in src
    assert "SINGLE-FAMILY" in src                     # honest degradation when GPT seat is dead
    assert "_BUILD_BRIEF.format(a=a, b=b" in src


def test_lens_rotation_gives_independent_draws():
    from scripts.run_capability_hunt import _ALPHA_LENSES, _DEFENSIVE_LENSES, _lens_for
    # same slot draws a different lens day to day -- consecutive draws are independent
    assert _lens_for("20260731", 0) != _lens_for("20260801", 0)
    # every lens of BOTH kinds is reachable over a month -- no favourite subset, yield stays
    # measurable per lens
    seen = {_lens_for(f"2026{m:02d}{d:02d}", s)
            for m in (7, 8) for d in range(1, 29) for s in range(6)}
    assert all(x in seen for x in _ALPHA_LENSES)
    assert all(x in seen for x in _DEFENSIVE_LENSES)


def test_majority_of_daily_draws_hunt_new_alpha():
    # Principal: exploration anchored to the growth/alpha goal -> most daily draws are offensive.
    from scripts.run_capability_hunt import _ALPHA_LENSES, _lens_for
    for day in ("20260731", "20260801", "20260815", "20260901"):
        alpha = sum(1 for s in range(6) if _lens_for(day, s) in _ALPHA_LENSES)
        assert alpha >= 4, f"{day}: only {alpha}/6 offensive"


def test_brief_is_anchored_to_the_growth_objective_and_brainstorms():
    from scripts.run_capability_hunt import _HUNT_BRIEF
    b = _HUNT_BRIEF.lower()
    assert "geometric growth" in b and "validated alpha" in b     # the supreme objective, up top
    assert "brainstorm" in b                                       # breadth on every run
    assert "forced participant" in " ".join(
        __import__("scripts.run_capability_hunt", fromlist=["_ALPHA_LENSES"])._ALPHA_LENSES).lower()


def test_hunt_history_is_append_only_and_lens_attributed(tmp_path):
    from scripts.run_capability_hunt import _record_yield
    (tmp_path / "data").mkdir()
    _record_yield(tmp_path, {"stamp": "20260731", "slot": 0, "lens": "L1", "built": True})
    _record_yield(tmp_path, {"stamp": "20260731", "slot": 1, "lens": "L2", "built": False})
    import json
    runs = json.loads((tmp_path / "data/capability_hunt_history.json").read_text())["runs"]
    assert [r["lens"] for r in runs] == ["L1", "L2"]   # attributable -> lens yield measurable
