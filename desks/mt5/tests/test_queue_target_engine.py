"""Every queued research task names the engine that could answer it (Tier-1 audit G21).

MEASURED on data/research_queue.jsonl: 47,150 rows, every one with `kind: None` and no
producer field. A row saying "nothing pays in Asia + low vol" was addressed to a general
audience, so the unused-heat loop was wired at both ends and routed nowhere in the middle. What
is pinned: the arm comes from the desk's own bandit map (imported read-only), the engines that
serve that arm travel with the task, an engine is never told to answer its own question, an arm
no other engine serves is UNROUTED rather than sent somewhere arbitrary, and a bandit outage
loses no task.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import bandit  # noqa: E402
from research import regime_coverage as rc  # noqa: E402


def _task(**kw) -> dict:
    base = {"source": "regime_coverage", "kind": "coverage_gap", "title": "t", "status": None}
    base.update(kw)
    return base


def test_the_arm_is_the_bandits_own_answer() -> None:
    tasks = [_task(), _task(kind="exit_hypothesis"), _task(kind="anomaly")]
    rc.stamp_target_engine(tasks)
    assert [t["target_arm"] for t in tasks] == [
        bandit.arm_of("regime_coverage", "coverage_gap"),
        bandit.arm_of("regime_coverage", "exit_hypothesis"),
        bandit.arm_of("regime_coverage", "anomaly"),
    ]
    assert tasks[0]["target_arm"] == "conditional_state_edge"
    assert tasks[1]["target_arm"] == "exit_improvement"


def test_the_engines_that_serve_the_arm_travel_with_the_task() -> None:
    (t,) = rc.stamp_target_engine([_task()])
    arm = t["target_arm"]
    expect = [n for n, a in bandit.SOURCE_ARM.items()
              if a == arm and n != "regime_coverage"]
    assert t["target_engines"] == expect and expect, arm
    assert t["target_engine"] == expect[0]
    # The audit's own worked example: an uncovered state routes to a conditional-state engine.
    assert "transition_alpha" in t["target_engines"]
    assert "engine(s) serve it" in t["target_engine_why"]


def test_an_engine_is_never_told_to_answer_its_own_question() -> None:
    (t,) = rc.stamp_target_engine([_task(source="transition_alpha", kind=None)])
    assert t["target_arm"] == bandit.arm_of("transition_alpha", None)
    assert "transition_alpha" not in t["target_engines"]
    assert t["target_engine"] != "transition_alpha"


def test_an_arm_no_other_engine_serves_is_unrouted_and_says_so(monkeypatch) -> None:
    monkeypatch.setattr(bandit, "SOURCE_ARM", {"regime_coverage": "conditional_state_edge"})
    (t,) = rc.stamp_target_engine([_task()])
    assert t["target_engines"] == [] and t["target_engine"] is None
    assert "unrouted rather than sent somewhere arbitrary" in t["target_engine_why"]


def test_a_bandit_outage_loses_no_task(monkeypatch) -> None:
    import builtins
    real = builtins.__import__

    def _blocked(name, *a, **kw):
        if name.startswith("libs.research.bandit"):
            raise ImportError("blocked for the test")
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    tasks = rc.stamp_target_engine([_task(), _task(kind="anomaly")])
    assert len(tasks) == 2
    assert all(t["target_engine"] is None and "bandit unavailable" in t["target_engine_why"]
               for t in tasks)


def test_the_queue_writer_stamps_before_it_writes(tmp_path, monkeypatch) -> None:
    """The rows the deepening worker reads must already carry their addressee."""
    q = tmp_path / "miner_deepening_queue.json"
    monkeypatch.setattr(rc, "QUEUE", q)
    rc._merge_into_queue([_task(title="a"), _task(title="b")])
    doc = json.loads(q.read_text("utf-8"))
    assert len(doc["tasks"]) == 2
    for row in doc["tasks"]:
        assert row["target_arm"] == "conditional_state_edge"
        assert row["target_engine"] in row["target_engines"]

    # A rerun replaces this source's rows and the replacements are stamped too -- the ownership
    # rule the function already had is untouched.
    rc._merge_into_queue([_task(title="c")])
    doc = json.loads(q.read_text("utf-8"))
    assert [r["title"] for r in doc["tasks"]] == ["c"]
    assert doc["tasks"][0]["target_engine"]

    # Another source's rows are neither deleted nor re-stamped by this source's pass.
    rc._merge_into_queue([_task(source="missed_growth", kind="rail_review", title="m")],
                         source="missed_growth")
    doc = json.loads(q.read_text("utf-8"))
    titles = {r["title"] for r in doc["tasks"]}
    assert titles == {"c", "m"}
    m = next(r for r in doc["tasks"] if r["title"] == "m")
    assert m["target_arm"] == bandit.arm_of("missed_growth", "rail_review")


def test_the_stamp_adds_routing_and_changes_nothing_else() -> None:
    """It names an addressee. Anything else it touched would be this component deciding
    something -- the bandit still sets the budget and the worker still decides what it can
    act on."""
    before = _task(state="global=bull|session=ASIA", families_tried=["carry"], status=None)
    original = dict(before)
    (after,) = rc.stamp_target_engine([before])
    assert after is before, "the tasks are stamped in place, not replaced"
    added = set(after) - set(original)
    assert added == {"target_arm", "target_engine", "target_engines", "target_engine_why"}
    for k, v in original.items():
        assert after[k] == v, f"the stamp rewrote {k}"
