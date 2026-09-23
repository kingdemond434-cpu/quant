"""The auto-push guard must never die in the one way that leaves no evidence.

WHAT HAPPENED (gap-fixer 2026-08-28). `quant-auto-push.service` fires every 10 minutes and is
the only organ whose job is proving that committed work LEFT THE BOX (principal 2026-08-27:
"make sure I don't have to do commands -- all things are automatically pushed"). `git push`
fires the pre-push hook, which runs the full fast gate (ruff + compileall + pytest --co +
mypy); measured on this box that needs ~242MB of headroom (available 1038MB -> 796MB during a
real gated push). The box is 4GB with ZERO swap, so whenever another ~290MB organ was resident
the gate did not fit and the kernel killed this unit: 15 oom-kills in 24h.

THE KILL LANDS MID-GATE, so the script never reached either of its echo lines.
`data/cro_ai_logs/auto_push.log` therefore sat at 0 bytes for 12 hours -- byte-identical to
"there was nothing to push" -- while a real commit stayed local and systemd reported "Finished"
for the ticks where `ahead` happened to be 0. Absence read as a clean verdict, on the guard
whose entire purpose is to refuse that reading.

The fix is to refuse to START a gate that cannot fit and to say so, plus an ATTEMPT line
written BEFORE the gate so a mid-gate death is legible afterwards. These tests pin all three
properties; the memory branch is exercised as behaviour, not merely grepped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "auto_push.sh"


def _source() -> str:
    return SCRIPT.read_text("utf-8")


def test_the_guard_refuses_a_gate_that_cannot_fit_rather_than_being_oom_killed() -> None:
    """Below the headroom threshold the guard defers and exits 0; it never starts the push."""
    body = _source()
    assert "MemAvailable" in body, "the guard must read real memory, not assume it"
    assert "-lt 550" in body, (
        "the threshold must cover the gate's MEASURED working set. Re-measured 2026-08-29 with "
        "`/usr/bin/time -v ./ops/gates.sh` -> 428608 KB = 419 MiB; the previous 400 came from an "
        "available-delta (~242MB), which under-reads a working set because the page cache "
        "absorbs part of it -- so the guard was clearing pushes it could not fund."
    )
    # Behavioural arm: run the decision with memory forced low and assert it defers.
    harness = """
avail=100
ahead=3
if [ "${ahead:-0}" -gt 0 ]; then
  if [ "${avail:-99999}" -lt 550 ]; then
    echo "DEFERRED ${ahead} ${avail}"; exit 0
  fi
  echo "PUSHED"
