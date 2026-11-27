"""Boot r20 (zuck 2026-11-27 01:16-01:21Z: a CLEARed build goes live as fast as possible, every
stage measured). Box 11-26: 0 adoptions in 7 days, 145 CLEARed changes built but not live --
one PR checked per ~2 h pass, two code-red PRs re-run every pass because their output tail
looked like a box defect, the drop read once per pass, and the only full run of LIVE (an env
red on 11-20) never re-run. These pin the r20 answers to each."""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from ops.box_git import box_ci, delivery_leadtime
from ops.box_git import box_loop as L

NOW = datetime(2026, 11, 27, 2, 0, tzinfo=UTC)


def _run(name: str, summary: str, *, ok: bool = False, mins_ago: float = 5) -> dict:
    return {"name": name, "status": "completed", "conclusion": "success" if ok else "failure",
            "started_at": (NOW - timedelta(minutes=mins_ago)).isoformat(), "id": 1,
            "output": {"summary": summary}}


# ------------------------------------------------------------------ 1. a code red is final
def test_a_framed_rc1_is_a_code_red_whatever_its_tail_says() -> None:
    tail = "box: replay-shadow rc=1: scenario 7 timed out after 30s; did not answer in time"
    assert not L._env_red(_run("replay-shadow", tail))
    assert L._env_red(_run("replay-shadow", "box: replay-shadow rc=124: timed out after 3600s"))
    assert L._env_red(_run("risk-invariants", "box: risk-invariants static rc=128: x"))
    assert not L._env_red(_run("risk-invariants", "box: risk suites rc=2: 1 failed"))
    # unframed text keeps the old reading
    assert L._env_red(_run("quality", "the CI worker did not answer in time"))


def test_pr_127_shape_is_checked_and_never_rerun_every_pass() -> None:
    runs = [_run("risk-invariants", "box: risk-invariants passed (3 suite file(s))", ok=True),
            _run("replay-shadow", 'box: replay-shadow rc=1: , "sleeves": [...] timed out after '
                                  "40s FUSION-ROSTER declaration")]
    assert L.checked(runs, NOW)


# ------------------------------------------------------- 2. parallel, continuous PR checks
def test_pr_checks_run_in_parallel_and_pick_up_prs_imported_mid_stage(monkeypatch) -> None:
    prs = [{"number": n, "head": {"sha": f"{n:040x}", "ref": f"b{n}"}} for n in (1, 2, 3)]
    late = {"number": 9, "head": {"sha": f"{9:040x}", "ref": "b9"}}
    calls = {"lists": 0}

    class F:
        def gh(self, path: str):
            if "/pulls" in path:
                calls["lists"] += 1
                return prs + ([late] if calls["lists"] > 1 else [])
            if "check-runs" in path:
                return {"check_runs": []}
            return [{"body": "AUDIT CLEAR x"}]

    monkeypatch.setattr(L, "_forge", lambda cfg, acct: F())
    monkeypatch.setattr(L, "audited_clear", lambda comments, head: True)
    live, peak, lock = [0], [0], threading.Lock()

    def check(cfg, p):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.3)
        with lock:
            live[0] -= 1
        return f"PR #{p['number']}: ok"

    monkeypatch.setattr(L, "check_pr", check)
    out = L.pr_tick(SimpleNamespace(), budget_s=30, parallel=3, relist_s=0.05)
    assert peak[0] == 3                                   # three at once, not one per pass
    for n in (1, 2, 3, 9):
        assert f"PR #{n}: ok" in out                      # #9 arrived while the others ran


def test_one_pr_raising_never_stops_the_others(monkeypatch) -> None:
    prs = [{"number": n, "head": {"sha": f"{n:040x}", "ref": "x"}} for n in (1, 2)]

    class F:
        def gh(self, path: str):
            return prs if "/pulls" in path else {"check_runs": []}

    monkeypatch.setattr(L, "_forge", lambda cfg, acct: F())
    monkeypatch.setattr(L, "audited_clear", lambda comments, head: True)

    def check(cfg, p):
        if p["number"] == 1:
            raise RuntimeError("boom")
        return "PR #2: ok"

    monkeypatch.setattr(L, "check_pr", check)
    out = L.pr_tick(SimpleNamespace(), budget_s=30, parallel=2, relist_s=0.05)
    assert "PR #1: ERROR RuntimeError" in out and "PR #2: ok" in out


def test_parallelism_is_a_third_of_the_cores_capped() -> None:
    assert L.pr_parallel(18) == 6 and L.pr_parallel(4) == 1 and L.pr_parallel(64) == 6


def test_the_worker_runs_jobs_concurrently_and_takes_new_ones(tmp_path: Path) -> None:
    pend = tmp_path / "pending"
    pend.mkdir()

    def job(i: int) -> None:
        (pend / f"{i}.json").write_text(json.dumps(
            {"id": str(i), "argv": [sys.executable, "-c", "import time; time.sleep(0.6)"],
             "cwd": str(tmp_path), "env": {}, "timeout": 30}), encoding="utf-8")

    for i in range(3):
        job(i)
    threading.Timer(0.3, job, args=(3,)).start()
    t0 = time.monotonic()
    n = L.worker_pass(tmp_path, parallel=3, idle_exit_s=0.5, poll_s=0.05)
    took = time.monotonic() - t0
    assert n == 4
    assert took < 4 * 0.6 + 0.5          # serial would be >= 2.4 s of sleeps plus the idle wait
    assert all(json.loads((tmp_path / "done" / f"{i}.json").read_text())["rc"] == 0
               for i in range(4))


