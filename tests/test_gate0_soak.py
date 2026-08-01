"""Differential test for the Gate 0 soak floor. Runs against a TEMP root, never live state.

Deliberately not touching the real box: creating data/CASHCARRY_KILL to "test the latch branch"
would freeze the live executor. A test that fires a production rail to prove the rail is read is
not a test, it is an incident.

The case that matters most is the DEPOSIT one. My first draft took the max over all capital events,
which would have meant the principal funding the account resets his own soak timer -- the gate
punishing the exact act it exists to authorise.

THIS FILE WAS A SCRIPT WEARING A TEST'S NAME (fixed 2026-08-01). It executed its cases at module
scope and ended in `raise SystemExit(...)`. Pytest collects by IMPORTING, so that SystemExit
escaped the collector and aborted the whole session with INTERNALERROR -- exit 3, no report, every
other test in the repo silently never run. Two failures compounded: the desk's entire safety gate
was down, and the seven cases below had never once been enforced by CI even though the file that
holds them looked like proof that they were. A test module must never execute at import and must
never raise SystemExit; assert instead, so a failure is one red case rather than a dead suite.
"""
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest
import scripts.check_gate0_ready as g


def run(rows, latch=None):
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        (r / "data").mkdir()
        (r / "data/capital_events.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in rows), "utf-8")
        if latch:
            (r / "data" / latch).write_text("x", "utf-8")
        with mock.patch.object(g, "_ROOT", r):
            return g._soak_clean_7d()


def _cases():
    """Built inside the function so the clock is read at call time, not at import."""
    now = datetime.now(tz=UTC)
    old = {"kind": "RESTART", "at": (now - timedelta(days=8)).isoformat()}
    new = {"kind": "RESTART", "at": (now - timedelta(days=2)).isoformat()}
    dep = {"kind": "DEPOSIT", "at": (now - timedelta(hours=1)).isoformat()}
    odd = {"kind": "SOMETHING_NEW", "at": (now - timedelta(hours=1)).isoformat()}
    return [
        ("8d clean since restart",           [old],      None,             "READY"),
        ("2d clean -- inside the floor",     [new],      None,             "NOT-READY"),
        ("8d clean, DEPOSIT 1h ago",         [old, dep], None,             "READY"),
        ("8d clean, UNKNOWN kind 1h ago",    [old, odd], None,             "NOT-READY"),
        ("8d clean but kill-file LATCHED",   [old],      "CASHCARRY_KILL", "NOT-READY"),
        ("8d clean but deadman LATCHED",     [old],      "DEADMAN_FIRED",  "NOT-READY"),
        ("empty ledger -- no clock start",   [],         None,             "BLOCKED-UNKNOWN"),
    ]


@pytest.mark.parametrize(("name", "rows", "latch", "want"), _cases(),
                         ids=[c[0] for c in _cases()])
def test_the_soak_floor_rules_as_specified(name, rows, latch, want):
    got = run(rows, latch)["status"]
    assert got == want, f"{name} -> {got} (want {want})"
