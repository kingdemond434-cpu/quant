"""DP2: an organ with no clock, no reader and no artifact update in N days is filed as a PROPOSED
retirement with its evidence. Nothing is deleted, and a proposal is never read as a retirement.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import dormant_components as dc  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


@dataclass
class _Spec:
    scheduled: bool
    schedule: str = "hourly_cycle:x"


class _Reg:
    def __init__(self, clocked: set[str]) -> None:
        self.clocked = clocked

    def owners_of(self, path: str) -> list[_Spec]:
        return [_Spec(True)] if path in self.clocked else [_Spec(False)]


def _census() -> dict[str, Any]:
    organs = {
        "desks/mt5/research/dead.py": {"verdict": "UNREACHED", "artifacts": ["DEAD.json"]},
        "desks/mt5/research/fresh.py": {"verdict": "UNREACHED", "artifacts": ["FRESH.json"]},
        "desks/mt5/research/in_git.py": {"verdict": "UNREACHED", "artifacts": ["GIT.json"]},
        "desks/mt5/research/reg_clock.py": {"verdict": "UNREACHED", "artifacts": ["R.json"]},
        "desks/mt5/research/live.py": {"verdict": "LIVE", "artifacts": ["LIVE.json"]},
        "desks/mt5/research/_retired/old.py": {"verdict": "UNREACHED", "artifacts": ["O.json"]},
        "libs/pkg/__init__.py": {"verdict": "UNREACHED", "artifacts": ["P.json"]},
    }
    return {"organs": organs, "unreached": [k for k, v in organs.items()
                                            if v["verdict"] == "UNREACHED"]}


def _run(tmp: Path, *, apply: bool, touched: set[str] | None = None) -> dict[str, Any]:
    return dc.run(apply=apply, now=NOW, root=tmp, retirements=tmp / "retirements.jsonl",
                  report=tmp / "DORMANT_COMPONENTS.json", census=_census(),
                  reg=_Reg({"desks/mt5/research/reg_clock.py"}),
                  mtimes={"FRESH.json": (NOW - timedelta(days=1)).timestamp(),
                          "DEAD.json": (NOW - timedelta(days=90)).timestamp()},
                  touched=touched if touched is not None else {"GIT.json"})


def test_only_an_organ_dead_on_all_three_facts_is_proposed(tmp_path):
    doc = _run(tmp_path, apply=False)
    assert [d["path"] for d in doc["dormant"]] == ["desks/mt5/research/dead.py"]
    assert doc["spared"]["registry_clock"] == 1
    assert doc["spared"]["artifact_recent_on_disk"] == 1
    assert doc["spared"]["artifact_recent_in_git"] == 1
    assert doc["spared"]["already_retired_dir"] == 1 and doc["spared"]["package_init"] == 1
    assert not list(tmp_path.iterdir())                  # measuring writes nothing


def test_apply_files_one_proposed_row_with_evidence_and_never_twice(tmp_path):
    first = _run(tmp_path, apply=True)
    rows = [json.loads(ln) for ln in
            (tmp_path / "retirements.jsonl").read_text("utf-8").splitlines()]
    assert first["n_newly_proposed"] == 1 and len(rows) == 1
    row = rows[0]
    assert row["status"] == dc.PROPOSED and row["path"] == "desks/mt5/research/dead.py"
    assert row["evidence"]["clock"] and row["evidence"]["reader"]
    assert row["evidence"]["artifact_last_update"].startswith("2026-07")
    second = _run(tmp_path, apply=True)
    assert second["n_newly_proposed"] == 0 and second["n_already_filed"] == 1
    assert len((tmp_path / "retirements.jsonl").read_text("utf-8").splitlines()) == 1
    assert (tmp_path / "DORMANT_COMPONENTS.json").exists()


def test_no_history_reading_means_no_proposal(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "git_touched", lambda root, days: (None, "git unreadable"))
    doc = dc.run(apply=False, now=NOW, root=tmp_path, retirements=tmp_path / "r.jsonl",
                 report=tmp_path / "d.json", census=_census(), reg=_Reg(set()), mtimes={})
    assert doc["n_dormant"] == 0 and doc["spared"]["history_unmeasured"] >= 1


def test_a_proposal_is_never_read_as_a_retirement(tmp_path):
    from libs.ops import producer_census as pc
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "retirements.jsonl").write_text(
        json.dumps({"path": "a.py", "status": "PROPOSED", "reason": "dormant"}) + "\n"
        + json.dumps({"path": "b.py", "reason": "gone", "replacement": "c.py"}) + "\n",
        "utf-8")
    got = pc.retirements(tmp_path)
    assert "b.py" in got and "a.py" not in got


def test_the_organ_is_on_the_daily_frontier_audit_lane():
    lane = (ROOT / "ops" / "run_frontier_audit.cmd").read_text("utf-8")
    assert "dormant_components.py\" --apply" in lane
