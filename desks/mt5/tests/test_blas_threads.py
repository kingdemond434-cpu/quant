"""The single-thread BLAS switch is OFF unless a run-bound, floor-clearing IDENTICAL proof for
this release, machine and BLAS build licenses it."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import blas_threads as bt  # noqa: E402
from research import judging_throughput as jt  # noqa: E402

KEY = b"test-signing-key-never-real"


def _full_doc(release: Path, **over) -> dict:
    """A report with every field the evidence floor reads, at the floor."""
    arm = {"n_judged": bt.MIN_SAMPLE, "census_calls": 1}
    doc = {"schema": bt.SCHEMA, "harness_version": bt.HARNESS_VERSION, "verdict": bt.IDENTICAL,
           "run_id": "run-1", "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
           "identity": bt.identity(release), "input": {"sampled_cells": bt.MIN_SAMPLE},
           "arms": {a: dict(arm) for a in bt.REQUIRED_ARMS},
           "thread_evidence": {"differed": True}, "differences": [], "n_differences": 0,
           "control_differences": 0,
           "rebuild_coverage": {"rebuilt": bt.MIN_REBUILT, "strata_unrebuilt": []}}
    doc.update(over)
    return doc


def _publish(tmp: Path, doc: dict, *, key: bytes | None = KEY, log: bool = True) -> Path:
    doc = dict(doc)
    doc["content_sha256"] = bt.content_sha256(doc)
    if key:
        doc["proof_hmac"] = bt.proof_hmac(doc["content_sha256"], key)
    p = tmp / "BLAS_DIFFERENTIAL.json"
    p.write_text(json.dumps(doc), "utf-8")
    if log:
        with open(tmp / "runs.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"run_id": doc.get("run_id"),
                                 "content_sha256": doc["content_sha256"]}) + "\n")
    return p


@pytest.fixture
def paths(tmp_path, monkeypatch):
    release = tmp_path / "RELEASE.json"
    release.write_text(json.dumps({"release_id": "abc123def456"}), "utf-8")
    flag = tmp_path / "BLAS_SINGLE_THREAD.json"
    monkeypatch.setattr(bt, "RELEASE", release)
    monkeypatch.setattr(bt, "FLAG", flag)
    monkeypatch.setattr(bt, "PROOF", tmp_path / "BLAS_DIFFERENTIAL.json")
    monkeypatch.setattr(bt, "RUN_LOG", tmp_path / "runs.jsonl")
    monkeypatch.setattr(bt, "_signing_key", lambda: KEY)
    for k in bt.THREAD_VARS:
        monkeypatch.delenv(k, raising=False)
    return tmp_path, release, flag


def _enable(flag: Path) -> None:
    flag.write_text(json.dumps({"enabled": True}), "utf-8")


def test_absent_flag_is_off_even_with_a_valid_proof(paths) -> None:
    tmp, release, _flag = paths
    _publish(tmp, _full_doc(release))
    d = bt.decide()
    assert d["active"] is False and d["env"] == {} and d["proof_valid"] is True, d


def test_enabled_with_a_valid_proof_sets_all_three_to_one(paths) -> None:
    tmp, release, flag = paths
    _enable(flag)
    _publish(tmp, _full_doc(release))
    d = bt.decide()
    assert d["active"] is True, d["why"]
    assert d["env"] == dict.fromkeys(bt.THREAD_VARS, "1")


def test_a_hand_built_five_field_report_licenses_nothing(paths) -> None:
    """The audit's forgery: schema, verdict, time, identity and a digest -- even run-logged."""
    tmp, release, flag = paths
    _enable(flag)
    doc = {"schema": bt.SCHEMA, "harness_version": bt.HARNESS_VERSION, "verdict": bt.IDENTICAL,
           "generated_utc": datetime.now(UTC).isoformat(), "identity": bt.identity(release),
           "run_id": "forged"}
    _publish(tmp, doc)
    d = bt.decide()
    assert d["active"] is False and "evidence floor" in d["why"], d["why"]


def test_a_report_no_run_wrote_is_refused(paths) -> None:
    tmp, release, flag = paths
    _enable(flag)
    _publish(tmp, _full_doc(release), log=False)
    assert "latest harness run" in bt.decide()["why"]
    _publish(tmp, _full_doc(release, run_id="run-1"))
    _publish(tmp, _full_doc(release, run_id="run-2"), log=False)     # newer file, older log
    assert bt.decide()["active"] is False


def test_on_a_keyed_box_the_mac_must_verify(paths) -> None:
    tmp, release, flag = paths
    _enable(flag)
    _publish(tmp, _full_doc(release), key=None)
    assert "proof_hmac" in bt.decide()["why"]
    _publish(tmp, _full_doc(release, run_id="run-3"), key=b"another-box-key")
    assert "proof_hmac" in bt.decide()["why"]
    _publish(tmp, _full_doc(release, run_id="run-4"))
    assert bt.decide()["active"] is True


