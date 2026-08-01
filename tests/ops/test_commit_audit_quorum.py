"""The commit audit must not row a finding when NO SEAT REPLIED.

WHY THIS TEST EXISTS. ops/run_commit_audit.sh gated its ledger write on the panel's EXIT CODE,
and scripts/run_external_panel.py exits 0 when every seat fails -- it prints "zero responses" and
returns cleanly. The organ's very first run (2026-08-01T16:58Z) therefore rowed R0341 claiming
"independent seats reviewed the last 24h of desk commits" after tencent 404'd, cohere and
nvidia-nano 400'd, and nvidia threw KeyError('choices'). 0/4 substantive, no inbox written,
nothing reviewed by anybody.

That is the UNMEASURED-REPORTED-AS-OK defect class (L1.40) aimed at the conversion queue: one
un-actionable row per day into a backlog already arriving ~4x faster than it drains (L1.28b), and
each phantom row costs a human triage slot just to discover it is empty.

The fix gates on the ARTIFACT -- docs/research/panel_inbox.md, which run_external_panel.py writes
only inside `if ok:` (scripts/run_external_panel.py:419-421) -- so the question "did a seat
actually answer?" is decided by a file that changed, never by an exit code.

These tests exercise the shell gate itself in both directions, because the failure was in the
CONDITION and a source-level grep would pass against a condition that is merely present.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "run_commit_audit.sh"


def _gate_snippet() -> str:
    """Extract the live gating block from the real script, so the test cannot drift from it.

    Deliberately re-reads the shipped file rather than restating the condition: a test that
    hardcodes its own copy of the logic proves only that the copy works.
    """
    src = SCRIPT.read_text("utf-8")
    m = re.search(r"^INBOX_AFTER=.*?^fi$", src, re.M | re.S)
    assert m, "gating block not found -- run_commit_audit.sh changed shape; update this test"
    return m.group(0)


def _run_gate(tmp_path: Path, *, rc: str, inbox_bumped: bool, log_body: str) -> tuple[str, str]:
    """Run the extracted gate with a stubbed ledger writer. Returns (ledger_calls, log_text)."""
    log = tmp_path / "audit.log"
    log.write_text(log_body, "utf-8")
    inbox = tmp_path / "panel_inbox.md"
    inbox.write_text("x", "utf-8")
    ledger = tmp_path / "ledger_calls.txt"

    # Stub `.venv/bin/python scripts/recommendations.py add ...` -- the gate's only side effect.
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text(
        f'#!/bin/sh\necho "$@" >> "{ledger}"\n', "utf-8")
    (venv / "python").chmod(0o755)

    before = 0 if inbox_bumped else int(inbox.stat().st_mtime)
    prelude = (f'cd "{tmp_path}"\nLOG="{log}"\nINBOX="{inbox}"\n'
               f'INBOX_BEFORE={before}\nRC={rc}\n')
    subprocess.run(["bash", "-c", prelude + _gate_snippet()],
                   cwd=tmp_path, check=True, capture_output=True, text=True, timeout=60)
    return (ledger.read_text("utf-8") if ledger.exists() else ""), log.read_text("utf-8")


def test_zero_seats_rows_nothing_and_says_so() -> None:
    """THE REGRESSION. rc=0 + no inbox write => NO row, and NO-QUORUM stated in the log.

    Fails against the pre-fix `if [ "$RC" = "0" ]` gate, which rows unconditionally here.
    """
    calls, log = _run_gate(
        tmp_path=_TMP(), rc="0", inbox_bumped=False,
        log_body="panel: zero responses -- check keys/quotas\n"
                 "panel: 0/4 substantive; next payload budget 40,000\n")
    assert calls == "", f"rowed a finding with zero seat replies: {calls!r}"
    assert "NO-QUORUM" in log
    assert "0/4" in log, "the measured seat count must reach the log, not just the verdict"


def test_real_replies_still_row_the_finding() -> None:
    """The gate must not become a blanket refusal: a genuine panel run still converts."""
    calls, _ = _run_gate(
        tmp_path=_TMP(), rc="0", inbox_bumped=True,
        log_body="panel: 9/13 substantive; next payload budget 260,000\n")
    assert "recommendations.py" in calls and "add" in calls
    assert "9/13" in calls, "the row must carry the measured seat count for the triager"


def test_panel_crash_rows_nothing() -> None:
    """A non-zero exit with a stale inbox is also NO-QUORUM -- both conditions are required."""
    calls, log = _run_gate(
        tmp_path=_TMP(), rc="124", inbox_bumped=False, log_body="timeout\n")
    assert calls == ""
    assert "NO-QUORUM" in log


# pytest tmp_path is a fixture, but _run_gate is called from three tests that each need their own
# directory; a tiny factory keeps the helper signature honest without threading the fixture.
_TMPS: list[Path] = []


def _TMP() -> Path:
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="commit_audit_gate_"))
    _TMPS.append(d)
    return d


@pytest.fixture(autouse=True, scope="module")
def _cleanup():  # noqa: ANN202
    yield
    import shutil
    for d in _TMPS:
        shutil.rmtree(d, ignore_errors=True)
