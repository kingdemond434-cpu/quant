"""scripts/arch_health.py: the architecture monitor reports, ranks and caps; it never gates.

Each test pins one failure that was live on 2026-11-13 so the check would have named it.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.arch_health as A

NOW = datetime(2026, 11, 13, 17, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def test_half_landed_names_a_workflow_step_whose_script_never_merged(tmp_path: Path) -> None:
    # paperclip-lab.yml merged (#594/#595); scripts/paperclip_lab_run.py (#593) never did
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "lab.yml").write_text(
        "jobs:\n  a:\n    steps:\n      - run: python scripts/gone.py --x\n"
        "      - run: python scripts/here.py\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "here.py").write_text("", encoding="utf-8")
    got = A.half_landed(tmp_path)
    assert got == [{"where": ".github/workflows/lab.yml:4", "missing": "scripts/gone.py"}]


def test_half_landed_follows_a_checkout_into_a_subfolder(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "g.yml").write_text(
        "      - uses: actions/checkout@v4\n        with:\n          path: harness\n"
        "      - run: python -I harness/ops/x.py\n",
        encoding="utf-8",
    )
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops" / "x.py").write_text("", encoding="utf-8")
    assert A.half_landed(tmp_path) == []


def test_half_landed_reads_every_path_a_box_task_runs(tmp_path: Path) -> None:
    man = tmp_path / "desks" / "mt5" / "ops"
    man.mkdir(parents=True)
    (man / "box_tasks.manifest").write_text(
        '# comment runs="nope.py"\nTASK name="T" runs="a.ps1" also_runs="b.py,c.py"\n',
        encoding="utf-8",
    )
    (tmp_path / "a.ps1").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    got = A.half_landed(tmp_path)
    assert [g["missing"] for g in got] == ["c.py"]


def test_cascade_is_counted_inside_a_thirty_minute_window() -> None:
    # 2026-11-13 16:2xZ: cancelling 505 PR runs fired 139 audit-gate workflow_run looks
    runs = [
        {
            "name": "audit-gate",
            "event": "workflow_run",
            "created_at": _iso(NOW - timedelta(minutes=40) + timedelta(seconds=10 * i)),
        }
        for i in range(139)
    ]
    runs += [{"name": "ci", "event": "pull_request", "created_at": _iso(NOW - timedelta(hours=5))}]
    q = A.queue(runs, NOW)
    assert q["workflow_run_burst_30m"] == 139
    assert q["oldest_h"] == 5.0
    assert q["by_workflow"]["audit-gate/workflow_run"] == 139


def test_deploy_lag_is_how_long_live_code_waited_for_the_box() -> None:
    d = A.deploy_lag(
        {"generated_utc": "2026-11-10T16:24:24+00:00", "code_sha": "bb527d650cfa"},
        "2026-11-13T14:09:48Z",
        NOW,
    )
    assert d["box_code_sha"] == "bb527d650"
    assert 69.7 < d["lag_h"] < 69.8
    assert (
        A.deploy_lag({"generated_utc": "2026-11-13T15:00:00Z"}, "2026-11-13T14:00:00Z", NOW)[
            "lag_h"
        ]
        == 0.0
    )


def test_unreadable_release_is_unmeasured_not_zero() -> None:
    assert A.deploy_lag(None, "2026-11-13T14:00:00Z", NOW)["lag_h"] is None


def test_flow_measures_arrival_against_service() -> None:
    prs = [{"draft": True, "updated_at": _iso(NOW - timedelta(days=9))}] * 3 + [
        {"draft": False, "updated_at": _iso(NOW)}
    ]
    f = A.flow(opened_7d=30, merged_7d=7, open_prs=prs, now=NOW)
    assert f == {
        "open": 4,
        "drafts": 3,
        "idle_7d": 3,
        "opened_7d": 30,
        "merged_7d": 7,
        "arrival_over_service": 4.3,
        "days_to_drain": 4.0,
    }
    assert A.flow(5, 0, prs, NOW)["days_to_drain"] is None


def test_duplicates_only_count_machinery_files() -> None:
    files = {
        1: ["ops/box/workflow_gate.ps1", "desks/mt5/research/x.py"],
        2: ["ops/box/workflow_gate.ps1", "desks/mt5/research/x.py"],
        3: ["ops/box/workflow_gate.ps1", "desks/mt5/research/x.py"],
        4: ["libs/ops/a.py"],
    }
    assert A.duplicate_clusters(files) == [{"file": "ops/box/workflow_gate.ps1", "prs": [1, 2, 3]}]


def test_alarms_are_ranked_and_capped_and_green_means_nothing_to_say() -> None:
    doc = {
        "deploy_lag": {"lag_h": 70, "box_code_sha": "bb5", "adopted_at": "x"},
        "half_landed": [{"where": "w", "missing": "m"}],
        "queue": {"queued": 190, "oldest_h": 4.7, "workflow_run_burst_30m": 142},
        "flow": {
            "opened_7d": 319,
            "merged_7d": 33,
            "arrival_over_service": 9.7,
            "open": 597,
            "days_to_drain": 126,
        },
        "duplicates": [{"file": "f", "prs": [1, 2, 3]}],
        "box_tasks": {"failing": [{"name": "MT5-AdoptRelease"}]},
        "live_ci": {"run": 1, "job": "seal", "oldest_queued_job_h": 4.0},
    }
    out = A.finish(dict(doc))
    assert (
        out["status"] == "RED" and out["alarms_total"] == 8 and len(out["alarms"]) == A.MAX_ALARMS
    )
    assert [a["key"] for a in out["alarms"]] == [
        "DEPLOY_LAG",
        "LIVE_CI_STARVED",
        "HALF_LANDED",
        "CASCADE",
        "WIP_GROWTH",
    ]
    assert (
        A.finish({"queue": {"oldest_h": 0.1}, "flow": {"opened_7d": 2, "merged_7d": 2}})["status"]
        == "GREEN"
    )


def test_the_live_tree_has_no_half_landed_step_except_known_ones() -> None:
    # the tree this test runs on: a new missing script fails here, in the PR that causes it
    known = {"scripts/paperclip_lab_run.py"}  # #1095 lands it; remove from this set then
    missing = {h["missing"] for h in A.half_landed(A.ROOT)}
    assert missing <= known, missing - known
