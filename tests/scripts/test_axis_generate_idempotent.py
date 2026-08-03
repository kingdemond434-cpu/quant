"""PRE-REGISTERING IS AN ACT, AND RE-RUNNING MUST NOT REPEAT IT.

`scripts/run_axis_generate.py` appends pre-registered hypotheses to the research agenda. It had no
dedupe: every invocation added the same hypothesis again under a FRESH timestamp.

Run once by hand that is a duplicate row. Run from a cadence -- which is exactly where it was
about to be wired -- it is twenty-four fabricated pre-registration dates a day, forever. And the
pre-registration DATE is load-bearing under the two-stage discovery law, because it is the thing
that makes forward evidence forward: a hypothesis whose registration date keeps moving has no
out-of-sample period at all. The script would have quietly corrupted the evidence base it exists
to populate.

It was caught by a smoke test that added a dated hypothesis to the live agenda, which is also why
it had stayed hidden: nothing had ever run it twice.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENDA = ROOT / "research_agenda.json"
DOC = ROOT / "docs/research/AXIS_PREREGISTRATIONS.md"
CADENCE = ROOT / "data/cadence_state.json"


def _queue() -> list:
    return json.loads(AGENDA.read_text("utf-8")).get("queue_ranked_by_expected_research_roi", [])


def test_a_second_run_pre_registers_nothing_new() -> None:
    """The property, tested the only way that means anything: by actually running it twice."""
    backup = {p: p.read_text("utf-8") for p in (AGENDA, DOC, CADENCE) if p.exists()}
    env = {"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"}
    try:
        subprocess.run([sys.executable, "scripts/run_axis_generate.py"],
                       cwd=ROOT, capture_output=True, env=env, timeout=180, check=False)
        after_first = len(_queue())
        r = subprocess.run([sys.executable, "scripts/run_axis_generate.py"],
                           cwd=ROOT, capture_output=True, text=True, env=env, timeout=180,
                           check=False)
        after_second = len(_queue())
        assert after_second == after_first, (
            f"the queue grew from {after_first} to {after_second} on a REPEAT run -- every "
            "cadence tick would fabricate another pre-registration date")
        assert "skipped" in r.stdout, (
            "a run that pre-registered nothing must SAY so: 'nothing new' and 'the script did "
            "nothing' look identical from outside, and only the first is a healthy cycle")
    finally:
        for p, text in backup.items():
            p.write_text(text, "utf-8")


def test_the_dedupe_reads_both_the_queue_and_the_graveyard() -> None:
    """A hypothesis REJECTED by the EV gate is recorded in do_not_repeat, not the queue. Checking
    only the queue would re-register every rejected idea on the next run -- re-opening a decision
    the desk already made, and burning DSR budget on it twice."""
    src = (ROOT / "scripts/run_axis_generate.py").read_text("utf-8")
    assert "already = {" in src
    assert "for q in queue" in src and "for e in dnr" in src, (
        "the dedupe must consult the do_not_repeat list as well as the live queue")
