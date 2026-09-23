"""The search has to be aimed by the coverage measurement, or the measurement changes nothing.

WHAT THIS GUARDS. `alpha_breadth` published, on its first ever run, that 32 sleeves behave like
1.513 independent bets and that 11 of 15 declared mechanism clusters are empty in both the traded
and the certified book. It also published, for each of those 11, a `payer` and a `hunt` -- a
research brief per dark axis. Nothing read them. This module turns them into owned queue tasks,
and these tests pin the three properties that decide whether that aiming is real:

    IT RANKS BY EMPTINESS, NOT BY RESULTS. A dark axis has no backtest by construction, so any
    ranking that consults one is really ranking its NEIGHBOURS -- which is how a search convinces
    itself that the region it already mined is the promising one. `test_ranking_ignores_results`
    feeds a payload with performance-shaped keys and pins that they move nothing.

    IT REFUSES TO QUEUE AN AXIS WITH NO BRIEF, and says so. Queueing a bare cluster name sends a
    worker to invent the mechanism it was supposed to look for, and a hunt that invents its own
    target returns whatever the worker already believed.

    IT IS IDEMPOTENT PER CLUSTER. The governor runs hourly; without a per-cluster dedupe key the
    same eleven briefs are queued every hour and the queue census reads as work in flight.

AND ONE PROPERTY THAT IS NOT ABOUT RANKING AT ALL: the tasks must be OWNED. `generate` belongs to
the research role in `DESK_ROLES`, so a queued hunt has a claimant and a supervisor above it. An
unowned kind is refused by `Org.delegate` and would sit READY forever while reading as a busy
queue -- the exact failure mode the wiring campaign exists to stop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.org import FROM_KEY, desk_org  # noqa: E402
from libs.ops.task_queue import TaskQueue  # noqa: E402
from libs.research.coverage_governor import (  # noqa: E402
    BREADTH_REL,
    HUNT_KIND,
    REGIME_REL,
    census,
    dark_axes,
    enqueue,
)


def _write(root: Path, *, empty_detail, empty_in_both, share=0.52, occupied=("session_liquidity",),
           regime=None) -> None:
    doc = {
        "effective": {"effective_breadth": 1.513, "n_nominal": 32},
        "clusters": {
            "declared": 15,
            "occupied_either": list(occupied),
            "empty_in_both": list(empty_in_both),
            "counts_traded": {"session_liquidity": 26, "mean_reversion": 19},
            "largest_cluster_share_traded": share,
            "target_band": [8, 15],
            "meets_target": False,
            "empty_detail": list(empty_detail),
        },
    }
    p = root / Path(*BREADTH_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")
    if regime is not None:
        r = root / Path(*REGIME_REL.split("/"))
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text(json.dumps(regime), encoding="utf-8")


def _row(cluster: str, *, hunt: str = "look for it", payer: str = "someone who must act", **extra):
    return {"cluster": cluster, "title": cluster.replace("_", " "), "payer": payer,
            "hunt": hunt} | extra


@pytest.fixture
def q(tmp_path) -> TaskQueue:
    return TaskQueue(tmp_path / "q.jsonl")


def test_absent_artifact_yields_no_axes_rather_than_a_guessed_map(tmp_path):
    """A governor that invents its coverage picture aims the search wherever its default points."""
    assert dark_axes(tmp_path) == []
    assert census(tmp_path)["dark"] == []


def test_unreadable_artifact_is_the_same_as_absent(tmp_path):
    p = tmp_path / Path(*BREADTH_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    assert dark_axes(tmp_path) == []


def test_empty_in_both_outranks_empty_in_one(tmp_path):
    """Nothing is there to correlate with, which is the strongest orthogonality available."""
    _write(tmp_path,
           empty_detail=[_row("only_traded"), _row("both")],
           empty_in_both=["both"])
    axes = dark_axes(tmp_path)
    assert [a.cluster for a in axes] == ["both", "only_traded"]
    assert axes[0].empty_in_both is True and axes[1].empty_in_both is False
    assert axes[0].components["emptiness"] > axes[1].components["emptiness"]


def test_concentration_raises_the_value_of_every_dark_axis(tmp_path):
    """One cluster at 52% is fragile in a way a balanced book is not, so relief is worth more."""
    _write(tmp_path, empty_detail=[_row("x")], empty_in_both=["x"], share=0.52)
    hot = dark_axes(tmp_path)[0]
    _write(tmp_path, empty_detail=[_row("x")], empty_in_both=["x"], share=0.10)
    cool = dark_axes(tmp_path)[0]
    assert hot.priority > cool.priority
    assert hot.components["relief"] == pytest.approx(0.52)


def test_ranking_ignores_results(tmp_path):
    """A dark axis has no backtest; ranking one by a neighbour's is how a search fools itself."""
    _write(tmp_path,
           empty_detail=[_row("a", sharpe=9.9, expected_return=1.0, pnl=1e6),
                         _row("b", sharpe=-9.9, expected_return=-1.0, pnl=-1e6)],
           empty_in_both=["a", "b"])
    axes = dark_axes(tmp_path)
    assert {a.cluster for a in axes} == {"a", "b"}
    assert axes[0].priority == axes[1].priority, "a performance key changed the ranking"
    assert [a.cluster for a in axes] == ["a", "b"], "ties must break by name, reproducibly"
    assert set(axes[0].components) == {"emptiness", "relief", "actionable"}


