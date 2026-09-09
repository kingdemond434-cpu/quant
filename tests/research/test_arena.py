"""Arms are judged against the leader and the verdict is written down; nothing is retired."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import arena  # noqa: E402

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def _arm(born, certified, group="exploit"):
    return {"born": born, "certified": certified, "alpha": certified + 1.0,
            "beta": born - certified + 1.0, "group": group, "cost_basis": "measured"}


def test_p_worse_is_symmetric_and_ordered() -> None:
    strong, weak = (21.0, 81.0), (2.0, 99.0)
    assert arena.p_worse(*weak, *strong) > 0.95
    assert arena.p_worse(*strong, *weak) < 0.05
    assert abs(arena.p_worse(*strong, *strong) - 0.5) < 1e-9


def test_the_leader_leads_a_clear_laggard_trails_and_a_thin_arm_is_unmeasured() -> None:
    v = arena.judge({"good": _arm(100, 20), "bad": _arm(100, 1), "thin": _arm(3, 3),
                     "mid": _arm(100, 15)})
    assert v["leader"] == "good"
    assert v["arms"]["good"]["verdict"] == arena.LEADS
    assert v["arms"]["bad"]["verdict"] == arena.TRAILS and v["trails"] == ["bad"]
    assert v["arms"]["mid"]["verdict"] in (arena.KEEP, arena.UNDECIDED)
    assert v["arms"]["thin"]["verdict"] == arena.UNMEASURED
    assert v["arms"]["thin"]["p_worse_than_leader"] is None
    assert v["recorded"] == 3, "AP5's own measure: arms carrying a verdict"


def test_no_arm_above_the_floor_means_no_leader_and_nothing_recorded() -> None:
    v = arena.judge({"a": _arm(3, 1), "b": _arm(5, 2)})
    assert v["leader"] is None and v["recorded"] == 0
    assert all(r["verdict"] == arena.UNMEASURED for r in v["arms"].values())


def test_the_controller_ab_needs_two_variants_with_entries() -> None:
    assert arena.variants([])["status"] == "UNMEASURED"
    one = [{"controller_variant": "A", "born": 50, "certified": 5}]
    assert arena.variants(one)["status"] == "ONE_ARM"
    two = [*one, {"controller_variant": "B", "born": 40, "certified": 1}]
    doc = arena.variants(two)
    assert doc["status"] == "MEASURED"
    assert doc["variants"]["A"]["rate"] > doc["variants"]["B"]["rate"]


def test_build_and_main_record_history_without_retiring_anything(tmp_path: Path,
                                                                 monkeypatch) -> None:
    bandit = {"controller_variant": "A", "arms": {"good": _arm(100, 20), "bad": _arm(100, 1)},
              "shares": {"good": 0.5, "bad": 0.5}}
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    b = tmp_path / "reports" / "RESEARCH_BANDIT.json"
    b.write_text(json.dumps(bandit), "utf-8")
    monkeypatch.setattr(arena, "BANDIT", b)
    monkeypatch.setattr(arena, "OUT", tmp_path / "reports" / "ARM_VERDICTS.json")
    monkeypatch.setattr(arena, "HISTORY", tmp_path / "data" / "arm_verdicts.jsonl")
    assert arena.main([]) == 0
    doc = json.loads((tmp_path / "reports" / "ARM_VERDICTS.json").read_text("utf-8"))
    assert doc["status"] == "MEASURED" and doc["recorded"] == 2 and doc["trails"] == ["bad"]
    hist = (tmp_path / "data" / "arm_verdicts.jsonl").read_text("utf-8").splitlines()
    assert len(hist) == 2 and json.loads(hist[0])["controller_variant"] == "A"
    assert json.loads(b.read_text("utf-8")) == bandit, "the bandit's own budget is untouched"
    arena.main([])
    assert len((tmp_path / "data" / "arm_verdicts.jsonl").read_text("utf-8").splitlines()) == 4


def test_an_absent_bandit_report_is_unmeasured() -> None:
    doc = arena.build({}, [], NOW)
    assert doc["status"] == "UNMEASURED" and doc["n_arms"] == 0 and doc["leader"] is None
