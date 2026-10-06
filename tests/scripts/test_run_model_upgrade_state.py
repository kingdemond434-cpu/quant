"""The PANEL upgrade runner must record that it ran.

`max_audit.check_model_freshness` reads a `checked` timestamp out of data/model_upgrade.json to
decide whether the panel surface is still being asked "has a better flagship shipped?". The runner
appended its report to a jsonl history and never wrote that file, so a runner which discovered
four upgrade candidates on every scheduled pass was indistinguishable from one that had never
executed -- and `model-upgrade-never-panel` fired forever on a working system.

This is the same defect shape already fixed on the brain surface (scripts/brain_model_upgrade.py
_save()); it was found on this surface by asking where else that shape existed.
"""
from __future__ import annotations

import json

import pytest
import scripts.run_model_upgrade as rmu


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """No network, no paging, no chain rewrite -- and state/log redirected into tmp."""
    monkeypatch.setattr(rmu, "_list_models_api", lambda: [])
    monkeypatch.setattr(rmu, "_probe_candidates", lambda head: ["claude-opus-6"])
    monkeypatch.setattr(rmu, "read_chain", lambda: ["claude-opus-5", "claude-opus-4-8"])
    monkeypatch.setattr(rmu, "_page", lambda msg: None)
    monkeypatch.setattr(rmu, "_STATE", tmp_path / "model_upgrade.json")
    monkeypatch.setattr(rmu, "_LOG", tmp_path / "model_upgrade_log.jsonl")
    monkeypatch.setattr("sys.argv", ["run_model_upgrade.py"])
    return tmp_path


def test_report_only_run_records_that_the_check_ran(offline):
    """Report-only is how cron invokes it, so it is the path that MUST leave a record."""
    assert rmu.main() == 0
    state = json.loads((offline / "model_upgrade.json").read_text())
    assert state["checked"]                       # the field the fence actually reads
    assert state["mode"] == "report-only"
    assert state["head"] == "claude-opus-5"
    assert state["adopted"] is None               # report-only never promotes


def test_the_freshness_fence_is_satisfiable_by_a_working_runner(offline):
    """The point of the fix, stated as the property: a runner that ran clears the fence.

    Guards against a regression where state is written only on a branch cron never takes -- which
    is exactly how this failed before, and how the brain surface failed independently.
    """
    rmu.main()
    state = json.loads((offline / "model_upgrade.json").read_text())
    # mirrors check_model_freshness: absent/blank `checked` is what raises model-upgrade-never-*
    assert state.get("checked") not in (None, "")


def test_discovering_an_upgrade_does_not_suppress_the_record(offline):
    """A pass that FOUND something must still record it ran. The brain surface got this wrong in
    the opposite direction -- it saved state only when it found nothing -- so the check screamed
    loudest exactly when the loop was working."""
    rmu.main()
    state = json.loads((offline / "model_upgrade.json").read_text())
    assert "claude-opus-6" in state["upgrades"]   # it did find one
    assert state["checked"]                       # ...and still recorded the run
