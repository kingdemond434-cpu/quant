"""A job dropped from the manifest kept its verdict and lost its seat in the summary.

MEASURED 2026-08-28: `data/job_manifest.json` held 17 rows with 2 FROZEN while its own `summary`
said 16 rows and 1 FROZEN. `state["jobs"]` persists across runs and was never pruned, so
`desks/mt5/data/sleeve_registry.json` -- deliberately retired from JOBS 19 hours earlier, with a
good reason -- kept reading FROZEN to anything that walked `jobs`, while `summary` (built from
this run's evaluations) silently stopped counting it. Two consumers, two answers, one file.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_job_manifest.py"


@pytest.fixture()
def mod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The module with STATE/ALARM redirected. It resolves ROOT from __file__, so `cwd` is not a
    redirect -- this desk has archived live sleeves learning that."""
    spec = importlib.util.spec_from_file_location("check_job_manifest_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE", tmp_path / "job_manifest.json")
    monkeypatch.setattr(module, "ALARM", tmp_path / "ALARM.txt")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "request_repair", lambda *a, **k: None)
    (tmp_path / "live.json").write_text('{"a": 1}', encoding="utf-8")
    monkeypatch.setattr(module, "JOBS", {"live.json": (26.0, "a consumer")})
    yield module
    sys.modules.pop(spec.name, None)


def _state(mod) -> dict:
    return json.loads(mod.STATE.read_text(encoding="utf-8"))


def test_a_dropped_job_is_retired_not_left_reading_frozen(mod) -> None:
    mod.STATE.write_text(json.dumps({"jobs": {
        "live.json": {"status": "OK", "hash": "x", "hash_runs": 1},
        "gone.json": {"status": "FROZEN", "hash": "y", "hash_runs": 53,
                      "checked_at": "2026-08-27T08:07:08+00:00"},
    }}), encoding="utf-8")

    mod.main()

    st = _state(mod)
    assert "gone.json" not in st["jobs"], "a row nothing evaluates must not sit in `jobs`"
    assert "gone.json" in st["retired"], "and it must not be deleted either -- keep the record"
    assert st["retired"]["gone.json"]["status"] == "FROZEN"
    assert st["retired"]["gone.json"]["retired_at"]


def test_the_summary_counts_exactly_the_rows_that_exist(mod) -> None:
    """The defect in one line: sum(summary) != len(jobs)."""
    mod.STATE.write_text(json.dumps({"jobs": {
        "live.json": {"status": "OK", "hash": "x", "hash_runs": 1},
        "gone.json": {"status": "FROZEN", "hash": "y", "hash_runs": 53},
    }}), encoding="utf-8")

    mod.main()

    st = _state(mod)
    assert sum(st["summary"].values()) == len(st["jobs"]) == 1


def test_a_retirement_is_announced_so_an_accidental_one_is_findable(mod) -> None:
    """A JOBS line lost in an edit looks exactly like a deliberate retirement -- unless it speaks."""
    mod.STATE.write_text(json.dumps({"jobs": {
        "gone.json": {"status": "OK", "hash": "y", "hash_runs": 3},
    }}), encoding="utf-8")

    mod.main()

    assert mod.ALARM.exists()
    assert "RETIRED gone.json" in mod.ALARM.read_text(encoding="utf-8")
