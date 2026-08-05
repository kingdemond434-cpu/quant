#!/usr/bin/env python3
"""R0237 -- FENCES MUST FAIL ON THE STATUSES THEY WERE BUILT TO CATCH, VIA THE EXIT CODE.

Two halves, because the row named two defects and only fixing one leaves the hole open.

HALF ONE -- the mapping itself. `libs.ops.fence_exit` inverts the map: a declared PASS set,
everything else fails. The tests below pin the property that matters -- an UNKNOWN status fails
-- because that is what makes the fix survive the next person to add a status.

HALF TWO -- the reason it survived for so long. Every existing fence test asserted
`rep["status"]` and NOT ONE asserted the process exit code, so the entire `main()` -> exit-code
path was untested repo-wide and a fence could report DARK in its body while exiting 0 to cron.
`test_no_fence_enumerates_failures` is the regression stop: it reads the source of every
`scripts/check_*.py` and fails if any of them goes back to the single-status idiom.

That meta-test is deliberately a SOURCE scan rather than a per-fence behavioural test. A
behavioural test only covers the fences someone remembered to write one for -- which is exactly
how eleven fences drifted into the same defect. The scan covers every file that exists now and
every file added later, with no registration step to forget (the L1.42 lesson: the mechanism has
to be the thing that cannot be skipped).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402

#: fence -> (declared pass set, artifact it writes, the field its exit code gates on). A fence is
#: driven end to end -- `python scripts/<fence>.py` -- so this asserts the real process exit code,
#: which is the only thing cron, systemd, the pre-push hook and CI ever read. The verdict is read
#: back from the ARTIFACT rather than scraped from stdout: the artifact is what every downstream
#: consumer reads, and the human-readable line is free to change wording without breaking a test.
_FENCES: dict[str, tuple[tuple[str, ...], str, str]] = {
    "check_organ_liveness": (("OK",), "data/organ_liveness.json", "status"),
    "check_mechanism_attribution": (("ATTRIBUTED",), "data/mechanism_attribution.json", "status"),
    "check_return_targeting": (("OK",), "data/return_targeting.json", "status"),
    "check_replacement_rate": (("OK", "BOOTSTRAPPING"), "data/replacement_rate.json", "status"),
    "check_calibration": (("OK",), "data/calibration_status.json", "status"),
    "check_conversion": (("OK", "REPAIR-MODE"), "data/conversion_status.json", "status"),
    "check_exploration": (("OK",), "data/exploration_status.json", "status"),
    # gates on `verdict`, not `status` -- see the note in the fence itself
    "check_change_window": (("ALLOW",), "data/change_window.json", "verdict"),
}

#: The idiom R0237 exists to kill: exactly one failing status named, everything else exits 0.
_SINGLE_STATUS_EXIT = re.compile(
    r"""return\s+\d+\s+if\s+\w+\[["'](?:status|verdict)["']\]\s*==\s*["'][A-Z-]+["']\s+else\s+0""")


def test_unknown_status_fails() -> None:
    """The whole point: a status nobody declared is a fence that did not measure."""
    assert fence_exit("SOMETHING-ADDED-NEXT-YEAR", {"OK"}) == FAIL
    assert fence_exit("UNMEASURED", {"OK"}) == FAIL
    assert fence_exit("OK", {"OK"}) == 0


def test_absent_status_fails() -> None:
    """A report built from a missing artifact hands us None -- that is a failure, not a pass."""
    assert fence_exit(None, {"OK"}) == FAIL
    assert fence_exit("", {"OK"}) == FAIL
    assert fence_exit({}, {"OK"}) == FAIL


def test_empty_pass_set_fails_everything() -> None:
    """No pass set declared -> nothing passes. Fail-closed has no exceptions here."""
    assert fence_exit("OK", frozenset()) == FAIL


@pytest.mark.parametrize("fence", sorted(_FENCES))
def test_fence_declares_its_pass_set(fence: str) -> None:
    """Each fence names what PASSES, in one visible place, and routes its exit through it."""
    passing = _FENCES[fence][0]
    mod = __import__(f"scripts.{fence}", fromlist=["_PASSING"])
    assert set(mod._PASSING) == set(passing), (
        f"{fence}: pass set drifted from what this test pins. Widening a pass set is a real "
        f"decision -- change it here too, with the reason, or the fence quietly got weaker.")


@pytest.mark.parametrize("fence", sorted(_FENCES))
def test_fence_exit_code_matches_its_own_verdict(fence: str) -> None:
    """END TO END, as the process. THIS is the assertion no fence test had.

    Run the fence for real and require the exit code to agree with the verdict it published: 0 iff
    that verdict is in the declared pass set. Before R0237 five of these eight would have written a
    failing status into their artifact and exited 0 -- green to every consumer able to act on it.
    """
    passing, artifact, field = _FENCES[fence]
    proc = subprocess.run([sys.executable, f"scripts/{fence}.py"],
                          cwd=_ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode in (0, FAIL), (
        f"{fence} exited {proc.returncode} -- a fence crash is not a verdict:\n"
        f"{proc.stderr[-2000:]}")
    rep = json.loads((_ROOT / artifact).read_text("utf-8"))
    verdict = rep.get(field)
    expected = 0 if verdict in passing else FAIL
    assert proc.returncode == expected, (
        f"{fence} published {field}={verdict!r} against pass set {sorted(passing)}, so it should "
        f"have exited {expected} -- it exited {proc.returncode}. A fence that disagrees with its "
        f"own artifact is the R0237 defect.")


def test_no_fence_enumerates_failures() -> None:
    """REGRESSION STOP, repo-wide, with nothing to register and nothing to remember.

    Any `scripts/check_*.py` that goes back to `return 2 if status == "X" else 0` sends every
    other status -- including every blind one -- down the `else 0` path. Route it through
    `fence_exit` with a declared pass set instead.
    """
    offenders = [
        p.relative_to(_ROOT).as_posix()
        for p in sorted((_ROOT / "scripts").glob("check_*.py"))
        if _SINGLE_STATUS_EXIT.search(p.read_text("utf-8", errors="ignore"))
    ]
    assert not offenders, (
        "single-status exit map (R0237) in: " + ", ".join(offenders)
        + " -- these exit 0 on every status they do not name, including UNMEASURED. Use "
          "libs.ops.fence_exit.fence_exit(status, _PASSING).")
