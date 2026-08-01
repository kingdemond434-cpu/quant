"""Differential test for the Gate 0 soak floor. Runs against a TEMP root, never live state.

Deliberately not touching the real box: creating data/CASHCARRY_KILL to "test the latch branch"
would freeze the live executor. A test that fires a production rail to prove the rail is read is
not a test, it is an incident.

The case that matters most is the DEPOSIT one. My first draft took the max over all capital events,
which would have meant the principal funding the account resets his own soak timer -- the gate
punishing the exact act it exists to authorise.
"""
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

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


now = datetime.now(tz=UTC)
old = {"kind": "RESTART", "at": (now - timedelta(days=8)).isoformat()}
new = {"kind": "RESTART", "at": (now - timedelta(days=2)).isoformat()}
dep = {"kind": "DEPOSIT", "at": (now - timedelta(hours=1)).isoformat()}
odd = {"kind": "SOMETHING_NEW", "at": (now - timedelta(hours=1)).isoformat()}

CASES = [
    ("8d clean since restart",           [old],      None,             "READY"),
    ("2d clean -- inside the floor",     [new],      None,             "NOT-READY"),
    ("8d clean, DEPOSIT 1h ago",         [old, dep], None,             "READY"),
    ("8d clean, UNKNOWN kind 1h ago",    [old, odd], None,             "NOT-READY"),
    ("8d clean but kill-file LATCHED",   [old],      "CASHCARRY_KILL", "NOT-READY"),
    ("8d clean but deadman LATCHED",     [old],      "DEADMAN_FIRED",  "NOT-READY"),
    ("empty ledger -- no clock start",   [],         None,             "BLOCKED-UNKNOWN"),
]

bad = 0
for name, rows, latch, want in CASES:
    got = run(rows, latch)["status"]
    ok = got == want
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name:34s} -> {got} (want {want})")

print("ALL PASS" if not bad else f"{bad} CASE(S) FAILED")
raise SystemExit(1 if bad else 0)
