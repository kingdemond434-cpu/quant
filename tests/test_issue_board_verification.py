"""Repair attempts are not evidence that an operational defect is closed."""
from unittest.mock import patch

import pytest

from desks.mt5.research import issue_board as board


def issue(key="stale:test", severity="STALLED"):
    return board.Issue(key, severity, "test", "test", "python producer.py", True)


@pytest.mark.parametrize("remains,expected", [(True, "UNRESOLVED"), (False, "REPAIRED")])
def test_verifies_postcondition_and_recounts(remains, expected):
    original = issue()
    with patch.object(board, "collect", side_effect=[[original], [original] if remains else []]), \
         patch.object(board, "repair", return_value=[{"key": original.key, "action": "RAN"}]):
        result = board.run(apply=True)
    assert result["actions"][0]["action"] == expected
    assert result["count"] == int(remains)
    assert result["count_before"] == 1
    assert result["verified_repairs"] == int(not remains)


def test_failed_verifier_preserves_issue():
    original = issue()
    with patch.object(board, "collect", side_effect=[[original], ValueError("bad evidence")]), \
         patch.object(board, "repair", return_value=[{"key": original.key, "action": "RAN"}]):
        result = board.run(apply=True)
    assert result["count"] == 1
    assert result["actions"][0]["action"] == "UNVERIFIED"
    assert result["verified_repairs"] == 0


@pytest.mark.parametrize("key,severity", [("alarm:test", "CAPITAL"),
                                         ("gate_threshold:test", "DEGRADED"),
                                         ("merge_conflict:test", "BLIND")])
def test_protected_repairs_refused_even_when_flagged_auto(key, severity):
    with patch.object(board.subprocess, "run") as execute:
        result = board.repair([issue(key, severity)], apply=True)
    assert result[0]["action"] == "REFUSED"
    execute.assert_not_called()


def test_nonzero_exit_is_failure(tmp_path):
    (tmp_path / "producer.py").touch()
    with patch.object(board, "BASE", tmp_path), \
         patch.object(board.subprocess, "run") as execute:
        execute.return_value.returncode = 1
        execute.return_value.stdout = "failed"
        result = board.repair([issue()], apply=True)
    assert result[0]["action"] == "FAILED"


def test_dry_run_does_not_claim_verification():
    with patch.object(board, "collect", return_value=[issue()]) as collect:
        result = board.run()
    assert collect.call_count == 1
    assert result["verified_repairs"] == 0
    assert result["actions"][0]["action"] == "WOULD_RUN"