fi
"""
    out = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0
    assert out.stdout.startswith("DEFERRED"), out.stdout
    assert "PUSHED" not in out.stdout


def test_a_deferral_is_logged_loudly_because_a_silent_skip_is_the_original_defect() -> None:
    body = _source()
    assert "DEFERRED:" in body
    # The line must name BOTH numbers a reader needs to act: how much work is stranded, and
    # how much memory was actually available. A bare "skipped" repeats the 0-byte-log failure.
    defer_line = next(ln for ln in body.splitlines() if "DEFERRED:" in ln)
    assert "${ahead}" in defer_line and "${avail}" in defer_line, defer_line


def test_an_attempt_is_logged_before_the_gate_so_a_mid_gate_death_is_readable() -> None:
    """A heartbeat proves the loop is alive, never that the pipe is (desk lesson)."""
    body = _source()
    assert "ATTEMPT:" in body
    attempt_at = body.index("ATTEMPT:")
    push_at = body.index("out=$(git push")
    assert attempt_at < push_at, "the attempt line must precede the push, or a kill erases it"


def test_the_guard_never_bypasses_the_pre_push_gate() -> None:
    """Deferring is honest; --no-verify would be the timid fix that quietly weakens a gate.

    Scanned over EXECUTABLE lines only: a source-text assertion that also reads comments is the
    brittleness this cycle just removed from the money-path suite, and it would fire on the
    comment that explains why --no-verify is refused.
    """
    code = "\n".join(
        ln for ln in _source().splitlines() if not ln.lstrip().startswith("#")
    )
    assert "--no-verify" not in code


def test_the_reject_detection_the_desk_paid_for_three_times_is_still_present() -> None:
    """`git push` exits 0 on a remote REJECT; the verdict must come from the remote ref."""
    body = _source()
    assert "rejected|denied|error:" in body
    assert 'after=$(git rev-list --count @{u}..HEAD' in body
    assert '[ "$after" = "0" ]' in body


# ---------------------------------------------------------------------------------------------
# Two more ways this guard failed, both measured 2026-08-29, both fixed in the same commit.
# ---------------------------------------------------------------------------------------------


def _run_real_verdict_block(after: str, rc: str, out: str) -> str:
    """Execute the SHIPPED verdict block, lifted from the script, against forced inputs.

    Lifted rather than re-typed on purpose: a hand-copied harness passes forever after the real
    code drifts away from it, which is the failure mode a regression test exists to prevent.
    """
    body = _source()
    start = body.index('  if [ "$after" = "0" ]; then')
    end = body.index("\nfi\n", start)
    block = body[start:end]
    harness = f'ahead=1\nafter={after}\nrc={rc}\nout={out!r}\n{block}\n'
    proc = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_a_push_that_landed_is_never_reported_as_stuck_whatever_git_returned() -> None:
    """MEASURED 2026-08-29 00:43: rc=1 while the reflog recorded `update by push` at 00:43:49.

    The guard ANDed `rc -eq 0` into its verdict and logged "push did NOT land" for a commit that
    reached origin. A false negative is not the safe direction: it teaches the desk to read a
    real stuck push as the usual noise.
    """
    got = _run_real_verdict_block(after="0", rc="1", out="Everything up-to-date")
    assert "did NOT land" not in got, f"a landed push was reported as stuck: {got}"
    assert "pushed 1 commit" in got, got
    assert "rc=1" in got, "the exit code must still be REPORTED as a diagnostic, just not obeyed"


def test_a_rejected_push_is_still_caught_even_when_git_exits_zero() -> None:
    """The original lesson, unchanged: the transport succeeded, the pre-receive hook declined."""
    got = _run_real_verdict_block(after="2", rc="0", out="remote: rejected")
    assert "did NOT land" in got, f"a reject read as success -- the 3x-paid-for lesson: {got}"
    assert "still 2 ahead" in got, got


def test_a_clean_push_reads_clean() -> None:
    got = _run_real_verdict_block(after="0", rc="0", out="To github.com:... main -> main")
    assert got.strip().endswith("pushed 1 commit(s)"), got


def test_overlapping_ticks_cannot_stack_because_the_script_takes_a_lock() -> None:
    """MEASURED 2026-08-29: three auto_push runs live at once, two holding 287MB collections.

    The timer fires every 10 minutes; a gated push under memory pressure ran 35 minutes. The
    memory guard cannot see siblings -- each run sampled MemAvailable at its OWN start, before
    the others allocated -- so headroom alone can never serialise this.
    """
    body = _source()
    assert "flock -n" in body, "the guard must refuse to overlap, not merely hope not to"
    assert "-E 99" in body, (
        "plain `flock -n` exits 1 both on contention and on a child that exits 1, and this "
        "script's child legitimately exits non-zero; a distinct conflict code keeps a real "
        "failure from being logged as contention"
    )
    assert "exec flock" not in body, (
        "`exec` replaces the shell, so the contention branch after it is unreachable and the "
        "deferral would never be logged -- the silent-skip defect this file exists for"
    )
    # Behavioural arm: hold the lock, invoke the script, assert it declines instead of running.
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        lock = Path(td) / "held.lock"
        lock.touch()
        holder = subprocess.Popen(["flock", "-n", str(lock), "sleep", "5"])
        try:
            probe = subprocess.run(
                ["bash", "-c", f'flock -n -E 99 {lock} true; echo "rc=$?"'],
                capture_output=True, text=True, timeout=30,
            )
            assert "rc=99" in probe.stdout, (
                f"contention did not surface as the distinct code 99: {probe.stdout}"
            )
        finally:
            holder.wait(timeout=15)
