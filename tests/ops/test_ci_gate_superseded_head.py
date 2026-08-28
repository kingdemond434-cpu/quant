"""A red verdict is a statement about a TREE, and the tree moves (CRO cycle 2026-08-28).

Measured that morning: the 08:54 CI marker recorded 25 committed-code failures
(`test_regime_monitor_wake`, `test_prompt_ratchet`, `test_short_order_path`, four governance
fences). Every one of them was fixed by 09:39 in commits 99247a13/22c91fd7/fb8be731 -- re-running
the exact 25 at 10:00 gave 127 passed. max_audit nonetheless kept reporting "RED on COMMITTED
code" and naming those tests, sending a reader to hunt a bug that no longer existed.

That is the same burying the `tracked_ok` and `killed` splits in the same function were each
written to stop: an un-actionable red recurs, gets skimmed, and hides the next real one. The
marker could not say WHICH commit it measured, so no consumer could tell "still broken" from
"already fixed, never re-run" -- and those demand opposite work.

Both stay DEFECTS. A verdict about a superseded tree has proven nothing about this one, and
unknown is never green; only the name and the prescribed repair change.
"""
from __future__ import annotations

import json

from scripts import max_audit

_TS = "2026-08-28T08:54:21.292840+00:00"
_OLD = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_NEW = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_FAIL = ["tests (pytest) 25 failed"]


def _run(tmp_path, monkeypatch, payload, head):
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/.ci_last_run.json").write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    monkeypatch.setattr(max_audit, "_git_head", lambda: head)
    defects: list = []
    max_audit.check_ci_gate(defects)
    return {d[0] for d in defects}, defects


def _payload(**extra):
    base = {"ok": False, "ts": _TS, "tracked_ok": False, "failed": _FAIL,
            "failed_tracked": _FAIL, "killed": [], "inflight": [], "failed_tests": {}}
    base.update(extra)
    return base


def test_a_red_measured_on_a_superseded_commit_is_named_as_unproven_not_as_broken_code(
        tmp_path, monkeypatch):
    """THE DEFECT VERBATIM: red at commit A, HEAD has since moved to B."""
    ids, defects = _run(tmp_path, monkeypatch, _payload(head=_OLD), _NEW)
    assert "ci-gate-red-superseded" in ids, ids
    assert "ci-gate-red" not in ids, "a superseded red was reported as broken committed code"
    msg = next(d[1] for d in defects if d[0] == "ci-gate-red-superseded")
    assert "proven nothing" in msg, "a superseded gate must not read as green"
    assert "re-run" in msg, "the defect must name the repair it actually needs"
    assert _OLD[:8] in msg and _NEW[:8] in msg, "both commits must be legible to the reader"


def test_a_red_measured_on_the_current_commit_is_still_ci_gate_red(tmp_path, monkeypatch):
    """POSITIVE CONTROL. The split must not soften the verdict that matters -- a red still
    standing against the tree the desk is running takes the desk-wide safety gate down."""
    ids, _ = _run(tmp_path, monkeypatch, _payload(head=_NEW), _NEW)
    assert "ci-gate-red" in ids and "ci-gate-red-superseded" not in ids, ids


def test_a_marker_without_a_head_still_escalates(tmp_path, monkeypatch):
    """FAIL-CLOSED on the old format. Markers written before this fix carry no `head`; a missing
    stamp is "cannot tell", and cannot-tell must never be spent softening a safety verdict."""
    ids, _ = _run(tmp_path, monkeypatch, _payload(), _NEW)
    assert "ci-gate-red" in ids and "ci-gate-red-superseded" not in ids, ids


def test_an_unresolvable_head_still_escalates(tmp_path, monkeypatch):
    """FAIL-CLOSED on a broken git dir: _git_head returns None and the red keeps its teeth."""
    ids, _ = _run(tmp_path, monkeypatch, _payload(head=_OLD), None)
    assert "ci-gate-red" in ids and "ci-gate-red-superseded" not in ids, ids


def test_run_ci_stamps_the_commit_it_measured(tmp_path, monkeypatch):
    """THE PRODUCER HALF. A consumer that reads `head` is worthless if nothing writes it -- the
    two halves of this fix travel by different routes and only one of them is self-evidencing."""
    import inspect

    from scripts import run_ci

    src = inspect.getsource(run_ci)
    assert '"head": head' in src, "run_ci must record which commit its verdict measured"