def test_axis_without_a_written_brief_is_not_queued_and_is_said(tmp_path, q):
    """Queueing a bare name sends a worker to invent the mechanism it was meant to search for."""
    _write(tmp_path,
           empty_detail=[_row("briefed"), _row("bare", hunt="   ")],
           empty_in_both=["briefed", "bare"])
    out = enqueue(q, tmp_path)
    assert out["queued"] == ["briefed"]
    assert any("bare" in s and "no written hunt brief" in s for s in out["skipped"])
    assert [t.kind for t in q.tasks().values()] == [HUNT_KIND]


def test_queued_task_is_owned_and_carries_the_brief(tmp_path, q):
    _write(tmp_path, empty_detail=[_row("relative_value", hunt="rank the basis")],
           empty_in_both=["relative_value"])
    enqueue(q, tmp_path)
    task = next(iter(q.tasks().values()))
    assert desk_org().owner_of(task.kind).name == "research"
    assert task.payload["cluster"] == "relative_value"
    assert task.payload["hunt"] == "rank the basis"
    assert task.payload["payer"]
    assert task.payload[FROM_KEY] == "ops"
    assert task.priority > 0.0


def test_second_pass_queues_nothing_new(tmp_path, q):
    """The governor runs hourly; without a per-cluster key the queue reads as work in flight."""
    _write(tmp_path, empty_detail=[_row("a"), _row("b")], empty_in_both=["a", "b"])
    first = enqueue(q, tmp_path)
    second = enqueue(q, tmp_path)
    assert sorted(first["queued"]) == ["a", "b"]
    assert second["queued"] == []
    assert all("already being searched" in s for s in second["skipped"])
    assert len(q.tasks()) == 2


def test_batch_bounds_the_queue(tmp_path, q):
    """A short queue whose head answers 'what is being searched' beats a backlog of eleven."""
    rows = [_row(f"c{i}") for i in range(9)]
    _write(tmp_path, empty_detail=rows, empty_in_both=[r["cluster"] for r in rows])
    out = enqueue(q, tmp_path, batch=3)
    assert len(out["queued"]) == 3
    assert len(q.tasks()) == 3


def test_census_reports_the_number_that_decides_breadth(tmp_path):
    _write(tmp_path, empty_detail=[_row("a")], empty_in_both=["a"],
           regime={"n_uncovered": 7, "n_buckets": 24})
    c = census(tmp_path)
    assert c["effective_breadth"] == 1.513 and c["nominal_sleeves"] == 32
    assert c["declared_clusters"] == 15 and c["occupied"] == ["session_liquidity"]
    assert c["dark"] == ["a"] and c["meets_target"] is False
    assert c["regime_uncovered"] == 7 and c["regime_buckets"] == 24
    assert "sqrt" in c["why"]


def test_governor_writes_no_code_and_runs_no_process():
    """It aims search. Anything that edits or spawns belongs to a worker with a supervisor."""
    src = (_ROOT / "libs" / "research" / "coverage_governor.py").read_text(encoding="utf-8")
    for forbidden in ("write_text(", "subprocess", "unlink(", "os.system", "importlib"):
        assert forbidden not in src, f"the governor reached for {forbidden}"
