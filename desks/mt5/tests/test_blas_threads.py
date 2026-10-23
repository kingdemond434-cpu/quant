"""The single-thread BLAS switch is OFF unless a release-bound IDENTICAL proof licenses it."""
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


def _proof(tmp: Path, release: Path, **over) -> Path:
    doc = {"schema": bt.SCHEMA, "verdict": bt.IDENTICAL,
           "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
           "identity": bt.identity(release)}
    doc.update(over)
    doc["content_sha256"] = bt.content_sha256(doc)
    p = tmp / "BLAS_DIFFERENTIAL.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


@pytest.fixture
def paths(tmp_path, monkeypatch):
    release = tmp_path / "RELEASE.json"
    release.write_text(json.dumps({"release_id": "abc123def456"}), "utf-8")
    flag = tmp_path / "BLAS_SINGLE_THREAD.json"
    monkeypatch.setattr(bt, "RELEASE", release)
    monkeypatch.setattr(bt, "FLAG", flag)
    monkeypatch.setattr(bt, "PROOF", tmp_path / "BLAS_DIFFERENTIAL.json")
    return tmp_path, release, flag


def test_absent_flag_is_off_even_with_a_valid_proof(paths) -> None:
    tmp, release, _flag = paths
    _proof(tmp, release)
    d = bt.decide()
    assert d["active"] is False and d["env"] == {}


def test_enabled_with_a_valid_proof_sets_all_three_to_one(paths) -> None:
    tmp, release, flag = paths
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    _proof(tmp, release)
    d = bt.decide()
    assert d["active"] is True, d["why"]
    assert d["env"] == {"OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1"}


@pytest.mark.parametrize("over", [
    {"verdict": "DIFFERS"}, {"verdict": "UNMEASURED"}, {"schema": "other/v0"},
    {"generated_utc": (datetime.now(UTC) - timedelta(days=8)).isoformat()},
    {"generated_utc": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    {"generated_utc": None},
])
def test_a_proof_that_does_not_hold_falls_back_to_default_threads(paths, over) -> None:
    tmp, release, flag = paths
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    _proof(tmp, release, **over)
    d = bt.decide()
    assert d["active"] is False and d["env"] == {}, d


def test_a_proof_from_another_release_or_machine_is_refused(paths) -> None:
    tmp, release, flag = paths
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    for key, value in (("release_id", "ffffffffffff"), ("cores", 999), ("numpy", "0.0"),
                       ("python", "2.7.18")):
        ident = {**bt.identity(release), key: value}
        _proof(tmp, release, identity=ident)
        assert bt.decide()["active"] is False, key


def test_a_hand_edited_proof_is_refused(paths) -> None:
    tmp, release, flag = paths
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    p = _proof(tmp, release, verdict=bt.DIFFERS)
    doc = json.loads(p.read_text("utf-8"))
    doc["verdict"] = bt.IDENTICAL                    # digest left as it was
    p.write_text(json.dumps(doc), "utf-8")
    assert "does not recompute" in bt.decide()["why"]


def test_an_unreleased_tree_never_activates(paths) -> None:
    tmp, release, flag = paths
    release.unlink()
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    _proof(tmp, release)
    assert bt.decide()["active"] is False


def test_flag_must_be_literally_true(paths) -> None:
    tmp, release, flag = paths
    _proof(tmp, release)
    for body in ('{"enabled": "yes"}', '{"enabled": 1}', "[]", "not json"):
        flag.write_text(body, "utf-8")
        assert bt.decide()["active"] is False, body


def test_apply_never_overwrites_an_operator_export(paths) -> None:
    tmp, release, flag = paths
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    _proof(tmp, release)
    env = {"OPENBLAS_NUM_THREADS": "4"}
    applied = bt.apply(env)
    assert env["OPENBLAS_NUM_THREADS"] == "4"
    assert applied == {"MKL_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}


def test_apply_env_production_call_carries_the_switch(paths, monkeypatch) -> None:
    tmp, release, flag = paths
    monkeypatch.setattr(jt, "ENV_FILE", tmp / "no_env_file.json")
    probe: dict[str, str] = {}
    assert jt.apply_env(env=probe) == {}, "switch off: nothing added"
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    _proof(tmp, release)
    probe = {}
    applied = jt.apply_env(env=probe)
    assert probe == applied == dict.fromkeys(bt.THREAD_VARS, "1")


def test_apply_env_with_an_explicit_file_never_touches_blas(paths) -> None:
    """Callers that name a file (tests, tools) keep the exact worker env they asked for."""
    tmp, release, flag = paths
    flag.write_text(json.dumps({"enabled": True}), "utf-8")
    _proof(tmp, release)
    target: dict[str, str] = {}
    assert jt.apply_env(tmp / "absent.json", target) == {}
    assert target == {}


def test_the_switch_is_decided_before_numpy_loads() -> None:
    """BLAS reads its thread count at load, so nothing on the launcher path may import numpy."""
    code = (f"import sys; sys.path[:0]=[{str(ROOT)!r},{str(DESK)!r}];"
            "import scripts.run_sharded_gauntlet, research.judging_throughput, "
            "research.blas_threads;"
            "from research.judging_throughput import apply_env; apply_env(env={});"
            "print('numpy' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, cwd=str(DESK))
    assert out.stdout.strip() == "False"
