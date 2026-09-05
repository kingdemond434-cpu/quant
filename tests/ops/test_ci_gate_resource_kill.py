"""A resource kill is not a code failure (gap-fixer 2026-08-26).

`run_ci.py` already writes a separate `killed` list, and its entries carry their own diagnosis.
The 2026-08-26 marker reads verbatim: "KILLED sig9, MemAvailable 827MB, 495MB of RAM held by
files under /tmp (tmpfs) -- box ran out of resources mid-step, NOT a code failure". max_audit
never read that field, so the desk-wide safety gate reported "RED on COMMITTED code" about a run
whose own record says the code was never the problem.

The two demand OPPOSITE repairs -- find a bug that does not exist, versus reclaim memory and
re-run -- and merging them is the failure the tracked_ok fix in the same function was written
for: a red nobody can act on recurs, gets skimmed, and buries a real one.

Both remain DEFECTS. Unknown is never green; only the name and the prescribed repair change.
"""
from __future__ import annotations

import json

from scripts import max_audit

_KILL = ("tests (pytest) (KILLED sig9, MemAvailable 827MB, 495MB of RAM held by files under "
         "/tmp (tmpfs) -- box ran out of resources mid-step, NOT a code failure; re-run "
         "when quiet)")


def _run(tmp_path, monkeypatch, payload):
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/.ci_last_run.json").write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    defects: list = []
    max_audit.check_ci_gate(defects)
    return defects


def _ids(defects):
    return {d[0] for d in defects}


def test_a_resource_kill_is_named_as_capacity_not_as_broken_code(tmp_path, monkeypatch):
    """THE DEFECT VERBATIM, from the live 2026-08-26 marker."""
    payload = {"ok": False, "ts": "2026-08-26T08:02:30.596531+00:00",
               "tracked_ok": False, "failed": [_KILL], "failed_tracked": [_KILL],
               "killed": [_KILL], "inflight": [], "failed_tests": {}}
    defects = _run(tmp_path, monkeypatch, payload)
    ids = _ids(defects)
    assert "ci-gate-resource-killed" in ids, ids
    assert "ci-gate-red" not in ids, "a resource kill was reported as broken committed code"
    msg = next(d[1] for d in defects if d[0] == "ci-gate-resource-killed")
    assert "proven NOTHING" in msg, "a non-finishing gate must not read as green"
    assert "reclaim memory" in msg, "the defect must name the repair it actually needs"


def test_a_real_test_failure_is_still_ci_gate_red(tmp_path, monkeypatch):
    """POSITIVE CONTROL. Splitting the verdict must not soften the one that matters -- a genuine
    failure on committed code still takes the desk-wide safety gate down."""
    payload = {"ok": False, "ts": "2026-08-26T08:02:30.596531+00:00",
               "tracked_ok": False, "failed": ["tests (pytest) 3 failed"],
               "failed_tracked": ["tests (pytest) 3 failed"], "killed": []}
    ids = _ids(_run(tmp_path, monkeypatch, payload))
    assert "ci-gate-red" in ids and "ci-gate-resource-killed" not in ids, ids


def test_a_mixed_run_is_red_not_excused(tmp_path, monkeypatch):
    """One genuine failure alongside a kill is a CODE red. Excusing the whole run because part of
    it was a resource kill would be the loophole this split could otherwise open."""
    payload = {"ok": False, "ts": "2026-08-26T08:02:30.596531+00:00",
               "tracked_ok": False,
               "failed_tracked": [_KILL, "mypy (2 errors in committed code)"],
               "killed": [_KILL]}
    ids = _ids(_run(tmp_path, monkeypatch, payload))
    assert "ci-gate-red" in ids, ids
    assert "ci-gate-resource-killed" not in ids


def test_a_green_run_produces_neither(tmp_path, monkeypatch):
    payload = {"ok": True, "tracked_ok": True, "ts": "2026-08-26T08:02:30.596531+00:00",
               "failed": [], "failed_tracked": [], "killed": []}
    ids = _ids(_run(tmp_path, monkeypatch, payload))
    assert "ci-gate-red" not in ids and "ci-gate-resource-killed" not in ids