# ------------------------------------------------------------------ 3. the light loop
def test_light_stages_repeat_while_the_heavy_stages_run() -> None:
    count = {"drop": 0}

    def drop() -> str:
        count["drop"] += 1
        return "nothing new"

    def heavy() -> str:
        time.sleep(0.6)
        return "done"

    seen: list[dict] = []
    stages = {"drop": drop, "pr": heavy, "full": lambda: "LIVE's head is already run"}
    cfg = SimpleNamespace(work=Path("/nonexistent-r20"), bare=Path("."))
    out = L.tick(cfg, light_every_s=0.1, stages=stages, progress=seen.append)
    assert out["pr"] == "done" and out["full"].startswith("LIVE")
    assert count["drop"] >= 4                     # first round, repeats, and a last round
    assert out["light_rounds"] == count["drop"]
    assert seen and all(d["in_progress"] for d in seen)
    assert out["stage_timing"]["pr"]["runs"] == 1


# ------------------------------------------------------- 4. the full suite is re-run on env
def _full(ok: bool, why: str, hours_ago: float, head: str = "a" * 40) -> dict:
    return {"head": head, "kind": box_ci.FULL, "ok": ok, "why": why,
            "at": (NOW - timedelta(hours=hours_ago)).isoformat()}


ENV_11_20 = ("law gate rc=124; pytest rc=1: PermissionError: [Errno 13] Permission denied: "
             "'C:\\\\ProgramData\\\\QuantBox\\\\forge\\\\work\\\\wt_03h6brs1\\\\pyproject.toml'")


def test_the_11_20_env_red_is_run_again_but_not_forever() -> None:
    live = "a" * 40
    st = {"full_results": [_full(False, ENV_11_20, 160)]}
    assert box_ci.plan_full_run(st, live, NOW).start == live
    st = {"full_results": [_full(False, ENV_11_20, 0.5)]}
    assert box_ci.plan_full_run(st, live, NOW).start is None          # waits its interval
    st = {"full_results": [_full(False, ENV_11_20, h) for h in (5, 3, 2)]}
    assert box_ci.plan_full_run(st, live, NOW).start is None          # re-runs spent
    st = {"full_results": [_full(False, ENV_11_20, 5), _full(False, "law gate rc=0; pytest rc=1: "
                                                              "3 failed", 3)]}
    assert box_ci.plan_full_run(st, live, NOW).start is None          # a code answer stands
    assert box_ci.promotable({"full_results": [_full(False, ENV_11_20, 5)]},
                             lambda a, b: True) is None                # env is never green


def test_junit_outcomes_keep_node_ids_and_signatures(tmp_path: Path) -> None:
    j = tmp_path / "j.xml"
    j.write_text(
        '<testsuites><testsuite errors="1" failures="1" skipped="1" tests="4">'
        '<testcase classname="tests.ops.test_a" name="test_ok"/>'
        '<testcase classname="tests.ops.test_a" name="test_bad">'
        '<failure message="assert 1 == 2" type="AssertionError">long</failure></testcase>'
        '<testcase classname="tests.ops.test_b" name="test_err">'
        '<error message="boom" type="RuntimeError"/></testcase>'
        '<testcase classname="tests.ops.test_b" name="test_skip"><skipped message="x"/></testcase>'
        "</testsuite></testsuites>", encoding="utf-8")
    d = box_ci.junit_outcomes(j)
    assert (d["collected"], d["passed"], d["failed"], d["error"], d["skipped"]) == (4, 1, 1, 1, 1)
    assert d["outcomes"]["tests/ops/test_a.py::test_bad"] == "failed"
    assert d["sigs"]["tests/ops/test_a.py::test_bad"] == "AssertionError: assert 1 == 2"
    assert box_ci.junit_outcomes(tmp_path / "missing.xml").get("unreadable")
    f = box_ci.save_full_nodes(tmp_path / "state.json", "a" * 40, d)
    assert f is not None and json.loads(f.read_text())["collected"] == 4


# -------------------------------------------------------------- 5. per-stage SLA + alarm
def _row(pr: int, **stages: float) -> dict:
    return {"pr": pr, "state": "open", "ci_causes": [],
            "stages": {k: (NOW - timedelta(minutes=v)).isoformat() for k, v in stages.items()}}


def test_sla_names_each_stage_past_its_limit_and_the_silent_checker() -> None:
    rows = [_row(146, forge_pr=420, clear=419), _row(147, forge_pr=5, clear=4),
            _row(150, forge_pr=90, clear=89, ci_start=80, ci_end=70)]
    s = delivery_leadtime.sla(rows, NOW)
    assert not s["ok"]
    assert s["breaches"]["clear"]["prs"] == [146]           # #147 is inside its 10 min
    assert s["breaches"]["ci_end"]["prs"] == [150]          # green 70 min and not merged
    assert s["alarms"][0]["alarm"] == "ci_zero_output" and s["alarms"][0]["silent_min"] == 70.0


def test_a_code_red_waiting_at_ci_end_is_not_a_loop_breach() -> None:
    r = _row(127, forge_pr=900, clear=899, ci_start=800, ci_end=700)
    r["ci_causes"] = ["other"]
    assert delivery_leadtime.sla([r], NOW)["ok"]