def test_an_unkeyed_box_accepts_a_run_bound_report(paths, monkeypatch) -> None:
    tmp, release, flag = paths
    monkeypatch.setattr(bt, "_signing_key", lambda: None)
    _enable(flag)
    _publish(tmp, _full_doc(release), key=None)
    d = bt.decide()
    assert d["active"] is True and "run-bound" in d["why"], d["why"]


def _drop_arm(doc: dict, arm: str) -> dict:
    arms = dict(doc["arms"])
    arms.pop(arm)
    return {**doc, "arms": arms}


@pytest.mark.parametrize("mutate", [
    lambda d: {**d, "input": {"sampled_cells": bt.MIN_SAMPLE - 1}},
    lambda d: {**d, "arms": {**d["arms"], "single": {"n_judged": 2, "census_calls": 1}}},
    lambda d: {**d, "arms": {**d["arms"], "default": {"n_judged": 500, "census_calls": 0}}},
    lambda d: _drop_arm(d, "control"),
    lambda d: {**d, "thread_evidence": {"differed": False}},
    lambda d: {**d, "control_differences": None},
    lambda d: {**d, "control_differences": 1},
    lambda d: {**d, "rebuild_coverage": {"rebuilt": bt.MIN_REBUILT - 1,
                                         "strata_unrebuilt": []}},
    lambda d: {**d, "rebuild_coverage": {"rebuilt": 40, "strata_unrebuilt": ["causal_residual"]}},
    lambda d: {**d, "verdict": bt.DIFFERS},
    lambda d: {**d, "verdict": bt.UNMEASURED},
    lambda d: {**d, "schema": "blas_differential/v1"},
    lambda d: {**d, "harness_version": "1.0"},
    lambda d: {**d, "generated_utc": (datetime.now(UTC) - timedelta(days=8)).isoformat()},
    lambda d: {**d, "generated_utc": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    lambda d: {**d, "generated_utc": None},
])
def test_a_proof_below_the_floor_or_stale_falls_back_to_default(paths, mutate) -> None:
    tmp, release, flag = paths
    _enable(flag)
    _publish(tmp, mutate(_full_doc(release)))
    d = bt.decide()
    assert d["active"] is False and d["env"] == {}, d


@pytest.mark.parametrize("key", bt.IDENTITY_KEYS)
def test_a_proof_from_another_release_machine_or_blas_is_refused(paths, key) -> None:
    tmp, release, flag = paths
    _enable(flag)
    ident = {**bt.identity(release), key: "something-else"}
    _publish(tmp, _full_doc(release, identity=ident))
    d = bt.decide()
    assert d["active"] is False and key in d["why"], d["why"]


def test_a_hand_edited_proof_is_refused(paths) -> None:
    tmp, release, flag = paths
    _enable(flag)
    p = _publish(tmp, _full_doc(release, verdict=bt.DIFFERS))
    doc = json.loads(p.read_text("utf-8"))
    doc["verdict"] = bt.IDENTICAL                    # digest left as it was
    p.write_text(json.dumps(doc), "utf-8")
    assert "does not recompute" in bt.decide()["why"]


def test_an_unreleased_tree_never_activates(paths) -> None:
    tmp, release, flag = paths
    release.unlink()
    _enable(flag)
    _publish(tmp, _full_doc(release))
    assert bt.decide()["active"] is False


def test_flag_must_be_literally_true(paths) -> None:
    tmp, release, flag = paths
    _publish(tmp, _full_doc(release))
    for body in ('{"enabled": "yes"}', '{"enabled": 1}', "[]", "not json"):
        flag.write_text(body, "utf-8")
        assert bt.decide()["active"] is False, body


def test_all_three_or_none(paths, monkeypatch) -> None:
    tmp, release, flag = paths
    _enable(flag)
    _publish(tmp, _full_doc(release))
    env = {"OMP_NUM_THREADS": "4"}
    assert bt.apply(env) == {} and env == {"OMP_NUM_THREADS": "4"}, "never a mixed set"
    monkeypatch.setenv("MKL_NUM_THREADS", "2")
    env2: dict[str, str] = {}
    assert bt.apply(env2) == {} and env2 == {}, "an export in this process counts too"
    monkeypatch.delenv("MKL_NUM_THREADS")
    env3: dict[str, str] = {}
    assert bt.apply(env3) == dict.fromkeys(bt.THREAD_VARS, "1") == env3


def test_status_names_the_decision_and_a_mixed_operator_set(paths) -> None:
    tmp, release, _flag = paths
    _publish(tmp, _full_doc(release))
    st = bt.status(env={"OMP_NUM_THREADS": "4"})
    assert st["active"] is False and st["proof_valid"] is True and "not enabled" in st["why"]
    assert st["mixed_operator_set"] is True and st["in_force"] == {"OMP_NUM_THREADS": "4"}
    assert set(st["identity"]) == set(bt.IDENTITY_KEYS)
    assert st["probe_raw_diff"]["state"] == "UNMEASURED", "the proof recorded none"


def test_status_publishes_the_raw_probe_movement_without_it_binding(paths) -> None:
    """A recorded 1-ULP eigvalsh move is shown to the reader and never voids the proof."""
    tmp, release, flag = paths
    _enable(flag)
    prd = {"binding": False, "n_paths": 2, "eigvalsh_moved": True, "max_ulp": 1,
           "max_abs": 1.7763568394002505e-15, "also_in_control": []}
    _publish(tmp, _full_doc(release, probe_raw_diff=prd))
    st = bt.status()
    assert st["active"] is True and st["proof_valid"] is True, st["why"]
    got = st["probe_raw_diff"]
    assert got["state"] == "MEASURED" and got["max_ulp"] == 1 and got["eigvalsh_moved"] is True
    assert got["binding"] is False and got["run_id"] == "run-1"


def test_blas_build_is_read_without_loading_numpy() -> None:
    code = (f"import sys; sys.path[:0]=[{str(ROOT)!r},{str(DESK)!r}];"
            "from research import blas_threads as bt; b = bt.blas_build(); bt.identity();"
            "print(b['digest'] != 'absent', 'numpy' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, cwd=str(DESK))
    assert out.stdout.split() == ["True", "False"]


def test_apply_env_production_call_carries_the_switch(paths, monkeypatch) -> None:
    tmp, release, flag = paths
    monkeypatch.setattr(jt, "ENV_FILE", tmp / "no_env_file.json")
    probe: dict[str, str] = {}
    assert jt.apply_env(env=probe) == {}, "switch off: nothing added"
    _enable(flag)
    _publish(tmp, _full_doc(release))
    probe = {}
    applied = jt.apply_env(env=probe)
    assert probe == applied == dict.fromkeys(bt.THREAD_VARS, "1")


def test_apply_env_with_an_explicit_file_never_touches_blas(paths) -> None:
    """Callers that name a file (tests, tools) keep the exact worker env they asked for."""
    tmp, release, flag = paths
    _enable(flag)
    _publish(tmp, _full_doc(release))
    target: dict[str, str] = {}
    assert jt.apply_env(tmp / "absent.json", target) == {}
    assert target == {}


def test_the_throughput_publisher_records_the_switch(paths, monkeypatch) -> None:
    """The consumer makes the state visible: a lapsed proof is a published fact, not silence."""
    _tmp, _release, flag = paths
    _enable(flag)
    monkeypatch.setattr(jt, "measure_box", lambda now=None: {"source": "test", "cores": 4,
                                                             "is_judging_box": False})
    monkeypatch.setattr(jt, "declared_costs", lambda: {})
    monkeypatch.setattr(jt, "measure_queue", lambda: {"depth": 0})
    monkeypatch.setattr(jt, "plan", lambda box, queue, costs: {
        "limiting_resource": "cores", "workers": 1, "cadence_minutes": 5})
    monkeypatch.setattr(jt, "measure_rate", lambda *a, **k: {"status": "UNMEASURED"})
    out = jt.run(write=False, apply=False)
    st = out["blas_single_thread"]
    assert st["active"] is False and st["enabled"] is True
    assert "proof does not hold" in st["why"]


def test_the_switch_is_decided_before_numpy_loads() -> None:
    """BLAS reads its thread count at load, so nothing on either launcher path imports numpy:
    the judge's (run_sharded_gauntlet -> judging_throughput) and MT5-CacheWarm's."""
    code = (f"import sys; sys.path[:0]=[{str(ROOT)!r},{str(DESK)!r},"
            f"{str(DESK / 'scripts')!r}];"
            "import scripts.run_sharded_gauntlet, research.judging_throughput, "
            "research.blas_threads, warm_gauntlet_cache;"
            "from research.judging_throughput import apply_env; apply_env(env={});"
            "warm_gauntlet_cache._apply_blas_switch();"
            "print('numpy' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, cwd=str(DESK))
    assert out.stdout.strip() == "False"


def test_cachewarm_takes_the_switch_before_the_judge_loads() -> None:
    src = (DESK / "scripts" / "warm_gauntlet_cache.py").read_text("utf-8")
    body = src.split("def _cli_main()", 1)[1]
    assert body.index("_apply_blas_switch()") < body.index("exclusive_job")
    assert "blas_threads.apply(os.environ)" in src
